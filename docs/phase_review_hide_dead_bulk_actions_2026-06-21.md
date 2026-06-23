# Review Declutter Pass

## Goal

Make Review feel less like a control panel while keeping the core Keep / Nah workflow and diagnostic detail available.

## Change

- The `Keep Strong` / `Skip Weak` quick-actions card now appears only when at least one bulk action has matching clips.
- When both bulk actions would be disabled, the card is hidden instead of showing dead buttons.
- Main review cards now show only one evidence row.
- The full evidence list remains available in the clip detail sheet.

## User impact

A normal user sees fewer choices when there is nothing to bulk-apply, and less stacked explanation while deciding on the current clip. Review stays focused on the current clip and the Keep / Nah decision.

## Product note

This keeps Review action-first and reduces inactive or overly detailed controls without hiding important review diagnostics.

## Validation

Not run in this pass per instruction to avoid extra simulator/build/test work unless explicitly requested.
