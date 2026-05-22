# Phase Launch4 AI Edit Kill Switches

Date: 2026-05-22
Branch: `codex/phase-launch4-ai-edit-kill-switches`

## Scope

- Added a first-class backend live-render kill switch: `HOOPS_AI_EDIT_LIVE_RENDER_ENABLED`.
- Kept the switch cloud-owned in `services/editing`; iOS still only requests, polls, previews, downloads, and shares cloud renders.
- Exposed the resolved `aiEditLiveRenderEnabled` state in `/version`.
- Made the four internal-beta AI Edit kill switches explicit Cloud Build substitutions for staging deploys.
- Added tests proving render enqueue is rejected with a structured backend policy error when live rendering is off.
- Did not add local video analysis, local composition, local rendering, Remotion, Canva, secret logging, R2 credential logging, or presigned URL logging.

## Kill Switch Matrix

| Product flag | Cloud env source | Default | Runtime behavior |
| --- | --- | --- | --- |
| `ai_edit_enabled` | `HOOPS_AI_EDIT_ENABLED` | `true` | Blocks edit-plan creation with `ai_edit_disabled`. |
| `ai_edit_live_render_enabled` | `HOOPS_AI_EDIT_LIVE_RENDER_ENABLED` | `true` | Blocks base and revision render enqueue with `ai_edit_live_render_disabled`. |
| `ai_edit_revisions_enabled` | `HOOPS_AI_EDIT_REVISION_ENABLED` | `true` | Blocks revision planning with `ai_edit_revision_disabled`. |
| `ai_edit_templates_enabled` | `HOOPS_AI_EDIT_TEMPLATE_PACK_ENABLED` | `true` | Blocks template-backed planning with `ai_edit_template_pack_disabled`. |

Statsig remains a production-cutover dependency. For internal beta, the authoritative runtime source is the Cloud Run environment snapshot exposed by `/version`, and the deploy-time source is `services/editing/cloudbuild.yaml` substitutions:

```text
_AI_EDIT_ENABLED
_AI_EDIT_LIVE_RENDER_ENABLED
_AI_EDIT_REVISION_ENABLED
_AI_EDIT_TEMPLATE_PACK_ENABLED
```

## Validation

Targeted tests:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest \
  services.editing.tests.test_editing_service.EditingServiceTests.test_version_reports_live_render_kill_switch \
  services.editing.tests.test_editing_service.EditingServiceTests.test_live_render_kill_switch_rejects_render_without_local_fallback \
  services.editing.tests.test_editing_service.EditingServiceTests.test_live_render_kill_switch_rejects_revision_render \
  services.editing.tests.test_editing_service.EditingServiceTests.test_live_render_kill_switch_rejects_stored_edit_render_route \
  services.editing.tests.test_editing_service.EditingServiceTests.test_live_render_kill_switch_emits_safe_policy_failed_event \
  -v
```

Result:

```text
Ran 5 tests in 2.496s
OK
```

Full backend regression:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
```

Result:

```text
Ran 35 tests in 36.882s
OK
```

Additional validation:

```text
python3 -m py_compile services/editing/editing_app/main.py ios/backend/app/editing.py: passed
ruby -e 'require "yaml"; YAML.load_file("services/editing/cloudbuild.yaml")': passed
git diff --check: passed
ASCII scan of changed files: passed
Redacted keyword scan of changed files: only expected secret/R2/presigned/token/key names and placeholders
iOS Debug simulator build through XcodeBuildMCP: passed
iOS Debug build-for-testing: passed
```

Expected `/version` evidence when live render is disabled:

```json
{
  "featureFlags": {
    "aiEditEnabled": true,
    "aiEditLiveRenderEnabled": false,
    "aiEditRevisionEnabled": true,
    "aiEditTemplatePackEnabled": true
  }
}
```

Expected render rejection:

```json
{
  "errorCode": "ai_edit_live_render_disabled",
  "failureReason": "AI Edit rendering is temporarily unavailable."
}
```

## Operator Smoke

After deploying staging with `_AI_EDIT_LIVE_RENDER_ENABLED=false`, verify:

1. `GET /version` reports `aiEditLiveRenderEnabled=false`.
2. `POST /v1/edit-jobs` can still create a reviewable edit plan when `HOOPS_AI_EDIT_ENABLED=true`.
3. `POST /v1/render-jobs`, `POST /v1/edit-jobs/{editJobId}/render`, and `POST /v1/edit-jobs/{editJobId}/revisions/{revisionId}/render` return `403 ai_edit_live_render_disabled`.
4. The iOS app shows the real backend unavailable/failure state; it must not fake work or fall back to local rendering for AI Edit.
5. Re-enable with `_AI_EDIT_LIVE_RENDER_ENABLED=true`, redeploy, and rerun the existing Worker-path render smoke.

## Remaining Blockers

- Statsig is still not wired as the remote production source of truth.
- A real staging deploy with live render disabled/enabled still needs the Cloudflare/GCP CI credentials from Phase Launch2.
- Real post-install TestFlight smoke still needs an online trusted iPhone with the internal staging build installed.
- Production cloud cutover remains blocked by production Worker, Cloud Run, R2, D1, Sentry, Statsig, RevenueCat, Google, rollback, and beta proof gates.
