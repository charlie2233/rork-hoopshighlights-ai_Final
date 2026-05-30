# Phase Launch64 CI Preflight Fix

Date: 2026-05-30
Branch: `codex/phase-launch64-ci-preflight-fix`
Base: `origin/main` at `27a85a3`

## Scope

The latest `main` Cloud Edit Deploy Preflight dispatch failed in the `Run launch script tests` step because `scripts/test_launch_backend_config_preflight.py` still asserted the old GPT sampling defaults:

- `_AI_CLIP_GPT_KEYFRAMES_PER_CLIP = 10`
- `_AI_CLIP_GPT_MAX_CANDIDATES_FREE = 60`
- `_AI_CLIP_GPT_MAX_CANDIDATES_PRO = 60`

The actual launch contract and deployed workflow now require:

- Free: 8 candidates, 3 frames per clip at runtime
- Pro/internal: 30 candidates max, 8 frames per clip

This branch updates the stale launch-script assertion to protect the current `8 / 8 / 30` Cloud Build substitution contract.

## Evidence

Failed run diagnosed:

- Cloud Edit Deploy Preflight run `26690872944`
- Failed job: `Editing backend Python tests`
- Failed step: `Run launch script tests`
- Failing assertion: expected `_AI_CLIP_GPT_KEYFRAMES_PER_CLIP` to be `10`, actual was `8`

Commands run locally:

```bash
python3 -m unittest scripts.test_launch_backend_config_preflight -v
```

Result: passed, 7 tests.

```bash
python3 scripts/launch_backend_config_preflight.py --json
```

Result: `status=pass`, `fail=0`, `pass=81`, `warn=12`.

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Result: passed, 114 tests.

## Notes

- This is a test-contract fix only; it does not change runtime GPT sampling behavior.
- The prior credential-only dispatch `26690841651` passed before this fix.
- A corrected Cloud Edit Deploy Preflight dispatch should be rerun on the updated `main` commit before spending a staging deploy.
