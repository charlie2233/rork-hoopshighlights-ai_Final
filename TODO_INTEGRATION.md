# UI Edit V2 Integration TODO

- Merge this branch after detection/upload agents confirm their job state fields still map to `CloudAnalysisTypes.swift` and the asset-first upload lifecycle (`initialized`, `uploading`, `uploaded`, `processing`, `proxy_ready`, `ready`, `failed`).
- Keep `UploadQueueProjection` as a view projection over canonical job state; do not persist it.
- If another agent adds a multi-item upload queue, feed its canonical DTOs through `UploadAssetQueueContract` and keep the same `UploadQueueItem` UI surface until the SwiftUI views are updated.
- Confirm Review keeps these existing actions wired to `Clip.isKept`: Keep, Nah, Keep Strong, Skip Weak, team filters, and feedback tags.
- Confirm Review shortcut routing stays: `K` keep, `D` discard, `N` Nah compatibility, `1`-`5` feedback tags, `[`/`]` boundary nudges.
- Confirm boundary nudges remain metadata-only and are reflected in cloud edit candidate clips through `CreateCloudEditJobRequest.clips`.
- Confirm AI Edit tab still calls cloud edit plan and render endpoints through `CloudEditService`; `assetId` and `sourceClipIds` are additive live fields and `sourceObjectKey` plus full `clips` remain as the compatibility route.
- Confirm Exports only handles rendered/downloaded MP4 states, reads latest status from `HighlightsViewModel.latestCloudEditRenderStatus`, and does not reintroduce a second editor flow.
- Re-run `HoopsClipsTests` and the workflow UI smoke after integrating upload/detection branches.
