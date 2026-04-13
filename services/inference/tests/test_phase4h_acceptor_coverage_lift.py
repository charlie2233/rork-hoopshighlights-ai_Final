from __future__ import annotations

import unittest

from services.inference.scripts.run_phase4h_acceptor_coverage_lift import (
    build_acceptance_dataset,
    build_dataset_manifest,
    evaluate_acceptor_sweep,
    recommend_sweep,
    run_acceptor_sweeps,
)
from services.inference.scripts.build_phase4h_hard_negative_label_queue import (
    build_label_queue,
    queue_summary,
)
from services.inference.scripts.build_phase4h_labeling_pack import (
    expand_queue,
    normalize_seed_queue,
    progress_summary,
)
from services.inference.scripts.build_phase4h_label_ingestion import (
    LabelIngestionError,
    build_review_packs,
    build_training_seed,
    compute_retrain_readiness,
    ingest_reviewed_rows,
)


class Phase4hAcceptorCoverageLiftTests(unittest.TestCase):
    def test_bootstrap_dataset_preserves_labels_and_hard_negatives(self) -> None:
        rows = build_acceptance_dataset(
            staging_report={
                "clips": [
                    {
                        "clipId": "made:clip-1",
                        "expectedEventFamily": "shot_attempt",
                        "expectedOutcome": "made",
                        "eventFamily": "other",
                        "proposalAccepted": True,
                        "proposalScore": 0.9,
                        "familyGateOpen": False,
                        "shotHeadInvoked": False,
                    },
                    {
                        "clipId": "miss:clip-1",
                        "expectedEventFamily": "shot_attempt",
                        "expectedOutcome": "missed",
                        "eventFamily": "other",
                        "proposalAccepted": False,
                        "proposalScore": 0.4,
                        "familyGateOpen": False,
                        "shotHeadInvoked": False,
                    },
                    {
                        "clipId": "setup:clip-1",
                        "eventFamily": "other",
                        "proposalAccepted": False,
                        "proposalScore": 0.1,
                        "familyGateOpen": False,
                        "shotHeadInvoked": False,
                    },
                ]
            },
            smoke_report={"clips": []},
            audit_queue={
                "items": [
                    {
                        "clipId": "setup:clip-1",
                        "manualAuditLabel": "true_negative_non_event",
                        "splitOtherBucket": "setup",
                    }
                ]
            },
            accepted_debug={
                "rows": [
                    {
                        "clipId": "made:clip-1",
                        "shadowRelaxedFamilyEval": {
                            "familyGateWouldOpen": True,
                            "shotHeadWouldInvoke": True,
                        },
                    }
                ]
            },
        )

        labels = {row["clipId"]: row["acceptanceLabel"] for row in rows}
        self.assertEqual(labels["made:clip-1"], "accept")
        self.assertEqual(labels["miss:clip-1"], "accept")
        self.assertEqual(labels["setup:clip-1"], "reject")
        hard_negatives = {row["clipId"]: row["hardNegativeBucket"] for row in rows}
        self.assertEqual(hard_negatives["setup:clip-1"], "setup")

        manifest = build_dataset_manifest(rows, baseline_acceptance_rate=0.127)
        self.assertEqual(manifest["acceptanceLabelDistribution"], {"accept": 2, "reject": 1})
        self.assertEqual(manifest["hardNegativeDistribution"], {"setup": 1})

    def test_sweep_lifts_acceptance_without_miss_to_made_drift(self) -> None:
        rows = [
            {
                "datasetSource": "fixture",
                "clipId": "made",
                "eventFamily": "shot_attempt",
                "outcome": "made",
                "expectedOutcome": "made",
                "acceptanceLabel": "accept",
                "acceptanceScore": 0.9,
                "energyScore": -0.7,
                "wouldFamilyGateOpenIfAccepted": True,
                "wouldShotHeadInvokeIfAccepted": True,
            },
            {
                "datasetSource": "fixture",
                "clipId": "miss",
                "eventFamily": "shot_attempt",
                "outcome": "missed",
                "expectedOutcome": "missed",
                "acceptanceLabel": "accept",
                "acceptanceScore": 0.4,
                "energyScore": -0.9,
                "wouldFamilyGateOpenIfAccepted": True,
                "wouldShotHeadInvokeIfAccepted": True,
            },
            {
                "datasetSource": "fixture",
                "clipId": "setup",
                "eventFamily": "other",
                "outcome": "uncertain",
                "acceptanceLabel": "reject",
                "acceptanceScore": 0.1,
                "energyScore": -1.2,
                "wouldFamilyGateOpenIfAccepted": False,
                "wouldShotHeadInvokeIfAccepted": False,
            },
        ]

        sweep = evaluate_acceptor_sweep(
            rows,
            temperature=1.0,
            threshold=0.3,
            energy_threshold=None,
            loss_config="focal_class_balanced:g2.00:a0.65",
            baseline_acceptance_rate=0.127,
        )

        self.assertGreater(sweep["proposalAcceptanceRate"], 0.127)
        self.assertEqual(sweep["familyGateOpenCount"], 2)
        self.assertEqual(sweep["shotHeadInvocationCount"], 2)
        self.assertEqual(sweep["missToMadeDrift"], 0)
        self.assertEqual(sweep["dunkMadeHallucinationSignal"], 0)
        self.assertEqual(sweep["acceptedAuditedRejectCount"], 0)
        self.assertEqual(sweep["flatLabelDistribution"]["Shot Attempt"], 1)

    def test_recommendation_requires_gate_and_shot_stack_coverage(self) -> None:
        rows = [
            {
                "datasetSource": "fixture",
                "clipId": "made",
                "eventFamily": "shot_attempt",
                "outcome": "made",
                "expectedOutcome": "made",
                "acceptanceLabel": "accept",
                "acceptanceScore": 0.9,
                "energyScore": -0.7,
                "wouldFamilyGateOpenIfAccepted": True,
                "wouldShotHeadInvokeIfAccepted": True,
            },
            {
                "datasetSource": "fixture",
                "clipId": "miss",
                "eventFamily": "shot_attempt",
                "outcome": "missed",
                "expectedOutcome": "missed",
                "acceptanceLabel": "accept",
                "acceptanceScore": 0.4,
                "energyScore": -0.9,
                "wouldFamilyGateOpenIfAccepted": True,
                "wouldShotHeadInvokeIfAccepted": True,
            },
            {
                "datasetSource": "fixture",
                "clipId": "unknown",
                "eventFamily": "other",
                "outcome": "uncertain",
                "acceptanceLabel": "unknown",
                "acceptanceScore": 0.2,
                "energyScore": -1.0,
                "wouldFamilyGateOpenIfAccepted": False,
                "wouldShotHeadInvokeIfAccepted": False,
            },
        ]

        recommended = recommend_sweep(run_acceptor_sweeps(rows, baseline_acceptance_rate=0.127))
        self.assertIsNotNone(recommended)
        assert recommended is not None
        self.assertGreater(recommended["proposalAcceptanceRate"], 0.127)
        self.assertGreater(recommended["familyGateOpenCount"], 0)
        self.assertGreater(recommended["shotHeadInvocationCount"], 0)
        self.assertEqual(recommended["missToMadeDrift"], 0)

    def test_hard_negative_label_queue_leaves_manual_labels_blank(self) -> None:
        queue = build_label_queue(
            [
                {
                    "datasetSource": "fixture",
                    "clipId": "other-collapse",
                    "acceptanceLabel": "unknown",
                    "eventFamily": "other",
                    "predictedEventFamily": "other",
                    "predictedFlatLabel": "Highlight",
                    "proposalAccepted": False,
                    "acceptanceScore": 0.2,
                },
                {
                    "datasetSource": "fixture",
                    "clipId": "accepted-shot",
                    "acceptanceLabel": "accept",
                    "eventFamily": "shot_attempt",
                    "predictedEventFamily": "shot_attempt",
                    "predictedFlatLabel": "Made Shot",
                    "proposalAccepted": True,
                    "shotAttempt": True,
                    "acceptanceScore": 0.9,
                },
            ]
        )

        self.assertEqual(len(queue), 2)
        hard_negative = next(row for row in queue if row["queueType"] == "hard_negative_bucket_assignment")
        self.assertEqual(
            hard_negative["candidateHardNegativeBuckets"],
            "dead_ball|replay_or_reaction|setup|true_negative_non_event",
        )
        self.assertEqual(hard_negative["manualHardNegativeBucket"], "")
        self.assertEqual(hard_negative["manualAuditLabel"], "")
        accepted = next(row for row in queue if row["queueType"] == "accepted_proposal_light_label")
        self.assertEqual(accepted["manualShotAttempt"], "")
        self.assertEqual(accepted["manualOutcome"], "")

        summary = queue_summary(queue)
        self.assertEqual(summary["hardNegativeCandidateRows"], 1)
        self.assertEqual(summary["acceptedProposalRows"], 1)

    def test_labeling_pack_keeps_reviewer_fields_blank_and_expands(self) -> None:
        seed_rows = [
            {
                "queueId": "hard:seed-other",
                "queueType": "hard_negative_bucket_assignment",
                "clipId": "seed-other",
                "datasetSource": "phase4h_staging_eval_63clip",
                "predictedFlatLabel": "Highlight",
                "predictedEventFamily": "other",
                "eventFamily": "other",
                "proposalAccepted": "False",
                "priorityReason": "predicted_highlight|event_family_other",
            },
            {
                "queueId": "accepted:seed-shot",
                "queueType": "accepted_proposal_light_label",
                "clipId": "seed-shot",
                "datasetSource": "phase4h_acceptor_smoke_15clip",
                "predictedFlatLabel": "Made Shot",
                "predictedEventFamily": "shot_attempt",
                "eventFamily": "shot_attempt",
                "proposalAccepted": "True",
                "priorityReason": "accepted_proposal",
            },
        ]
        normalized = normalize_seed_queue(seed_rows, audit_by_clip={})
        self.assertEqual(len(normalized), 2)
        for row in normalized:
            self.assertEqual(row["review_status"], "needs_review")
            self.assertEqual(row["qa_status"], "not_started")
            self.assertEqual(row["reviewer_split_other_bucket"], "")
            self.assertEqual(row["reviewer_manual_audit_label"], "")
            self.assertEqual(row["reviewer_shot_attempt"], "")
            self.assertEqual(row["reviewer_outcome"], "")

        report_path = self._write_shadow_report(
            {
                "clips": [
                    {
                        "clipId": "new-other",
                        "flatLabel": "Highlight",
                        "eventFamily": "other",
                        "proposalAccepted": False,
                        "sourceDomain": "fixture",
                    },
                    {
                        "clipId": "new-shot",
                        "flatLabel": "Highlight",
                        "eventFamily": "other",
                        "expectedEventFamily": "shot_attempt",
                        "proposalAccepted": False,
                        "sourceDomain": "fixture",
                    },
                ]
            }
        )
        expanded = expand_queue(normalized, [report_path], audit_by_clip={})
        self.assertGreater(len(expanded), len(normalized))
        self.assertTrue(all(row["review_status"] == "needs_review" for row in expanded))
        self.assertIn("possible_real_event_miss", {row["candidate_bucket"] for row in expanded})

        progress = progress_summary(normalized=normalized, expanded=expanded)
        self.assertEqual(progress["expanded"]["confirmedRowsByBucket"]["dead_ball"], 0)
        self.assertEqual(progress["recommendation"], "continue labeling")

        report_path.unlink()

    def test_label_ingestion_slices_review_packs_by_priority(self) -> None:
        rows = [
            {
                "row_id": "accepted:1",
                "clip_id": "clip-a",
                "source_batch": "phase4h_staging_eval_63clip",
                "candidate_bucket": "accepted_proposal_light_label",
                "candidate_reason": "proposal_accepted",
                "proposal_accepted": "true",
                "priority_score": "0.9",
                "source_artifact_path": "artifact.json",
                "job_id": "job-a",
                "request_id": "request-a",
                "upload_trace_id": "upload-a",
                "inference_attempt_id": "attempt-a",
            },
            {
                "row_id": "hard:1",
                "clip_id": "clip-b",
                "source_batch": "phase4h_staging_eval_63clip",
                "candidate_bucket": "dead_ball|replay_or_reaction|setup|true_negative_non_event",
                "candidate_reason": "needs_human_bucket_assignment",
                "priority_score": "0.8",
                "source_artifact_path": "artifact.json",
                "job_id": "job-b",
                "request_id": "request-b",
                "upload_trace_id": "upload-b",
                "inference_attempt_id": "attempt-b",
            },
            {
                "row_id": "miss:1",
                "clip_id": "clip-c",
                "source_batch": "phase4h_staging_eval_63clip",
                "candidate_bucket": "possible_real_event_miss",
                "candidate_reason": "predicted_event_family_other",
                "predicted_event_family": "other",
                "priority_score": "0.7",
            },
            {
                "row_id": "miss:dupe",
                "clip_id": "clip-a",
                "source_batch": "phase4h_staging_eval_63clip",
                "candidate_bucket": "possible_real_event_miss",
                "candidate_reason": "duplicate_clip_lower_priority",
                "predicted_event_family": "other",
                "priority_score": "0.1",
            },
        ]

        packs = build_review_packs(rows)

        self.assertEqual(len(packs["review_pack_01_accepted_proposals"]), 1)
        self.assertEqual(len(packs["review_pack_02_hard_negatives_priority"]), 1)
        self.assertEqual(len(packs["review_pack_03_remaining_predicted_other"]), 1)
        self.assertEqual(packs["review_pack_01_accepted_proposals"][0]["clip_id"], "clip-a")
        self.assertEqual(packs["review_pack_03_remaining_predicted_other"][0]["clip_id"], "clip-c")
        self.assertIn("provenance_score=", packs["review_pack_02_hard_negatives_priority"][0]["pack_priority_reason"])

    def test_label_ingestion_rejects_malformed_reviewer_values(self) -> None:
        with self.assertRaises(LabelIngestionError):
            ingest_reviewed_rows(
                [
                    {
                        "row_id": "bad:1",
                        "clip_id": "clip-bad",
                        "reviewer_split_other_bucket": "dead-ball-ish",
                        "review_status": "reviewed",
                        "qa_status": "passed",
                    }
                ]
            )

    def test_label_ingestion_excludes_conflicting_clip_labels(self) -> None:
        confirmed, conflicts = ingest_reviewed_rows(
            [
                {
                    "row_id": "row:1",
                    "clip_id": "clip-conflict",
                    "source_batch": "fixture",
                    "candidate_bucket": "dead_ball|replay_or_reaction|setup|true_negative_non_event",
                    "reviewer_split_other_bucket": "dead_ball",
                    "review_status": "reviewed",
                    "qa_status": "passed",
                },
                {
                    "row_id": "row:2",
                    "clip_id": "clip-conflict",
                    "source_batch": "fixture",
                    "candidate_bucket": "dead_ball|replay_or_reaction|setup|true_negative_non_event",
                    "reviewer_split_other_bucket": "setup",
                    "review_status": "reviewed",
                    "qa_status": "passed",
                },
            ]
        )

        self.assertEqual(confirmed, [])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["clip_id"], "clip-conflict")

    def test_retrain_readiness_uses_confirmed_labels_only(self) -> None:
        confirmed, conflicts = ingest_reviewed_rows(
            [
                {
                    "row_id": "row:dead",
                    "clip_id": "clip-dead",
                    "source_batch": "fixture",
                    "candidate_bucket": "dead_ball|replay_or_reaction|setup|true_negative_non_event",
                    "reviewer_split_other_bucket": "dead_ball",
                    "review_status": "reviewed",
                    "qa_status": "passed",
                },
                {
                    "row_id": "row:accepted",
                    "clip_id": "clip-shot",
                    "source_batch": "fixture",
                    "candidate_bucket": "accepted_proposal_light_label",
                    "reviewer_shot_attempt": "true",
                    "reviewer_outcome": "missed",
                    "review_status": "reviewed",
                    "qa_status": "passed",
                },
                {
                    "row_id": "row:blank",
                    "clip_id": "clip-blank",
                    "source_batch": "fixture",
                    "candidate_bucket": "dead_ball|replay_or_reaction|setup|true_negative_non_event",
                    "review_status": "needs_review",
                    "qa_status": "not_started",
                },
            ]
        )
        readiness = compute_retrain_readiness(
            confirmed_rows=confirmed,
            expanded_rows=[
                {"clip_id": "clip-dead"},
                {"clip_id": "clip-shot"},
                {"clip_id": "clip-blank"},
            ],
            conflicts=conflicts,
        )
        seed = build_training_seed(confirmed)

        self.assertEqual(readiness["confirmedCountsByBucket"]["dead_ball"], 1)
        self.assertEqual(readiness["acceptedProposalLightLabelCount"], 1)
        self.assertFalse(readiness["localPreRetrainUnlocked"])
        self.assertEqual(readiness["recommendation"], "continue labeling")
        self.assertEqual(len(seed), 2)
        labels = {row["clipId"]: row["acceptorLabel"] for row in seed}
        self.assertEqual(labels["clip-dead"], "reject")
        self.assertEqual(labels["clip-shot"], "accept")

    def _write_shadow_report(self, payload: dict) -> "Path":
        from pathlib import Path
        import json
        import tempfile

        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        with handle:
            json.dump(payload, handle)
        return Path(handle.name)


if __name__ == "__main__":
    unittest.main()
