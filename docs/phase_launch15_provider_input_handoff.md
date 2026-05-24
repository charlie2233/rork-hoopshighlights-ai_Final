# Phase Launch15 Provider Input Handoff

Date: 2026-05-24
Branch: `codex/phase-launch15-provider-input-handoff`

## Scope

- Added `scripts/launch_provider_input_handoff.py` to generate a safe provider setup handoff for the remaining HoopClips TestFlight/App Store blockers.
- The handoff prints exact GitHub `staging` secret/variable command shapes and local signing input guidance using placeholders only.
- It does not read, print, store, infer, or commit secret values.
- It does not change cloud deploy, iOS upload, GPT editing, rendering, or app runtime behavior.

## Why This Exists

The current submission preflight is blocked by provider and device state: missing GitHub environment inputs, missing local signing team, no archive/IPA, unavailable iPhone, staging Worker `/v1/editing/version` returning `404`, and unproven installed TestFlight smoke.

The handoff generator turns those missing input names into a repeatable setup packet for the operator without putting secret values in chat or docs.

## Usage

```sh
python3 scripts/launch_provider_input_handoff.py
python3 scripts/launch_provider_input_handoff.py --json
python3 scripts/launch_provider_input_handoff.py --output /tmp/hoopclips-provider-handoff.md
```

## Output Groups

- GitHub environment secrets for `staging`
- GitHub environment variables for `staging`
- Local `HOOPS_DEVELOPMENT_TEAM` signing input
- Verification commands for preflight, cloud deploy preflight, iOS TestFlight preflight, staging deploy, and final preflight
- Manual gates for trusted iPhone, staging Worker version proof, archive/IPA, installed TestFlight smoke, cloud render, revision, preview, and share/open-in

## Validation

Commands run:

```sh
python3 scripts/launch_provider_input_handoff.py
python3 scripts/launch_provider_input_handoff.py --json
python3 -m py_compile scripts/launch_provider_input_handoff.py scripts/test_launch_provider_input_handoff.py
python3 -m unittest scripts.test_launch_provider_input_handoff -v
python3 -m unittest scripts.test_submission_readiness_preflight scripts.test_launch_provider_input_handoff -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/launch_backend_config_preflight.py
git diff --check
python3 scripts/submission_readiness_preflight.py
```

Results:

- `python3 scripts/launch_provider_input_handoff.py` exited `0` and generated `/tmp/hoopclips-provider-handoff.md`.
- `python3 scripts/launch_provider_input_handoff.py --json` exited `0` and generated `/tmp/hoopclips-provider-handoff.json`.
- `python3 -m py_compile scripts/launch_provider_input_handoff.py scripts/test_launch_provider_input_handoff.py` exited `0`.
- `python3 -m unittest scripts.test_launch_provider_input_handoff -v` ran 3 tests, all passing.
- `python3 -m unittest scripts.test_submission_readiness_preflight scripts.test_launch_provider_input_handoff -v` ran 13 tests, all passing.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` ran 19 tests, all passing.
- `python3 scripts/launch_backend_config_preflight.py` exited `0` with `pass=63 warn=12 fail=0`.
- `git diff --check` exited `0`.
- `python3 scripts/submission_readiness_preflight.py` exited `1` with `pass=19 warn=1 fail=10` before commit. The warning was the 3 untracked files from this branch. The failures are the known provider/device/live-route launch gates, not new runtime regressions from this script.
- After commit, `python3 scripts/submission_readiness_preflight.py` exited `1` with `pass=20 warn=0 fail=10`. The remaining failures are the known provider/device/live-route launch gates.

## Launch Notes

- This branch does not unblock Apple submission by itself.
- After the operator installs the listed provider inputs and makes the iPhone available, rerun `python3 scripts/submission_readiness_preflight.py`.
- Do not submit to Apple until the preflight is green and the real installed TestFlight smoke proves upload/import, cloud analysis, Review, Export, AI Edit render, preview, More Hype revision, revised preview, and share/open-in.
