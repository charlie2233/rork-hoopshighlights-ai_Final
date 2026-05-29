# Phase Clip81 Selected-Team Uncertain Review Budget

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Improve selected-team highlight review recall after the team quick scan. When GPT/frame review is not confident enough to prove team ownership, HoopClips should still keep strong uncertain clips in the Review surface so the user can decide, especially for blocks, steals, and other defensive plays.

## Changes

- Raised the selected-team uncertain review reserve from about one-sixth of visible clips to about one-quarter.
- Kept small review lists conservative: lists under 6 clips still reserve 1 uncertain clip.
- Preserved the existing defensive reserve path, so blocks, steals, forced turnovers, and defensive stops still get dedicated room before normal scoring clips fill the list.
- Added a regression test proving an 8-clip selected-team review can keep 3 strong uncertain clips while dropping weaker uncertain and lower-priority matched scoring clips.

## Architecture Guardrails

- This is cloud backend review policy only.
- iOS still only displays team options, status, clips, previews, and controls.
- No local video analysis, rendering, composition, or export was added.
- No full videos are sent to GPT by this change.
- Existing deterministic validators and downstream EditPlan/render paths remain unchanged.

## Validation

Completed locally:

```bash
python3 -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
git diff --check
```

Results:

- Python compile passed for the touched backend/test modules.
- Focused pipeline quality tests passed: 41 tests.
- iOS backend discovery passed: 166 tests.
- Scripts discovery passed: 57 tests.
- `git diff --check` passed.

Remote CI after push to `e350ff2`:

- Cloud Edit Deploy Preflight: run `26559820561`, failed before useful job logs were available (`log not found` for failed job `78239827963`).
- iOS Internal TestFlight Upload: run `26559820578`, failed before useful job logs were available (`log not found` for failed job `78239827903`).
- PR #32 remained `UNSTABLE` from those remote checks.

## Remaining Proof

- The 85% accuracy target still requires real labeled-footage evaluation, not just unit tests.
- Internal TestFlight launch readiness still needs a post-install smoke on a real install.
- GitHub Actions remain provider-blocked if the account billing/spending-limit issue is still active; the latest failed jobs did not produce logs, so no code-level CI failure was available to debug from this push.
