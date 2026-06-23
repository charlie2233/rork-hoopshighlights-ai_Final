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

Use `rankScore` or `scores.finalScore` for ordering when present. Use `canonicalLabel`, `eventFamily`, and `outcome` for display and filtering.

## Legacy Web/API Aliases

`POST /api/ai/analyze` now aliases the existing upload job creation contract. `GET /api/ai/result/{jobId}` aliases job polling. These aliases are compatibility routes, not a separate stub AI path.

## Rollout

1. Deploy backend with detection v2 schema.
2. Smoke old upload/start/poll route.
3. Smoke `/v2/detection/analyze` internally.
4. Update UI to prefer `candidateClips`.
5. Update edit planner to use `scores.finalScore` when available.
