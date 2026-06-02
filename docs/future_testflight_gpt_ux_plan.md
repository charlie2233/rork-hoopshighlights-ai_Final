# Future Plan: TestFlight, GPT-Led Highlights, UX Simplicity

Date: 2026-06-01

This plan defines the next work needed before HoopClips is considered ready for internal iOS TestFlight launch and broader beta proof. It keeps the product architecture cloud-first: the backend owns analysis, GPT clip selection, edit planning, policy, rendering, storage, and revisions; iOS remains the upload, review, status, preview, download, share, and control surface.

## Current Truth

- `main` is synced at `d8e9503` as of this plan.
- Cloud analysis and cloud rendering are the product path. iOS must not add new production video analysis, composition, or rendering.
- Existing unrelated root folders `HoopsClips.xcodeproj/` and `HoopsHighlightsAI.xcodeproj/` are not part of this plan and must not be staged accidentally.
- GitHub Actions minutes are budget-sensitive. Prefer local validation and `[skip ci]` for docs-only or local-only changes; reserve Actions for release, deploy, and confidence gates.
- No launch claim should be made from intent alone. Every launch claim needs evidence: device screenshots, job IDs, commands, logs, or smoke documentation, without exposing secrets or full presigned URLs.

## Product Principles

- Keep the app simple: import, choose team, review clips, export, preview, share.
- Keep visible copy readable on small phones, older iOS versions, and larger Dynamic Type.
- Do not fake AI thinking, fake ETA, artificial delays, or pretend backend work is happening. Status can say real things such as analyzing video, scanning teams, preparing candidate clips, waiting for cloud render, or render complete.
- Let GPT act as the semantic editor, but never let GPT replace deterministic validators, timestamp logic, CV/audio signals, or renderer safety.
- Cost is not the primary beta constraint, but limits, feature flags, fallbacks, and kill switches must remain configurable.

## Phase 0: Internal Launch Proof

Goal: prove the complete TestFlight path on a real iPhone before submission or wider invite.

Required smoke:

1. Install the TestFlight build.
2. Sign in.
3. Import or upload a real basketball video.
4. Run quick team scan and select a team or all teams.
5. Run cloud analysis.
6. Review clips, including uncertain clips.
7. Open Export with simplified defaults.
8. Add an optional side note such as "focus on defense" or "make it NBA recap."
9. Start AI Edit.
10. Wait for real backend job status.
11. Preview rendered MP4.
12. Request a revision such as More Hype.
13. Preview revised render.
14. Use one simple share button and verify share/open-in works.

Evidence to capture:

- Device, iOS version, build number, and app version.
- Screenshots for import, team selection, review, export, render status, preview, revision, and share.
- Backend job IDs and render IDs, with secrets and full presigned URLs redacted.
- Any timeout, crash, or confusing copy seen during the smoke.

Known launch risks to re-check:

- Cloud editing version check timeout during Export.
- Preparing video hang on large Photos imports.
- Random app quits.
- Account isolation after sign-out/sign-in.
- App title and hidden text issues across screens.
- Cloud render status and retry behavior.

## Phase 1: UX Simplicity And Readability

Goal: make the app feel like a real product for players, parents, coaches, and non-technical testers.

Work items:

- Simplify Export to a small number of obvious choices: format, length, template, and optional side note.
- Keep the side note structured: user text maps to safe intent, not raw renderer commands.
- Remove small low-contrast explanatory clutter where it does not help a decision.
- Make titles, project names, history rows, and empty states visually aligned.
- Let users rename projects by tapping the project title in History.
- Use a single simple share action instead of listing every possible target in the main UI.
- Add confirmation dialogs for sign-out and reset-to-default.
- Clear active video/player state when switching accounts.
- Verify bottom tab drag/swipe behavior is smooth and not accidental.
- Ensure the footer reads `Created by atrak.dev with love` with a real heart icon treatment, not broken text.

Acceptance:

- No important words are hidden on small phones.
- Layout survives larger Dynamic Type.
- Export can be understood without reading a long explanation.
- History formatting is clean and scannable.
- Sign-out and reset cannot be triggered by mistake.

## Phase 2: GPT-Led Highlight Accuracy

Goal: make GPT the final semantic highlight editor while keeping CV, audio, and deterministic renderer logic authoritative.

Pipeline:

1. Existing CV/runtime analysis creates a high-recall candidate pool.
2. Backend expands candidates for recall before GPT.
3. Backend extracts compact keyframes per candidate: start, event center, finish, and optional action or rim frame.
4. Backend builds `ClipEditContext` with clip metadata, team evidence, audio evidence, watchability, duplicate group, template, tier, and sampled keyframes.
5. GPT vision model returns strict Structured Outputs JSON.
6. Backend validates and repairs output only within safe policy bounds.
7. GPT-selected clips feed deterministic `EditPlan` generation.
8. Renderer executes the validated `EditPlan`.

Accuracy rules:

- Never send full videos to GPT.
- Never let GPT output FFmpeg commands.
- Never let GPT invent exact timestamps outside the candidate bounds.
- Blocks, steals, defensive stops, rebounds leading to fast breaks, made shots, crowd pops, and strong reactions can all be highlights.
- Team selection matters: users should choose a target team before full analysis, and `all teams` remains available.
- Quick team scan should label teams by visible color and confidence.
- If the system is uncertain but the clip might be valuable, keep it reviewable instead of silently deleting it.

Target beta quality:

- At least 85 percent useful highlight precision on a small manually labeled beta set.
- High recall for defense and crowd-reaction moments.
- Clear AI Work Receipt explaining the high-level signals used, without exposing private prompts or raw frame payloads.

## Phase 3: Agent Templates And Edit Planning

Goal: give GPT a real editor strategy for each template instead of a vague "make highlights" instruction.

Template system:

- `TemplatePack` controls render defaults, validation, aspect ratio, watermark/outro policy, and renderer-safe values.
- `AgentTemplateCookbook` controls GPT selection, rejection, ordering, captions, slow motion, crop focus, audio vibe, and story flow.

Priority templates:

- `personal_highlight_v1`: fast vertical personal hype reel.
- `full_game_highlight_v1`: clean 16:9 recap with game flow.
- `coach_review_v1`: chronological review, original audio, minimal effects.
- `recruiting_reel_pro_v1`: player showcase focused on skill clarity.
- `cinematic_mixtape_pro_v1`: high-energy social edit with dramatic moments.
- `nba_recap_pro_v1`: clean full-game recap tone.
- `team_highlight_pro_v1`: balanced team variety across offense and defense.

Revision behavior:

- More Hype, NBA Style, Shorter, Longer, and Focus Defense should produce validated `EditPlanPatch` JSON.
- Invalid patches are rejected or repaired by backend validators before rendering.
- Revisions must create real render jobs and real timeline states.

## Phase 4: Cloud Locker And Render History

Goal: make finished AI edits easy to recover, re-download, re-render, and share.

Work items:

- Show latest renders in My AI Edits or Cloud Locker.
- Show expiration clearly: short retention for Free, longer retention for Pro/internal.
- Allow re-download when the object is still available.
- Allow re-render from a validated plan when the original file and policy allow it.
- Avoid exposing full storage URLs in UI, logs, docs, or telemetry.

Acceptance:

- Users can find the last rendered edit without redoing the whole flow.
- Expiration copy is honest.
- Failed or expired renders have a clear next action.

## Phase 5: Operations And Release Gates

Goal: make launch operations boring, observable, and reversible.

Release checks:

- App Store Connect API key configured in GitHub environment secrets.
- Cloudflare deploy token scoped correctly and deploy preflight passing.
- Staging and production Worker URLs documented.
- Cloud Run editing URLs documented.
- R2 buckets and retention policy documented.
- Sentry and Statsig configured with no secret leakage.
- RevenueCat config checked, even if paid enforcement waits until after beta.
- Feature flags and kill switches verified:
  - `ai_edit_enabled`
  - `ai_edit_live_render_enabled`
  - `ai_edit_revisions_enabled`
  - `ai_edit_templates_enabled`
  - `ai_clip_gpt_editor_enabled`
  - `ai_clip_gpt_plan_edit_enabled`
  - `ai_clip_gpt_revision_enabled`

Runbook expectations:

- Each launch phase doc records commands, evidence, screenshots, job IDs, validation, and blockers.
- Use `[skip ci]` when safe to avoid unnecessary GitHub Actions spend.
- Run full CI only for deploy gates, release candidates, or when code changes need hosted validation.
- No force-push, destructive resets, or unrelated staging.

## Phase 6: Labeling And Beta Feedback

Goal: create a feedback loop that improves clipping accuracy with real examples.

Work items:

- Prepare a small manual labeling bundle with representative clips and multi-angle examples where available.
- Let testers label keep/reject, team, event type, made/missed outcome, defense value, and watchability.
- Track false positives, false negatives, and uncertain-but-reviewable clips.
- Compare CV-only ranking against GPT-led ranking.
- Feed results into candidate recall, audio reaction cues, team evidence, and GPT prompt/schema improvements.

Beta user perspectives to include:

- Player making social highlights.
- Parent who is not technical.
- College coach reviewing recruiting clips.
- Team manager posting a recap.
- Trainer focused on defense and skill clarity.

## Do Not Do Yet

- Do not submit to the App Store without real-device smoke evidence.
- Do not move Remotion or Canva runtime into iOS.
- Do not make iOS a production renderer or analyzer.
- Do not cut over production backend publicly without the launch gate.
- Do not enforce paid Pro subscriptions until RevenueCat entitlement behavior and Free limits are proven.
- Do not hide uncertain clips that may be valuable; keep them reviewable.

## Final Readiness Checklist

- Real iPhone smoke passes end to end.
- Export version check timeout is fixed or has a proven retry/fallback.
- Large video import no longer hangs on Preparing video.
- Account isolation clears visible video and project state correctly.
- App does not randomly quit during import, review, export, render status, or preview.
- Export is simple, with optional side note.
- Team selection and all-teams mode work before analysis.
- GPT-led clip selection improves highlight quality and keeps uncertain clips reviewable.
- Blocks, steals, defense, crowd pops, made shots, and strong reactions are represented.
- Cloud Locker or render history can recover recent edits.
- All important text is visible on supported phones and Dynamic Type sizes.
- Sentry, Statsig, storage, and secret checks pass.
- TestFlight build evidence is documented.
- GitHub Actions usage is controlled and intentional.
