#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[1]
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from scripts.submission_readiness_preflight import (
    DEFAULT_WORKER_BASE_URL,
    REQUIRED_FEATURE_FLAGS,
    VERSION_ROUTE,
    redacted_endpoint_label,
)


DEFAULT_EDITING_VERSION_URL = "https://hoopclips-editing-staging-npya43jiia-uc.a.run.app/version"
USER_AGENT = "HoopClipsStagingVersionProbe/1.0"


@dataclass(frozen=True)
class EndpointProbe:
    name: Literal["worker", "editing"]
    endpoint: str
    status: Literal["pass", "fail"]
    httpStatus: int | None
    detail: str
    featureFlagKeys: list[str]
    gitSha: str | None
    backendModelVersion: str | None


@dataclass(frozen=True)
class VersionProbeReport:
    status: Literal["pass", "fail"]
    diagnosis: str
    worker: EndpointProbe
    editing: EndpointProbe


def run_probe(
    *,
    worker_base_url: str = DEFAULT_WORKER_BASE_URL,
    editing_version_url: str = DEFAULT_EDITING_VERSION_URL,
    timeout_seconds: float = 10.0,
    opener: Callable[[Request, float], tuple[int, bytes]] | None = None,
) -> VersionProbeReport:
    fetcher = opener or fetch_endpoint
    worker_endpoint = endpoint_with_path(worker_base_url, VERSION_ROUTE)
    editing_endpoint = endpoint_without_query(editing_version_url)
    worker = probe_endpoint("worker", worker_endpoint, timeout_seconds, fetcher)
    editing = probe_endpoint("editing", editing_endpoint, timeout_seconds, fetcher)
    diagnosis = diagnose(worker, editing)
    status = "pass" if worker.status == "pass" and editing.status == "pass" else "fail"
    return VersionProbeReport(status=status, diagnosis=diagnosis, worker=worker, editing=editing)


def probe_endpoint(
    name: Literal["worker", "editing"],
    endpoint: str,
    timeout_seconds: float,
    opener: Callable[[Request, float], tuple[int, bytes]],
) -> EndpointProbe:
    endpoint_label = redacted_endpoint_label(endpoint)
    request = Request(endpoint, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        http_status, body = opener(request, timeout_seconds)
    except HTTPError as error:
        error.close()
        return EndpointProbe(name, endpoint_label, "fail", error.code, f"Returned HTTP {error.code}.", [], None, None)
    except (OSError, URLError) as error:
        return EndpointProbe(name, endpoint_label, "fail", None, f"Probe failed: {type(error).__name__}.", [], None, None)

    if http_status != 200:
        return EndpointProbe(name, endpoint_label, "fail", http_status, f"Returned HTTP {http_status}; expected 200.", [], None, None)

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return EndpointProbe(name, endpoint_label, "fail", http_status, "Response was not valid JSON.", [], None, None)

    git_sha = str(payload.get("gitSha")) if isinstance(payload, dict) and payload.get("gitSha") is not None else None
    backend_model_version = (
        str(payload.get("backendModelVersion")) if isinstance(payload, dict) and payload.get("backendModelVersion") is not None else None
    )

    feature_flags = payload.get("featureFlags") if isinstance(payload, dict) else None
    if not isinstance(feature_flags, dict):
        return EndpointProbe(name, endpoint_label, "fail", http_status, "Response did not include featureFlags.", [], git_sha, backend_model_version)

    missing_flags = [flag for flag in REQUIRED_FEATURE_FLAGS if flag not in feature_flags]
    if missing_flags:
        return EndpointProbe(
            name,
            endpoint_label,
            "fail",
            http_status,
            f"Missing feature flag(s): {', '.join(missing_flags)}.",
            sorted(str(key) for key in feature_flags.keys()),
            git_sha,
            backend_model_version,
        )

    return EndpointProbe(
        name,
        endpoint_label,
        "pass",
        http_status,
        "Returned non-secret AI Edit feature-flag state.",
        sorted(str(key) for key in feature_flags.keys()),
        git_sha,
        backend_model_version,
    )


def fetch_endpoint(request: Request, timeout_seconds: float) -> tuple[int, bytes]:
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.getcode(), response.read(256_000)


def endpoint_with_path(base_url: str, path: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        return base_url.rstrip("/") + "/" + path.lstrip("/")
    base_path = parsed.path.rstrip("/")
    joined_path = f"{base_path}/{path.lstrip('/')}" if base_path else f"/{path.lstrip('/')}"
    return urlunparse((parsed.scheme, parsed.netloc, joined_path, "", "", ""))


def endpoint_without_query(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") or "/", "", "", ""))


def diagnose(worker: EndpointProbe, editing: EndpointProbe) -> str:
    if worker.status == "pass" and editing.status == "pass":
        return "staging_version_ready"
    if worker.httpStatus == 404 and editing.status == "fail" and editing.httpStatus == 200:
        return "worker_route_missing_and_editing_version_stale"
    if worker.httpStatus == 404 and editing.status == "pass":
        return "worker_route_stale_or_not_deployed"
    if worker.status == "fail" and editing.status == "pass":
        return "worker_proxy_blocked_but_editing_service_reachable"
    if worker.status == "pass" and editing.status == "fail":
        return "worker_proxy_ready_but_direct_editing_probe_failed"
    return "staging_version_unready"


def render_text(report: VersionProbeReport) -> str:
    lines = [
        "HoopClips staging version probe",
        f"status={report.status}",
        f"diagnosis={report.diagnosis}",
        "",
        render_endpoint(report.worker),
        render_endpoint(report.editing),
        "",
    ]
    return "\n".join(lines)


def render_endpoint(probe: EndpointProbe) -> str:
    flags = ", ".join(probe.featureFlagKeys) if probe.featureFlagKeys else "none"
    return "\n".join(
        [
            f"[{probe.status.upper()}] {probe.name} ({probe.endpoint})",
            f"  httpStatus={probe.httpStatus if probe.httpStatus is not None else 'unknown'}",
            f"  detail={probe.detail}",
            f"  gitSha={probe.gitSha or 'unknown'}",
            f"  backendModelVersion={probe.backendModelVersion or 'unknown'}",
            f"  featureFlagKeys={flags}",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe HoopClips staging version endpoints without printing secrets.")
    parser.add_argument("--worker-base-url", default=DEFAULT_WORKER_BASE_URL)
    parser.add_argument("--editing-version-url", default=DEFAULT_EDITING_VERSION_URL)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run_probe(
        worker_base_url=args.worker_base_url,
        editing_version_url=args.editing_version_url,
        timeout_seconds=args.timeout_seconds,
    )
    if args.json:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
    else:
        print(render_text(report), end="")
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
