#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[1]
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from scripts.launch_backend_config_preflight import has_failures as backend_has_failures
from scripts.launch_backend_config_preflight import run_checks as run_backend_config_checks
from scripts.launch_backend_config_preflight import summarize as summarize_backend_findings


VERSION_ROUTE = "/v1/editing/version"
DEFAULT_WORKER_BASE_URL = "https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev"
EXPECTED_IOS_BUNDLE_ID = "atrak.charlie.hoopsclips"
EXPECTED_IOS_MARKETING_VERSION = "1.0.0"
EXPECTED_IOS_BUILD_NUMBER = "4"
KNOWN_CONFLICTING_BUNDLE_IDS = ("app.rork.hoopshighlights-ai",)
REQUIRED_FEATURE_FLAGS = (
    "aiEditEnabled",
    "aiEditLiveRenderEnabled",
    "aiEditRevisionEnabled",
    "aiEditTemplatePackEnabled",
)
REQUIRED_DEPLOY_SECRET_INPUTS = (
    "CLOUDFLARE_API_TOKEN",
    "GCP_WORKLOAD_IDENTITY_PROVIDER",
    "GCP_DEPLOY_SERVICE_ACCOUNT",
)
REQUIRED_DEPLOY_VARIABLE_INPUTS = (
    "GCP_PROJECT_ID",
    "GCP_REGION",
)
REQUIRED_IOS_UPLOAD_SECRET_INPUTS = (
    "HOOPS_DEVELOPMENT_TEAM",
    "HOOPS_REVENUECAT_API_KEY",
    "HOOPS_GOOGLE_CLIENT_ID",
    "HOOPS_GOOGLE_REVERSED_CLIENT_ID",
    "HOOPS_FIREBASE_AUTH_API_KEY",
    "HOOPS_SENTRY_DSN",
    "APP_STORE_CONNECT_KEY_ID",
    "APP_STORE_CONNECT_ISSUER_ID",
    "APP_STORE_CONNECT_API_KEY_BASE64",
)
REQUIRED_IOS_UPLOAD_VARIABLE_INPUTS = (
    "HOOPS_PRIVACY_POLICY_URL",
    "HOOPS_TERMS_OF_SERVICE_URL",
)
REQUIRED_IOS_UPLOAD_WORKFLOW_SNIPPETS = (
    "environment: staging",
    "ios/scripts/materialize_local_secrets.sh",
    "ios/scripts/verify_internal_staging_config.sh",
    "ios/HoopsClips/HoopsClips/Config/InternalStaging.xcconfig",
    "xcodebuild archive",
    "xcodebuild -exportArchive",
    "-authenticationKeyPath",
    "ios/exportOptions.testflight-internal.plist",
)
REQUIRED_MAIN_WORKFLOWS = (
    "Cloud Edit Deploy Preflight",
    "iOS Internal TestFlight Upload",
)
BLOCKER_DOCS = (
    (
        "docs/phase_edit7g_post_testflight_internal_smoke.md",
        "NO-GO for claiming post-install TestFlight proof",
        "Installed TestFlight post-install smoke remains unproven.",
    ),
    (
        "docs/phase_launch_doc_reconciliation.md",
        "Live staging Worker `GET /v1/editing/version` returned `404`",
        "Staging Worker editing version route is not proven live.",
    ),
    (
        "docs/phase_launch2_ci_deploy_token_unblock.md",
        "`CLOUDFLARE_API_TOKEN` is still missing",
        "Cloudflare deploy credential proof is still missing.",
    ),
    (
        "docs/phase_launch5_ios_kill_switch_status.md",
        "live staging Worker still returned `404`",
        "Live iOS kill-switch state is not proven through the Worker.",
    ),
)
PLACEHOLDER_VALUES = {"", "YOUR_TEAM_ID", "$(HOOPS_DEVELOPMENT_TEAM)"}
UUID_RE = re.compile(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$")


@dataclass(frozen=True)
class Finding:
    status: str
    check: str
    path: str
    detail: str


class Collector:
    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def pass_(self, check: str, path: str, detail: str) -> None:
        self.findings.append(Finding("pass", check, path, detail))

    def warn(self, check: str, path: str, detail: str) -> None:
        self.findings.append(Finding("warn", check, path, detail))

    def fail(self, check: str, path: str, detail: str) -> None:
        self.findings.append(Finding("fail", check, path, detail))


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    findings = run_checks(
        repo_root,
        worker_base_url=args.worker_base_url,
        archive_path=Path(args.archive_path).resolve() if args.archive_path else None,
        skip_live=args.skip_live,
        timeout_seconds=args.timeout_seconds,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "status": "fail" if has_failures(findings) else "pass",
                    "summary": summarize(findings),
                    "findings": [asdict(finding) for finding in findings],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print_text_report(findings)

    return 1 if has_failures(findings) else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "HoopClips internal TestFlight/App Store submission readiness preflight. "
            "Checks readiness evidence without reading or printing secret values."
        )
    )
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--worker-base-url", default=None, help="Override staging Worker base URL for live /v1/editing/version probe.")
    parser.add_argument("--archive-path", default=None, help="Optional .xcarchive or .ipa path to require for upload readiness.")
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="Timeout for the live Worker version probe.")
    parser.add_argument("--skip-live", action="store_true", help="Skip live Worker probe and report it as a warning.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable findings.")
    return parser.parse_args()


def run_checks(
    repo_root: Path,
    *,
    worker_base_url: str | None = None,
    archive_path: Path | None = None,
    skip_live: bool = False,
    timeout_seconds: float = 10.0,
) -> list[Finding]:
    collector = Collector()
    check_git_state(repo_root, collector)
    check_backend_config_preflight(repo_root, collector)
    check_ios_signing(repo_root, collector)
    check_export_options(repo_root, collector)
    check_bundle_id_references(repo_root, collector)
    check_upload_artifact(repo_root, collector, archive_path)
    check_connected_ios_device(collector)
    resolved_worker_base_url = worker_base_url or worker_base_url_from_internal_staging(repo_root) or DEFAULT_WORKER_BASE_URL
    check_live_worker_version(resolved_worker_base_url, collector, skip_live=skip_live, timeout_seconds=timeout_seconds)
    check_ci_deploy_inputs(collector)
    check_github_workflow_runs(collector)
    check_blocker_docs(repo_root, collector)
    check_submission_automation(repo_root, collector)
    check_ios_upload_inputs(collector)
    return collector.findings


def check_git_state(repo_root: Path, collector: Collector) -> None:
    result = run_git(repo_root, "status", "--porcelain=v1")
    if result is None:
        collector.warn("git status", "repo", "Could not inspect git status.")
        return

    tracked_changes: list[str] = []
    unrelated_untracked_xcode_roots: list[str] = []
    other_untracked: list[str] = []
    for line in result.splitlines():
        if not line:
            continue
        status = line[:2]
        path = line[3:]
        if status == "??":
            if path in {"HoopsClips.xcodeproj/", "HoopsHighlightsAI.xcodeproj/"}:
                unrelated_untracked_xcode_roots.append(path)
            else:
                other_untracked.append(path)
        else:
            tracked_changes.append(path)

    if tracked_changes:
        collector.fail("git tracked changes", "repo", "Tracked files are modified; finish, commit, or discard before submission.")
    else:
        collector.pass_("git tracked changes", "repo", "No tracked working-tree changes.")

    if unrelated_untracked_xcode_roots:
        collector.warn("untracked root xcode folders", "repo", "Unrelated root Xcode folders are present and must not be staged.")
    if other_untracked:
        collector.warn("untracked files", "repo", f"{len(other_untracked)} untracked path(s) exist; verify before submission.")
    if not unrelated_untracked_xcode_roots and not other_untracked:
        collector.pass_("untracked files", "repo", "No untracked files.")

    branch_result = run_git(repo_root, "branch", "--show-current")
    branch = branch_result.strip() if branch_result else ""
    if branch:
        collector.pass_("git branch", "repo", f"Current branch is {branch}.")
    else:
        collector.warn("git branch", "repo", "Could not resolve current branch.")


def check_backend_config_preflight(repo_root: Path, collector: Collector) -> None:
    backend_findings = run_backend_config_checks(repo_root)
    summary = summarize_backend_findings(backend_findings)
    detail = f"backend/config preflight pass={summary['pass']} warn={summary['warn']} fail={summary['fail']}."
    if backend_has_failures(backend_findings):
        collector.fail("backend config preflight", "scripts/launch_backend_config_preflight.py", detail)
    else:
        collector.pass_("backend config preflight", "scripts/launch_backend_config_preflight.py", detail)


def check_ios_signing(repo_root: Path, collector: Collector) -> None:
    project_path = repo_root / "ios/HoopsClips.xcodeproj/project.pbxproj"
    project_text = read_text(project_path)
    if project_text is None:
        collector.fail("ios project", rel(project_path, repo_root), "iOS Xcode project is missing.")
        return

    for needle, label in (
        (f'PRODUCT_BUNDLE_IDENTIFIER = "{EXPECTED_IOS_BUNDLE_ID}";', f"bundle id {EXPECTED_IOS_BUNDLE_ID}"),
        (f"MARKETING_VERSION = {EXPECTED_IOS_MARKETING_VERSION};", f"marketing version {EXPECTED_IOS_MARKETING_VERSION}"),
        (f"CURRENT_PROJECT_VERSION = {EXPECTED_IOS_BUILD_NUMBER};", f"build number {EXPECTED_IOS_BUILD_NUMBER}"),
        ("CODE_SIGN_STYLE = Automatic;", "automatic signing"),
        ('DEVELOPMENT_TEAM = "$(HOOPS_DEVELOPMENT_TEAM)";', "team resolved from HOOPS_DEVELOPMENT_TEAM"),
    ):
        if needle in project_text:
            collector.pass_("ios project setting", rel(project_path, repo_root), f"Project includes {label}.")
        else:
            collector.fail("ios project setting", rel(project_path, repo_root), f"Project is missing {label}.")

    local_secrets_path = repo_root / "ios/HoopsClips/HoopsClips/Config/LocalSecrets.xcconfig"
    local_values = parse_xcconfig_values(local_secrets_path)
    env_team = os.getenv("HOOPS_DEVELOPMENT_TEAM", "").strip()
    local_team = local_values.get("HOOPS_DEVELOPMENT_TEAM", "").strip() if local_values else ""
    if env_team or (local_team not in PLACEHOLDER_VALUES):
        collector.pass_("ios signing team", rel(local_secrets_path, repo_root), "Development team is configured without printing its value.")
    else:
        collector.fail("ios signing team", rel(local_secrets_path, repo_root), "HOOPS_DEVELOPMENT_TEAM is missing or placeholder.")


def check_export_options(repo_root: Path, collector: Collector) -> None:
    path = repo_root / "ios/exportOptions.testflight-internal.plist"
    if not path.exists():
        collector.fail("export options", rel(path, repo_root), "Internal TestFlight export options plist is missing.")
        return

    try:
        with path.open("rb") as handle:
            plist = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as error:
        collector.fail("export options", rel(path, repo_root), f"Could not parse export options: {error}.")
        return

    expectations = {
        "destination": "upload",
        "distributionBundleIdentifier": EXPECTED_IOS_BUNDLE_ID,
        "method": "app-store-connect",
        "signingStyle": "automatic",
        "testFlightInternalTestingOnly": True,
        "uploadSymbols": True,
    }
    for key, expected in expectations.items():
        if plist.get(key) == expected:
            collector.pass_("export options", rel(path, repo_root), f"{key} is configured for internal TestFlight upload.")
        else:
            collector.fail("export options", rel(path, repo_root), f"{key} must be {expected!r}.")

    if plist.get("teamID"):
        collector.pass_("export options team", rel(path, repo_root), "teamID is present without printing its value.")
    else:
        collector.fail("export options team", rel(path, repo_root), "teamID is missing.")


def check_bundle_id_references(repo_root: Path, collector: Collector) -> None:
    path = repo_root / "ios/docs/runbooks/rork-release-operator-handoff.md"
    text = read_text(path)
    if text is None:
        collector.warn("bundle id references", rel(path, repo_root), "Rork release handoff doc is missing.")
        return

    conflicts = [bundle_id for bundle_id in KNOWN_CONFLICTING_BUNDLE_IDS if bundle_id in text]
    if conflicts:
        collector.fail(
            "bundle id references",
            rel(path, repo_root),
            "Release handoff references a bundle ID that does not match the iOS project/export options; resolve the App Store Connect app record before submission.",
        )
    else:
        collector.pass_("bundle id references", rel(path, repo_root), f"Release handoff does not reference known conflicting bundle IDs.")


def check_upload_artifact(repo_root: Path, collector: Collector, archive_path: Path | None) -> None:
    candidates: list[Path]
    if archive_path is not None:
        candidates = [archive_path]
    else:
        candidates = default_upload_artifact_candidates(repo_root)

    existing = [path for path in candidates if path.exists()]
    valid: list[Path] = []
    metadata_failures: list[tuple[Path, str]] = []
    for path in existing:
        if is_xcarchive_path(path):
            failure = archive_metadata_failure(path)
            if failure:
                metadata_failures.append((path, failure))
            else:
                valid.append(path)
        elif path.suffix == ".ipa":
            valid.append(path)

    if valid:
        collector.pass_("upload artifact", "repo", f"{len(valid)} upload artifact candidate(s) found.")
    elif metadata_failures:
        failure_path, failure_detail = metadata_failures[0]
        collector.fail("upload artifact", rel(failure_path, repo_root), failure_detail)
    elif archive_path is not None:
        collector.fail("upload artifact", rel(archive_path, repo_root), "Requested archive/IPA path does not exist.")
    else:
        collector.fail("upload artifact", "repo", "No .xcarchive or .ipa upload artifact found under the expected build output locations.")


def check_connected_ios_device(collector: Collector) -> None:
    try:
        result = subprocess.run(
            ["xcrun", "devicectl", "list", "devices"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        collector.warn("connected ios device", "xcrun devicectl", "Could not inspect connected iOS devices.")
        return
    if result.returncode != 0:
        collector.warn("connected ios device", "xcrun devicectl", "devicectl did not return connected device state.")
        return

    devices = parse_devicectl_devices(result.stdout)
    available_iphones = [device for device in devices if device["model"].startswith("iPhone") and device["state"].lower() == "available"]
    unavailable_iphones = [device for device in devices if device["model"].startswith("iPhone") and device["state"].lower() != "available"]
    if available_iphones:
        collector.pass_("connected ios device", "xcrun devicectl", f"{len(available_iphones)} available iPhone device(s) detected for TestFlight smoke.")
    elif unavailable_iphones:
        states = ", ".join(sorted({device["state"] for device in unavailable_iphones}))
        collector.fail("connected ios device", "xcrun devicectl", f"iPhone device(s) detected but unavailable for install/smoke testing: {states}.")
    else:
        collector.fail("connected ios device", "xcrun devicectl", "No available physical iPhone detected for installed TestFlight smoke.")


def parse_devicectl_devices(output: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("Name ") or line.startswith("----"):
            continue
        parts = line.split()
        identifier_index = next((index for index, part in enumerate(parts) if UUID_RE.match(part)), None)
        if identifier_index is None or len(parts) <= identifier_index + 2:
            continue
        state = parts[identifier_index + 1]
        model = " ".join(parts[identifier_index + 2 :])
        identifier = parts[identifier_index]
        hostname = parts[identifier_index - 1] if identifier_index >= 1 else ""
        name = " ".join(parts[: max(0, identifier_index - 1)])
        devices.append(
            {
                "name": name,
                "hostname": hostname,
                "identifier": identifier,
                "state": state,
                "model": model,
            }
        )
    return devices


def is_xcarchive_path(path: Path) -> bool:
    return path.name.endswith(".xcarchive")


def archive_metadata_failure(path: Path) -> str | None:
    info_path = path / "Info.plist"
    try:
        with info_path.open("rb") as handle:
            plist = plistlib.load(handle)
    except (FileNotFoundError, OSError, plistlib.InvalidFileException):
        return "Archive metadata Info.plist is missing or unreadable."

    application_properties = plist.get("ApplicationProperties")
    if not isinstance(application_properties, dict):
        return "Archive metadata is missing ApplicationProperties."

    expectations = {
        "CFBundleIdentifier": EXPECTED_IOS_BUNDLE_ID,
        "CFBundleShortVersionString": EXPECTED_IOS_MARKETING_VERSION,
        "CFBundleVersion": EXPECTED_IOS_BUILD_NUMBER,
    }
    for key, expected in expectations.items():
        if application_properties.get(key) != expected:
            return f"Archive {key} does not match expected upload metadata."
    return None


def check_live_worker_version(worker_base_url: str, collector: Collector, *, skip_live: bool, timeout_seconds: float) -> None:
    endpoint = normalized_endpoint(worker_base_url, VERSION_ROUTE)
    endpoint_label = redacted_endpoint_label(endpoint)
    if skip_live:
        collector.warn("live worker version route", endpoint_label, "Live Worker probe skipped by request.")
        return

    request = Request(endpoint, headers={"Accept": "application/json", "User-Agent": "HoopClipsSubmissionPreflight/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status_code = response.getcode()
            body = response.read(256_000)
    except HTTPError as error:
        collector.fail("live worker version route", endpoint_label, f"Returned HTTP {error.code}; staging Worker must proxy editing /version before submission.")
        return
    except (OSError, URLError) as error:
        collector.fail("live worker version route", endpoint_label, f"Probe failed: {type(error).__name__}.")
        return

    if status_code != 200:
        collector.fail("live worker version route", endpoint_label, f"Returned HTTP {status_code}; expected 200.")
        return

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        collector.fail("live worker version payload", endpoint_label, "Response was not valid JSON.")
        return

    feature_flags = payload.get("featureFlags") if isinstance(payload, dict) else None
    if not isinstance(feature_flags, dict):
        collector.fail("live worker feature flags", endpoint_label, "Response did not include featureFlags.")
        return

    missing_flags = [flag for flag in REQUIRED_FEATURE_FLAGS if flag not in feature_flags]
    if missing_flags:
        collector.fail("live worker feature flags", endpoint_label, f"Missing feature flag(s): {', '.join(missing_flags)}.")
    else:
        collector.pass_("live worker feature flags", endpoint_label, "Worker returned non-secret AI Edit kill-switch state.")


def check_ci_deploy_inputs(collector: Collector) -> None:
    required = (*REQUIRED_DEPLOY_SECRET_INPUTS, *REQUIRED_DEPLOY_VARIABLE_INPUTS)
    github_secret_names = github_environment_names("secret")
    github_variable_names = github_environment_names("variable")
    github_names = github_secret_names | github_variable_names
    missing = [name for name in required if not os.getenv(name) and name not in github_names]
    if missing:
        collector.fail(
            "cloud deploy inputs",
            "environment",
            f"Missing required deploy input name(s): {', '.join(missing)}.",
        )
    else:
        collector.pass_("cloud deploy inputs", "environment", "Required deploy input names are present locally or in the GitHub staging environment without printing values.")


def check_github_workflow_runs(collector: Collector) -> None:
    try:
        result = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--repo",
                "charlie2233/rork-hoopshighlights-ai_Final",
                "--branch",
                "main",
                "--limit",
                "20",
                "--json",
                "workflowName,status,conclusion,createdAt,headSha,event",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        collector.warn("github workflow status", "GitHub Actions", "Could not inspect latest main-branch workflow runs.")
        return
    if result.returncode != 0:
        collector.warn("github workflow status", "GitHub Actions", "gh run list did not return workflow state.")
        return
    try:
        runs = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        collector.warn("github workflow status", "GitHub Actions", "gh run list returned invalid JSON.")
        return
    if not isinstance(runs, list):
        collector.warn("github workflow status", "GitHub Actions", "gh run list returned an unexpected payload.")
        return

    for workflow_name in REQUIRED_MAIN_WORKFLOWS:
        latest = next((run for run in runs if isinstance(run, dict) and run.get("workflowName") == workflow_name), None)
        if latest is None:
            collector.fail("github workflow status", workflow_name, "No recent main-branch workflow run was found.")
            continue
        status = str(latest.get("status") or "unknown")
        conclusion = str(latest.get("conclusion") or "unknown")
        created_at = str(latest.get("createdAt") or "unknown")
        if status == "completed" and conclusion == "success":
            collector.pass_("github workflow status", workflow_name, f"Latest main-branch run completed successfully at {created_at}.")
        else:
            collector.fail("github workflow status", workflow_name, f"Latest main-branch run status={status} conclusion={conclusion} at {created_at}.")


def github_environment_names(kind: str) -> set[str]:
    if kind == "secret":
        args = ["gh", "secret", "list", "--env", "staging", "--json", "name"]
    elif kind == "variable":
        args = ["gh", "variable", "list", "--env", "staging", "--json", "name"]
    else:
        return set()
    try:
        result = subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    except OSError:
        return set()
    if result.returncode != 0:
        return set()
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return set()
    if not isinstance(payload, list):
        return set()
    return {str(item.get("name")) for item in payload if isinstance(item, dict) and item.get("name")}


def check_blocker_docs(repo_root: Path, collector: Collector) -> None:
    for doc_path, marker, detail in BLOCKER_DOCS:
        path = repo_root / doc_path
        text = read_text(path)
        if text is None:
            collector.warn("blocker doc", doc_path, "Expected launch blocker doc is missing.")
            continue
        if marker in text:
            collector.fail("documented launch blocker", doc_path, detail)
        else:
            collector.pass_("documented launch blocker", doc_path, "Known blocker marker is absent.")


def check_submission_automation(repo_root: Path, collector: Collector) -> None:
    archive_workflow = repo_root / ".github/workflows/ios-testflight-upload.yml"
    fastlane_dir = repo_root / "fastlane"
    text = read_text(archive_workflow)
    if text is not None:
        missing_snippets = [snippet for snippet in REQUIRED_IOS_UPLOAD_WORKFLOW_SNIPPETS if snippet not in text]
        if missing_snippets:
            collector.fail("submission automation", rel(archive_workflow, repo_root), f"iOS upload workflow is missing required snippet(s): {', '.join(missing_snippets)}.")
        else:
            collector.pass_("submission automation", rel(archive_workflow, repo_root), "iOS upload workflow archives internal staging and uploads only through explicit workflow_dispatch.")
    elif fastlane_dir.exists():
        collector.pass_("submission automation", rel(fastlane_dir, repo_root), "fastlane directory exists.")
    else:
        collector.warn("submission automation", "repo", "No dedicated iOS upload workflow or fastlane lane found; submission likely requires manual Xcode/App Store Connect steps.")


def check_ios_upload_inputs(collector: Collector) -> None:
    required = (*REQUIRED_IOS_UPLOAD_SECRET_INPUTS, *REQUIRED_IOS_UPLOAD_VARIABLE_INPUTS)
    github_secret_names = github_environment_names("secret")
    github_variable_names = github_environment_names("variable")
    github_names = github_secret_names | github_variable_names
    missing = [name for name in required if not os.getenv(name) and name not in github_names]
    if missing:
        collector.fail("ios upload inputs", "environment", f"Missing required iOS upload input name(s): {', '.join(missing)}.")
    else:
        collector.pass_("ios upload inputs", "environment", "Required iOS upload input names are present locally or in the GitHub staging environment without printing values.")


def worker_base_url_from_internal_staging(repo_root: Path) -> str | None:
    path = repo_root / "ios/HoopsClips/HoopsClips/Config/InternalStaging.xcconfig"
    values = parse_xcconfig_values(path)
    raw = values.get("HOOPS_CLOUD_EDIT_BASE_URL") or values.get("HOOPS_CLOUD_ANALYSIS_BASE_URL")
    if not raw:
        return None
    return raw.replace("https:/$()/", "https://").strip()


def default_upload_artifact_candidates(repo_root: Path) -> list[Path]:
    roots = [
        repo_root / "ios/build",
        repo_root / "build",
        repo_root / "ios/archives",
        repo_root / "archives",
    ]
    candidates: list[Path] = []
    for root in roots:
        if root.exists():
            candidates.extend(root.rglob("*.xcarchive"))
            candidates.extend(root.rglob("*.ipa"))
    candidates.extend(repo_root.glob("*.xcarchive"))
    candidates.extend(repo_root.glob("*.ipa"))
    return candidates


def parse_xcconfig_values(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError):
        return {}

    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def normalized_endpoint(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def redacted_endpoint_label(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.netloc:
        return VERSION_ROUTE
    return f"{parsed.netloc}{parsed.path}"


def run_git(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError):
        return None


def has_failures(findings: list[Finding]) -> bool:
    return any(finding.status == "fail" for finding in findings)


def summarize(findings: list[Finding]) -> dict[str, int]:
    return {
        "pass": sum(1 for finding in findings if finding.status == "pass"),
        "warn": sum(1 for finding in findings if finding.status == "warn"),
        "fail": sum(1 for finding in findings if finding.status == "fail"),
    }


def print_text_report(findings: list[Finding]) -> None:
    summary = summarize(findings)
    print("HoopClips submission readiness preflight")
    print(f"pass={summary['pass']} warn={summary['warn']} fail={summary['fail']}")
    for finding in findings:
        print(f"[{finding.status.upper()}] {finding.check} ({finding.path}) - {finding.detail}")


def rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
