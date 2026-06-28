# Background Upload App-Switch Handoff

Date: 2026-06-21

## Goal

Make HoopClips feel safe when a long cloud upload is running and the user switches apps.

## What changed

- When the app moves inactive/background during cloud analysis, `ContentView` now tells the view model.
- `HighlightsViewModel` records a sanitized background-upload proof event.
- If the current cloud stage is upload/pre-upload/resume, the visible status becomes: `Background upload still running. Safe to switch apps.`
- If upload has already handed off and cloud analysis is running, the visible status becomes: `Cloud analysis still running. Reopen HoopClips for live status.`
- The current project is persisted with that handoff status so returning to HoopClips can restore a calmer pipeline state.
- Upload handoff records `app_switch_handoff` in the upload progress proof summary without URLs, object keys, or local file paths.

## Files changed

- `ios/HoopsClips/HoopsClips/ContentView.swift`
- `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`

## Validation

Not run in this slice. This was a focused lifecycle/UX patch only.

## Remaining blockers

- Run simulator smoke for AI Analysis tap crash.
- Run real iPhone/TestFlight smoke with a long video and app switching during upload.
- Confirm Formspree/background-upload proof shows `app_switch_cloud_analysis_handoff`.
- Confirm the refreshed logo assets are included in the next TestFlight build.
- Production cloud cutover still needs release-owner/staging evidence signoff.
