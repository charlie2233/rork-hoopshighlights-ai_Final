# HoopsClips UI Architecture

The app shell is now workflow-first:

- Uploads: import, upload queue, cloud analysis status, History/Settings utility routes.
- Review: filters, score/confidence/label/time sorting, keep/nah decisions, feedback tags, keyboard shortcuts, boundary nudges.
- AI Edit: style, target duration, aspect ratio, prompt, edit plan preview, render status, preview/save/share.
- Exports: finished MP4 output state, preview, save to Photos, system share sheet, local fallback export controls when allowed.

`ContentView` owns authenticated app state and switches between these sections. `HighlightsViewModel` remains the shared state owner for project, upload, analysis, clip review, and export state.

`UploadsWorkflowView` wraps the existing player/import surface and adds a queue tray backed by `UploadQueueProjection`. The projection accepts the asset-first upload fields from the upload agent (`assetId`, `storageKey`, `proxyKey`, status, byte progress, analysis job, clip count, and failure reason) and falls back to the legacy current-job state while the backend branches merge.

`AIEditWorkflowView` promotes the existing `AIEditView` from an Export subsection into its own section.

`AIEditView` owns style, duration, aspect ratio, prompt selection, edit plan preview, render request, render polling, and download preparation. It mirrors the latest render status into `HighlightsViewModel.latestCloudEditRenderStatus` for output-only Exports display.

`ExportView` can still embed AI Edit for compatibility, but the workflow shell passes `showsAIEditAgentSection: false` so Exports is output-focused.
