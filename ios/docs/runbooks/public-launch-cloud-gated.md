# Runbook: Public Launch With Cloud Gated

## Scope
- Public launch path: on-device analysis only.
- Internal-only path: cloud backend and any future dashboard moderation flows.
- GitHub Actions `production` environment is the source of truth for Release secrets and required legal-link URLs; the local ignored xcconfig is only a smoke-machine mirror.

## What the app should do
- Release builds should default to `HOOPS_CLOUD_LAUNCH_MODE = disabled`.
- When cloud is disabled, analysis starts on-device immediately instead of entering the cloud path and falling back later.
- Support staff should expect:
  - no cloud upload
  - no cloud polling
  - no cloud quota banner as the primary product message
  - export, history, and review to continue working locally

## Launch-day checks
1. Populate the existing GitHub `production` environment secrets with `HOOPS_DEVELOPMENT_TEAM`, `HOOPS_REVENUECAT_API_KEY`, `HOOPS_GOOGLE_CLIENT_ID`, `HOOPS_GOOGLE_REVERSED_CLIENT_ID`, and `HOOPS_SENTRY_DSN`.
2. Populate the existing GitHub `production` environment variables with `HOOPS_PRIVACY_POLICY_URL` and `HOOPS_TERMS_OF_SERVICE_URL`.
3. Run the `Release Secrets Preflight` workflow and require it to pass before the device smoke starts.
4. On the smoke Mac, export those same operator-held values and run `./ios/scripts/materialize_local_secrets.sh`.
5. Verify Release config values are present for team, Google sign-in, RevenueCat, legal links, and telemetry settings.
6. Verify the app shows `On-device only` in Settings > Launch Status.
7. Confirm `Google Sign-In = Ready`, `RevenueCat = Ready`, `Legal Links = Ready`, and `Telemetry = DSN staged`.
8. Open both links from Settings > About & Privacy and confirm they resolve to the intended production pages.
9. Import one short basketball clip from Photos.
10. Import one short basketball clip from Files.
11. Run analysis and confirm progress text says `Analyzing on device`.
12. Confirm clips appear in Review.
13. Run the paywall, purchase with an Apple sandbox tester, then restore purchases with the same sandbox account.
14. Export and save to Photos.
15. Submit one support message from Settings > Support Center.

## Failure handling
### Google sign-in fails
- Check both `HOOPS_GOOGLE_CLIENT_ID` and `HOOPS_GOOGLE_REVERSED_CLIENT_ID` for the Release build.
- Capture the unified log stream from the launch device.
- Keep guest and email/phone fallback options available while fixing config.

### Legal links fail to open
- Check `HOOPS_PRIVACY_POLICY_URL` and `HOOPS_TERMS_OF_SERVICE_URL` in both GitHub `production` and the local mirrored xcconfig.
- Confirm each URL is `https://` and resolves without redirecting to a draft or placeholder page.
- Do not submit a public build that has missing or broken in-app legal links.

### RevenueCat offerings fail or purchase/restore fails
- Check `HOOPS_REVENUECAT_API_KEY`.
- Confirm the paywall loads and capture the unified log stream if it does not.
- Do not ship a Release build that silently disables purchases.

### Import fails
- Re-test Photos and Files separately.
- Collect device model, iOS version, and the source file extension.

### On-device analysis fails
- Record the exact status message from the analysis card.
- Capture whether the failure is reproducible on a second clip.
- File the failure with device model, iOS version, clip duration, and whether the clip is from Photos or Files.

### Export/save fails
- Confirm the latest reel appears in Export.
- Capture whether failure occurs during render or Photos save.

## Rollback
- If cloud is accidentally enabled, restore `HOOPS_CLOUD_LAUNCH_MODE = disabled` and clear the Release cloud base URL.
- Re-run the release smoke and confirm Settings shows `On-device only`.

## Out of scope until cloud cutover
- Public `/v1/analysis/*` backend access
- Dashboard/admin reliance during public launch
- Phase 4h medium-batch promotion
