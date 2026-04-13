# Phase 4h Smoke Runner Reliability Notes

## Scope

- File patched: `scripts/control-plane-shadow-batch.ts`.
- Purpose: make Worker-path smoke runs resilient to transient polling/network failures such as `ECONNRESET`.
- Model impact: none. This change does not alter model thresholds, label mapping, family gates, detector paths, or eval metrics.

## Behavior

- Fetch calls now use bounded retries with exponential backoff and jitter.
- Retryable HTTP statuses are `408`, `425`, `429`, and `5xx`.
- Network fetch failures are retried up to `--fetch-retries`; default is `4`.
- Base backoff is controlled by `--fetch-retry-base-ms`; default is `500`.
- Polling resumes after a successful retry instead of aborting the manifest.
- If retries are exhausted for one item, the runner writes a `*.runner_failed.json` artifact, records `finalStatus=runner_failed`, and continues with the next manifest item.
- Use `--fail-fast true` to restore abort-on-first-item-failure behavior.

## Output Changes

- Final console summary now includes:
  - `completedCount`
  - `failedCount`
  - `statusCounts`
  - per-item `error`
- Retry attempts are logged as JSON lines with `event=fetch_retry`.
- Exhausted item failures are logged as JSON lines with `event=batch_item_failed`.

## Smoke Usage

```bash
node --experimental-strip-types scripts/control-plane-shadow-batch.ts \
  --base-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  --manifest /tmp/phase4h-smoke/manifest.json \
  --output-dir /tmp/phase4h-smoke/batch \
  --poll-timeout-seconds 240 \
  --poll-interval-seconds 2 \
  --fetch-retries 4 \
  --fetch-retry-base-ms 500
```

## Evaluation Rule

If any `runner_failed` artifacts are produced, include only completed job outputs in promotion decisions and report the failed item count separately. Do not treat runner failures as model pass/fail evidence.
