# Phase Clip32: Staging GPT Live Gate

## Goal

Make the quality-beta staging deploy actually use the GPT editor when the OpenAI secret is present. The code already supports GPT-led clip selection, shot-tracker-style evidence checks, plan edits, and revision patches, but staging deploy config still treated GPT as disabled. That could make internal TestFlight smoke pass while silently falling back to deterministic editing.

## Change

- Staging `services/editing/cloudbuild.yaml` now sets:
  - `_AI_CLIP_GPT_EDITOR_ENABLED: "true"`
  - `_AI_CLIP_GPT_PLAN_EDIT_ENABLED: "true"`
  - `_AI_CLIP_GPT_REVISION_ENABLED: "true"`
  - `_GPT_HIGHLIGHT_RERANKER_ENABLED: "true"`
- Staging Cloud Run maps `HOOPS_OPENAI_API_KEY` from Secret Manager by name only.
- Deploy preflight now requires the `HOOPS_OPENAI_API_KEY` Secret Manager entry.
- The post-deploy `/version` checks now require:
  - GPT clip editor, plan edit, revision, and legacy reranker feature flags to be true.
  - `gptHighlightReranker.configured == true`, proving the secret is mounted without exposing it.
- Submission readiness/version probes require the safe GPT feature-flag keys to be present.

## Secret Status

Local non-secret verification checked the configured project and found that the Secret Manager entry named `HOOPS_OPENAI_API_KEY` is not present yet. Do not paste the key into chat or docs. Create the secret in GCP Secret Manager, then rerun deploy preflight.

## Validation Evidence

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `gcloud config get-value project --quiet` -> configured project resolved.
- `gcloud secrets describe HOOPS_OPENAI_API_KEY --project=hoopsclips-9d38f --format='value(name)'` -> missing secret, no secret value printed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 39 tests passed.
- `python3 -m py_compile scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py scripts/staging_version_probe.py scripts/test_staging_version_probe.py services/editing/scripts/deploy_preflight.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 112 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 78 tests passed.
- `git diff --check` -> passed.

## Launch Recommendation

Create the `HOOPS_OPENAI_API_KEY` Secret Manager entry before deploying staging. Keep the kill switches in place, but the internal TestFlight quality smoke should run with GPT enabled so clip choice, selected-team filtering, More Hype revisions, and AI Work Receipt evidence reflect the real beta experience.
