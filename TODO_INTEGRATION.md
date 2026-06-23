# HoopClips Integration TODO

Last updated: 2026-06-23

## Done In This Worktree

- Added additive `assetId`, `sourceClipIds`, `editIntent`, and `idempotencyKey` support to iOS, control-plane types, and backend edit-job requests.
- Preserved `sourceObjectKey` and full `clips` compatibility fields.
- Echoed `assetId`, `sourceObjectKey`, `sourceClipIds`, structured intent, and full candidate clips on edit-job responses.
- Mapped existing iOS prompt/template/team-selection UI into `edit-intent-v1`.
- Kept validated `EditPlan` as the render contract.
- Added durable edit-job idempotency indexing and replay after app reload.

## Still To Integrate With Agent A

- Wire the upload pipeline's durable `assetId` into `CreateCloudEditJobRequest.assetId` once the Agent A branch is merged.
- Keep `sourceObjectKey` populated during migration for old render and manual URL flows.
- Confirm asset readiness states before edit-job creation: `proxy_ready` or `ready`.

## Still To Integrate With Agent C

- Confirm the UI sends the selected review set as `sourceClipIds` while keeping the full candidate list as `clips`.
- Apply the agreed status copy for plan preparation, plan ready, render queue, cloud MP4 rendering, and preview/share preparation.
- Keep the fallback timeline step IDs stable until Agent C removes older UI dependencies.

## Removal Gate

Do not remove `sourceObjectKey` or full candidate `clips` from edit-job requests/responses until iOS, Worker, backend, smoke tests, and TestFlight validation all use `assetId` plus `sourceClipIds` successfully.
