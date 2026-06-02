# Phase Launch209 AI Edit Long Reel Quick Prompt

Date: 2026-06-02

## Goal

Make AI Edit simpler for users who want a longer highlight reel by adding a one-tap quick prompt for a 4:30 edit. This supports the launch plan requirement that Export stays simple while still allowing longer reels through structured user intent.

## What Changed

- Moved AI Edit quick prompt definitions into `AIEditQuickPromptLibrary` so the prompt list is testable.
- Added `Long reel` quick prompt:
  - prompt: `Make this a longer 4:30 highlight reel with clear outcomes, defense, and crowd pops.`
  - maps to a 270-second edit through existing structured intent parsing
  - avoids Pro-only template terms, so Free users get the nearest allowed free style instead of a locked-template surprise
- Quick prompt taps now apply structured setup immediately, so parsed duration/template choices update before the user starts AI Edit.
- Kept iOS as a control surface only. The prompt is sent as user intent; backend validation and cloud rendering still own the actual edit.

## Why This Helps

- Users no longer need to open extra controls or type `4:30 reel` manually.
- The prompt also nudges better accuracy by asking for clear outcomes, defense, and crowd/audio pop clues.
- The quick prompt title is short enough for small phones and larger Dynamic Type layouts.

## Validation Evidence

Commands run locally:

```bash
git diff --check
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47' -derivedDataPath /Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClipsCodex -resultBundlePath /Users/hanfei/rork-hoopshighlights-ai_Final/build/HoopsClipsLongReelPromptTests.xcresult -only-testing:HoopsClipsTests
```

Result:

- `git diff --check`: passed.
- `HoopsClipsTests` on iPhone 17 simulator: passed.
- Result bundle generated during validation: `build/HoopsClipsLongReelPromptTests.xcresult` (not committed).

Covered:

- `testAIEditQuickPromptsIncludeSimpleLongReelIntent`
- existing prompt, duration, Free/Pro, team targeting, audio cue, defensive candidate, and cloud edit request tests

## Real-Device Smoke

Still needs iPhone/TestFlight confirmation:

1. Open Export -> AI Edit.
2. Tap `Long reel`.
3. Confirm the note appears in the text box and the selected length updates to 4:30.
4. Start AI Edit and verify backend receives structured intent only, with no raw renderer commands.
