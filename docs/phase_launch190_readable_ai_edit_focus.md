# Phase Launch190 - Readable AI Edit Focus

## Goal

Make the AI Edit target/focus copy easier to read on small iPhones and larger Dynamic Type settings without weakening the cloud editing guardrails.

## Change

- Shortened the visible AI Edit focus summary to one compact target line.
- Kept the important accuracy cues visible: made shots, blocks, steals, defensive stops, and crowd/audio cues with visual proof.
- Added a compact team-name rule so long detected team names do not crowd the prompt card.
- Left the backend-facing prompt guardrails intact, including selected-team filtering, defense-without-a-make, crowd/audio-pop verification, duplicate/dead-ball rejection, and reviewable uncertain clips.

## Architecture

- iOS still only displays the target and sends compact user intent to the cloud.
- The cloud backend still owns candidate selection, GPT editing, validation, rendering, and storage.
- No local video analysis, audio analysis, rendering, or composition was added.

## Validation

Completed locally on 2026-06-01:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' test -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultPromptCarriesSelectedTeamFocus -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultFocusSummaryShowsAllTeamsTarget -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultFocusSummaryStaysCompactForLongTeamNames
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' build
cd ios/backend
uv run --isolated --with-requirements requirements.txt --with pytest python -m pytest tests/test_pipeline_quality.py -q
cd ../../services/editing
uv run --isolated --with-requirements requirements.txt --with pytest python -m pytest tests/test_gpt_reranker.py -q
```

Results:

- `git diff --check`: passed.
- Focused AI Edit focus-summary tests: passed on iPhone 16e simulator.
- iOS Debug simulator build: passed on iPhone 16e simulator.
- Backend pipeline quality regression suite: `58 passed, 6 subtests passed`.
- GPT reranker regression suite: `81 passed`.

An earlier `test-without-building` attempt was interrupted because the selected simulator stayed shutdown, so the verified test path used a normal `xcodebuild test` run after booting the iPhone 16e simulator.

## Launch Note

This is a UX readability pass, not a launch gate removal. TestFlight readiness still requires real installed-app smoke, current upload proof, live deploy/preflight proof, and human-reviewed accuracy evidence.
