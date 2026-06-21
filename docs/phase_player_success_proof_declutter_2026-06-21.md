# Player Proof Declutter

## Goal

Make the Player AI Analysis area feel like a user workflow, not a QA/debug panel.

## Change

- Removed the visible `Proof` card after clips are already ready.
- Removed the duplicate nested upload diagnostics tray from the `Still uploading` card.
- Kept proof actions available in the top-level slow/background upload help tray and in failed/recovered upload states where they help debugging.
- Did not add another section, badge, or explanation.

## User impact

A normal user who gets clips now sees the analysis result directly instead of extra proof controls. During long uploads, the user still gets progress and one proof/help surface instead of duplicate proof boxes.

## Product note

This keeps HoopClips action-first: success means review clips, and diagnostics appear only when upload support is relevant.

## Validation

Not run in this pass per instruction to avoid extra simulator/build/test work unless explicitly requested.
