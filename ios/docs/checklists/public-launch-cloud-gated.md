# Public Launch Checklist: Cloud Gated

## Launch posture
- Public App Store build uses on-device Vision/CoreML + audio analysis as the supported path.
- Cloud analysis stays internal-only until authenticated rollout, dashboard alignment, and Phase 4h gates are green.

## Release config
- Fill `HoopsClips/HoopsClips/Config/LocalSecrets.xcconfig` or CI equivalents with:
  - `HOOPS_DEVELOPMENT_TEAM`
  - `HOOPS_REVENUECAT_API_KEY`
  - `HOOPS_GOOGLE_CLIENT_ID`
  - `HOOPS_SENTRY_DSN`
- Keep `HOOPS_CLOUD_LAUNCH_MODE = disabled` for the public Release build.
- Keep `HOOPS_CLOUD_ANALYSIS_BASE_URL` empty for the public Release build.

## Required validation before launch
- Release app installs and signs successfully on a real device.
- Google sign-in succeeds in Release.
- RevenueCat offerings load and purchase/restore paths work in Release.
- Video import works from Photos and Files.
- On-device analysis completes without cloud fallback.
- Review and export flows complete successfully.
- Save to Photos works.
- Support Center is reachable and shows launch status accurately.
- Launch telemetry writes unified logs in Release, and staged DSN config is visible in Settings when present.

## Explicit no-go items for public cloud cutover
- Do not enable public cloud analysis while `ios/backend` is internal-only.
- Do not re-enable `/v1/analysis/*` in managed mode without real authn/authz.
- Do not treat Phase 4h as ready while the human-truth gate is still locked.

## Required artifacts
- Update `ios/docs/reports/release-device-smoke-report.md` with the latest device smoke result.
- Keep launch-day notes in `ios/docs/runbooks/public-launch-cloud-gated.md`.
