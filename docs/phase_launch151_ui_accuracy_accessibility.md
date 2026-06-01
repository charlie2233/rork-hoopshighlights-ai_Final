# Phase Launch151 UI Accuracy Accessibility

## Goal

Make the internal beta app simpler and more accurate without changing the cloud-first architecture. This phase targets the AI Edit screen copy, dynamic-type text wrapping, and GPT-side edit intent guardrails for defensive highlights.

## Changes

- Changed the visible plan copy in AI Edit from `video edits/day` to `AI edits/day`, matching the Free policy of `3 AI edits/day`.
- Updated the cloud edit prompt guardrails so GPT treats blocks, steals, and defensive stops as valid highlights even when they do not end in a made basket.
- Kept the prompt compact enough to preserve user notes such as `Make this a 4:30 team reel` while still attaching team and accuracy guardrails.
- Added extra wrapping and scale protection to AI Edit status and plan-limit text so labels stay visible on smaller phones and accessibility Dynamic Type sizes.

## Architecture

- Cloud still owns analysis, GPT selection, edit planning, rendering, and storage.
- iOS remains the control surface for setup, status, preview, save, and share.
- No local iOS rendering, composition, or production analysis was added.
- GPT still receives only compact request context and existing candidate clips/keyframes through the backend path.

## Validation

```sh
git diff --check
```

- Passed.

```sh
XcodeBuildMCP test_sim -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditPolicySummaryExposesFreemiumCopy -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultPromptAddsAccuracyGuidanceWhenUserLeavesNoteEmpty -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultPromptCarriesSelectedTeamFocus -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderPreservesUserInstruction -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderKeepsTeamGuardrailsWithTypedNote
```

- Passed with no failures.

```sh
XcodeBuildMCP build_sim
```

- Passed with no warnings.

```sh
XcodeBuildMCP test_sim -only-testing:HoopsClipsTests
```

- Passed: 121 tests, 0 failures.
- The first broad run found two tests that depended on leaked persisted team-selection state. The tests now explicitly set `.allTeams`, then the focused retry and full target passed.

## Launch Notes

- This is a low-risk launch polish change. It improves wording, accessibility resilience, and GPT edit intent quality.
- A real-device TestFlight smoke is still required before App Store submission.
