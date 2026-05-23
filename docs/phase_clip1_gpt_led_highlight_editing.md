# Phase Clip1: GPT-Led Highlight Editing

Date: 2026-05-23
Branch: `codex/phase-clip1-gpt-led-highlight-editing`

## Architecture

HoopClips remains cloud-first. The cloud backend owns candidate expansion, keyframe extraction, GPT highlight selection, EditPlan planning, revision patching, deterministic validation, rendering, storage, and retention. The iOS app remains the upload, review, status, preview, download, share, and external-editor control surface.

GPT is the final highlight editor, not the renderer. Existing CV/runtime analysis still generates the candidate pool with high recall. GPT receives compact candidate metadata plus sampled keyframes only; full videos, source object keys, presigned URLs, storage credentials, and FFmpeg commands are not included in the model payload.

The renderer continues to execute only validated `EditPlan` JSON through the backend FFmpeg renderer.

## Pipeline

1. Existing analysis emits candidate clips.
2. Backend ranks candidates and expands the sampled pool according to plan-tier limits.
3. Backend extracts sampled keyframes per candidate:
   - `start`
   - `eventCenter`
   - `finish`
   - optional `action` / `rim` / context frames for Pro/internal limits
4. Backend builds compact clip context.
5. OpenAI Responses API is called with `store=false` and strict Structured Outputs JSON.
6. Backend validates GPT clip decisions and optional `planEdit`.
7. GPT-selected clips, captions, crop/slow-motion hints, story roles, and ordering feed deterministic EditPlan generation.
8. Renderer executes the repaired and validated EditPlan.

## Clip Context

Each candidate sent to GPT includes:

- `clipId`
- `start`
- `end`
- `duration`
- `eventCenter`
- `existingLabel`
- `confidence`
- `motionScore`
- `audioPeak`
- `watchabilityScore`
- `duplicateGroup`
- `templateId`
- `planTier`
- `sampledKeyframes`

The payload intentionally omits `sourceObjectKey`, source video URLs, full videos, R2 credentials, presigned URLs, and raw inference logs.

## GPT Output

Clip decisions use strict JSON:

- `clipId`
- `keep`
- `rejectReason`
- `highlightScore`
- `watchabilityScore`
- `basketballEvent`
- `outcome`
- `caption`
- `reason`
- `storyRole`: `opener`, `peak`, `filler`, or `closer`
- `suggestedEdit`

`suggestedEdit` includes:

- `slowMotion`
- `slowMotionCenter`
- `captionMoment`
- `cropFocus`
- `extendBeforeSeconds`
- `extendAfterSeconds`

`planEdit` lets GPT propose final ordering, pacing, captions, and slow-motion moments. The backend accepts only existing clip IDs and clamps or rejects unsafe edits during EditPlan validation.

Revision commands such as More Hype, NBA Style, and Shorter can use GPT-produced `EditPlanPatch` JSON when enabled. The backend rejects unsupported patch paths and any patch text containing FFmpeg commands before repair and validation.

## Feature Flags

- `HOOPS_AI_CLIP_GPT_EDITOR_ENABLED`: enables GPT-led clip selection.
- `HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP`: shared sampled-keyframe cap, clamped to `3...8`.
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE`: Free candidate cap, clamped to `1...8`.
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO`: Pro/internal candidate cap, clamped to `20...30`.
- `HOOPS_AI_CLIP_GPT_PLAN_EDIT_ENABLED`: applies GPT `planEdit` directives after validation.
- `HOOPS_AI_CLIP_GPT_REVISION_ENABLED`: allows GPT `EditPlanPatch` revision proposals.

Legacy `HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED` remains mapped for backward compatibility, but the launch-facing flag is now `HOOPS_AI_CLIP_GPT_EDITOR_ENABLED`.

## Cost Controls

Cost is intentionally not the primary constraint for this phase, but the rollout remains bounded by tier caps:

- Free: up to 8 candidate clips and 3 keyframes per clip.
- Pro/internal: 20 to 30 candidate clips and 5 to 8 keyframes per clip.
- JPEG keyframes are resized and capped by byte size before upload to the model.
- Requests use `store=false`.
- OpenAI key is required only when GPT editing is enabled.

## Fallback Behavior

If GPT is disabled, missing an API key, missing source video, fails keyframe extraction, returns invalid JSON, rejects every clip, or proposes an invalid patch, the backend falls back to deterministic candidate ranking and EditPlan generation. The AI Work Receipt records disabled/fallback/applied status, sampled clip/frame counts, story-order IDs, and whether GPT plan edit was applied.

## Validation

Validation must pass before rendering:

- existing clip IDs only
- no duplicate clip IDs
- source bounds stay inside candidate bounds
- caption moments and slow-motion ranges stay inside clip bounds
- template, preset, aspect ratio, effect, asset, watermark, outro, music, and policy limits enforced
- Free watermark/outro restored by repair
- render-cost and duration limits enforced
- unsupported patch paths rejected
- FFmpeg command strings rejected in GPT patches

## Tests

Focused tests cover:

- GPT disabled fallback
- keyframe sampling roles and limits
- strict Structured Outputs payload shape
- no full video/source object/presigned URL in GPT payload
- boring/duplicate clip rejection
- best clips selected
- captions generated
- GPT story order and `planEdit` ordering used by EditPlan
- invalid GPT patch rejection
- no FFmpeg commands accepted from GPT patch payloads

Commands run:

```bash
python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py services/editing/editing_app/main.py services/editing/editing_app/models.py scripts/launch_backend_config_preflight.py
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
python3 scripts/launch_backend_config_preflight.py --repo-root . --json
PYTHONPATH=. /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest scripts.test_launch_backend_config_preflight -v
git diff --check
```

Results:

- `test_gpt_reranker`: 7 tests passed.
- `test_edit_plan_agent`: 21 tests passed.
- `test_editing_service`: 37 tests passed, including local FFmpeg render/revision/download-history coverage.
- `test_launch_backend_config_preflight`: 2 tests passed.
- Backend config preflight: pass, 63 checks passing, 12 warnings, 0 failures.
- `git diff --check`: passed.

## Launch Recommendations

Keep all GPT clip-editor flags disabled in production until staging proves:

1. Worker-mediated `/version` exposes the intended flag snapshot.
2. OpenAI key is present only in the backend secret manager.
3. A live cloud render smoke proves sampled keyframes, GPT selection, EditPlan validation, render, preview, revision patch, revised render, and download.
4. Logs contain no R2 credentials, full presigned URLs, source video URLs, or raw model payloads.
5. iOS remains a control surface only.
