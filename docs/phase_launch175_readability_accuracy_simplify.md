# Phase Launch175 - Readability, Simplicity, and GPT Accuracy

## Goal

Move HoopClips closer to internal TestFlight readiness by improving small-phone readability, reducing hidden text risk, and making long GPT-led edits less likely to pass with too few clips.

## Changes

- Shared section headers now wrap title and subtitle text instead of squeezing on small phones or accessibility Dynamic Type sizes.
- Empty state titles and messages now have explicit wrapping and scaling rules.
- Settings tag rows now use a wrapping flow layout, so privacy/storage/about tags and the "Created by atrak.dev with love" credit stay visible on narrow screens.
- Long GPT target durations now require a deeper minimum kept-clip floor before the result is considered acceptable. If GPT keeps too few clips for a long reel, the backend backfill path has a stronger reason to sample more candidates instead of returning a thin edit.

## Architecture Safety

- iOS remains a control surface only; no video analysis, production rendering, or composition was added to iOS.
- GPT still works only on candidate clips and sampled keyframes through the backend.
- No full videos, storage keys, presigned URLs, or FFmpeg commands are exposed to GPT.
- The change does not loosen team attribution, selected-team filtering, or render validation.

## Validation

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_long_target_duration_requires_deeper_gpt_backfill_floor -v
```

Result: passed, 1 test.

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
```

Result: passed, 68 tests.

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/gpt_reranker.py
```

Result: passed.

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build
```

Result: passed. The Build iOS Apps plugin session check failed because the plugin transport closed, so this used local `xcodebuild`.

```bash
git diff --check
```

Result: passed.

## Launch Note

This is incremental readiness work. Full submission readiness still needs real-device/TestFlight smoke across import, team scan, cloud analysis, Review, AI Edit render, preview, revision, share/open-in, and labeled clip accuracy review.
