# Phase 4h Inference Guardrails Integration

Date: 2026-05-23
Branch: `codex/phase4h-inference-guardrails-integration`
Base: `ebd0e34d40037ca72e9b965a7f4f1757a6a400ae`

## Scope

This branch keeps the launch stack intact and adds a Worker contract guard for the Phase 4h inference shadow fields. It does not merge PR #2 wholesale because that branch is stale against the launch stack and conflicts with current iOS, control-plane, and launch configuration files.

Cloud remains the owner for analysis, clipping enhancement, model evaluation, and render policy. iOS remains only the upload/review/status/preview/download/share surface.

## Evidence

- Current launch stack head before this branch: `ebd0e34d40037ca72e9b965a7f4f1757a6a400ae`.
- PR #2 head inspected: `4f319182c569d232b5c1e68dff4ecee3cc51cee4`.
- Draft PR #4: `codex/phase4h-inference-guardrails-integration` into `codex/phase-launch2-ci-deploy-token-unblock-readiness`.
- The true Phase 4h slice is the delta after `origin/codex/phase4g-proposal-conditioned-shot-head-and-hierarchical-promotion`.
- That slice is inference/eval focused: temporal event detector runtime, temporal encoder raw logits, shadow-eval guardrails, temporal detector training loss controls, tests, and docs.
- A wholesale merge reported conflicts in launch-owned `ios/**`, `services/control-plane/**`, `.gitignore`, `AGENTS.md`, and `ios/backend/**`.
- The launch branch does not currently track `services/inference`; only ignored local inference leftovers exist on disk. Importing all of PR #2's inference tree would add 161 files and about 7.6 MB, including model artifacts.
- GitHub Actions run `26337948161`: Worker typecheck and dry run passed. Deploy-secret verification was skipped because this was a pull request run, not a `workflow_dispatch` run.

## Change

`services/control-plane/test/control-plane-structured-metadata.test.ts` now proves that the Worker callback and public job polling contract preserves Phase 4h shadow fields additively:

- `temporal_event_detector_family_gate_rejection_reason`
- `temporal_event_detector_proposal_acceptance_probability`
- `temporal_event_detector_proposal_acceptance_energy`
- `temporal_event_detector_shot_head_invoked`

This prevents the launch control plane from stripping the new evaluation signals when the inference service lands or when PR #2 is extracted onto the launch stack.

## Required Follow-Up

Do not merge PR #2 wholesale into the launch branch. Use a fresh integration branch that starts from the launch stack and ports only:

- `services/inference/app/runtime_models/temporal_event_detector.py`
- `services/inference/app/temporal_encoder.py`
- `services/inference/scripts/run_shadow_eval.py`
- `services/inference/tests/test_temporal_event_detector.py`
- `services/inference/tests/test_shadow_eval.py`
- `services/inference/training/temporal_event_detector.py`
- Phase 4h docs with stale claims corrected

Before public cutover, run a live shadow batch with confirmed labels and record only job IDs, aggregate metrics, and redacted evidence. Do not paste source URLs, upload URLs, R2 credentials, or full presigned download URLs into docs or tickets.

## Validation

Completed in this branch:

- `npm --prefix services/control-plane run typecheck`: passed.
- `npx tsx --test services/control-plane/test/control-plane-structured-metadata.test.ts`: passed, 1/1.
- `npx tsx --test services/control-plane/test/*.test.ts`: passed, 20/20.
- `npm --prefix services/control-plane run deploy:staging:dry-run`: passed with staging Worker bindings only; no deploy was performed.
- `python3 -m py_compile $(rg --files services/editing | rg '\.py$')`: passed.
- `PYTHONPATH=services/editing:ios/backend services/editing/.venv/bin/python -m unittest discover -s services/editing/tests`: passed, 44/44, using Python 3.13 with pinned editing requirements plus the FastAPI TestClient `httpx` test dependency.
- `python3 -m py_compile $(rg --files ios/backend | rg '\.py$')`: passed.
- `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests`: passed, 31/31.
- XcodeBuildMCP `build_run_sim` for `HoopsClips` Debug on iPhone 17 Pro simulator: passed and launched the app.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath /tmp/hoopclips-phase4h-bft-dd -skipPackagePluginValidation build-for-testing`: passed with `** TEST BUILD SUCCEEDED **`.

Notes:

- The first editing test attempt with Homebrew `python3` used Python 3.14 and failed because the pinned `pydantic-core`/PyO3 stack supports up to Python 3.13. The successful run used Python 3.13.
- The first `ios/backend` test attempt missed `PYTHONPATH=ios/backend`; rerunning with that path passed.
- Xcode emitted existing Swift concurrency/deprecation warnings in local analysis/export files. This branch does not change iOS analysis or export code.
- Final diff hygiene checks are run after this evidence update.

## Blockers

- No installed TestFlight device smoke has been completed in this branch.
- PR #2 remains draft/dirty/conflicting and needs extraction rather than merge.
- The live Phase 4h shadow rerun on a confirmed-label batch is still required.
