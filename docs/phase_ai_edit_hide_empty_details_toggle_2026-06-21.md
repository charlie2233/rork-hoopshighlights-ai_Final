# AI Edit Setup Declutter

## Goal

Keep AI Edit focused on making a reel instead of showing advanced/debug-style choices before they are useful.

## Change

- The `Edit details` toggle now appears only when there is real secondary detail to inspect:
  - an AI Edit job has started,
  - Cloud Locker/history details are available,
  - or a work receipt is available.
- Removed the visible smart-setup summary banner under the user note box.
- Prompt parsing still applies structured intent to setup choices.
- Advanced cards remain unchanged once the toggle is available.
- Initial setup stays focused on prompt, style, format, duration, and the main make-reel action.

## User impact

A normal user sees fewer choices before starting. Typed edit notes can still influence setup, but the screen no longer repeats an extra confirmation box below the note field.

## Product note

This removes early advanced/control surfaces instead of adding more explanation.

## Validation

Not run in this pass per instruction to avoid extra simulator/build/test work unless explicitly requested.
