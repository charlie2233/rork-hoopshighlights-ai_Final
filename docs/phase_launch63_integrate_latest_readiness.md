# Phase Launch63 Integrate Latest Readiness

Date: 2026-05-30
Branch: `codex/phase-launch63-integrate-latest-readiness`
Base: `origin/main` at `dbb80ab`

## Scope

Integrated the latest locally validated launch-readiness branches without running a staging deploy or GitHub Actions job:

- `codex/phase-launch61-accuracy-collection-proof` at `2a385d2`
- `codex/phase-launch62-horizontal-swipe-polish` at `4b0cfe6`
- `codex/phase-clip155-gpt-editor-contract-gap` at `9adb19e`

This brings selected-team analysis fallback, smoother horizontal app swipes with honest AI work status copy, and the GPT sampling cap contract into one integration branch for the next local/device proof pass.

## Evidence

Commands run locally:

```bash
uv run --with-requirements ios/backend/requirements.txt --python 3.11 env PYTHONPATH=ios/backend:services/editing python -m unittest services.editing.tests.test_gpt_reranker ios.backend.tests.test_edit_plan_agent ios.backend.tests.test_team_quick_scan -v
```

Result: passed, 196 tests.

```bash
python3 -m py_compile ios/backend/app/api.py ios/backend/app/models.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py scripts/launch_backend_config_preflight.py
python3 scripts/launch_backend_config_preflight.py
```

Result: compile passed; launch preflight passed with `pass=81 warn=12 fail=0`.

```bash
npm --prefix services/control-plane ci
npm --prefix services/control-plane run typecheck && npm --prefix services/control-plane test
```

Result: dependencies installed cleanly; typecheck passed; 30 control-plane tests passed.

```bash
xcodebuildmcp build_sim
```

Result: Debug simulator build passed on iPhone 17. Build warnings are existing Swift 6/deprecation warnings in `CloudAnalysisService.swift` and `VideoExportService.swift`; no build errors.

```bash
xcodebuildmcp test_sim -only-testing:HoopsClipsTests
xcodebuildmcp test_sim -only-testing:HoopsClipsUITests/HoopsClipsUITests/testSettingsLaunchStatusOpensForGuestSession
```

Result: 94 unit tests passed, 1 focused UI smoke passed.

```bash
ruby -e 'require "yaml"; YAML.load_file("services/editing/cloudbuild.yaml"); YAML.load_file(".github/workflows/cloud-edit-deploy-preflight.yml"); puts "yaml parses"'
git diff --cached --check
```

Result: YAML parsed and staged diff check passed.

## Readiness Notes

- The branch keeps cloud ownership intact: cloud services own analysis fallback, GPT reranking controls, edit planning contracts, and render handoff.
- iOS remains a control surface for upload, selected-team review/start, status, preview, and share.
- The "AI is ..." app copy is tied to real upload, team scan, analysis, edit planning, queued render, rendering, and finalizing states. No artificial waits, fake ETA, or fake backend work were added.
- GPT sampling caps now match the launch contract: Free uses up to 8 candidate clips with 3 keyframes per clip; Pro/internal use 20-30 clips with 5-8 keyframes per clip.
- GitHub Actions and staging deploys were intentionally skipped on this integration branch to conserve Actions budget until a live proof run is worth spending.

## Blockers Before Submission

- Physical iPhone/TestFlight smoke still needs proof: install, import/upload, cloud team scan, selected-team analysis, review, AI Edit, render, preview, More Hype revision, revised preview, share/open-in.
- Staging deploy/version proof is still needed after deciding to spend the Actions/deploy budget.
- Production config review is still required for Worker URLs, editing URLs, R2 buckets, Sentry, Statsig, RevenueCat, Google config, and feature flags.
- Root workspace has unrelated dirty files and untracked Xcode project folders from other local work; this branch does not stage or modify them.
