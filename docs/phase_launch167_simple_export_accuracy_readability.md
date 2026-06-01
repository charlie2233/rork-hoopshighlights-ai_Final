# Phase Launch167: Simple Export Accuracy Readability

## Goal

Make the Export AI Edit path simpler for a first-time user while improving GPT-led clipping accuracy guardrails. Keep the cloud-first contract intact: iOS sends intent and displays status, while cloud owns analysis, planning, rendering, storage, and validation.

## Changes

- Changed the AI Edit entry copy from agent-heavy wording to a simpler "Make My Reel" flow.
- Made the side-note field clearer: users can leave it blank for the best automatic edit or type a short focus like defense, NBA recap, or a 4:30 team reel.
- Preserved selected-team, visible-outcome, blocks, steals, forced-turnover, defensive-stop, duplicate rejection, and uncertain-review guardrails even when the user types a long note.
- Added dynamic-type-safe wrapping/scaling to the AI Edit hero title, helper copy, and setup chips so text has more room across phone sizes and accessibility text settings.

## Architecture Guardrails

- No local iOS video analysis, rendering, composition, or export was added.
- No full video is sent to GPT.
- GPT still receives compact structured intent and backend-validated clip/edit context.
- No raw FFmpeg commands, presigned URLs, storage keys, or secrets are exposed.
- Status copy remains tied to real cloud job state, not fake thinking or fake ETA.

## Validation Evidence

Ran locally on branch `codex/phase-launch167-simple-export-accuracy-readability`:

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch167-derived-data test -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderPreservesGuardrailsForLongUserNote CODE_SIGNING_ALLOWED=NO -quiet
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch167-derived-data build-for-testing CODE_SIGNING_ALLOWED=NO -quiet
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch167-derived-data test -only-testing:HoopsClipsTests CODE_SIGNING_ALLOWED=NO -quiet
```

Results:

- Focused prompt guardrail test: exit 0.
- iOS Debug `build-for-testing`: exit 0.
- iOS `HoopsClipsTests`: exit 0.

## Remaining Blockers

- Real-footage selected-team/highlight accuracy still needs a labeled report before claiming the 85% quality target.
- Installed TestFlight smoke and current archive/IPA are still required before submission.
- Live deploy verification should be run deliberately because GitHub Actions budget is constrained.
