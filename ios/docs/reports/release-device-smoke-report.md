# Release Device Smoke Report

## Current status
- Launch posture: public app launch with cloud gated.
- Report state: pending real-device execution.

## Automated validation completed from this branch
- iOS launch-gating unit tests: passed via `LaunchRuntimeConfigTests`.
- Simulator app launch sanity check: passed after adding explicit RevenueCat guards for unconfigured builds.
- Backend launch-guardrail unit tests: passed locally.

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

## Blockers
- Real device + valid signing team required.
- Production Google sign-in and RevenueCat values required.
- External crash-reporting client is not linked in this branch; launch telemetry currently relies on unified logs, with DSN config surfaced for future enablement.
