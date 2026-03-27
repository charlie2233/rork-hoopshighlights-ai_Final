# Cloudflare Environment Setup

This doc maps the control-plane scaffold to the real Wrangler bindings and the secret names used by the happy-path script.

## Worker Bindings

The Worker reads these values from `services/control-plane/wrangler.jsonc`:

- `JOB_STATE` Durable Object namespace
- `ANALYSIS_QUEUE` Queue producer
- `DB` D1 database
- `R2_UPLOADS` upload bucket
- `R2_RESULTS` result bucket

## Runtime Variables

These land in `Env` and are read by the control-plane code:

- `APP_ENV`
- `DEFAULT_POLL_AFTER_SECONDS`
- `SIGNED_UPLOAD_TTL_SECONDS`
- `JOB_TTL_SECONDS`
- `MAX_FILE_SIZE_BYTES`
- `MAX_DURATION_SECONDS`
- `ADMIN_API_TOKEN`
- `CONTROL_PLANE_SHARED_SECRET`
- `INFERENCE_BASE_URL`
- `INFERENCE_SHARED_SECRET`
- `R2_ACCOUNT_ID`
- `R2_UPLOAD_BUCKET_NAME`
- `R2_RESULT_BUCKET_NAME`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

## Local Harness Mode

This is the fastest way to verify the happy path and does not require Cloudflare bindings:

```bash
npm --prefix services/control-plane install
npx tsx scripts/control-plane-happy-path.ts
```

The harness uses in-memory state, so R2 credentials may be blank. It still exercises:

- job creation
- signed upload URL generation
- queue dispatch capture
- heartbeat handling
- callback hydration
- final poll response

## Live Local Worker Mode

Run the Worker locally with Wrangler:

```bash
cd services/control-plane
npm install
npm run dev
```

For local dev secrets, set the same names as staging:

```bash
cd services/control-plane
wrangler secret put ADMIN_API_TOKEN
wrangler secret put CONTROL_PLANE_SHARED_SECRET
wrangler secret put INFERENCE_SHARED_SECRET
wrangler secret put R2_ACCESS_KEY_ID
wrangler secret put R2_SECRET_ACCESS_KEY
```

The non-secret runtime variables can stay in `wrangler.jsonc` for local dev, or be overridden with `wrangler deploy --env <name>`.

## Staging Setup

Use the same variable names in staging, but populate them from the staging environment:

- `APP_ENV=staging`
- `INFERENCE_BASE_URL` pointing at the staging inference service
- `R2_ACCOUNT_ID` for the staging Cloudflare account
- `R2_UPLOAD_BUCKET_NAME` and `R2_RESULT_BUCKET_NAME` pointing at staging buckets

Staging secrets:

```bash
cd services/control-plane
wrangler secret put ADMIN_API_TOKEN --env staging
wrangler secret put CONTROL_PLANE_SHARED_SECRET --env staging
wrangler secret put INFERENCE_SHARED_SECRET --env staging
wrangler secret put R2_ACCESS_KEY_ID --env staging
wrangler secret put R2_SECRET_ACCESS_KEY --env staging
```

## Notes

- Durable Objects own per-job state.
- D1 is the secondary index, not the source of truth.
- R2 stores uploads, result manifests, and derived artifacts.
- The happy-path script can run against either the in-memory harness or a live Worker via `--base-url`.
