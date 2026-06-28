# Review Smoke Proof Declutter

Date: 2026-06-21

## Goal

Keep internal proof controls out of the default clip-review path.

## Change

- Removed the visible Review smoke-proof shortcut from the main Review stack.
- Left the existing proof helpers in place for now so this stays a low-risk visibility change.
- Launch/test proof remains available through Settings diagnostics instead of sitting above the clip preview.

## Product rationale

Review should feel like a user task: watch the clip, tap Keep or Nah, move on. A visible `Proof / Internal test / Send` card is useful for launch debugging, but it makes the default screen feel like an internal tool instead of a simple product.

## Validation

Not run in this slice. The user did not request simulator, build, or tests.
