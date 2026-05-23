# Phase Launch13 Smoke Log Redaction

Date: 2026-05-23
Branch: `codex/phase-launch13-smoke-log-redaction`

## Scope

- Hardened smoke-script failure logging so backend error payloads do not leak bearer-style URLs, object keys, credentials, tokens, authorization values, or secrets into terminal logs or CI artifacts.
- Updated the legacy iOS backend live render smoke and Worker render smoke failure paths.
- Added focused unit coverage for nested redaction behavior.
- No cloud rendering, edit planning, iOS UI, template, or local video-processing behavior changed.

## Redaction Behavior

The smoke helper now recursively redacts dictionary fields whose keys contain:

- `url`
- `objectKey`
- `secret`
- `credential`
- `token`
- `authorization`

It also redacts presigned-style string values containing `X-Amz-Signature` or `X-Amz-Credential`.

## Validation

Commands run:

```sh
python3 -m py_compile ios/backend/scripts/live_render_smoke.py services/editing/scripts/live_render_smoke.py services/editing/scripts/worker_render_smoke.py scripts/test_smoke_log_redaction.py
python3 -m unittest scripts.test_smoke_log_redaction -v
python3 -m unittest scripts.test_launch_backend_config_preflight scripts.test_submission_readiness_preflight scripts.test_smoke_log_redaction -v
git diff --check
```

Results:

- Redaction unit tests: 2 passed, 0 failed.
- Script/preflight unit tests: 14 passed, 0 failed.
- Python compile check: passed.
- `git diff --check`: passed.

## Launch Notes

- This branch reduces log exposure during failed live smoke runs.
- It does not resolve external launch blockers: signing/team inputs, App Store Connect upload inputs, Cloudflare/GCP deploy inputs, staging Worker 404 on `/v1/editing/version`, unavailable wired iPhone, failed main workflows, and unproven installed TestFlight smoke remain blocking.
