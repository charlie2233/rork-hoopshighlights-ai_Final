# Phase Launch28 Provider Form and Version Guard

Date: 2026-05-29
Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Turn the latest browser/provider-agent blocker report into safer, more precise repo-side launch tooling.

The agent reported:

- GCP Secret Manager state: blocked by restricted Google Cloud project access for `hoopsclips-9d38f`.
- GitHub Actions hosted runners: no billing or spending-limit blocker observed.
- GCP deploy service account Secret Manager access: blocked by restricted IAM access.
- Cloudflare API token: blocked because the operator is not logged in to Cloudflare and the token still needs to be created and stored as GitHub `staging / CLOUDFLARE_API_TOKEN`.

## Change

`scripts/launch_provider_input_handoff.py` now gives the Atlas/browser agent exact non-secret form values for the Cloudflare token:

- Token name: `HoopClips staging CI deploy`
- Account ID: `78fb4442e6e37b2c46d7e539c6e79172`
- TTL: creation date through 90 days later for internal beta rotation
- Account resources: Worker `hoopsclips-control-plane-staging` and staging R2 buckets
- Zone resources: no zone permission for the workers.dev staging route; if the dashboard requires a choice, use All zones only as a form-required fallback and do not add DNS Edit
- Permissions: Account Settings Read, Workers Scripts Edit, Workers R2 Storage Edit, D1 Edit, optional Workers Tail Read

The handoff still forbids returning token values, private keys, R2 credentials, OpenAI keys, Secret Manager values, and full presigned URLs.

The GCP Secret Manager repair commands now require the latest version state to be exactly `ENABLED` instead of accepting any successful `describe latest` response.

`scripts/staging_version_probe.py` now defaults to the current checkout SHA and fails if the live Worker/direct editing `/version` endpoints agree with each other but do not match the expected branch SHA.

The Cloud Edit Deploy Preflight workflow now prints deploy and rollback rerun commands using the current workflow ref instead of hardcoded `main`.

## Validation

Commands run:

```bash
python3 -m py_compile scripts/launch_provider_input_handoff.py scripts/test_launch_provider_input_handoff.py scripts/staging_version_probe.py scripts/test_staging_version_probe.py scripts/test_main_workflow_codecheck_triggers.py
python3 -m unittest scripts.test_launch_provider_input_handoff scripts.test_staging_version_probe scripts.test_main_workflow_codecheck_triggers -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/launch_backend_config_preflight.py --json
python3 scripts/launch_provider_input_handoff.py --json --ref codex/phase-clip28-cloud-team-quick-scan
python3 scripts/staging_version_probe.py --json --expected-git-sha 4f34eddd5d183b4fa50f643b11946710cb36a04a
```

Results:

- `py_compile`: exited `0`.
- Focused handoff/probe/workflow tests: 15 tests passed.
- Script test discovery: 84 tests passed.
- Backend config preflight: `pass=79 warn=12 fail=0`.
- Provider handoff JSON emitted the new Cloudflare form guide and did not emit secret values.
- Staging version probe still failed, as expected before provider repair, with `worker_route_missing_and_editing_version_stale`: Worker `/v1/editing/version` returned HTTP 404, direct editing `/version` reported `gitSha=d00d0d5`, and direct editing was missing live-render/GPT feature flags.

## Current Blockers

- Google Cloud console access for project `hoopsclips-9d38f`.
- Enabled latest Secret Manager versions for `HOOPS_EDITING_SERVICE_SECRET`, `HOOPS_R2_ACCESS_KEY_ID`, `HOOPS_R2_SECRET_ACCESS_KEY`, and `HOOPS_OPENAI_API_KEY`.
- Secret Manager Secret Accessor on the staging `GCP_DEPLOY_SERVICE_ACCOUNT`.
- Cloudflare token creation/rescope and GitHub staging `CLOUDFLARE_API_TOKEN` update.
- Staging deploy proof and rollback proof.
- Installed TestFlight smoke on an available wired iPhone.
- Launch-grade labeled team/highlight accuracy report.

## Launch Recommendation

Do not submit to Apple yet. After provider access is repaired, rerun Cloud Edit Deploy Preflight on this branch, deploy staging, rerun the staging version probe with the branch SHA, then run the installed TestFlight smoke.
