# Phase Launch202 - Audio Cue Confidence

## Goal

Improve highlight recall from loud crowd/audio pops without letting audio-only noise become an automatic highlight.

## Architecture

- Cloud/backend remains the owner of analysis, candidate scoring, GPT selection, edit planning, rendering, and storage.
- iOS remains a control and review surface only.
- Full videos are not sent to GPT. GPT receives sampled candidate keyframes and compact metadata only.
- Audio pops are treated as recall hints. They require visual evidence from sampled frames before GPT can claim an outcome.

## Changes

- Added `audio_reaction_salience_score` for valid crowd/audio-pop candidates.
- Included audio salience in backend ranking and duplicate moment selection after quality/context/outcome checks.
- Exposed `audioReactionSalienceScore` in GPT quality hints and Agent Template Cookbook candidate context.
- Added `audioReactionCandidates` to agent candidate quality summary.
- Kept weak audio-only filler at zero salience and outside render-quality eligibility.

## Tests

- `ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_sampling_reserves_unlabeled_loud_audio_pop_for_review services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_audio_reaction_detection_ignores_weak_audio_only_filler services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_audio_reaction_salience_prefers_valid_crowd_pop_duplicate`
  - Passed.
- `ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_marks_crowd_reaction_candidates_as_audio_recall_hints services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_revision_patch_payload_marks_audio_reaction_candidates_as_recall_hints`
  - Passed.
- `ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker`
  - Passed: 86 tests.
- `ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service`
  - Passed: 57 tests.
- `git diff --check`
  - Passed.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch202-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation build-for-testing`
  - Passed: `** TEST BUILD SUCCEEDED **`.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch202-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation build`
  - Passed: `** BUILD SUCCEEDED **`.

## Launch Notes

- This improves recall for moments where crowd noise marks an important play nearby.
- It does not claim that audio alone proves a highlight.
- GPT should still reject boring, unclear, duplicate, or outcome-less clips when sampled keyframes do not show real basketball action.
