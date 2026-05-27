# Phase Clip72: AI Edit Candidate Reserves and GPT Integrity

## Goal

Improve selected-team highlight quality by keeping defensive and uncertain review clips in the cloud AI Edit candidate pool before the iOS forty-clip upload cap, and make GPT rerank output fail closed when it does not make a complete, valid decision for every sampled candidate.

## Changes

- Updated iOS cloud-edit candidate ranking to reserve eligible block, steal, forced-turnover, defensive-stop, and `needsUserReview` clips before trimming to the upload cap.
- Added a regression test proving lower-scored defensive/review clips survive when made-shot candidates would otherwise fill the first forty slots.
- Updated GPT rerank validation so sampled candidates must have a complete valid decision set. Missing, duplicate, or contaminated decisions now fall back to deterministic server selection instead of applying a partial GPT subset.
- Updated reranker tests for incomplete decisions and unsampled existing-clip decisions to assert fallback behavior and empty GPT keep/reject receipts.

## Architecture Notes

- iOS still only uploads candidate metadata, exposes controls, and displays review/status/preview/share surfaces.
- Cloud remains responsible for analysis, GPT selection, edit planning, validation, rendering, and storage.
- This patch does not add local iOS rendering, composition, video analysis, Remotion, Canva, or FFmpeg behavior.
- GPT still cannot introduce exact timestamps, FFmpeg commands, storage keys, or unsampled clip IDs into the render path.
- Blocks, steals, forced turnovers, and uncertain selected-team clips remain eligible for user review even when lower scored than obvious scoring clips.

## Validation

Commands run from:

`/Users/hanfei/.config/superpowers/worktrees/rork-hoopshighlights-ai_Final/codex-phase-clip5-hybrid-recall-quality`

```bash
XcodeBuildMCP test_sim -only-testing:HoopsClipsTests
```

Result: passed. 74 tests passed, 0 failed, including `testCloudEditCandidateRankingReservesDefenseAndReviewClipsBeforeCap`.

```bash
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath /tmp/hoopclips-clip45-dd -quiet
```

Result: passed with exit code 0.

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover services/editing/tests -v
```

Result: passed. 93 tests passed, 0 failed, including `test_incomplete_gpt_decisions_fallback_without_dropping_sampled_candidates` and `test_unsampled_existing_clip_decision_falls_back_without_applying_gpt`.

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover ios/backend/tests -v
```

Result: passed. 160 tests passed, 0 failed.

```bash
npm --prefix services/control-plane run typecheck
```

Result: passed with exit code 0.

```bash
npm --prefix services/control-plane test
```

Result: passed. 28 tests passed, 0 failed.

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Result: passed. 53 tests passed, 0 failed.

```bash
npm --prefix services/control-plane run deploy:staging:dry-run
```

Result: passed with exit code 0. Wrangler validated the staging Worker bundle and bindings locally; no deploy was performed.

## Remaining Blockers

- Real labeled basketball footage is still required before claiming the 85% selected-team/highlight quality target.
- Wired-iPhone/TestFlight smoke is still required before Apple submission.
- PR CI still needs fresh post-push evidence; earlier runs failed before recording job steps.
