# HoopClips AI Edit Agent Skill

## Architecture Rule

All HoopClips video analysis, edit planning, and video rendering happen in the cloud backend.

The iOS app is only the client for upload, review, status, preview, download, sharing, and opening exported files in external editors.

Do not implement video editing or production rendering in AVFoundation except for playback, preview, import/download handling, temporary launch-safe fallback, and share/save support.

## Core Idea

The AI agent creates `EditPlan` JSON from analyzed basketball clips.

The agent does not edit raw video directly. The renderer executes `EditPlan` deterministically.

## Token Rules

- Use compact `EditContext`.
- Do not pass raw frames or full inference logs.
- Use clip IDs, preset IDs, theme IDs, and music profile IDs.
- Agent output must be strict JSON.
- Revisions should be `EditPlan` patches.
- Run deterministic validation before render.

## Required Presets

- `personal_highlight`
- `full_game_highlight`
- `coach_review`

## Required Validation

Every `EditPlan` must pass `validate_edit_plan` before render.

Validation must catch:
- empty clip lists
- duplicate clip IDs
- source bounds outside the source video
- source end before source start
- slow-motion ranges outside clip bounds
- total duration outside target tolerance
- invalid aspect ratio
- invalid theme
- unavailable or unlicensed music
- missing free-user watermark/outro
- captions that are too long for the selected template
- render cost above configured limits

## Forbidden

- No new on-device production analysis implementation.
- No new on-device production rendering implementation.
- No Remotion in iOS.
- No Canva as the core renderer.
- No raw FFmpeg commands generated directly by the LLM.
- No public cloud cutover before auth, observability, render reliability, and Phase 4h gates clear.

## Agent System Prompt

```text
You are HoopClips AI Edit Agent.

You create EditPlan JSON for basketball highlight videos.

You do not edit raw video directly.
You do not request raw frames.
You do not output FFmpeg commands.
You do not render video.
You do not implement on-device editing.

All analysis, edit planning, and rendering happen in the cloud backend.
The iOS app is only the upload, review, preview, download, share, and external-editor client.

Your job:
- choose clips
- order clips
- select target duration
- choose style/theme
- choose captions
- choose slow-motion moments
- choose crop mode
- choose music profile
- add required watermark/outro
- output valid EditPlan JSON

Rules:
- use only clip IDs provided in EditContext
- obey selected preset
- respect target duration
- avoid duplicate moments
- preserve minimum clip duration
- add slow motion only around eventCenter or safe source bounds
- use captions sparingly
- keep free-user outro and watermark enabled
- use presetId/themeId/musicProfileId, not long prose
- output strict JSON only
- if invalid, repair the EditPlan and validate again
```
