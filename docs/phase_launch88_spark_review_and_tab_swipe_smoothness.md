# Phase Launch88: Spark Review Triage and Tab Swipe Smoothness

Date: 2026-05-30
Branch: `codex/phase-launch70-editing-analysis-progress`

## Scope

- Triage `/Users/hanfei/Desktop/HoopClips-Review-Notes-2026-05-30_full.txt` as advisory input only.
- Preserve cloud-first launch rules. No iOS video analysis, rendering, or export behavior was added.
- Improve the main horizontal tab transition without changing app routing or backend behavior.

## Spark Review Triage

The review note reported five possible issues. Current checkout verification:

1. `VideoPlayerView.swift` import filename interpolation is fixed in this branch.
   - Current code uses `imported_video_\(UUID().uuidString).\(fileExtension)`.
2. Photos import is file-backed only for the supported video types inspected here.
   - `ImportedVideoFile` has `FileRepresentation` entries for `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`.
   - No `Data.self` fallback was found in `VideoPlayerView.swift`.
3. Import error state updates from the Photos flow are MainActor-gated.
   - Error assignments inside the file-backed import closure use `await MainActor.run`.
   - `VideoAnalysisService` remains `@MainActor`, so `await viewModel.loadVideo(...)` crosses to the actor safely.
4. The CloudEditService rerender payload failure from the note does not reproduce on this branch.
   - Focused simulator test suite passed for `HoopsClipsTests/CloudEditServiceTests`.
5. The minor ContentView indentation note was stale on the current file.

## UX Change

The previous main tab setup applied an animation directly to the page `TabView` whenever `selectedTab` changed. That can fight the native interactive page swipe because child pages and the selected tab state are both being animated at the same level.

Changed behavior:

- Removed the global `.animation(..., value: selectedTab)` from the page `TabView`.
- Kept explicit button-tap page animation through `selectTab(_:)`.
- Added a `matchedGeometryEffect` selected-state pill in the bottom tab bar.
- Added a separate, tighter tab selection spring so the bottom indicator glides smoothly during taps and horizontal swipes.
- Preserved Reduce Motion behavior.

## Validation

Commands run:

```bash
git fetch --prune origin
git status --short --branch
rg -n "imported_video_|Data\\.self|FileRepresentation|beginVideoImport|importVideo\\(" ios/HoopsClips/HoopsClips/Views/VideoPlayerView.swift
rg -n "testLockerRerenderUsesRevisionEndpointForRevisionRows|testLockerRerenderUsesStoredEditEndpointForBaseRows|installId|forceNew|idempotencyKey|rerender" ios/HoopsClipsTests/CloudEditServiceTests.swift ios/HoopsClips/HoopsClips/Services/CloudEditService.swift
```

XcodeBuildMCP:

```text
test_sim -only-testing:HoopsClipsTests/CloudEditServiceTests
build_sim
```

Results:

- `CloudEditServiceTests`: passed, 11 tests, 0 failures.
- iOS Debug simulator build: passed.
- `git diff --check`: passed.

Local preflight before commit:

- `scripts/submission_readiness_preflight.py --archive-path ios/archives/HoopsClips-Launch72.xcarchive --json`
- Result: `27 pass / 7 fail / 0 warn`
- One failure was expected while this working tree had tracked edits.

## Remaining Blockers

The same launch blockers remain after this local UX/triage pass:

- Launch-grade labeled footage accuracy report is still missing, so the 85% selected-team/highlight quality gate is unproven.
- Connected iPhone is still detected but unavailable for install/smoke testing.
- Main-branch Cloud Edit Deploy Preflight and iOS Internal TestFlight Upload runs are stale relative to the current checkout.
- Secret-gated deploy preflight is stale relative to the current checkout.
- Installed TestFlight post-install smoke remains unproven.

No GitHub Actions were triggered for this phase to conserve Actions budget.
