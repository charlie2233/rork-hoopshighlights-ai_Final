# Phase Launch86: Sticky Label Review Video

## Scope

This pass improves the local team/highlight label review page used for the launch-grade 85% accuracy proof. It does not change GPT output, human-review requirements, cloud analysis, rendering, iOS runtime behavior, or launch thresholds.

Branch under test: `codex/phase-launch70-editing-analysis-progress`.

## Change

The source video panel now stays visible while reviewers scroll through the clip-label cards on desktop-width pages:

- `.video-panel` is `position: sticky`.
- The video is capped to `min(42vh, 420px)` so labels remain reachable.
- Mobile-width pages keep normal document flow to avoid a sticky video taking over the screen.

The existing `Mark reviewed + next` behavior still sets the source video time to the current clip event center, so reviewers can verify the prefilled team/event/outcome label against the original footage while moving down the list.

## Launch71 Evidence

Command:

```bash
python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --draft-bundle /Users/hanfei/Downloads/team_highlight_manual_labels_bundle_draft.json \
  --output artifacts/team_highlight_accuracy_launch71_review.html \
  --json
```

Output summary:

- Case count: `3`.
- Clip count: `66`.
- Draft prefill applied clips: `66`.
- Draft prefill skipped clips: `0`.
- `humanReviewRequired`: `true`.

Generated page checks:

- Contains sticky video CSS.
- Shows `GPT draft prefilled 66 clips. Human review is still required.`
- Has 66 clip cards.
- Has 0 reviewed checkboxes checked.
- Secret/presigned URL scan found no `X-Amz-Signature`, `uploadUrl`, `sourceObjectKey`, `sourceUrl`, `downloadUrl`, `presignedUrl`, `resultObjectKey`, `uploadHeaders`, `AKIA`, `ASIA`, OpenAI key-looking values, `Approve all`, or `markAllReviewed`.

Browser visual check was attempted through the Browser/desktop tool, but the local browser automation server requires `SAFE_MCP_ACTION_PIN`, which is not available in this session. The generated HTML was validated by unit tests and static page scans instead.

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

Result: 3 tests passed.

## Launch Impact

The accuracy blocker still requires human review of the 66 prefilled clips and a real launch-grade `--team-accuracy-report`. This change reduces friction in that review loop by keeping the original source video visible while the reviewer works through the labels.
