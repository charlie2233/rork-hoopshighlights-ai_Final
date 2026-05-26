# Phase Clip7 Native Shot Signals Metadata

Branch: `codex/phase-clip7-native-shot-signals-metadata`

## Goal

Improve GPT-led highlight quality by carrying compact native shot-context signals from cloud analysis into cloud edit planning and GPT reranking. This gives the editor better evidence about setup, follow-through, event-center quality, and native outcome hints before it judges candidates.

## Architecture

- Cloud analysis computes `nativeShotSignals` for candidate clips.
- iOS relays those optional signals from cloud analysis clips into the cloud edit request. It does not analyze, compose, render, or export video.
- GPT receives only existing candidate clip metadata plus sampled keyframes. No full videos, source URLs, storage keys, presigned URLs, FFmpeg commands, or local file paths are sent.
- Backend validators still enforce clip bounds, shot setup/follow-through, template policy, watermark/outro rules, and render safety before deterministic FFmpeg rendering.

## Schema

`nativeShotSignals` is optional on `CloudClip`, `EditCandidateClip`, control-plane edit types, and iOS cloud edit candidate clips:

```json
{
  "isShotLike": true,
  "leadInSeconds": 2.0,
  "followThroughSeconds": 1.25,
  "setupContextScore": 1.0,
  "outcomeContextScore": 1.0,
  "eventCenterQuality": 0.94,
  "contextQualityScore": 0.91,
  "timingWindowOk": true,
  "outcome": "made",
  "outcomeConfidence": 0.74
}
```

Allowed outcomes are `made`, `missed`, `blocked`, `uncertain`, and `not_shot`.

## Safety

- Incoming client-provided shot signals are treated as hints. The editing backend re-derives lead-in, follow-through, setup score, outcome score, timing-window status, event-center quality, and context quality from the current clip bounds.
- A passed-through analysis outcome can improve GPT context, but it cannot relax deterministic timing gates.
- GPT payloads include `nativeShotSignals` inside compact candidate context and `qualityHints`; they still use strict Structured Outputs JSON.
- GPT edit patches still validate through `EditPlanPatch` and cannot include FFmpeg commands, shell commands, URLs, storage keys, or unsupported patch paths.

## Files

- `ios/backend/app/models.py`: added `CloudNativeShotSignals`.
- `ios/backend/app/pipeline.py`: attaches native shot signals after cloud candidate normalization.
- `ios/backend/app/editing.py`: added `NativeShotSignals`, backend re-derived signal helper, and compact agent context payload fields.
- `services/editing/editing_app/gpt_reranker.py`: includes native signals in GPT quality hints, rerank clip payloads, and revision patch context.
- `services/control-plane/src/types.ts`: adds optional native shot signals to Worker-facing types.
- `ios/HoopsClips/HoopsClips/Models/*` and `HighlightsViewModel.swift`: pass through optional signals from cloud analysis to cloud edit requests.

## Validation

Completed locally:

```bash
python3 -m py_compile ios/backend/app/models.py ios/backend/app/pipeline.py ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality ios.backend.tests.test_edit_plan_agent services.editing.tests.test_gpt_reranker -v
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
cd services/control-plane && npm ci
cd services/control-plane && npm test
cd services/control-plane && npm run typecheck
# Build iOS Apps MCP, profile hoopclips-ios:
# build_sim CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation
# test_sim CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation
xcrun xcresulttool get test-results summary --path /Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-05-26T10-34-58-491Z_pid20749_52cb4957.xcresult
```

Results:

- Python compile passed.
- Backend/GPT focused suite: 89 tests passed.
- Full iOS backend discovery: 84 tests passed.
- Full editing service discovery: 65 tests passed.
- Control-plane test suite: 20 tests passed.
- Control-plane typecheck passed.
- iOS Debug simulator build passed.
- iOS simulator tests passed: `result=Passed`, `passedTests=71`, `failedTests=0`, `skippedTests=3`, `totalTestCount=74`.

## Launch Notes

- This branch improves semantic editor inputs without changing launch gates.
- Live staging GPT/render smoke still requires deployed Worker and editing service plus valid Cloudflare/GCP/OpenAI secrets.
- Signed TestFlight archive and post-install iPhone smoke remain separate P0 launch blockers.
