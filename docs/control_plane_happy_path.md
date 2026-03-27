# Control Plane Happy Path

This runbook is the quickest way for a fresh engineer to verify the HoopsClips control plane without touching the iOS client.

## Prerequisites

- Node.js 20+
- `services/control-plane` dependencies installed locally
- For live Worker runs, a `wrangler` login and the Cloudflare bindings/secrets from [`docs/cloudflare_env_setup.md`](./cloudflare_env_setup.md)

## Local Happy Path

The fastest verification path is the in-memory harness:

```bash
npm --prefix services/control-plane install
npx tsx scripts/control-plane-happy-path.ts
```

That script performs:

1. `POST /v1/analysis/jobs`
2. R2 upload to the signed upload URL
3. `POST /v1/analysis/jobs/{jobId}/start`
4. queue dispatch capture
5. `POST /v1/internal/inference/heartbeat/{jobId}`
6. `POST /v1/internal/inference/callback/{jobId}`
7. `GET /v1/analysis/jobs/{jobId}`

## Live Local Worker

To run the same flow against a local `wrangler dev` instance:

```bash
cd services/control-plane
npm install
npm run dev
```

In another terminal:

```bash
npx tsx scripts/control-plane-happy-path.ts --base-url http://127.0.0.1:8787
```

## Staging

After the Worker, R2, D1, and Queue bindings are deployed to staging:

```bash
npx tsx scripts/control-plane-happy-path.ts --base-url https://<staging-control-plane-host>
```

Pass `--shared-secret` if staging uses a non-default internal callback secret.

## Automated Checks

```bash
npx tsx --test services/control-plane/test/control-plane-status-transitions.test.ts
npx tsx --test services/control-plane/test/control-plane-failure-path.test.ts
```

## What to Expect

- The happy-path script prints a JSON summary with the final job status, model version, clip count, and upload key.
- The success test should end in `succeeded`.
- The failure test should end in `failed` and preserve the failure reason.
