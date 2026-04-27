# Release Device Smoke Report

## Current status
- Launch posture: public app launch with cloud gated.
- Report state: Current `main` Release app built, installed, and cold-launched on the physical iPhone on 2026-04-27 09:39 PDT; Settings launch-status navigation was already verified on the physical iPhone. Remaining manual real-device smoke rows are still pending.
- Latest GitHub preflight evidence: `Release Secrets Preflight` run `25004048712` passed on 2026-04-27 on `main`, verifying production secret presence, Release build settings, cloud-disabled launch posture, Release simulator build, and built Info.plist wiring.

## Automated validation completed from this branch
- iOS launch-gating unit tests: passed via `LaunchRuntimeConfigTests`.
- Simulator app launch sanity check: passed after adding explicit RevenueCat guards for unconfigured builds.
- Backend launch-guardrail unit tests: passed locally.
- Release simulator artifact wiring: passed with an explicit app plist. Verified that Release resolves `HOOPS_CLOUD_LAUNCH_MODE = disabled`, an empty cloud base URL, the Google callback URL scheme, the legal-link URLs, and the staged billing/telemetry keys when injected.
- Local Release device build settings: passed after materializing `LocalSecrets.xcconfig`; Release resolves non-empty signing, RevenueCat, Google, legal-link, and telemetry settings while preserving cloud-disabled launch posture.
- Physical iPhone pairing and Developer Mode: passed; Xcode now sees `charlie`'s iPhone as an available iOS destination.
- Firebase Email/Password backend auth: passed via real Firebase project `hoopsclips-9d38f`; App Review account sign-in was verified through Firebase Auth, with credentials stored only in ignored local secrets.
- Release physical-device build, install, and command launch: refreshed on 2026-04-27 for current `main`; passed for bundle `atrak.charlie.hoopsclips` on `charlie`'s iPhone after the device was unlocked.
- Settings launch-status regression check: passed after patching the Release-only Settings tab crash. LLDB showed the prior crash in `SettingsView.body` Swift metadata instantiation; the patched Release build was rebuilt, installed, and user-verified on the physical iPhone.
- Google Sign-In callback plumbing is wired from `HOOPS_GOOGLE_REVERSED_CLIENT_ID`; real-device sign-in passed with the populated Release config.
- Privacy Policy and Terms of Service links are now surfaced in-app; the real-device smoke still needs to verify both links open the intended production pages.
- Accessibility hardening build validation: passed on 2026-04-27 10:58 PDT. `HoopsClipsTests` passed 45 tests on the booted iPhone 17 Pro simulator, and a signed `Release` device build succeeded for bundle `atrak.charlie.hoopsclips`.
- Accessibility real-device smoke status: blocked on 2026-04-27 10:58 PDT because `xcrun devicectl list devices` reported `charlie`'s iPhone `E5786BB6-0095-5509-8B85-110C0B5CE6D3` as `unavailable`. Run the checklist after the phone is unlocked/trusted/online.

## Manual real-device validation required
- Cold launch
- Accessibility pass with VoiceOver, largest text size, Reduce Motion, and normal mode
- RevenueCat paywall, purchase, and restore
- Video import from Photos
- Video import from Files
- On-device analysis
- Review navigation
- Export render
- Save to Photos
- About & Privacy opens Privacy Policy and Terms of Service successfully

## Result template
| Check | Result | Notes |
| --- | --- | --- |
| Cold launch | pass | Current `main` Release app built, installed, and launched on paired iPhone via `devicectl` at 2026-04-27 09:39 PDT for bundle `atrak.charlie.hoopsclips`; installed bundle reports version `1.0.0` build `1`. |
| Google sign-in | pass | User verified Google Sign-In completes on the physical iPhone using the Release build and production Google config. |
| RevenueCat purchase | fail | Paywall opened on the physical iPhone. A later purchase attempt prompted for the App Store Apple account, then returned to Processing with no visible completion state. The app now surfaces a clear error if StoreKit/RevenueCat returns without activating the `pro` entitlement. Verify the App Store Connect product, sandbox account, RevenueCat entitlement `pro`, current offering, and package are wired for bundle `atrak.charlie.hoopsclips`. |
| RevenueCat restore | blocked | Blocked by the same RevenueCat offering/package availability issue until subscription options load. |
| Photos import | pending |  |
| Files import | pending |  |
| On-device analysis | pending |  |
| Review flow | pending |  |
| Export render | pending |  |
| Save to Photos | pending |  |
| Launch Status card | pass | Patched Release app no longer exits when switching to Settings; user verified Settings opens on the physical iPhone after reinstall. Built app plist still resolves `HOOPS_CLOUD_LAUNCH_MODE=disabled` and empty cloud base URL. |
| Legal links open | pending |  |
| Accessibility normal mode | blocked | Use `ios/docs/checklists/release-accessibility-smoke-checklist.md`; blocked because the connected iPhone was unavailable to `devicectl` at 2026-04-27 10:58 PDT. |
| Accessibility VoiceOver | blocked | Verify labels/hints, progress announcements, selected/locked/kept/discarded states, sliders, share targets, and paywall states after the physical iPhone is online. |
| Accessibility largest text | blocked | Verify auth, paywall, settings, review, export, and share controls do not clip or become unreachable after the physical iPhone is online. |
| Accessibility Reduce Motion | blocked | Verify animated hero/backdrop are static and tab/option state changes still work without motion after the physical iPhone is online. |

## Blockers
- GitHub `production` environment secrets, legal-link variables, and Firebase auth key passed the `main` Release preflight on 2026-04-27.
- Local `LocalSecrets.xcconfig` has been materialized on this Mac and Release build settings validate without exposing secret values.
- Manual Release-device smoke remains pending for purchase/restore, import, on-device analysis, review, export, save, and legal links.
- Manual Release-device accessibility smoke remains pending until VoiceOver, largest text size, Reduce Motion, and normal mode are run on the physical iPhone.
- External crash-reporting client is not linked in this branch; launch telemetry currently relies on unified logs, with DSN config surfaced for future enablement.
