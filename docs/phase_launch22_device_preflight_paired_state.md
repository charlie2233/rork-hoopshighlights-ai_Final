# Phase Launch22: Device Preflight Paired State

## Goal

Remove a false internal-launch blocker where `submission_readiness_preflight.py` failed the connected-iPhone gate even though `xcrun devicectl` reported a paired available iPhone.

## Fix

`devicectl` can report physical devices with a state like `available (paired)`. The readiness parser now:

- preserves parenthesized state tokens such as `(paired)`
- keeps the model field as `iPhone 15 Pro (iPhone16,1)`
- treats states that start with `available` as usable for installed TestFlight smoke

This does not fake the installed smoke. It only makes the device availability gate match the current `devicectl` output.

## Evidence

Observed local device state:

```text
charlie's iPhone: available (paired), iPhone 15 Pro (iPhone16,1)
```

Validation:

```bash
python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py -> passed
python3 -m unittest scripts.test_submission_readiness_preflight -v -> 16 tests passed
git diff --check -> passed
```

Readiness preflight now passes the connected-device check, but still fails on external/live launch gates:

- staging Worker `/v1/editing/version` returns `404`
- direct editing `/version` is stale and missing current AI Edit/GPT flags
- required main-branch CI does not match the current checkout
- installed TestFlight post-install smoke is still unproven
- Cloudflare deploy credential proof and live Worker kill-switch proof remain documented blockers
