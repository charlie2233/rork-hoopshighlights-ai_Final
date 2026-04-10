# Phase 4 In-Domain Active Learning Slice

This slice keeps the live control plane untouched and focuses only on dataset curation for the basketball label recovery path.

## What Is Included

- `services/inference/datasets/phase4_in_domain_annotations.json`
- `services/inference/datasets/phase4_event_localization_queue.jsonl`

The slice is intentionally small and biased toward the failure cases that matter most in the live product path:

- `Highlight` outputs that should really be `shot_attempt`, `transition`, or `turnover`
- `eventFamily=other` clips that still contain useful basketball structure
- high-uncertainty clips where the runtime and teacher views disagree
- explicit hard negatives such as camera pans, dead-ball resets, and inbound resets

## Source Domains

The new rows preserve the live provenance through `sourceDomain`:

- `staging_smoke`
- `live_staging`
- `live_shadow`

## Temporal Supervision

Phase 4 adds coarse event-localization fields to the same canonical row schema:

- `eventStart`
- `eventCenter`
- `eventEnd`
- `shotReleaseTime`
- `ballNearRimTime`
- `ballThroughHoopTime`
- `possessionChangeTime`
- `transitionStartTime`

Exact timing is used when it is known. Otherwise, the fields can stay `null` and still load through the canonical annotation schema.

## Review Rule

The queue is sorted by informativeness and disagreement pressure. It is safe for the queue to include clips that already have human labels when the remaining work is temporal localization or failure-case auditing.
