# Detection V2 Integration TODO

## Upload Agent

- Keep using `/v1/analysis/jobs`, `/v1/analysis/jobs/{jobId}/team-scan`, and `/v1/analysis/jobs/{jobId}/start`.
- No upload client change is required for detection v2.
- Preserve `sourceObjectKey`, `uploadTraceId`, and `inferenceAttemptId` in smoke evidence.

## UI Agent

- Existing Review UI can continue reading `results.clips`.
- New Review UI should read `results.candidateClips ?? results.clips`.
- Show product label fields in this order when present: `label`, `canonicalLabel`, `eventFamily`, `outcome`.
- Do not display raw signed URLs, source object keys, or provider secrets.

## Edit Agent

- AI Edit should use candidates that pass existing quality gates.
- Prefer `rankScore` and `scores.finalScore` for candidate ordering when present.
- Keep using `teamAttributionStatus`, `nativeShotSignals`, and `shouldAutoKeep` gates.

## Detection Agent

- Update `ios/backend/app/data/basketball_taxonomy.json` for label language changes.
- Add real OpenCLIP/SigLIP runtime adapters behind `EmbeddingAdapter` without changing response shapes.
- Add real R2Plus1D model loading behind `VideoClassifierAdapter` without changing response shapes.

## Merge Notes

- Run Python detection tests, editing service tests, control-plane typecheck, control-plane tests, and the benchmark CLI before merging.
- Confirm old `/api/ai/analyze` and `/api/ai/result/{jobId}` aliases still route through the Worker.
- Confirm new `/v2/detection/analyze` returns more than one candidate in the route test.
