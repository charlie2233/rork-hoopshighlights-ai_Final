# HoopClips Future Plan

Date: 2026-06-02

## Product Direction

HoopClips should feel like a real basketball editing product: easy for players, parents, and coaches, but strong enough that the cloud editor makes serious highlight decisions. The main bet is still cloud-first AI editing:

- iOS is the control surface for import, team choice, Review, Export settings, status, preview, download, share, and user instructions.
- Cloud owns analysis, team attribution, GPT clip selection, EditPlan generation, revisions, rendering, storage, retention, and policy.
- GPT is the final semantic editor, but deterministic validators own timestamps, clip bounds, templates, watermark/outro, storage safety, and render safety.

## P0: Internal TestFlight Readiness

1. Real-device smoke
   - Install latest TestFlight build on a wired iPhone.
   - Import a large video.
   - Confirm upload copy tells users to keep HoopClips open until cloud handoff.
   - Confirm post-handoff copy tells users they can switch apps and reopen for real status.
   - Run cloud team scan, team selection, analysis, Review, AI Edit render, preview, revision, and share/open-in.

2. Preparing-video reliability
   - Photos import now uses file-backed transfers only, broader video content types, no `Data.self` fallback, copy work off MainActor, and active recovery for saved imports.
   - Confirm on a real device that closing/reopening is no longer needed for imports to appear.
   - Add device smoke evidence for 1GB+ and long iPhone camera videos.

3. Cloud version/render check reliability
   - Investigate export timeout on cloud editing version check.
   - Make version checks resilient with short timeout, clear retry, and no fake status.
   - Confirm staging Worker -> Cloud Run -> R2 render status path.

4. Submission evidence
   - Build Debug and build-for-testing locally.
   - Run backend tests locally to avoid GitHub Actions spend.
   - Use GitHub Actions only for final deploy/preflight or App Store upload.
   - Keep App Store Connect secrets in GitHub environment secrets only.

## P1: Highlight Accuracy

1. Team-first analysis
   - User chooses target team before analysis after quick cloud jersey-color scan.
   - Support one team or all teams.
   - Keep uncertain clips in Review instead of deleting them too early.
   - Include defense: blocks, steals, forced turnovers, and defensive stops are valid highlights.

2. Bigger candidate pool
   - Preserve more high-recall candidates before GPT.
   - Use deeper backfill for long edits up to 4:30.
   - Keep duplicate groups, audio peaks, watchability, team attribution, and outcome evidence in compact GPT context.

3. Audio reaction recall
   - Use very loud crowd/bench/whistle/audio-pop moments as recall hints.
   - Never accept audio-only scoring claims without sampled visual support.
   - Sample frames before and after the audio spike so GPT can judge the actual play.

4. GPT-led editor
   - Send only candidate clips and sampled keyframes, never full videos.
   - GPT selects/rejects clips, captions, story order, crop focus, and slow-motion suggestions.
   - Validators reject invented clip IDs, unsafe text, FFmpeg commands, bad timestamps, weak shot evidence, and contradicted outcomes.
   - Surface GPT work in AI Work Receipt with clean labels and no fake thinking.

5. Accuracy eval loop
   - Build a simple labeling bundle for clips: video preview, team target, event type, outcome, keep/reject, reason.
   - Include multi-angle or varied public basketball samples where licensing allows, plus user-provided internal test clips.
   - Track at least:
     - selected-team precision
     - selected-team recall
     - made/missed/block/steal outcome accuracy
     - boring/duplicate rejection rate
     - reviewer rescue rate for uncertain clips
   - Target 85%+ for confident automated keeps; uncertain clips can be lower confidence as long as they land in Review.

## P1: UX/Product Polish

1. Export simplification
   - Keep simple choices: template, target length, aspect ratio, side note.
   - Hide advanced knobs unless they are genuinely useful.
   - Keep one clear Share button after render.

2. Free acquisition
   - Free should feel useful enough to attract users.
   - Set free video-editing chances to 3.
   - Keep Pro value visible without making Free feel fake or unusable.
   - Free can include watermark/outro and shorter retention; Pro gets longer retention, priority, premium templates, and no-watermark path when entitlement is real.

3. Cloud Locker
   - Show latest renders, expiry, re-download, and re-render.
   - Free retention should be short but clear.
   - Pro retention can be longer after RevenueCat entitlement proof.

4. Compatibility
   - Keep text visible on small phones and larger Dynamic Type.
   - Remove low-value helper copy.
   - Use real status words, not fake ETA/thinking.
   - Continue testing tab drag, history formatting, project rename, sign-out confirmation, reset confirmation, and account-switch cleanup.

## P2: Pro and Scale

1. RevenueCat Pro
   - Finish real subscription products, entitlements, gating, and receipt verification.
   - Only enable Pro live render/template privileges after backend entitlement checks pass.

2. Pro templates
   - Recruiting Reel Pro
   - Cinematic Mixtape Pro
   - NBA Recap Pro
   - Team Highlight Pro
   - Add real template assets on backend only. No Remotion/Canva runtime inside iOS.

3. Manual editor
   - Timeline trim/reorder/caption edits as user commands to backend.
   - Cloud validator turns those commands into deterministic EditPlan patches.

4. Production backend cutover
   - Durable queues/leases for scaled render workers.
   - R2 lifecycle cleanup for old renders/logs/state.
   - Sentry, Statsig, RevenueCat, Cloudflare, GCP, and App Store Connect checks documented before public launch.

## Current Known Blockers

- Internal TestFlight installed-device smoke is still required.
- Preparing-video import reliability still needs real-device proof with large Photos videos.
- Cloud editing version check timeout needs device/staging proof.
- App Store submission should wait for real smoke evidence.
- Production cloud cutover remains gated by auth, storage, observability, render reliability, and confirmed-label/accuracy evidence.

## Operating Rules

- Prefer local validation over GitHub Actions until final CI/deploy proof.
- Use `[skip ci]` for local-only product/backend doc commits.
- Do not log secrets or full presigned URLs.
- Keep untracked root Xcode folders unstaged unless explicitly requested.
