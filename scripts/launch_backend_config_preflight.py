#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REQUIRED_WORKER_SECRETS = {
    "ADMIN_API_TOKEN",
    "CONTROL_PLANE_BASE_URL",
    "CONTROL_PLANE_SHARED_SECRET",
    "INFERENCE_BASE_URL",
    "INFERENCE_SHARED_SECRET",
    "EDITING_BASE_URL",
    "EDITING_SHARED_SECRET",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
}

REQUIRED_AI_EDIT_SUBSTITUTIONS = {
    "_AI_EDIT_ENABLED": "true",
    "_AI_EDIT_LIVE_RENDER_ENABLED": "true",
    "_AI_EDIT_REVISION_ENABLED": "true",
    "_AI_EDIT_TEMPLATE_PACK_ENABLED": "true",
}

REQUIRED_GPT_RERANK_SUBSTITUTIONS = {
    "_AI_CLIP_GPT_EDITOR_ENABLED": "true",
    "_AI_CLIP_GPT_PLAN_EDIT_ENABLED": "true",
    "_AI_CLIP_GPT_REVISION_ENABLED": "true",
    "_AI_CLIP_GPT_KEYFRAMES_PER_CLIP": "8",
    "_AI_CLIP_GPT_MAX_CANDIDATES_FREE": "60",
    "_AI_CLIP_GPT_MAX_CANDIDATES_PRO": "60",
    "_AI_CLIP_GPT_TIMEOUT_SECONDS": "60",
    "_AI_CLIP_GPT_MAX_OUTPUT_TOKENS": "12000",
    "_GPT_HIGHLIGHT_RERANKER_ENABLED": "true",
}

REQUIRED_GPT_RERANK_ENV_MAPPINGS = (
    "HOOPS_AI_CLIP_GPT_EDITOR_ENABLED=${_AI_CLIP_GPT_EDITOR_ENABLED}",
    "HOOPS_AI_CLIP_GPT_PLAN_EDIT_ENABLED=${_AI_CLIP_GPT_PLAN_EDIT_ENABLED}",
    "HOOPS_AI_CLIP_GPT_REVISION_ENABLED=${_AI_CLIP_GPT_REVISION_ENABLED}",
    "HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP=${_AI_CLIP_GPT_KEYFRAMES_PER_CLIP}",
    "HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE=${_AI_CLIP_GPT_MAX_CANDIDATES_FREE}",
    "HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO=${_AI_CLIP_GPT_MAX_CANDIDATES_PRO}",
    "HOOPS_AI_CLIP_GPT_TIMEOUT_SECONDS=${_AI_CLIP_GPT_TIMEOUT_SECONDS}",
    "HOOPS_AI_CLIP_GPT_MAX_OUTPUT_TOKENS=${_AI_CLIP_GPT_MAX_OUTPUT_TOKENS}",
    "HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED=${_GPT_HIGHLIGHT_RERANKER_ENABLED}",
)

REQUIRED_ANALYSIS_TEAM_SCAN_SUBSTITUTIONS = {
    "_MAX_RETURNED_CLIPS": "60",
    "_TEAM_QUICK_SCAN_ENABLED": "true",
    "_TEAM_QUICK_SCAN_CLIP_FRAMES_PER_CLIP": "8",
    "_TEAM_QUICK_SCAN_RICH_CANDIDATE_CLIPS": "120",
    "_TEAM_QUICK_SCAN_MAX_TOTAL_CLIP_FRAMES": "1200",
    "_TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS": "160",
    "_TEAM_QUICK_SCAN_MAX_OUTPUT_TOKENS": "12000",
}

REQUIRED_ANALYSIS_TEAM_SCAN_ENV_MAPPINGS = (
    "HOOPS_MAX_RETURNED_CLIPS=${_MAX_RETURNED_CLIPS}",
    "HOOPS_TEAM_QUICK_SCAN_ENABLED=${_TEAM_QUICK_SCAN_ENABLED}",
    "HOOPS_TEAM_QUICK_SCAN_CLIP_FRAMES_PER_CLIP=${_TEAM_QUICK_SCAN_CLIP_FRAMES_PER_CLIP}",
    "HOOPS_TEAM_QUICK_SCAN_RICH_CANDIDATE_CLIPS=${_TEAM_QUICK_SCAN_RICH_CANDIDATE_CLIPS}",
    "HOOPS_TEAM_QUICK_SCAN_MAX_TOTAL_CLIP_FRAMES=${_TEAM_QUICK_SCAN_MAX_TOTAL_CLIP_FRAMES}",
    "HOOPS_TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS=${_TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS}",
    "HOOPS_TEAM_QUICK_SCAN_MAX_OUTPUT_TOKENS=${_TEAM_QUICK_SCAN_MAX_OUTPUT_TOKENS}",
)

REQUIRED_FREE_DAILY_EDIT_CHANCES = 3

REQUIRED_DEPLOY_INPUTS = {
    "CLOUDFLARE_API_TOKEN",
    "GCP_WORKLOAD_IDENTITY_PROVIDER",
    "GCP_DEPLOY_SERVICE_ACCOUNT",
    "GCP_PROJECT_ID",
    "GCP_REGION",
}


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
    findings = run_checks(repo_root)

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
    parser = argparse.ArgumentParser(description="Static HoopClips backend/config launch preflight. Does not read secrets.")
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="Emit machine-readable findings.")
    return parser.parse_args()


def run_checks(repo_root: Path) -> list[Finding]:
    collector = Collector()
    check_control_plane_wrangler(repo_root, collector)
    check_editing_cloudbuild(repo_root, collector)
    check_analysis_cloudbuild(repo_root, collector)
    check_free_daily_edit_chances(repo_root, collector)
    check_workflows(repo_root, collector)
    check_ios_configs(repo_root, collector)
    check_observability_and_flags(repo_root, collector)
    check_secret_url_logging_guards(repo_root, collector)
    check_literal_secret_values(repo_root, collector)
    check_phase_docs(repo_root, collector)
    return collector.findings


def check_control_plane_wrangler(repo_root: Path, collector: Collector) -> None:
    path = repo_root / "services/control-plane/wrangler.jsonc"
    config = load_jsonc(path, collector)
    if not isinstance(config, dict):
        return

    envs = config.get("env")
    staging = envs.get("staging") if isinstance(envs, dict) else None
    if not isinstance(staging, dict):
        collector.fail("control-plane staging env", rel(path, repo_root), "Missing env.staging in Wrangler config.")
        return

    if staging.get("name") == "hoopsclips-control-plane-staging":
        collector.pass_("control-plane staging worker", rel(path, repo_root), "Staging Worker name is explicit.")
    else:
        collector.fail("control-plane staging worker", rel(path, repo_root), "Staging Worker name is missing or not staging-scoped.")

    staging_vars = staging.get("vars") if isinstance(staging.get("vars"), dict) else {}
    if staging_vars.get("APP_ENV") == "staging":
        collector.pass_("control-plane staging app env", rel(path, repo_root), "Staging Worker APP_ENV resolves to staging.")
    else:
        collector.fail("control-plane staging app env", rel(path, repo_root), "Staging Worker APP_ENV must be staging.")

    for key in ("R2_UPLOAD_BUCKET_NAME", "R2_RESULT_BUCKET_NAME"):
        value = str(staging_vars.get(key, ""))
        if value.endswith("-staging"):
            collector.pass_("control-plane staging buckets", rel(path, repo_root), f"{key} is staging-scoped.")
        else:
            collector.fail("control-plane staging buckets", rel(path, repo_root), f"{key} is not staging-scoped.")

    r2_buckets = staging.get("r2_buckets") if isinstance(staging.get("r2_buckets"), list) else []
    r2_by_binding = {bucket.get("binding"): bucket.get("bucket_name") for bucket in r2_buckets if isinstance(bucket, dict)}
    if str(r2_by_binding.get("R2_UPLOADS", "")).endswith("-staging") and str(r2_by_binding.get("R2_RESULTS", "")).endswith("-staging"):
        collector.pass_("control-plane r2 bindings", rel(path, repo_root), "R2 bindings point to staging buckets.")
    else:
        collector.fail("control-plane r2 bindings", rel(path, repo_root), "R2 upload/result bindings must use staging buckets.")

    queue_config = staging.get("queues") if isinstance(staging.get("queues"), dict) else {}
    producers = queue_config.get("producers") if isinstance(queue_config.get("producers"), list) else []
    consumers = queue_config.get("consumers") if isinstance(queue_config.get("consumers"), list) else []
    producer_names = {str(item.get("queue")) for item in producers if isinstance(item, dict)}
    dlq_names = {str(item.get("dead_letter_queue")) for item in consumers if isinstance(item, dict) and item.get("dead_letter_queue")}
    if dlq_names and dlq_names.issubset(producer_names):
        collector.pass_("control-plane dlq wiring", rel(path, repo_root), "Staging DLQ consumer references a configured producer queue.")
    else:
        collector.fail("control-plane dlq wiring", rel(path, repo_root), "Staging DLQ consumer must reference a configured producer queue.")

    d1_databases = staging.get("d1_databases") if isinstance(staging.get("d1_databases"), list) else []
    d1 = next((item for item in d1_databases if isinstance(item, dict) and item.get("binding") == "DB"), {})
    if d1.get("database_name") == "hoopsclips-control-plane-staging" and not is_placeholder_id(str(d1.get("database_id", ""))):
        collector.pass_("control-plane d1", rel(path, repo_root), "Staging D1 binding is non-placeholder.")
    else:
        collector.fail("control-plane d1", rel(path, repo_root), "Staging D1 binding is missing or placeholder.")

    staging_secrets = set(read_required_secret_names(staging))
    missing_staging_secrets = sorted(REQUIRED_WORKER_SECRETS - staging_secrets)
    if missing_staging_secrets:
        collector.fail("control-plane staging secret contract", rel(path, repo_root), f"Missing required secret names: {', '.join(missing_staging_secrets)}.")
    else:
        collector.pass_("control-plane staging secret contract", rel(path, repo_root), "Required staging Worker secret names are declared.")

    if config.get("observability", {}).get("enabled") is True:
        collector.pass_("control-plane observability", rel(path, repo_root), "Worker observability is enabled.")
    else:
        collector.warn("control-plane observability", rel(path, repo_root), "Worker observability is not enabled.")

    production = envs.get("production") if isinstance(envs, dict) else None
    if production is None:
        collector.warn("production worker gate", rel(path, repo_root), "env.production is absent; production Worker cutover remains blocked by design.")
    elif not isinstance(production, dict):
        collector.fail("production worker gate", rel(path, repo_root), "env.production is malformed.")
    else:
        production_vars = production.get("vars") if isinstance(production.get("vars"), dict) else {}
        production_d1 = production.get("d1_databases") if isinstance(production.get("d1_databases"), list) else []
        production_db = next((item for item in production_d1 if isinstance(item, dict) and item.get("binding") == "DB"), {})
        if production_vars.get("APP_ENV") != "production":
            collector.fail("production worker gate", rel(path, repo_root), "env.production APP_ENV must be production before cutover.")
        if is_placeholder_id(str(production_db.get("database_id", ""))):
            collector.fail("production worker gate", rel(path, repo_root), "env.production D1 database_id is placeholder.")

    top_level_d1 = config.get("d1_databases") if isinstance(config.get("d1_databases"), list) else []
    top_level_db = next((item for item in top_level_d1 if isinstance(item, dict) and item.get("binding") == "DB"), {})
    if is_placeholder_id(str(top_level_db.get("database_id", ""))):
        collector.warn("top-level worker config", rel(path, repo_root), "Top-level D1 id is placeholder; use env.staging only for internal beta.")
    top_vars = config.get("vars") if isinstance(config.get("vars"), dict) else {}
    if not top_vars.get("R2_ACCOUNT_ID"):
        collector.warn("top-level worker config", rel(path, repo_root), "Top-level R2 account id is empty; use env.staging only for internal beta.")


def check_editing_cloudbuild(repo_root: Path, collector: Collector) -> None:
    path = repo_root / "services/editing/cloudbuild.yaml"
    text = read_text(path, collector)
    if text is None:
        return

    substitutions = parse_simple_substitutions(text)
    if substitutions.get("_SERVICE_NAME") == "hoopclips-editing-staging":
        collector.pass_("editing cloud run service", rel(path, repo_root), "Cloud Build targets the staging editing service.")
    else:
        collector.fail("editing cloud run service", rel(path, repo_root), "_SERVICE_NAME must be hoopclips-editing-staging for internal beta.")

    for key in ("_R2_SOURCE_BUCKET", "_R2_OUTPUT_BUCKET"):
        if str(substitutions.get(key, "")).endswith("-staging"):
            collector.pass_("editing r2 buckets", rel(path, repo_root), f"{key} is staging-scoped.")
        else:
            collector.fail("editing r2 buckets", rel(path, repo_root), f"{key} must be staging-scoped.")

    for key, expected in REQUIRED_AI_EDIT_SUBSTITUTIONS.items():
        if substitutions.get(key) == expected:
            collector.pass_("editing ai edit substitution", rel(path, repo_root), f"{key} is explicit.")
            if key in {"_AI_EDIT_ENABLED", "_AI_EDIT_LIVE_RENDER_ENABLED"}:
                collector.warn("editing ai edit internal beta default", rel(path, repo_root), f"{key} defaults enabled for staging; verify this is intentional before deploy.")
        else:
            collector.fail("editing ai edit substitution", rel(path, repo_root), f"{key} must be explicit and default true for internal beta.")

    for key, expected in REQUIRED_GPT_RERANK_SUBSTITUTIONS.items():
        if substitutions.get(key) == expected:
            collector.pass_("editing gpt reranker substitution", rel(path, repo_root), f"{key} is explicit for quality-beta staging.")
        else:
            collector.fail("editing gpt reranker substitution", rel(path, repo_root), f"{key} must be explicit for quality-beta staging.")

    env_line = find_arg_value_after(text, "--set-env-vars")
    if env_line and "HOOPS_ENVIRONMENT=staging" in env_line and "HOOPS_RENDER_STORAGE_PROVIDER=r2" in env_line:
        collector.pass_("editing cloud env", rel(path, repo_root), "Cloud Run deploy sets staging R2 render environment.")
    else:
        collector.fail("editing cloud env", rel(path, repo_root), "Cloud Run deploy must set staging R2 render environment.")

    required_ai_edit_env_mappings = (
        "HOOPS_AI_EDIT_ENABLED=${_AI_EDIT_ENABLED}",
        "HOOPS_AI_EDIT_LIVE_RENDER_ENABLED=${_AI_EDIT_LIVE_RENDER_ENABLED}",
        "HOOPS_AI_EDIT_REVISION_ENABLED=${_AI_EDIT_REVISION_ENABLED}",
        "HOOPS_AI_EDIT_TEMPLATE_PACK_ENABLED=${_AI_EDIT_TEMPLATE_PACK_ENABLED}",
        *REQUIRED_GPT_RERANK_ENV_MAPPINGS,
    )
    missing_env_mappings = [name for name in required_ai_edit_env_mappings if not env_line or name not in env_line]
    if missing_env_mappings:
        collector.fail("editing ai edit env mapping", rel(path, repo_root), f"Missing env mappings: {', '.join(missing_env_mappings)}.")
    else:
        collector.pass_("editing ai edit env mapping", rel(path, repo_root), "AI Edit kill switches and GPT quality limits map into Cloud Run env.")

    if env_line and REQUIRED_GPT_RERANK_ENV_MAPPINGS[-1] in env_line:
        collector.pass_("editing gpt reranker env mapping", rel(path, repo_root), "GPT highlight reranker launch switch maps into Cloud Run env.")
    else:
        collector.fail("editing gpt reranker env mapping", rel(path, repo_root), "Cloud Run deploy must map the GPT highlight reranker launch switch.")

    gpt_enabled = substitutions.get("_AI_CLIP_GPT_EDITOR_ENABLED") == "true" or substitutions.get("_GPT_HIGHLIGHT_RERANKER_ENABLED") == "true"
    if "HOOPS_OPENAI_API_KEY" not in text and not gpt_enabled:
        collector.pass_("openai secret gate", rel(path, repo_root), "OpenAI key is not required while GPT clip editor defaults disabled.")
    elif "HOOPS_OPENAI_API_KEY" in text:
        collector.pass_("openai secret gate", rel(path, repo_root), "OpenAI key secret name is configured without a secret value in source.")
    else:
        collector.fail("openai secret gate", rel(path, repo_root), "GPT reranker is enabled but no OpenAI key secret name is configured.")

    secret_line = find_arg_value_after(text, "--set-secrets")
    missing_secret_names = [
        name
        for name in ("HOOPS_EDITING_SERVICE_SECRET", "HOOPS_R2_ACCESS_KEY_ID", "HOOPS_R2_SECRET_ACCESS_KEY", "HOOPS_OPENAI_API_KEY")
        if not secret_line or name not in secret_line
    ]
    if missing_secret_names:
        collector.fail("editing deploy secret names", rel(path, repo_root), f"Missing Cloud Run secret names: {', '.join(missing_secret_names)}.")
    else:
        collector.pass_("editing deploy secret names", rel(path, repo_root), "Cloud Run deploy references required secret names only.")

    if "HOOPS_SENTRY_DSN" not in text:
        collector.warn("backend sentry gate", rel(path, repo_root), "Editing Cloud Build does not configure backend Sentry DSN.")
    if "STATSIG" not in text.upper():
        collector.warn("statsig gate", rel(path, repo_root), "Editing Cloud Build does not configure Statsig as remote flag source.")
    if "HOOPS_REVENUECAT_REST_API_KEY" not in text and "REVENUECAT_REST_API_KEY" not in text:
        collector.warn("backend revenuecat gate", rel(path, repo_root), "Editing Cloud Build does not configure RevenueCat REST verifier secret.")

    if "--allow-unauthenticated" in text:
        if "HOOPS_EDITING_SERVICE_SECRET" in text:
            collector.warn("editing ingress posture", rel(path, repo_root), "Cloud Run allows unauthenticated ingress; staging relies on shared-secret enforcement and Worker mediation.")
        else:
            collector.fail("editing ingress posture", rel(path, repo_root), "Unauthenticated Cloud Run ingress requires shared-secret enforcement.")


def check_analysis_cloudbuild(repo_root: Path, collector: Collector) -> None:
    path = repo_root / "ios/backend/cloudbuild.yaml"
    text = read_text(path, collector)
    if text is None:
        return

    substitutions = parse_simple_substitutions(text)
    for key, expected in REQUIRED_ANALYSIS_TEAM_SCAN_SUBSTITUTIONS.items():
        if substitutions.get(key) == expected:
            collector.pass_("analysis team scan substitution", rel(path, repo_root), f"{key} is explicit for selected-team beta quality.")
        else:
            collector.fail("analysis team scan substitution", rel(path, repo_root), f"{key} must be explicit for selected-team beta quality.")

    env_line = find_arg_value_after(text, "--set-env-vars")
    missing_env_mappings = [name for name in REQUIRED_ANALYSIS_TEAM_SCAN_ENV_MAPPINGS if not env_line or name not in env_line]
    if missing_env_mappings:
        collector.fail("analysis team scan env mapping", rel(path, repo_root), f"Missing env mappings: {', '.join(missing_env_mappings)}.")
    else:
        collector.pass_("analysis team scan env mapping", rel(path, repo_root), "Selected-team scan limits map into Cloud Run env.")

    secret_line = find_arg_value_after(text, "--set-secrets")
    if secret_line and "HOOPS_OPENAI_API_KEY=HOOPS_OPENAI_API_KEY:latest" in secret_line:
        collector.pass_("analysis openai secret gate", rel(path, repo_root), "OpenAI key secret name is configured for team scan without a source value.")
    else:
        collector.fail("analysis openai secret gate", rel(path, repo_root), "Selected-team scan requires the HOOPS_OPENAI_API_KEY secret name in Cloud Run deploy config.")


def check_free_daily_edit_chances(repo_root: Path, collector: Collector) -> None:
    checks = [
        (
            repo_root / "services/control-plane/src/routes/public.ts",
            rf"const\s+DEFAULT_FREE_DAILY_QUOTA\s*=\s*{REQUIRED_FREE_DAILY_EDIT_CHANCES}\s*;",
            "control-plane free quota fallback",
            "Control-plane fallback quota returns 3 Free analyses/edits per day.",
            "Control-plane DEFAULT_FREE_DAILY_QUOTA must stay at 3 for internal beta.",
        ),
        (
            repo_root / "ios/backend/app/config.py",
            rf'daily_quota=int\(os\.getenv\("HOOPS_DAILY_QUOTA", "{REQUIRED_FREE_DAILY_EDIT_CHANCES}"\)\)',
            "analysis backend free quota default",
            "Local analysis backend defaults Free daily quota to 3.",
            "Analysis backend HOOPS_DAILY_QUOTA default must stay at 3.",
        ),
        (
            repo_root / "ios/backend/app/editing.py",
            rf'"free":\s*PlanTierPolicy\([^)]*maxDailyRenders={REQUIRED_FREE_DAILY_EDIT_CHANCES}\s*,',
            "editing free render quota",
            "Editing backend Free policy allows 3 AI renders per day.",
            "Editing backend Free maxDailyRenders must stay at 3.",
        ),
        (
            repo_root / "ios/HoopsClips/HoopsClips/Models/CloudEditTypes.swift",
            rf"static\s+let\s+freeDefault\s*=\s*CloudEditPolicySummary\([^)]*maxDailyRenders:\s*{REQUIRED_FREE_DAILY_EDIT_CHANCES}\s*,",
            "ios free policy copy",
            "iOS Free policy default shows 3 AI edits per day.",
            "iOS CloudEditPolicySummary.freeDefault must stay at 3.",
        ),
        (
            repo_root / "ios/HoopsClipsUITests/HoopsClipsUITests.swift",
            rf'"{REQUIRED_FREE_DAILY_EDIT_CHANCES} AI edits/day"',
            "ios free policy ui smoke",
            "iOS UI smoke expects 3 AI edits/day copy.",
            "iOS Free/Pro UI smoke must assert 3 AI edits/day copy.",
        ),
    ]

    for path, pattern, check_name, pass_detail, fail_detail in checks:
        text = read_text(path, collector)
        if text is None:
            continue
        if re.search(pattern, text, flags=re.DOTALL):
            collector.pass_(check_name, rel(path, repo_root), pass_detail)
        else:
            collector.fail(check_name, rel(path, repo_root), fail_detail)


def check_workflows(repo_root: Path, collector: Collector) -> None:
    deploy_path = repo_root / ".github/workflows/cloud-edit-deploy-preflight.yml"
    deploy_text = read_text(deploy_path, collector)
    if deploy_text is not None:
        for key in REQUIRED_DEPLOY_INPUTS:
            if key in deploy_text:
                collector.pass_("cloud deploy workflow inputs", rel(deploy_path, repo_root), f"{key} presence is checked without printing values.")
            else:
                collector.fail("cloud deploy workflow inputs", rel(deploy_path, repo_root), f"{key} is not checked by deploy workflow.")
        for snippet, label in (
            ("environment: staging", "staging environment"),
            ("id-token: write", "GCP WIF permission"),
            ("wrangler secret list --env staging --format json", "Worker secret-name check"),
            ("wrangler deployments list --env staging --json", "deployment read scope check"),
            ("wrangler deploy", "staging deploy command"),
            ("wrangler rollback", "staging rollback command"),
            ("deploy:staging:dry-run", "staging dry-run check"),
        ):
            if snippet in deploy_text:
                collector.pass_("cloud deploy workflow coverage", rel(deploy_path, repo_root), f"Workflow includes {label}.")
            else:
                collector.fail("cloud deploy workflow coverage", rel(deploy_path, repo_root), f"Workflow is missing {label}.")

    release_path = repo_root / ".github/workflows/release-secrets-preflight.yml"
    release_text = read_text(release_path, collector)
    if release_text is not None:
        for snippet, label in (
            ('HOOPS_CLOUD_ANALYSIS_BASE_URL: ${{ vars.HOOPS_CLOUD_ANALYSIS_BASE_URL }}', "production cloud analysis URL input"),
            ('HOOPS_CLOUD_EDIT_BASE_URL: ${{ vars.HOOPS_CLOUD_EDIT_BASE_URL }}', "production cloud edit URL input"),
            ('require_non_empty "HOOPS_CLOUD_ANALYSIS_BASE_URL"', "non-empty Release analysis URL"),
            ('require_non_empty "HOOPS_CLOUD_EDIT_BASE_URL"', "non-empty Release edit URL"),
            ('require_exact "HOOPS_CLOUD_LAUNCH_MODE" "enabled"', "Release cloud-enabled build setting"),
            ('require_plist_exact "HOOPSCloudLaunchMode" "enabled"', "built Info.plist cloud-enabled mode"),
            ('require_plist_non_empty "HOOPSCloudAnalysisBaseURL"', "built Info.plist analysis URL"),
            ('require_plist_non_empty "HOOPSCloudEditBaseURL"', "built Info.plist edit URL"),
        ):
            if snippet in release_text:
                collector.pass_("release cloud gate", rel(release_path, repo_root), f"Release preflight enforces {label}.")
            else:
                collector.fail("release cloud gate", rel(release_path, repo_root), f"Release preflight is missing {label}.")


def check_ios_configs(repo_root: Path, collector: Collector) -> None:
    release_path = repo_root / "ios/HoopsClips/HoopsClips/Config/Release.xcconfig"
    release_text = read_text(release_path, collector)
    if release_text is not None:
        for pattern, label in (
            (r"HOOPS_APP_ENV\s*=\s*production", "production app env"),
            (r"HOOPS_CLOUD_LAUNCH_MODE\s*=\s*enabled", "cloud launch enabled"),
        ):
            if re.search(pattern, release_text, flags=re.MULTILINE):
                collector.pass_("ios release cloud gate", rel(release_path, repo_root), f"Release config keeps {label}.")
            else:
                collector.fail("ios release cloud gate", rel(release_path, repo_root), f"Release config must keep {label}.")
        for pattern, label in (
            (r"HOOPS_CLOUD_ANALYSIS_BASE_URL\s*=", "cloud analysis URL override"),
            (r"HOOPS_CLOUD_EDIT_BASE_URL\s*=", "cloud edit URL override"),
        ):
            if re.search(pattern, release_text, flags=re.MULTILINE):
                collector.fail("ios release cloud gate", rel(release_path, repo_root), f"Release config must not hardcode {label}; CI/LocalSecrets must provide it.")
            else:
                collector.pass_("ios release cloud gate", rel(release_path, repo_root), f"Release config does not hardcode {label}.")

    internal_path = repo_root / "ios/HoopsClips/HoopsClips/Config/InternalStaging.xcconfig"
    internal_text = read_text(internal_path, collector)
    if internal_text is not None:
        if re.search(r"^#include", internal_text, flags=re.MULTILINE):
            collector.fail("ios internal staging overlay", rel(internal_path, repo_root), "InternalStaging must not include Release or LocalSecrets.")
        else:
            collector.pass_("ios internal staging overlay", rel(internal_path, repo_root), "InternalStaging does not include secret-bearing configs.")
        if "HOOPS_CLOUD_LAUNCH_MODE = internal_only" in internal_text:
            collector.pass_("ios internal staging launch mode", rel(internal_path, repo_root), "Internal staging uses internal_only cloud mode.")
        else:
            collector.fail("ios internal staging launch mode", rel(internal_path, repo_root), "Internal staging must use internal_only cloud mode.")
        if internal_text.count("hoopsclips-control-plane-staging") >= 2:
            collector.pass_("ios internal staging urls", rel(internal_path, repo_root), "Internal staging analysis/edit URLs point to staging Worker.")
        else:
            collector.fail("ios internal staging urls", rel(internal_path, repo_root), "Internal staging analysis/edit URLs must point to staging Worker.")


def check_observability_and_flags(repo_root: Path, collector: Collector) -> None:
    editing_main = repo_root / "services/editing/editing_app/main.py"
    editing_text = read_text(editing_main, collector)
    if editing_text is None:
        return

    for flag in (
        "HOOPS_AI_EDIT_ENABLED",
        "HOOPS_AI_EDIT_LIVE_RENDER_ENABLED",
        "HOOPS_AI_EDIT_REVISION_ENABLED",
        "HOOPS_AI_EDIT_TEMPLATE_PACK_ENABLED",
    ):
        if flag in editing_text:
            collector.pass_("editing kill switch implementation", rel(editing_main, repo_root), f"{flag} is resolved by the editing service.")
        else:
            collector.fail("editing kill switch implementation", rel(editing_main, repo_root), f"{flag} is not resolved by the editing service.")

    if '"featureFlags": feature_flags.model_dump()' in editing_text:
        collector.pass_("editing version flags", rel(editing_main, repo_root), "Editing /version exposes non-secret feature flags.")
    else:
        collector.fail("editing version flags", rel(editing_main, repo_root), "Editing /version must expose feature flags for staging verification.")

    if "sentry_sdk" in editing_text:
        collector.pass_("editing sentry breadcrumbs", rel(editing_main, repo_root), "Editing service can add Sentry breadcrumbs/messages when SDK is configured.")
    else:
        collector.warn("editing sentry breadcrumbs", rel(editing_main, repo_root), "Editing service has no Sentry breadcrumb integration.")

    if "statsig" not in editing_text.lower():
        collector.warn("statsig runtime source", rel(editing_main, repo_root), "Statsig is not wired as the editing service flag source of truth.")


def check_secret_url_logging_guards(repo_root: Path, collector: Collector) -> None:
    editing_main = repo_root / "services/editing/editing_app/main.py"
    editing_text = read_text(editing_main, collector)
    if editing_text is not None and '"url" not in key.lower() and "secret" not in key.lower()' in editing_text:
        collector.pass_("editing event redaction", rel(editing_main, repo_root), "Structured event fields drop URL and secret keys.")
    else:
        collector.fail("editing event redaction", rel(editing_main, repo_root), "Structured event logging must filter URL and secret keys.")

    public_routes = repo_root / "services/control-plane/src/routes/public.ts"
    route_text = read_text(public_routes, collector)
    if route_text is not None:
        presign_log = re.search(r'console\.info\(\s*JSON\.stringify\(\{(?P<body>.*?)\}\)\s*\)', route_text, flags=re.DOTALL)
        if presign_log and "uploadUrl" not in presign_log.group("body") and "sourceObjectKey" not in presign_log.group("body"):
            collector.pass_("control-plane presign log", rel(public_routes, repo_root), "Presign console log omits signed URLs and object keys.")
        else:
            collector.fail("control-plane presign log", rel(public_routes, repo_root), "Presign console log must not include signed URLs or object keys.")


def check_literal_secret_values(repo_root: Path, collector: Collector) -> None:
    paths = [
        repo_root / ".github/workflows/release-secrets-preflight.yml",
        repo_root / ".github/workflows/cloud-edit-deploy-preflight.yml",
        repo_root / "services/control-plane/wrangler.jsonc",
        repo_root / "services/editing/cloudbuild.yaml",
        repo_root / "services/editing/README.md",
        repo_root / "services/editing/editing_app/gpt_reranker.py",
        *sorted((repo_root / "docs").glob("phase_launch*.md")),
        *sorted((repo_root / "docs").glob("phase_clip1_gpt*.md")),
    ]
    suspicious: list[str] = []
    pattern = re.compile(r"(?i)(secret|token|access[_-]?key|api[_-]?key)\s*[:=]\s*['\"]?([A-Za-z0-9_./+=-]{20,})")
    for path in paths:
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = pattern.search(line)
            if not match:
                continue
            value = match.group(2)
            if any(marker in line for marker in ("${{", "${", "<", "...", ":latest", "--env", "required", "missing", "present")):
                continue
            if value.upper() in REQUIRED_WORKER_SECRETS or value.upper() in REQUIRED_DEPLOY_INPUTS:
                continue
            suspicious.append(f"{rel(path, repo_root)}:{line_number}")
    if suspicious:
        collector.fail("literal secret scan", "repo", f"Potential literal secret values found at: {', '.join(suspicious)}.")
    else:
        collector.pass_("literal secret scan", "repo", "No literal secret-like values found in launch configs/docs.")


def check_phase_docs(repo_root: Path, collector: Collector) -> None:
    docs = sorted((repo_root / "docs").glob("phase_launch*.md"))
    if not docs:
        collector.warn("phase launch docs", "docs", "No phase_launch docs found.")
        return
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)
    if "Production cloud cutover remains blocked" in combined or "Production cloud cutover" in combined:
        collector.warn("production cutover docs", "docs/phase_launch*.md", "Launch docs still record production cutover blockers.")
    if "CLOUDFLARE_API_TOKEN" in combined:
        collector.warn("ci credential docs", "docs/phase_launch*.md", "Launch docs still record missing CI deploy credential proof.")
    if "ready for production" in combined.lower() or "production ready" in combined.lower():
        collector.fail("production readiness claim", "docs/phase_launch*.md", "Launch docs contain a production-ready claim while gates remain unresolved.")
    else:
        collector.pass_("production readiness claim", "docs/phase_launch*.md", "Launch docs do not claim production readiness.")


def load_jsonc(path: Path, collector: Collector) -> Any:
    text = read_text(path, collector)
    if text is None:
        return None
    try:
        return json.loads(strip_jsonc_comments(text))
    except json.JSONDecodeError as error:
        collector.fail("json parse", str(path), f"Could not parse JSONC: {error.msg}.")
        return None


def strip_jsonc_comments(text: str) -> str:
    output: list[str] = []
    in_string = False
    escaping = False
    i = 0
    while i < len(text):
        char = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if in_string:
            output.append(char)
            if escaping:
                escaping = False
            elif char == "\\":
                escaping = True
            elif char == '"':
                in_string = False
            i += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            i += 1
            continue
        if char == "/" and nxt == "/":
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue
        if char == "/" and nxt == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        output.append(char)
        i += 1
    return "".join(output)


def read_text(path: Path, collector: Collector) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        collector.fail("file exists", str(path), "Required config file is missing.")
    except UnicodeDecodeError:
        collector.fail("file encoding", str(path), "Could not read file as UTF-8.")
    return None


def parse_simple_substitutions(text: str) -> dict[str, str]:
    substitutions: dict[str, str] = {}
    in_substitutions = False
    for line in text.splitlines():
        if line.strip() == "substitutions:":
            in_substitutions = True
            continue
        if in_substitutions and line and not line.startswith(" "):
            break
        if in_substitutions:
            match = re.match(r'\s{2}(_[A-Z0-9_]+):\s*"?([^"]*)"?\s*$', line)
            if match:
                substitutions[match.group(1)] = match.group(2)
    return substitutions


def find_arg_value_after(text: str, flag: str) -> str | None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == f"- {flag}" and index + 1 < len(lines):
            value = lines[index + 1].strip()
            if value in {"- >-", "- >", "- |", "- |-"}:
                block_lines: list[str] = []
                for block_line in lines[index + 2 :]:
                    if block_line.strip().startswith("- "):
                        break
                    block_lines.append(block_line.strip())
                return " ".join(block_lines)
            if value.startswith("- "):
                return value[2:].strip()
    return None


def read_required_secret_names(config: dict[str, Any]) -> list[str]:
    secrets = config.get("secrets")
    if not isinstance(secrets, dict):
        return []
    required = secrets.get("required")
    if not isinstance(required, list):
        return []
    return [item for item in required if isinstance(item, str)]


def is_placeholder_id(value: str) -> bool:
    return not value or value == "00000000-0000-0000-0000-000000000000"


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
    print("HoopClips backend/config launch preflight")
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
