# Phase Clip68: Control-Plane Team Identity Parity

## Goal

Keep the Cloudflare Worker selected-team gate aligned with the Python backend team identity rules. Staging/prod should not queue selected-team analysis unless the chosen team matches a cloud-scanned jersey-color team without an explicit color conflict.

## Change

- Added a Worker-side team identity helper for jersey-color aliases such as dark/black, light/white, navy/blue, and gold/yellow.
- Updated `validateScanBackedTeamSelection` to use the shared identity matcher instead of a raw `teamId OR colorLabel` comparison.
- Equivalent color aliases can pass the scan-backed gate, so `Dark jerseys` can match a scanned `Black jerseys` option.
- Explicit conflicts fail before an exact team ID can pass, so `team_dark` with `White jerseys` is rejected.

## Architecture

- Cloud still owns team scan, selected-team validation, analysis queueing, GPT review, edit planning, rendering, and storage.
- iOS remains the control surface for upload/import, team choice, analysis status, review, export, preview, download, and share.
- No full videos, storage keys, presigned URLs, or renderer commands are exposed to GPT or logs by this change.

## Validation

```bash
npm --prefix services/control-plane run typecheck
# Result: passed

npm --prefix services/control-plane test
# Result: 28 tests passed

git diff --check
# Result: passed
```

## Launch Note

This closes a Worker/Python parity gap in selected-team validation, but it is still not the 85% real-footage accuracy proof. Internal launch still needs green CI, staging Worker smoke, installed iPhone smoke, and labeled eval coverage for selected-team ownership, uncertain review clips, made/missed outcomes, blocks, steals, forced turnovers, and bad-window negatives.
