# Phase UX20: Simple Visible Export Accuracy

## Goal

Improve the AI Edit control surface and highlight accuracy without moving analysis or rendering into iOS.

## Architecture

- Cloud/backend remains responsible for candidate generation, audio reaction detection, GPT selection, edit planning, and rendering.
- iOS only shows shorter prompts, status, previews, and sends structured edit notes to the cloud.
- Loud crowd pops, bench reactions, cheers, and audio spikes are recall hints. They are not proof of a highlight by themselves.
- GPT must keep audio-reaction candidates only when sampled frames show real basketball action and a visible outcome.

## Changes

- Shortened AI Edit quick prompts so button/text content is more visible on small phones.
- Shortened default focus summaries while preserving team targeting, blocks, steals, stops, and crowd-pop guidance.
- Added structured `audio_reaction` user intent for prompts like "crowd pops", "bench reactions", and "loud cheers".
- Extended backend audio-reaction label recognition for `Loud Cheer`, `Bench Reaction`, and `Crowd Roar`.
- Updated GPT selection rules to treat requested audio reactions as nearby timing clues, while requiring visual confirmation.
- Added focused tests for backend audio-reaction reservation, GPT audio-reaction intent, and iOS prompt copy.

## Sound Recognition Behavior

The existing cloud pipeline extracts an audio profile with FFmpeg, detects spike/cluster/swell reaction cues, builds recall windows around those moments, and reserves strong audio-reaction candidates for review/GPT sampling.

This phase improves the language and label bridge:

- User note: "Use loud crowd pops" becomes structured `audio_reaction` intent.
- Provider/backend labels like `Loud Cheer`, `Bench Reaction`, and `Crowd Roar` are treated as audio-reaction hints.
- GPT receives `audioReactionFocusRequested` and the audio cue metadata.
- Validators and prompt rules still require visible basketball action/outcome before final keep/render.

## Validation

Commands run locally:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest \
  ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_review_trim_reserves_unlabeled_loud_crowd_pop_candidate \
  ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_review_trim_reserves_super_loud_crowd_pop_with_modest_action_context \
  ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_audio_reaction_boundaries_detect_loud_local_crowd_pops \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_marks_crowd_pop_focus_as_structured_audio_reaction_intent \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_detects_loud_cheer_and_bench_reaction_labels_as_recall_hints \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_sampling_reserves_unlabeled_loud_audio_pop_for_review -v
```

Result: `Ran 6 tests in 0.024s OK`.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest \
  ios.backend.tests.test_pipeline_quality \
  services.editing.tests.test_gpt_reranker -v
```

Result: `Ran 179 tests in 6.612s OK`.

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 16e' \
  -derivedDataPath /tmp/hoopclips-ux20-dd CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation -skipMacroValidation \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testAIEditPromptCopyStaysShortVisibleAndPlain \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultPromptAddsAccuracyGuidanceWhenUserLeavesNoteEmpty \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultPromptCarriesSelectedTeamFocus \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultPromptRespectsConfidentTeamOnlySelection \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultFocusSummaryShowsAllTeamsTarget \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultFocusSummaryStaysCompactForLongTeamNames \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderPreservesUserInstruction \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderKeepsTeamGuardrailsWithTypedNote \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderPreservesGuardrailsForLongUserNote
```

Result: `TEST SUCCEEDED`.

```bash
git diff --check
```

Result: clean.

```bash
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 16e' \
  -derivedDataPath /tmp/hoopclips-ux20-dd CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation -skipMacroValidation
```

Result: `TEST BUILD SUCCEEDED`.

## Launch Notes

- No GitHub Actions were manually triggered in this phase.
- The branch should be committed with `[skip ci]` to protect Actions budget.
- This is not a full TestFlight launch sign-off. Real-device end-to-end smoke still needs install, upload/import, cloud analysis, AI Edit render, preview, revision, and share/open-in evidence.
