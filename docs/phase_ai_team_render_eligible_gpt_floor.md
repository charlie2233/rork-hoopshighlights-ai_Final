# Phase AI Team Render Eligible GPT Floor

## Goal

Improve selected-team AI edit accuracy by separating review-only uncertain team clips from render-eligible selected-team clips when GPT plans the final highlight reel.

## Issue

Selected-team GPT payloads already included uncertain team-attribution clips so users can review them. However, the selection floor used by GPT counted every quality candidate, including review-only uncertain clips. That could pressure GPT to satisfy long-reel length requirements with clips that were intentionally not final-render eligible yet.

## Change

- `selectionQualityRules.availableQualityCandidateCount` still reports all reviewable quality clips.
- Added `reviewableQualityCandidateCount`.
- Added `renderEligibleQualityCandidateCount`.
- `minRecommendedKeptClipCount` and `minRecommendedKeptDurationSeconds` now use render-eligible clips for selected-team edits.
- GPT instructions now explicitly say not to satisfy final edit floors with review-only uncertain clips.

## Product Behavior

- Evidence-backed selected-team highlights remain eligible for final AI edits.
- Uncertain selected-team clips remain available for user Review.
- Confident opponent clips stay excluded.
- Blocks, steals, forced turnovers, and defensive stops still count as valid highlights when they are team-eligible and visually clear.

## Validation

- Added `test_selected_team_quality_floor_counts_render_eligible_not_review_only_uncertain`.
- Existing selected-team sampling tests continue to cover uncertain review reserves and `includeUncertain=false`.
- `git diff --check` passed.
- `ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker` passed: 78 tests.
- `ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests` passed: 137 tests.

## Launch Notes

This is a semantic accuracy improvement for GPT-led editing. It does not change iOS rendering, local analysis, local export, storage, or FFmpeg behavior.
