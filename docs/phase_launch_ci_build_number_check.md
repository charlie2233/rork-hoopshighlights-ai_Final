# Phase: Launch CI Build Number Check

## Goal

Unblock the no-secret iOS staging codecheck without spending another blind GitHub Actions run. The latest failed iOS upload codecheck expected `CURRENT_PROJECT_VERSION=11`, while the app target is already build `14`.

## Change

- `ios/scripts/verify_internal_staging_config.sh` now expects `CURRENT_PROJECT_VERSION=14`.
- `scripts/submission_readiness_preflight.py` now uses `EXPECTED_IOS_BUILD_NUMBER=14`.
- The preflight app-project check now reads build-settings blocks for the real app bundle ID, instead of passing because a test target happens to contain the expected build number.

## Evidence

Read-only GitHub log inspection found:

```text
Expected CURRENT_PROJECT_VERSION=11, got 14
```

The current project has app Debug/Release build `14`; test targets still have build `7`, so the readiness preflight must not rely on raw substring matching across the whole project file.

## Validation

```bash
python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py
python3 -m unittest scripts.test_submission_readiness_preflight -v
bash ios/scripts/verify_internal_staging_config.sh
python3 scripts/submission_readiness_preflight.py --skip-live --json
python3 -m unittest discover scripts -v
PYTHONPATH=services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_team_scan_endpoint_uses_editing_secret_and_redacts_source_details -v
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build-for-testing
git diff --check
```

The first `build-for-testing` attempt was started while another Xcode build was still active and failed with a DerivedData `build.db` lock. The serial rerun passed.

This does not prove App Store/TestFlight upload readiness by itself. It only fixes a stale local/CI validation expectation.
