# Review Filter Simplification

Date: 2026-06-21

## Goal

Make Review feel less stacked for normal testers. The default Review path should be:

1. Watch the clip.
2. Tap Keep or Nah.
3. Move on.

## Change

- Default visible filters now prioritize `All`, `Review`, and `Kept`.
- Team, defense, sound, skipped, and other detailed filters remain available behind `More`.
- Filter chips now stay on one line with shorter labels.
- The `More` chip no longer repeats the hidden filter count in the visible UI.

## Product rationale

The advanced filters are still useful for QA and accuracy checks, but they should not be the first thing a new user has to understand. This keeps power-user control without making the default Review screen feel like a scouting spreadsheet.

## Validation

Not run in this slice. The user did not request simulator, build, or tests.
