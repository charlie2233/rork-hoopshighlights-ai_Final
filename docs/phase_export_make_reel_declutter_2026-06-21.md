# Export Make Reel Declutter

Date: 2026-06-21

## Goal

Make Export feel like a simple `Make Reel` flow instead of another status/config screen.

## Change

- Renamed the Export navigation title to `Make Reel`.
- Shortened the top summary copy.
- Removed the repeated context pills from the top summary card.
- Removed the extra explanatory paragraph under the hero card.
- Hid the AI Edit progress card until an edit job has started.
- Hid the Preview / Save / Share dock until a render download exists.
- Moved plan-limit and Pro upsell cards behind `Edit details`.
- Left AI Edit prompt, setup, render action, status notices, preview, save, and share behavior intact.

## Product rationale

The user should land on one clear action: make the reel. Detailed counts, disabled future actions, and plan/upsell cards made the screen feel more stacked before the user even started AI Edit. The real controls still live in AI Edit, but the default flow now stays phase-based.

## Validation

Not run in this slice. The user did not request simulator, build, or tests.
