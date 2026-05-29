# Phase Clip100 - Analysis Team Evidence Parity

## Goal

Make selected-team confidence consistent from cloud analysis through AI Edit. A clip should not be treated as a confident selected-team match just because a quick scan or GPT frame review returned a high confidence number without cited frame evidence.

## Change

- Added the same evidence-backed status guard to the analysis pipeline that AI Edit already uses.
- `quick_scan` and `gpt_frame_review` attributions now require at least two evidence frame refs and two role groups before analysis can mark the clip as `matched`.
- If that evidence is missing, the clip is marked `uncertain`, so it can remain available for Review when `includeUncertain` is enabled instead of being overclaimed as a confident match or filtered as a confident opponent.

## Why

The user goal is high selected-team accuracy, with unsure clips still reviewable. This avoids false certainty from weak jersey-color evidence while preserving recall for review.

## Guardrails

- All-teams mode is unchanged.
- Confident opponent filtering still works when attribution has evidence-backed refs and role groups.
- This does not expose frame images, storage object keys, presigned URLs, or secrets.
- This keeps analysis, team attribution, and selection cloud-owned; iOS remains the control surface.

## Validation

Run after this phase:

```bash
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
git diff --check
```

## Remaining Launch Proof

This improves the correctness of the selected-team evidence contract, but it does not prove the 85% target. Internal launch still needs a real cloud-path labeled-footage report, installed iPhone/TestFlight smoke, live staging version/kill-switch proof, Cloudflare deploy proof, and unblocked GitHub Actions.
