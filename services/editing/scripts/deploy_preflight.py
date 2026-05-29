#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_GCP_SECRETS = [
    "HOOPS_EDITING_SERVICE_SECRET",
    "HOOPS_R2_ACCESS_KEY_ID",
    "HOOPS_R2_SECRET_ACCESS_KEY",
    "HOOPS_OPENAI_API_KEY",
]

SMOKE_ENV_KEYS = [
    "HOOPS_EDITING_BASE_URL",
    "HOOPS_EDITING_SERVICE_SECRET",
    "HOOPS_R2_ENDPOINT_URL",
    "HOOPS_R2_ACCESS_KEY_ID",
    "HOOPS_R2_SECRET_ACCESS_KEY",
]

DEFAULT_R2_ENDPOINT_URL = "https://78fb4442e6e37b2c46d7e539c6e79172.r2.cloudflarestorage.com"


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    detail: str


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[3]
    control_plane_dir = repo_root / "services" / "control-plane"
    report: dict[str, Any] = {
        "status": "pass",
        "project": args.project or None,
        "region": args.region,
        "serviceName": args.service_name,
        "artifactRepo": args.artifact_repo,
        "r2": {
            "sourceBucket": args.r2_source_bucket,
            "outputBucket": args.r2_output_bucket,
            "endpointConfigured": bool(args.r2_endpoint_url or os.getenv("HOOPS_R2_ENDPOINT_URL")),
        },
        "checks": [],
        "blockers": [],
        "warnings": [],
    }

    def check(name: str, ok: bool, detail: str, *, blocker: bool = False) -> None:
        report["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok and blocker:
            report["blockers"].append(detail)

    if not shutil.which("gcloud"):
        check("gcloud", False, "gcloud CLI is not installed or not on PATH.", blocker=True)
    else:
        check("gcloud", True, "gcloud CLI is available.")

    if not shutil.which("npx"):
        check("npx", False, "npx is not installed or not on PATH.", blocker=True)
    else:
        check("npx", True, "npx is available for wrangler commands.")

    project = args.project or active_gcloud_project()
    report["project"] = project or None
    if not project:
        check("gcloud-project", False, "No active gcloud project is configured.", blocker=True)
    else:
        check("gcloud-project", True, f"Active gcloud project is {project}.")

    active_account = active_gcloud_account()
    if not active_account:
        check("gcloud-auth", False, "No active gcloud account is configured.", blocker=True)
    else:
        check("gcloud-auth", True, "Active gcloud account is configured.")

    if project and shutil.which("gcloud"):
        artifact = run(
            [
                "gcloud",
                "artifacts",
                "repositories",
                "describe",
                args.artifact_repo,
                "--location",
                args.region,
                "--project",
                project,
                "--format=value(name)",
            ]
        )
        check(
            "artifact-registry",
            artifact.returncode == 0,
            f"Artifact Registry repo {args.artifact_repo} {'exists' if artifact.returncode == 0 else 'is missing'} in {args.region}.",
            blocker=True,
        )

        for secret_name in REQUIRED_GCP_SECRETS:
            secret = classify_secret_manager_secret(secret_name, project)
            check(
                f"secret-manager-{secret_name}",
                secret.ok,
                secret.detail,
                blocker=True,
            )

        service = run(
            [
                "gcloud",
                "run",
                "services",
                "describe",
                args.service_name,
                "--region",
                args.region,
                "--project",
                project,
                "--format=value(status.url)",
            ]
        )
        service_exists = service.returncode == 0 and bool(service.stdout.strip())
        check(
            "cloud-run-service",
            service_exists,
            f"Cloud Run service {args.service_name} {'exists' if service_exists else 'does not exist yet; first deploy can create it'}.",
            blocker=args.require_cloud_run_service,
        )
        if service_exists:
            report["cloudRunUrl"] = service.stdout.strip()

    endpoint = args.r2_endpoint_url or os.getenv("HOOPS_R2_ENDPOINT_URL")
    if not endpoint:
        check("r2-endpoint", False, "R2 endpoint URL is not configured; Cloud Build must receive _R2_ENDPOINT_URL.", blocker=True)
    else:
        check("r2-endpoint", True, "R2 endpoint URL is configured.")

    if args.r2_source_bucket == args.r2_output_bucket:
        report["warnings"].append("R2 source and output buckets are the same; this works, but staging usually uses uploads for source and results for render output.")

    whoami = run(["npx", "wrangler", "whoami"], cwd=control_plane_dir)
    if os.getenv("CLOUDFLARE_API_TOKEN"):
        wrangler = classify_wrangler_auth(whoami, token_present=True)
        check(
            "wrangler-auth",
            wrangler.ok,
            wrangler.detail,
            blocker=True,
        )
    else:
        wrangler = classify_wrangler_auth(whoami, token_present=False)
        check(
            "wrangler-auth",
            wrangler.ok,
            wrangler.detail,
            blocker=True,
        )
        if whoami.returncode == 0:
            report["warnings"].append("Wrangler deploy is using local OAuth; CI/automation still needs CLOUDFLARE_API_TOKEN.")

    missing_smoke_env = [key for key in SMOKE_ENV_KEYS if not os.getenv(key)]
    if missing_smoke_env:
        report["warnings"].append(
            "Live smoke env is incomplete; missing presence for: " + ", ".join(missing_smoke_env)
        )

    if report["blockers"]:
        report["status"] = "blocked"

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)

    return 1 if report["blockers"] else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight the HoopClips live cloud editing deploy without printing secrets.")
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT"))
    parser.add_argument("--region", default=os.getenv("HOOPS_EDITING_REGION", "us-central1"))
    parser.add_argument("--service-name", default=os.getenv("HOOPS_EDITING_SERVICE_NAME", "hoopclips-editing-staging"))
    parser.add_argument("--artifact-repo", default=os.getenv("HOOPS_ARTIFACT_REPO", "hoopsclips"))
    parser.add_argument("--r2-source-bucket", default=os.getenv("HOOPS_R2_SOURCE_BUCKET", "hoopsclips-uploads-staging"))
    parser.add_argument("--r2-output-bucket", default=os.getenv("HOOPS_R2_OUTPUT_BUCKET", "hoopsclips-results-staging"))
    parser.add_argument("--r2-endpoint-url", default=os.getenv("HOOPS_R2_ENDPOINT_URL", DEFAULT_R2_ENDPOINT_URL))
    parser.add_argument("--require-cloud-run-service", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def active_gcloud_project() -> str:
    result = run(["gcloud", "config", "get-value", "project", "--quiet"])
    if result.returncode != 0:
        return ""
    value = result.stdout.strip()
    return "" if value in {"", "(unset)"} else value


def active_gcloud_account() -> str:
    result = run(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
    if result.returncode != 0:
        return ""
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""


def classify_secret_manager_secret(secret_name: str, project: str) -> ProbeResult:
    secret = run(
        [
            "gcloud",
            "secrets",
            "describe",
            secret_name,
            "--project",
            project,
            "--format=value(name)",
        ]
    )
    if secret.returncode != 0:
        failure = classify_gcloud_failure(secret)
        if failure == "missing":
            return ProbeResult(False, f"Secret Manager secret {secret_name} is missing.")
        if failure == "permission":
            return ProbeResult(
                False,
                f"Secret Manager secret {secret_name} metadata is not readable by the deploy identity; grant Secret Manager Viewer plus Secret Manager Secret Accessor.",
            )
        return ProbeResult(
            False,
            f"Secret Manager secret {secret_name} could not be verified; inspect GCP Secret Manager access for this name.",
        )

    version = run(
        [
            "gcloud",
            "secrets",
            "versions",
            "describe",
            "latest",
            "--secret",
            secret_name,
            "--project",
            project,
            "--format=value(state)",
        ]
    )
    if version.returncode != 0:
        failure = classify_gcloud_failure(version)
        if failure == "missing":
            return ProbeResult(False, f"Secret Manager secret {secret_name} has no latest version.")
        if failure == "permission":
            return ProbeResult(
                False,
                f"Secret Manager secret {secret_name} latest version metadata is not readable by the deploy identity; grant Secret Manager Viewer plus Secret Manager Secret Accessor.",
            )
        return ProbeResult(False, f"Secret Manager secret {secret_name} latest version state could not be verified.")

    state = version.stdout.strip()
    if state == "ENABLED":
        return ProbeResult(True, f"Secret Manager secret {secret_name} exists and latest version is ENABLED.")
    if state:
        return ProbeResult(
            False,
            f"Secret Manager secret {secret_name} latest version is {state}; add or enable a latest version.",
        )
    return ProbeResult(False, f"Secret Manager secret {secret_name} latest version state is empty.")


def classify_gcloud_failure(result: subprocess.CompletedProcess[str]) -> str:
    text = f"{result.stdout}\n{result.stderr}".lower()
    if "permission_denied" in text or "permission denied" in text or "access denied" in text or "does not have permission" in text:
        return "permission"
    if "not_found" in text or "not found" in text or "not exist" in text or "could not be found" in text:
        return "missing"
    return "unknown"


def classify_wrangler_auth(result: subprocess.CompletedProcess[str], *, token_present: bool) -> ProbeResult:
    if result.returncode == 0:
        if token_present:
            return ProbeResult(True, "Wrangler auth is valid with CLOUDFLARE_API_TOKEN.")
        return ProbeResult(True, "Wrangler auth is valid through local OAuth. Set CLOUDFLARE_API_TOKEN for CI automation.")

    text = f"{result.stdout}\n{result.stderr}".lower()
    if token_present:
        if "invalid api token" in text or "authentication error" in text or "unable to authenticate" in text:
            return ProbeResult(False, "Wrangler auth failed because CLOUDFLARE_API_TOKEN was rejected.")
        if "permission" in text or "not authorized" in text or "unauthorized" in text or "scope" in text or "account" in text:
            return ProbeResult(
                False,
                "Wrangler auth failed because CLOUDFLARE_API_TOKEN is missing required account scope or permissions.",
            )
        return ProbeResult(False, "Wrangler auth failed with CLOUDFLARE_API_TOKEN; verify token account, scope, and expiration.")

    if "not logged in" in text or "not authenticated" in text or "login" in text:
        return ProbeResult(False, "CLOUDFLARE_API_TOKEN is not set and local Wrangler OAuth is not authenticated.")
    return ProbeResult(False, "CLOUDFLARE_API_TOKEN is not set and local Wrangler OAuth could not be verified.")


def run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=str(cwd) if cwd else None, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return subprocess.CompletedProcess(command, returncode=127, stdout="", stderr="command not found")


def print_human(report: dict[str, Any]) -> None:
    print(f"status: {report['status']}")
    print(f"project: {report.get('project') or 'missing'}")
    print(f"service: {report['serviceName']} ({report['region']})")
    print(f"artifact repo: {report['artifactRepo']}")
    print(f"r2 source bucket: {report['r2']['sourceBucket']}")
    print(f"r2 output bucket: {report['r2']['outputBucket']}")
    if report.get("cloudRunUrl"):
        print(f"cloud run url: {report['cloudRunUrl']}")
    print("\nchecks:")
    for item in report["checks"]:
        marker = "ok" if item["ok"] else "missing"
        print(f"- {marker}: {item['detail']}")
    if report["warnings"]:
        print("\nwarnings:")
        for warning in report["warnings"]:
            print(f"- {warning}")
    if report["blockers"]:
        print("\nblockers:")
        for blocker in report["blockers"]:
            print(f"- {blocker}")


if __name__ == "__main__":
    raise SystemExit(main())
