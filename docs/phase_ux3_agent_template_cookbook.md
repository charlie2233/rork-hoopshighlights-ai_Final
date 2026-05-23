# Phase UX3: Agent Template Cookbook

## Goal

Make HoopClips AI Edit feel more like a real creative editor by adding an Agent Template Cookbook layer for GPT/edit-agent strategy. The existing `TemplatePack` registry remains the renderer and policy source of truth. The cookbook tells GPT how to select, reject, order, caption, slow down, crop, and pace candidate clips before the deterministic backend validator and renderer execute the final `EditPlan`.

## Architecture

- Cloud backend owns analysis, GPT clip reranking, edit planning, revision planning, templates, validation, rendering, storage, and policy.
- iOS stays a control surface for upload/import, template choice, status/timeline, preview, download, share, and user revision commands.
- No full videos are sent to GPT. GPT receives existing candidate clip metadata plus sampled keyframe references from the existing GPT reranker flow.
- GPT does not generate FFmpeg commands, shell commands, file paths, storage keys, or render instructions.
- `TemplatePack` controls render defaults: aspect ratio, duration, captions, audio, effects, watermark/outro, and premium gating.
- `AgentTemplateCookbook` controls editor strategy: selection, rejection, ordering, captions, slow motion, crop focus, audio vibe, pacing, opener/closer, and story flow.

## Schema

Each cookbook JSON lives in `services/editing/templates/agent_cookbook/` and validates through `AgentTemplateCookbook`:

- `templateId`
- `agentStyleIntent`
- `selectionRules`
- `rejectionRules`
- `orderingRules`
- `captionRules`
- `effectRules`
- `audioRules`
- `targetDurationRules`
- `cropRules`
- `storyRules`
- `planTier`
- `enabledForFree`
- `enabledForPro`
- `enabledForInternal`

`build_agent_editing_context(templateId, clipPoolSummary, candidateClips)` returns a compact JSON-ready payload containing cookbook rules, renderer constraints, clip-pool summary, and top candidate metadata only. It excludes source objects, presigned URLs, render storage details, and full-video data.

## Templates

| Template ID | Strategy |
| --- | --- |
| `personal_highlight_v1` | Fast vertical hype reel, best plays first, bold captions, high slow motion. |
| `full_game_highlight_v1` | Clean 16:9 recap, chronological game flow, subtle captions/effects, more game audio. |
| `coach_review_v1` | Chronological film review, original audio, minimal captions/effects, full-play context. |
| `recruiting_reel_pro_v1` | Player showcase, skill clarity, strong individual plays, formal recruiting captions. |
| `cinematic_mixtape_pro_v1` | High-energy social edit, dramatic captions, aggressive slow motion, strong opener/closer. |
| `nba_recap_pro_v1` | Broadcast-style game recap, chronological story, lower-third tone, game-audio priority. |
| `team_highlight_pro_v1` | Team variety, offense/defense balance, player/action diversity, clean team captions. |

## Gating

- Base cookbooks are enabled for Free, Pro, and internal plans.
- Pro cookbooks are locked for Free and enabled for Pro/internal plans only.
- The existing backend policy still rejects Free attempts to create premium template jobs.
- This phase does not implement payment and does not enable Pro rendering for Free.

## GPT Integration

The existing GPT-led highlight reranker now includes `agentTemplateCookbook` in its structured prompt payload. This adds strategy context to the existing candidate/keyframe payload without adding a new GPT call.

The payload still uses:

- Existing candidate clips only.
- Keyframe references/images only, never full videos.
- Structured Outputs JSON.
- `store=false`.
- Backend validation and repair before rendering.

## Cost Notes

The cookbook adds small text metadata to the existing GPT request. It does not increase candidate caps, frame counts, or add extra GPT calls. Existing caps remain controlled by:

- `HOOPS_AI_CLIP_GPT_EDITOR_ENABLED`
- `HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP`
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE`
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO`
- `HOOPS_AI_CLIP_GPT_PLAN_EDIT_ENABLED`
- `HOOPS_AI_CLIP_GPT_REVISION_ENABLED`

## Fallback Behavior

- GPT disabled or unavailable still falls back to the existing deterministic candidate ranking/edit-plan path.
- If a cookbook file is missing at runtime, the backend can synthesize a conservative cookbook from the matching `TemplatePack`.
- Registry validation fails if a checked-in `TemplatePack` lacks a matching cookbook entry.

## Validation

Commands run:

```bash
python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-ux3-cookbook-mcp-dd -skipMacroValidation -quiet build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-ux3-cookbook-mcp-dd -skipMacroValidation -quiet build-for-testing
```

Results:

- `37` iOS backend tests passed.
- `45` editing-service tests passed.
- Debug simulator build passed.
- Build-for-testing passed with existing Swift 6 actor-isolation warnings in test code.

## Launch Recommendations

- Keep Pro templates gated until entitlement, staging render, and RevenueCat proof are confirmed.
- Deploy to staging before live Pro template render proof.
- Re-run GPT-led edit smoke with at least one personal, full-game, and Pro/internal template after deploy.
- Keep production cutover blocked until Worker, Cloud Run, R2, Sentry, Statsig, RevenueCat, Google config, rollback, privacy/storage, and post-install TestFlight proof gates are all current.
