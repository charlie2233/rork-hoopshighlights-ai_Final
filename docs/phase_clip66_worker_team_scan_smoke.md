# Phase Clip66: Worker Team Scan Smoke

## Goal

Add a no-secret-output smoke harness for the staging Worker team-scan path:

1. create an analysis job through the Worker
2. upload one real MP4 to the returned presigned upload target
3. call `POST /v1/analysis/jobs/{jobId}/team-scan`
4. optionally start analysis for a selected scan-backed team or all teams

This proves the iOS launch flow can keep iOS as the upload/control surface while cloud services own scan, selection gating, and analysis.

## Script

`scripts/worker_team_scan_smoke.py`

Required inputs:

```bash
WORKER_BASE_URL="https://<staging-worker>"
HOOPS_TEAM_SCAN_SMOKE_VIDEO_PATH="/absolute/path/to/local-smoke.mp4"
python3 scripts/worker_team_scan_smoke.py
```

Optional selected-team proof:

```bash
python3 scripts/worker_team_scan_smoke.py \
  --worker-url "$WORKER_BASE_URL" \
  --video-path "$HOOPS_TEAM_SCAN_SMOKE_VIDEO_PATH" \
  --start-selected-team \
  --confidence-threshold 0.85
```

Optional all-teams proof:

```bash
python3 scripts/worker_team_scan_smoke.py \
  --worker-url "$WORKER_BASE_URL" \
  --video-path "$HOOPS_TEAM_SCAN_SMOKE_VIDEO_PATH" \
  --start-all-teams
```

## Safety

- The script does not print `uploadUrl`, presigned source/download URLs, object keys, tokens, credentials, authorization headers, or signatures.
- Failure payloads go to stderr and pass through the same sanitizer.
- Selected-team start uses the first detected team unless `--selected-team-id` or `--selected-color-label` is provided.
- Selected-team start sends `includeUncertain: true` so lower-confidence but reviewable clips remain available to users.

## Launch Use

Run this after:

- the Worker is deployed with `INFERENCE_BASE_URL`
- the Worker has `INFERENCE_SHARED_SECRET`
- the inference/backend service includes `POST /v1/team-scan`
- R2 upload/read permissions are live

The smoke is a release evidence gate, not an accuracy claim. The 85% selected-team highlight target still requires labeled footage evaluation across team ownership, made/missed shot outcome, blocks, steals, and uncertain-review behavior.

## Validation

Fresh validation for this branch update:

```bash
python3 -m unittest scripts.test_worker_team_scan_smoke -v
# Result: 3 tests passed

python3 -m unittest discover -s scripts -p 'test_*.py' -v
# Result: 49 tests passed

npm --prefix services/control-plane run typecheck
# Result: passed

npm --prefix services/control-plane test
# Result: 26 tests passed

PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
# Result: 153 tests passed

PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
# Result: 93 tests passed
```

`git diff --check` passed before staging. A direct worktree-local `ios/backend/.venv/bin/python` path does not exist in this worktree, and system `python3` lacks `fastapi`/`pydantic`, so the backend suites were run with the existing repo venv from the main checkout while loading this worktree's source paths.

Live staging smoke remains blocked until CI/deploy billing is unblocked and staging Worker/backend settings are verified current.

## CI Evidence After Push

Pushed commit: `f21ff85aedda64ad84cb0690f18c9b4e7a8925a0`

- PR: `https://github.com/charlie2233/rork-hoopshighlights-ai_Final/pull/32`
- `Cloud Edit Deploy Preflight`: run `26505121132`
  - `Editing backend Python tests`: job `78055378258`, failed before steps, no failed log available
  - `Worker typecheck and dry run`: job `78055378272`, failed before steps
  - `Verify cloud edit deploy secrets`: job `78055387670`, skipped
- `iOS Internal TestFlight Upload`: run `26505121057`
  - `No-secret internal staging codecheck`: job `78055378209`, failed before steps, no failed log available
  - `Build internal staging TestFlight archive`: job `78055379021`, skipped

This still blocks internal TestFlight submission and live staging team-scan smoke evidence. The prior runs on this branch exposed the GitHub account billing/spend-limit message; the fresh run has the same no-steps/no-logs failure shape.
