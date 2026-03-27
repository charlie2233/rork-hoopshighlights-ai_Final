# Release Smoke Checklist

- Confirm `DEVELOPMENT_TEAM` is set for all app targets.
- Confirm RevenueCat production API key is populated.
- Confirm Google sign-in client ID is populated.
- Confirm the production cloud base URL is not localhost and is injected from environment-specific config.
- Confirm the app launches in release mode with no config crashes.
- Confirm sign-in works in release.
- Confirm the control-plane happy-path harness passes locally or against staging.
- For live staging, follow [`docs/staging_smoke_runbook.md`](./staging_smoke_runbook.md) and keep the returned `requestIds` summary.
- Confirm a sample video can be imported.
- Confirm cloud upload, queueing, polling, and result hydration work end to end.
- Confirm local fallback still works when cloud analysis is unavailable.
- Confirm the current on-device Vision/CoreML path still produces clips offline.
- Confirm a sample export still renders and saves.
