# AI Edit Hero Metadata Declutter

## Goal

Make AI Edit feel like a user-facing reel builder instead of an internal build/debug/setup metadata screen.

## Change

- Removed the visible `Build N` pill from the AI Edit hero header.
- Removed the second hero metadata row with plan tier and team-target chips.
- Kept the user-facing `EXPORT` label, reel title, clip/aspect/duration metrics, and all render/status/share behavior.
- Build proof remains available through Settings/proof surfaces instead of the main make-reel path.
- Plan/team choices still affect setup and rendering; they are just no longer repeated as hero metadata.

## User impact

A normal user sees fewer internal details before making a reel. The hero now focuses on the outcome: make the reel.

## Product note

This removes developer/setup-looking metadata from the primary action flow without changing diagnostics or render behavior elsewhere.

## Validation

Not run in this pass per instruction to avoid extra simulator/build/test work unless explicitly requested.
