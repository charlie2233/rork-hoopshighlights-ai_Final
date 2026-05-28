# Phase Clip85 Eval Team Evidence Quality

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Prevent HoopClips from claiming the selected-team 85% quality target when confident team ownership is only a confidence score. Confident selected-team predictions now need sampled-frame evidence refs in the launch evaluator.

## Change

- Added `selectedTeamEvidenceQuality` to `scripts/evaluate_team_highlight_accuracy.py`.
- Added default `0.85` threshold and CLI override `--min-selected-team-evidence`.
- Counted every confident selected-team prediction as evidence-scored.
- A confident selected-team prediction only passes evidence quality when it includes at least two unique `evidenceFrameRefs` and at least two unique `evidenceRoleGroups`.
- Added metrics:
  - `selectedTeamEvidenceClipCount`
  - `badSelectedTeamEvidenceCount`
- Added a regression test where one confident selected-team prediction has no evidence refs and the eval fails.
- Added a regression test where one confident selected-team prediction has two refs but only one role group and the eval fails.

## Architecture Guardrails

- The evaluator still reads metadata only; it does not inspect videos or call providers.
- Evidence refs are frame identifiers only, not images, storage keys, presigned URLs, or secrets.
- Uncertain review clips still count toward selected-team recall-with-review, but they do not count as confident selected-team evidence.

## Validation

Fresh local run on 2026-05-28:

```bash
python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/test_team_highlight_accuracy_eval.py
python3 -m unittest scripts.test_team_highlight_accuracy_eval -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
git diff --check
```

Results:

- `py_compile`: passed
- `scripts.test_team_highlight_accuracy_eval`: 14 passed
- scripts discovery suite: 58 passed
- `git diff --check`: passed

## Launch Recommendation

Internal launch evidence should now include `evidenceFrameRefs` and `evidenceRoleGroups` for confident selected-team clips exported from the cloud analysis quick scan. If a clip is plausible but evidence is weak or missing, keep it uncertain/reviewable instead of treating it as a confident selected-team match.
