# Phase UX3 Pro Template Pack

## Branch

- Branch: `codex/phase-ux3-pro-template-pack`
- Base commit at implementation start: `aa6ec64`
- Final commit: recorded in git history for this document update

## Goal

Convert the existing locked Pro template cards into real cloud-renderable template packs while preserving the cloud-first HoopClips architecture. iOS remains the control surface for selecting templates, starting jobs, viewing status, previewing MP4 output, and sharing. All template application, policy checks, edit planning, revision planning, validation, and FFmpeg rendering remain backend-owned.

## Template IDs

| Template ID | Preset wire value | Default aspect | Durations | Premium | Notes |
| --- | --- | --- | --- | --- | --- |
| `personal_highlight_v1` | `personal_highlight` | `9:16` | `15, 30, 45, 60, 90, 120, 180, 270` | No | Existing free template |
| `full_game_highlight_v1` | `full_game_highlight` | `16:9` | `60, 90, 120, 180, 240, 270` | No | Existing free template |
| `coach_review_v1` | `coach_review` | source/`16:9` | `60, 120, 180, 240, 270` | No | Existing free template |
| `recruiting_reel_pro_v1` | `personal_highlight` | `9:16` | `45, 60, 90, 120, 180, 240, 270` | Yes | Player/recruiting style, clean hype captions, stronger slow motion, clean export |
| `cinematic_mixtape_pro_v1` | `personal_highlight` | `9:16` | `30, 45, 60, 90, 120, 180, 270` | Yes | Premium social edit, cinematic pacing, speed ramp/punch zoom profile, clean export |
| `nba_recap_pro_v1` | `full_game_highlight` | `16:9` | `90, 120, 180, 240, 270` | Yes | Broadcast recap, chronological game-flow, scorebug/lower-third styling, clean export |
| `team_highlight_pro_v1` | `full_game_highlight` | `16:9` | `90, 120, 180, 240, 270` | Yes | Team package recap, balanced game-flow, moderate effects, clean export |

Each Pro template has JSON assets under `services/editing/templates/<template_slug>/` for template defaults, captions, colors, watermark metadata, title cards, outro metadata, and lower-thirds where applicable.

## Pro Gating

- Free users cannot create or render Pro templates. Backend failures use `premium_template_required`.
- `internal` and `dev` tiers can create and render Pro templates for staging/test smoke without RevenueCat.
- `pro` tier requires `HOOPS_AI_EDIT_PRO_EXPORTS_ENABLED=true`.
- `pro` tier also requires server-side RevenueCat entitlement verification for entitlement `pro`.
- Missing RevenueCat app user ID fails as `pro_entitlement_required`.
- Missing RevenueCat verifier secret fails closed with `revenuecat_verifier_unconfigured`.
- RevenueCat network or parse failures fail closed with `revenuecat_verifier_unavailable`.
- RevenueCat negative verification fails with `pro_entitlement_unverified`.
- No Stripe fallback is used for iOS digital Pro template unlocks.

## RevenueCat Verifier

Server-side envs:

- `HOOPS_REVENUECAT_REST_API_KEY` or `REVENUECAT_REST_API_KEY`
- `HOOPS_REVENUECAT_PRO_ENTITLEMENT_ID`, default `pro`
- `HOOPS_REVENUECAT_API_BASE_URL`, default `https://api.revenuecat.com`; values with a trailing `/v1` are normalized

The editing service calls RevenueCat REST API v1 `GET /subscribers/{app_user_id}` and checks the configured entitlement. Entitlement is considered active when `expires_date` is null, in the future, or a valid grace period is in the future.

## iOS UX

- Free users still see Pro template cards with lock/Pro messaging.
- Free taps open the existing Pro information/paywall path and do not start rendering.
- Pro/internal state makes the four Pro cards selectable.
- Selecting a Pro template updates selected template ID, default aspect ratio, and length options.
- Edit creation and render requests send the real `templateId`.
- RevenueCat app user ID is included in cloud edit and render requests when available.
- Receipts and timelines show the selected Pro template display name and clean-export/no-watermark policy when the policy allows it.

## Renderer Behavior

- FFmpeg remains the core renderer.
- Render logs include the template signature and `premiumOnly`.
- Existing template-driven caption, audio, effects, outro, and watermark fields are reused.
- Pro clean-export semantics disable watermark/outro when policy does not require them and the template outro duration is `0`.
- No Remotion runtime, Canva runtime, or local AVFoundation composition is introduced.

## Validation

Commands run:

- `cd ios/backend && .venv/bin/python -m unittest tests/test_edit_plan_agent.py`
- `ios/backend/.venv/bin/python -m unittest services/editing/tests/test_editing_service.py`
- `cd services/control-plane && npm run typecheck`
- `cd services/control-plane && npx tsx --test test/control-plane-editing-proxy.test.ts`
- `jq empty` over all new Pro template JSON files
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux3-debug-dd CODE_SIGNING_ALLOWED=NO build`
- `xcodebuild -quiet -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux3-debug-dd CODE_SIGNING_ALLOWED=NO build-for-testing`
- `xcodebuild -quiet -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Release -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux3-release-dd CODE_SIGNING_ALLOWED=NO build`

## Live Smoke

Representative local renderer smoke is covered by `services/editing/tests/test_editing_service.py`, including `cinematic_mixtape_pro_v1` rendering and a render log signature check.

Live Worker -> Cloud Run -> R2 smoke was not rerun in this branch because this local branch has not been deployed to staging and CI/Worker deploy automation still depends on operator-provided Cloudflare auth. Required live smoke after deploy:

1. Enable staging/internal or verified Pro config.
2. Deploy Worker and editing service from this branch.
3. Start `cinematic_mixtape_pro_v1` or `recruiting_reel_pro_v1`.
4. Confirm render reaches `rendered`.
5. Confirm final MP4 downloads and passes `ffprobe`.
6. Confirm `render_log.json` includes `templateId`, `premiumOnly`, policy, and clean-export metadata.
7. Confirm no full presigned URL is logged.

## Remaining Rollout Blockers

- Deploy this branch to staging before live Pro-template smoke.
- Configure `HOOPS_REVENUECAT_REST_API_KEY` in the editing service.
- Approve and set `HOOPS_AI_EDIT_PRO_EXPORTS_ENABLED=true` for the target environment.
- Confirm the iOS RevenueCat app user ID is stable and bound to the backend user identity before external beta.
- Keep production rollout gated until real RevenueCat, Cloudflare, R2, Sentry, and Statsig configs are approved.
