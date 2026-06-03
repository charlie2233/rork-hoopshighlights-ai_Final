# Phase Launch: Release Secrets Cloud URL Blocker

Date: 2026-06-03
Branch: `codex/phase-launch-proof-next`
Head: `86fdc33eb53033ed7d527c69adbdf07c0cb96872`

## Current proof

Current-head non-secret proof is green:

- Cloud Edit Deploy Preflight: `26883915588` succeeded on `86fdc33eb53033ed7d527c69adbdf07c0cb96872`.
- iOS Internal TestFlight Upload `operation=codecheck`: `26883917628` succeeded on `86fdc33eb53033ed7d527c69adbdf07c0cb96872`.
- The signed TestFlight archive job was skipped intentionally in the no-secret codecheck run.

Release production configuration proof is blocked:

- Release Secrets Preflight: `26884199422` failed on `86fdc33eb53033ed7d527c69adbdf07c0cb96872`.
- Failed job: `Validate production release secrets`.
- Non-secret missing GitHub `production` environment variables:
  - `HOOPS_CLOUD_ANALYSIS_BASE_URL`
  - `HOOPS_CLOUD_EDIT_BASE_URL`

Visible GitHub `production` environment variables at the time of this note:

- `HOOPS_PRIVACY_POLICY_URL=https://rork.com/privacy`
- `HOOPS_TERMS_OF_SERVICE_URL=https://rork.com/terms`

The run showed the required production secrets for team, RevenueCat, Google, Firebase, and Sentry as present without exposing their values.

## Candidate internal TestFlight value

The repo's internal staging configuration and no-secret iOS codecheck expect this Worker base URL for both cloud analysis and cloud edit:

```text
https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
```

Do not set this as a production environment value unless Rork confirms that the current internal TestFlight build should point Release smoke at the staging Worker. Public cloud cutover still remains gated by the launch runbooks.

## Operator action after confirmation

After Rork confirms the intended Release smoke endpoint, set the two non-secret GitHub environment variables:

```bash
WORKER_BASE_URL="https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev"

gh variable set HOOPS_CLOUD_ANALYSIS_BASE_URL -e production --body "$WORKER_BASE_URL"
gh variable set HOOPS_CLOUD_EDIT_BASE_URL -e production --body "$WORKER_BASE_URL"

gh workflow run release-secrets-preflight.yml --ref codex/phase-launch-proof-next
```

If Rork provides a different production Worker URL, use that confirmed URL for both variables instead.

## Why this matters

Release builds require non-empty cloud analysis and cloud edit base URLs. If these remain blank, the Release app cannot prove the cloud-owned launch path and should not proceed to signed archive, TestFlight upload, or installed-device smoke as launch evidence.
