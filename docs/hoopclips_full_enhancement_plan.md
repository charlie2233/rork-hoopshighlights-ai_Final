# HoopClips Full Enhancement Plan

Date: 2026-06-21
Branch: main

## Product target

HoopClips should feel like a few-tap basketball highlight maker, not a control panel. The app should guide a user from import to finished highlights with clear progress, low text density, safe recovery when analysis is not ready, and cloud-owned AI/edit/render behavior.

## Non-negotiable architecture

- Cloud owns analysis, GPT clip selection, edit planning, revisions, template strategy, rendering, storage, and policy.
- iOS owns upload/import, status, review controls, export configuration, preview, download, share, and recovery UX.
- iOS may use AVFoundation for playback, import/download handling, previews, temporary fallback, and share/save support only.
- Do not move production AI analysis, edit composition, or final rendering into iOS.

## Current launch blockers

- Latest code still needs a fresh TestFlight upload and installed-device proof.
- Real iPhone smoke still needs proof for import, upload, analyze, Review, Export, AI Edit, revision, preview, and share.
- Long-video upload still needs real-device proof for backgrounding and progress behavior.
- AI Analysis crash reports need a simulator/real-device reproduction pass on the latest build.
- App icon/logo needs confirmation in the installed TestFlight build.
- Audio/mute behavior needs phone proof across Player, Review, Export, History, and AI Edit previews.

## P0 reliability and trust

1. Make AI Analysis safe under every app state.
   - If analysis is active, Review shows "analyzing, please wait" with progress and ETA.
   - If no reviewable clips exist, Review shows a recovery card, not a crash.
   - Crash telemetry must include last tab, project id hash, clip counts, analysis status, and suggested fix.

2. Make upload feel alive and recoverable.
   - Show upload size, optimized size, elapsed time, and estimated remaining time.
   - Keep Cancel and Retry simple and protected by confirmation.
   - Add background upload/chunked upload as the long-term fix for 30 to 60 minute videos.

3. Keep proof tooling out of the normal user path.
   - Smoke proof controls can exist for internal builds.
   - Normal users should see clips, status, and clear next actions, not QA/debug cards.

## P1 simple product UX

1. Player
   - Keep one top pipeline tracker: Uploading -> Analyzing -> Review ready.
   - Avoid duplicate progress cards.
   - Keep the primary action obvious: Analyze, Cancel, Retry, or Review.

2. Review
   - One clip at a time.
   - Swipe left for Nah and right for Keep.
   - Buttons remain big, obvious, and low-word-count.
   - Feedback tags stay quick: duplicate, wrong team, bad window.
   - Auto-advance after Keep/Nah and show undo toast.

3. Export
   - One primary "make my highlight" path.
   - Prompt box maps to structured intent only.
   - Keep advanced settings tucked away.

4. History and Settings
   - Use real project names instead of random codes.
   - Use fewer sections and fewer repeated badges.
   - Keep launch/debug tools in a compact internal-only area.

5. Rookie guide
   - Keep language consistent with the app language.
   - Make coach marks look native and product-designed, not AI-generated.
   - Settings should replay the guide.

## P1 AI highlight quality

1. Candidate generator should be high recall but deduped.
   - Collapse near-identical/overlapping clips before review/export.
   - Combine scores for duplicate windows instead of showing redundant clips.
   - Prefer longer, watchable windows over tiny fragments.

2. GPT should act as the semantic editor/director.
   - Input: compact clip metadata plus sampled keyframes.
   - Output: strict JSON with keep, score, event, outcome, caption, story role, and suggested edit.
   - Backend validation remains the safety gate.

3. Team selection should be fast and forgiving.
   - If team scan takes too long, fall back to sampled frames and ask GPT for visible team hints.
   - Support personal highlight mode without forcing full team detection.

## P2 polish

- Confirm the selected logo is actually wired into app icon assets and TestFlight build metadata.
- Remove black-screen or hard-cut effects around made shots unless the user selects a dramatic template.
- Make bottom bar visible first; liquid glass only stays if icons remain readable.
- Improve push/local notification after analysis finishes and Review is ready.

## Implementation order

1. Stabilize AI Analysis and Review crash recovery.
2. Simplify Player and Review surfaces until the flow feels like a few clicks.
3. Add background/chunked upload design and backend contract.
4. Tighten GPT-led highlight selection and dedupe scoring.
5. Finish logo/icon and TestFlight proof.
6. Run full real-device launch smoke.

## This slice

- Added this current plan so the broad enhancement goal has a single source of truth.
- Kept Review proof tooling internal-only and quieter.
- Next cleanup should continue removing stacked/internal UI from the main product path.
