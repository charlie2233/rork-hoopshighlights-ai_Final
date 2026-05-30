# Phase Launch45: Provider Handoff Cheap Check

## Goal

Keep Cloudflare token repair iterations from burning full GitHub Actions deploy preflights. The browser/Atlas handoff now tells the provider-side agent to run only the cheap `operation=credential-check` after updating `staging / CLOUDFLARE_API_TOKEN`.

## Change

- Updated `scripts/launch_provider_input_handoff.py`.
- Added `operation=credential-check` before `operation=preflight` in generated verification commands.
- Changed the Atlas/browser prompt to trigger only `operation=credential-check` after provider repair.
- Explicitly tells the browser agent not to run `operation=preflight` or `operation=deploy` during token repair.
- Updated `scripts/test_launch_provider_input_handoff.py` so the safe handoff stays budget-aware.
- Updated `scripts/submission_readiness_preflight.py` failure copy to point operators at `operation=credential-check` before the full readiness `operation=preflight`.

## Why

`operation=preflight` still proves launch readiness, but it also runs the heavier Worker and backend test jobs. Token repair is currently failing at Wrangler auth, so the cheapest useful proof is the credential-only path added in Phase Launch44.

## Validation

Commands:

```bash
python3 scripts/launch_provider_input_handoff.py --json --ref main | python3 -m json.tool | rg -n "operation=credential-check|operation=preflight|Cloud deploy credential check|Do not run operation"
python3 scripts/submission_readiness_preflight.py --json
```

Observed:

- The Atlas/browser prompt uses `operation=credential-check`.
- The verification command list keeps `operation=preflight` for the later full proof.
- The prompt says not to run `operation=preflight` or `operation=deploy` during provider repair.
- Readiness preflight still fails, as expected before launch proof, with `21` passing checks and `13` failing checks on this branch snapshot.

## Next Step

After the GitHub `staging / CLOUDFLARE_API_TOKEN` timestamp changes, run:

```bash
gh workflow run cloud-edit-deploy-preflight.yml \
  --repo charlie2233/rork-hoopshighlights-ai_Final \
  --ref main \
  -f operation=credential-check
```

Only run the full `operation=preflight` after the credential-only run passes.
