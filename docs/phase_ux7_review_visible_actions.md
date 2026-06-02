# Phase UX7 Review Visible Actions

## Goal

Make the Review screen easier to trust on small phones and large Dynamic Type while keeping the cloud-first AI editing architecture intact.

## Architecture Guardrails

- Cloud backend still owns analysis, GPT clip selection, edit planning, rendering, and storage.
- iOS remains the review/control surface for checking clips, choosing what stays in the edit, opening Export, previewing, downloading, and sharing.
- No local iOS video analysis, rendering, FFmpeg command generation, storage credential handling, or presigned URL logging was added.
- Loud crowd/audio cues remain recall hints only. GPT and validators still need visible basketball evidence before a crowd pop can become a final highlight.

## Changes

- Renamed Review bulk actions:
  - `Keep Best` -> `Keep Strong`
  - `Skip Low` -> `Skip Weak`
- Made bulk action subtitles clearer:
  - selected-team mode now says how many target-team clips are affected
  - low-confidence cleanup now says the clips are safe to skip
- Increased adaptive grid width for bulk actions so labels have more room before wrapping.
- Added layout priority, minimum scaling, and larger fixed icon/touch targets to bulk Review actions.
- Rebuilt each clip card action bar with:
  - stable score-detail and slow-motion icon buttons
  - stable keep/skip capsule sizing
  - a vertical fallback when the horizontal action row cannot fit

## Validation Evidence

- `git diff --check` passed.
- iOS Debug simulator build:
  - Command: `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux7-dd CODE_SIGNING_ALLOWED=NO build`
  - Result: `** BUILD SUCCEEDED **`
- iOS Debug simulator build-for-testing:
  - Command: `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux7-dd CODE_SIGNING_ALLOWED=NO build-for-testing`
  - Result: `** TEST BUILD SUCCEEDED **`
- Observed existing App Intents metadata warning during both Xcode commands:
  - `Metadata extraction skipped. No AppIntents.framework dependency found.`
- No GitHub Actions run was triggered for this phase to conserve Actions budget.

## Launch Notes

- This pass improves Review usability, but it is not a TestFlight launch signoff.
- Internal launch still needs the real-device smoke: import/upload -> cloud analysis -> Review -> Export -> AI Edit render -> preview -> revision -> share/open-in.
- Keep the unrelated root `HoopsClips.xcodeproj/` and `HoopsHighlightsAI.xcodeproj/` folders untracked unless explicitly requested.
