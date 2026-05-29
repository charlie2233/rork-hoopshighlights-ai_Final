# Phase Clip88 iOS Team Evidence Relay

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Preserve cloud quick-scan team evidence metadata across the iOS control surface. The backend now emits sampled frame refs and role groups for selected-team confidence; iOS must keep that metadata when it maps cloud analysis clips into Review and sends candidate clips to AI Edit.

## Change

- Added optional `evidenceFrameRefs` and `evidenceRoleGroups` to the shared Swift `ClipTeamAttribution` model.
- Preserved the metadata through `CloudClip.makeClip()` and `CreateCloudEditJobRequest` candidate encoding.
- Kept fields optional so cached or older cloud analysis results without evidence metadata still decode.
- Updated the existing Swift fixtures to include the newer team diagnostics fields.

## Guardrails

- iOS still does not analyze frames, generate team evidence, render video, or make GPT decisions.
- Evidence refs are sampled-frame IDs and role labels only; no image data, presigned URLs, storage keys, or secrets are stored or logged by this change.
- Backend validators remain responsible for deciding whether evidence is strong enough for confident selected-team attribution.

## Validation

- `mcp__xcodebuildmcp__.test_sim` with `-only-testing:HoopsClipsTests/HoopsClipsTests` passed: 45 tests.
- `mcp__xcodebuildmcp__.build_sim` passed for the `HoopsClips` Debug simulator build.
- `PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v` passed: 170 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 59 tests.
- `cd services/control-plane && npm run typecheck` passed.
- `git diff --check` passed.

## Remaining Proof

This prevents metadata loss between cloud analysis and AI Edit, but it does not prove the 85% real-footage target by itself. Internal launch still needs a labeled footage eval run and installed TestFlight smoke covering selected-team makes, misses, blocks, steals, uncertain review clips, opponent clips, and bad-window negatives.
