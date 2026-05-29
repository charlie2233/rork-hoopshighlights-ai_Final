# Phase Launch35 Provider Handoff Rerun Guard

Branch: `codex/phase-launch35-provider-handoff-rerun-guard`

## Goal

Make the provider/browser-agent handoff harder to stop halfway. The last provider status stopped at `HOOPS_OPENAI_API_KEY` missing and did not trigger a fresh cloud deploy preflight, so the handoff now requires a non-secret rerun result after GCP and Cloudflare repairs.

## Change

- `scripts/launch_provider_input_handoff.py` now tells the Atlas/browser agent to trigger:

```bash
gh workflow run cloud-edit-deploy-preflight.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref <ref> -f operation=preflight
```

- The prompt explicitly says not to run `operation=deploy` yet.
- The non-secret return contract now requires:
  - `Cloud deploy preflight triggered: yes/no`
  - `GitHub run URL:`
  - `Final conclusion:`
- `services/editing/scripts/deploy_preflight.py` now classifies provider blockers more specifically:
  - GCP Secret Manager `missing`
  - GCP Secret Manager permission/accessor issue
  - secret exists but has no latest version
  - secret latest version is not `ENABLED`
  - Wrangler rejected token
  - Wrangler account/scope/permission failure
- iOS production runtime config no longer allows Release to pass as an on-device product:
  - production `.disabled` cloud launch mode is a missing-key failure
  - production requires both cloud analysis and cloud edit base URLs
  - `Release.xcconfig` keeps `HOOPS_CLOUD_LAUNCH_MODE = enabled`
  - release preflight requires production cloud URL variables and built Info.plist values

## Current Evidence

- Main commit inspected before this branch: `cc451617382967fb4844ad48a4f9a75033a52054`.
- Current main cloud preflight remains blocked: [run 26666556008](https://github.com/charlie2233/rork-hoopshighlights-ai_Final/actions/runs/26666556008).
- Current main iOS internal TestFlight archive preflight passed: [run 26666556017](https://github.com/charlie2233/rork-hoopshighlights-ai_Final/actions/runs/26666556017).
- `python3 scripts/submission_readiness_preflight.py --json` still fails as expected until provider secrets, Wrangler auth, live Worker `/v1/editing/version`, current editing deploy, wired-device smoke, and launch-grade team accuracy evidence are proven.
- After adding richer local diagnostics, `python3 services/editing/scripts/deploy_preflight.py --project hoopsclips-9d38f --json` showed all four required GCP Secret Manager names exist with latest `ENABLED` for the active local `gcloud` identity. This does not prove the GitHub Actions deploy service account has Secret Manager access; the secret-gated workflow must still pass.
- Latest browser-agent/provider reply still reported:
  - `HOOPS_OPENAI_API_KEY` missing/not enabled from that provider path
  - Secret Manager accessor not granted/proven
  - Cloudflare token not updated
  - no rerun URL triggered

## Remaining Blockers

- GitHub Actions deploy service account access to GCP Secret Manager is still unproven after the last failed workflow.
- Wrangler auth still fails or is unavailable for deploy automation until a valid `CLOUDFLARE_API_TOKEN` is proven in GitHub Actions.
- Staging Worker `/v1/editing/version` returns `404`.
- Direct staging editing service is not at the current git SHA and does not expose the required GPT/live-render feature flags.
- Wired iPhone post-install TestFlight smoke is unproven.
- Launch-grade selected-team/highlight accuracy report is missing.

## Validation

- `python3 -m py_compile scripts/launch_provider_input_handoff.py scripts/test_launch_provider_input_handoff.py scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py` passed.
- `python3 -m unittest scripts.test_launch_provider_input_handoff scripts.test_submission_readiness_preflight -v` passed: 32 tests.
- `python3 scripts/launch_provider_input_handoff.py --json --ref main | python3 -m json.tool >/tmp/launch35_handoff.json && rg -n "Cloud deploy preflight triggered|GitHub run URL|operation=preflight|operation=deploy|HOOPS_OPENAI" /tmp/launch35_handoff.json` passed and confirmed the generated prompt includes the guarded rerun request without secret values.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 103 tests.
- `git diff --check` passed.
- `python3 scripts/submission_readiness_preflight.py --json` still fails before commit as expected with `fail=12`, `pass=21`, `warn=1`; the extra fail/warn are the uncommitted branch diff and new doc, and the live/provider/evidence blockers remain unchanged.
- `python3 -m py_compile services/editing/scripts/deploy_preflight.py scripts/test_deploy_preflight_diagnostics.py scripts/launch_provider_input_handoff.py scripts/test_launch_provider_input_handoff.py` passed.
- `python3 -m unittest scripts.test_deploy_preflight_diagnostics scripts.test_launch_provider_input_handoff scripts.test_launch_backend_config_preflight -v` passed: 20 tests.
- `python3 services/editing/scripts/deploy_preflight.py --project hoopsclips-9d38f --json` exited `1` with `status=blocked`: GCP secret checks passed for the active local identity, and the remaining local blocker was missing/unusable Wrangler auth.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker services.editing.tests.test_editing_service -v` passed: 109 tests.
- `python3 scripts/launch_backend_config_preflight.py --json` passed with `pass=81`, `warn=12`, `fail=0`.
- XcodeBuildMCP `test_sim -only-testing:HoopsClipsTests` passed: 90 tests, 0 failed, iPhone 17 Pro simulator.
- XcodeBuildMCP `build_sim` passed for `HoopsClips` Debug on the iPhone 17 Pro simulator.
