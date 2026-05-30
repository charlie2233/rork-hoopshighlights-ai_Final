# Phase Launch61 Accuracy Collection Proof

Branch: `codex/phase-launch61-accuracy-collection-proof`

## Goal

Prove and unblock the selected-team cloud analysis path so HoopClips can support the import flow where the user chooses one detected team before analysis. The fix keeps the cloud-first architecture: iOS sends team intent and reviews results, while backend services own analysis, team attribution, callbacks, storage, and rendering handoff.

## Root Cause

The staging control plane could quick-scan teams, but full selected-team analysis could fail at queue dispatch. The Worker sent `teamSelection` into the legacy inference `/v1/analyze` contract. That legacy service may reject unknown or unsupported team-selection fields with a 422 before analysis starts.

Team quick-scan already had an editing-service fallback, but full analysis dispatch did not. That meant a selected team could be detected correctly, then the queued analysis job could still fail before clips were generated.

## Backend Changes

- Added an analysis dispatch provider chain in `services/control-plane/src/queue/consumer.ts`.
- Primary provider remains `INFERENCE_BASE_URL` for the legacy inference service.
- Fallback provider is `EDITING_BASE_URL` for cloud editing analysis when legacy inference returns a compatibility status: 404, 405, 422, or 501.
- Kept the legacy inference body compatible by omitting newer file metadata fields. For selected-team jobs, `teamSelection` is still attempted against inference first so modern inference can accept it when available.
- Added sanitized `provider` evidence to queue accepted events without logging source URLs, object keys, credentials, or full presigned URLs.
- Added an editing backend `/v1/analyze` compatibility endpoint that accepts Worker dispatch, materializes the remote source, runs cloud analysis, and posts the existing inference callback contract.
- Preserved callback secrets as callback-only credentials and used provider ingress secrets for provider authentication.

## Privacy And Storage

- No R2 access keys, API tokens, callback secrets, or full presigned URLs are logged.
- The new tests assert event payloads do not include upload URLs, source object keys, or result object keys.
- The editing callback payload intentionally excludes `sourceUrl`.

## Team Highlight Behavior

- Selected team intent survives queueing and fallback dispatch.
- Analysis receives the selected team and can return only that team's clips, including offense and defensive events such as steals and blocks.
- Uncertain clips can remain in the result when `includeUncertain` is enabled, so the user can review borderline moments instead of losing recall.

## Validation

Commands run locally:

```bash
python3 -m py_compile ios/backend/app/api.py ios/backend/app/models.py
```

Result: passed.

```bash
uv run --with-requirements ios/backend/requirements.txt --python 3.11 env PYTHONPATH=ios/backend python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_analyze_source_endpoint_accepts_worker_dispatch_and_posts_callback -v
```

Result: passed.

```bash
uv run --with-requirements ios/backend/requirements.txt --python 3.11 env PYTHONPATH=ios/backend python -m unittest ios.backend.tests.test_team_quick_scan -v
```

Result: passed, 38 tests.

```bash
npm --prefix services/control-plane run typecheck
```

Result: passed.

```bash
npm --prefix services/control-plane run typecheck && npm --prefix services/control-plane test
```

Result: passed, 30 tests.

```bash
git diff --check
```

Result: pending final rerun after this document update.

## Evidence

- Control-plane test `control plane falls back to editing analysis when legacy inference rejects selected team dispatch` simulates staging legacy inference returning 422 for selected-team dispatch.
- The same test verifies the editing provider receives the selected-team request, posts a normal callback, stores completed job results, and records `provider: "editing"` on the accepted queue event.
- Editing backend test `test_analyze_source_endpoint_accepts_worker_dispatch_and_posts_callback` verifies `/v1/analyze` accepts Worker dispatch, builds a `StoredJob` with `team_selection`, runs analysis, posts the callback, and keeps `sourceUrl` out of the callback payload.

## Launch Notes

- This branch is locally validated but not deployed to staging yet. A live staging collection proof still needs a deploy, then a rerun of the selected-team video import/analysis flow.
- To save GitHub Actions minutes, this branch should be merged or deployed only when ready for the next staging proof pass.
- Recommended live proof after deploy: rerun the selected-team collection on the known local basketball sample and capture job ID, team scan result, analysis completion, and clip attribution.
