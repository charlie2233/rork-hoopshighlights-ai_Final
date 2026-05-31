# Phase Launch82: Label Review Ergonomics

## Scope

This pass improves the local manual-review page used to unblock the launch-grade team/highlight accuracy report. It does not change app runtime behavior, cloud analysis, rendering, or GPT decision logic.

Branch under test: `codex/phase-launch70-editing-analysis-progress`.

## Changes

- Added a global `Next incomplete` control to jump to the next clip that still needs a human label.
- Added per-clip `Mark reviewed + next` controls.
- Preserved the human gate: a clip cannot be marked reviewed by that shortcut until expected team, highlight, event, and outcome are all filled.
- Added keyboard focus styling so the current card is visible after jumping.
- Kept local draft save/restore behavior and download confirmation behavior unchanged.

There is intentionally no bulk approve/auto-review action. GPT draft labels still require explicit human review before they can satisfy the launch accuracy gate.

## Review Page Regeneration

Command:

```bash
python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --output artifacts/team_highlight_accuracy_launch71_review.html \
  --json
```

Result:

- Output: `artifacts/team_highlight_accuracy_launch71_review.html`.
- Case count: `3`.
- Generated page includes `Next incomplete`, `markReviewedAndNext`, `focusNextIncomplete`, and per-card `tabindex="-1"`.
- Generated page scan found no `X-Amz-Signature`, `uploadUrl`, `sourceObjectKey`, `sourceUrl`, `downloadUrl`, `presignedUrl`, `resultObjectKey`, `uploadHeaders`, `AKIA`, or `ASIA`.
- Generated page scan found no `Approve all` or `markAllReviewed`.

The regenerated HTML artifact remains a local ignored artifact and was not staged as source.

## Tests

Commands:

```bash
python3 -m py_compile \
  scripts/build_team_highlight_label_review_page.py \
  scripts/test_build_team_highlight_label_review_page.py
```

Result: pass.

```bash
python3 -m unittest scripts.test_build_team_highlight_label_review_page -v
```

Result: 2 tests passed.

```bash
python3 -m unittest \
  scripts.test_build_team_highlight_label_review_page \
  scripts.test_draft_team_highlight_manual_labels_with_gpt \
  scripts.test_apply_team_highlight_manual_labels \
  scripts.test_build_launch_team_accuracy_report \
  -v
```

Result: 15 tests passed.

## Spark Review Note Triage

The read-only Spark note at `/Users/hanfei/Desktop/HoopClips-Review-Notes-2026-05-30_full.txt` was treated as a lead and rechecked against this branch:

- The reported bad import filename is stale here. Current code uses `imported_video_\(UUID().uuidString).\(fileExtension)`.
- The file-backed Photos import path already supports `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`.
- No `Data.self` fallback was found in the current Photos import type.
- Focused `CloudEditServiceTests` now pass locally with `** TEST SUCCEEDED **`, including the locker rerender endpoint cases flagged by the note.

## Launch Impact

This makes the remaining human-label bottleneck faster without weakening the evidence gate. The main launch blocker remains the missing completed manual label bundle and derived `--team-accuracy-report`; this change helps produce that bundle but does not fake it.
