# Phase Clip102: Preserve Analysis Team Uncertainty

## Goal

Keep scan/provider uncertainty sticky through analysis results so a clip explicitly marked `teamAttributionStatus=uncertain` is not promoted to a confident selected-team match just because its attribution also contains high confidence and frame evidence.

## Change

- `_analysis_team_status` now returns `uncertain` when the incoming `CloudClip` already carries `teamAttributionStatus="uncertain"`.
- Added a regression where a high-confidence, evidence-backed selected-team block remains review-only when upstream attribution explicitly marked it uncertain.

## Why

The launch flow keeps not-sure clips in Review instead of hiding them or treating them as automatic final selections. This is especially important for blocks, steals, and partially occluded defensive plays where GPT/team scan may have enough evidence to keep the clip visible but not enough certainty to auto-promote it.

## Validation

- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_analysis_team_status_preserves_explicit_uncertain_scan_status ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_analysis_team_status_requires_evidence_for_unknown_and_provider_sources -v` passed: 2 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v` passed on sequential rerun: 176 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v` passed: 97 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 71 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py` passed.
- `git diff --check` passed.

Note: one earlier full iOS backend run was started in parallel with editing-service render tests and hit a timing failure in `test_team_scan_endpoint_runs_before_start_and_start_accepts_selection` where the job was still `processing`. That exact test passed when rerun alone, and the full iOS backend suite passed on the sequential rerun above.
