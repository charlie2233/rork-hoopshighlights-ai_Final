# Phase Clip87 Team Evidence Role Groups

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Make selected-team evidence auditable beyond raw frame IDs. Runtime already requires confident ownership to cite frames from different play phases; the exported metadata and launch evaluator should prove that same standard.

## Change

- Added `evidenceRoleGroups` to backend `ClipTeamAttribution`.
- Runtime quick scan now records validated role groups such as `setup`, `action`, and `outcome` from cited frame refs.
- Control-plane preserves bounded `evidenceRoleGroups` metadata.
- The selected-team launch evaluator now requires both:
  - at least two unique `evidenceFrameRefs`
  - at least two unique `evidenceRoleGroups`
- Added evaluator coverage for the failure case where two refs exist but both are from one phase.

## Guardrails

- Role groups are small metadata strings only; they do not include images, URLs, storage keys, or secrets.
- GPT still never sends full videos or renderer commands.
- Weak evidence remains reviewable as uncertain rather than being treated as a confident selected-team match.

## Validation

- `PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m py_compile ios/backend/app/models.py ios/backend/app/team_quick_scan.py ios/backend/tests/test_team_quick_scan.py` passed.
- `python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/test_team_highlight_accuracy_eval.py scripts/test_build_team_highlight_eval_payload.py` passed.
- `PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan -v` passed: 28 tests.
- `python3 -m unittest scripts.test_team_highlight_accuracy_eval scripts.test_build_team_highlight_eval_payload -v` passed: 18 tests.
- `PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v` passed: 170 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 59 tests.
- `cd services/control-plane && npm run typecheck` passed.
- `git diff --check` passed.

## Remaining Proof

This improves metadata and evaluator strictness, but it is not the real-footage 85% proof. Internal launch still needs labeled footage that includes selected-team makes, misses, blocks, steals, forced turnovers, uncertain review clips, opponent highlights, and bad-window negatives.
