# Phase Export2: Version Timeout Resilience

## Goal

Reduce the Export/AI Edit blocker where the app reports a cloud editing version check timeout before users can start an edit.

## Changes

- Increased the iOS cloud edit version probe timeout from 6 seconds to 15 seconds for real mobile networks.
- Treated Cloudflare edge timeout codes (`http_520` through `http_525`, `http_530`, and `cloudflare_timeout`) as transient status-refresh failures.
- Kept transient version failures non-blocking: the app can still start the edit and then follows real edit job/render state.
- Kept real config/auth failures blocking: missing config, invalid responses, and non-transient backend errors still stop the action.
- Marked project-history persistence helpers as nonisolated so the large-video import persistence path can stay off the main actor without Swift 6 isolation warnings.
- Confirmed the crowd-pop audio cue feature is already present on current `main`: backend audio peaks/reaction cues feed clip metadata, GPT reranking context, and review UI evidence without sending full videos to GPT.

## Architecture

- iOS only checks cloud status and starts real cloud edit jobs.
- No iOS rendering, local edit planning, or fake backend status was added.
- The app does not claim the backend is healthy when the version check times out; it shows the cloud status as slow and allows the real edit request to prove current state.

## Validation

Local commands run:

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build-for-testing
git diff --check
PYTHONPATH=ios/backend uv run --with-requirements ios/backend/requirements.txt --with pytest python -m pytest ios/backend/tests/test_pipeline_quality.py -k "audio_reaction or crowd_pop or audio_cue"
uv run --with-requirements services/editing/requirements.txt --with pytest python -m pytest services/editing/tests/test_gpt_reranker.py -k "audio_reaction or crowd_pop or audio_cue"
```

Results:

- iOS Debug build: passed.
- iOS build-for-testing: passed.
- `git diff --check`: passed.
- Backend audio cue/crowd-pop selected tests: 12 passed, 56 deselected.
- GPT reranker audio cue/crowd-pop selected tests: 8 passed, 83 deselected.
- Only Xcode warning observed: metadata extraction skipped because no AppIntents framework dependency was found.

## Real-Device Follow-Up

On iPhone, open Export/AI Edit while staging is slow:

1. Confirm the status banner says cloud status is slow instead of config failed.
2. Confirm the primary button remains available for transient timeout cases.
3. Confirm actual edit creation/render still uses real backend job responses.
