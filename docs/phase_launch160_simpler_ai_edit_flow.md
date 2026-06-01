# Phase Launch160 - Simpler AI Edit Flow

## Goal

Make Export AI Edit easier to use on phones by putting the user's editing intent before the primary render action and reducing small-screen text squeeze.

## Architecture Guardrails

- iOS remains the control surface for choosing edit intent, template shape, status, preview, save, and share.
- Cloud remains responsible for GPT clip selection, edit planning, rendering, revisions, and storage.
- No local video analysis, rendering, composition, FFmpeg command generation, or fake backend state was added.

## Changes

- Moved the side-note prompt above the Make My Reel action so users can tell HoopClips what they want before starting the cloud job.
- Kept style, shape, and length choices collapsed behind Smart setup.
- Moved plan/Pro detail cards below the main create/status/preview path so the render workflow reads top-to-bottom.
- Made the side-note header adaptive for accessibility Dynamic Type: the title and character count stack vertically instead of crowding each other.
- Updated hero copy to say: "Add a side note or quick focus, then tap Make My Reel."

## Validation

- Passed `git diff --check`.
- Passed focused iOS Debug simulator test coverage:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch160-derived-data test -only-testing:HoopsClipsTests/CloudEditServiceTests CODE_SIGNING_ALLOWED=NO -quiet`
  - 11 CloudEditServiceTests passed, including AIEditView service injection.
- Passed iOS build-for-testing:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch160-derived-data build-for-testing CODE_SIGNING_ALLOWED=NO -quiet`
- Existing Swift warnings remain around `CloudAnalysisService` progress awaits and `VideoExportService` Sendable captures. They were not introduced by this branch.
