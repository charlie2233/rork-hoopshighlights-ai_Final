# Rork Release Operator Handoff

## Current release posture
- Product name for handoff: Hoops Clips Final.
- Release source: `main` on `https://github.com/charlie2233/rork-hoopshighlights-ai_Final`.
- Public App Store path: on-device analysis only.
- Cloud ML path: gated/internal until Phase 4h confirmed-label gates clear.
- Release operations owner: Rork.

## What is already done
- `main` contains the public-launch cloud-gated release plumbing.
- GitHub Actions has a `production` environment.
- GitHub `production` variables are populated for:
  - `HOOPS_PRIVACY_POLICY_URL=https://rork.com/privacy`
  - `HOOPS_TERMS_OF_SERVICE_URL=https://rork.com/terms`
- The Release build is configured to keep `HOOPS_CLOUD_LAUNCH_MODE=disabled` and `HOOPS_CLOUD_ANALYSIS_BASE_URL` empty.
- Google callback routing, RevenueCat readiness checks, legal links, and launch-status UI are wired in app code.

## Rork inputs required
Rork must provide or confirm these production values before the Release smoke can start:

- `HOOPS_DEVELOPMENT_TEAM`
- `HOOPS_REVENUECAT_API_KEY`
- `HOOPS_GOOGLE_CLIENT_ID`
- `HOOPS_GOOGLE_REVERSED_CLIENT_ID`
- `HOOPS_SENTRY_DSN`

Rork also needs:

- Apple Developer/App Store Connect access for the bundle ID `app.rork.hoopshighlights-ai`
- a signing-capable Mac with the Apple team available in Xcode
- a trusted physical iPhone for the Release-device smoke
- Apple sandbox tester access for purchase and restore validation

## GitHub production setup
Run these from a machine authenticated to GitHub with admin access to the repo:

```bash
gh secret set HOOPS_DEVELOPMENT_TEAM -e production -b "$HOOPS_DEVELOPMENT_TEAM"
gh secret set HOOPS_REVENUECAT_API_KEY -e production -b "$HOOPS_REVENUECAT_API_KEY"
gh secret set HOOPS_GOOGLE_CLIENT_ID -e production -b "$HOOPS_GOOGLE_CLIENT_ID"
gh secret set HOOPS_GOOGLE_REVERSED_CLIENT_ID -e production -b "$HOOPS_GOOGLE_REVERSED_CLIENT_ID"
gh secret set HOOPS_SENTRY_DSN -e production -b "$HOOPS_SENTRY_DSN"

gh variable list -e production
gh secret list -e production
```

Then run the release preflight:

```bash
gh workflow run "Release Secrets Preflight" --ref main
gh run watch
```

The workflow must pass before the real-device smoke starts.

## Local Release smoke setup
On the signing-capable smoke Mac:

```bash
git clone https://github.com/charlie2233/rork-hoopshighlights-ai_Final.git
cd rork-hoopshighlights-ai_Final
git checkout main

export HOOPS_DEVELOPMENT_TEAM="..."
export HOOPS_REVENUECAT_API_KEY="..."
export HOOPS_GOOGLE_CLIENT_ID="..."
export HOOPS_GOOGLE_REVERSED_CLIENT_ID="..."
export HOOPS_SENTRY_DSN="..."
export HOOPS_PRIVACY_POLICY_URL="https://rork.com/privacy"
export HOOPS_TERMS_OF_SERVICE_URL="https://rork.com/terms"

./ios/scripts/materialize_local_secrets.sh
```

Use Xcode to select a physical iPhone and run the `HoopsClips` scheme in `Release`. If using command-line checks first, verify signing and config resolution before launching on device.

## Required smoke evidence
Update `ios/docs/reports/release-device-smoke-report.md` with pass/fail evidence for:

- cold launch
- Google sign-in
- RevenueCat paywall offerings
- sandbox purchase
- restore purchase
- Photos import
- Files import
- on-device analysis without cloud states
- review flow
- export render
- save to Photos
- Settings > Launch Status showing on-device-only
- Privacy Policy and Terms links opening correctly

If any row fails, fix only that concrete release blocker and rerun the smoke.

## App Store Connect submission
After a passing smoke:

- verify metadata, screenshots, support URL, privacy URL, and terms URL
- complete App Privacy answers
- verify subscription products and review metadata if subscriptions are live
- upload/archive from Xcode or Transporter
- submit to TestFlight or App Review

Browser automation can assist with App Store Connect forms, but the current Codex session does not expose a direct App Store Connect API connector. Treat App Store Connect as an operator-browser task unless Rork provides an API key and a dedicated submission flow.

## Do not change for GA
- Do not enable public cloud analysis.
- Do not run Phase 4h retraining, smoke, or medium batch as part of this publish path.
- Do not make cloud ML launch-critical.
- Do not transfer the GitHub repo before App Store submission unless Rork explicitly chooses that slower ownership path.
