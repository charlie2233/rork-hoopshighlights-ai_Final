# Public Launch Checklist: Cloud Gated

## Launch posture
- Hoopclips target architecture is cloud-backend video analysis, AI edit planning, and cloud rendering.
- The current public App Store build keeps cloud disabled and uses the local/on-device path as a temporary launch-safe fallback.
- Cloud analysis, cloud edit planning, and cloud rendering stay internal-only until authenticated rollout, storage/render reliability, dashboard alignment, observability, and Phase 4h gates are green.

## Release config
- GitHub Actions `production` environment is the source of truth for Release secrets and required Release URLs.
- Rork release operators should use `ios/docs/runbooks/rork-release-operator-handoff.md` as the handoff entrypoint.
- Fill GitHub `production` secrets and the local mirror file `HoopsClips/HoopsClips/Config/LocalSecrets.xcconfig` with:
  - `HOOPS_DEVELOPMENT_TEAM`
  - `HOOPS_REVENUECAT_API_KEY`
  - `HOOPS_GOOGLE_CLIENT_ID`
  - `HOOPS_GOOGLE_REVERSED_CLIENT_ID`
  - `HOOPS_FIREBASE_AUTH_API_KEY`
  - `HOOPS_SENTRY_DSN`
- Fill GitHub `production` environment variables and the same local mirror with:
  - `HOOPS_PRIVACY_POLICY_URL`
  - `HOOPS_TERMS_OF_SERVICE_URL`
- Generate the local mirror with `./ios/scripts/materialize_local_secrets.sh` from operator-held environment variables on the smoke machine.
- Keep `HOOPS_CLOUD_LAUNCH_MODE = disabled` for the public Release build.
- Keep `HOOPS_CLOUD_ANALYSIS_BASE_URL` empty for the public Release build.
- Require the manual `Release Secrets Preflight` GitHub Actions workflow to pass before the real-device Release smoke.

## Required validation before launch
- Release app installs and signs successfully on a real device.
- Google sign-in succeeds in Release.
- Firebase-backed email/password sign-in succeeds in Release with the App Review account.
- RevenueCat offerings load and purchase/restore paths work in Release.
- RevenueCat purchase/restore uses an Apple sandbox tester account, not a live purchase.
- App Store subscription metadata and review notes match `ios/docs/legal/hoopsclips-premium-subscription-policy.md`.
- Video import works from Photos and Files.
- Temporary local/on-device fallback analysis completes without attempting public cloud fallback.
- Review and export flows complete successfully.
- Save to Photos works.
- Support Center is reachable and shows launch status accurately.
- About & Privacy opens the Privacy Policy and Terms of Service URLs from the shipped app.
- Launch telemetry writes unified logs in Release, and staged DSN config is visible in Settings when present.
- Accessibility smoke passes on a physical iPhone for VoiceOver, largest text size, Reduce Motion, and normal mode. Use `ios/docs/checklists/release-accessibility-smoke-checklist.md` and record results in the release smoke report.

## Explicit no-go items for public cloud cutover
- Do not enable public cloud analysis, edit planning, or rendering while `ios/backend` is internal-only.
- Do not re-enable `/v1/analysis/*` in managed mode without real authn/authz.
- Do not add iOS-owned production video rendering as a substitute for the cloud renderer.
- Do not treat Phase 4h as ready while the human-truth gate is still locked.

## Required artifacts
- Update `ios/docs/reports/release-device-smoke-report.md` with the latest device smoke result.
- Keep the accessibility smoke checklist current at `ios/docs/checklists/release-accessibility-smoke-checklist.md`.
- Keep launch-day notes in `ios/docs/runbooks/public-launch-cloud-gated.md`.
- Keep the Premium subscription policy current at `ios/docs/legal/hoopsclips-premium-subscription-policy.md`.
- Use `ios/docs/app-store/app-review-sign-in.md` for App Store Connect review credentials and notes.
- Use `ios/docs/runbooks/firebase-auth-setup.md` to configure real email/password auth.
