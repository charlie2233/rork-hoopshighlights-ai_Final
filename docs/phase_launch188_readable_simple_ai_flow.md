# Phase Launch188 - Readable Simple AI Flow

Date: 2026-06-01
Branch: `codex/phase-launch188-readable-simple-ai-flow`

## Goal

Stop logo-only churn and improve the actual app plus AI editing path:

- Make AI Edit clearer about which team is being edited.
- Give users more room for a useful side note.
- Strengthen selected-team guardrails so GPT/edit planning can keep blocks, steals, defensive stops, and uncertain reviewable clips while rejecting confident opponent clips.
- Keep the cloud-first boundary intact: iOS sends intent/status controls only; backend owns edit planning/rendering.

## Changes

- AI Edit now shows a visible target chip: selected team or all teams.
- Export side note budget is now 320 characters on iOS and backend request validation.
- Selected-team default prompt now explicitly says to render selected-team matches and reject confident opponent clips.
- Selected-team focus summary now says confident matches should render while uncertain team clips stay reviewable.
- Prompt placeholder copy is shorter and less cluttered.
- Tests cover selected-team guardrails and the 320-character backend prompt limit.

## Architecture

- No iOS analysis, rendering, FFmpeg generation, or composition was added.
- iOS continues to pass a sanitized structured user intent into the cloud edit request.
- Backend validation still stores structured edit intent, not the raw prompt text inside the context dump.
- This supports the GPT-led editor plan without letting GPT bypass validators or renderer rules.

## Evidence

Commands run:

```bash
git diff --check
```

Result: passed.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest \
  ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_user_prompt_allows_richer_side_note_without_leaking_to_context_dump \
  ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_user_prompt_is_sanitized_and_mapped_to_structured_edit_intent -v
```

Result: `Ran 2 tests in 0.012s` and `OK`.

```bash
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  build-for-testing
```

Result: `** TEST BUILD SUCCEEDED **`.

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultPromptCarriesSelectedTeamFocus \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderKeepsTeamGuardrailsWithTypedNote \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderPreservesGuardrailsForLongUserNote
```

Result: `** TEST SUCCEEDED **`.

## Remaining Blockers

- Not ready to claim internal launch/TestFlight submission from this phase alone.
- Still needs real-device TestFlight smoke: import, cloud analysis, Review, Export, AI Edit render, preview, revision, share/open-in.
- Still needs a labeled clip accuracy bundle to prove the 85% target on real basketball footage.
- Still needs the full GPT-led highlight editor/candidate expansion work to improve actual clip quality beyond prompt guardrails.
- The unrelated root `HoopsClips.xcodeproj/` and `HoopsHighlightsAI.xcodeproj/` folders were intentionally not staged.
