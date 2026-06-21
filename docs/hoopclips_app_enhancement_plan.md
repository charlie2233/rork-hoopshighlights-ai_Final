# HoopClips App Enhancement Plan

This document tracks the active "make the app good" goal in repo form so future work is not trapped in chat history.

## Product direction

HoopClips should feel like this:

- Pick a video.
- Let cloud analysis run without babysitting the app.
- Review a simple stack of good clips.
- Keep or reject clips fast.
- Make an AI reel without confusing settings.
- Export/share with no dead black screens, no fake progress, and no mystery crashes.

The architecture stays cloud-first:

- iOS uploads, reviews, configures, previews, shares, and displays status.
- Backend owns analysis, GPT selection, edit planning, revisions, rendering, storage, and policy.
- iOS must not add production local analysis, local final rendering, or local composition as a substitute for cloud.

## Recently completed slices

- Background upload proof now recognizes both initial URLSession wake events and reattached session events.
- Large-video multipart upload concurrency increased from 2 to 3 lanes.
- Multipart upload lanes now adapt to network conditions.
- Slow, stalled, retrying, or waiting uploads now show calmer "still alive" copy.
- Required cloud-render outro no longer uses a near-black slate; it is now a bright HoopClips end card.
- Saved project titles are cleaner and less random-looking.
- Review, History, Settings, Export, and AI Edit copy has been simplified in several places.
- Review top stack has been reduced: status cards collapsed, progress folded into the status strip, filters hidden when not useful, advanced filters moved behind More, and the AI Edit entry is now one compact row.
- AI Edit prompt chips now prioritize common edit intents without adding more choices: Hype, Solo, Team, Defense, Recruit, Recap, and Long.
- Solo/personal highlight flow is clearer and does not force team scan language.
- Team scan fallback copy explains that HoopClips will use all teams when teams are unclear.

## Active launch blockers

- Latest `main` needs Swift build validation after recent upload/network changes.
- Recent Review SwiftUI declutter needs simulator confirmation before more Review layout work.
- Recent AI Edit prompt/copy updates need simulator confirmation before more AI Edit UI work.
- AI Analysis crash report needs simulator reproduction on current code.
- Background upload needs real iPhone app-switch proof with a long video.
- No-black-outro render needs cloud render smoke proof.
- Latest build needs TestFlight upload after validation.
- Real iPhone end-to-end smoke still needs proof on the newest build.
- Production/staging deploy proof remains separate from local code readiness.

## Next implementation order

1. Build and simulator safety pass.
2. AI Analysis crash reproduction and fix if current code still crashes.
3. Player audio/mute fix and clear audio-unavailable state.
4. Review-page validation pass: confirm the compact Review screen builds, scrolls, swipes, scrubs, keeps/nahs, undo works, and empty/analyzing states are correct.
5. Export and AI Edit validation pass: confirm compact status/progress copy, prompt-chip order, revision copy, and preview/share flow.
6. Background upload proof pass on real iPhone.
7. Cloud render smoke for no-black-outro output.
8. Bump build and upload TestFlight.
9. Real iPhone full smoke.

## UX principles

- Prefer one obvious primary action per screen.
- Avoid stacked paragraphs and redundant status cards.
- Show progress once, then show only the next useful action.
- Use short, human labels before technical details.
- Put technical proof behind copy buttons or diagnostics areas.
- Never fake ETA, fake thinking, or fake waits.
- Make recovery cards specific: what happened, whether work is saved, what to tap next.

## Upload and analysis experience

Target behavior:

- Huge videos should upload in chunks when the backend supports it.
- Uploads should survive app switch/reopen as much as iOS allows.
- Users should see percent, rough ETA, speed, and "still alive" copy.
- Cancel should confirm before stopping active upload/analysis.
- Retry/resume should skip already completed chunks.
- Low Data Mode should reduce upload lanes automatically.

Still needed:

- Real-device proof for app switch during upload.
- Better visible distinction between uploading, analyzing, and review-ready.
- Stalled upload proof should surface a short status card, not a wall of diagnostics.

## Review experience

Target behavior:

- Show one clip at a time.
- Swipe left for `Nah`.
- Swipe right for `Keep`.
- Buttons remain available for users who do not swipe.
- Auto-advance after each decision.
- Undo toast after each decision.
- Clip scrubber stays under preview.
- Quick feedback tags persist: duplicate, wrong team, bad window.
- Feedback tags flow into backend accuracy reports.

Still needed:

- Simulator proof on latest code.
- Confirm the compact status strip, hidden filters, AI Edit row, swipe gestures, scrubber, Keep/Nah, and undo toast all work after the declutter pass.
- Reduce remaining context/quick-action clutter only after the current Review layout passes simulator build.
- Verify unsafe/no-clip state shows "Analyzing, please wait" during analysis and recovery only after analysis ends.

## Export and AI Edit experience

Target behavior:

- Export should feel like "make my reel", not a backend console.
- AI Edit prompt should accept natural language and map it to structured intent.
- Status/progress should not duplicate the same information in multiple cards.
- Revisions should feel simple: More Hype, Cleaner, Shorter, Defense, Recruiting.
- Rendered videos should avoid black-screen effects unless the user asks for a dramatic transition.

Still needed:

- Cloud render smoke for bright outro.
- Verify mute/audio behavior in rendered preview and player preview.
- Confirm Export status card/details are not duplicating progress.
- Confirm AI Edit quick prompts are ordered as Hype, Solo, Team, Defense, Recruit, Recap, Long and do not crowd the screen.

## History and persistence

Target behavior:

- Going to History should not make users lose current import/upload progress.
- Project names should be readable.
- Resume should be obvious when source video exists.
- Missing-source recovery should be clear.

Still needed:

- Real-device smoke while importing/uploading, then switching tabs.
- Confirm current project stays visible while History is opened.

## Rookie guide and Settings

Target behavior:

- First-run tutorial should match current app language.
- Settings should include replay for the guide.
- Coach marks should point at exact tabs/buttons.
- Tutorial should feel designed, not AI-generated.

Still needed:

- Screenshot pass for current tutorial overlay.
- Confirm Settings tab visibility on latest build.

## Logo and brand

Target behavior:

- App icon should match the selected HoopClips logo direction.
- Logo should look like a basketball highlight app: play, hoop, motion, replay.
- Colors should feel tough and athletic, not random rainbow cards.

Still needed:

- Confirm latest TestFlight shows the selected logo.
- If not, audit all icon asset sizes and App Store/TestFlight cache path.

## Backend and accuracy

Target behavior:

- CV/runtime creates a high-recall candidate pool.
- GPT acts as final semantic editor/director on candidates.
- Backend validator remains the safety gate.
- FFmpeg renders deterministically in cloud.
- Temporal dedupe collapses near-identical clips before review/export.

Still needed:

- Fresh launch accuracy report if accuracy proof is revived.
- More real cases if the 85 percent proof gate is enforced again.
- Continue preserving human review labels as diagnostic evidence.

## Proof required before calling the goal complete

- Current `main` builds.
- Simulator AI Analysis no longer crashes.
- Real iPhone can upload/import a long video.
- App switch during upload does not lose progress.
- Review becomes ready or shows a correct waiting/recovery state.
- Keep/Nah review data persists.
- Export/AI Edit can render and preview.
- Rendered output does not have the unwanted black-screen outro/effect.
- Share/open-in works.
- TestFlight build is uploaded from current code.
- Remaining external deploy/staging gates are either cleared or documented as non-code blockers.

## Subagent candidates

Use subagents for these independent chunks once the build is stable:

- Review UI cleanup and gesture audit.
- Player audio/mute diagnosis.
- Export status simplification audit.
- Real-device smoke evidence packaging.
- Backend render smoke evidence packaging.
