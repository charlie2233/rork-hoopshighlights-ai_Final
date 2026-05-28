# Phase Clip84 Team Scan Evidence Refs

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Improve selected-team attribution precision by making GPT cite the sampled frames that support each clip ownership decision. High-confidence team ownership should only survive when GPT points back to actual clip keyframes supplied by the backend.

## Changes

- Added `evidenceFrameRefs` to the strict team quick-scan structured output schema for every clip attribution.
- Added prompt/context rules telling GPT that high-confidence ownership requires cited sampled frames from that clip.
- Added backend validation that checks `evidenceFrameRefs` against actual sampled frame refs for the same clip.
- If a clip attribution has no matching sampled-frame evidence, the backend caps confidence below the selected-team threshold so the clip remains uncertain/reviewable instead of becoming a confident match.
- Added tests proving:
  - schema requires `evidenceFrameRefs`
  - unsampled or missing evidence caps high confidence below `0.85`
  - matching sampled-frame evidence preserves high confidence

## Architecture Guardrails

- GPT still receives sampled frames only, never the full video.
- GPT does not generate FFmpeg commands, render instructions, URLs, storage keys, or local paths.
- The backend validates GPT output before selected-team filtering.
- Unproven high-confidence team decisions become uncertain, which keeps strong clips available for user Review.

## Validation

Fresh local run on 2026-05-28:

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m py_compile ios/backend/app/team_quick_scan.py ios/backend/tests/test_team_quick_scan.py
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
git diff --check
```

Results:

- `py_compile`: passed
- `ios.backend.tests.test_team_quick_scan`: 26 passed
- backend discovery suite: 168 passed
- scripts discovery suite: 57 passed
- `git diff --check`: passed

## Remaining Proof

- This tightens the GPT team scan proof path, but the 85% target still requires real labeled-footage eval.
- Internal launch still needs live staging proof, installed TestFlight smoke, and unblocked remote CI.
