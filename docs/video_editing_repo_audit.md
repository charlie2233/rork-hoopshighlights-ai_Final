# HoopClips Video Editing Repo Audit

Date: 2026-04-27

Branch: `codex/phase-edit0-repo-audit`

## Audit Result

The repo currently contains a launch-safe iOS-first implementation and an internal cloud-analysis backend scaffold. It does not yet contain the target HoopClips AI Edit Agent backend, EditPlan schema, edit-job API, cloud render service, or cloud MP4 storage flow.

The product direction is now cloud-first:

- cloud backend owns analysis, edit planning, and rendering
- iOS owns upload, style selection, review/status, preview, download, sharing, and open-in-editor
- AVFoundation/Vision/CoreML remain allowed only for playback, preview, import/download handling, share/save, and temporary fallback while cloud gates are locked

## Current Backend State

Implemented under `ios/backend`:

- `POST /v1/analysis/jobs`
- `POST /v1/analysis/jobs/{jobId}/start`
- `GET /v1/analysis/jobs/{jobId}`
- `DELETE /v1/analysis/jobs/{jobId}`
- `POST /v1/internal/process/{jobId}`
- local upload emulator route `PUT /v1/internal/uploads/{jobId}`

Current managed deployment assumptions:

- Cloud Run service
- Firestore job store
- GCS upload storage
- Cloud Tasks internal dispatch
- Secret Manager for internal processing secret
- public `/v1/analysis/*` disabled outside local mode by default

No Cloudflare Worker, R2, D1, Durable Object, or Cloudflare Queue implementation was found in the current repo. Cloudflare can still be the future control plane if that is the chosen architecture, but it is not the current implementation source of truth.

Current model behavior:

- built-in deterministic/heuristic pipeline exists
- optional external HoopCut/autohighlight adapters exist
- `HOOPS_USE_GEMINI_RELABELING` is reserved/stubbed
- there is no production EditPlan agent or cloud render path yet

## Missing Backend Pieces

- `EditContext` model
- `EditPlan` model
- `EditPlanClip` model
- `EditPreset` and `EditTheme` registries
- deterministic `EditPlanValidator`
- edit-job state model
- `/v1/edit-jobs` API
- `/v1/edit-jobs/{id}/plan`
- `/v1/edit-jobs/{id}/revise`
- `/v1/edit-jobs/{id}/render`
- `/v1/edit-jobs/{id}/render-status`
- `/v1/edit-jobs/{id}/download-url`
- FFmpeg cloud renderer
- render logs
- final MP4 storage and signed download URL
- cloud-first iOS client flow for plan/status/render/download

## Current iOS State

The app still has local video processing paths:

- `VideoAnalysisService.swift` imports and uses AVFoundation, Vision, and CoreML-style local analysis helpers.
- `HighlightsViewModel.swift` still owns cloud-disabled fallback and local analysis orchestration.
- `CloudAnalysisService.swift` speaks to `/v1/analysis/jobs`, `/start`, and polling endpoints.
- `VideoExportService.swift` and `ExportThemeRenderer.swift` use AVFoundation/CoreImage export for local reel creation.
- release launch config keeps cloud analysis disabled and uses local/on-device analysis as the current safe public path.

These paths explain why Codex kept drifting back to on-device work. They are allowed as current fallback, playback, share/save, and release-safety code, but they are not the target production architecture for HoopClips AI editing.

## Documentation Drift Found

The following docs previously described on-device analysis as the public product posture:

- `README.md`
- `ios/docs/checklists/public-launch-cloud-gated.md`
- `ios/docs/runbooks/public-launch-cloud-gated.md`
- `ios/backend/README.md`

This branch reframes them as temporary cloud-gated fallback / release-safety posture while documenting cloud-backend editing as the target architecture.

## Recommended Next Branch

Create `codex/phase-edit1-cloud-edit-plan-agent` after this audit lands.

Definition of done for the next branch:

- add backend `EditContext`, `EditPlan`, `EditPlanClip`, `EditPreset`, and `EditTheme`
- add deterministic `EditPlanValidator`
- add preset registry for `personal_highlight`, `full_game_highlight`, `coach_review`, `fast_break_mix`, and `best_five`
- add pure planning tools for ranking, duplicate removal, target-duration fitting, captions, slow motion, watermark/outro, validation, repair, and render-cost estimation
- add edit-job planning endpoints but no renderer yet
- add backend tests for presets, duration fitting, duplicate removal, free-user watermark/outro, minimum clip duration, slow-motion bounds, and invalid plan repair

## Explicit Stop Rules

- Do not implement cloud rendering in this audit branch.
- Do not add new iOS-owned production analysis or rendering.
- Do not make cloud ML or cloud rendering public.
- Do not touch Phase 4h retraining or thresholds.
- Do not change detector-family, SpaceJam, or Phase 4i outcome-model work.
