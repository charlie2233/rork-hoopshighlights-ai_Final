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

## 2026-06-03 current branch refresh - 245794e

Current recheck: 2026-06-03T21:16:57Z
Branch: `codex/phase-launch-proof-next`
Checked tip: `245794e60356c72e24321ec29af9f14ecb2b0d4b`

Fresh no-secret branch proof on this tip:

- Cloud Edit Deploy Preflight: `26913261169`, conclusion `success`, head `245794e`.
- iOS Internal TestFlight Upload with `operation=codecheck`: `26913261147`, conclusion `success`, head `245794e`.

Current production variable check still shows only:

- `HOOPS_PRIVACY_POLICY_URL=https://rork.com/privacy`
- `HOOPS_TERMS_OF_SERVICE_URL=https://rork.com/terms`

Still missing visible production variables:

- `HOOPS_CLOUD_ANALYSIS_BASE_URL`
- `HOOPS_CLOUD_EDIT_BASE_URL`

Latest Release Secrets Preflight evidence remains unchanged:

- Run `26884199422`: `failure`, head `86fdc33`, branch `codex/phase-launch-proof-next`, dispatched 2026-06-03T12:17:59Z.

The green no-secret branch workflows above do not close this blocker. The blocker closes only after the production cloud URL variables are set or otherwise proven through a secret-safe release-owner path and `release-secrets-preflight.yml` passes on the launch branch tip.

Do not proceed to signed archive/upload or installed TestFlight smoke as launch evidence while Release builds cannot prove non-empty cloud analysis and edit base URLs.
