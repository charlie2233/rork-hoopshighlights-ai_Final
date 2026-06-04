# Troy vs El Dorado Human Accuracy Check and Backend Clip Collection Report

Date: 2026-06-04

Branch: `codex/phase-launch-proof-next`

Latest implementation commit at report time: `a225a76 Pad team highlight review clip windows`

## Executive Summary

This report documents the full backend path used to collect candidate highlight clips from the Troy vs El Dorado source video, the human labeling workflow, the duplicate-clip problem, the dedupe and padding fixes that were added, and the resulting launch-grade accuracy report.

The human review itself is complete for the Troy slice that was evaluated. The current launch-grade report still fails, but the failure is not because the human labels are missing. The failure is because the cloud candidate set was mostly false positives, the run had to use `all` team mode instead of selected white-team mode, and the current evidence covers only one case.

The most important results are:

- Raw cloud candidates from the Troy slice: `81`.
- Temporal dedupe reduced review/export candidates to `43`.
- Omitted near-duplicate candidates: `38`.
- Completed human-reviewed labels after applying the user checkpoint: `43/43`.
- Review queue after applying labels: `0`.
- Average raw cloud candidate window: `4.905s`.
- Average padded review/export window after the clip-length fix: `8.905s`.
- Final launch accuracy report status: `fail`.
- Main report failure: `highlightPrecision 0.116`, below required `0.850`.
- This Troy run is `teamMode=all`; selected Troy/white-team evidence remains unresolved because selected-team scan did not produce selectable teams during collection.

## Files and Artifacts

Primary source video supplied by user:

- `/Users/hanfei/Downloads/YTDown_YouTube_Troy-vs-El-Dorado-Jan-28-2026_Media_fbLnRi6_0ao_001_1080p.mp4`

Derived local source files created for cloud constraints and review:

- `/Users/hanfei/Downloads/HoopClips_Troy_vs_ElDorado_2026-01-28_cloud_720p_under500mb.mp4`
- `/Users/hanfei/Downloads/HoopClips_Troy_vs_ElDorado_2026-01-28_cloud_part1_0000-2950.mp4`
- `/Users/hanfei/Downloads/HoopClips_Troy_vs_ElDorado_2026-01-28_cloud_part2_2950-end.mp4`
- `/Users/hanfei/Downloads/HoopClips_Troy_vs_ElDorado_2026-01-28_troy_white_slice_10m-15m.mp4`

Primary Troy artifacts:

- Manifest: `artifacts/team_highlight_accuracy_manifest_troy.json`
- Cloud analysis result: `artifacts/team_highlight_accuracy_troy/launch_label_troy_white_slice_10m_15m_all_001/analysis_result.json`
- Human labels: `artifacts/team_highlight_accuracy_troy/launch_label_troy_white_slice_10m_15m_all_001/manual_labels_template.json`
- Review page: `artifacts/team_highlight_labeling_bundle_troy/team_highlight_label_review.html`
- Label status: `artifacts/team_highlight_labeling_bundle_troy/label_status.json`
- Review queue: `artifacts/team_highlight_labeling_bundle_troy/review_queue.md`
- Bundle metadata: `artifacts/team_highlight_labeling_bundle_troy/bundle_metadata.json`
- Eval payload: `artifacts/team_highlight_labeling_bundle_troy/team_highlight_eval.json`
- Accuracy report: `artifacts/team_highlight_labeling_bundle_troy/team_highlight_accuracy_report.json`

User-downloaded checkpoint that was applied:

- `/Users/hanfei/Downloads/team_highlight_manual_labels_progress_2026-06-04T06-18-59-868Z.json`

## Backend Architecture Used for Grabbing Clips

The clip collection flow stayed cloud-first, consistent with HoopClips project rules. The iOS app and local review page were not used to perform production analysis or rendering. They were only control/review surfaces.

The backend collection path used these local scripts and cloud endpoints:

- `scripts/collect_team_highlight_accuracy_case.py`
- `scripts/worker_team_scan_smoke.py`
- `scripts/make_team_highlight_label_template.py`
- `scripts/prepare_team_highlight_labeling_bundle.py`
- `scripts/apply_team_highlight_manual_labels.py`
- `scripts/build_launch_team_accuracy_report.py`
- `scripts/build_team_highlight_eval_payload.py`
- `scripts/evaluate_team_highlight_accuracy.py`

The staging Worker endpoint used by the collector was:

```text
https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
```

The collector defaults to this endpoint through `DEFAULT_WORKER_URL` in `scripts/collect_team_highlight_accuracy_case.py`.

### Technical Flow

The end-to-end collection path was:

1. Build a create-job payload from the local source video path.
2. Send `POST /v1/analysis/jobs` to the staging control-plane Worker.
3. Receive a `jobId`, a presigned `uploadUrl`, and upload headers.
4. Upload the local video file to the presigned storage URL.
5. In selected-team mode, call `POST /v1/analysis/jobs/{jobId}/team-scan`.
6. If selectable teams are returned, choose the team by `selectedTeamId` or `selectedColorLabel`.
7. Start analysis with `POST /v1/analysis/jobs/{jobId}/start` and a `teamSelection` payload.
8. Poll `GET /v1/analysis/jobs/{jobId}` until a terminal status.
9. Write `analysis_result.json` locally.
10. Build `manual_labels_template.json` from the cloud result.
11. Upsert the case in `artifacts/team_highlight_accuracy_manifest_troy.json`.
12. Build the local HTML review bundle and review queue.
13. Apply the human-reviewed checkpoint back into the label artifact.
14. Build the launch-grade eval payload and accuracy report.

### Request and Upload Safety

`scripts/worker_team_scan_smoke.py` redacts sensitive output fields. The redaction list includes keys/fragments such as:

- `authorization`
- `credential`
- `downloadUrl`
- `objectKey`
- `secret`
- `signature`
- `sourceUrl`
- `token`
- `uploadUrl`

Presigned URL markers are also scrubbed, including `X-Amz-`, `X-Goog-`, `Signature=`, `Credential=`, `AccessKeyId=`, and `token=`.

During this work, the upload helper was improved to stream uploads in chunks rather than reading a large file into one in-memory request. It now uses `http.client` with a `Content-Length` header and `UPLOAD_CHUNK_BYTES = 1024 * 1024`.

The collector also now has explicit upload and request timeouts:

- `--upload-timeout-seconds`
- `--request-timeout-seconds`
- `--timeout-seconds`

This was necessary because the long Troy source and 236 MB segment exceeded the original helper behavior.

## Source Video Preparation

The user supplied a long YouTube-downloaded game video under Downloads. The source was described as 57 minutes long. Local metadata verification showed:

- Size: about `815 MB`.
- Duration: about `3347.365s`, approximately `55.8 minutes`.
- Resolution: `1920x1080`.
- Frame rate: `30fps`.
- Codec: H.264 video with AAC audio.

The staging control plane rejected the original file because it exceeded the Worker file-size limit.

Relevant Worker constraints:

- `MAX_FILE_SIZE_BYTES=524288000`, approximately `500 MiB`.
- `MAX_DURATION_SECONDS=1800`, exactly `30 minutes`.

The full source was compressed to a cloud-safe 720p file:

```text
/Users/hanfei/Downloads/HoopClips_Troy_vs_ElDorado_2026-01-28_cloud_720p_under500mb.mp4
```

That compressed file was still too long for the 1800-second limit, so it was split into shorter segments.

A 10-15 minute slice was then carved out for the human accuracy check:

```text
/Users/hanfei/Downloads/HoopClips_Troy_vs_ElDorado_2026-01-28_troy_white_slice_10m-15m.mp4
```

That slice was used because the full/long selected-team scan path did not produce selectable teams, and the smaller slice gave a faster, cleaner test case.

## Team Target and Selection Intent

The intended target team was Troy.

The user clarified that Troy was the white team. The selected-team collector attempts used:

```text
--selected-color-label white
```

The intended selected-team case was supposed to evaluate Troy/white highlights. However, selected-team scan did not produce usable selectable teams during the collection attempts.

## What Happened During Collection

### Full Source Attempt

The original source video could not be submitted directly.

Failure:

```text
File size exceeds control plane limits.
```

Reason:

- Original file was about `815 MB`.
- Control-plane max file size is about `500 MiB`.

### Compressed Full Video Attempt

After compression to 720p, file size was under the max size limit, but the full compressed video was still rejected.

Failure:

```text
Duration exceeds control plane limits.
```

Reason:

- Compressed full video duration was about `3347s`.
- Control-plane max duration is `1800s`.

### Split Segment Attempt

The first large segment was within size and duration limits, but the original upload helper hit transport issues.

Initial failure:

```text
Upload failed: The write operation timed out
```

After adding configurable upload timeout, the next failure was:

```text
Upload failed: Broken pipe
```

The helper was then changed to stream the upload in chunks and send an explicit `Content-Length`. That fixed the large-upload client behavior.

After upload worked, the next selected-team issue was the team-scan path.

Selected-team scan on a long segment returned:

```json
{
  "status": "unavailable",
  "detectedTeams": []
}
```

### Smaller 10-15 Minute Slice Attempt

A five-minute slice was created and submitted in selected-team mode with `--selected-color-label white`.

The smaller slice still returned no selectable teams for the selected-team scan path:

```json
{
  "status": "unavailable",
  "detectedTeams": []
}
```

This means the issue was not only source length. The team-scan provider/configuration/path was not reliably returning selectable teams for the selected-team staging flow during collection.

### All-Teams Fallback

Because selected-team scan did not produce selectable teams, the collector was run in all-teams mode on the 10-15 minute Troy slice.

The successful case was:

```text
caseId=launch_label_troy_white_slice_10m_15m_all_001
videoId=troy_el_dorado_2026_01_28_slice_10m_15m
teamMode=all
```

The cloud analysis job completed successfully:

```text
analysisJobId=11a1b81418c642fca4934d7ae0d26edf
analysisStatus=completed
rawClipCount=81
```

The analysis result currently contains detected team options:

```json
[
  {
    "teamId": "team_black",
    "label": "black jersey",
    "colorLabel": "black",
    "confidence": 0.98,
    "source": "quick_scan"
  },
  {
    "teamId": "team_white",
    "label": "white jersey",
    "colorLabel": "white",
    "confidence": 0.98,
    "source": "quick_scan"
  }
]
```

Important nuance: even though the completed all-teams analysis result contains detected team options, the launch eval case is still `teamMode=all` with `selectedTeamId=null`. Therefore it does not count as selected Troy/white-team launch evidence.

## Human Review Workflow

The review page was generated at:

```text
artifacts/team_highlight_labeling_bundle_troy/team_highlight_label_review.html
```

The review page was improved during this work to make human labeling easier:

- Click a clip card to jump to its start.
- The clip plays the clip window and auto-pauses at the clip end.
- Each clip card has a `Play clip` button.
- `Enter` or `Space` plays the active clip.
- `S` plays the clip from start-to-end.
- Event and Finish buttons still jump exactly to those markers.
- The currently playing clip is visually highlighted.
- Playback status text explains what is happening.

The user completed a human-review checkpoint and provided:

```text
/Users/hanfei/Downloads/team_highlight_manual_labels_progress_2026-06-04T06-18-59-868Z.json
```

The checkpoint was applied with `scripts/apply_team_highlight_manual_labels.py` without `--allow-incomplete`.

Apply result:

```json
{
  "status": "ready",
  "launchEvidenceEligible": true,
  "completeClipCount": 81,
  "incompleteClipCount": 0,
  "appliedCaseCount": 1
}
```

After dedupe and padding were applied, the currently retained label set is:

```text
completeClipCount=43
incompleteClipCount=0
launchEvidenceEligible=true
reviewQueueRowCount=0
```

The human labels include notes from the reviewer, such as:

- `made heavy contested layup good`
- `good defence by white, but not clip for black team. so bad selection`
- `steal, layup and finish good clip, but mid window, can be extended a bit more`
- `White team highlight`
- `white didnt make the sho..`
- `holy bad window i think he made the lay rtight after`

These notes were useful because they exposed both false positives and short/bad windows.

## Duplicate and Similar Clip Problem

The raw cloud output generated too many overlapping clips around similar moments.

Before dedupe:

- Raw candidate clips: `81`.
- Human review showed many near-identical or overlapping time windows.
- A quick overlap count found `58` adjacent near/overlapping pairs in the original 81-clip checkpoint.

The likely reason is that the candidate generator emitted multiple windows around the same possession/play. This can happen when several nearby scoring, motion, audio, or event-confidence signals fire in the same possession.

The practical user-facing effect was bad:

- Too many redundant review cards.
- Repeated similar timestamps.
- A 5-minute source slice produced far more candidate clips than a reviewer should have to inspect.
- Many candidates were later marked `not_highlight` or `bad_window`.

## Temporal Dedupe Implementation

A temporal dedupe filter was added at the label-template/review boundary in:

```text
scripts/make_team_highlight_label_template.py
```

This is intentionally not an iOS feature. The cloud analysis can still return raw candidates, but the manual-review/export set collapses near-identical windows before the reviewer sees them.

Default dedupe settings:

```text
minOverlapRatio=0.25
centerToleranceSeconds=4.0
startToleranceSeconds=4.0
strategy=ranked_temporal_overlap
```

The dedupe algorithm:

1. Indexes all cloud clips by original prediction index.
2. Ranks clips by a quality score.
3. Quality score includes keep/autokeep, watchability, confidence, motion, audio, team confidence, and shot outcome reliability when present.
4. Keeps the strongest candidate in each temporal neighborhood.
5. Omits lower-ranked candidates when they overlap, share a close event center, or start very close and overlap.
6. Stores omitted duplicates as metadata in `omittedDuplicateClips`.
7. Keeps original `predictionIndex` and `predictionClipId` for auditability.

The eval builder was updated in:

```text
scripts/build_team_highlight_eval_payload.py
```

It now treats `omittedDuplicateClips` as intentional omissions, so intentionally collapsed duplicate predictions are not treated as unlabeled human-review gaps.

Current dedupe result:

```json
{
  "enabled": true,
  "strategy": "ranked_temporal_overlap",
  "minOverlapRatio": 0.25,
  "centerToleranceSeconds": 4.0,
  "startToleranceSeconds": 4.0,
  "originalClipCount": 81,
  "reviewClipCount": 43,
  "omittedClipCount": 38
}
```

## Clip Window Padding / Longer Clip Length

The user noted that it is fine to have about 35 seconds of actual highlights from a 5-minute source, but each individual clip should be longer.

The clip-window padding was added in:

```text
scripts/make_team_highlight_label_template.py
```

Defaults:

```text
preRollSeconds=1.5
postRollSeconds=2.5
```

This means each retained review/export clip window now starts `1.5s` before the raw detected cloud window and ends `2.5s` after it, clamped to source duration when known.

The template preserves both:

- `predictionStart` and `predictionEnd`, which are raw cloud timings.
- `start` and `end`, which are padded review/export timings.

This distinction matters because the report/eval can still trace back to the raw prediction while the human/editor sees a better clip window.

Current timing stats:

```json
{
  "rawAvg": 4.905,
  "rawMin": 3.067,
  "rawMax": 8.3,
  "paddedAvg": 8.905,
  "paddedMin": 7.067,
  "paddedMax": 12.3
}
```

## Final Human Label Distribution

After dedupe and padding, the retained human-reviewed labels are:

```text
clipCount=43
completeClipCount=43
incompleteClipCount=0
```

Highlight distribution:

```json
{
  "True": 5,
  "False": 38
}
```

Expected event distribution:

```json
{
  "bad_window": 5,
  "boring": 32,
  "defensive_stop": 1,
  "layup": 4,
  "rebound": 1
}
```

Expected outcome distribution:

```json
{
  "bad_window": 5,
  "defensive_stop": 1,
  "made": 4,
  "not_highlight": 32,
  "not_shot": 1
}
```

Interpretation:

- Only `5` of the `43` retained candidates were human-marked highlights.
- `38` were human-marked negatives.
- The system produced many false positives even after dedupe.
- The labels are complete, but they reveal candidate quality problems.

## Launch Accuracy Report

The launch report was generated with:

```text
scripts/build_launch_team_accuracy_report.py
```

Output files:

```text
artifacts/team_highlight_labeling_bundle_troy/team_highlight_eval.json
artifacts/team_highlight_labeling_bundle_troy/team_highlight_accuracy_report.json
```

Current report status:

```text
fail
```

Current metrics:

```json
{
  "caseCount": 1,
  "clipCount": 43,
  "highlightPrecision": 0.1163,
  "highlightRecall": 1.0,
  "clipTimingQuality": 1.0,
  "negativeClipCount": 38,
  "badWindowNegativeCount": 5,
  "shotOutcomeEvidenceClipCount": 4,
  "shotOutcomeEvidenceQuality": 0.0,
  "selectedTeamHighlightCount": 0,
  "selectedTeamEvidenceClipCount": 0,
  "opponentHighlightCount": 0,
  "defensiveEventCount": 0,
  "uncertainReviewCount": 33
}
```

Current failures:

```text
highlightPrecision 0.116 is below required 0.850.
shotOutcomeEvidenceQuality 0.000 is below required 0.850.
caseCoverage 1 is below required 2.
selectedTeamHighlightCoverage 0 is below required 6.
madeShotOutcomeEvidenceCoverage 0 is below required 1.
missedShotOutcomeEvidenceCoverage 0 is below required 1.
opponentHighlightCoverage 0 is below required 2.
selectedTeamDefensiveEventCoverage 0 is below required 2.
selectedTeamBlockCoverage 0 is below required 1.
selectedTeamStealCoverage 0 is below required 1.
selectedTeamForcedTurnoverCoverage 0 is below required 1.
selectedTeamDefensiveStopCoverage 0 is below required 1.
```

Thresholds relevant to this failure:

```json
{
  "highlightPrecision": 0.85,
  "highlightRecall": 0.85,
  "clipTimingQuality": 0.85,
  "selectedTeamEvidenceQuality": 0.85,
  "shotOutcomeEvidenceQuality": 0.85,
  "minCases": 2,
  "minSelectedTeamHighlights": 6,
  "minOpponentHighlights": 2,
  "minSelectedTeamDefensiveEvents": 2,
  "minMadeShotOutcomeEvidenceClips": 1,
  "minMissedShotOutcomeEvidenceClips": 1
}
```

## Why the Report Fails Despite Complete Human Labels

The report fails for backend/model quality and coverage reasons, not because labeling is incomplete.

### 1. Highlight precision is far too low

The report says:

```text
highlightPrecision=0.1163
required=0.85
```

This means the candidate generator produced too many clips that the human reviewer marked as non-highlights.

From the final retained clips:

- Human highlights: `5`.
- Human non-highlights: `38`.

Even after dedupe, the candidate generator is still too spammy.

### 2. The run used all-teams fallback

The manifest case is:

```json
{
  "teamMode": "all",
  "selectedTeamId": null
}
```

Because selected Troy/white-team scan did not produce selectable teams at collection time, this case cannot satisfy selected-team gates.

That is why selected-team counts are zero:

```text
selectedTeamHighlightCount=0
selectedTeamEvidenceClipCount=0
selectedTeamBlockCount=0
selectedTeamStealCount=0
selectedTeamDefensiveStopCount=0
```

### 3. Only one case exists

The report requires at least two cases:

```text
caseCoverage 1 is below required 2.
```

This Troy slice is only one case.

### 4. Shot outcome evidence failed

The report says:

```text
shotOutcomeEvidenceQuality=0.000
required=0.850
```

The current analysis/eval did not provide enough reliable made/missed outcome evidence that aligned with human labels. This is separate from whether the human could watch and label the clip.

### 5. Defensive coverage gates were not met

The launch report requires defensive variety, including blocks, steals, forced turnovers, and defensive stops. The current all-teams Troy slice does not cover these gates.

## What Worked

The following parts worked:

- Cloud upload and job creation worked after upload streaming/timeouts were improved.
- All-teams cloud analysis completed successfully.
- Cloud result was persisted to local artifacts.
- Manual label template generation worked.
- Review HTML generation worked.
- Human review was completed.
- User notes were preserved.
- Downloaded progress checkpoint applied successfully.
- Temporal dedupe reduced reviewer noise from 81 to 43 clips.
- Longer padded review/export windows were applied.
- Label status is complete and launch-evidence eligible at the label-file level.
- Eval/report generation completed and produced concrete failure metrics.

## What Did Not Work

The following parts did not work or remain unresolved:

- The full source could not be uploaded because of file-size limits.
- The compressed full source could not be processed because of duration limits.
- Selected-team scan for Troy/white returned no selectable teams during collection attempts.
- The all-teams fallback produced too many false positives.
- The launch accuracy report failed quality and coverage gates.
- The evidence is one case only, while the launch gate requires at least two.
- Selected-team gates remain unresolved because the successful case is `teamMode=all`.

## Backend Technical Details and Source Pointers

### `scripts/collect_team_highlight_accuracy_case.py`

Role:

- Owns accuracy-case collection.
- Uploads real basketball video to staging Worker.
- Runs team or all-teams analysis.
- Polls the cloud job.
- Writes local analysis and label-template artifacts.
- Updates the accuracy manifest.

Important details:

- Default Worker URL is staging.
- Uses `POST /v1/analysis/jobs` for create/presign.
- Uses `POST /v1/analysis/jobs/{jobId}/team-scan` in selected-team mode.
- Uses `POST /v1/analysis/jobs/{jobId}/start` to start analysis.
- Uses `GET /v1/analysis/jobs/{jobId}` to poll.
- Terminal statuses are `completed`, `failed`, `cancelled`, `succeeded`, and `expired`.

### `scripts/worker_team_scan_smoke.py`

Role:

- Shared Worker smoke helper.
- Provides request helper, upload helper, team selection, team normalization, and secret-safe logging.

Important details:

- Sanitizes presigned URLs and object keys.
- Streams uploads in `1 MiB` chunks.
- Uses configurable request/upload timeouts.
- Selects a team by `selectedTeamId` first, then exact `selectedColorLabel`, then first detected team only if no selector was provided.

### `services/control-plane/src/routes/public.ts`

Role:

- Validates job creation requests.
- Enforces file-size and duration limits.
- Normalizes team selection.

Important details:

- Rejects files larger than `maxFileSizeBytes`.
- Rejects durations above `maxDurationSeconds`.
- Normalizes `mode=all` or `mode=team`.
- Defaults selected-team confidence threshold to `0.85`.
- Defaults `includeUncertain` to `true`.

### `services/control-plane/src/routes/internal.ts`

Role:

- Normalizes inference callback payloads and clips.
- Converts manifest clip-like values into `CloudClip` objects.

Important details:

- Normalizes `startTime`, `endTime`, `eventCenter`, confidence, label/action, outcome, audio/motion/visual scores, combined score, and team/shot evidence fields.
- Clip count and diagnostics are derived from normalized callback clips.

### `scripts/make_team_highlight_label_template.py`

Role:

- Converts cloud analysis JSON into manual label rows.
- Adds human-review scaffolding.
- Adds temporal dedupe metadata.
- Adds padded review/export windows.

Important current defaults:

```text
DEFAULT_TEMPORAL_DEDUPE_MIN_OVERLAP_RATIO=0.25
DEFAULT_TEMPORAL_DEDUPE_CENTER_TOLERANCE_SECONDS=4.0
DEFAULT_TEMPORAL_DEDUPE_START_TOLERANCE_SECONDS=4.0
DEFAULT_CLIP_WINDOW_PRE_ROLL_SECONDS=1.5
DEFAULT_CLIP_WINDOW_POST_ROLL_SECONDS=2.5
```

### `scripts/build_team_highlight_eval_payload.py`

Role:

- Builds evaluator-ready payload from cloud analysis plus human labels.
- Validates that every retained label row has `needsLabel=false`, `reviewedByHuman=true`, and complete expected fields.
- Resolves label rows to prediction clips by index, ID, or time overlap.
- Ignores intentionally omitted temporal duplicates recorded in `omittedDuplicateClips`.

### `scripts/build_launch_team_accuracy_report.py`

Role:

- Builds label status.
- Builds launch eval payload across manifest cases.
- Calls `evaluate_accuracy`.
- Writes report JSON.

Important behavior:

- It refuses to build a launch report if label status is incomplete.
- Label completion is only about human label readiness, not model quality.

## Current State

Current label status:

```json
{
  "status": "complete",
  "clipCount": 43,
  "completeClipCount": 43,
  "incompleteClipCount": 0,
  "launchEvidenceEligible": true
}
```

Current report status:

```json
{
  "status": "fail",
  "clipCount": 43,
  "highlightPrecision": 0.1163,
  "caseCount": 1
}
```

The human accuracy check did its job: it produced concrete evidence that the current all-teams candidate generator is too noisy on this source and that selected-team collection still needs fixing.

## Recommended Next Backend Work

1. Fix selected-team scan reliability for Troy/white.

The selected-team gate cannot pass while the successful evidence case is all-teams mode. The backend should make the quick scan/team scan path return stable `team_white` / `team_black` options for this source, then selected-team analysis should be rerun with `--selected-color-label white` or explicit `--selected-team-id team_white`.

2. Add a stricter candidate-quality filter before review/export.

Temporal dedupe reduced duplicate spam, but it did not solve false positives. The candidate generator needs a precision filter, likely around combined score, event family, shot outcome evidence, team evidence, or a reranker.

3. Add possession-level suppression.

Even after temporal dedupe, there can be multiple bad candidates from the same possession. A possession-aware filter would keep only the best highlight candidate per short possession window unless there are clearly separate events.

4. Improve shot outcome evidence.

The report failed `shotOutcomeEvidenceQuality`. The backend needs better made/missed outcome extraction or a fallback review/evidence path that does not score missing evidence as quality failure.

5. Collect at least one more case.

Launch requires at least two cases. Even if candidate quality improves on Troy, `caseCoverage` remains failing until another case is collected and human-reviewed.

6. Preserve the current human labels as diagnostic evidence.

The Troy labels are valuable even though the report fails. They show exactly where the model is over-selecting, picking bad windows, and missing selected-team evidence.

## Bottom Line

The backend pipeline successfully collected and reviewed a real Troy source slice, but it had to fall back to all-teams mode because selected-team scan did not return usable teams. Human review proved the candidate set was noisy: only `5` of `43` deduped retained candidates were true highlights. Dedupe and longer clip windows improved the review/export experience, but the launch gate remains blocked by backend candidate precision, selected-team coverage, shot outcome evidence, case coverage, and defensive-event coverage.
