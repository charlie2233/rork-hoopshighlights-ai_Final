# Phase 4h Label Ingestion Workflow

## Scope

- Branch: `codex/phase4h-label-ingestion-and-retrain-gate`.
- Purpose: turn reviewer-filled Phase 4h queues into confirmed-label and training-seed artifacts for a future acceptor retrain.
- This workflow does not retrain a checkpoint, run another smoke batch, run a medium batch, or change runtime thresholds.
- Raw source queues remain immutable inputs. Reviewers should edit copies of the review packs, not `hard_negative_label_queue_expanded.csv`.

## Review Packs

Generated packs live under `services/inference/evals/phase4h_acceptor_coverage_lift/`.

- `review_pack_01_accepted_proposals.csv`: accepted-proposal rows first; reviewers fill `reviewer_shot_attempt` and `reviewer_outcome` when visible.
- `review_pack_02_hard_negatives_priority.csv`: prioritized likely `dead_ball`, `replay_or_reaction`, `setup`, and `true_negative_non_event` candidates.
- `review_pack_03_remaining_predicted_other.csv`: remaining predicted-other/model-miss candidates not assigned to the first two packs.

Every pack preserves clip provenance:

- `clip_id`
- `job_id`
- `request_id`
- `upload_trace_id`
- `inference_attempt_id`
- `source_batch`
- `source_artifact_path`
- `candidate_bucket`
- `candidate_reason`

## Reviewer Fields

Reviewers should only fill reviewer-owned fields.

- `reviewer_split_other_bucket`: one of `dead_ball`, `replay_or_reaction`, `setup`, `true_negative_non_event`, `ambiguous_event`, `other_true_unknown`, or blank.
- `reviewer_manual_audit_label`: one of `true_negative_non_event`, `real_event_missed_by_model`, `ambiguous_clip`, `data_sampling_issue`, `accepted_proposal_valid`, `accepted_proposal_false_positive`, or blank.
- `reviewer_shot_attempt`: `true`, `false`, `uncertain`, or blank.
- `reviewer_outcome`: `made`, `missed`, `blocked`, `uncertain`, or blank.
- `review_status`: set to `reviewed` once a reviewer has entered truth fields.
- `reviewed_by`: reviewer name or handle.
- `review_timestamp`: ISO-like timestamp when review was completed.
- `qa_status`: `not_started`, `needs_qa`, `passed`, `failed`, or `needs_rework`.
- `notes`: optional notes for edge cases, missing video, ambiguous camera angle, or QA comments.

Ambiguous clips do not need a forced hard-negative bucket. Mark `reviewer_manual_audit_label=ambiguous_clip`, or use `reviewer_split_other_bucket=ambiguous_event` when the clip is clearly not clean enough for accept/reject training.

## Commands

Regenerate review packs from the immutable expanded queue:

```bash
python3 services/inference/scripts/build_phase4h_label_ingestion.py --mode packs
```

Ingest reviewed packs and update confirmed outputs:

```bash
python3 services/inference/scripts/build_phase4h_label_ingestion.py --mode ingest \
  --reviewed-pack services/inference/evals/phase4h_acceptor_coverage_lift/review_pack_01_accepted_proposals.csv \
  --reviewed-pack services/inference/evals/phase4h_acceptor_coverage_lift/review_pack_02_hard_negatives_priority.csv \
  --reviewed-pack services/inference/evals/phase4h_acceptor_coverage_lift/review_pack_03_remaining_predicted_other.csv
```

Run both pack generation and ingestion:

```bash
python3 services/inference/scripts/build_phase4h_label_ingestion.py --mode all
```

## Validation

The ingestion script rejects malformed reviewer values and duplicate `row_id` values. It detects duplicate `clip_id` rows after review and excludes conflicting clip labels from confirmed outputs until a reviewer resolves them.

When conflicts exist, the script writes:

- `services/inference/evals/phase4h_acceptor_coverage_lift/conflicts_report.csv`

Confirmed labels are written only when `review_status` is `reviewed` or `qa_reviewed`, QA has not failed, and at least one reviewer truth field is present.

## Outputs

- `confirmed_phase4h_labels.csv`: confirmed reviewer labels with provenance and duplicate metadata.
- `confirmed_phase4h_labels.jsonl`: JSONL mirror of confirmed labels.
- `phase4h_acceptor_training_seed.jsonl`: confirmed-only seed rows for eventual acceptor retrain prep. Rows with ambiguous labels are preserved with `useForTraining=false`.
- `phase4h_retrain_readiness_summary.json`: machine-readable unlock status.
- `docs/phase4h_retrain_readiness_report.md`: human-readable readiness report.

## Retrain Gate

Local pre-retrain unlock bars:

- At least `20` confirmed `dead_ball`.
- At least `20` confirmed `replay_or_reaction`.
- At least `20` confirmed `setup`.
- At least `20` confirmed `true_negative_non_event`.
- At least `25` accepted-proposal light labels.

Roadmap context target:

- `300` tagged Phase 4h clips overall.

Do not start acceptor retrain prep until the local pre-retrain bars are met and conflicts are resolved or explicitly excluded.
