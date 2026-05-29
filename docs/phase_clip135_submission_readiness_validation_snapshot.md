# Phase Clip135: Submission Readiness Validation Snapshot

Branch: `codex/phase-clip28-cloud-team-quick-scan`

Latest commit at validation: `5cc467e`

## Summary

This snapshot checks whether HoopClips is ready for internal iOS launch/TestFlight after the team-aware and GPT-led clipping quality work on this branch.

Result: **not ready for Apple submission yet**.

The local code/test surface is healthy, but provider-side and real-world evidence gates are still blocking submission:

- GitHub Actions deploy/upload runners are blocked by account billing or spending-limit state before any workflow step starts.
- Staging Worker `/v1/editing/version` is still live-stale and returns `404`.
- Direct staging editing `/version` is still deployed from stale source and missing required GPT/live-render flags.
- The wired iPhone is detected but unavailable, so installed TestFlight smoke cannot run.
- No launch-grade real labeled team-highlight accuracy report exists in the repo artifacts.

## Code Changes Covered

- `a995420` tightened the launch-grade team-highlight evaluator so selected-team defensive coverage must include forced turnovers and defensive stops, in addition to blocks and steals.
- `5cc467e` exposed forced-turnover and defensive-stop review segment counts in cloud analysis diagnostics.

These changes do not claim the 85% target by themselves. They make the eventual real-footage proof harder to overclaim.

## Local Validation

### Focused Regression Slice

Command:

```bash
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality scripts.test_team_highlight_accuracy_eval scripts.test_submission_readiness_preflight scripts.test_build_team_highlight_eval_payload scripts.test_launch_provider_input_handoff -v
```

Result:

```text
Ran 105 tests in 0.850s
OK
```

### Backend, Editing, Scripts, Control Plane

Commands:

```bash
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test
```

Results:

```text
ios/backend/tests: Ran 195 tests in 7.753s, OK
services/editing/tests: Ran 107 tests in 26.869s, OK
scripts: Ran 80 tests in 0.802s, OK
services/control-plane typecheck: passed
services/control-plane tests: 28 passed, 0 failed
```

### iOS Simulator Build And Tests

Tooling:

```text
XcodeBuildMCP session defaults:
project: ios/HoopsClips.xcodeproj
scheme: HoopsClips
configuration: Debug
simulator: iPhone 17 Pro
derivedDataPath: /tmp/hoopclips-clip45-dd
```

Build:

```text
build_sim CODE_SIGNING_ALLOWED=NO
status: SUCCEEDED
log: /Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-05-29T11-36-19-479Z_pid97875_5fb20308.log
```

Tests:

```text
test_sim CODE_SIGNING_ALLOWED=NO
xcresult status: succeeded
testsCount: 93
testsSkippedCount: 3
result bundle: /Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-05-29T11-36-41-029Z_pid97875_f5d237a0.xcresult
```

Notes:

- The `test_sim` tool call timed out at 120 seconds, but the underlying `xcodebuild` process completed after the tool timeout.
- The final `.xcresult` action status was `succeeded`.
- Existing warnings remain in `CloudAnalysisService.swift` and `VideoExportService.swift`; no compiler errors were reported.

### Formatting And Compile Checks

Commands:

```bash
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/models.py ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py scripts/evaluate_team_highlight_accuracy.py scripts/submission_readiness_preflight.py
git diff --cached --check
git diff --check
```

Result:

```text
passed
```

## Submission Preflight

Command:

```bash
python3 scripts/submission_readiness_preflight.py --skip-live
```

Result:

```text
pass=22 warn=2 fail=8
```

Key failures:

- Missing launch-grade labeled footage team-highlight accuracy report.
- Connected iPhone detected but unavailable.
- Required main-branch workflow evidence is stale relative to `5cc467e`.
- Installed TestFlight post-install smoke remains unproven.
- Staging Worker editing version route remains unproven.
- Cloudflare deploy credential proof remains missing.
- Live iOS kill-switch state through Worker remains unproven.

Command:

```bash
python3 scripts/submission_readiness_preflight.py
```

Result:

```text
pass=22 warn=0 fail=11
```

Additional live failures:

- Worker `GET /v1/editing/version` returned HTTP `404`.
- Direct editing `/version` was stale and missing required GPT/live-render feature flags.

## Deploy Attempt

Command:

```bash
gh workflow run "Cloud Edit Deploy Preflight" --ref codex/phase-clip28-cloud-team-quick-scan -f operation=deploy
```

Run:

```text
https://github.com/charlie2233/rork-hoopshighlights-ai_Final/actions/runs/26634921072
```

Result:

```text
failure before workflow steps started
```

GitHub check annotations:

```text
The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings
```

Impact:

- No Worker deploy occurred.
- No Cloud Run editing deploy occurred.
- No Worker version ID or Cloud Run revision ID was produced.
- The deploy failure is provider/account state, not a source/test failure.

## Device State

Command:

```bash
xcrun devicectl list devices
```

Result:

```text
charlie's iPhone: unavailable, iPhone 15 Pro
```

Impact:

- Installed TestFlight smoke cannot run until the phone is unlocked/trusted/available to CoreDevice.

## Accuracy Evidence State

Repo search found no local real footage, manual label JSON, or generated launch-grade accuracy artifact:

```bash
find artifacts docs -maxdepth 4 -type f \( -name '*team*accuracy*' -o -name '*team*highlight*eval*' -o -name '*manual*label*' -o -name '*analysis*result*' -o -name '*.json' \)
find . -maxdepth 5 -type f \( -name '*.mp4' -o -name '*.mov' -o -name '*.m4v' \)
```

Impact:

- Do not claim the 85% team-highlight/highlight-quality target yet.
- The repo has the evaluator and builder path, but still needs real cloud analysis output plus manual labels.

## Atlas/Browser Agent Prompt For Remaining Provider Gates

Use this prompt with the browser/Atlas agent if provider UI work is needed:

```text
You are helping unblock HoopClips internal TestFlight submission for repo charlie2233/rork-hoopshighlights-ai_Final.

Do not paste or reveal secret values in chat, screenshots, logs, or docs.

Tasks:
1. Open GitHub billing/settings for the charlie2233 account or owning org and fix the Actions runner blocker:
   "The job was not started because recent account payments have failed or your spending limit needs to be increased."
   Confirm GitHub Actions can start ubuntu-latest jobs again.
2. In repo charlie2233/rork-hoopshighlights-ai_Final, environment staging, confirm these inputs exist without showing values:
   - CLOUDFLARE_API_TOKEN
   - GCP_WORKLOAD_IDENTITY_PROVIDER
   - GCP_DEPLOY_SERVICE_ACCOUNT
   - GCP_PROJECT_ID
   - GCP_REGION
3. If CLOUDFLARE_API_TOKEN is missing or expired, create or rotate a Cloudflare API token scoped to the HoopClips account with Workers Scripts Edit and Account Settings Read at minimum, plus D1/R2 Edit only if required by the repo deploy preflight. Store it directly in GitHub environment secret staging/CLOUDFLARE_API_TOKEN. Do not paste the token anywhere.
4. Return only non-secret status:
   - GitHub Actions billing/spending fixed: yes/no
   - staging inputs present: list present/missing names only
   - Cloudflare token stored/rotated: yes/no
   - Any provider-side blocker remaining
```

## Launch Recommendation

Do not submit to Apple yet.

Next required proof sequence:

1. Fix GitHub Actions billing/spending-limit state.
2. Rerun `Cloud Edit Deploy Preflight` with `operation=deploy` on the launch branch or on `main` after merge.
3. Verify Worker and direct editing `/version` both match the launch commit and expose required AI Edit/GPT flags.
4. Unlock/trust the wired iPhone until `xcrun devicectl list devices` reports it as available.
5. Produce a real launch-grade labeled team-highlight report:
   - real cloud analysis result JSON
   - manual labels JSON
   - `python3 -m scripts.evaluate_team_highlight_accuracy artifacts/team_highlight_eval.json --json > artifacts/team_highlight_accuracy_report.json`
6. Rerun `python3 scripts/submission_readiness_preflight.py --team-accuracy-report artifacts/team_highlight_accuracy_report.json`.
7. Only after the preflight passes, run TestFlight upload and installed-device smoke.
