# HoopClips Full Enhancement Roadmap

Last updated: 2026-06-21

## Goal

Make HoopClips easier to test, easier to use, and safer to launch by finishing the remaining product, upload, review, AI quality, TestFlight, and launch-proof work without breaking the cloud-first architecture.

## Non-negotiable architecture

- Cloud owns video analysis, team detection, GPT clip selection, edit planning, revisions, policy, rendering, storage, and final MP4 production.
- iOS owns upload/import, user choices, review decisions, progress/status, preview, download/share, and recovery UI.
- iOS must not become the production AI analysis, composition, or final rendering engine.
- Local AVFoundation use is allowed only for import, playback, preview, temporary export-source preparation, download/share, and launch-safe fallbacks.
- No logs or reports should include secrets, full presigned URLs, object keys, or local file URLs.

## Current working lanes

### Lane 1: Upload and background reliability

Purpose: long videos must not feel frozen, and app switching during upload should not make the user lose progress.

Done recently:

- Background-upload resume plumbing exists.
- Upload progress proof copy exists.
- Cancel/retry upload UX exists.
- Optimized upload source preparation exists for large videos when policy recommends it.
- Stale optimized upload cache cleanup exists.
- Several strict-concurrency risks in upload telemetry and resume plumbing have been reduced.

Remaining work:

- Run a simulator build to prove the latest upload/concurrency patches compile.
- Prove long-video upload with a real Troy-style source.
- Prove app switching during upload and returning to a sane pipeline state.
- Add server-guided upload mode so backend can recommend original, optimized, or chunked upload.
- Add stale background-session cleanup proof for orphaned session identifiers.

Acceptance evidence:

- Simulator build succeeds on current `main`.
- Real phone upload shows percent, MB transferred, speed, elapsed time, and useful wait copy.
- Switching apps during upload does not lose the project or hide progress.
- Proof text confirms no secrets, presigned URLs, object keys, or local file URLs.

### Lane 2: AI Analysis crash and recovery

Purpose: tapping AI Analysis must never crash, and Review must show the correct waiting/recovery state.

Known state:

- Simulator short-video path previously built, analyzed, and opened Review successfully.
- User-reported crash likely involves real cloud upload, long-video state, or in-progress analysis state, not just the button tap alone.

Remaining work:

- Reproduce with the long Troy video path.
- Keep Review in an analyzing/wait state while upload or analysis is active.
- Show recovery only when analysis is actually idle or failed.
- Add a visible reason when Review is unavailable.
- Preserve crash breadcrumbs, but mark benign blocked-tab guards as non-crash events.

Acceptance evidence:

- AI Analysis button does not crash on simulator with imported source.
- AI Analysis button does not crash on TestFlight phone with long source.
- Formspree crash breadcrumb either stops appearing or points to a concrete guarded state.
- Review tab shows `Analyzing, please wait` during active analysis, not `rerun`.

### Lane 3: Review UX simplification

Purpose: users should not feel like they are solving calculus just to keep or skip clips.

Current direction:

- One clip at a time.
- Big Keep and Nah actions.
- Swipe right for Keep and left for Nah.
- Auto-advance after each decision.
- Undo toast after each decision.
- Clip scrubber and live progress under preview.
- Quick feedback tags: duplicate, wrong team, bad window.

Remaining work:

- Reduce stacked text in Review.
- Make feedback tags persist into clip/review data.
- Send feedback tags to backend accuracy reports.
- Make empty/unsafe Review state show a clear recovery card.
- Ensure Review never crashes when clips are empty, stale, or unsafe.

Acceptance evidence:

- Reviewer can process clips with one thumb.
- Keep/Nah changes are undoable.
- Feedback tags survive navigation and app restart.
- Accuracy report receives feedback tags.

### Lane 4: Player and upload status UX

Purpose: upload/analyzing status should be obvious but not duplicated or visually stacked.

Remaining work:

- Keep one top pipeline tracker: Uploading -> Analyzing -> Review ready.
- Avoid duplicate progress between card and details.
- Show approximate remaining time with honest caveat that long uploads can take a while.
- Make cancel ask for confirmation on the main screen.
- Add retry after cancel.
- Keep slow-upload help hidden until it is actually useful.
- Fix source audio/mute behavior.

Acceptance evidence:

- Player top pipeline uses distinct but restrained status colors.
- Only one primary progress message is visible at a time.
- Audio toggle affects playback as expected.
- Cancel/retry path is clear and safe.

### Lane 5: History and project persistence

Purpose: switching to History must not destroy import or analysis progress.

Remaining work:

- Preserve current project state while navigating tabs.
- Use human-friendly project names instead of random codes.
- Show useful status per project: imported, uploading, analyzing, review ready, exported.
- Support reopening an in-progress or completed project without losing clip decisions.

Acceptance evidence:

- Import progress survives tab switch to History and back.
- Project names are readable.
- Saved decisions and feedback tags reload correctly.

### Lane 6: Export and AI Edit UX

Purpose: export should feel like a creator tool, not a settings maze.

Remaining work:

- Keep Export status card/details non-duplicative.
- Preserve no black-screen effect around made-shot/recovery clips unless user explicitly chooses it.
- Keep user prompt textbox simple: `Tell HoopClips how to edit this`.
- Map user text to structured intent only; never let prompt bypass backend validation.
- Keep template choices clear and not stacked.
- Verify More Hype revision path.

Acceptance evidence:

- Export preview has no unwanted black-screen transitions.
- Prompt textbox produces validated backend intent.
- AI Edit render and revision produce playable previews.

### Lane 7: AI clip quality and accuracy

Purpose: fewer redundant clips, better event windows, better team focus, and better human trust.

Current target architecture:

- CV/runtime creates a high-recall candidate pool.
- GPT acts as final semantic editor/director over compact metadata and sampled frames.
- Backend validator enforces safety, schema, policy, and timestamp sanity.
- FFmpeg renders deterministically in cloud.

Remaining work:

- Stronger temporal dedupe and overlap collapse before review/export.
- Possession-level suppression for near-identical clips.
- Better selected-team scan reliability.
- Better shot outcome evidence.
- Keep uncertain clips available for review instead of silently overclaiming.
- Add more labeled real footage cases after Troy.

Acceptance evidence:

- Near-identical time windows collapse before Review.
- No opponent leakage in selected-team mode.
- Miss-to-made drift is reduced.
- Launch report can show useful/accurate selection quality from real labels.

### Lane 8: Rookie guide and settings

Purpose: new users should understand the app in a few taps, and returning users should replay the guide.

Remaining work:

- Keep rookie guide language consistent with app language.
- Make coach marks feel native, not AI-generated.
- Settings button should replay the guide.
- Coach marks should point at exact tabs/buttons.
- Keep settings visually strong but not cluttered.

Acceptance evidence:

- First-launch guide appears once.
- Settings replay starts the guide.
- Coach marks point at exact UI controls.
- Copy changes with selected language.

### Lane 9: Branding and app icon

Purpose: the TestFlight icon and in-app logo must match the accepted HoopClips identity.

Remaining work:

- Ensure the exact selected logo is used in app icon assets.
- Ensure all icon sizes are valid, especially 1024x1024 App Store icon.
- Ensure TestFlight build includes the latest icon.
- Keep in-app logo aligned with the app icon style.

Acceptance evidence:

- App Store Connect upload accepts icon assets.
- TestFlight displays the selected logo.
- In-app logo visually matches the selected mark.

### Lane 10: TestFlight and launch proof

Purpose: launch readiness must be based on proof, not vibes.

Remaining work:

- Bump build after current changes.
- Upload current `main` to TestFlight.
- Run real iPhone smoke.
- Document job IDs, render IDs, revisions, backend versions, and screenshots.
- Confirm production/staging route state before public launch.

Acceptance evidence:

- TestFlight upload succeeds for current commit.
- Real iPhone smoke covers import, upload, analysis, review, export, AI Edit, revision, preview, and share/open-in.
- Evidence is documented in `docs/` with commit, build number, screenshots or proof notes, and blockers.

## Recommended execution order

1. Run simulator build on current `main` to prove recent upload/concurrency patches.
2. Fix any build blockers immediately.
3. Bump build and upload current `main` to TestFlight.
4. Run real iPhone smoke with a short video.
5. Run real iPhone or simulator smoke with the long Troy video.
6. Patch the exact AI Analysis long-video crash if reproduced.
7. Simplify Review/Player/Export stacked UI based on actual smoke pain.
8. Finish feedback-tag persistence and backend accuracy reporting.
9. Strengthen GPT-led reranking and temporal dedupe.
10. Refresh launch-readiness docs and production/staging proof.

## Subagent-ready task splits

Use subagents only when work is independent enough to avoid file conflicts.

Good subagent lanes:

- Upload reliability reviewer: inspect `CloudAnalysisService` warnings and propose isolated fixes.
- Review UX implementer: simplify Review page interactions and empty states.
- Export UX implementer: remove duplicate status copy and black-screen effect options.
- Accuracy pipeline implementer: temporal dedupe, overlap scoring, feedback report payload.
- TestFlight proof collector: build/upload monitoring and evidence doc updates.
- Branding implementer: asset catalog, icon dimensions, in-app logo consistency.

Avoid parallel subagents when multiple tasks touch the same Swift view model or `CloudAnalysisService.swift` at the same time.

## Always report remaining blockers

Current recurring blockers to report until cleared:

- Current `main` needs simulator build proof after recent upload/concurrency patches.
- Current `main` needs TestFlight upload.
- Real iPhone TestFlight smoke is still needed.
- Long-video Troy upload/analysis/review proof is still needed.
- Audio/mute issue still needs reproduction and fix.
- Optimized upload needs real long-video proof.
- Full Review, Export, AI Edit, History, and Settings smoke is still open.
- Accuracy proof and production/staging proof remain open for public launch readiness.
