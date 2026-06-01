# Phase UX7 - AI Edit Simplicity

Date: 2026-06-01

## Goal

Keep HoopClips focused on app flow, clipping accuracy, and AI edit quality instead of logo work. The Export AI Edit path should feel like a real product: side note, simple setup, real cloud status, preview, then one share button.

## Changes

- Collapsed advanced AI Edit panels behind one `Edit details` control.
- Kept normal user flow focused on:
  - optional edit note
  - simple style/format/length summary
  - `Make My Reel`
  - real cloud status
  - preview/share/revision
- Preserved internal visibility for:
  - cloud job timeline
  - My AI Edits / Cloud Locker
  - AI Work Receipt
  - Free/Pro plan details
  - Pro value card
- Kept the status copy tied to real job/queue/render state. No fake thinking, no artificial waits.

## Accuracy State

The current main branch already includes the latest GPT/team accuracy pass:

- team quick prescan uses up to 64 candidate clips and 288 sampled frames
- full scan/GPT paths can consider up to 320 candidates
- defensive plays such as blocks, steals, forced turnovers, deflections, charges, and loose balls are explicitly modeled
- GPT selected-team underfill now ignores review-only uncertain clips that should not be auto-rendered
- Free AI edits are set to 3/day and max render length is 270 seconds (4:30)

## Validation

- `git diff --check` - passed
- `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests -v` - 42 tests passed
- `PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests -v` - 77 tests passed
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build-for-testing` - passed

Note: XcodeBuildMCP was attempted first, but `session_show_defaults` failed because the transport closed. Validation used shell `xcodebuild` after that.

## Launch Notes

This does not change the cloud-first architecture. iOS still only uploads, configures, shows status/timeline, previews, downloads, and shares. GPT selection, edit planning, rendering, storage, and clipping enhancement remain backend-owned.
