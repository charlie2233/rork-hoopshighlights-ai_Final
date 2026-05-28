# Phase Clip91 Eval Team Evidence Summary

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Make the 85% selected-team quality proof score the same evidence contract used by the cloud/GPT path. `teamEvidence` is now the compact summary that tells GPT and the backend whether jersey-color ownership is evidence-backed, weak, or missing; the real-footage eval must not ignore that status.

## Change

- `scripts/build_team_highlight_eval_payload.py` now preserves `teamEvidence` from cloud analysis clips in evaluator-ready predictions.
- `scripts/evaluate_team_highlight_accuracy.py` now reads:
  - `teamEvidence.status`
  - `teamEvidence.evidenceBacked`
  - `teamEvidence.frameRefCount`
  - `teamEvidence.roleGroupCount`
- Confident selected-team predictions now fail evidence quality when `teamEvidence` is `weak_evidence`, missing-backed, explicitly `evidenceBacked=false`, or reports too few frame refs/role groups.
- The evaluator still requires actual `teamAttribution.evidenceFrameRefs` and `teamAttribution.evidenceRoleGroups`; a summary alone cannot prove the 85% target.

## Guardrails

- This remains metadata-only evaluation. It does not inspect videos, send full videos to GPT, call providers, render, or expose storage URLs.
- Weak/uncertain selected-team clips can still count for user-review recall, but they do not count as confident selected-team ownership proof.

## Validation

- `python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/build_team_highlight_eval_payload.py scripts/test_team_highlight_accuracy_eval.py scripts/test_build_team_highlight_eval_payload.py` passed.
- `python3 -m unittest scripts.test_team_highlight_accuracy_eval scripts.test_build_team_highlight_eval_payload -v` passed: 19 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 62 tests after the follow-up sample-size gate.
- `git diff --check` passed.

## Remaining Proof

This closes an evaluator mismatch, but it still does not prove the real 85% target. Internal launch still needs a real labeled-footage eval set with selected-team makes, misses, blocks, steals, forced turnovers, uncertain review clips, opponent highlights, and bad-window negatives.
