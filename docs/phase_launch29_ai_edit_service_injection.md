# Phase Launch29 AI Edit Service Injection

Date: 2026-05-29
Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Make the iOS AI Edit control surface easier to verify without changing the cloud-first product architecture.

## Change

- Added `CloudEditServicing` as the client-side protocol for the cloud edit API calls used by `AIEditView`.
- Made the production `CloudEditService` conform to that protocol.
- Added initializer injection to `AIEditView`, with the real `CloudEditService()` as the default.
- Added focused tests proving the production service conforms and the view can be created with an injected service.
- Added AI Edit telemetry failure-reason redaction for URL-shaped values, storage object keys, and signed query values before unified logging.

This does not add on-device analysis, edit planning, rendering, composition, or export. It does not add Remotion/Canva to iOS. The injected service boundary is only for testability and future deterministic UI smoke harnesses; production still sends requests to the cloud backend and uses real render/download state.

## Validation

Commands run:

```bash
xcodebuild test \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -only-testing:HoopsClipsTests/CloudEditServiceTests \
  -only-testing:HoopsClipsTests/LaunchTelemetryTests \
  CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation

# Result: passed. 12 focused test cases passed.
# xcresult:
# /Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClips-dbjgwzgujbxeswbuapfjrdblbgqm/Logs/Test/Test-HoopsClips-2026.05.29_13-46-35--0700.xcresult

xcodebuild build-for-testing \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation

# Result: passed.

git diff --check

# Result: passed.

python3 scripts/launch_backend_config_preflight.py --json

# Result: passed with 79 pass, 12 warn, 0 fail.
```

`python3 -m pytest -q scripts services/editing/tests ios/backend/tests` was attempted, but the local Python 3.14 environment did not have `pytest` installed. Focused iOS tests, build-for-testing, diff whitespace, and the launch backend config preflight all passed with the existing local toolchain.

## Launch Notes

This reduces iOS smoke-test coupling but does not clear the external launch gates. Internal TestFlight launch still needs provider credentials, staging deploy/version proof, an available wired iPhone, installed TestFlight smoke, and launch-grade labeled team/highlight accuracy evidence.
