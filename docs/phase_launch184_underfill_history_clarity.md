# Phase Launch184 Underfill Guard And History Clarity

Date: 2026-06-01
Branch: `codex/phase-launch184-underfill-history-clarity`

## Goal

Continue improving HoopClips toward internal TestFlight readiness by making AI edits less likely to underfill long reels and making History easier for non-technical users to understand on small phones.

## GPT Underfill Guard

`_backfill_underfilled_gpt_result()` already detects when GPT keeps too few clips for the requested reel length. Before this phase, if GPT had already sampled the full candidate pool and there were no remaining clips to backfill, the over-pruned GPT result could still stay applied.

New behavior:

- If GPT over-prunes a long/full-pool request and no backfill candidates remain, the backend falls back to the deterministic quality-ranked candidate pool.
- The fallback reason is `underfilled_gpt_result_no_backfill`.
- This keeps backend ownership intact: GPT still only reviews candidate clips and sampled keyframes, and rendering still uses deterministic validated edit plans.

## History Clarity

History project badges now use plain labels:

- Clip badge: `8 kept` instead of `8/22`.
- Export badge: `Saved reel` instead of `Export`.
- Accessibility still exposes the fuller clip count, for example `8 kept clips out of 22 total clips`.

This reduces cryptic UI for players, parents, and coaches reopening a project or finding a saved render.

## Validation Evidence

Completed locally on 2026-06-01:

```bash
python3 -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py
```

Result: passed.

```bash
uv run --no-project --with-requirements services/editing/requirements.txt python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_underfilled_gpt_result_uses_keyframe_only_backfill_pass services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_underfilled_gpt_result_falls_back_when_full_pool_was_sampled services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_long_target_duration_requires_deeper_gpt_backfill_floor
```

Result: passed, 3 tests.

```bash
uv run --no-project --with-requirements services/editing/requirements.txt python -m unittest services.editing.tests.test_gpt_reranker
```

Result: passed, 74 tests.

```bash
git diff --check
```

Result: passed.

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2 -derivedDataPath .codex-build/DerivedData -only-testing:HoopsClipsTests/HoopsClipsTests/testProjectHistoryBadgesUsePlainUserVisibleLabels test
```

Result: passed. Test result bundle: `.codex-build/DerivedData/Logs/Test/Test-HoopsClips-2026.06.01_03-39-48--0700.xcresult`.

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2 -derivedDataPath .codex-build/DerivedData build-for-testing
```

Result: passed.

## Remaining Launch Risk

- Real-device/TestFlight smoke is still required.
- Staging cloud edit timeout/version proof is still required.
- Labeled footage accuracy evidence is still required for selected-team highlights, uncertain review clips, blocks, steals, stops, and opponent rejection.
