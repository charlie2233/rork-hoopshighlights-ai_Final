# HoopClips AI Edit Engine Contract

Last updated: 2026-06-23

## Scope

This worktree owns the AI Edit engine request/response contract shared by the iOS client, the Cloudflare control plane, and the backend editing service. The architecture stays cloud-first: AI edit planning and production rendering remain backend-owned, while iOS is the upload, review, status, preview, download, and share surface.

## Edit Job Create Request

`CreateEditJobRequest` accepts these additive asset-aware fields:

- `assetId`: optional stable uploaded asset identifier from the upload pipeline.
- `sourceClipIds`: optional ordered IDs for the selected source clips that should drive edit planning and render source clip selection.
- `sourceObjectKey`: compatibility storage key. Keep this until the upload and edit integrations complete.
- `clips`: compatibility full candidate clip payload. Keep this even when `sourceClipIds` is present so older clients, render paths, and review surfaces can replay the full candidate context.
- `editIntent`: structured edit-intent object described below.
- `idempotencyKey`: optional client-supplied key for replay-safe edit job creation.

If `sourceClipIds` is present, every entry must reference a clip in `clips`. The edit engine plans and renders from the selected IDs after team filtering. Responses continue to echo the full candidate clip payload as `candidateClips`.

## Structured Edit Intent

`editIntent.schemaVersion` is `edit-intent-v1`.

Required intent fields:

- `style`: one of `personal_highlight`, `full_game_highlight`, `coach_review`, `recruiting_reel`, `cinematic_mixtape`, `nba_recap`, `team_highlight`, `defense_focus`, `custom`.
- `pace`: one of `fast`, `balanced`, `cinematic`, `coach_review`, `deliberate`.
- `audioPreference`: one of `music_forward`, `game_audio`, `balanced`, `muted`.
- `chronology`: one of `best_first`, `chronological`, `story_arc`, `coach_review`.
- `captionDensity`: one of `minimal`, `clean`, `medium`, `high`.
- `hardConstraints`: `requireVisibleOutcome`, `requireFullPlayContext`, `rejectDuplicates`, `rejectDeadBall`, `defenseOnly`, `selectedTeamOnly`, and `maxCaptionCharacters`.

Existing prompt UI maps into this schema on iOS. Backend clients that omit `editIntent` still get a server-derived schema from legacy prompt/template defaults, preserving the validated `EditPlan` flow.

## Edit Job Responses

`EditJobResponse` and `EditPlanResponse` echo:

- `assetId`
- `sourceObjectKey`
- `sourceClipIds`
- `editIntent`
- `candidateClipCount`
- `candidateClips` on create/status responses

`EditPlan` remains the validated render contract and must pass backend validation before render.

## Durability

Edit job payloads and plans are persisted to render storage under the existing durable editing namespace. Edit creation idempotency keys are indexed in the durable store, so retrying a create request after service reload returns the original edit job when the install owner matches.

Render jobs continue to use the existing durable render state store, leases, indexes, and render idempotency flow.

## Agent Sync Notes

Agent A upload integration should pass `assetId` at the edit-job level and keep `sourceObjectKey` until the compatibility gate closes. Clip payloads remain clip-centric.

Agent C UI integration should pass selected clip IDs as `sourceClipIds`, keep the full candidate clip list in `clips`, and use status copy aligned to: preparing edit plan, plan ready, queued, rendering cloud MP4, preparing preview and share access.
