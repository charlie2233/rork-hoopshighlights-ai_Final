# History Action-First Cards

Date: 2026-06-21

## Goal

Make History feel like a place to resume work, not a project admin dashboard.

## Change

- Moved `Resume` to the first visible project-card action.
- Renamed the visible `Details` action to `Preview` when a saved reel exists, otherwise `More`.
- Removed the always-visible red `Delete` button from project cards.
- Reduced summary badges to the essentials: clip count and saved-reel state.
- Kept delete available through the project context menu and the detail sheet.

## Product rationale

Normal users open History to continue a project or find a saved reel. A red destructive action on every card adds visual anxiety, and extra analysis/team badges make each row feel like an audit log. The safer default is action-first: Resume, then Preview or More.

## Validation

Not run in this slice. The user did not request simulator, build, or tests.
