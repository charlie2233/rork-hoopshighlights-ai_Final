# Staging Smoke Runbook

This runbook covers the live Cloudflare staging path for phase 1b: resource setup, deploy, iOS smoke, rollback, and the known failure modes for the happy-path flow.

## Preconditions

- `wrangler login` is complete for the Cloudflare account.
- `services/control-plane` dependencies are installed.
- `Cloudflare R2` is enabled for the account.
- The iOS Staging build uses `ios/Config/Staging.xcconfig` plus a local secrets overlay if needed.

## Exact Resource Setup

Run these once for the staging environment:

```bash
cd services/control-plane
npx wrangler queues create hoopsclips-analysis
npx wrangler queues create hoopsclips-analysis-dlq
npx wrangler d1 create hoopsclips-control-plane-staging
npx wrangler d1 migrations apply hoopsclips-control-plane-staging --env staging
npx wrangler r2 bucket create hoopsclips-uploads-staging
npx wrangler r2 bucket create hoopsclips-results-staging
```

The staging Worker needs these secret names, and they must be stored with `wrangler secret put`:

```bash
cd services/control-plane
npx wrangler deploy --env staging
printf '%s' 'https://<printed-workers-dev-or-custom-domain-url>' | npx wrangler secret put CONTROL_PLANE_BASE_URL --env staging
npx wrangler secret put ADMIN_API_TOKEN --env staging
npx wrangler secret put CONTROL_PLANE_SHARED_SECRET --env staging
npx wrangler secret put INFERENCE_SHARED_SECRET --env staging
npx wrangler secret put R2_ACCESS_KEY_ID --env staging
npx wrangler secret put R2_SECRET_ACCESS_KEY --env staging
npx wrangler deploy --env staging
```

`CONTROL_PLANE_BASE_URL` is the only service URL required in phase 1b. It must match the deployed staging Worker host so queue-driven stub inference can call back into `/internal/inference/callback`.

## Exact Deploy Commands

Deploy the staging Worker from the control-plane package:

```bash
cd services/control-plane
npx wrangler deploy --env staging
```

Verify queue and D1 state after deploy:

```bash
cd services/control-plane
npx wrangler queues info hoopsclips-analysis
npx wrangler queues info hoopsclips-analysis-dlq
npx wrangler d1 info hoopsclips-control-plane-staging
```

## Exact Smoke Commands

Local harness smoke:

```bash
npx tsx scripts/control-plane-happy-path.ts
```

Live staging smoke:

```bash
npx tsx scripts/control-plane-happy-path.ts --base-url https://api-staging.hoopsclips.example --trace-id staging-smoke-001
```

For the iOS Staging build, run the app against the same staging base URL stored in the `CONTROL_PLANE_BASE_URL` secret, then upload the same sample video and confirm the returned clips render in the UI.

The script now prints a summary with `requestIds.presign`, `requestIds.finalize`, `requestIds.callback`, and `requestIds.poll` so the trace can be matched against Worker logs.

## Staging Smoke Checklist

- Confirm the presign request returns `201` and includes `requestId`.
- Confirm the upload lands in `R2_UPLOADS` under the returned source key.
- Confirm `POST /jobs` returns `queued`.
- Confirm the queue dispatch appears in Worker logs with the same `requestId`.
- Confirm the stub inference callback completes successfully.
- Confirm `GET /jobs/:id` reaches `completed`.
- Confirm the app renders the returned clips.
- Confirm the final JSON summary includes `modelVersion`, `confidence`, and `clipCount`.

## Rollback Checklist

- Pause queue delivery first:

```bash
cd services/control-plane
npx wrangler queues pause-delivery hoopsclips-analysis
npx wrangler queues pause-delivery hoopsclips-analysis-dlq
```

- If the issue is the Worker, redeploy the previous known-good git SHA with the staging env:

```bash
cd services/control-plane
git checkout <previous-good-sha>
npx wrangler deploy --env staging
```

- If the issue is a bad secret, replace it with the known-good value using `wrangler secret put --env staging`.
- If the issue is only queue pressure, leave the Worker deployed and drain or purge the queue after the incident.

## Known Failure Modes

- Duplicate callback: the Durable Object ignores terminal-state regressions, so a second callback should return the current job state without rewinding status.
- Queue retry: queue messages can be retried; the DLQ receives messages after the configured retry limit, and the consumer message body should stay lightweight.
- Expired presigned URL: the upload fails before `POST /jobs`; issue a fresh presign and retry the upload.
- Missing staging secret: callback auth fails with `403`; verify all `wrangler secret put --env staging` entries exist.
- Invalid job state regression: `created -> upload_pending -> uploaded -> queued -> processing -> completed | failed | cancelled` is enforced, and backward transitions are ignored.

## Repeatability Notes

- `requestId` is emitted at presign, finalize, callback, and poll.
- The staging config is meant to be non-local and non-default; do not point the iOS staging build at localhost.
- `R2` must be enabled before the bucket commands will succeed.
