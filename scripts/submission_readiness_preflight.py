#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import shlex
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

from scripts.evaluate_team_highlight_accuracy import AccuracyThresholds
from scripts.launch_backend_config_preflight import has_failures as backend_has_failures
from scripts.launch_backend_config_preflight import run_checks as run_backend_config_checks
from scripts.launch_backend_config_preflight import summarize as summarize_backend_findings


VERSION_ROUTE = "/v1/editing/version"
DEFAULT_WORKER_BASE_URL = "https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev"
DEFAULT_EDITING_VERSION_URL = "https://hoopclips-editing-staging-npya43jiia-uc.a.run.app/version"
EXPECTED_IOS_BUNDLE_ID = "atrak.charlie.hoopsclips"
EXPECTED_IOS_MARKETING_VERSION = "1.0.0"
EXPECTED_IOS_BUILD_NUMBER = "18"
KNOWN_CONFLICTING_BUNDLE_IDS = ("app.rork.hoopshighlights-ai",)
REQUIRED_FEATURE_FLAGS = (
    "aiEditEnabled",
    "aiEditLiveRenderEnabled",
    "aiEditRevisionEnabled",
    "aiEditTemplatePackEnabled",
    "aiClipGptEditorEnabled",
    "aiClipGptPlanEditEnabled",
    "aiClipGptRevisionEnabled",
    "gptHighlightRerankerEnabled",
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
REQUIRED_PRODUCTION_CLOUD_URL_VARIABLE_INPUTS = (
    "HOOPS_CLOUD_ANALYSIS_BASE_URL",
    "HOOPS_CLOUD_EDIT_BASE_URL",
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
SECRET_GATED_DEPLOY_WORKFLOW_FILE = "cloud-edit-deploy-preflight.yml"
SECRET_GATED_DEPLOY_JOB_NAME = "Verify cloud edit deploy secrets"
IOS_TESTFLIGHT_UPLOAD_WORKFLOW_FILE = "ios-testflight-upload.yml"
GITHUB_ACTIONS_STARTABILITY_CONCLUSIONS = {"action_required", "startup_failure"}
TESTFLIGHT_UPLOAD_LOG_MARKERS = (
    "Upload succeeded.",
    "Uploaded HoopsClips",
    "Internal TestFlight upload command completed",
)
TESTFLIGHT_SIGNING_FAILURE_MARKERS = (
    "maximum number of certificates",
    "No profiles for 'atrak.charlie.hoopsclips' were found",
    "requires a development team",
    "conflicting provisioning settings",
)
IOS_UPLOAD_RELEVANT_PREFIXES = (
    ".github/workflows/ios-testflight-upload.yml",
    "ios/HoopsClips/",
    "ios/HoopsClips.xcodeproj/",
    "ios/HoopsClipsTests/",
    "ios/HoopsClipsUITests/",
    "ios/exportOptions.testflight-internal.plist",
    "ios/exportOptions.testflight-internal.example.plist",
    "ios/scripts/",
    "ios/tools/",
)
CLOUD_DEPLOY_RELEVANT_PREFIXES = (
    ".github/workflows/cloud-edit-deploy-preflight.yml",
    "scripts/",
    "services/control-plane/",
    "services/editing/",
    "services/inference/",
)
EDITING_SERVICE_DEPLOY_RELEVANT_PREFIXES = (
    "ios/backend/",
    "ios/HoopsClips/HoopsClips/Resources/Audio/",
    "services/editing/",
)
REQUIRED_MAIN_WORKFLOW_RELEVANT_PREFIXES = {
    "Cloud Edit Deploy Preflight": CLOUD_DEPLOY_RELEVANT_PREFIXES,
    "iOS Internal TestFlight Upload": IOS_UPLOAD_RELEVANT_PREFIXES,
}
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
    (
        "docs/phase_launch_release_secrets_cloud_url_blocker_2026-06-03.md",
        "Release Secrets Preflight: `26884199422` failed",
        "Release Secrets Preflight is still blocked by missing production cloud URL variables.",
    ),
    ('docs/phase_launch_production_cloud_urls_handoff_2026-06-03.md',
     'The required production cloud URL variables are missing:',
     'Production cloud URL handoff still documents missing production cloud URL variables.'),
    ('docs/phase_launch_accuracy_reviewer_handoff_2026-06-03.md',
     '- Complete clips: `0`',
     'Human-reviewed accuracy handoff still documents 0/54 complete label coverage.'),
    ('docs/phase_launch_installed_testflight_smoke_handoff_2026-06-03.md',
     'Installed TestFlight smoke: `unproven`',
     'Installed TestFlight smoke handoff still documents unproven trusted-device smoke.'),
    ('docs/phase_launch_build15_signing_handoff_2026-06-03.md',
     'Signed iOS archive preflight is not green for build `15` yet.',
     'Apple signing handoff still documents blocked signed archive/TestFlight upload proof.'),
    ('docs/phase_launch_testflight_archive_smoke_live_recheck_2026-06-03.md',
     'Do not treat green codecheck or deploy dry-run status as installed TestFlight proof.',
     'TestFlight archive/smoke live recheck still documents skipped archive and unproven installed smoke.'),
    ('docs/phase_launch_release_owner_gate_handoff_2026-06-03.md',
     'This release-owner handoff remains open until production cloud URLs/secrets, Release Secrets Preflight, signed archive/upload, installed TestFlight smoke, and human labels are all proven current on the launch branch.',
     'Release-owner gate handoff still documents unresolved external launch gates.'),
    ('docs/phase_launch_submission_readiness_index_2026-06-03.md',
     'Green codecheck, green dry-run deploy preflight, generated local label-review tools, or GPT draft labels are not launch evidence by themselves.',
     'Submission readiness index still documents unresolved launch proof requirements.'),
    ('docs/phase_launch_current_tip_external_gate_handoff_2026-06-03.md',
     'This current-tip proof does not close production cloud URLs/secrets,',
     'Current-tip external gate handoff still documents unresolved launch gates.'),
    ('docs/phase_launch_production_gate_live_recheck_2026-06-03.md',
     'Production cloud cutover remains blocked',
     'Production gate live recheck still documents unresolved cloud URL/secrets readiness.'),
    ('docs/phase_launch_label_bundle_video_source_handoff_2026-06-03.md',
     'complete clips: `0/54`',
     'Label bundle handoff still documents unresolved human-reviewed accuracy labels.'),
    ('docs/phase_launch_label_review_execution_handoff_2026-06-03.md',
     'complete clips: `0/54`',
     'Label review execution handoff still documents unresolved human-reviewed accuracy labels.'),
)
DEFAULT_TEAM_ACCURACY_MANIFEST = Path("artifacts/team_highlight_accuracy_manifest.json")
DEFAULT_LABELING_BUNDLE_DIR = Path("artifacts/team_highlight_labeling_bundle")
DEFAULT_LABELING_BUNDLE_METADATA = DEFAULT_LABELING_BUNDLE_DIR / "bundle_metadata.json"
DEFAULT_LABELING_BUNDLE_STATUS = DEFAULT_LABELING_BUNDLE_DIR / "label_status.json"
DEFAULT_LABELING_BUNDLE_NEXT_STEPS = DEFAULT_LABELING_BUNDLE_DIR / "next_steps.md"
DEFAULT_LABELING_BUNDLE_REVIEW_PAGE = DEFAULT_LABELING_BUNDLE_DIR / "team_highlight_label_review.html"
LABELING_BUNDLE_REVIEW_PAGE_MARKERS = (
    ("Next close review", "close-review jump"),
    ("J/L scrub", "video scrub shortcuts"),
    ("function scrubVideosForCard", "synced video scrub controls"),
    ("Download launch-ready labels", "launch-ready label export guard"),
    ("Launch evidence checklist", "launch evidence checklist"),
    ("needsLabel=false", "launch needsLabel requirement"),
    ("reviewedByHuman=true", "launch human-review requirement"),
)
LABELING_BUNDLE_NEXT_STEPS_MARKERS = (
    ("Use `Next close review` first", "close-review first instruction"),
    ("`J/L` scrub back/forward", "scrub shortcut instruction"),
    ("data-entry help only", "GPT draft data-entry-only warning"),
    ("not evidence until you watch the video and mark reviewed", "GPT draft human-review evidence warning"),
    ("Download launch-ready labels", "launch-ready label export instruction"),
    ("Launch Evidence Checklist", "launch evidence checklist"),
    ("expected.teamId", "expected team checklist item"),
    ("expected.isHighlight", "expected highlight checklist item"),
    ("expected.eventType", "expected event checklist item"),
    ("expected.outcome", "expected outcome checklist item"),
    ("final bundle is applied without `--allow-incomplete`", "final complete-bundle warning"),
)
REQUIRED_LABEL_REVIEW_FIELDS = (
    "expected.teamId",
    "expected.isHighlight",
    "expected.eventType",
    "expected.outcome",
    "needsLabel=false",
    "reviewedByHuman=true",
)
PLACEHOLDER_VALUES = {"", "YOUR_TEAM_ID", "$(HOOPS_DEVELOPMENT_TEAM)"}
UUID_RE = re.compile(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$")
TEAM_ACCURACY_THRESHOLD_TO_METRIC = (
    ("selectedTeamPrecision", "selectedTeamPrecision"),
    ("selectedTeamEvidenceQuality", "selectedTeamEvidenceQuality"),
    ("selectedTeamRecallWithUncertain", "selectedTeamRecallWithUncertain"),
    ("highlightPrecision", "highlightPrecision"),
    ("highlightRecall", "highlightRecall"),
    ("defensiveEventRecall", "defensiveEventRecall"),
    ("clipTimingQuality", "clipTimingQuality"),
    ("shotOutcomeEvidenceQuality", "shotOutcomeEvidenceQuality"),
    ("minCases", "caseCount"),
    ("minScoredClips", "clipCount"),
    ("minSelectedTeamHighlights", "selectedTeamHighlightCount"),
    ("minShotOutcomeEvidenceClips", "shotOutcomeEvidenceClipCount"),
    ("minMadeShotOutcomeEvidenceClips", "madeShotOutcomeEvidenceClipCount"),
    ("minMissedShotOutcomeEvidenceClips", "missedShotOutcomeEvidenceClipCount"),
    ("minOpponentHighlights", "opponentHighlightCount"),
    ("minNegativeClips", "negativeClipCount"),
    ("minBadWindowNegatives", "badWindowNegativeCount"),
    ("minUncertainReviewClips", "uncertainReviewCount"),
    ("minSelectedTeamDefensiveEvents", "defensiveEventCount"),
    ("minSelectedTeamBlocks", "selectedTeamBlockCount"),
    ("minSelectedTeamSteals", "selectedTeamStealCount"),
    ("minSelectedTeamForcedTurnovers", "selectedTeamForcedTurnoverCount"),
    ("minSelectedTeamDefensiveStops", "selectedTeamDefensiveStopCount"),
    ("minAllTeamsCases", "allTeamsCaseCount"),
)
EXPECTED_TEAM_ACCURACY_INPUT_SCHEMA = "team-highlight-eval-v1"
EXPECTED_TEAM_ACCURACY_INPUT_SOURCE = "real_cloud_analysis_with_manual_labels"
DRAFT_TEAM_ACCURACY_REPORT_PATH_MARKERS = (
    "temp_mapped_draft",
    "draft",
    "drafts",
    "gpt_draft",
)


@dataclass(frozen=True)
class Finding:
    status: str
    check: str
    path: str
    detail: str


@dataclass(frozen=True)
class GithubEnvironmentNameLookup:
    names: set[str]
    unavailable_detail: str | None = None


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
    labeling_bundle_dir = resolve_repo_path(repo_root, Path(args.labeling_bundle_dir))
    findings = run_checks(
        repo_root,
        worker_base_url=args.worker_base_url,
        editing_version_url=args.editing_version_url,
        archive_path=Path(args.archive_path).resolve() if args.archive_path else None,
        team_accuracy_report_path=Path(args.team_accuracy_report).resolve() if args.team_accuracy_report else None,
        labeling_bundle_dir=labeling_bundle_dir,
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
    parser.add_argument("--editing-version-url", default=DEFAULT_EDITING_VERSION_URL, help="Override direct editing Cloud Run /version URL for live version drift probe.")
    parser.add_argument("--archive-path", default=None, help="Optional .xcarchive or .ipa path to require for upload readiness.")
    parser.add_argument(
        "--team-accuracy-report",
        default=None,
        help="Path to a JSON report from `python3 -m scripts.evaluate_team_highlight_accuracy <labels.json> --json` using launch-grade default thresholds.",
    )
    parser.add_argument(
        "--labeling-bundle-dir",
        default=str(DEFAULT_LABELING_BUNDLE_DIR),
        help=(
            "Labeling bundle directory to use when explaining a missing --team-accuracy-report. "
            "This does not weaken the launch accuracy gate; it only points the blocker message at the current review bundle."
        ),
    )
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="Timeout for the live Worker version probe.")
    parser.add_argument("--skip-live", action="store_true", help="Skip live Worker probe and report it as a warning.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable findings.")
    return parser.parse_args()


def run_checks(
    repo_root: Path,
    *,
    worker_base_url: str | None = None,
    editing_version_url: str = DEFAULT_EDITING_VERSION_URL,
    archive_path: Path | None = None,
    team_accuracy_report_path: Path | None = None,
    labeling_bundle_dir: Path = DEFAULT_LABELING_BUNDLE_DIR,
    skip_live: bool = False,
    timeout_seconds: float = 10.0,
) -> list[Finding]:
    collector = Collector()
    check_git_state(repo_root, collector)
    check_backend_config_preflight(repo_root, collector)
    check_team_highlight_accuracy_report(repo_root, collector, team_accuracy_report_path, labeling_bundle_dir)
    check_ios_signing(repo_root, collector)
    check_export_options(repo_root, collector)
    check_bundle_id_references(repo_root, collector)
    check_upload_artifact(repo_root, collector, archive_path)
    check_connected_ios_device(collector)
    resolved_worker_base_url = worker_base_url or worker_base_url_from_internal_staging(repo_root) or DEFAULT_WORKER_BASE_URL
    check_live_worker_version(resolved_worker_base_url, collector, skip_live=skip_live, timeout_seconds=timeout_seconds)
    check_live_editing_version(editing_version_url, collector, repo_root=repo_root, skip_live=skip_live, timeout_seconds=timeout_seconds)
    check_ci_deploy_inputs(collector)
    check_production_cloud_url_inputs(collector)
    check_github_workflow_runs(repo_root, collector)
    check_secret_gated_deploy_preflight(repo_root, collector)
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


def check_team_highlight_accuracy_report(
    repo_root: Path,
    collector: Collector,
    report_path: Path | None,
    labeling_bundle_dir: Path = DEFAULT_LABELING_BUNDLE_DIR,
) -> None:
    check_name = "team highlight accuracy evidence"
    if report_path is None:
        collector.fail(
            check_name,
            "scripts/evaluate_team_highlight_accuracy.py",
            missing_team_accuracy_report_detail(repo_root, labeling_bundle_dir),
        )
        return

    display_path = rel(report_path, repo_root)
    try:
        with report_path.open("r", encoding="utf-8") as handle:
            report = json.load(handle)
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        collector.fail(check_name, display_path, f"Could not read team accuracy JSON report: {type(error).__name__}.")
        return
    if not isinstance(report, dict):
        collector.fail(check_name, display_path, "Team accuracy report must be a JSON object.")
        return

    status = str(report.get("status") or "").strip().lower()
    metrics = report.get("metrics")
    thresholds = report.get("thresholds")
    evidence = report.get("evidence")
    if not isinstance(metrics, dict) or not isinstance(thresholds, dict):
        collector.fail(check_name, display_path, "Report must include metrics and thresholds objects from the evaluator.")
        return
    if not isinstance(evidence, dict):
        collector.fail(
            check_name,
            display_path,
            "Report must include evaluator evidence from a real cloud-analysis/manual-label payload.",
        )
        return

    failures: list[str] = []
    draft_path_marker = draft_team_accuracy_report_path_marker(report_path)
    if draft_path_marker:
        failures.append(f"report path includes temporary/draft marker {draft_path_marker}")
    if status != "pass":
        failures.append(f"report status is {status or 'missing'}")

    default_thresholds = asdict(AccuracyThresholds())
    default_min_cases = int(default_thresholds["minCases"])
    if evidence.get("inputSchemaVersion") != EXPECTED_TEAM_ACCURACY_INPUT_SCHEMA:
        failures.append("evidence inputSchemaVersion is not team-highlight-eval-v1")
    if evidence.get("inputSource") != EXPECTED_TEAM_ACCURACY_INPUT_SOURCE:
        failures.append("evidence inputSource is not real cloud analysis with manual labels")
    evidence_case_count = number_or_none(evidence.get("caseCount"))
    metric_case_count = number_or_none(metrics.get("caseCount"))
    if evidence_case_count is None or metric_case_count is None or int(evidence_case_count) != int(metric_case_count):
        failures.append("evidence caseCount does not match metrics caseCount")
    distinct_video_count = number_or_none(evidence.get("distinctVideoCount"))
    if distinct_video_count is None or distinct_video_count < default_min_cases:
        failures.append(f"distinctVideoCount is below launch default {default_min_cases}")
    for evidence_name in (
        "casesMissingTeamMode",
        "casesMissingCaseId",
        "casesMissingVideoId",
        "casesMissingSelectedTeamId",
        "casesMissingAnalysisJobId",
        "casesMissingTeamScanJobId",
        "casesMissingDetectedTeamOptions",
        "casesMissingSelectedTeamColorLabel",
        "casesMissingSelectedTeamDetectedOption",
    ):
        missing_count = number_or_none(evidence.get(evidence_name))
        if missing_count is None:
            failures.append(f"missing evidence {evidence_name}")
        elif missing_count > 0:
            failures.append(f"{evidence_name} must be 0")

    for threshold_name, metric_name in TEAM_ACCURACY_THRESHOLD_TO_METRIC:
        default_value = number_or_none(default_thresholds.get(threshold_name))
        threshold_value = number_or_none(thresholds.get(threshold_name))
        metric_value = number_or_none(metrics.get(metric_name))
        if default_value is None:
            continue
        if threshold_value is None:
            failures.append(f"missing threshold {threshold_name}")
        elif threshold_value + 1e-9 < default_value:
            failures.append(f"{threshold_name} threshold {threshold_value:g} is below launch default {default_value:g}")
        if metric_value is None:
            failures.append(f"missing metric {metric_name}")
        elif metric_value + 1e-9 < default_value:
            failures.append(f"{metric_name} {metric_value:g} is below launch default {default_value:g}")

    if failures:
        detail = "; ".join(failures[:8]) + ("." if len(failures) <= 8 else "; additional failures omitted.")
        if draft_path_marker:
            hint = team_labeling_bundle_hint(repo_root, labeling_bundle_dir)
            if hint:
                detail = f"{detail} {hint}"
        collector.fail(check_name, display_path, detail)
        return

    collector.pass_(
        check_name,
        display_path,
        (
            "Launch-grade 85% report passed with default-or-stricter thresholds, "
            f"{int(metrics['caseCount'])} case(s), {int(metrics['clipCount'])} clip(s), "
            f"{int(evidence['distinctVideoCount'])} distinct video(s), "
            f"{int(metrics['opponentHighlightCount'])} opponent highlight(s), "
            f"{int(metrics['badWindowNegativeCount'])} bad-window negative(s), and "
            f"{int(metrics['uncertainReviewCount'])} uncertain review clip(s)."
        ),
    )


def draft_team_accuracy_report_path_marker(report_path: Path) -> str | None:
    for part in report_path.parts:
        normalized = part.lower()
        stem = Path(normalized).stem
        if normalized in DRAFT_TEAM_ACCURACY_REPORT_PATH_MARKERS or stem in DRAFT_TEAM_ACCURACY_REPORT_PATH_MARKERS:
            return part
        if stem.startswith("draft_") or stem.endswith("_draft"):
            return part
    return None


def missing_team_accuracy_report_detail(repo_root: Path, labeling_bundle_dir: Path = DEFAULT_LABELING_BUNDLE_DIR) -> str:
    base = (
        "Missing --team-accuracy-report from a launch-grade labeled footage run; "
        "85% selected-team/highlight quality is unproven."
    )
    hint = team_labeling_bundle_hint(repo_root, labeling_bundle_dir)
    return f"{base} {hint}" if hint else base


def team_labeling_bundle_hint(repo_root: Path, labeling_bundle_dir: Path = DEFAULT_LABELING_BUNDLE_DIR) -> str:
    bundle_dir = resolve_repo_path(repo_root, labeling_bundle_dir)
    metadata_path = bundle_dir / "bundle_metadata.json"
    status_path = bundle_dir / "label_status.json"
    next_steps_path = bundle_dir / "next_steps.md"
    metadata = read_json_object(metadata_path)
    status = read_json_object(status_path)

    if metadata is not None or status is not None:
        source = status or metadata or {}
        complete = number_or_none(source.get("completeClipCount"))
        total = number_or_none(source.get("clipCount"))
        incomplete = number_or_none(source.get("incompleteClipCount"))
        review_page = metadata_path_from_payload(repo_root, metadata, "reviewPage", bundle_dir / "team_highlight_label_review.html")
        status_label = metadata_path_from_payload(repo_root, metadata, "labelStatus", bundle_dir / "label_status.json")
        progress = ""
        if complete is not None and total is not None:
            progress = f" Existing labeling bundle progress: {int(complete)}/{int(total)} clips complete"
            if incomplete is not None:
                progress += f", {int(incomplete)} remaining"
            progress += "."
        draft_detail = labeling_bundle_draft_detail(metadata)
        staleness_detail = labeling_bundle_staleness_detail(repo_root, bundle_dir, review_page, next_steps_path, metadata, status)
        launch_gate_detail = labeling_bundle_launch_gate_detail(status)
        return (
            f"{progress} Continue human review at {rel(review_page, repo_root)}; "
            f"status: {rel(status_label, repo_root)}; next steps: {rel(next_steps_path, repo_root)}. "
            f"{draft_detail}"
            f"{staleness_detail}"
            f"{launch_gate_detail}"
            "GPT draft labels do not count until every clip is human-reviewed and the launch report is rebuilt."
        ).strip()

    manifest_path = repo_root / DEFAULT_TEAM_ACCURACY_MANIFEST
    if manifest_path.exists():
        return (
            f" A manifest exists at {rel(manifest_path, repo_root)}; prepare or reopen the labeling bundle with "
            "`python3 scripts/prepare_team_highlight_labeling_bundle.py "
            f"--manifest {rel(manifest_path, repo_root)} "
            f"--output-dir {rel(repo_root / DEFAULT_LABELING_BUNDLE_DIR, repo_root)}`."
        )
    return ""


def labeling_bundle_draft_detail(metadata: dict[str, object] | None) -> str:
    review_metadata = metadata.get("reviewPageMetadata") if metadata else None
    if not isinstance(review_metadata, dict):
        return ""
    draft_prefill = review_metadata.get("draftPrefill")
    priority_counts = review_metadata.get("reviewPriorityCounts")
    details: list[str] = []
    if isinstance(draft_prefill, dict):
        applied = number_or_none(draft_prefill.get("appliedClipCount"))
        skipped = number_or_none(draft_prefill.get("skippedClipCount"))
        if applied is not None:
            details.append(f"GPT draft prefilled {int(applied)} clip(s)")
            if skipped is not None:
                details[-1] += f" and skipped {int(skipped)}"
    if isinstance(priority_counts, dict):
        close_review = number_or_none(priority_counts.get("needs_close_review"))
        standard_review = number_or_none(priority_counts.get("standard_review"))
        if close_review is not None or standard_review is not None:
            priority_parts = []
            if close_review is not None:
                priority_parts.append(f"{int(close_review)} close-review")
            if standard_review is not None:
                priority_parts.append(f"{int(standard_review)} standard-review")
            details.append("review priority queue: " + ", ".join(priority_parts))
    return f"{'; '.join(details)}. " if details else ""


def labeling_bundle_launch_gate_detail(status: dict[str, object] | None) -> str:
    base = "Launch label gate requires " + ", ".join(REQUIRED_LABEL_REVIEW_FIELDS) + " for every clip"
    if not isinstance(status, dict):
        return base + ". "
    missing_field_counts = status.get("missingFieldCounts")
    if not isinstance(missing_field_counts, dict):
        return base + ". "
    missing = [
        field
        for field in REQUIRED_LABEL_REVIEW_FIELDS
        if number_or_none(missing_field_counts.get(field)) not in (None, 0)
    ]
    if missing:
        return base + f"; current status still reports missing {', '.join(missing)}. "
    return base + ". "


def labeling_bundle_staleness_detail(
    repo_root: Path,
    bundle_dir: Path,
    review_page: Path,
    next_steps_path: Path,
    metadata: dict[str, object] | None,
    status: dict[str, object] | None,
) -> str:
    missing: list[str] = []
    if labeling_bundle_status_missing_human_review_gate(status):
        missing.append("status file reviewedByHuman=true counts")

    review_text = read_text(review_page)
    if review_text is None:
        missing.append(f"review page {rel(review_page, repo_root)} is missing or unreadable")
    else:
        missing.extend(label for marker, label in LABELING_BUNDLE_REVIEW_PAGE_MARKERS if marker not in review_text)

    next_steps_text = read_text(next_steps_path)
    if next_steps_text is None:
        missing.append(f"next steps {rel(next_steps_path, repo_root)} is missing or unreadable")
    else:
        missing.extend(label for marker, label in LABELING_BUNDLE_NEXT_STEPS_MARKERS if marker not in next_steps_text)

    if not missing:
        return ""

    detail = "Labeling bundle looks stale or incomplete"
    detail += f" (missing {', '.join(missing)})."
    regenerate_command = labeling_bundle_regenerate_command(repo_root, bundle_dir, metadata)
    if regenerate_command:
        detail += (
            f" Regenerate before review with `{regenerate_command}`. "
            "For multi-video bundles, replace --video-path with repeated --video videoId=/path.mp4 mappings."
        )
    else:
        detail += " Regenerate the labeling bundle from current scripts before review."
    return f"{detail} "


def labeling_bundle_status_missing_human_review_gate(status: dict[str, object] | None) -> bool:
    if not status:
        return False
    if status.get("status") != "incomplete":
        return False
    missing_field_counts = status.get("missingFieldCounts")
    if not isinstance(missing_field_counts, dict):
        return True
    return "reviewedByHuman=true" not in missing_field_counts


def labeling_bundle_regenerate_command(repo_root: Path, bundle_dir: Path, metadata: dict[str, object] | None) -> str:
    manifest_path = labeling_bundle_manifest_path(repo_root, bundle_dir, metadata)
    if not manifest_path.exists():
        return ""
    command = [
        "python3",
        "scripts/prepare_team_highlight_labeling_bundle.py",
        "--manifest",
        rel(manifest_path, repo_root),
        "--video-path",
        "/absolute/path/to/source.mp4",
        "--output-dir",
        rel(bundle_dir, repo_root),
    ]
    draft_bundle_path = labeling_bundle_draft_path(metadata)
    if draft_bundle_path:
        command.extend(["--draft-bundle", rel(draft_bundle_path, repo_root)])
    return " ".join(shlex.quote(part) for part in command)


def labeling_bundle_manifest_path(repo_root: Path, bundle_dir: Path, metadata: dict[str, object] | None) -> Path:
    raw_value = metadata.get("manifest") if metadata else None
    if isinstance(raw_value, str) and raw_value.strip():
        path = Path(raw_value).expanduser()
        return path if path.is_absolute() else repo_root / path
    local_manifest = bundle_dir / "manifest.json"
    if local_manifest.exists():
        return local_manifest
    return repo_root / DEFAULT_TEAM_ACCURACY_MANIFEST


def labeling_bundle_draft_path(metadata: dict[str, object] | None) -> Path | None:
    gpt_draft = metadata.get("gptDraft") if metadata else None
    if not isinstance(gpt_draft, dict):
        return None
    raw_path = gpt_draft.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    return Path(raw_path).expanduser()


def metadata_path_from_payload(repo_root: Path, payload: dict[str, object] | None, key: str, fallback: Path) -> Path:
    raw_value = payload.get(key) if payload else None
    if isinstance(raw_value, str) and raw_value.strip():
        path = Path(raw_value).expanduser()
        return path if path.is_absolute() else repo_root / path
    return repo_root / fallback


def resolve_repo_path(repo_root: Path, path: Path) -> Path:
    expanded = path.expanduser()
    return expanded if expanded.is_absolute() else repo_root / expanded


def check_ios_signing(repo_root: Path, collector: Collector) -> None:
    project_path = repo_root / "ios/HoopsClips.xcodeproj/project.pbxproj"
    project_text = read_text(project_path)
    if project_text is None:
        collector.fail("ios project", rel(project_path, repo_root), "iOS Xcode project is missing.")
        return

    for key, expected, label in (
        ("PRODUCT_BUNDLE_IDENTIFIER", EXPECTED_IOS_BUNDLE_ID, f"bundle id {EXPECTED_IOS_BUNDLE_ID}"),
        ("MARKETING_VERSION", EXPECTED_IOS_MARKETING_VERSION, f"marketing version {EXPECTED_IOS_MARKETING_VERSION}"),
        ("CURRENT_PROJECT_VERSION", EXPECTED_IOS_BUILD_NUMBER, f"build number {EXPECTED_IOS_BUILD_NUMBER}"),
        ("CODE_SIGN_STYLE", "Automatic", "automatic signing"),
        ("DEVELOPMENT_TEAM", "$(HOOPS_DEVELOPMENT_TEAM)", "team resolved from HOOPS_DEVELOPMENT_TEAM"),
    ):
        if app_target_build_setting_matches(project_text, key, expected):
            collector.pass_("ios project setting", rel(project_path, repo_root), f"Project includes {label}.")
        else:
            collector.fail("ios project setting", rel(project_path, repo_root), f"Project is missing {label}.")

    local_secrets_path = repo_root / "ios/HoopsClips/HoopsClips/Config/LocalSecrets.xcconfig"
    local_values = parse_xcconfig_values(local_secrets_path)
    env_team = os.getenv("HOOPS_DEVELOPMENT_TEAM", "").strip()
    local_team = local_values.get("HOOPS_DEVELOPMENT_TEAM", "").strip() if local_values else ""
    github_team_secret_present = "HOOPS_DEVELOPMENT_TEAM" in github_environment_names("secret")
    if env_team or (local_team not in PLACEHOLDER_VALUES) or github_team_secret_present:
        collector.pass_("ios signing team", rel(local_secrets_path, repo_root), "Development team is configured without printing its value.")
    else:
        collector.fail("ios signing team", rel(local_secrets_path, repo_root), "HOOPS_DEVELOPMENT_TEAM is missing or placeholder.")


def app_target_build_setting_matches(project_text: str, key: str, expected: str) -> bool:
    return any(build_setting_value(block, key) == expected for block in app_target_build_setting_blocks(project_text))


def app_target_build_setting_blocks(project_text: str) -> list[str]:
    blocks = [match.group("body") for match in re.finditer(r"buildSettings = \{(?P<body>.*?)^\s*\};", project_text, re.S | re.M)]
    return [block for block in blocks if build_setting_value(block, "PRODUCT_BUNDLE_IDENTIFIER") == EXPECTED_IOS_BUNDLE_ID]


def build_setting_value(block: str, key: str) -> str | None:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(.+?);\s*$", re.M)
    match = pattern.search(block)
    if not match:
        return None
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    return value


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
        if archive_path is None and current_testflight_upload_proof(repo_root):
            collector.pass_("upload artifact", "GitHub Actions", "Successful internal TestFlight upload log proof exists, and no iOS upload-relevant files changed afterward.")
            return
        if archive_path is None and (workflow_missing_upload_detail := current_testflight_workflow_missing_upload_detail(repo_root)):
            collector.fail("upload artifact", "iOS Internal TestFlight Upload", workflow_missing_upload_detail)
            return
        if archive_path is None and (workflow_failure_detail := current_testflight_workflow_failure_detail(repo_root)):
            collector.fail("upload artifact", "iOS Internal TestFlight Upload", workflow_failure_detail)
            return
        failure_path, failure_detail = metadata_failures[0]
        collector.fail("upload artifact", rel(failure_path, repo_root), failure_detail)
    elif archive_path is not None:
        collector.fail("upload artifact", rel(archive_path, repo_root), "Requested archive/IPA path does not exist.")
    elif current_testflight_upload_proof(repo_root):
        collector.pass_("upload artifact", "GitHub Actions", "Successful internal TestFlight upload log proof exists, and no iOS upload-relevant files changed afterward.")
    elif workflow_missing_upload_detail := current_testflight_workflow_missing_upload_detail(repo_root):
        collector.fail("upload artifact", "iOS Internal TestFlight Upload", workflow_missing_upload_detail)
    elif workflow_failure_detail := current_testflight_workflow_failure_detail(repo_root):
        collector.fail("upload artifact", "iOS Internal TestFlight Upload", workflow_failure_detail)
    else:
        collector.fail("upload artifact", "repo", "No .xcarchive or .ipa upload artifact found under the expected build output locations.")


def current_testflight_upload_proof(repo_root: Path) -> bool:
    runs = current_testflight_workflow_dispatch_runs(repo_root)
    current_sha = current_git_sha(repo_root)
    if not current_sha:
        return False
    matching_runs = [
        run
        for run in runs
        if isinstance(run, dict)
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and commit_is_current_or_unchanged_for_paths(repo_root, str(run.get("headSha") or ""), current_sha, IOS_UPLOAD_RELEVANT_PREFIXES)
    ]
    for run in matching_runs:
        if testflight_upload_log_has_markers(run.get("databaseId")):
            return True
    return False


def current_testflight_workflow_failure_detail(repo_root: Path) -> str:
    runs = current_testflight_workflow_dispatch_runs(repo_root)
    current_sha = current_git_sha(repo_root)
    if not current_sha:
        return ""
    for run in runs:
        head_sha = str(run.get("headSha") or "")
        if not commit_is_current_or_unchanged_for_paths(repo_root, head_sha, current_sha, IOS_UPLOAD_RELEVANT_PREFIXES):
            continue
        status = str(run.get("status") or "unknown")
        conclusion = str(run.get("conclusion") or "unknown")
        created_at = str(run.get("createdAt") or "unknown")
        if status == "completed" and conclusion == "success":
            continue
        run_id = run.get("databaseId")
        detail = testflight_workflow_failure_log_detail(run_id)
        if detail:
            return (
                f"Current-branch internal TestFlight archive/upload workflow status={status} "
                f"conclusion={conclusion} at {created_at}; {detail}"
            )
        return (
            f"Current-branch internal TestFlight archive/upload workflow status={status} "
            f"conclusion={conclusion} at {created_at}; inspect run {run_id or 'unknown'}."
        )
    return ""


def current_testflight_workflow_missing_upload_detail(repo_root: Path) -> str:
    runs = current_testflight_workflow_dispatch_runs(repo_root)
    current_sha = current_git_sha(repo_root)
    if not current_sha:
        return ""
    for run in runs:
        head_sha = str(run.get("headSha") or "")
        if not commit_is_current_or_unchanged_for_paths(repo_root, head_sha, current_sha, IOS_UPLOAD_RELEVANT_PREFIXES):
            continue
        status = str(run.get("status") or "unknown")
        conclusion = str(run.get("conclusion") or "unknown")
        created_at = str(run.get("createdAt") or "unknown")
        if status == "completed" and conclusion == "success" and not testflight_upload_log_has_markers(run.get("databaseId")):
            return (
                "Current-branch iOS workflow completed successfully at "
                f"{created_at}, but internal TestFlight upload log proof was not found; "
                "this may be a codecheck-only run and does not prove signed archive/upload."
            )
        return ""
    return ""


def current_testflight_workflow_dispatch_runs(repo_root: Path) -> list[dict[str, object]]:
    try:
        result = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--repo",
                "charlie2233/rork-hoopshighlights-ai_Final",
                "--workflow",
                IOS_TESTFLIGHT_UPLOAD_WORKFLOW_FILE,
                "--limit",
                "20",
                "--json",
                "databaseId,status,conclusion,createdAt,headSha,event",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    try:
        runs = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(runs, list):
        return []
    return [
        run
        for run in runs
        if isinstance(run, dict)
        and run.get("event") == "workflow_dispatch"
    ]


def testflight_upload_log_has_markers(run_id: object) -> bool:
    if run_id in (None, ""):
        return False
    try:
        result = subprocess.run(
            [
                "gh",
                "run",
                "view",
                str(run_id),
                "--repo",
                "charlie2233/rork-hoopshighlights-ai_Final",
                "--log",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    return all(marker in result.stdout for marker in TESTFLIGHT_UPLOAD_LOG_MARKERS)


def testflight_workflow_failure_log_detail(run_id: object) -> str:
    if run_id in (None, ""):
        return ""
    try:
        result = subprocess.run(
            [
                "gh",
                "run",
                "view",
                str(run_id),
                "--repo",
                "charlie2233/rork-hoopshighlights-ai_Final",
                "--log",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    matched = [
        marker
        for marker in TESTFLIGHT_SIGNING_FAILURE_MARKERS
        if marker in result.stdout
    ]
    if matched:
        return "signing/provisioning failure markers found: " + ", ".join(matched) + "."
    return ""


def commit_is_current_or_unchanged_for_paths(repo_root: Path, base_sha: str, current_sha: str, path_prefixes: tuple[str, ...]) -> bool:
    if not base_sha:
        return False
    if base_sha == current_sha:
        return True
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_sha}..{current_sha}"],
            cwd=repo_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    changed_paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return not any(path_is_relevant_to_prefixes(path, path_prefixes) for path in changed_paths)


def path_is_relevant_to_prefixes(path: str, path_prefixes: tuple[str, ...]) -> bool:
    for prefix in path_prefixes:
        if prefix.endswith("/"):
            if path.startswith(prefix):
                return True
        elif path == prefix:
            return True
    return False


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
    available_iphones = [device for device in devices if device["model"].startswith("iPhone") and ios_device_state_is_smoke_ready(device["state"])]
    unavailable_iphones = [device for device in devices if device["model"].startswith("iPhone") and not ios_device_state_is_smoke_ready(device["state"])]
    if available_iphones:
        collector.pass_("connected ios device", "xcrun devicectl", f"{len(available_iphones)} available iPhone device(s) detected for TestFlight smoke.")
    elif unavailable_iphones:
        states = ", ".join(sorted({device["state"] for device in unavailable_iphones}))
        detail = unavailable_ios_device_detail(unavailable_iphones[0]["identifier"])
        detail_suffix = f" Device detail: {detail}." if detail else ""
        recovery_hint = unavailable_ios_device_recovery_hint(detail)
        recovery_suffix = f" {recovery_hint}" if recovery_hint else ""
        collector.fail(
            "connected ios device",
            "xcrun devicectl",
            f"iPhone device(s) detected but unavailable for install/smoke testing: {states}.{detail_suffix}{recovery_suffix}",
        )
    else:
        collector.fail("connected ios device", "xcrun devicectl", "No available physical iPhone detected for installed TestFlight smoke.")


def ios_device_state_is_smoke_ready(state: str) -> bool:
    normalized = state.lower().strip()
    return normalized.startswith("available") or normalized == "connected"


def unavailable_ios_device_detail(identifier: str) -> str | None:
    try:
        result = subprocess.run(
            ["xcrun", "devicectl", "device", "info", "details", "--device", identifier],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None

    fields = []
    for field in ("pairingState", "tunnelState", "developerModeStatus", "ddiServicesAvailable", "lastConnectionDate"):
        value = devicectl_detail_field(result.stdout, field)
        if value:
            fields.append(f"{field}={value}")
    return ", ".join(fields) or None


def unavailable_ios_device_recovery_hint(detail: str | None) -> str:
    if not detail:
        return ""
    if "tunnelState=unavailable" in detail or "ddiServicesAvailable=false" in detail:
        return (
            "Recovery: unlock the iPhone, connect it by USB or put it on the same local network as this Mac, "
            "then reopen Xcode Devices or rerun devicectl before installed TestFlight smoke."
        )
    return ""


def devicectl_detail_field(output: str, field: str) -> str | None:
    pattern = re.compile(rf"•\s+{re.escape(field)}:\s+(.+)")
    for line in output.splitlines():
        match = pattern.search(line)
        if match:
            return match.group(1).strip()
    return None


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
        state_tokens = [parts[identifier_index + 1]]
        model_start = identifier_index + 2
        while model_start < len(parts) and parts[model_start].startswith("(") and parts[model_start].endswith(")"):
            state_tokens.append(parts[model_start])
            model_start += 1
        state = " ".join(state_tokens)
        model = " ".join(parts[model_start:])
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

    result = fetch_version_payload(endpoint, timeout_seconds=timeout_seconds)
    if isinstance(result, HTTPError):
        result.close()
        error = result
        reason = _safe_probe_error_detail(error)
        detail = f"Returned HTTP {error.code}"
        if reason:
            detail += f" ({reason})"
        detail += "; staging Worker must proxy editing /version before submission."
        collector.fail("live worker version route", endpoint_label, detail)
        return
    if isinstance(result, (OSError, URLError)):
        error = result
        detail = _safe_probe_error_detail(error)
        hint = "Retry this check from an authorized/networked environment and confirm staging Worker deploy is current."
        if detail:
            collector.fail("live worker version route", endpoint_label, f"Probe failed: {type(error).__name__} ({detail}). {hint}")
        else:
            collector.fail("live worker version route", endpoint_label, f"Probe failed: {type(error).__name__}. {hint}")
        return

    status_code, body = result
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


def check_live_editing_version(editing_version_url: str, collector: Collector, *, repo_root: Path, skip_live: bool, timeout_seconds: float) -> None:
    endpoint = strip_url_query(editing_version_url)
    endpoint_label = redacted_endpoint_label(endpoint)
    if skip_live:
        collector.warn("live editing version route", endpoint_label, "Direct editing service probe skipped by request.")
        return

    result = fetch_version_payload(endpoint, timeout_seconds=timeout_seconds)
    if isinstance(result, HTTPError):
        result.close()
        error = result
        reason = _safe_probe_error_detail(error)
        detail = f"Returned HTTP {error.code}"
        if reason:
            detail += f" ({reason})"
        detail += "; staging editing service must expose /version before submission."
        collector.fail("live editing version route", endpoint_label, detail)
        return
    if isinstance(result, (OSError, URLError)):
        error = result
        detail = _safe_probe_error_detail(error)
        hint = "Retry this check from an authorized/networked environment and verify Cloud Run/Wrangler routing before re-running preflight."
        if detail:
            collector.fail("live editing version route", endpoint_label, f"Probe failed: {type(error).__name__} ({detail}). {hint}")
        else:
            collector.fail("live editing version route", endpoint_label, f"Probe failed: {type(error).__name__}. {hint}")
        return

    status_code, body = result
    if status_code != 200:
        collector.fail("live editing version route", endpoint_label, f"Returned HTTP {status_code}; expected 200.")
        return

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        collector.fail("live editing version payload", endpoint_label, "Response was not valid JSON.")
        return

    if not isinstance(payload, dict):
        collector.fail("live editing version payload", endpoint_label, "Response was not a JSON object.")
        return

    feature_flags = payload.get("featureFlags")
    if not isinstance(feature_flags, dict):
        collector.fail("live editing feature flags", endpoint_label, "Response did not include featureFlags.")
        return

    missing_flags = [flag for flag in REQUIRED_FEATURE_FLAGS if flag not in feature_flags]
    if missing_flags:
        collector.fail("live editing feature flags", endpoint_label, f"Missing feature flag(s): {', '.join(missing_flags)}.")
    else:
        collector.pass_("live editing feature flags", endpoint_label, "Direct editing service returned non-secret AI Edit kill-switch state.")

    reported_git_sha = payload.get("gitSha")
    current_git_sha = run_git(repo_root, "rev-parse", "HEAD")
    if not isinstance(reported_git_sha, str) or not reported_git_sha.strip():
        collector.fail("live editing git sha", endpoint_label, "Response did not include gitSha for deploy drift proof.")
    elif not current_git_sha:
        collector.warn("live editing git sha", endpoint_label, "Could not compare live gitSha with the current checkout.")
    elif git_sha_matches(reported_git_sha.strip(), current_git_sha.strip()):
        collector.pass_("live editing git sha", endpoint_label, "Direct editing service gitSha matches the current checkout.")
    elif commit_is_current_or_unchanged_for_paths(
        repo_root,
        reported_git_sha.strip(),
        current_git_sha.strip(),
        EDITING_SERVICE_DEPLOY_RELEVANT_PREFIXES,
    ):
        collector.pass_(
            "live editing git sha",
            endpoint_label,
            "Direct editing service gitSha is older than the current checkout, but no editing-service deploy-relevant files changed afterward.",
        )
    else:
        collector.fail("live editing git sha", endpoint_label, "Direct editing service gitSha does not match the current checkout; deploy current source before submission.")


def fetch_version_payload(endpoint: str, *, timeout_seconds: float) -> tuple[int, bytes] | HTTPError | OSError | URLError:
    request = Request(endpoint, headers={"Accept": "application/json", "User-Agent": "HoopClipsSubmissionPreflight/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.getcode(), response.read(256_000)
    except HTTPError as error:
        return error
    except (OSError, URLError) as error:
        return error


def _safe_probe_error_detail(error: Exception) -> str:
    reason = getattr(error, "reason", None)
    if reason is None and isinstance(error, OSError):
        reason = getattr(error, "strerror", None)
    if isinstance(reason, str):
        return reason.strip()
    if isinstance(reason, Exception):
        reason_message = str(reason).strip()
        return reason_message
    if isinstance(reason, tuple):
        reason_message = " ".join(str(item).strip() for item in reason if str(item).strip())
        if reason_message:
            return reason_message
    if isinstance(error, OSError) and error.args:
        reason_message = " ".join(str(item).strip() for item in error.args if str(item).strip())
        if reason_message:
            return reason_message
    return ""


def _gh_stderr_detail(stderr: str, command_desc: str) -> str:
    message = (stderr or "").strip()
    if not message:
        return f"gh {command_desc} returned a non-zero exit code."
    compact = " ".join(message.splitlines())
    compact = _redact_diagnostic_text(compact)
    lower = compact.lower()
    if "auth" in lower or "login" in lower or "token" in lower:
        return (
            f"gh {command_desc} needs a valid GitHub login. Run `gh auth login` and retry from an authorized environment."
            f" Original error: {compact[:180]}"
        )
    return f"gh {command_desc} failed: {compact[:180]}"


def _redact_diagnostic_text(message: str) -> str:
    redacted = message.replace("x-oauth-basic", "<redacted>")
    redacted = re.sub(r"(?i)(authorization:\s*bearer\s+)\S+", r"\1<redacted>", redacted)
    redacted = re.sub(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]+\b", "<redacted-token>", redacted)
    redacted = re.sub(r"\b[A-Za-z0-9+/=_-]{48,}\b", "<redacted-token>", redacted)
    return redacted


def check_ci_deploy_inputs(collector: Collector) -> None:
    required = (*REQUIRED_DEPLOY_SECRET_INPUTS, *REQUIRED_DEPLOY_VARIABLE_INPUTS)
    github_secret_lookup = github_environment_name_lookup("secret")
    github_variable_lookup = github_environment_name_lookup("variable")
    github_names = github_secret_lookup.names | github_variable_lookup.names
    missing = [name for name in required if not os.getenv(name) and name not in github_names]
    if missing:
        collector.fail(
            "cloud deploy inputs",
            "environment",
            missing_input_detail(
                missing,
                label="deploy",
                workflow="cloud-edit-deploy-preflight.yml",
                lookup_details=github_lookup_unavailable_details(github_secret_lookup, github_variable_lookup),
            ),
        )
    else:
        collector.pass_("cloud deploy inputs", "environment", "Required deploy input names are present locally or in the GitHub staging environment without printing values.")


def check_production_cloud_url_inputs(collector: Collector) -> None:
    github_variable_lookup = github_production_variable_name_lookup()
    missing = [
        name
        for name in REQUIRED_PRODUCTION_CLOUD_URL_VARIABLE_INPUTS
        if not os.getenv(name) and name not in github_variable_lookup.names
    ]
    if missing:
        collector.fail(
            "production cloud URL inputs",
            "environment",
            missing_input_detail(
                missing,
                label="production cloud URL",
                workflow="release-secrets-preflight.yml",
                lookup_details=github_lookup_unavailable_details(github_variable_lookup),
                environment_label="GitHub production environment variable names only",
                configure_label="GitHub production environment",
                lookup_label="GitHub production name lookup",
            ),
        )
    else:
        collector.pass_(
            "production cloud URL inputs",
            "environment",
            "Required production cloud URL variable names are present locally or in the GitHub production environment without printing values.",
        )


def check_github_workflow_runs(repo_root: Path, collector: Collector) -> None:
    current_sha = current_git_sha(repo_root)
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
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        collector.warn("github workflow status", "GitHub Actions", "Could not inspect latest main-branch workflow runs.")
        return
    if result.returncode != 0:
        collector.warn(
            "github workflow status",
            "GitHub Actions",
            _gh_stderr_detail(result.stderr or "", "run list"),
        )
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
        head_sha = str(latest.get("headSha") or "")
        status = str(latest.get("status") or "unknown")
        conclusion = str(latest.get("conclusion") or "unknown")
        created_at = str(latest.get("createdAt") or "unknown")
        if status == "completed" and conclusion in GITHUB_ACTIONS_STARTABILITY_CONCLUSIONS:
            collector.fail(
                "github actions startability",
                workflow_name,
                f"Latest main-branch run conclusion={conclusion} at {created_at}; repair GitHub Actions billing/spending/action-required account state before deploy/upload proof.",
            )
        elif status != "completed" or conclusion != "success":
            collector.fail("github workflow status", workflow_name, f"Latest main-branch run status={status} conclusion={conclusion} at {created_at}.")
        elif current_sha and head_sha != current_sha:
            short_latest = head_sha[:7] if head_sha else "unknown"
            short_current = current_sha[:7]
            relevant_prefixes = REQUIRED_MAIN_WORKFLOW_RELEVANT_PREFIXES.get(workflow_name, ())
            if relevant_prefixes and commit_is_current_or_unchanged_for_paths(repo_root, head_sha, current_sha, relevant_prefixes):
                collector.pass_(
                    "github workflow status",
                    workflow_name,
                    (
                        f"Latest main-branch run for {short_latest} completed successfully at {created_at}, "
                        "and no workflow-relevant files changed afterward."
                    ),
                )
            else:
                collector.fail(
                    "github workflow status",
                    workflow_name,
                    f"Latest main-branch run is for {short_latest}, not current checkout {short_current}; rerun required CI on current main before submission.",
                )
        else:
            collector.pass_("github workflow status", workflow_name, f"Latest main-branch run for current checkout completed successfully at {created_at}.")


def check_secret_gated_deploy_preflight(repo_root: Path, collector: Collector) -> None:
    check_name = "secret-gated deploy preflight"
    current_sha = current_git_sha(repo_root)
    try:
        result = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--repo",
                "charlie2233/rork-hoopshighlights-ai_Final",
                "--workflow",
                SECRET_GATED_DEPLOY_WORKFLOW_FILE,
                "--limit",
                "50",
                "--json",
                "databaseId,status,conclusion,createdAt,headSha,event,url",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        collector.warn(check_name, "GitHub Actions", "Could not inspect secret-gated deploy preflight workflow_dispatch runs.")
        return
    if result.returncode != 0:
        collector.warn(
            check_name,
            "GitHub Actions",
            _gh_stderr_detail(result.stderr or "", "run list --workflow cloud-edit-deploy-preflight.yml"),
        )
        return
    try:
        runs = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        collector.warn(check_name, "GitHub Actions", "gh run list returned invalid JSON for deploy preflight runs.")
        return
    if not isinstance(runs, list):
        collector.warn(check_name, "GitHub Actions", "gh run list returned an unexpected deploy preflight payload.")
        return

    dispatch_runs = [run for run in runs if isinstance(run, dict) and run.get("event") == "workflow_dispatch"]
    if not dispatch_runs:
        collector.fail(
            check_name,
            "Cloud Edit Deploy Preflight",
            (
                "No manually dispatched deploy preflight run was found; push codechecks do not prove staging secrets or provider auth. "
                "Use operation=credential-check first while repairing provider credentials, then operation=preflight or operation=deploy for launch readiness."
            ),
        )
        return

    matching_run = None
    for run in dispatch_runs:
        head_sha = str(run.get("headSha") or "")
        if current_sha and commit_is_current_or_unchanged_for_paths(repo_root, head_sha, current_sha, CLOUD_DEPLOY_RELEVANT_PREFIXES):
            matching_run = run
            break

    if matching_run is None:
        latest = dispatch_runs[0]
        latest_sha = str(latest.get("headSha") or "")
        short_latest = latest_sha[:7] if latest_sha else "unknown"
        short_current = current_sha[:7] if current_sha else "unknown"
        collector.fail(
            check_name,
            "Cloud Edit Deploy Preflight",
            (
                f"Latest manually dispatched deploy preflight is for {short_latest}, not current checkout {short_current}; "
                "use operation=credential-check first while repairing provider credentials, then rerun workflow_dispatch "
                "operation=preflight or operation=deploy for launch readiness."
            ),
        )
        return

    run_id = matching_run.get("databaseId")
    status = str(matching_run.get("status") or "unknown")
    conclusion = str(matching_run.get("conclusion") or "unknown")
    created_at = str(matching_run.get("createdAt") or "unknown")
    if status != "completed" or conclusion != "success":
        collector.fail(
            check_name,
            "Cloud Edit Deploy Preflight",
            f"Current-commit workflow_dispatch deploy/preflight status={status} conclusion={conclusion} at {created_at}.",
        )
        return

    job_result = deploy_preflight_secret_job_result(run_id)
    if job_result is None:
        collector.fail(
            check_name,
            "Cloud Edit Deploy Preflight",
            (
                "Could not confirm the secret-gated deploy job; use operation=credential-check first while repairing provider "
                "credentials, then rerun workflow_dispatch operation=preflight or operation=deploy and verify provider-auth checks."
            ),
        )
        return
    job_status, job_conclusion = job_result
    if job_status == "completed" and job_conclusion == "success":
        collector.pass_(
            check_name,
            "Cloud Edit Deploy Preflight",
            f"Workflow_dispatch deploy/preflight completed successfully with provider-auth job proof at {created_at}, and no deploy-relevant files changed afterward.",
        )
    else:
        collector.fail(
            check_name,
            "Cloud Edit Deploy Preflight",
            (
                f"Secret-gated deploy job status={job_status} conclusion={job_conclusion}; provider-auth preflight is not proven. "
                "Use operation=credential-check first while repairing provider credentials, then operation=preflight or operation=deploy for launch readiness."
            ),
        )


def deploy_preflight_secret_job_result(run_id: object) -> tuple[str, str] | None:
    if run_id in (None, ""):
        return None
    try:
        result = subprocess.run(
            [
                "gh",
                "run",
                "view",
                str(run_id),
                "--repo",
                "charlie2233/rork-hoopshighlights-ai_Final",
                "--json",
                "jobs",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        return None
    for job in jobs:
        if isinstance(job, dict) and job.get("name") == SECRET_GATED_DEPLOY_JOB_NAME:
            return str(job.get("status") or "unknown"), str(job.get("conclusion") or "unknown")
    return "missing", "missing"


def current_git_sha(repo_root: Path) -> str | None:
    value = run_git(repo_root, "rev-parse", "HEAD")
    if value is None:
        return None
    sha = value.strip()
    return sha or None


def github_environment_names(kind: str) -> set[str]:
    return github_environment_name_lookup(kind).names


def github_environment_name_lookup(kind: str) -> GithubEnvironmentNameLookup:
    if kind == "secret":
        args = ["gh", "secret", "list", "--env", "staging", "--json", "name"]
        command_desc = "secret list --env staging"
    elif kind == "variable":
        args = ["gh", "variable", "list", "--env", "staging", "--json", "name"]
        command_desc = "variable list --env staging"
    else:
        return GithubEnvironmentNameLookup(set(), f"unsupported GitHub environment name kind {kind}")
    try:
        result = subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
    except OSError as error:
        return GithubEnvironmentNameLookup(set(), f"gh {command_desc} could not run: {type(error).__name__}")
    except subprocess.TimeoutExpired:
        return GithubEnvironmentNameLookup(set(), f"gh {command_desc} timed out")
    if result.returncode != 0:
        return GithubEnvironmentNameLookup(set(), _gh_stderr_detail(result.stderr, command_desc))
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return GithubEnvironmentNameLookup(set(), f"gh {command_desc} returned invalid JSON")
    if not isinstance(payload, list):
        return GithubEnvironmentNameLookup(set(), f"gh {command_desc} returned an unexpected JSON shape")
    return GithubEnvironmentNameLookup({str(item.get("name")) for item in payload if isinstance(item, dict) and item.get("name")})


def github_production_variable_name_lookup() -> GithubEnvironmentNameLookup:
    args = ["gh", "variable", "list", "--env", "production", "--json", "name"]
    command_desc = "variable list --env production"
    try:
        result = subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
    except OSError as error:
        return GithubEnvironmentNameLookup(set(), f"gh {command_desc} could not run: {type(error).__name__}")
    except subprocess.TimeoutExpired:
        return GithubEnvironmentNameLookup(set(), f"gh {command_desc} timed out")
    if result.returncode != 0:
        return GithubEnvironmentNameLookup(set(), _gh_stderr_detail(result.stderr, command_desc))
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return GithubEnvironmentNameLookup(set(), f"gh {command_desc} returned invalid JSON")
    if not isinstance(payload, list):
        return GithubEnvironmentNameLookup(set(), f"gh {command_desc} returned an unexpected JSON shape")
    return GithubEnvironmentNameLookup({str(item.get("name")) for item in payload if isinstance(item, dict) and item.get("name")})


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
    github_secret_lookup = github_environment_name_lookup("secret")
    github_variable_lookup = github_environment_name_lookup("variable")
    github_names = github_secret_lookup.names | github_variable_lookup.names
    missing = [name for name in required if not os.getenv(name) and name not in github_names]
    if missing:
        collector.fail(
            "ios upload inputs",
            "environment",
            missing_input_detail(
                missing,
                label="iOS upload",
                workflow="ios-testflight-upload.yml",
                lookup_details=github_lookup_unavailable_details(github_secret_lookup, github_variable_lookup),
            ),
        )
    else:
        collector.pass_("ios upload inputs", "environment", "Required iOS upload input names are present locally or in the GitHub staging environment without printing values.")


def github_lookup_unavailable_details(*lookups: GithubEnvironmentNameLookup) -> list[str]:
    return [lookup.unavailable_detail for lookup in lookups if lookup.unavailable_detail]


def missing_input_detail(
    missing: list[str],
    *,
    label: str,
    workflow: str,
    lookup_details: list[str] | None = None,
    environment_label: str = "GitHub staging environment secret/variable names only",
    configure_label: str = "GitHub staging environment",
    lookup_label: str = "GitHub staging name lookup",
) -> str:
    detail = (
        f"Missing required {label} input name(s): {', '.join(missing)}. "
        f"Checked local environment values and {environment_label}; "
        "secret values are not needed for this check and must not be pasted into logs. "
        f"Configure the missing names in the {configure_label}, then rerun `{workflow}` or this preflight from an authorized `gh` session."
    )
    if lookup_details:
        detail += f" {lookup_label} was incomplete: {'; '.join(lookup_details)}."
    return detail


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


def strip_url_query(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.netloc:
        return url.rstrip("/")
    return parsed._replace(query="", fragment="").geturl().rstrip("/")


def redacted_endpoint_label(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.netloc:
        return VERSION_ROUTE
    return f"{parsed.netloc}{parsed.path}"


def git_sha_matches(reported: str, expected: str) -> bool:
    reported_normalized = reported.strip()
    expected_normalized = expected.strip()
    return expected_normalized.startswith(reported_normalized) or reported_normalized.startswith(expected_normalized)


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


def read_json_object(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def number_or_none(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
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
