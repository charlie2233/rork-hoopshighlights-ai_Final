# Phase Launch27: Team Scan State and Provider Status

## Goal

Keep the pre-analysis team selection flow launch-safe while recording the latest non-secret provider status.

## Provider Status

The browser/provider agent reported:

- GitHub Actions hosted runners: unblocked; no failed-payment or spending-limit blocker was seen.
- GCP Secret Manager secrets: still not verified because Google Cloud project access is restricted.
- GCP deploy service account Secret Manager access: still not verified because Google Cloud IAM access is restricted.
- Cloudflare API token: still not created or updated because Cloudflare login is not available.

Remaining external blockers:

- Google Cloud console access for project `hoopsclips-9d38f`.
- Secret Manager secret versions for `HOOPS_EDITING_SERVICE_SECRET`, `HOOPS_R2_ACCESS_KEY_ID`, `HOOPS_R2_SECRET_ACCESS_KEY`, and `HOOPS_OPENAI_API_KEY`.
- Secret Manager Secret Accessor permission for the staging deploy service account.
- Cloudflare token creation/rescope and GitHub staging secret `CLOUDFLARE_API_TOKEN` update.

Read-only CI/provider audit confirmed:

- Branch PR codechecks at `944b089` are green:
  - Cloud Edit Deploy Preflight run `26659150878`: success.
  - iOS Internal TestFlight Upload run `26659150828`: success.
- Secret-gated deploy preflight run `26658372197` still failed on GCP Secret Manager access and Cloudflare Wrangler auth.
- Live staging is stale: Worker `/v1/editing/version` returns HTTP 404 and direct editing `/version` reports `gitSha=d00d0d5`.
- The wired iPhone is detected but unavailable, so installed TestFlight smoke is still not proven.

## Change

The iOS team quick-scan flow now tracks the active scan with a local scan ID. If the cloud scan is cancelled, errors before completion, or returns after the source video changes, the old scan cannot leave the UI stuck in the scanning/disabled state.

This keeps the launch flow usable:

1. Import video.
2. Cloud quick scan detects jersey-color teams.
3. User chooses a team or All teams.
4. Analysis starts only after a real selection.

The fix stays cloud-first. iOS still only uploads, shows status, and sends the selected team. It does not analyze or render video locally.

`scripts/launch_provider_input_handoff.py` now accepts `--ref` and defaults to the current branch when building safe provider-agent workflow commands. This keeps the next GCP/Cloudflare repair pass from accidentally validating or deploying stale `main` while this launch branch is still ahead.

Follow-up hardening in Phase Launch28 now also includes exact Cloudflare token form fields, requires GCP Secret Manager latest versions to be `ENABLED`, and makes the staging version probe fail when live version metadata is stale relative to the expected branch SHA.

## Verification

Commands run:

```bash
xcodebuild test \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 17' \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testTeamScanCancellationClearsInProgressState

PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest scripts.test_launch_provider_input_handoff scripts.test_submission_readiness_preflight -v

xcodebuild build-for-testing \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 17' \
  CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation

python3 scripts/launch_backend_config_preflight.py --json
python3 scripts/staging_version_probe.py --json
python3 scripts/launch_provider_input_handoff.py --json --ref codex/phase-clip28-cloud-team-quick-scan
python3 scripts/submission_readiness_preflight.py --json
```

Results:

- Focused iOS cancellation test: passed. Result bundle: `/Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClips-dbjgwzgujbxeswbuapfjrdblbgqm/Logs/Test/Test-HoopsClips-2026.05.29_13-06-30--0700.xcresult`.
- Launch/provider script tests: 28 tests passed.
- iOS Debug build-for-testing: `** TEST BUILD SUCCEEDED **`.
- Backend config preflight: `pass=79 warn=12 fail=0`.
- Provider handoff JSON/Markdown uses the explicit branch ref for Cloud Edit Deploy Preflight and iOS TestFlight preflight commands.
- Staging version probe: failed as expected with `worker_route_missing_and_editing_version_stale`.
- Submission readiness preflight: still fails because external launch gates are not complete.

## Launch Recommendation

After GCP and Cloudflare access are repaired, rerun the secret-gated Cloud Edit Deploy Preflight and live staging version probe before TestFlight upload or Apple submission.
