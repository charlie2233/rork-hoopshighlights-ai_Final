# Phase Launch116 Export Simplicity, Status, and Visibility

## Goal

Make HoopClips easier to use during internal TestFlight prep without changing the cloud-first architecture:

- Keep cloud analysis, GPT editing, edit planning, rendering, and storage in the backend.
- Keep iOS as the upload/review/configure/status/preview/share control surface.
- Reduce Export friction so a tester can start an AI edit with sane defaults.
- Avoid presenting a cloud version timeout as a blocking failure when the render request can still use real job state.
- Keep visible labels short enough for smaller iPhones and larger text settings.

## Repo Audit Notes

- Branch created from `main` after `git pull --ff-only origin main`.
- Current main already removed the risky Photos `Data.self` fallback.
- Current Photos import uses file-backed transfer representations for `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`.
- Current import persistence copies the selected asset into the app project library before analysis/export.
- Current account-boundary handling resets the visible project on sign-out/account switch.
- Unrelated untracked root Xcode folders were left untouched:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`

## Changes

- Moved the AI Edit side-note box and `Make My Reel` action near the top of Export.
- Kept detailed plan, Pro, style, format, duration, timeline, locker, receipt, revision, preview, save, and share controls available.
- Changed non-blocking cloud status timeout copy from failure-like wording to "you can still start the edit" wording.
- Replaced the preview overlay filename with `Latest AI edit` so long generated filenames do not crowd the video preview.
- Allowed long filenames in the expanded preview sheet to wrap to two lines with scaling.

## Architecture Guardrails

- No local iOS analysis was added.
- No local iOS production rendering was added.
- No FFmpeg commands are generated in iOS.
- No Remotion or Canva runtime was added to iOS.
- No secrets, R2 credentials, or presigned URLs are logged or displayed.
- Status copy still refers to real cloud job/render state only.

## Validation

- `git diff --check`
  - Result: passed.
- Focused local iOS tests:
  - Command:
    `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch116-derived-data CODE_SIGNING_ALLOWED=NO test ...`
  - Covered import policy, AI Edit policy copy, real cloud-status wording, user prompt encoding, candidate reserve behavior, Pro template definitions, feature flag decode, work timeline/receipt decode, and cloud edit service injection.
  - Result: passed.
  - Result bundle: `/tmp/hoopclips-launch116-derived-data/Logs/Test/Test-HoopsClips-2026.05.31_15-07-56--0700.xcresult`
- iOS Debug simulator `build-for-testing`:
  - Command:
    `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch116-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing`
  - Result: passed.

## Remaining Launch Work

- Real-device/TestFlight smoke still needs a connected trusted iPhone.
- Cloud deploy/version smoke should be run sparingly because GitHub Actions budget is tight.
- Full staging path still needs installed-app proof: import, cloud analysis, Review, AI Edit render, preview, revision, revised preview, and share/open-in.
