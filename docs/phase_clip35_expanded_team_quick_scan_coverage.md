# Phase Clip35: Expanded Team Quick Scan Coverage

## Goal

Improve selected-team highlight accuracy after the expanded recall pool by making GPT team attribution cover the same larger candidate pool instead of stopping at the first 40 candidates.

## Change

- Added `HOOPS_TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS`; Phase Clip63 raises the quality-beta default to `160`, clamped to `1..160`.
- Added `HOOPS_TEAM_QUICK_SCAN_MAX_OUTPUT_TOKENS`, default `6000`, clamped to `512..12000`.
- The team quick-scan payload now includes candidate metadata only up to the configured candidate cap.
- The sampled frame extraction loop now samples clip frames up to the same configured candidate cap.
- The strict Structured Output schema sets `clipAttributions.maxItems` to the same configured cap.

## Product Impact

When selected-team analysis expands the prefilter pool, team quick scan can now attribute later selected-team plays instead of leaving them unreviewed by GPT. This matters for games where the highest-ranked early candidates are opponent plays and the user's chosen team has good blocks, steals, or finishes later in the pool.

Uncertain clips are still preserved for user review when `includeUncertain=true`; this phase improves confidence coverage, not deterministic over-filtering.

## Safety

- GPT still receives sampled JPEG frames and compact candidate metadata only.
- No full videos, source paths, presigned URLs, storage keys, credentials, or FFmpeg commands are sent to GPT.
- The payload remains bounded at 160 candidate clips.
- Low-confidence team ownership still remains uncertain instead of selected-team proof.

## Validation

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios/backend/tests/test_team_quick_scan.py -v` -> 6 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/config.py ios/backend/app/team_quick_scan.py ios/backend/tests/test_team_quick_scan.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 118 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 78 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 39 tests passed.
- `git diff --check` -> passed.

## Launch Recommendation

Use the default 160-candidate scan cap for internal beta while collecting labeled footage. If payload size or latency becomes painful, lower `HOOPS_TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS` in staging, but do not claim selected-team 85% accuracy until the labeled team/highlight eval proves it.
