# Phase Launch66 Accuracy CLI Entrypoints

Date: 2026-05-30
Branch: `codex/phase-launch66-accuracy-cli-handoff`
Base: `origin/main` at `f6c7204`

## Scope

Fix launch accuracy collection scripts so the documented direct commands work from a clean checkout. The affected scripts imported `scripts.*` modules before adding the repo root to `sys.path`, so direct commands such as `python3 scripts/collect_team_highlight_accuracy_case.py --help` could fail with `ModuleNotFoundError` before any cloud collection work started.

## Changes

- Added repo-root import bootstrapping to:
  - `scripts/collect_team_highlight_accuracy_case.py`
  - `scripts/make_team_highlight_label_template.py`
  - `scripts/build_launch_team_accuracy_report.py`
- Added `scripts/test_accuracy_cli_entrypoints.py` to run the documented accuracy scripts directly with `--help`.

## Evidence

Commands run:

```bash
python3 scripts/collect_team_highlight_accuracy_case.py --help
python3 scripts/make_team_highlight_label_template.py --help
python3 scripts/build_launch_team_accuracy_report.py --help
python3 -m unittest scripts.test_accuracy_cli_entrypoints scripts.test_collect_team_highlight_accuracy_case scripts.test_build_launch_team_accuracy_report scripts.test_build_team_highlight_eval_payload scripts.test_team_highlight_accuracy_eval -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Results:

- All three direct `--help` commands exited 0 and printed usage.
- Targeted accuracy suite: 40 tests passed.
- Full scripts suite: 115 tests passed.

## Spark Review Notes Triage

The review note at `/Users/hanfei/Desktop/HoopClips-Review-Notes-2026-05-30_full.txt` correctly flags a malformed temp filename string in the dirty root `codex/redesign-hoopclips-logo` worktree:

```swift
"imported_video_(UUID().uuidString).(fileExtension)"
```

This is not present in the clean launch66 worktree based on current `origin/main`, which uses:

```swift
"imported_video_\(UUID().uuidString).\(fileExtension)"
```

Keep that root-branch bug separate from launch readiness work so uncommitted logo/import changes do not leak into the release branch.

## Remaining Launch Blockers

- A real launch-grade team/highlight accuracy report is still needed. It must come from real cloud analysis plus human-filled labels, not local video analysis or synthetic labels.
- Installed post-TestFlight build 6 smoke is still needed on a real iPhone: install from TestFlight, import/upload, cloud analysis, Review, Export AI Edit, render preview, More Hype revision, revised preview, share/open-in.
