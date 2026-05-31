# Phase Launch98: Label Review Local Browser Smoke

Date: 2026-05-30
Branch: `codex/phase-launch70-editing-analysis-progress`

## Scope

Make the local Launch71 team-highlight label review page easier to verify through Browser without weakening the launch accuracy gate.

This phase only changes the local manual-review HTML generator. It does not analyze, render, export, upload, or call GPT from iOS.

## Change

`scripts/build_team_highlight_label_review_page.py` now accepts local-only video URL mappings:

```bash
--video-url videoId=http://127.0.0.1:8787/artifacts/source.mp4
```

Allowed URLs:

- `file://` local paths
- `http://localhost/...`
- `http://127.0.0.1/...`
- `http://[::1]/...`

Rejected URLs:

- Remote hosts
- Query strings or fragments
- Signed URL, token, secret, or credential markers

The default `--video-path` and `--video videoId=/path.mp4` behavior remains unchanged for normal file-open review.

## Why

The in-app Browser can open the generated review page through a localhost server, but browser security blocks `file://` video sources on an `http://127.0.0.1` page. The local-only `--video-url` option lets us serve both the page and source video from the same local HTTP origin for smoke verification, without embedding remote storage URLs or presigned URLs.

## Guardrails

- This does not mark GPT drafts reviewed.
- This does not allow remote R2 or presigned video URLs in the generated page.
- Launch evidence still requires a human-reviewed bundle with every clip marked complete.

## Validation

Commands:

```bash
python3 -m py_compile scripts/build_team_highlight_label_review_page.py scripts/test_build_team_highlight_label_review_page.py
python3 -m unittest scripts.test_build_team_highlight_label_review_page -v
python3 -m unittest scripts.test_build_team_highlight_label_review_page scripts.test_draft_team_highlight_manual_labels_with_gpt scripts.test_apply_team_highlight_manual_labels scripts.test_build_launch_team_accuracy_report -v
git diff --check
```

Browser smoke:

```bash
python3 -m http.server 8787 --bind 127.0.0.1
ln -sf /Users/hanfei/Downloads/326_1770329282.mp4 artifacts/launch71_source_video.mp4
python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-url downloads_326_1770329282=http://127.0.0.1:8787/artifacts/launch71_source_video.mp4 \
  --draft-bundle /Users/hanfei/Downloads/team_highlight_manual_labels_bundle_draft.json \
  --output artifacts/team_highlight_accuracy_launch71_review_browser.html \
  --json
```

Then Browser opened:

```text
http://127.0.0.1:8787/artifacts/team_highlight_accuracy_launch71_review_browser.html
```

The page loaded and showed `0 / 66 clips complete`, `GPT draft prefilled 66 clips`, and the priority review controls. The localhost video source returned `HTTP/1.0 200 OK` with `Content-type: video/mp4` in a HEAD check.

## Launch Impact

This improves verification of the label-review tool, but it does not clear the team/highlight accuracy blocker. The remaining required step is still human review of all 66 clips, applying the downloaded bundle without `--allow-incomplete`, and generating a launch-grade `--team-accuracy-report`.
