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

## Backend Pieces Implemented After Audit

The follow-up Phase Edit 1 branch adds a backend-only planning layer:

- compact edit-job request as the first `EditContext` surface
- `EditPlan` and `EditPlanClip` models
- `EditPreset` registry for `personal_highlight`, `full_game_highlight`, `coach_review`, `fast_break_mix`, and `best_five`
- deterministic `validate_edit_plan`
- deterministic `repair_edit_plan`
- in-process edit-job state for local/internal planning
- `POST /v1/edit-jobs`
- `GET /v1/edit-jobs/{id}`
- `GET /v1/edit-jobs/{id}/plan`
- `POST /v1/edit-jobs/{id}/revise`

The planning routes are still hidden when `HOOPS_PUBLIC_API_ENABLED=false`, matching the current cloud-gated launch posture.

## Missing Backend Pieces

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

After `codex/phase-edit1-cloud-edit-plan-agent` lands, continue with `codex/phase-edit2-ai-edit-client-ui` for the iOS cloud-edit client surface, or `codex/phase-edit3-cloud-ffmpeg-renderer` if backend render infrastructure should be built first.

Definition of done for the next backend render branch:

- add `/v1/edit-jobs/{id}/render`
- add `/v1/edit-jobs/{id}/render-status`
- add `/v1/edit-jobs/{id}/download-url`
- render FFmpeg output from validated `EditPlan`
- store preview/final MP4 plus render logs
- return signed download URLs
- keep iOS as preview/download/share client only

## Explicit Stop Rules

- Do not implement cloud rendering until the planning layer is validated.
- Do not add new iOS-owned production analysis or rendering.
- Do not make cloud ML or cloud rendering public.
- Do not touch Phase 4h retraining or thresholds.
- Do not change detector-family, SpaceJam, or Phase 4i outcome-model work.
