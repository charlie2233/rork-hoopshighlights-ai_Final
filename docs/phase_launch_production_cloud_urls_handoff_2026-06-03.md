# Production Cloud URL Variable Handoff - 2026-06-03

This handoff is for the release owner who can confirm and set the public
production cloud endpoints for HoopClips.

Do not paste secrets, tokens, private keys, base64 values, or credential
contents into chat or logs. The variables below are non-secret URLs, but they
still affect the production launch gate and must be confirmed before setting.

## Current blocker

Latest verified GitHub `production` environment variables only show:

- `HOOPS_PRIVACY_POLICY_URL=https://rork.com/privacy`
- `HOOPS_TERMS_OF_SERVICE_URL=https://rork.com/terms`

The required production cloud URL variables are missing:

- `HOOPS_CLOUD_ANALYSIS_BASE_URL`
- `HOOPS_CLOUD_EDIT_BASE_URL`

Latest `Release Secrets Preflight` evidence:

- Run `26884199422`: `failure`

Do not claim the production cloud gate is green until the missing URL variables
are set and Release Secrets Preflight passes on the current launch branch.

## Values to confirm

Release owner must confirm the exact production values for:

- `HOOPS_CLOUD_ANALYSIS_BASE_URL`
- `HOOPS_CLOUD_EDIT_BASE_URL`

The current internal staging Worker endpoint that has been used for internal
proof is:

`https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`

Use that endpoint for production only if the release owner explicitly confirms
that the internal TestFlight production environment should point at the staging
Worker for this launch gate. Otherwise use the release-owner-provided
production Worker URLs.

## Commands for the release owner

Run these from the repo root after confirming the exact URL values:

```bash
gh variable set HOOPS_CLOUD_ANALYSIS_BASE_URL \
  --env production \
  --body '<confirmed-analysis-base-url>'

gh variable set HOOPS_CLOUD_EDIT_BASE_URL \
  --env production \
  --body '<confirmed-edit-base-url>'
```

Then rerun the release preflight:

```bash
gh workflow run release-secrets-preflight.yml \
  --ref codex/phase-launch-proof-next
```

After the workflow starts, report only non-secret status:

- The two variable names were set.
- The workflow run ID.
- Whether the run passed or failed.
- If it failed, the missing variable names or failing check names only.

Do not report URL query strings, credentials, secrets, private key contents,
base64 values, API keys, tokens, or full secret values.

## Expected completion evidence

This blocker can be marked resolved only after:

- `gh variable list --env production` shows both cloud URL variable names.
- `Release Secrets Preflight` passes on the launch branch after those variables
  are set.
- The launch readiness snapshot is updated with the passing run ID.

Until then, internal TestFlight readiness remains incomplete.

## 2026-06-03 current production-variable check

A current non-secret GitHub environment check still shows only:

- `HOOPS_PRIVACY_POLICY_URL=https://rork.com/privacy`
- `HOOPS_TERMS_OF_SERVICE_URL=https://rork.com/terms`

The production environment still does not visibly expose
`HOOPS_CLOUD_ANALYSIS_BASE_URL` or `HOOPS_CLOUD_EDIT_BASE_URL`.
The latest `Release Secrets Preflight` run remains `26884199422`, completed
`failure` on `86fdc33` at `2026-06-03T12:17:59Z`.

Do not rerun release preflight as launch evidence until the production cloud URL
variables are set or the release owner confirms a different non-secret evidence
source.
