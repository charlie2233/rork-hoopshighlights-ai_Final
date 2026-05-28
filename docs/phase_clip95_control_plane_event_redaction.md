# Phase Clip95 Control Plane Event Redaction

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Keep HoopClips cloud job timelines useful without exposing storage internals. The iOS app and operators need real job state, but job event payloads should not carry presigned URLs, upload headers, source object keys, result object keys, or download URLs.

## Change

- Added centralized job-event payload redaction in `services/control-plane/src/db/index.ts`.
- Redaction runs inside `appendJobEvent`, so Durable Object patches, public route events, queue dispatch events, retry events, and direct DB event inserts all pass through one guard.
- Updated the local control-plane harness to use the same redaction helper for Durable Object mock events.
- Tightened `control-plane-status-transitions.test.ts` so real upload URLs, source object keys, and result object keys must not appear in recorded event payloads.

## Guardrails

- Operational job records, queue messages, and inference dispatch payloads still keep the real object keys where the backend needs them.
- Only event/timeline payloads are redacted.
- No local video analysis, rendering, or iOS behavior changed.

## Validation

- `npm --prefix services/control-plane test` passed: 28 tests.
- `npm --prefix services/control-plane run typecheck` passed.

## Remaining Proof

This hardens stored timeline events, but internal launch still needs a live staging smoke that confirms UI-visible timelines do not expose presigned URLs or storage object-key values.
