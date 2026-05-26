# Phase Clip3: Shot-Aware Highlight Quality

Date: 2026-05-25
Branch: `codex/phase-clip3-shot-aware-highlight-quality`

## Goal

Improve GPT-led HoopClips highlight selection quality with a bias toward basketball-complete plays instead of cheap or tiny model payloads. The branch keeps the cloud-first architecture: backend CV/runtime systems create candidate clips, GPT judges only those existing candidates from compact metadata and sampled keyframes, and deterministic backend validators/renderers keep ownership of timestamps, FFmpeg, EditPlan validation, rendering, storage, and receipts.

## What Changed

- Raised quality-beta GPT sampling defaults:
  - Free: up to 8 candidate clips and 8 keyframes per clip.
  - Pro/internal: up to 30 candidate clips and 8 keyframes per clip.
  - Default sampled frame width is 768, JPEG quality is 4, max frame bytes is 300000, OpenAI image detail defaults to `high`, and structured output budget defaults to 3500 tokens.
- Added shot-aware keyframe roles beyond start/eventCenter/finish:
  - `preEvent`
  - `release`
  - `outcome`
  - `rim`
  - `midAction`
- Added candidate quality filters before GPT:
  - reject clips shorter than the backend minimum
  - reject clips whose event center is too close to clip start
  - reject clips without enough follow-through after the event center
- Added an ordinary/non-GPT selector guard so shot-like clips also need minimum setup and follow-through context when GPT is disabled or falls back.
- Added a shot-keyframe completeness gate before the GPT call. With quality-beta sampling, shot-like candidates must have setup, release, outcome, and rim keyframes extracted successfully before they can be sent to GPT.
- Added `qualityHints` to the compact GPT payload so the model sees timing-window expectations without receiving full video.
- Added strict GPT `qualitySignals` output:
  - `setupVisible`
  - `eventVisible`
  - `outcomeVisible`
  - `ballPathVisible`
  - `playerControlVisible`
  - `cleanCamera`
  - `fullPlayContext`
  - `reason`
- Added backend rejection of GPT-kept clips that still fail shot quality:
  - tiny clips
  - pre-basket-only shot windows
  - low highlight/watchability scores
  - unclear or non-basketball outcomes
  - missing event/outcome/clean camera
  - missing setup/full play context
  - made shots without visible ball path
  - made/missed shots without visible player control
- Updated Cloud Run staging substitutions and config preflight expectations to match the higher-quality defaults while keeping GPT launch switches disabled by default.

## Safety Rules Preserved

- GPT receives only sampled JPEG keyframes from existing candidate windows and compact metadata.
- GPT does not receive full source videos, presigned URLs, R2 credentials, storage keys, or source object keys.
- GPT cannot generate FFmpeg commands or renderer commands.
- GPT cannot invent clip IDs or exact timestamps.
- GPT is not asked to judge made-shot quality from only generic start/event/finish frames when richer shot-context roles are configured.
- Backend validators still produce and repair deterministic `EditPlan` JSON before rendering.
- iOS is unchanged; it remains a control surface for upload, status, preview, download, share, and user commands.

## Cost Notes

Cost is deliberately not the main constraint for this phase. The defaults spend more on visual context to improve clipping quality:

- more keyframes per candidate
- larger frames
- high image detail
- more Pro/internal candidates
- larger structured-output budget

The knobs remain configurable through environment variables and kill switches:

- `HOOPS_AI_CLIP_GPT_EDITOR_ENABLED`
- `HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP`
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE`
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO`
- `HOOPS_GPT_HIGHLIGHT_RERANK_FRAME_WIDTH`
- `HOOPS_GPT_HIGHLIGHT_RERANK_JPEG_QUALITY`
- `HOOPS_GPT_HIGHLIGHT_RERANK_MAX_IMAGE_BYTES`
- `HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL`
- `HOOPS_GPT_HIGHLIGHT_RERANK_MAX_OUTPUT_TOKENS`

## Validation

Commands run:

```sh
python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py scripts/launch_backend_config_preflight.py services/editing/tests/test_gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker ios.backend.tests.test_edit_plan_agent -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/launch_backend_config_preflight.py
```

Results:

- Python compile: passed.
- GPT reranker + edit-plan focused suite: 52 tests passed.
- Editing service focused suite: 37 tests passed, including local FFmpeg render/revision/download-history paths.
- iOS backend Python discovery: 46 tests passed.
- Services editing discovery: 56 tests passed.
- Scripts discovery: 34 tests passed.
- Launch backend config preflight: `pass=63 warn=12 fail=0`.

## Launch Recommendations

- Deploy this branch to staging only after the Cloudflare/GCP deploy secret blockers are cleared.
- Run a live cloud smoke using a real basketball sample with GPT enabled:
  - upload/import
  - cloud analysis candidate generation
  - GPT rerank with keyframes
  - Review
  - Export AI Edit
  - render
  - preview
  - More Hype revision
  - revised render
  - download/share
- Inspect the AI Work Receipt for sampled clip/frame counts, GPT applied/fallback status, rejected tiny/pre-basket candidates, and selected clip order.
- Keep production rollout gated until staging proves live render reliability, privacy/log redaction, provider config, and installed TestFlight smoke.
