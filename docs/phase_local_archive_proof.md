# Phase Local Archive Proof

## Goal

Create local evidence for the internal TestFlight submission path without spending additional GitHub Actions minutes. This phase targets the launch blocker where the submission preflight could not find an `.xcarchive` or `.ipa` artifact.

## Architecture Notes

- iOS remains the upload, review, export-control, status, preview, download, and share surface.
- Cloud/backend remains responsible for analysis, GPT clip selection, edit planning, revisions, rendering, and storage.
- No local iOS video analysis, composition, rendering, FFmpeg command generation, or fake backend state was added.
- No secrets, R2 credentials, API keys, or full presigned URLs were printed or stored.

## Commands

Current branch:

```bash
git status --short --branch
```

Local archive:

```bash
mkdir -p ios/build
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath ios/build/HoopsClips-InternalStaging-Build14.xcarchive \
  archive
```

Archive inspection:

```bash
ls -ld ios/build/HoopsClips-InternalStaging-Build14.xcarchive
plutil -p ios/build/HoopsClips-InternalStaging-Build14.xcarchive/Info.plist
plutil -p ios/build/HoopsClips-InternalStaging-Build14.xcarchive/Products/Applications/HoopsClips.app/Info.plist | rg 'CFBundleIdentifier|CFBundleShortVersionString|CFBundleVersion|MinimumOSVersion|CFBundleDisplayName'
```

Submission readiness preflight with local archive evidence:

```bash
python3 scripts/submission_readiness_preflight.py \
  --skip-live \
  --archive-path ios/build/HoopsClips-InternalStaging-Build14.xcarchive \
  --json
```

Background cloud-job copy check:

```bash
rg -n 'switch apps|cloud job|cloud handoff|upload' ios/HoopsClips/HoopsClips -g '*.swift'
```

## Evidence

- Local Release archive succeeded with `** ARCHIVE SUCCEEDED **`.
- Archive artifact exists at `ios/build/HoopsClips-InternalStaging-Build14.xcarchive`.
- Archive metadata:
  - app name: `HoopsClips`
  - bundle id: `atrak.charlie.hoopsclips`
  - version: `1.0.0`
  - build: `14`
  - architecture: `arm64`
- App Info.plist metadata:
  - display name: `HoopClips`
  - minimum iOS version: `17.0`
- Submission readiness preflight improved from the earlier local state by clearing the upload-artifact blocker:
  - status: `fail`
  - summary: `fail=6, pass=24, warn=3`
  - upload artifact: `pass`, `1 upload artifact candidate(s) found`

## Background Job Reminder Check

The app already keeps the user-facing copy honest about background behavior:

- During upload, the app tells the user to keep HoopClips open.
- After cloud handoff, the app tells the user they can switch apps and reopen HoopClips for real job status.
- AI Edit render states tell users it is safe to switch apps only once the cloud source/job is ready, queued, or rendering.

Relevant files:

- `ios/HoopsClips/HoopsClips/Models/CloudAnalysisProgressCopy.swift`
- `ios/HoopsClips/HoopsClips/Models/AIEditPromptCopy.swift`
- `ios/HoopsClips/HoopsClips/Views/AIEditView.swift`
- `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`

## Remaining Launch Blockers

The local archive proof does not make HoopClips ready for Apple submission yet. The current preflight still reports these launch blockers:

1. Team/highlight accuracy evidence is incomplete.
   - The launch-grade labeled-footage report is still missing.
   - Current bundle status: `0/54` clips human-reviewed, `54` remaining.
   - GPT draft labels do not count until human review is complete and the launch report is rebuilt.
2. Wired iPhone smoke is still blocked.
   - A device is detected, paired, and Developer Mode is enabled, but Xcode reports it unavailable for install/smoke testing.
3. Latest main `Cloud Edit Deploy Preflight` workflow is stale/failed.
4. Latest main `iOS Internal TestFlight Upload` workflow is stale/failed.
5. Latest manually dispatched deploy preflight targets an older SHA, not the current checkout.
6. Installed TestFlight post-install smoke remains unproven.

Warnings still present:

- Unrelated root Xcode folders are present and must not be staged.
- Live Worker route probe was skipped.
- Live editing route probe was skipped.

## Launch Recommendation

Keep conserving GitHub Actions while fixing evidence gaps:

1. Finish human label review and rebuild the selected-team/highlight accuracy report.
2. Repair the physical-device connection, then run the installed TestFlight smoke end to end.
3. Rerun provider-secret/deploy preflight only when credentials are confirmed current.
4. Run the iOS upload workflow only after the archive, accuracy report, staging backend, and wired-device smoke are all green.
