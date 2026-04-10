# Live Watchability Review

## Goal

Run 10 to 15 real basketball videos through staging and judge whether the returned clips are actually usable to a reviewer, not just technically correct.

This is the live validation step after the inference cutover. It is intentionally separate from the offline eval harness in [`docs/eval_harness.md`](/Users/hanfei/rork-hoopshighlights-ai_Final/docs/eval_harness.md).

## Sample Mix

Use a small but balanced set:

- 2 dunk clips
- 2 layup clips
- 2 jumper or 3PT clips
- 2 block clips
- 2 steal clips
- 2 fast break clips
- 2 miss clips
- 1 to 3 ambiguous or borderline non-highlight clips

Prefer real game footage with different camera angles and possession pacing. Do not use the synthetic eval scaffold as the live watchability input.

## Fastest Batch Flow

Use the existing live smoke script as the batch runner. It now emits the clip-level fields needed for review: `uploadTraceId`, `inferenceAttemptId`, `attemptCount`, `acceptedAt`, `processingStartedAt`, and a `clips[]` array with `finalLabel`, `clipDurationSeconds`, `wasMerged`, and `sourceEventCount`.

1. Put 10 to 15 real MP4 files in one folder, grouped by label.
2. Run one smoke per file and save each JSON summary.
3. Aggregate the summaries into a single Markdown table and summary block.

Example:

```bash
export STAGING_WORKER_URL='https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev'
mkdir -p /tmp/hoops-watchability/runs

while IFS=$'\t' read -r label file; do
  trace_id="watch-${label}-$(basename "$file" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-')"
  npx tsx scripts/control-plane-happy-path.ts \
    --base-url "$STAGING_WORKER_URL" \
    --file "$file" \
    --trace-id "$trace_id" \
    --install-id "watchability-${label}" \
    > "/tmp/hoops-watchability/runs/${trace_id}.json"
done < /tmp/hoops-watchability/samples.tsv
```

Then summarize the run set:

```bash
python3 - <<'PY'
import glob, json, statistics

runs = [json.load(open(path)) for path in glob.glob('/tmp/hoops-watchability/runs/*.json')]
clips = [clip for run in runs for clip in run.get('clips', [])]
durations = [clip['clipDurationSeconds'] for clip in clips if clip.get('clipDurationSeconds') is not None]
labels = {}
for clip in clips:
    labels.setdefault(clip['finalLabel'], []).append(clip.get('clipDurationSeconds'))

print(f'runs={len(runs)} clips={len(clips)}')
if durations:
    print(f'median={statistics.median(durations):.2f}s')
    print(f'p90={sorted(durations)[max(int(len(durations) * 0.9) - 1, 0)]:.2f}s')
print('labels=' + json.dumps({k: [d for d in v if d is not None] for k, v in labels.items()}, indent=2))
PY
```

## Required Capture Fields

Record these for every run:

- `requestId`
- `uploadTraceId`
- `inferenceAttemptId`
- `modelVersion`
- `finalStatus`
- `finalLabel`
- `clipDurationSeconds`
- `clipCount`
- `wasMerged`
- `sourceEventCount`

If a run returns multiple clips, record each clip separately. If the job retries or times out, record the retry count and terminal outcome.

## Watchability Rubric

Score each returned clip with a simple yes/no checklist:

- `contains setup`
- `contains finish/outcome`
- `feels complete`
- `would keep/export`

Add a short note when a clip feels too short, starts too late, ends too early, or fragments a single play into multiple clips.

## Acceptance Targets

For this phase, the live run should generally land here:

- No clip under 3.5s unless the source video itself is shorter.
- Normal plays should usually feel like 5.0s to 7.0s clips.
- Fast break or multi-event sequences may stretch to 6.0s to 9.0s when that makes the play more coherent.
- Median returned clip duration should be in the watchable range, not clustered at the minimum.
- Merge behavior should prefer one coherent play over multiple micro-clips.

## Suggested Live Flow

1. Upload a real sample video from the Staging iOS build.
2. Capture the returned `requestId` and `uploadTraceId`.
3. Confirm the job reaches `queued`, then `processing`, then `completed`.
4. Capture `inferenceAttemptId` and `modelVersion` from the job detail response.
5. Review the returned clips in the app.
6. Fill out the checklist for every clip.
7. Repeat until you have 10 to 15 videos across the target label mix.

If a clip is borderline, keep it in the report. The goal is to learn where the boundary policy still needs adjustment, not to hide awkward outputs.

## Report Layout

Use one table row per returned clip:

| clipId | requestId | uploadTraceId | inferenceAttemptId | modelVersion | finalLabel | clipDurationSeconds | merged | setup | finish | complete | keep/export | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Then add a summary section with:

- clip count
- below-min clip rate
- median duration
- p90 duration
- merged clip count
- per-label duration distribution
- timeout and retry counts

## Review Notes

- If the clip starts too late, note whether the boundary issue came from the label preset or from merge behavior.
- If the clip feels fragmented, note whether a merge should have happened or whether the input was actually two separate events.
- If the clip is under 4.0s but the source is short, mark it as boundary-limited rather than a policy failure.
- If the app renders the clip but the human would not keep it, record that explicitly. Watchability is the metric that matters here.
