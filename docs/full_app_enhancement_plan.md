# HoopClips Full App Enhancement Plan

Date: 2026-06-20
Starting commit: `43da8c40`

## Product direction

HoopClips should feel like this:

```text
Pick a video -> tell HoopClips what you want -> wait with honest progress -> review a few good clips -> get a clean shareable reel.
```

The app should not feel like this:

```text
Choose from too many technical options -> guess what the AI is doing -> lose progress -> wonder if upload died -> decode launch/debug language.
```

## Hard architecture rules

- Cloud owns analysis, team scan, GPT clip selection, edit planning, rendering, storage, revisions, policy, and final MP4 production.
- iOS owns import/upload, simple intent selection, review, status, preview, share/open-in, history, and proof/debug copy.
- Do not add local iOS production analysis or final rendering as a replacement for the backend path.
- Do not fake ETA, fake thinking, fake waits, or fake launch proof.
- Do not leak presigned URLs, local file paths, upload IDs, job IDs, object keys, upload headers, private keys, or raw secrets.

## Current state summary

Already built or heavily progressed:

- Cloud analysis and cloud AI Edit control surfaces.
- Review, Export, AI Edit, History, Settings, rookie guide, telemetry, and proof copy surfaces.
- Background/resumable upload proof tooling and app-switch proof handoff.
- Free/Pro copy, template packs, AI Edit prompt parsing, and revision flows.
- Real proof tooling for TestFlight/backend/phone evidence.

Still blocking launch quality:

- Current TestFlight build proof.
- Real iPhone smoke proof.
- Backend/staging deploy proof.
- Real background upload app-switch proof.
- Accuracy proof on real labeled footage.
- Continued reduction of stacked UI and decision fatigue.

## Enhancement principles

- Fewer choices on first screen; advanced options only after intent is clear.
- Every long operation needs clear state, honest progress, cancel/retry, and recovery.
- Review should be fast: one clip at a time, keep/nah, quick tags, undo.
- Export should be simple: "Make my reel" before technical controls.
- History should preserve work, explain status, and make resume obvious.
- Settings should be proof/support, not a junk drawer.
- Any proof/reporting surface must be sanitized by default.

## Phase 1: Make the main flow simpler

Goal:

```text
Users should be able to get from video import to AI Edit without reading stacked technical copy.
```

Tasks:

- Simplify Player import/upload card language.
- Keep background upload/progress visible but compact.
- Make personal-highlight intent obvious for solo/player-focused videos.
- Keep team scan optional-feeling: if no teams are found quickly, continue without trapping the user.
- Make Review unavailable states say exactly what is happening: uploading, analyzing, no clips, or needs retry.

Files likely touched:

- `ios/HoopsClips/HoopsClips/Views/VideoPlayerView.swift`
- `ios/HoopsClips/HoopsClips/Models/VideoImportStatusCopy.swift`
- `ios/HoopsClips/HoopsClips/Models/CloudAnalysisProgressCopy.swift`
- `ios/HoopsClips/HoopsClips/Models/AIEditQuickPromptLibrary.swift`
- `ios/HoopsClips/HoopsClips/ContentView.swift`

## Phase 2: Make Review feel like a fast clip deck

Goal:

```text
Review should feel like TikTok-style clip triage, not a spreadsheet.
```

Tasks:

- One clip primary view.
- Big Keep / Nah actions.
- Auto-advance after decision.
- Swipe right = Keep, swipe left = Nah.
- Undo toast after each decision.
- Scrubber and live playback progress.
- Quick tags: duplicate, wrong team, bad window.
- Persist tags into review data and send to backend accuracy reports.
- Collapse redundant clips in the same timeframe before review/export.

Files likely touched:

- `ios/HoopsClips/HoopsClips/Views/ReviewView.swift`
- `ios/HoopsClips/HoopsClips/Models/Clip.swift`
- `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`
- backend accuracy/report scripts where review tags are exported

## Phase 3: Make upload/background behavior truly calm

Goal:

```text
Huge videos should not feel frozen, and switching apps should not feel dangerous.
```

Tasks:

- Keep Uploading -> Analyzing -> Review ready pipeline visible and compact.
- Show real upload progress, speed, ETA when known.
- Add cancel/retry with confirmation.
- Preserve imported project if user visits History during upload.
- Continue background/resumable upload proof path.
- Add visible survived-background badge only after real proof signal.
- Add optional pre-upload compression later if backend and product policy allow it.

Files likely touched:

- `ios/HoopsClips/HoopsClips/Services/CloudAnalysisService.swift`
- `ios/HoopsClips/HoopsClips/Models/CloudAnalysisProgressCopy.swift`
- `ios/HoopsClips/HoopsClips/Views/VideoPlayerView.swift`
- `ios/HoopsClips/HoopsClips/Views/HistoryView.swift`

## Phase 4: Make Export / AI Edit a coach, not a cockpit

Goal:

```text
Users describe the reel they want, and HoopClips handles the setup.
```

Tasks:

- Keep "Tell HoopClips how to edit this" as the primary mental model.
- Expand quick prompts for common jobs:
  - personal highlight
  - team recap
  - defense
  - recruiting
  - longer 4:30 reel
  - NBA recap style
- Keep technical controls secondary.
- Show a short "Smart setup from note" preview.
- Keep backend validation strict.

Files likely touched:

- `ios/HoopsClips/HoopsClips/Views/ExportView.swift`
- `ios/HoopsClips/HoopsClips/Views/AIEditView.swift`
- `ios/HoopsClips/HoopsClips/Models/AIEditQuickPromptLibrary.swift`
- `ios/HoopsClips/HoopsClips/Services/CloudEditService.swift`

## Phase 5: Make History reliable

Goal:

```text
Users should never feel they lost work by switching tabs or leaving the app.
```

Tasks:

- Preserve active import/upload/analysis progress when entering History.
- Use better project names from video metadata/date/team when available.
- Show project state: importing, uploading, analyzing, review ready, exported.
- One obvious resume action.
- Keep Cloud Locker/render-history path clear without overpromising.

Files likely touched:

- `ios/HoopsClips/HoopsClips/Views/HistoryView.swift`
- `ios/HoopsClips/HoopsClips/Services/ProjectHistoryStore.swift`
- `ios/HoopsClips/HoopsClips/Models/ProjectHistory.swift`
- `ios/HoopsClips/HoopsClips/Models/VideoImportStatusCopy.swift`

## Phase 6: Make onboarding and Settings useful

Goal:

```text
New users learn by doing, and Settings helps recover/prove what happened.
```

Tasks:

- Keep rookie guide replayable.
- Make coach marks feel designed, not AI-generated.
- Keep guide language tied to the active language.
- Keep Settings proof tools compact.
- Add support/proof copy only where needed.

Files likely touched:

- `ios/HoopsClips/HoopsClips/ContentView.swift`
- `ios/HoopsClips/HoopsClips/Views/SettingsView.swift`
- `ios/HoopsClips/HoopsClips/Services/AppLanguageStore.swift`

## Phase 7: Accuracy and backend quality

Goal:

```text
AI-selected clips should be useful, team-correct, non-duplicative, and watchable.
```

Tasks:

- Improve selected-team scan reliability.
- Keep candidate pool high recall, then use GPT as final semantic editor.
- Add stricter candidate-quality filters.
- Add possession/time-overlap dedupe.
- Improve shot outcome evidence.
- Preserve uncertain clips for human review.
- Generate real labeled accuracy reports.

Backend/cloud files likely touched:

- `services/control-plane`
- `services/inference`
- `services/editing`
- accuracy/evaluation scripts under `scripts/`

## Phase 8: Launch proof

Goal:

```text
A current TestFlight build on a real iPhone proves import -> upload -> analysis -> Review -> AI Edit -> render -> preview -> share.
```

Tasks:

- Deploy current backend/staging.
- Upload current TestFlight build.
- Run real iPhone smoke.
- Run background upload app-switch proof.
- Run accuracy proof.
- Generate final launch evidence.

Important proof docs:

- `docs/background_upload_phone_tester_checklist.md`
- `docs/background_upload_real_proof_handoff.md`
- `docs/background_upload_current_tip_proof_packet.md`

## Subagent plan

Use subagents after this plan for independent phase chunks:

- Implementation subagent: one phase or one file cluster at a time.
- Spec reviewer subagent: confirm the phase matches this plan and architecture rules.
- Code quality reviewer subagent: check for regressions, overbuilt UI, and cloud-first violations.

Do not dispatch parallel implementers against overlapping SwiftUI files.

## First implementation slice

Start small:

```text
Add a Personal quick prompt for solo/player-focused highlight reels.
```

Why:

- It supports users who only care about one player.
- It avoids forcing team scan/team recap thinking when the video is personal.
- It does not change backend architecture; it only sends structured user intent through the existing AI Edit prompt path.
