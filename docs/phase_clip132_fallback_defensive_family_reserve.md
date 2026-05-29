# Phase Clip132 Fallback Defensive Family Reserve

Date: 2026-05-29
Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Keep team-selected defensive highlights from being crowded out when GPT editing is disabled, unavailable, or falls back to deterministic EditPlan selection.

The GPT sampler and cloud pipeline already preserve defensive families beyond blocks and steals. The deterministic EditPlan reserve only protected `block` and `steal`, so short selected-team reels filled with higher-scoring buckets could drop lower-scored but important `forced_turnover` and `defensive_stop` clips.

## Architecture

- Cloud backend still owns analysis, clip quality selection, EditPlan generation, and rendering.
- iOS behavior is unchanged; iOS remains the control surface for upload, selection, status, preview, download, and share.
- No local iOS video analysis, rendering, composition, or export was added.
- No GPT prompt, FFmpeg command, secret, R2 credential, or presigned URL behavior changed.

## Change

- `reserve_defensive_highlight_families` now reserves one candidate each for:
  - `block`
  - `steal`
  - `forced_turnover`
  - `defensive_stop`
- `_defensive_highlight_family` now classifies forced/defensive turnovers as `forced_turnover` instead of folding them into `steal`.
- `_defensive_highlight_family` now classifies `Defensive Stop`, `Defense Stop`, and exact `Stop` labels as `defensive_stop`.
- `Stop and Pop Jumper` remains protected by existing classifier tests and does not become a defensive stop.

## Tests

Red test before implementation:

```bash
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_short_selected_team_plan_reserves_turnovers_and_defensive_stops_when_scoring_fills_reel -v
```

Initial result:

```text
FAILED (failures=1)
AssertionError: 'dark_defensive_stop' not found in ['dark_make_1', 'dark_make_2', 'dark_make_5', 'dark_forced_turnover']
```

Green focused result after implementation:

```text
Ran 1 test in 0.003s
OK
```

Broader backend quality validation:

```bash
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker ios.backend.tests.test_edit_plan_agent ios.backend.tests.test_pipeline_quality -v
```

Result:

```text
Ran 201 tests in 0.995s
OK
```

## Launch Notes

This improves the non-GPT fallback path for selected-team highlights, especially defensive possessions. It does not prove the full 85% launch accuracy target by itself; that still needs launch-grade labeled footage and an installed TestFlight smoke with wired iPhone evidence.

Clean-commit submission preflight:

```bash
python3 scripts/submission_readiness_preflight.py --skip-live
```

Result:

```text
pass=22 warn=2 fail=8
```

Remaining blockers:

- Launch-grade selected-team/highlight quality accuracy report is still missing.
- Wired iPhone is detected but unavailable for install/smoke testing.
- Live Worker and direct editing service probes were intentionally skipped.
- Main-branch Cloud Edit Deploy Preflight and iOS Internal TestFlight Upload workflows are stale for this checkout.
- Installed TestFlight post-install smoke remains unproven.
- Staging Worker editing route is not proven live.
- Cloudflare deploy credential proof is still missing.
- Live iOS kill-switch state is not proven through the Worker.

Live submission preflight:

```bash
python3 scripts/submission_readiness_preflight.py
```

Result:

```text
pass=22 warn=0 fail=11
```

Additional live findings:

- Staging Worker `/v1/editing/version` returned HTTP 404.
- Direct editing `/version` is deployed from a stale git sha.
- Direct editing `/version` is missing expected GPT/AI Edit feature flag keys in the live response.

Local route and flag-contract validation:

```bash
npm --prefix services/control-plane exec -- tsx --test services/control-plane/test/control-plane-editing-proxy.test.ts
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_version_reports_required_gpt_editor_flags -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
```

Results:

```text
control-plane editing proxy: 11 tests passed
GPT editor flag-contract focused test: OK
editing service suite: Ran 49 tests in 23.652s, OK
```

Conclusion: the Worker route and editing `/version` schema are covered locally; the live failures require deploying current control-plane and editing service sources, then rerunning the workflow/live preflight.
