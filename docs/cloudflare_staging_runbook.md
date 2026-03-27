# Cloudflare Staging Runbook

This runbook covers the phase-1b live staging path for the control plane only.
It does not include dashboard work or model work.

## Prerequisites

- `wrangler` logged in against the HoopsClips Cloudflare account
- Node.js dependencies installed in `services/control-plane`
- The staging iOS build configured with the staging API base URL

## Resource Setup

The staging Worker uses these Cloudflare resources:

- `hoopsclips-control-plane-staging` Worker name
- `hoopsclips-control-plane-staging` D1 database
- `hoopsclips-analysis` main queue
- `hoopsclips-analysis-dlq` dead-letter queue
- `hoopsclips-uploads-staging` R2 upload bucket
- `hoopsclips-results-staging` R2 result bucket

Create or verify the resources:

```bash
cd services/control-plane
npx wrangler queues create hoopsclips-analysis
npx wrangler queues create hoopsclips-analysis-dlq
npx wrangler d1 create hoopsclips-control-plane-staging
npx wrangler d1 info hoopsclips-control-plane-staging
npx wrangler r2 bucket create hoopsclips-uploads-staging
npx wrangler r2 bucket create hoopsclips-results-staging
```

If `wrangler r2 bucket create` fails with `code: 10042`, R2 is not enabled for the account yet.
That is a hard blocker for live staging until Cloudflare enables R2 in the account.

## Secrets

Set these as Wrangler secrets. Do not place them in `vars`.

- `ADMIN_API_TOKEN`
- `CONTROL_PLANE_SHARED_SECRET`
- `INFERENCE_SHARED_SECRET`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

Local:

```bash
cd services/control-plane
wrangler secret put ADMIN_API_TOKEN
wrangler secret put CONTROL_PLANE_SHARED_SECRET
wrangler secret put INFERENCE_SHARED_SECRET
wrangler secret put R2_ACCESS_KEY_ID
wrangler secret put R2_SECRET_ACCESS_KEY
```

Staging:

```bash
cd services/control-plane
wrangler secret put ADMIN_API_TOKEN --env staging
wrangler secret put CONTROL_PLANE_SHARED_SECRET --env staging
wrangler secret put INFERENCE_SHARED_SECRET --env staging
wrangler secret put R2_ACCESS_KEY_ID --env staging
wrangler secret put R2_SECRET_ACCESS_KEY --env staging
```

## Deploy

```bash
cd services/control-plane
npx wrangler deploy --env staging
```

The deploy output prints the staging Worker URL. Use that URL for smoke tests.

## Smoke Test

Run the live happy path against the deployed staging Worker:

```bash
npx tsx scripts/control-plane-happy-path.ts --base-url https://<staging-worker-url> --shared-secret "$CONTROL_PLANE_SHARED_SECRET"
```

If the app build is already pointed at the staging API URL, run the iOS staging build and upload the sample video through the app.
Confirm the terminal output and the app logs both show the same `requestId` from presign through completed poll.

## Smoke-Test Checklist

- `POST /uploads/presign` returns `201`
- The sample video uploads to R2 successfully
- `POST /jobs` returns `queued`
- A queue message is emitted
- The callback returns `200`
- `GET /jobs/:id` returns `completed`
- The app renders the returned clips
- `requestId` is visible in presign, queue dispatch, callback, and poll logs

## Rollback Checklist

- Pause queue delivery for `hoopsclips-analysis`
- Disable or remove the staging Worker route
- Leave the R2 buckets and D1 database intact unless the rollback is destructive
- Revert the staging Worker deployment if the config change is the source of the failure
- Keep the DLQ untouched so failed messages can be inspected after rollback

## Known Failure Modes

- Duplicate callback: the Worker should ignore terminal regressions and return the current job snapshot.
- Queue retry: the message may be retried before the DLQ threshold is reached; keep the payload small and idempotent.
- Expired presigned URL: the upload step will fail before job finalization; request a new presign.
- Missing staging secret: callback or upload signing fails with an auth or signature error.
- Invalid job state regression: the Durable Object should reject status moves that go backward from terminal states.

## Notes

- The control plane still runs the on-device Vision/CoreML fallback in iOS if the cloud path is unavailable.
- The staging path is stub-inference only for this phase.
