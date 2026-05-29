# Phase Clip103: Confident Detected-Team Fallback

## Goal

Prevent weak clip-level team guesses from becoming selectable detected-team options when the explicit quick-scan team list is unavailable.

## Change

- Fallback detected-team synthesis now ignores clips with `teamAttributionStatus="uncertain"`.
- Fallback detected-team synthesis requires attribution confidence of at least `0.85`.
- Sources that require evidence (`quick_scan`, `gpt_frame_review`, `provider`, and default `unknown`) must have at least two evidence frame refs and two role groups before they can create a fallback `TeamOption`.
- Manual attributions remain eligible without frame evidence.

## Why

The product flow asks users to choose from teams detected by a quick scan and labeled by jersey color. If the scan/team list is unavailable, weak clip guesses should not become team choices. This keeps selected-team analysis grounded in confident evidence while preserving uncertain clips for Review instead of turning them into automatic team options.

## Validation

- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v`
  - Result: `Ran 177 tests in 4.855s`, `OK`.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v`
  - Result: `Ran 97 tests in 20.181s`, `OK`.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Result: `Ran 71 tests in 0.259s`, `OK`.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py`
  - Result: passed.
- `git diff --check`
  - Result: passed.

## Remaining Launch Blockers

- This change is covered by unit tests only. Internal submission still needs the launch-grade labeled team-highlight accuracy report, a real iPhone/TestFlight smoke, live staging Worker/version checks, and green GitHub Actions.
- GitHub Actions for the open PR remained blocked before this patch by account billing/spending-limit status, so CI cannot be treated as green until billing is fixed and the checks run on this branch.
