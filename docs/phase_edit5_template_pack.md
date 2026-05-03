# Phase Edit5 Template Pack

## Goal

Phase Edit5 adds the first HoopClips AI Edit Agent template pack registry. Templates now define style defaults for cloud edit planning and FFmpeg rendering while keeping `EditPlan` as the source of truth.

The iOS app still only configures export intent, requests cloud jobs, previews MP4s, downloads local files, and opens the share sheet. It does not analyze, plan, patch, or render video locally.

## Template IDs

### `personal_highlight_v1`

- Purpose: fast vertical player/recruiting/social reel.
- Aspect defaults: `9:16`.
- Target durations: `15`, `30`, `45`.
- Ordering: best plays first.
- Captions: `bold_hype`.
- Audio: `hype`, music-forward with quieter game audio.
- Effects: slow motion, punch zoom, speed ramp.
- Free policy: Hoopclips watermark and branded outro required.
- Assets: `services/editing/templates/personal_highlight/assets/watermark.json`, `services/editing/templates/personal_highlight/assets/outro_free.json`.

### `full_game_highlight_v1`

- Purpose: clean game-flow recap.
- Aspect defaults: `16:9`.
- Target durations: `60`, `90`, `120`.
- Ordering: chronological with best moments boosted.
- Captions: `clean_scorebug`.
- Audio: more game audio with lighter music.
- Effects: subtle replay/lower-third hooks and bounded slow motion.
- Free policy: Hoopclips watermark and standard outro required.
- Assets: `services/editing/templates/full_game_highlight/assets/watermark.json`, `services/editing/templates/full_game_highlight/assets/outro_standard.json`, `services/editing/templates/full_game_highlight/assets/lower_third.json`.

### `coach_review_v1`

- Purpose: simple chronological film review.
- Aspect defaults: source framing, with `16:9` allowed.
- Target durations: `60`, `120`, `180`.
- Ordering: chronological.
- Captions: `plain`.
- Audio: original game audio, no music.
- Effects: minimal, with slow motion allowed only when explicitly requested and validated.
- Free policy: Hoopclips watermark and minimal outro required.
- Assets: `services/editing/templates/coach_review/assets/watermark.json`, `services/editing/templates/coach_review/assets/outro_minimal.json`.

## Backend Integration

- `TemplatePack`, `TemplateAsset`, `CaptionStyle`, `AudioProfile`, `EffectProfile`, `OutroProfile`, and `WatermarkProfile` live in `ios/backend/app/editing.py`.
- `TEMPLATE_PACK_REGISTRY` maps template IDs to validated runtime templates.
- `CreateEditJobRequest` accepts `templateId`.
- `EditPlan` stores `templateId`, `captionStyle`, and template asset IDs on watermark/outro objects.
- `validate_template_registry()` checks required assets, aspect ratios, captions, effects, music tracks, watermark rules, and outro rules.
- `validate_edit_plan()` enforces template compatibility before render.
- Revision commands preserve the active template unless the command explicitly switches style.

## Renderer Integration

The FFmpeg renderer remains the core cloud renderer. Template packs feed deterministic fields into the renderer:

- caption density/font sizing from `CaptionStyle`
- watermark copy from `WatermarkProfile`
- generated outro copy from the selected template
- `templateId`, `captionStyle`, `watermarkAssetId`, and `outroAssetId` in `render_log.json`

The renderer still does not accept raw FFmpeg commands from the LLM or the iOS app.

## iOS Export UI

The Export AI Edit section now presents template cards instead of plain style rows:

- Personal Highlight: fast vertical hype reel.
- Full Game Highlight: clean game recap.
- Coach Review: simple chronological film review.

The iOS app sends the selected `templateId` with the cloud edit request and keeps the existing cloud preview/share path unchanged.

## Validation

Run for branch closeout:

- `git diff --check`
- `PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v`
- `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent ios.backend.tests.test_render_jobs -v`
- `npm --prefix services/control-plane run typecheck`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build-for-testing CODE_SIGNING_ALLOWED=NO`

## Remaining Polish Ideas

- Replace JSON placeholder assets with Remotion-generated intro/outro MP4 assets.
- Add Canva-designed thumbnail and outro-card source assets.
- Add visual lower-third overlays once the FFmpeg renderer supports image overlays.
- Split full live cloud smoke into nightly/manual while keeping a faster fixture-based CI smoke.
