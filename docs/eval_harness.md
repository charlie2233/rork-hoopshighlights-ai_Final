# Eval Harness

## Goal

Measure whether the learned cloud pipeline improves on the current heuristic-heavy baseline without breaking the iOS fallback path.

## Benchmark Set

- Build a fixed sample set of basketball clips with clip-level labels.
- Include `dunk`, `layup`, `jumper`, `block`, `steal`, `fast break`, `miss`, and ambiguous non-highlight segments.
- Keep a held-out slice for regression checks.
- Start with a small scaffold in [`services/inference/evals/basketball_eval_set.json`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/evals/basketball_eval_set.json).

## Metrics

- Candidate recall@k
- Action accuracy
- Rerank quality
- Zero-clip rate
- Local-fallback rate
- End-to-end p50/p95 latency
- Upload failure rate
- Callback failure rate
- Result schema validation failures
- Percentage of clips below the 3.5s minimum
- Median clip duration
- p90 clip duration
- Merged clip count
- Per-label duration distribution

## Process

- Run the same videos through each candidate model path.
- Compare VideoMAE and X-CLIP behind the same recognizer interface.
- Store per-run manifests and summary metrics.
- Promote reviewer corrections from the dashboard into the training set.
- Generate the report with [`services/inference/scripts/run_eval_report.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_eval_report.py).
- For live staging watchability reviews, follow [`docs/live_watchability_review.md`](/Users/hanfei/rork-hoopshighlights-ai_Final/docs/live_watchability_review.md).

## Output

- A short benchmark report in Markdown and JSON
- A regression table with per-class precision, recall, and top-k hit rate
- A clip-quality section with duration policy compliance and merge stats
- A manual review checklist for `contains setup`, `contains finish`, and `feels watchable`
- A list of sample clips that should be reviewed or relabeled

## Recommended Labeling Priorities

- `jumper` and `miss` first, because they tend to collapse into one another when shot release is visible but ball flight is not.
- `layup` next, because it is the most common overlap with `jumper` and `dunk` in short clips.
- `fast break` after that, because transition plays often look like generic scoring clips without enough context.
- `steal` and `block` last, because they are defensive classes the model usually separates better once motion is obvious.
