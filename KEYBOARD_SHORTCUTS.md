# Keyboard Shortcuts

Review supports hardware keyboard shortcuts when a clip is focused:

- `K`: keep the current clip.
- `D`: discard the current clip.
- `N`: compatibility shortcut for Nah / skipped.
- `1` through `5`: toggle Duplicate, Wrong team, Bad window, Wrong label, and Low quality feedback tags.
- `[`: move the clip start 0.5 seconds earlier.
- `]`: move the clip end 0.5 seconds later.

Review also exposes touch controls for clip boundaries:

- `Start -`: move the clip start 0.5 seconds earlier.
- `Start +`: move the clip start 0.5 seconds later.
- `End -`: move the clip end 0.5 seconds earlier.
- `End +`: move the clip end 0.5 seconds later.

Boundary changes update `Clip.startTime`, `Clip.endTime`, and the clamped event center in the shared review model. They do not render video locally.
