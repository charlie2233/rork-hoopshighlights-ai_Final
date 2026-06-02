# Phase Background Analysis Resume

## Goal

Make the "you can switch apps" copy honest and backed by real cloud state. Upload/import still needs to finish in HoopClips, but after the backend analysis job is started, the app persists the cloud job/source handoff and can reconnect on reopen.

## Changes

- `CloudAnalysisService` now exposes a cloud handoff callback after `/start` succeeds and before polling begins.
- `CloudAnalysisService.resumeAnalysisJob` can poll an existing backend analysis job by saved job ID and source object key.
- `HighlightsViewModel` persists the in-flight cloud analysis job to the current project as soon as the backend accepts the job.
- `ContentView` resumes polling the current project's in-flight cloud analysis job when the app becomes active with that project loaded.

## User Copy

- During upload, HoopClips tells users to keep the app open until cloud handoff.
- After handoff, HoopClips tells users they can switch apps and reopen HoopClips for real job status.
- AI Edit/render copy already tells users that cloud edits keep running and can be refreshed from real backend status.

## Architecture

Cloud still owns analysis, clip selection, edit planning, rendering, and storage. iOS only stores the backend job identifiers needed to reconnect status and results for the current project. No local analysis, local rendering, FFmpeg commands, full-video GPT upload, or fake status was added.

## Validation

- Passed: `git diff --check`
- Passed: `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO`

## Remaining Launch Notes

- This improves app-switch/reopen behavior for an accepted backend job. It does not guarantee background upload completion if the user leaves before upload or `/start` completes.
- Internal TestFlight still needs a physical-device smoke: import/upload, cloud analysis, Review, AI Edit render, preview, revision, share/open-in.
