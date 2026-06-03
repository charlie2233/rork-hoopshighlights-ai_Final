# Phase Launch Active Readiness Snapshot (2026-06-03)

Branch: `codex/phase-launch-proof-next`
Commit: `3b746b6`

## Preflight Verification Run

- Command: `python3 scripts/launch_backend_config_preflight.py --json`
  - Result: `status=pass`, `pass=85`, `warn=12`, `fail=0`
- Command: `python3 scripts/submission_readiness_preflight.py --skip-live --json`
  - Result: `status=fail`, `pass=22`, `warn=6`, `fail=4`

## Submission Fails

1. **Team-highlight accuracy evidence (hard blocker)**
   - Missing --team-accuracy-report from launch-grade human-reviewed labels.
   - Current status: 0/54 complete; 54 remaining.
   - Bundle files in progress:
     - `artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html`
     - `artifacts/team_highlight_labeling_bundle/label_status.json`
     - `artifacts/team_highlight_labeling_bundle/next_steps.md`

2. **Cloud deploy inputs (environment)**
   - Missing: `CLOUDFLARE_API_TOKEN`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`, `GCP_PROJECT_ID`, `GCP_REGION`

3. **iOS upload inputs (environment)**
   - Missing: `HOOPS_DEVELOPMENT_TEAM`, `HOOPS_REVENUECAT_API_KEY`, `HOOPS_GOOGLE_CLIENT_ID`, `HOOPS_GOOGLE_REVERSED_CLIENT_ID`, `HOOPS_FIREBASE_AUTH_API_KEY`, `HOOPS_SENTRY_DSN`, `APP_STORE_CONNECT_KEY_ID`, `APP_STORE_CONNECT_ISSUER_ID`, `APP_STORE_CONNECT_API_KEY_BASE64`, `HOOPS_PRIVACY_POLICY_URL`, `HOOPS_TERMS_OF_SERVICE_URL`

4. **Installed TestFlight smoke (doc-required blocker)**
   - `docs/phase_edit7g_post_testflight_internal_smoke.md` still records unproven post-install smoke.

## Current Warnings

- `devicectl` connected-device state could not be read in this environment.
- Live staging Worker and direct editing `/version` probes are currently skipped/failed by `staging_version_probe.py` with `URLError` in this environment.
- `docs/` launch blocker notes still intentionally include production cutover and credential staging blockers.

## Passes and Non-Blockers

- Backend config preflight: production-readiness claim remains intentionally blocked by design (no env.production).
- iOS settings and TestFlight internal overlay configuration checks pass.
- Internal staging upload artifact candidate exists in repo.
- 4 accuracy helper labels from scripts are unchanged and verified by local tests.

## Next Required Actions

- Finish manual human review to produce a launch-grade label report (`artifacts/team_highlight_accuracy_report.json`) then rerun submission readiness.
- Populate required deploy/upload secrets in environment and run secret-gated GitHub Actions on main.
- Install TestFlight internal build on trusted device and complete the full import→analysis→export→render→revision→share smoke with screenshot evidence.
- Re-run staging version probe when network access is available and confirm backend git SHA + feature flags.
