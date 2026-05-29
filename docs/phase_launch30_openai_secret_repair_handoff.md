# Phase Launch30: OpenAI Secret Repair Handoff

Date: 2026-05-29
Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Make the provider/browser-agent handoff unambiguous after the latest status came back blocked at step 1 because `HOOPS_OPENAI_API_KEY` was missing.

## Provider Status Interpreted

The latest non-secret provider-agent status was:

- GCP Secret Manager: `HOOPS_OPENAI_API_KEY` missing.
- Enabled latest version: no.
- Secret accessor granted: no.
- Cloudflare token updated: no.
- GitHub run URL: not triggered.
- Conclusion: failed at step 1.

That is a real launch blocker, but it is also the expected repair path: create the missing GCP Secret Manager secret, add an enabled latest version from an operator-held value, grant Secret Manager Secret Accessor to the staging deploy service account, then continue to Cloudflare token repair and workflow verification.

## Change

`scripts/launch_provider_input_handoff.py` now includes a `gcpSecretRepairPolicy` section and a stricter Atlas/browser-agent prompt:

- Missing Secret Manager secrets are explicitly described as repair actions, not terminal failures.
- `HOOPS_OPENAI_API_KEY` is called out as GCP Secret Manager only; it must not be mirrored into GitHub secrets, chat, docs, screenshots, or logs.
- The browser-agent prompt now says not to stop after reporting a missing secret unless the operator-held value is unavailable.
- The requested non-secret return format now reports each required GCP secret individually:
  - `HOOPS_EDITING_SERVICE_SECRET`
  - `HOOPS_R2_ACCESS_KEY_ID`
  - `HOOPS_R2_SECRET_ACCESS_KEY`
  - `HOOPS_OPENAI_API_KEY`
- The handoff still requests only yes/no provider state and blocker names, never secret values.

## Safe Agent Response

Use this as the response to the provider/browser agent:

```text
Continue. `HOOPS_OPENAI_API_KEY` missing is the first repair step, not the final conclusion.

In GCP project `hoopsclips-9d38f`, create or repair Secret Manager secret `HOOPS_OPENAI_API_KEY` from the operator-held OpenAI key and verify the latest version state is `ENABLED`. Do not paste, reveal, screenshot, summarize, or return the key value.

Then verify these required secrets all exist with latest version `ENABLED`:
- `HOOPS_EDITING_SERVICE_SECRET`
- `HOOPS_R2_ACCESS_KEY_ID`
- `HOOPS_R2_SECRET_ACCESS_KEY`
- `HOOPS_OPENAI_API_KEY`

Next verify the staging deploy service account configured in GitHub environment secret `GCP_DEPLOY_SERVICE_ACCOUNT` has Secret Manager Secret Accessor for those secret names.

Then create/rescope the Cloudflare token and set it directly as GitHub environment secret `staging / CLOUDFLARE_API_TOKEN`.

Return only non-secret status:
- HOOPS_EDITING_SERVICE_SECRET present and enabled: yes/no
- HOOPS_R2_ACCESS_KEY_ID present and enabled: yes/no
- HOOPS_R2_SECRET_ACCESS_KEY present and enabled: yes/no
- HOOPS_OPENAI_API_KEY present and enabled: yes/no
- all required GCP secrets present and enabled: yes/no
- deploy service account has Secret Manager access: yes/no
- GitHub staging CLOUDFLARE_API_TOKEN updated: yes/no
- Any blocker that remains, by name only
```

## Validation

Commands run:

```bash
python3 -m py_compile scripts/launch_provider_input_handoff.py scripts/test_launch_provider_input_handoff.py
python3 -m unittest scripts.test_launch_provider_input_handoff -v
python3 scripts/launch_provider_input_handoff.py --json --ref codex/phase-clip28-cloud-team-quick-scan
python3 scripts/launch_provider_input_handoff.py --ref codex/phase-clip28-cloud-team-quick-scan
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/launch_backend_config_preflight.py --json
python3 scripts/staging_version_probe.py --json --expected-git-sha $(git rev-parse HEAD)
python3 scripts/submission_readiness_preflight.py --json
git diff --check
```

Results:

- Focused provider handoff tests passed: 5 tests.
- Script test discovery passed: 92 tests.
- Backend config preflight passed: pass=79, warn=12, fail=0.
- Staging version probe still failed as expected before provider repair: Worker `/v1/editing/version` returned 404 and direct editing `/version` was stale at `gitSha=d00d0d5`.
- Submission readiness remained NO-GO as expected because this branch had uncommitted changes during validation, launch-grade team/highlight accuracy proof is missing, the wired iPhone is unavailable, live Worker/direct editing are stale or missing required flags, main-branch CI is stale, and the documented TestFlight/Worker/Cloudflare/kill-switch blockers remain.

## Launch Recommendation

Do not submit to Apple or claim internal TestFlight readiness yet. Independent read-only checks also confirmed that the launch-critical GPT editing, Agent Cookbook, Free=3, and selected-team quick-scan work is on `codex/phase-clip28-cloud-team-quick-scan`, while the root `codex/redesign-hoopclips-logo` checkout is a dirty, stale logo branch and is not a submission baseline.

After the provider repair succeeds, rerun `Cloud Edit Deploy Preflight` on `codex/phase-clip28-cloud-team-quick-scan`, deploy staging only after preflight passes, verify live `/v1/editing/version` through the Worker, then run the installed TestFlight smoke and launch-grade team/highlight accuracy report.
