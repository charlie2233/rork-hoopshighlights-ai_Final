# Phase UX2: Freemium Pro Experience

Branch: `codex/phase-ux2-freemium-pro-experience`

Base: `codex/phase-ux1-ai-work-timeline-background-render` at `48d4986`

## Goal

Make HoopClips AI Edit plan value clear without dark patterns. Free users should understand their real limits, and Pro should feel faster, cleaner, and more capable, but this phase does not implement payments or paid entitlements.

## Architecture Rules

- iOS remains the control surface for configuration, status, preview, share, and plan-tier messaging.
- Cloud backend remains responsible for analysis, edit planning, template application, policy enforcement, rendering, retention, and storage.
- No local AVFoundation rendering or composition was added.
- No fake thinking, fake ETA, or intentional delay was added.
- No full presigned download URLs, backend secrets, or R2 credentials are exposed.

## Free vs Pro Policy Table

| Capability | Free | Pro Placeholder |
| --- | --- | --- |
| Queue | Standard render queue | Priority render when available |
| Max output resolution | 720p | 1080p |
| Max render duration | 45 seconds | 180 seconds |
| Daily AI edits | 3/day | 25/day |
| Revisions | 3/edit | 10/edit |
| Branding | HoopClips watermark/outro required | No required watermark/outro |
| Premium templates | Locked | Allowed by policy placeholder |
| Cloud storage | 14 days | 60 days |

These values are surfaced from the existing `CloudEditPolicySummary` defaults and backend policy responses when present.

## UX Copy Added

- `Current plan: Free`
- `Standard render queue`
- `HoopClips keeps editing in the cloud. Pro gets priority rendering.`
- `Upgrade to Pro`
- `Priority rendering, cleaner exports, longer videos, and more revisions.`
- `Free export includes HoopClips branding. Upgrade later to remove watermark/outro.`
- `My AI Edits: rendered videos expire in X days on the current plan.`

## Pro Template Placeholders

Locked placeholder cards were added for:

- `Recruiting Reel Pro`
- `Cinematic Mixtape Pro`
- `NBA Recap Pro`
- `Team Highlight Pro`

Selecting a locked template opens an informational Pro sheet. It does not change the current real template, start a render, or attempt unsupported Pro rendering.

## AI Work Receipt Plan Awareness

The receipt now highlights plan-tier facts:

- Free plan limits
- Standard vs priority queue messaging
- Output resolution
- Watermark/outro status
- Storage expiration or retention days
- Revision limit
- Clean export messaging for Pro/internal policies

Receipt rows are still derived from real policy, render, receipt, and retention metadata. No fake AI work or fake counts were introduced.

## Feature Flags

Safe local placeholders were added for:

- `ai_edit_pro_upsell_enabled`
- `ai_edit_pro_templates_enabled`
- `ai_edit_priority_queue_enabled`
- `ai_edit_cloud_locker_enabled`

Current implementation uses safe in-app defaults for non-payment UX only. If remote Statsig wiring is unavailable, Free render flow remains functional and unsupported Pro behavior is not enabled.

## Placeholder vs Implemented

Implemented:

- Plan-tier card on Export AI Edit.
- Pro value card and informational sheet.
- Locked Pro template placeholders.
- Plan-aware AI Work Receipt.
- Cloud locker retention copy.
- Unit coverage for policy copy, Pro placeholders, and safe UX flags.

Placeholder:

- Real Pro subscription activation.
- Real Pro-only template rendering.
- Full render history / My AI Edits service.
- Payment/RevenueCat entitlement wiring.

## No-Dark-Pattern Note

This phase intentionally avoids deceptive waits and fake AI progress. Free can use the product with standard limits. Pro value is expressed through real policy differences: priority queue messaging, resolution, branding, revision limits, render duration, premium templates, and retention.

## Validation

Run for this branch:

- `git diff --check`: passed.
- iOS Debug simulator build: passed with `** BUILD SUCCEEDED **`.
- iOS build-for-testing: passed with `** TEST BUILD SUCCEEDED **`.
- Focused `test-without-building -only-testing:HoopsClipsTests`: simulator runner failed before test execution with `com.apple.CoreSimulator.SimError Code=405` and nested `NSMachErrorDomain Code=-308`. This is runner IPC/device-state failure, not a compile failure.

Backend services were not changed in this phase.
