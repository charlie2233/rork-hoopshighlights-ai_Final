# Settings Diagnostics Declutter

Date: 2026-06-21

## Goal

Keep internal launch/test diagnostics available without making Settings feel like a proof dashboard.

## Change

- Removed the always-visible smoke-proof status strip from the Settings card body.
- Moved the compact phone/upload status pills inside the existing `Test tools` drawer.
- Stopped showing the diagnostics card only because stale saved upload proof exists.
- Kept active import, analysis, team scan, upload retry, crash delivery, and pending upload recovery states eligible to surface diagnostics.
- Kept all proof copy/send/status tools and identifiers intact.

## Product rationale

Normal users should see Settings as account, language, support, workflow, and app info first. Internal launch proof is still useful, but it should be deliberate: active problems can surface diagnostics, and dormant proof remains inside the tools instead of keeping the main Settings stack busy.

## Validation

Not run in this slice. The user did not request simulator, build, or tests.
