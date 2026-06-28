# History Friendly Project Names

## Goal

Make saved projects easier to recognize without adding another History section or more stacked metadata.

## Change

- Generic fallback titles now include the import date/time, for example `Full Game - 57 min, Jun 21, 4:12 PM`.
- Imported filenames now drop embedded random/hash-like tokens, not only leading or trailing generated tokens.
- When a stored title is empty, generated, or random-looking, History can use existing team context:
  - `Team vs Opponent`
  - `Team Highlights`
- Manual user renames still win and are not overwritten.
- Existing History cards, detail sheets, rename labels, and accessibility labels benefit through `PersistedProjectRecord.displayTitle` without extra UI.

## User impact

A normal user should see a project name that helps them pick the right import instead of random-looking codes or multiple identical `Full Game - 57 min` rows.

## Product note

This keeps History action-first and uncluttered. The improvement is in naming quality, not more badges or explanatory text.

## Validation

Not run in this pass per instruction to avoid extra simulator/build/test work unless explicitly requested.
