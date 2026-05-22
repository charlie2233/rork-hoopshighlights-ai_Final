# Phase Edit6 Agent Polish And Cost Controls

## Goal

Phase Edit6 hardens the HoopClips AI Edit Agent for beta use. The branch adds plan-tier policy enforcement, render queue safety, retention metadata, observability events, feature flag placeholders, and clearer Export-page failure/limit UX while preserving the cloud-first architecture.

The iOS app still does not analyze, plan, patch, or render production video locally. It configures the export, requests cloud jobs, previews returned MP4s, downloads local files for sharing, and opens the system share sheet.

## Plan-Tier Policy

The centralized policy model lives in `ios/backend/app/editing.py` as `PlanTierPolicy`.

| Tier | Max Render | Daily Renders | Active Renders | Revisions/Edit | Max Output | Watermark | Outro | Retention |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: |
| `free` | 45s | 3 | 1 | 3 | 720p | required | required | 14 days |
| `pro` | 180s | 25 | 2 | 10 | 1080p | optional | optional | 60 days |
| `internal` | 300s | 100 | 4 | 25 | 1080p | optional | optional | 7 days |
| `dev` | 300s | 500 | 8 | 50 | 1080p | optional | optional | 3 days |

Policy is enforced during:

- edit plan creation
- revision creation
- render request
- revision render request
- render validation

Free-user watermark and outro remain required. Over-limit render duration, over-limit source duration, daily render limit, active render limit, and revision limit now produce explicit failure codes.

## Feature Flags

The branch adds safe feature flag placeholders in the editing service. These are environment-driven defaults for now and can be backed by Statsig later.

| Flag | Env Override | Safe Default |
| --- | --- | --- |
| `ai_edit_enabled` | `HOOPS_AI_EDIT_ENABLED` | `true` |
| `ai_edit_revision_enabled` | `HOOPS_AI_EDIT_REVISION_ENABLED` | `true` |
| `ai_edit_template_pack_enabled` | `HOOPS_AI_EDIT_TEMPLATE_PACK_ENABLED` | `true` |
| `ai_edit_max_daily_renders` | `HOOPS_AI_EDIT_MAX_DAILY_RENDERS` | policy default |
| `ai_edit_free_watermark_required` | `HOOPS_AI_EDIT_FREE_WATERMARK_REQUIRED` | `true` |
| `ai_edit_pro_exports_enabled` | `HOOPS_AI_EDIT_PRO_EXPORTS_ENABLED` | `false` |
| `gpt_highlight_reranker_enabled` | `HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED` | `false` |

`pro` exports are intentionally gated as a placeholder until product/billing decisions are final.

The editing service `/version` response includes the resolved safe feature flag snapshot so staging can verify rollout configuration without exposing secrets. GPT highlight reranking also exposes a safe public config summary (`enabled`, `configured`, model name when enabled, and sampling caps), but never API keys, sampled frames, source URLs, or presigned URLs.

## Render Queue Safety

Render safety additions:

- duplicate render requests use idempotency keys and return the existing active/rendered job when applicable
- active render count is capped per install ID
- daily render count is capped per install ID
- revision count is capped per edit
- stale queued/rendering jobs are marked failed with `failed_timeout`
- failed render retries are capped by tier

The local service still uses in-memory state. This is acceptable for the current staging renderer proof, but persistent job state is a remaining beta-hardening item if Cloud Run instances scale out.

## Retention Metadata

Rendered outputs now carry retention metadata in `render_log.json`, the render status response, and local/R2 object metadata where supported.

Example shape:

```json
{
  "expiresAt": "2026-05-17T00:00:00+00:00",
  "retentionClass": "free_final_render",
  "deleteEligible": true,
  "planTier": "free",
  "editJobId": "edit_123",
  "renderJobId": "render_456",
  "templateId": "personal_highlight_v1",
  "outputBytes": 329805,
  "durationSeconds": 14.422
}
```

No destructive cleanup job was added in this branch. Cleanup should be a separate beta-hardening task with safe dry-run reporting first.

## Observability

The editing service emits structured JSON events and Sentry breadcrumbs when `sentry_sdk` is available. Events avoid secrets and full presigned download URLs.

Backend events:

- `edit_plan.created`
- `edit_revision.created`
- `render.requested`
- `render.started`
- `render.completed`
- `render.failed`
- `download_url.created`

iOS unified-log events:

- `ios.preview.loaded`
- `ios.share.opened`
- `render.failed`
- `edit_plan.created`
- `edit_revision.created`

Event fields include the safe identifiers that matter for support and debugging:

- `editJobId`
- `renderJobId`
- `revisionId`
- `templateId`
- `planTier`
- `rendererVersion`
- `failureReason`
- `outputBytes`
- `durationSeconds`

## iOS Export UX

The Export-page AI Edit section now shows plan limits and clearer failure/retry affordances:

- free/pro limit summary
- disabled over-limit target durations
- friendly backend failure messages for policy and render errors
- retry button when a render fails
- duplicate render taps remain blocked by `isWorking`
- download URL refresh state shows `Download URL expired, refreshing...`
- preview/share flow still downloads the MP4 and shares a local file, not the presigned URL

## Tests Run

Passed:

- `ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py services/editing/editing_app/main.py services/editing/editing_app/models.py services/editing/editing_app/render_storage.py services/editing/scripts/template_pack_smoke.py`
- `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent services.editing.tests.test_editing_service`
- `npm --prefix services/control-plane run typecheck`
- `npx tsx --test services/control-plane/test/control-plane-editing-proxy.test.ts`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-phase6-dd-2 build CODE_SIGNING_ALLOWED=NO`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-phase6-dd-2 build-for-testing CODE_SIGNING_ALLOWED=NO`
- `git diff --check`

Note: an earlier build attempt against `/tmp/hoopclips-phase6-dd` failed with Xcode's `build.db` lock error. The clean rerun with `/tmp/hoopclips-phase6-dd-2` passed.

## Live Smoke

No live Worker/Cloud Run/R2 render smoke was rerun during this branch. Phase Edit5b already proved all three templates and a revision through the live cloud path. Phase Edit6 focuses on policy and beta safety; a focused Personal Highlight free-user smoke should be run before a beta cut if the backend is deployed from this branch.

## Remaining Beta Blockers

- Persist render quota/job state outside a single Cloud Run instance before high-traffic beta.
- Add a dry-run R2 cleanup job for expired `deleteEligible` artifacts.
- Wire Statsig as the remote source of truth for feature flags.
- Configure Sentry DSNs and dashboards for editing service and iOS support traces.
- Finalize product policy for `pro` exports before enabling `HOOPS_AI_EDIT_PRO_EXPORTS_ENABLED`.
- Keep full live render smoke manual or nightly; use faster fixture checks in routine CI.
