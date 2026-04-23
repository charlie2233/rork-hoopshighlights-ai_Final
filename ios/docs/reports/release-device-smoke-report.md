# Release Device Smoke Report

## Current status
- Launch posture: public app launch with cloud gated.
- Report state: blocked pending production secret population and a trusted physical iPhone connected to this Mac.

## Automated validation completed from this branch
- iOS launch-gating unit tests: passed via `LaunchRuntimeConfigTests`.
- Simulator app launch sanity check: passed after adding explicit RevenueCat guards for unconfigured builds.
- Backend launch-guardrail unit tests: passed locally.
- Release simulator artifact wiring: passed with an explicit app plist. Verified that Release resolves `HOOPS_CLOUD_LAUNCH_MODE = disabled`, an empty cloud base URL, the Google callback URL scheme, the legal-link URLs, and the staged billing/telemetry keys when injected.
- Google Sign-In callback plumbing is now wired from `HOOPS_GOOGLE_REVERSED_CLIENT_ID`; real-device sign-in still requires populated Release secrets.
- Privacy Policy and Terms of Service links are now surfaced in-app; the real-device smoke still needs to verify both links open the intended production pages.

## Manual real-device validation required
- Cold launch
- Google sign-in
- RevenueCat paywall, purchase, and restore
- Video import from Photos
- Video import from Files
- On-device analysis
- Review navigation
- Export render
- Save to Photos
- Settings > Launch Status reflects `On-device only`
- About & Privacy opens Privacy Policy and Terms of Service successfully

## Result template
| Check | Result | Notes |
| --- | --- | --- |
| Cold launch | pending |  |
| Google sign-in | pending |  |
| RevenueCat purchase | pending |  |
| RevenueCat restore | pending |  |
| Photos import | pending |  |
| Files import | pending |  |
| On-device analysis | pending |  |
| Review flow | pending |  |
| Export render | pending |  |
| Save to Photos | pending |  |
| Launch Status card | pending |  |
| Legal links open | pending |  |

## Blockers
- GitHub `production` environment has the real legal-link URLs populated, but it still needs real secrets for signing, Google, RevenueCat, and telemetry.
- Local `LocalSecrets.xcconfig` has not been materialized on this Mac because the operator-held Release values are not available in the current shell.
- The only visible physical iPhone is currently offline, so no true Release-device smoke has been executed yet.
- External crash-reporting client is not linked in this branch; launch telemetry currently relies on unified logs, with DSN config surfaced for future enablement.
