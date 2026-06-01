# Phase Launch181 - Team Reel Prompt Intent

## Goal

Make AI Edit easier to use from the optional side-note box and improve template accuracy for common user language.

## Finding

The AI Edit prompt placeholder suggests "4:30 team reel," but `CloudEditUserIntent.parse` did not understand "team reel." That meant users could type the exact suggested phrase and only get the length parsed, while the setup stayed on the default personal highlight style.

## Change

- Added common team-video phrases to the structured intent parser:
  - `team reel`
  - `team reels`
  - `team highlights`
  - `team package`
  - `team edit`
  - `team video`
  - `team mixtape`
  - `team highlight`
  - `season recap`
  - `team-first`
- These phrases map to `team_highlight_pro_v1`.
- For Free users, the existing fallback remains the nearest free renderer template: `full_game_highlight_v1`.
- Duration parsing still handles `4:30` as 270 seconds.
- Specific team phrases now win over generic `reel`/`mixtape` wording so a team-first note does not get downgraded to a personal/cinematic edit.

## Product Impact

- The side-note box now matches what the app tells users to try.
- Parents, coaches, and players can type natural wording instead of hunting through template options.
- GPT/Edit Agent receives a more accurate template intent for team-first edits, which improves clip selection and ordering toward offense/defense variety instead of individual-only hype.

## Architecture Notes

- No local iOS analysis, rendering, composition, or export was added.
- This only changes iOS intent parsing and request setup before cloud AI Edit.
- Cloud remains responsible for GPT clip selection, EditPlan validation, rendering, storage, and revisions.

## Validation

- `git diff --check` passed.
- Focused `CloudEditUserIntent` tests passed on iPhone 17 Pro simulator (`7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2`):
  - `testCloudEditUserIntentParsesTeamReelPhraseFromPromptPlaceholder`
  - `testCloudEditUserIntentParsesCommonTeamVideoPhrases`
  - `testCloudEditUserIntentParsesRecapShapeAndDuration`
  - `testCloudEditUserIntentParsesCoachReviewSourceAndLongDuration`
- iOS Debug `build-for-testing` passed with `CODE_SIGNING_ALLOWED=NO`.
- The first focused test attempt hit local Simulator launch server error `NSMachErrorDomain -308`; rebooting the simulator path and rerunning passed.
- A first full `HoopsClipsTests/HoopsClipsTests` run failed on the two new team intent tests because generic `reel`/`mixtape` parsing still won over specific team phrases. The parser order was fixed and rerun.
- Full `HoopsClipsTests/HoopsClipsTests` passed on iPhone 17 Pro simulator (`7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2`): 95 tests passed, 0 failed.

## Launch Status

This is a usability and template-accuracy improvement. It does not complete internal TestFlight readiness by itself; real-device TestFlight smoke and cloud edit reliability still need proof.
