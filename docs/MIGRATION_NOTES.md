# Detection V2 Migration Notes

## Existing Clients

No client break is required.

- Continue creating upload jobs with `/v1/analysis/jobs`.
- Continue starting jobs with `/v1/analysis/jobs/{jobId}/start`.
- Continue polling `/v1/analysis/jobs/{jobId}`.
- Continue reading `results.clips`.

## New Clients

New clients should read:

```swift
let candidates = response.results?.candidateClips ?? response.results?.clips ?? []
```

Use `rankScore` or `scores.finalScore` for ordering when present. Use `canonicalLabel`, `eventFamily`, and `outcome` for display and filtering. Keep `rerankEvidence` diagnostics-only unless product explicitly promotes it into the review UI.

iOS now preserves additive rerank metadata without requiring it:

- `CloudClip.id` or `CloudClip.clipId` maps to `Clip.analysisClipID`.
- `CloudClip.rankScore ?? CloudClip.scores.finalScore` maps to `Clip.rankScore`.
- Cloud edit candidates encode `rankScore` and keep the existing team/native-shot/auto-keep gates.

## Legacy Web/API Aliases

`POST /api/ai/analyze` now aliases the existing upload job creation contract. `GET /api/ai/result/{jobId}` aliases job polling. These aliases are compatibility routes, not a separate stub AI path.

## Detection V2 Source Materialization

`POST /v2/detection/analyze` accepts asset-backed and legacy URL-backed requests. The backend now prefers `storageKey` or `sourceObjectKey` and only falls back to `sourceUrl` when object identity is unavailable. Rerank evidence preserves `jobId`, `assetId`, `storageKey`, `sourceObjectKey`, `uploadTraceId`, `inferenceAttemptId`, and request/trace IDs when provided.

Editing-service dispatch and callbacks also echo `assetId` and `storageKey`, so control-plane, backend, and edit-service traffic can share the same asset identity without replacing the legacy manual URL flow.

## Rollout

1. Deploy backend with detection v2 schema.
2. Smoke old upload/start/poll route.
3. Smoke `/v2/detection/analyze` internally.
4. Update UI to prefer `candidateClips`.
5. Update edit planner to use `rankScore` or `scores.finalScore` when available.
6. Keep `HOOPS_SEMANTIC_RERANK_ENABLED=false` available as a fast rollback if model runtime, latency, or provider readiness is not acceptable.
