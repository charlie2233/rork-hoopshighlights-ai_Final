# Phase Launch174 - Team-Aware GPT Accuracy

## Goal

Improve selected-team highlight quality without changing the cloud-first architecture.

Cloud still owns candidate analysis, GPT keyframe review, edit planning, rendering, and storage. iOS remains the control surface for choosing All teams or a detected jersey-color team, reviewing clips, requesting AI Edit, previewing, sharing, and downloading.

## Change

- GPT sampling now prioritizes evidence-backed selected-team render candidates when a user chooses one team.
- Uncertain team-attribution clips still go to GPT as review-only candidates when allowed, but they no longer consume too much of the selected-team frame budget before evidence-backed clips.
- Blocks, steals, forced turnovers, and defensive stops are still preserved as valid highlight candidates.
- Underfilled GPT backfill now prefers evidence-backed selected-team clips over user-kept uncertain clips.
- GPT payloads now include explicit `teamTargetingRules` so the model sees the contract:
  - selected-team final edit uses selected-team clips only
  - confident opponent clips are excluded before GPT
  - uncertain team clips are review-only unless the user kept them
  - evidence-backed selected-team clips are preferred
  - blocks, steals, forced turnovers, and stops count as highlights

## Safety

- GPT still receives only compact candidate metadata and sampled keyframes.
- No full video is sent to GPT.
- GPT cannot output FFmpeg commands, file paths, source URLs, storage keys, or presigned URLs.
- Team confidence thresholds and evidence requirements were not loosened.
- Confident opponent clips remain excluded from selected-team GPT review.

## Validation

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_includes_team_targeting_and_excludes_confident_opponent_clips \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_selected_team_sampling_prioritizes_evidence_backed_matches_over_uncertain_defense \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_selected_team_backfill_prefers_matched_clips_over_user_kept_uncertain -v
```

Result: passed, 3 tests.

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
```

Result: passed, 67 tests.

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
```

Result: passed, 57 tests.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest \
  ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_agent_editing_context_includes_team_targeting_and_attribution \
  ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_agent_editing_context_marks_uncertain_team_clips_as_manual_review_only \
  ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_agent_decision_guidance_constrains_gpt_selection_and_review_semantics -v
```

Result: passed, 3 tests.

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/gpt_reranker.py
git diff --check
```

Result: passed.

## Launch Note

This improves accuracy for the current internal beta path, but submission readiness still needs a real-device TestFlight smoke with upload/import, team scan, cloud analysis, Review, AI Edit render, preview, revision, share/open-in, and a small labeled footage accuracy proof.
