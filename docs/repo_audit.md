# Repo Audit

## Current Shape

- The repo has already been reorganized around an `ios/` root for the app and backend code.
- The iOS app lives under `ios/HoopsClips/`.
- The current backend scaffold lives under `ios/backend/`.
- There is no existing `docs/` tree or dashboard app scaffold.

## Current AI Path

- The on-device path is the fast local fallback.
- It uses Vision pose extraction, motion scoring, scene scoring, audio peaks, and a bundled CoreML action classifier.
- The cloud path is still the older API-oriented scaffold and remains heuristic-first unless optional external repos are installed.

## Release Blockers

- `DEVELOPMENT_TEAM` is blank in the Xcode project.
- RevenueCat production configuration is blank in `AppConstants`.
- Google sign-in client ID is blank in `AppConstants` and `Config`.
- The cloud base URL is localhost-oriented in debug and empty in release unless manually overridden.
- The current backend README and config still assume a GCP/Cloud Run/Cloud Tasks model.

## Migration Risks

- The current public cloud API is stable enough to preserve, but the backend internals are not Cloudflare-shaped yet.
- The backend schema does not yet treat `modelVersion` and `failureReason` as first-class contract fields.
- There is no dashboard surface yet, so review tooling is a greenfield addition.
- The GPU inference service should stay separate from the control plane so the Worker and dashboard never host FFmpeg or model execution.

## Phase 0 Outputs

- Repo audit
- Architecture doc
- Implementation plan
- Release smoke checklist
- Cloudflare env/setup doc
- Deployment checklist
- Eval harness doc

