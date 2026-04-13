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


if __name__ == "__main__":
    unittest.main()
