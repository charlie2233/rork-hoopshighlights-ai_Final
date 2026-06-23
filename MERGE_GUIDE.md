# Merge Guide

## Detection V2 For Upload/UI/Edit Agents

Upload agents:

- No upload API change is required.
- Keep all source upload and progress proof on `/v1/analysis/*`.
- Treat `/v2/detection/analyze` as an internal backend validation route, not the mobile upload path.

UI agents:

- Prefer `results.candidateClips ?? results.clips`.
- Display `label` as product copy.
- Use `canonicalLabel`, `eventFamily`, and `outcome` for filtering.
- Surface provenance only in diagnostics or reviewer/debug views.

Edit agents:

- Prefer `rankScore` or `scores.finalScore` for candidate ordering.
- Preserve existing quality gates for team attribution and native shot signals.
- Do not make iOS perform local detection or rendering.

Validation before merge:

- `python3 -m unittest ios.backend.tests.test_detection_pipeline`
- `PYTHONPATH=ios/backend:services/editing python3 -m unittest services.editing.tests.test_editing_service`
- `python3 scripts/benchmark_detection_pipeline.py --json`
- `npm --prefix services/control-plane run typecheck`
- `npm --prefix services/control-plane test`
