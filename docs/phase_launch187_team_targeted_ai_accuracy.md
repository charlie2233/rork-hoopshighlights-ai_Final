# Phase Launch187 - Team Targeted AI Accuracy

Date: 2026-06-01
Branch: codex/phase-launch187-team-targeted-ai-accuracy

## Goal

Tighten the app and backend path that lets a user pick a team, keep blocks and steals as valid highlights, and give GPT/editor prompts clearer evidence about what the selected-team candidate pool contains.

This phase is intentionally focused on app behavior and AI accuracy. It does not change the logo or local iOS rendering.

## Changes

- Normalized blank or missing `TeamOption.source` and `ClipTeamAttribution.source` values to `unknown`.
- Treated blank/unknown/provider team sources as requiring real frame or role evidence before a selected-team clip can become render eligible.
- Added selected-team candidate counters to GPT compact selection rules:
  - selected-team render candidates
  - evidence-backed selected-team candidates
  - selected-team defensive candidates
  - uncertain review-only candidates
- Added regression coverage for blank-source team attribution so it cannot silently become trusted.
- Added a checked-in synthetic CLI accuracy fixture covering:
  - selected dark team highlights
  - blocks
  - steals
  - confident opponent highlight rejection
  - bad-window negative rejection
  - all-teams mode
  - made and missed shot outcome evidence

## Architecture

- Cloud remains the owner for analysis, GPT clip selection, edit planning, rendering, and storage.
- iOS remains the control surface for upload, team choice, review, export controls, preview, download, and share.
- GPT still receives compact candidate/keyframe context only. No full videos, presigned URLs, storage credentials, or FFmpeg commands are introduced.

## Evidence

Read-only agent review found the current GPT path is already candidate-only and keyframe/source-frame based, with no full-video handoff to GPT. The main accuracy gap was selected-team evidence handling and measurable fixture coverage.

Validation commands run:

```bash
python3 -m unittest scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_cli_fixture_covers_selected_team_blocks_steals_and_all_teams -v
```

Result: passed, 1 test.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_includes_team_targeting_and_excludes_confident_opponent_clips -v
```

Result: passed, 1 test.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_selected_team_unknown_and_provider_sources_need_evidence -v
```

Result: passed, 1 test.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_analysis_team_status_requires_evidence_for_unknown_and_provider_sources -v
```

Result: passed, 1 test.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
```

Result: passed, 74 tests.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent ios.backend.tests.test_pipeline_quality -v
```

Result: passed, 156 tests.

```bash
python3 -m unittest scripts.test_team_highlight_accuracy_eval scripts.test_build_team_highlight_eval_payload scripts.test_build_launch_team_accuracy_report scripts.test_prepare_team_highlight_labeling_bundle scripts.test_worker_team_scan_smoke scripts.test_accuracy_cli_entrypoints -v
```

Result: passed, 47 tests.

## Launch Notes

This improves guardrails and test coverage, but it does not prove the 85 percent real-world target yet. The remaining accuracy blocker is a completed real labeled footage bundle with enough multi-angle clips and selected-team/all-teams labels to run the launch accuracy report.

Recommended next steps:

- Finish real clip labeling for selected team, all teams, blocks, steals, makes, misses, bad windows, and uncertain review cases.
- Run the launch team accuracy report against the completed real-label manifest.
- Use any failures to tune candidate pool recall, keyframe sampling, GPT rules, and EditPlan validation.
