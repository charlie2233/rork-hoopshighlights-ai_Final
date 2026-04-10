# Eval Harness

## Goal

Measure whether the learned cloud pipeline improves on the current heuristic-heavy baseline without breaking the iOS fallback path.

## Benchmark Set

- Build a fixed, stratified sample set of basketball clips with clip-level labels.
- Include at least `dunk`, `layup`, `jumper`, `three`, `putback`, `block`, `steal`, `fast break`, `miss`, and ambiguous non-highlight segments.
- Keep a held-out slice for regression checks, and balance the benchmark by class rather than by a mixed random batch.
- Start with the original scaffold in [`services/inference/evals/basketball_eval_set.json`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/evals/basketball_eval_set.json).
- Use the structured-signal regression slice in [`services/inference/evals/structured_basketball_eval_set.json`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/evals/structured_basketball_eval_set.json) for live basketball clips that emphasize made vs miss, turnover, defensive events, transition, and non-highlight negatives.

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
- Label top-1 accuracy
- Label top-k hit rate
- Event-family top-1 / top-k
- Shot-subtype top-1 / top-k
- Outcome top-1 / top-k
- Confusion matrices for event family, shot subtype, and outcome
- Percentage of clips below the 3.5s minimum
- Median clip duration
- p90 clip duration
- Merged clip count
- Per-label duration distribution
- Uncertainty rate
- Signal-audit notes for ball / rim / player explanations on a small manual subset

## Process

- Run the same videos through each candidate model path.
- Compare VideoMAE and X-CLIP behind the same recognizer interface.
- Treat VideoMAE and X-CLIP as auxiliary classifiers once structured ball / rim / player signals are enabled.
- Store per-run manifests and summary metrics.
- Keep teacher-label outputs separate from runtime outputs; use the Qwen-based teacher path only for offline audit and pseudo-label generation.
- Use [`docs/disagreement_mining.md`](/Users/hanfei/rork-hoopshighlights-ai_Final/docs/disagreement_mining.md) to turn the unified annotation schema into a manual review queue for runtime-vs-teacher disagreements.
- Promote reviewer corrections from the dashboard into the training set.
- Generate the report with [`services/inference/scripts/run_eval_report.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_eval_report.py).
- For live staging watchability reviews, follow [`docs/live_watchability_review.md`](/Users/hanfei/rork-hoopshighlights-ai_Final/docs/live_watchability_review.md).

## Output

- A short benchmark report in Markdown and JSON
- A regression table with per-class precision, recall, and top-k hit rate
- A taxonomy section with per-class metrics for `eventFamily`, `shotSubtype`, and `outcome`
- Confusion matrices for label, family, subtype, and outcome
- A clip-quality section with duration policy compliance and merge stats
- A signal-audit section showing whether ball / hoop / player features explain the win or failure cases
- A manual review checklist for `contains setup`, `contains finish`, and `feels watchable`
- A list of sample clips that should be reviewed or relabeled

## Recommended Labeling Priorities

- `jumper`, `three`, and `miss` first, because they tend to collapse into one another when shot release is visible but ball flight is not.
- `layup` and `putback` next, because they are the most common overlap with `jumper` and `dunk` in short clips.
- `fast break` after that, because transition plays often look like generic scoring clips without enough context.
- `steal` and `block` last, because they are defensive classes the model usually separates better once motion is obvious.
