# Review Context Strip Simplification

Date: 2026-06-21

## Goal

Remove one more visible section from Review so normal users see fewer dashboard-style metrics before deciding Keep or Nah.

## Change

- Removed the `reviewContextStrip` from the default Review stack.
- Kept the core Review flow visible: clip preview, Keep/Nah controls, filters, priority prompt, quick actions, and AI Edit entry.
- Kept quick actions visible for tester speed.
- Left the underlying context-strip helpers in place for now so this is a low-risk visibility change instead of a deeper refactor.

## Product rationale

Review should feel like a clip decision screen, not a scouting dashboard. The context strip summarized Team, Defense, Team Check, and Sound as metrics, which made the default page feel more like QA telemetry than a simple clip-review flow.

Those details still exist through filters and clip-level cues, but they no longer sit in the main default path.

## Validation

Not run in this slice. The user did not request simulator, build, or tests.
