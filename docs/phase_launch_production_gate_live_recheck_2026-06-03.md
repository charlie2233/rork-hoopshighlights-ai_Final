# Phase Launch production gate live recheck - 2026-06-03

## Scope

This is a secret-safe live recheck of GitHub production environment metadata and recent release/deploy workflow status. It does not read secret values, change variables, change launch mode, rerun signed archive workflows, or enable public cloud ML/rendering.

## Production environment variables

Current `gh variable list --env production` output shows only:

- `HOOPS_PRIVACY_POLICY_URL=https://rork.com/privacy` (updated `2026-04-23T17:54:20Z`)
- `HOOPS_TERMS_OF_SERVICE_URL=https://rork.com/terms` (updated `2026-04-23T17:54:21Z`)

Production launch URL variables are still not present in the visible environment variable list:

- `HOOPS_CLOUD_ANALYSIS_BASE_URL`
- `HOOPS_CLOUD_EDIT_BASE_URL`

## Production environment secret names

Current `gh secret list --env production` confirms secret names only, not values:

- `HOOPS_DEVELOPMENT_TEAM` (updated `2026-04-26T02:56:23Z`)
- `HOOPS_FIREBASE_AUTH_API_KEY` (updated `2026-04-27T15:23:55Z`)
- `HOOPS_GOOGLE_CLIENT_ID` (updated `2026-04-26T02:58:13Z`)
- `HOOPS_GOOGLE_REVERSED_CLIENT_ID` (updated `2026-04-26T02:58:41Z`)
- `HOOPS_REVENUECAT_API_KEY` (updated `2026-04-26T02:58:03Z`)
- `HOOPS_SENTRY_DSN` (updated `2026-04-26T02:58:56Z`)

This secret-name list does not prove that the secret values are valid, that production cloud URLs are configured, or that signed archive/upload credentials are usable.

## Workflow status

Latest `Release Secrets Preflight` run remains:

- `26884199422`: completed `failure`, head `86fdc33`, branch `codex/phase-launch-proof-next`, event `workflow_dispatch`, created `2026-06-03T12:17:59Z`

Recent `Cloud Edit Deploy Preflight` runs on `codex/phase-launch-proof-next` are green, including:

- `26904259095`: completed `success`, head `c16d6e2`, created `2026-06-03T18:17:54Z`

The green deploy-preflight run is useful branch proof, but it does not replace Release Secrets Preflight and does not close production URL/secrets readiness.

## Launch gate conclusion

Production cloud cutover remains blocked until release owners set and confirm the production cloud URL variables, fix any required secret values/settings, and rerun Release Secrets Preflight to a green result on the current launch branch tip.
