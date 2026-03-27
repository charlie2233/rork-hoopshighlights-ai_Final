# Eval Harness

## Goal

Measure whether the learned cloud pipeline improves on the current heuristic-heavy baseline without breaking the iOS fallback path.

## Benchmark Set

- Build a fixed sample set of basketball clips with clip-level labels.
- Include made shots, misses, dunks, layups, fast breaks, steals, blocks, and ambiguous non-highlight segments.
- Keep a held-out slice for regression checks.

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

## Process

- Run the same videos through each candidate model path.
- Compare VideoMAE and X-CLIP behind the same recognizer interface.
- Store per-run manifests and summary metrics.
- Promote reviewer corrections from the dashboard into the training set.

## Output

- A short benchmark report
- A regression table
- A list of sample clips that should be reviewed or relabeled

