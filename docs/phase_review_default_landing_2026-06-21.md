# Review Default Landing Simplification

Date: 2026-06-21

## Goal

Keep Review calm when a tester first opens it. The app should not silently switch the user into a QA-style filter before they understand the clip queue.

## Change

- Removed automatic first-load switching from `All` to `Priority`.
- Kept the `Review these first` card so priority clips are still available as an intentional tap.
- Review now lands on the broader clip queue and lets the user decide whether to narrow down.

## Product rationale

Normal users want to watch clips and decide Keep or Nah. Auto-selecting Priority made the page feel like the app was changing modes on its own and could reintroduce a busy filter chip even after the default filter set was simplified.

## Validation

Not run in this slice. The user did not request simulator, build, or tests.
