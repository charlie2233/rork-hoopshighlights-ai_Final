# Runbook: Public Launch With Cloud Gated

## Scope
- Target product path: cloud backend owns video analysis, AI edit planning, and final rendering.
- Current fallback launch path: cloud disabled, with local/on-device analysis only while cloud gates remain locked.
- Internal-only path: cloud backend, AI edit agent, cloud rendering, and any future dashboard moderation flows.
- GitHub Actions `production` environment is the source of truth for Release secrets and required legal-link URLs; the local ignored xcconfig is only a smoke-machine mirror.
- Rork release operations should start from `ios/docs/runbooks/rork-release-operator-handoff.md`.

## What the app should do
- Release builds should default to `HOOPS_CLOUD_LAUNCH_MODE = disabled`.
- When cloud is disabled, analysis starts on-device immediately instead of entering the cloud path and falling back later.
- This is a temporary release-safety posture, not the long-term Hoopclips AI Edit Agent architecture.
- Support staff should expect:
  - no cloud upload
  - no cloud polling
  - no cloud quota banner as the primary product message
  - export, history, and review to continue working locally

## Launch-day checks
1. Populate the existing GitHub `production` environment secrets with `HOOPS_DEVELOPMENT_TEAM`, `HOOPS_REVENUECAT_API_KEY`, `HOOPS_GOOGLE_CLIENT_ID`, `HOOPS_GOOGLE_REVERSED_CLIENT_ID`, `HOOPS_FIREBASE_AUTH_API_KEY`, and `HOOPS_SENTRY_DSN`.
2. Populate the existing GitHub `production` environment variables with `HOOPS_PRIVACY_POLICY_URL` and `HOOPS_TERMS_OF_SERVICE_URL`.
3. Run the `Release Secrets Preflight` workflow and require it to pass before the device smoke starts.
4. On the smoke Mac, export those same operator-held values and run `./ios/scripts/materialize_local_secrets.sh`.
5. Verify Release config values are present for team, Google sign-in, Firebase email auth, RevenueCat, legal links, and telemetry settings.
6. Verify the app shows `On-device only` in Settings > Launch Status.
7. Confirm `Google Sign-In = Ready`, `Email Auth = Ready`, `RevenueCat = Ready`, `Legal Links = Ready`, and `Telemetry = DSN staged`.
8. Open both links from Settings > About & Privacy and confirm they resolve to the intended production pages.
9. Import one short basketball clip from Photos.
10. Import one short basketball clip from Files.
11. Run analysis and confirm progress text says `Analyzing on device`.
12. Confirm clips appear in Review.
13. Run the paywall, purchase with an Apple sandbox tester, then restore purchases with the same sandbox account.
14. Export and save to Photos.
15. Submit one support message from Settings > Support Center.
16. Confirm App Store subscription metadata, review notes, and paywall copy match `ios/docs/legal/hoopsclips-premium-subscription-policy.md`.
17. Fill App Store Connect sign-in information from `ios/docs/app-store/app-review-sign-in.md` without committing the real password.

## Failure handling
### Google sign-in fails
- Check both `HOOPS_GOOGLE_CLIENT_ID` and `HOOPS_GOOGLE_REVERSED_CLIENT_ID` for the Release build.
- Capture the unified log stream from the launch device.
- Keep guest and email/phone fallback options available while fixing config.

### Email/password sign-in fails
- Check `HOOPS_FIREBASE_AUTH_API_KEY` in both GitHub `production` and the local mirrored xcconfig.
- Confirm Firebase Authentication has Email/Password enabled for the Hoopclips Firebase project.
- Confirm the App Review account can sign in twice, either after reinstall or on a second device.
- Use `ios/docs/runbooks/firebase-auth-setup.md` for setup steps.

### Legal links fail to open
- Check `HOOPS_PRIVACY_POLICY_URL` and `HOOPS_TERMS_OF_SERVICE_URL` in both GitHub `production` and the local mirrored xcconfig.
- Confirm each URL is `https://` and resolves without redirecting to a draft or placeholder page.
- Do not submit a public build that has missing or broken in-app legal links.

### RevenueCat offerings fail or purchase/restore fails
- Check `HOOPS_REVENUECAT_API_KEY`.
- Confirm the paywall loads and capture the unified log stream if it does not.
- Do not ship a Release build that silently disables purchases.

### Subscription disclosure is unclear
- Check that the paywall shows the subscription name, price, billing period, renewal behavior, Premium benefits, and Restore Purchases.
- Check that App Store Connect metadata points to the current Privacy Policy and Terms of Service.
- Keep the subscription copy aligned with `ios/docs/legal/hoopsclips-premium-subscription-policy.md`.
- Do not submit if subscription price, duration, renewal, or cancellation language conflicts across the paywall, App Store metadata, and support docs.

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
- Public `/v1/edit-jobs/*` backend access
- Cloud FFmpeg rendering for public users
- Dashboard/admin reliance during public launch
- Phase 4h medium-batch promotion
