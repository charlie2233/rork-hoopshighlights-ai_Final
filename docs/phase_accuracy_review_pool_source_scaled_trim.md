# Phase Accuracy: Source-Scaled Review Pool Trim

## Goal

Reduce redundant and low-value analysis review clips before human review, GPT handoff, and launch accuracy evaluation. The specific failure this addresses is the Troy/El Dorado slice producing a huge recall-heavy review set where most clips were boring, generic, or audio-reaction-only candidates.

## What changed

- Added a source-length-aware review cap for the default large internal review pool.
- Kept explicit small review caps unchanged so existing focused review reserve behavior still works.
- Preserved bounded audio-reaction reserves so loud crowd pops stay available for GPT/user review without dominating the list.
- Preserved defensive reserves for blocks, steals, forced turnovers, and defensive stops.
- Changed final fill ordering to prefer contextual scoring clips, then defensive clips, then other high-scoring candidates, while avoiding extra same-family defensive-shot duplicates outranking normal made-shot candidates after defensive reserves are satisfied.

## Architecture guardrails

- Cloud/backend still owns analysis candidate generation, team filtering, review trimming, GPT handoff inputs, and render planning.
- iOS remains the control surface for upload, review, export configuration, status, preview, and share.
- No local iOS analysis, local rendering, local composition, FFmpeg commands, storage keys, presigned URLs, or secrets were added.

## Evidence

- Focused backend test command:

```bash
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios/backend/tests/test_pipeline_quality.py -v
```

- Result: `86` tests passed.

- Syntax command:

```bash
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py
```

- Result: passed.

- Fresh local Troy slice rerun used source:

```text
/Users/hanfei/Downloads/HoopClips_Troy_vs_ElDorado_2026-01-28_troy_white_slice_10m-15m.mp4
```

- Before this fix, current local analysis returned `80` review clips from `81` candidates on the Troy 10m-15m slice.
- After this fix, current local analysis returned `11` review clips from `81` candidates on the same slice.
- After-fix label counts: `6` Fast Break, `2` Three Pointer, `1` Shot Attempt, `1` Crowd Reaction, `1` Highlight.
- After-fix diagnostics: `finalSegments=11`, `candidateSegments=81`, `audioReactionReviewSegments=3`.

## What this does not prove yet

- This does not close the launch-grade 85% accuracy gate by itself.
- The reduced Troy candidate set still needs human label mapping/review before it can become launch evidence.
- The launch accuracy report still needs at least two real labeled cases and must satisfy selected-team, shot-outcome, defensive coverage, and hard-negative coverage thresholds.
- Staging/production deploy and TestFlight launch proof still need their own evidence.

## Next step

Generate a fresh review bundle from the reduced candidate output, map or redo the human labels, then add at least one more real labeled case before rebuilding the launch accuracy report.
