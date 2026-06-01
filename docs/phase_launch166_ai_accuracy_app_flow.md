# Phase Launch166: AI Accuracy And App Flow

## Goal

Move focus back to launch-critical app behavior and AI highlight quality, not logo polish. This phase improves the candidate supply reaching cloud analysis/GPT and makes staging deploy checks harder to accidentally weaken.

## Changes

- Increased the cloud analysis pre-trim candidate pool cap from `640` to `1280` clips. The iOS app still only sends user intent and displays review/export state; cloud owns analysis and trimming.
- Kept the returned/review/GPT caps controlled by existing policy (`HOOPS_MAX_RETURNED_CLIPS=320`, GPT candidate caps `320`) so the UI does not become a giant raw-candidate dump.
- Fixed the GitHub deploy workflow to pass `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE=320` and `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO=320`, matching `cloudbuild.yaml`, docs, and the launch preflight contract.
- Added a static launch-preflight guard so the workflow fails if it regresses to the older `220` GPT candidate cap.
- Raised the iOS cloud-edit version status timeout from 15s to 30s. A version-status timeout still does not block editing; the app uses the real render response as the source of truth.

## Architecture Guardrails

- No iOS local video analysis, rendering, composition, or export was added.
- No full video is sent to GPT.
- GPT candidate limits still use structured-output JSON and backend validators.
- No secrets, R2 credentials, or presigned URLs are logged or documented.
- The app status copy remains tied to real cloud job/timeline state.

## Validation Evidence

Ran locally on branch `codex/phase-launch166-ai-accuracy-app-flow`:

```bash
git diff --check
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v
python3 -m unittest scripts.test_launch_backend_config_preflight -v
python3 scripts/launch_backend_config_preflight.py
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch166-derived-data build-for-testing CODE_SIGNING_ALLOWED=NO -quiet
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch166-derived-data test -only-testing:HoopsClipsTests CODE_SIGNING_ALLOWED=NO -quiet
```

Results:

- `git diff --check`: pass.
- `ios/backend/tests`: 214 tests passed.
- `services/editing/tests`: 123 tests passed.
- `scripts.test_launch_backend_config_preflight`: 7 tests passed.
- `scripts/launch_backend_config_preflight.py`: `pass=84 warn=12 fail=0`.
- iOS Debug `build-for-testing`: exit 0.
- iOS `HoopsClipsTests`: exit 0.

## Remaining Blockers

- Real-footage 85% selected-team/highlight accuracy still needs a launch-grade labeled report.
- A current `.xcarchive`/`.ipa` and installed TestFlight smoke are still required before App Store/TestFlight submission.
- Live deploy verification should be run deliberately because GitHub Actions budget is constrained.
