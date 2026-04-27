# HoopClips Codex Rules

## Cloud-First Video Architecture

All HoopClips video analysis, AI edit planning, and production rendering should be cloud-backend owned.

The iOS app is the control surface for:
- upload
- style and target-length selection
- generated clip/edit-plan review
- job status
- finished MP4 preview
- download
- share sheet and opening exports in CapCut, iMovie, Adobe, Files, Photos, or other editors

Do not implement new AI editing, final video rendering, or production analysis as an iOS/AVFoundation feature. AVFoundation is allowed in iOS only for playback, preview, import/download handling, temporary launch-safe fallback, and share/save support while cloud gates are still locked.

## Launch Gate

Cloud-first is the product architecture. Public cloud cutover is still gated by production auth, storage, observability, render reliability, and the Phase 4h confirmed-label gate. Do not turn cloud ML or cloud rendering public by changing thresholds, secrets, or launch mode without the explicit gate decision.

## Repo Hygiene

Before making changes, sync with the remote branch. After changes, commit and push the work. Preserve unrelated untracked files and dirty worktree state.
