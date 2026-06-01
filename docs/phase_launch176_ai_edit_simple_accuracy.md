# Phase Launch176 - AI Edit Simplicity and GPT Accuracy Hardening

## Goal

Keep HoopClips focused on internal TestFlight readiness by simplifying the AI Edit entry flow and tightening GPT-led highlight selection quality.

## Changes

- AI Edit first screen copy is shorter: the side note is clearly optional, options are labeled plainly, and the default accuracy guardrail text no longer sits in the main path before the primary action.
- AI Work Timeline is hidden before an edit starts. Detailed timeline rows are shown only when the backend returns a real `workTimeline`; the local fallback stays a simple current-state row after a job is in progress.
- My AI Edits / Cloud Locker is hidden on a brand-new export screen unless there is render history or an edit has started.
- GPT compact payload now includes `selectionQualityRules` with target duration, available quality candidates, minimum recommended kept clip count, and duration floor so long reels are not over-pruned to a few clips.
- GPT response validation now requires returned decision IDs to exactly match the sampled keyframe clip IDs in the initial pass and backfill pass.
- GPT candidate sampling now gives unique moments priority before using remaining budget on duplicates, reducing wasted vision budget on repeated plays.

## Architecture Safety

- iOS remains a control surface only: no local production analysis, rendering, composition, or export logic was added.
- GPT still receives only existing candidate clip IDs, compact metadata, and sampled keyframes.
- GPT still cannot generate FFmpeg commands, storage paths, URLs, or render instructions.
- Backend validators remain authoritative for selection, plan repair, policy, template, watermark/outro, and render safety.

## Validation

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_includes_long_reel_selection_floor_for_gpt -v
```

Result: passed, 1 test.

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_extra_unsampled_decision_falls_back_even_when_sampled_ids_complete -v
```

Result: passed, 1 test.

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_keeps_unique_moments_before_duplicate_fill -v
```

Result: passed, 1 test.

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
```

Result: passed, 71 tests.

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
```

Result: passed, 57 tests.

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/gpt_reranker.py
```

Result: passed.

```bash
git diff --check
```

Result: passed.

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug \
  -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build
```

Result: passed.

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug \
  -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build-for-testing
```

Result: passed.

## Launch Notes

- This branch improves AI Edit clarity and GPT selection robustness but does not replace the required real-device/TestFlight smoke.
- Real-device smoke still needs: import/upload, team scan, selected team or all teams, cloud analysis, Review, AI Edit render, preview, More Hype revision, revised preview, share/open-in.
- For accuracy proof, the next strongest step is a labeled clip bundle with selected-team offense/defense examples and measured keep/reject accuracy.
