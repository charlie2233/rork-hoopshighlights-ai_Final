# Phase Launch26 Provider Secret Repair Handoff

## Goal

Make the current staging deploy blocker actionable without printing or storing secret values.

## Current Evidence

The latest PR codechecks are green on branch `codex/phase-clip28-cloud-team-quick-scan` at `58b161e`:

- `Cloud Edit Deploy Preflight` PR run `26658624497`: success.
- `iOS Internal TestFlight Upload` PR run `26658624491`: success.

The secret-gated staging deploy preflight run `26658372197` reached provider checks but failed before deploy. It confirmed required GitHub staging input names exist and Google Cloud auth works, then blocked on:

- GCP Secret Manager secret `HOOPS_EDITING_SERVICE_SECRET` missing or inaccessible.
- GCP Secret Manager secret `HOOPS_R2_ACCESS_KEY_ID` missing or inaccessible.
- GCP Secret Manager secret `HOOPS_R2_SECRET_ACCESS_KEY` missing or inaccessible.
- GCP Secret Manager secret `HOOPS_OPENAI_API_KEY` missing or inaccessible.
- Cloudflare token cannot authenticate Wrangler.

GitHub environment secret timestamps still show `CLOUDFLARE_API_TOKEN` was last updated on 2026-05-24, so there is no current evidence that token repair happened after the failed preflight.

## Change

Updated `scripts/launch_provider_input_handoff.py` so the safe provider handoff now includes:

- Required GCP Secret Manager secret names and local-prompt `gcloud` commands that avoid printing secret values.
- Cloudflare token requirements for CI Wrangler automation.
- A GitHub Actions billing/spending/startability gate so deploy and TestFlight workflows cannot be treated as proven if runners cannot start.
- A ready-to-copy Atlas/browser-agent prompt that forbids returning secret values, API keys, R2 credentials, private key material, or full presigned URLs.
- Non-secret return fields for provider-side status.

This keeps the local agent out of provider UI credential entry while giving the browser agent a precise task.

## Verification

```bash
python3 -m py_compile scripts/launch_provider_input_handoff.py scripts/test_launch_provider_input_handoff.py
python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py
python3 -m unittest scripts.test_launch_provider_input_handoff scripts.test_submission_readiness_preflight -v
python3 scripts/launch_provider_input_handoff.py --json
```

Expected:

- Handoff JSON includes `gcpSecretManagerSecrets`.
- Handoff JSON includes `cloudflareTokenRequirements`.
- Handoff JSON includes `atlasAgentPrompt`.
- Handoff JSON includes the GitHub Actions billing/spending/startability status gate.
- No secret values are emitted.

## Next Gate

After the browser/provider agent reports the non-secret status is complete, rerun:

```bash
gh workflow run "Cloud Edit Deploy Preflight" \
  --repo charlie2233/rork-hoopshighlights-ai_Final \
  --ref codex/phase-clip28-cloud-team-quick-scan \
  -f operation=preflight
```

If that passes, run staging deploy and version proof before any internal TestFlight upload or Apple submission.
