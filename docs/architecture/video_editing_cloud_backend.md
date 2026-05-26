# HoopClips Cloud Video Editing Architecture

## Architecture Rule

HoopClips is a cloud-backend video product.

All basketball video analysis, AI edit planning, and final rendering happen in the cloud backend. The iOS app is the control surface for upload, style selection, target-length selection, edit-plan review, render status, finished MP4 preview, download, sharing, and opening exports in external editors.

AVFoundation, Vision, and CoreML may remain in iOS for playback, preview, import/download handling, share/save support, and temporary launch-safe fallback while cloud gates are locked. They are not the target production editing engine.

## Product Shape

HoopClips AI Edit Agent turns detected basketball clips into polished highlight videos.

```text
Raw game video
  -> Cloud analysis service
  -> Clip pool
  -> AI Edit Agent
  -> EditPlan JSON
  -> deterministic EditPlan validator
  -> cloud render service
  -> final MP4 storage
  -> iOS preview / download / share / open in editor
```

The agent makes creative decisions. The renderer executes a validated plan.

## Backend Responsibilities

- Accept source video uploads.
- Run highlight analysis and clip scoring.
- Build compact `EditContext` objects from analyzed clips.
- Generate strict `EditPlan` JSON.
- Validate every plan deterministically before render.
- Render preview and final MP4 outputs in the backend.
- Store source, analysis, plan, render logs, preview MP4, and final MP4.
- Return status, diagnostics, download URLs, and share/open-in-editor metadata to iOS.

## iOS Responsibilities

- Upload videos.
- Choose edit style, target length, aspect ratio, music profile, and optional revision intent.
- Review generated clips and edit plan summaries.
- Show job status and failure messages.
- Preview final MP4.
- Download, save to Photos, share, and open exported MP4s in CapCut, iMovie, Adobe, Files, Photos, or other editors.

iOS must not add new production video analysis, AI edit planning, or final rendering logic.

## Renderer Strategy

- Primary renderer: FFmpeg backend for trim, concat, crop, zoom, slow motion, captions, audio mix, watermark, outro, and final MP4 encoding.
- Motion templates: Remotion for branded intros, outros, title cards, animated captions, and social templates.
- Future web editor: Revideo for browser preview or template-studio work after the backend render path is stable.
- Design assets: Canva for thumbnails, title cards, overlays, and branded static or animated assets.
- Optional transformations: Cloudinary for lightweight preview variants or media transformations if cost and limits are acceptable.
- Workflow orchestration: current queue/control-plane first; Temporal only when preview, revise, render, upload, and notify workflows become long-running and multi-step.

## Edit Job API Target

```text
POST /v1/edit-jobs
GET  /v1/edit-jobs/{id}
GET  /v1/edit-jobs/{id}/plan
POST /v1/edit-jobs/{id}/revise
POST /v1/edit-jobs/{id}/render
GET  /v1/edit-jobs/{id}/render-status
GET  /v1/edit-jobs/{id}/download-url
GET  /healthz
GET  /readyz
GET  /version
```

Edit job states:

```text
created
planning
plan_ready
rendering_preview
preview_ready
rendering_final
rendered
failed
cancelled
```

## Storage Target

```text
videos/{videoId}/source.mp4
analysis/{analysisJobId}/clips.json
edits/{editJobId}/edit_context.json
edits/{editJobId}/edit_plan.json
edits/{editJobId}/plan.json
edits/{editJobId}/render_jobs/{renderJobId}/preview.mp4
edits/{editJobId}/render_jobs/{renderJobId}/final.mp4
edits/{editJobId}/render_jobs/{renderJobId}/render_log.json
```

Storage provider can be R2 or GCS depending on the deployment lane, but the logical object layout should stay stable.

## Renderer V1

Renderer V1 is backend-owned FFmpeg. It accepts only validated `EditPlan` JSON and source media from storage. It never accepts raw FFmpeg commands from the LLM or the client.

Current V1 operations:

- trim
- concat
- crop to `9:16` or `16:9`
- slow-motion subranges
- caption/watermark overlays
- free-user Hoopclips outro
- music/game-audio mix
- H.264/AAC MP4 encode
- render log emission
- local/R2-compatible output storage

Current limitations:

- render jobs are local/in-process state until a durable queue/store is added
- advanced transitions and beat sync are deferred
- Remotion/Canva/Revideo are still template/asset/future-editor tools, not core render engines

## EditPlan Contract

The agent outputs `EditPlan` JSON, not raw FFmpeg commands.

Minimum fields:

```json
{
  "version": "edit-plan-v1",
  "editJobId": "edit_123",
  "videoId": "video_123",
  "analysisJobId": "analysis_456",
  "preset": "personal_highlight",
  "theme": "hype_black_gold",
  "targetDurationSeconds": 30,
  "aspectRatio": "9:16",
  "renderMode": "cloud_ffmpeg",
  "audio": {
    "mode": "music_plus_game_audio",
    "musicTrackId": "hype_01",
    "musicVolume": 0.82,
    "gameAudioVolume": 0.28
  },
  "clips": [
    {
      "clipId": "c01",
      "sourceStart": 12.4,
      "sourceEnd": 18.9,
      "eventCenter": 15.2,
      "timelineStart": 0,
      "timelineEnd": 6.5,
      "label": "Fast Break",
      "caption": "FAST BREAK",
      "cropMode": "center_action",
      "effects": [
        {
          "type": "punch_zoom",
          "at": 15.2,
          "strength": 0.18
        },
        {
          "type": "slow_motion",
          "sourceStart": 14.8,
          "sourceEnd": 16.0,
          "speed": 0.5
        }
      ]
    }
  ],
  "intro": {
    "enabled": true,
    "durationSeconds": 1.2,
    "templateId": "quick_flash_title"
  },
  "outro": {
    "enabled": true,
    "durationSeconds": 2.0,
    "templateId": "free_hoopclips_outro"
  },
  "watermark": {
    "enabled": true,
    "position": "bottom_right"
  }
}
```

## EditContext Token Rules

The agent receives compact clip metadata, not raw video.

- Limit input to the top 20-30 clips for the selected job.
- Use clip IDs, preset IDs, theme IDs, and music profile IDs.
- Use numeric scores from the backend.
- Do not include full video files, full inference logs, full transcript/audio payloads, secrets, or full presigned URLs.
- Optional GPT highlight reranking may send sampled keyframes from existing candidate clip windows only. Quality-beta defaults favor stronger context and visual detail over cost: Free jobs stay capped to 8 clips but can sample up to 10 frames per clip, while Pro/internal jobs can sample up to 30 clips and 10 frames per clip. Sampled keyframes default to 1024px wide with a 750 KB per-frame cap so GPT has more ball/rim detail for semantic editing.
- Filter out tiny, too-late, or no-follow-through candidates before GPT; require GPT to return strict shot-quality signals plus explicit `shotResultEvidence` and frame-role `shotTrackingEvidence` for release-to-rim continuity, visible rim/net result, ball/rim frame roles, outcome confidence, camera quality, and full play context.
- GPT reranking can adjust ranking scores, captions, watchability/event metadata, and safe edit suggestions, but it must not invent clip IDs, replace exact timestamps, run CV/tracking, invoke FFmpeg, or render video.
- Store preset and theme details in backend registries.
- Use patches for revisions.
- Allow one repair pass after validation failure, not endless loops.

## Required Presets

- `personal_highlight`: vertical, fast, music-forward recruiting/social reel.
- `full_game_highlight`: cleaner game recap, chronological with best moments boosted.
- `coach_review`: slower, chronological, original-audio-focused review mode.

Optional next presets:

- `fast_break_mix`
- `best_five`

## Validation Requirements

`validate_edit_plan` must reject:

- empty clip lists
- duplicate clip IDs
- invalid source bounds
- slow motion outside clip bounds
- clips shorter than the minimum
- total duration outside target tolerance
- captions too long for the selected template
- free-user plans missing required watermark/outro
- invalid aspect ratio
- invalid theme
- unavailable or unlicensed music
- render cost above configured limits

## Forbidden Paths

- No new on-device production analysis implementation.
- No new on-device production rendering implementation.
- No Remotion in iOS.
- No Canva as the core renderer.
- No LLM-generated raw FFmpeg commands.
- No public cloud cutover before production auth, storage, observability, render reliability, and Phase 4h confirmed-label gates clear.
