# Phase Accuracy Label Progress Checkpoint

## Goal

Reduce the launch accuracy bottleneck by making the local human label-review workflow safer for multi-session review. The current 85% selected-team/highlight gate still requires every clip to be human-reviewed, but reviewers should be able to save partial progress without confusing it with launch-ready evidence.

## Changes

- Added a dedicated `Download progress checkpoint` action to the generated local label-review page.
- Checkpoint bundles use the existing safe manual-label bundle schema plus:
  - `source: team_highlight_label_review_page_progress_checkpoint`
  - `savedAt`
  - `clipCount`
  - `completeClipCount`
  - `incompleteClipCount`
  - `launchReady`
- The final `Download launch-ready labels` action remains disabled until every clip has:
  - reviewed checked
  - expected team
  - highlight yes/no
  - event type
  - outcome
- The generated next-steps handoff now includes a separate partial-save command using `--allow-incomplete`, clearly marked as not launch evidence.

## Architecture Notes

- This is local label-review tooling only.
- It does not run product analysis, video rendering, export, upload, or local iOS ML.
- It does not send full videos to GPT.
- It does not store secrets, R2 credentials, object keys, upload URLs, source URLs, or full presigned URLs in label bundles.
- GPT draft labels still require human review before launch evidence counts.

## Regenerated Local Bundle

Command:

```bash
python3 scripts/prepare_team_highlight_labeling_bundle.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --output-dir artifacts/team_highlight_labeling_bundle \
  --video 326_1770329282=/Users/hanfei/Downloads/326_1770329282.mp4 \
  --draft-bundle /Users/hanfei/Downloads/team_highlight_manual_labels_bundle_draft.json \
  --json
```

Result:

- review page: `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html`
- next steps: `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_labeling_bundle/next_steps.md`
- cases: 2
- clips: 54
- complete clips: 0
- incomplete clips: 54
- GPT draft prefilled clips: 54
- skipped draft clips: 1
- review priority: 49 close-review, 5 standard-review

The regenerated ignored artifact now contains:

- `Download progress checkpoint`
- `team_highlight_label_review_page_progress_checkpoint`
- `Commands To Save Partial Progress`
- `--allow-incomplete`
- `Download launch-ready labels`

## Validation

```bash
python3 -m py_compile \
  scripts/build_team_highlight_label_review_page.py \
  scripts/prepare_team_highlight_labeling_bundle.py \
  scripts/test_build_team_highlight_label_review_page.py \
  scripts/test_prepare_team_highlight_labeling_bundle.py

python3 -m unittest \
  scripts.test_build_team_highlight_label_review_page \
  scripts.test_prepare_team_highlight_labeling_bundle \
  scripts.test_apply_team_highlight_manual_labels \
  scripts.test_build_launch_team_accuracy_report -v

awk '/<script>/{flag=1;next}/<\/script>/{flag=0}flag' \
  artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html \
  > /tmp/hoopclips_label_review.js

node --check /tmp/hoopclips_label_review.js
```

Results:

- Python compile passed.
- Focused label/apply/report tests passed: 19 tests, 0 failures.
- Regenerated review-page JavaScript passed `node --check`.

Browser smoke was attempted, but the local Browser MCP requires a valid pin in this environment. No browser interaction was performed.

## Remaining Launch Blocker

This branch does not clear the 85% launch accuracy gate. The bundle is still `0/54` complete because every clip needs human review. The next reviewer action is:

1. Open `artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html`.
2. Review `Next close review` clips first.
3. Use checkpoints whenever pausing.
4. After all 54 clips are complete, download launch-ready labels.
5. Apply the final bundle without `--allow-incomplete`.
6. Build `team_highlight_accuracy_report.json`.
7. Rerun submission readiness with `--team-accuracy-report`.
