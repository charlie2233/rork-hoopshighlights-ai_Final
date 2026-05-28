# Phase Launch23: Staging Deploy Preflight Refresh

## Goal

Check whether this workstation can refresh the live staging editing service and Worker after the latest GPT/team-highlight quality changes.

## Evidence

Command:

```bash
python3 services/editing/scripts/deploy_preflight.py --json
```

Result: `status=blocked`.

Passing checks:

- gcloud CLI is available
- active GCP project is configured
- active gcloud account is configured
- Artifact Registry repo `hoopsclips` exists in `us-central1`
- Secret Manager entries exist for editing service secret and R2 access keys
- Cloud Run service `hoopclips-editing-staging` exists
- R2 endpoint URL is configured

Blocking checks:

- Secret Manager secret `HOOPS_OPENAI_API_KEY` is missing or inaccessible
- `CLOUDFLARE_API_TOKEN` is not set locally and local Wrangler OAuth is not valid

Related live probe:

```bash
python3 scripts/staging_version_probe.py --json
```

Result: `status=fail`.

- staging Worker `/v1/editing/version` returns HTTP `404`
- direct editing `/version` is reachable but stale and missing current AI Edit/GPT feature flags

## Launch Impact

No staging deploy or rollback was attempted from this machine. Internal TestFlight submission remains blocked until the live staging Worker and editing service are refreshed and verified with current git SHA plus required AI Edit/GPT flags.

No secret values, R2 credentials, storage object keys, or full presigned URLs were printed or committed.
