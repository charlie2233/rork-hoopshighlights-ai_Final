# Phase Clip2 - Candidate Recall Accuracy

Date: 2026-06-01
Branch: `codex/phase-clip2-candidate-recall-accuracy`

## Goal

Improve GPT-led highlight accuracy for selected-team edits by sending the right candidate pool to GPT:

- Keep confident selected-team render candidates.
- Keep more uncertain selected-team clips for review when uncertainty is enabled.
- Exclude uncertain clips when the user chooses confident-only team targeting.
- Preserve defensive highlights like blocks, steals, forced turnovers, and defensive stops.

## Findings

- The backend already supports high-recall candidate pools up to 320 clips.
- GPT reranker defaults are already high for this phase: 320 candidates and up to 10 keyframes per clip.
- Team quick scan already uses GPT and rich clip/frame sampling when enabled.
- A selected-team sampler bug remained: when the quality-eligible pool was smaller than the max candidate count, the sampler returned early before applying selected-team filtering.

## Changes

- Selected-team GPT sampling now applies team filtering before the small-pool early return.
- `includeUncertain=false` now prevents uncertain selected-team clips from being sampled for GPT.
- `includeUncertain=true` reserves up to one third of the selected-team GPT sample for uncertain review candidates, instead of one fourth.
- Final selected-team sample ordering now boosts defensive candidates so blocks/steals/stops are less likely to be buried.

## Architecture

- No full videos are sent to GPT.
- GPT still only sees candidate clips and sampled keyframes.
- GPT still cannot generate FFmpeg or renderer commands.
- Backend validators and deterministic EditPlan/render execution remain authoritative.
- iOS behavior was not changed in this branch.

## Evidence

Commands run:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_selected_team_sampling_reserves_more_uncertain_review_candidates \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_selected_team_sampling_respects_include_uncertain_false -v
```

Result: `Ran 2 tests in 0.008s` and `OK`.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_includes_team_targeting_and_excludes_confident_opponent_clips \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_adds_team_defense_context_for_selected_team_candidates \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_selected_team_sampling_reserves_more_uncertain_review_candidates \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_selected_team_sampling_respects_include_uncertain_false \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_disabled_gpt_fallback_preserves_uncertain_team_review_ids \
  ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_selected_team_filter_keeps_matching_and_uncertain_clips_for_review \
  ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_keeps_selected_and_uncertain_team_steals \
  ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_does_not_render_unreviewed_uncertain_team_clip -v
```

Result: `Ran 8 tests in 0.057s` and `OK`.

```bash
git diff --check
```

Result: passed.

## Remaining Blockers

- This improves candidate routing; it does not prove the requested 85% accuracy target by itself.
- Accuracy still needs a labeled real-footage bundle and a repeatable evaluation report.
- Real-device TestFlight smoke is still required before internal launch/submission.
