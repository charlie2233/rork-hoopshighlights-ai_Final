from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.scripts.run_shadow_eval import (
    build_shadow_comparison_summary,
    build_shadow_report,
    load_batch_records,
    load_manual_audits,
)


class ShadowEvalTests(unittest.TestCase):
    @staticmethod
    def repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def test_builds_shadow_report_for_mixed_batch(self) -> None:
        fixture = self.repo_root() / "services" / "inference" / "tests" / "fixtures" / "shadow_batch_results.json"
        records = load_batch_records([fixture])
        report = build_shadow_report(records)

        self.assertEqual(report["summary"]["jobCount"], 1)
        self.assertEqual(report["summary"]["clipCount"], 4)
        self.assertEqual(report["summary"]["requestIds"], ["req-shadow-001"])
        self.assertEqual(report["summary"]["uploadTraceIds"], ["upload-shadow-001"])
        self.assertEqual(report["summary"]["inferenceAttemptIds"], ["attempt-shadow-001"])
        self.assertEqual(report["summary"]["modelVersions"], ["runtime:v1-shadow"])

        self.assertEqual(report["summary"]["flatLabelDistribution"]["Highlight"], 1)
        self.assertEqual(report["summary"]["flatLabelDistribution"]["Steal"], 1)
        self.assertEqual(report["summary"]["eventFamilyDistribution"]["shot_attempt"], 2)
        self.assertEqual(report["summary"]["eventFamilyDistribution"]["turnover"], 1)
        self.assertEqual(report["summary"]["outcomeDistribution"]["made"], 2)
        self.assertEqual(report["summary"]["outcomeDistribution"]["uncertain"], 2)
        self.assertEqual(report["summary"]["shotSubtypeDistribution"]["null"], 2)
        self.assertEqual(report["summary"]["uncertaintyRate"], 0.25)
        self.assertEqual(report["summary"]["highlightDominance"], 0.25)
        self.assertEqual(report["summary"]["eventFamilyOtherDominance"], 0.25)
        self.assertEqual(report["summary"]["splitOtherDistribution"]["ambiguous_event"], 1)
        self.assertEqual(report["summary"]["otherBucketAudit"]["eligibleOtherClips"], 1)
        self.assertEqual(report["summary"]["otherBucketAudit"]["manualAuditDistribution"]["real_event_missed_by_model"], 1)
        self.assertEqual(report["summary"]["otherBucketAudit"]["trueModelMissRateWithinOther"], 1.0)
        self.assertEqual(report["summary"]["missVsMadeConfusion"]["expectedMissPredictedMadeShot"], 1)
        self.assertEqual(report["summary"]["mixedBatchLabelSpread"]["uniqueLabelCount"], 4)
        self.assertGreaterEqual(report["summary"]["mixedBatchLabelSpread"]["spreadScore"], 0.0)
        self.assertEqual(len(report["collapseExamples"]), 1)
        self.assertGreaterEqual(len(report["labelSpreadWarnings"]), 0)

    def test_report_includes_labeled_eval_metrics_when_expected_fields_exist(self) -> None:
        payload = {
            "jobId": "job-labeled-001",
            "requestId": "req-labeled-001",
            "uploadTraceId": "upload-labeled-001",
            "inferenceAttemptId": "attempt-labeled-001",
            "clips": [
                {
                    "clipId": "clip-labeled-001",
                    "label": "Layup",
                    "eventFamily": "shot_attempt",
                    "shotSubtype": "layup",
                    "outcome": "made",
                    "confidence": 0.88,
                    "clipDurationSeconds": 4.75,
                    "expectedLabel": "Layup",
                    "expectedEventFamily": "shot_attempt",
                    "expectedOutcome": "made",
                    "expectedShotSubtype": "layup",
                    "sourceDomain": "live_shadow",
                },
                {
                    "clipId": "clip-labeled-002",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "shotSubtype": None,
                    "outcome": "uncertain",
                    "confidence": 0.42,
                    "clipDurationSeconds": 4.25,
                    "expectedLabel": "Highlight",
                    "expectedEventFamily": "other",
                    "expectedOutcome": "uncertain",
                    "sourceDomain": "live_shadow",
                },
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "labeled.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            report = build_shadow_report(load_batch_records([path]))

        self.assertEqual(report["summary"]["labeledClipCount"], 2)
        self.assertEqual(report["summary"]["eventDetectionPrecision"], 1.0)
        self.assertEqual(report["summary"]["eventDetectionRecall"], 1.0)
        self.assertEqual(report["summary"]["eventFamilyAccuracy"], 1.0)
        self.assertEqual(report["summary"]["outcomeAccuracy"], 1.0)
        self.assertEqual(report["summary"]["shotSubtypeAccuracy"], 1.0)
        self.assertEqual(report["summary"]["sourceDomainDistribution"]["live_shadow"], 2)

    def test_report_includes_proposal_metrics_for_temporal_shadow(self) -> None:
        payload = {
            "jobId": "job-proposal-001",
            "requestId": "req-proposal-001",
            "uploadTraceId": "upload-proposal-001",
            "inferenceAttemptId": "attempt-proposal-001",
            "clips": [
                {
                    "clipId": "clip-proposal-accepted",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "shotSubtype": None,
                    "outcome": "uncertain",
                    "confidence": 0.41,
                    "clipDurationSeconds": 4.5,
                    "expectedEventFamily": "shot_attempt",
                    "expectedOutcome": "made",
                    "expectedShotSubtype": "layup",
                    "runtimeFusionTemporalShadow": {
                        "modelVersion": "temporal-event-detector-tridet-hybrid-v1",
                        "label": "Layup",
                        "eventFamily": "shot_attempt",
                        "shotSubtype": "layup",
                        "outcome": "made",
                        "confidenceBeforeMapping": 0.88,
                        "confidenceAfterMapping": 0.93,
                        "confidence": 0.93,
                        "isUncertain": False,
                        "temporal_event_detector_classifier_gate_open": True,
                        "temporal_event_detector_family_gate_open": True,
                        "temporal_event_detector_family_gate_rejection_reason": None,
                        "temporal_event_detector_proposal_accepted": True,
                        "temporal_event_detector_event_score": 1.0,
                        "temporal_event_detector_proposal_acceptance_raw_score": 0.88,
                        "temporal_event_detector_proposal_acceptance_probability": 0.94,
                        "temporal_event_detector_proposal_energy_score": 0.11,
                        "temporal_event_detector_proposal_rejector_label": "real_event",
                        "temporal_event_detector_proposal_rejector_confidence": 0.91,
                        "temporal_event_detector_shot_specialist_used": True,
                        "temporal_event_detector_shot_specialist_abstained": False,
                        "temporal_event_detector_event_family": "shot_attempt",
                    },
                },
                {
                    "clipId": "clip-proposal-rejected",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "shotSubtype": None,
                    "outcome": "uncertain",
                    "confidence": 0.41,
                    "clipDurationSeconds": 4.5,
                    "expectedEventFamily": "other",
                    "expectedOutcome": "uncertain",
                    "manualAuditLabel": "true_negative_non_event",
                    "runtimeFusionTemporalShadow": {
                        "modelVersion": "temporal-event-detector-tridet-hybrid-v1",
                        "label": "Highlight",
                        "eventFamily": "other",
                        "shotSubtype": None,
                        "outcome": "uncertain",
                        "confidenceBeforeMapping": 0.32,
                        "confidenceAfterMapping": 0.32,
                        "confidence": 0.32,
                        "isUncertain": True,
                        "temporal_event_detector_classifier_gate_open": False,
                        "temporal_event_detector_family_gate_open": False,
                        "temporal_event_detector_family_gate_rejection_reason": "proposal_rejected",
                        "temporal_event_detector_proposal_accepted": False,
                        "temporal_event_detector_event_score": 0.0,
                        "temporal_event_detector_proposal_acceptance_raw_score": 0.22,
                        "temporal_event_detector_proposal_acceptance_probability": 0.09,
                        "temporal_event_detector_proposal_energy_score": 0.77,
                        "temporal_event_detector_proposal_rejector_label": "non_event",
                        "temporal_event_detector_proposal_rejector_confidence": 0.89,
                        "temporal_event_detector_shot_specialist_used": False,
                        "temporal_event_detector_shot_specialist_abstained": False,
                        "temporal_event_detector_event_family": "other",
                    },
                },
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "proposal-shadow.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            report = build_shadow_report(load_batch_records([path], shadow_source="runtimeFusionTemporalShadow"))

        self.assertEqual(report["summary"]["proposalAcceptanceRate"], 0.5)
        self.assertEqual(report["summary"]["proposalAcceptanceClipCount"], 2)
        self.assertEqual(report["summary"]["proposalAcceptedCount"], 1)
        self.assertEqual(report["summary"]["familyGateOpenRate"], 0.5)
        self.assertEqual(report["summary"]["familyGateOpenCount"], 1)
        self.assertEqual(report["summary"]["shotHeadInvocationRate"], 0.5)
        self.assertEqual(report["summary"]["shotHeadInvocationCount"], 1)
        self.assertIsNotNone(report["summary"]["acceptanceCalibration"])
        self.assertEqual(report["summary"]["acceptanceCalibration"]["scoredClips"], 2)
        self.assertEqual(report["summary"]["eventnessCalibration"]["eligibleClips"], 2)
        self.assertAlmostEqual(report["summary"]["eventnessCalibration"]["brierScore"], 0.0059, places=4)
        self.assertEqual(report["summary"]["acceptedShotProposalOutcomeAccuracy"], 1.0)
        self.assertEqual(report["summary"]["acceptedShotSubtypeDistribution"], {"layup": 1})
        self.assertEqual(report["summary"]["acceptedShotAbstentionRate"], 0.0)
        self.assertIsNotNone(report["summary"]["acceptedShotOutcomeCalibration"])
        self.assertEqual(report["summary"]["acceptedShotOutcomeCalibration"]["scoredClips"], 1)
        self.assertEqual(report["summary"]["acceptedShotOutcomeCalibration"]["brierScore"], 0.0049)
        self.assertEqual(len(report["summary"]["acceptedShotOutcomeCalibration"]["reliabilityBuckets"]), 5)
        self.assertEqual(len(report["summary"]["acceptedShotOutcomeCalibration"]["coverageRiskCurve"]), 1)
        self.assertEqual(report["summary"]["dunkDominance"], 0.0)
        self.assertEqual(report["summary"]["rejectedProposalAudit"]["eligibleRejectedClips"], 1)
        self.assertEqual(report["summary"]["rejectedProposalAudit"]["trueNegativeRate"], 1.0)
        self.assertEqual(report["summary"]["rejectedProposalAudit"]["trueMissRate"], 0.0)

    def test_report_includes_phase4d_proposal_metrics(self) -> None:
        payload = {
            "jobId": "job-proposal-001",
            "requestId": "req-proposal-001",
            "uploadTraceId": "upload-proposal-001",
            "inferenceAttemptId": "attempt-proposal-001",
            "clips": [
                {
                    "clipId": "clip-proposal-accepted",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "outcome": "uncertain",
                    "shotSubtype": None,
                    "expectedEventFamily": "shot_attempt",
                    "expectedOutcome": "made",
                    "runtimeFusionTemporalShadow": {
                        "modelVersion": "temporal-event-detector-tridet-hybrid-v1",
                        "label": "Layup",
                        "eventFamily": "shot_attempt",
                        "outcome": "made",
                        "shotSubtype": "layup",
                        "confidenceBeforeMapping": 0.72,
                        "confidenceAfterMapping": 0.81,
                        "confidence": 0.81,
                        "isUncertain": False,
                        "temporal_event_detector_classifier_gate_open": True,
                        "temporal_event_detector_proposal_accepted": True,
                        "temporal_event_detector_event_score": 0.82,
                        "temporal_event_detector_proposal_acceptance_probability": 0.83,
                        "temporal_event_detector_proposal_energy_score": 0.18,
                        "temporal_event_detector_proposal_rejector_label": "real_event",
                        "temporal_event_detector_proposal_rejector_confidence": 0.88,
                        "temporal_event_detector_shot_specialist_used": True,
                        "temporal_event_detector_shot_specialist_abstained": False,
                    },
                },
                {
                    "clipId": "clip-proposal-rejected-negative",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "outcome": "uncertain",
                    "shotSubtype": None,
                    "expectedEventFamily": "other",
                    "expectedOutcome": "uncertain",
                    "runtimeFusionTemporalShadow": {
                        "modelVersion": "temporal-event-detector-tridet-hybrid-v1",
                        "label": "Highlight",
                        "eventFamily": "other",
                        "outcome": "uncertain",
                        "shotSubtype": None,
                        "confidenceBeforeMapping": 0.28,
                        "confidenceAfterMapping": 0.31,
                        "confidence": 0.31,
                        "isUncertain": True,
                        "temporal_event_detector_classifier_gate_open": False,
                        "temporal_event_detector_proposal_accepted": False,
                        "temporal_event_detector_event_score": 0.18,
                        "temporal_event_detector_proposal_acceptance_probability": 0.19,
                        "temporal_event_detector_proposal_energy_score": 0.65,
                        "temporal_event_detector_proposal_rejector_label": "dead_ball",
                        "temporal_event_detector_proposal_rejector_confidence": 0.74,
                        "temporal_event_detector_shot_specialist_used": False,
                        "temporal_event_detector_shot_specialist_abstained": False,
                    },
                },
                {
                    "clipId": "clip-proposal-rejected-miss",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "outcome": "uncertain",
                    "shotSubtype": None,
                    "expectedEventFamily": "shot_attempt",
                    "expectedOutcome": "missed",
                    "runtimeFusionTemporalShadow": {
                        "modelVersion": "temporal-event-detector-tridet-hybrid-v1",
                        "label": "Highlight",
                        "eventFamily": "other",
                        "outcome": "uncertain",
                        "shotSubtype": None,
                        "confidenceBeforeMapping": 0.34,
                        "confidenceAfterMapping": 0.37,
                        "confidence": 0.37,
                        "isUncertain": True,
                        "temporal_event_detector_classifier_gate_open": False,
                        "temporal_event_detector_proposal_accepted": False,
                        "temporal_event_detector_event_score": 0.27,
                        "temporal_event_detector_proposal_acceptance_probability": 0.24,
                        "temporal_event_detector_proposal_energy_score": 0.59,
                        "temporal_event_detector_proposal_rejector_label": "ambiguous",
                        "temporal_event_detector_proposal_rejector_confidence": 0.58,
                        "temporal_event_detector_shot_specialist_used": False,
                        "temporal_event_detector_shot_specialist_abstained": False,
                    },
                },
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "proposal.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            report = build_shadow_report(load_batch_records([path], shadow_source="runtimeFusionTemporalShadow"))

        self.assertEqual(report["summary"]["proposalAcceptanceRate"], 0.3333)
        self.assertEqual(report["summary"]["familyGateOpenRate"], 0.3333)
        self.assertEqual(report["summary"]["shotHeadInvocationRate"], 0.3333)
        self.assertIsNotNone(report["summary"]["acceptanceCalibration"])
        self.assertEqual(report["summary"]["acceptanceCalibration"]["scoredClips"], 3)
        self.assertEqual(report["summary"]["acceptedShotProposalOutcomeAccuracy"], 1.0)
        self.assertEqual(report["summary"]["acceptedShotSubtypeDistribution"], {"layup": 1})
        self.assertEqual(report["summary"]["acceptedShotAbstentionRate"], 0.0)
        self.assertEqual(report["summary"]["dunkDominance"], 0.0)
        self.assertEqual(report["summary"]["eventnessCalibration"]["eligibleClips"], 3)
        self.assertAlmostEqual(report["summary"]["eventnessCalibration"]["brierScore"], 0.2142, places=4)
        self.assertIsNotNone(report["summary"]["acceptedShotOutcomeCalibration"])
        self.assertEqual(report["summary"]["acceptedShotOutcomeCalibration"]["scoredClips"], 1)
        self.assertAlmostEqual(report["summary"]["acceptedShotOutcomeCalibration"]["brierScore"], 0.0361, places=4)
        self.assertAlmostEqual(report["summary"]["acceptedShotOutcomeCalibration"]["eceLite"], 0.19, places=2)
        self.assertEqual(report["summary"]["rejectedProposalAudit"]["eligibleRejectedClips"], 2)
        self.assertEqual(report["summary"]["rejectedProposalAudit"]["trueNegativeCount"], 1)
        self.assertEqual(report["summary"]["rejectedProposalAudit"]["trueMissCount"], 1)
        self.assertEqual(report["summary"]["rejectedProposalAudit"]["trueNegativeRate"], 0.5)
        self.assertEqual(report["summary"]["rejectedProposalAudit"]["trueMissRate"], 0.5)

    def test_report_exposes_calibration_curve_for_accepted_shots(self) -> None:
        payload = {
            "jobId": "job-calibration-001",
            "requestId": "req-calibration-001",
            "uploadTraceId": "upload-calibration-001",
            "inferenceAttemptId": "attempt-calibration-001",
            "clips": [
                {
                    "clipId": "clip-calibration-accepted-good",
                    "label": "Layup",
                    "eventFamily": "shot_attempt",
                    "shotSubtype": "layup",
                    "outcome": "made",
                    "confidence": 0.91,
                    "confidenceAfterMapping": 0.92,
                    "expectedEventFamily": "shot_attempt",
                    "expectedOutcome": "made",
                    "runtimeFusionTemporalShadow": {
                        "label": "Layup",
                        "eventFamily": "shot_attempt",
                        "shotSubtype": "layup",
                        "outcome": "made",
                        "confidenceAfterMapping": 0.92,
                        "confidence": 0.92,
                        "isUncertain": False,
                        "temporal_event_detector_proposal_accepted": True,
                        "temporal_event_detector_classifier_gate_open": True,
                        "temporal_event_detector_shot_specialist_used": True,
                    },
                },
                {
                    "clipId": "clip-calibration-accepted-bad",
                    "label": "Jumper",
                    "eventFamily": "shot_attempt",
                    "shotSubtype": "jumper",
                    "outcome": "missed",
                    "confidence": 0.22,
                    "confidenceAfterMapping": 0.21,
                    "expectedEventFamily": "shot_attempt",
                    "expectedOutcome": "made",
                    "runtimeFusionTemporalShadow": {
                        "label": "Jumper",
                        "eventFamily": "shot_attempt",
                        "shotSubtype": "jumper",
                        "outcome": "missed",
                        "confidenceAfterMapping": 0.21,
                        "confidence": 0.21,
                        "isUncertain": True,
                        "temporal_event_detector_proposal_accepted": True,
                        "temporal_event_detector_classifier_gate_open": True,
                        "temporal_event_detector_shot_specialist_used": True,
                    },
                },
                {
                    "clipId": "clip-calibration-rejected",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "outcome": "uncertain",
                    "confidenceAfterMapping": 0.14,
                    "expectedEventFamily": "other",
                    "expectedOutcome": "uncertain",
                    "runtimeFusionTemporalShadow": {
                        "label": "Highlight",
                        "eventFamily": "other",
                        "outcome": "uncertain",
                        "confidenceAfterMapping": 0.14,
                        "confidence": 0.14,
                        "isUncertain": True,
                        "temporal_event_detector_proposal_accepted": False,
                        "temporal_event_detector_classifier_gate_open": False,
                        "temporal_event_detector_shot_specialist_used": False,
                    },
                },
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "calibration.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            report = build_shadow_report(load_batch_records([path], shadow_source="runtimeFusionTemporalShadow"))

        calibration = report["summary"]["acceptedShotOutcomeCalibration"]
        self.assertEqual(calibration["scoredClips"], 2)
        self.assertEqual(len(calibration["reliabilityBuckets"]), 5)
        self.assertEqual(len(calibration["coverageRiskCurve"]), 2)
        self.assertAlmostEqual(calibration["brierScore"], 0.0252, places=4)
        self.assertEqual(calibration["coverageRiskCurve"][0]["coverage"], 0.5)
        self.assertEqual(calibration["coverageRiskCurve"][1]["coverage"], 1.0)

    def test_report_warns_on_acceptance_collapse_and_gate_suppression(self) -> None:
        payload = {
            "jobId": "job-guardrail-001",
            "requestId": "req-guardrail-001",
            "uploadTraceId": "upload-guardrail-001",
            "inferenceAttemptId": "attempt-guardrail-001",
            "clips": [
                {
                    "clipId": "clip-guardrail-accepted",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "outcome": "uncertain",
                    "confidenceAfterMapping": 0.33,
                    "expectedEventFamily": "shot_attempt",
                    "expectedOutcome": "made",
                    "runtimeFusionTemporalShadow": {
                        "label": "Highlight",
                        "eventFamily": "other",
                        "outcome": "uncertain",
                        "confidenceAfterMapping": 0.33,
                        "confidence": 0.33,
                        "isUncertain": True,
                        "temporal_event_detector_proposal_accepted": True,
                        "temporal_event_detector_classifier_gate_open": False,
                        "temporal_event_detector_shot_specialist_used": False,
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "guardrail.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            report = build_shadow_report(load_batch_records([path], shadow_source="runtimeFusionTemporalShadow"))

        warnings = report["labelSpreadWarnings"]
        self.assertIn("Proposal acceptance collapsed to 0% or 100%.", warnings)
        self.assertIn("Accepted proposals exist, but family gate never opened.", warnings)
        self.assertIn("Accepted proposals exist, but shot head never invoked.", warnings)

    def test_report_warns_on_zero_acceptance(self) -> None:
        payload = {
            "jobId": "job-guardrail-002",
            "requestId": "req-guardrail-002",
            "uploadTraceId": "upload-guardrail-002",
            "inferenceAttemptId": "attempt-guardrail-002",
            "clips": [
                {
                    "clipId": "clip-guardrail-rejected",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "outcome": "uncertain",
                    "confidenceAfterMapping": 0.18,
                    "expectedEventFamily": "other",
                    "expectedOutcome": "uncertain",
                    "runtimeFusionTemporalShadow": {
                        "label": "Highlight",
                        "eventFamily": "other",
                        "outcome": "uncertain",
                        "confidenceAfterMapping": 0.18,
                        "confidence": 0.18,
                        "isUncertain": True,
                        "temporal_event_detector_proposal_accepted": False,
                        "temporal_event_detector_classifier_gate_open": False,
                        "temporal_event_detector_shot_specialist_used": False,
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "zero-acceptance.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            report = build_shadow_report(load_batch_records([path], shadow_source="runtimeFusionTemporalShadow"))

        self.assertEqual(report["summary"]["proposalAcceptanceRate"], 0.0)
        self.assertIn("Proposal acceptance collapsed to 0% or 100%.", report["labelSpreadWarnings"])

    def test_report_tracks_shot_specialist_abstention(self) -> None:
        payload = {
            "jobId": "job-specialist-001",
            "requestId": "req-specialist-001",
            "uploadTraceId": "upload-specialist-001",
            "inferenceAttemptId": "attempt-specialist-001",
            "clips": [
                {
                    "clipId": "clip-generic-made",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "outcome": "uncertain",
                    "shotSubtype": None,
                    "expectedEventFamily": "shot_attempt",
                    "expectedOutcome": "made",
                    "runtimeFusionTemporalShadow": {
                        "modelVersion": "temporal-event-detector-tridet-shot-specialist-v1",
                        "label": "Made Shot",
                        "eventFamily": "shot_attempt",
                        "outcome": "made",
                        "shotSubtype": None,
                        "confidenceBeforeMapping": 0.61,
                        "confidenceAfterMapping": 0.54,
                        "confidence": 0.54,
                        "isUncertain": True,
                        "metadata": {
                            "temporal_event_detector_proposal_accepted": True,
                            "temporal_event_detector_event_score": 0.74,
                            "temporal_event_detector_shot_specialist_used": True,
                            "temporal_event_detector_shot_specialist_abstained": True,
                        },
                    },
                },
                {
                    "clipId": "clip-dunk-made",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "outcome": "uncertain",
                    "shotSubtype": None,
                    "expectedEventFamily": "shot_attempt",
                    "expectedOutcome": "made",
                    "runtimeFusionTemporalShadow": {
                        "modelVersion": "temporal-event-detector-tridet-shot-specialist-v1",
                        "label": "Dunk",
                        "eventFamily": "shot_attempt",
                        "outcome": "made",
                        "shotSubtype": "dunk",
                        "confidenceBeforeMapping": 0.72,
                        "confidenceAfterMapping": 0.7,
                        "confidence": 0.7,
                        "isUncertain": False,
                        "metadata": {
                            "temporal_event_detector_proposal_accepted": True,
                            "temporal_event_detector_event_score": 0.82,
                            "temporal_event_detector_shot_specialist_used": True,
                            "temporal_event_detector_shot_specialist_abstained": False,
                        },
                    },
                },
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "specialist.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            report = build_shadow_report(load_batch_records([path], shadow_source="runtimeFusionTemporalShadow"))

        self.assertEqual(report["summary"]["acceptedShotProposalOutcomeAccuracy"], 1.0)
        self.assertEqual(report["summary"]["acceptedShotSubtypeDistribution"], {"dunk": 1, "null": 1})
        self.assertEqual(report["summary"]["acceptedShotAbstentionRate"], 0.5)
        self.assertEqual(report["summary"]["dunkDominance"], 0.5)

    def test_cli_writes_markdown_and_json(self) -> None:
        fixture = self.repo_root() / "services" / "inference" / "tests" / "fixtures" / "shadow_batch_results.json"
        records = load_batch_records([fixture])
        report = build_shadow_report(records)

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            json_path = output / "shadow_eval_report.json"
            md_path = output / "shadow_eval_report.md"
            json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
            md_path.write_text("placeholder", encoding="utf-8")

            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

    def test_loads_flat_clip_arrays(self) -> None:
        fixture = self.repo_root() / "services" / "inference" / "tests" / "fixtures" / "shadow_batch_results.json"
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        flat_rows = [
            {
                "jobId": payload["jobId"],
                "requestId": payload["requestId"],
                "uploadTraceId": payload["uploadTraceId"],
                "inferenceAttemptId": payload["inferenceAttemptId"],
                "modelVersion": payload["modelVersion"],
                **clip,
            }
            for clip in payload["clips"]
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "flat.json"
            path.write_text(json.dumps(flat_rows, indent=2), encoding="utf-8")
            records = load_batch_records([path])

        self.assertEqual(len(records), 4)
        self.assertEqual(records[0].jobId, "job-shadow-001")
        self.assertEqual(records[0].flatLabel, "Dunk")

    def test_prefers_runtime_shadow_payload_when_present(self) -> None:
        payload = {
            "jobId": "job-shadow-rt-001",
            "requestId": "req-shadow-rt-001",
            "uploadTraceId": "upload-shadow-rt-001",
            "inferenceAttemptId": "attempt-shadow-rt-001",
            "modelVersion": "videomae:test",
            "clips": [
                {
                    "clipId": "clip-shadow-rt-001",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "shotSubtype": None,
                    "outcome": "uncertain",
                    "confidence": 0.41,
                    "clipDurationSeconds": 4.75,
                    "runtimeFusionShadow": {
                        "runtime_fusion_model_version": "runtime-fusion-v1",
                        "label": "Steal",
                        "eventFamily": "turnover",
                        "shotSubtype": None,
                        "outcome": "uncertain",
                        "confidenceBeforeMapping": 0.62,
                        "confidenceAfterMapping": 0.62,
                        "confidence": 0.62,
                        "isUncertain": True,
                        "runtime_fusion_snapshot": {
                            "videoMAE": [{"label": "steal", "confidence": 0.44}],
                            "xclip": [{"label": "steal", "confidence": 0.51}],
                        },
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "shadow-runtime.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            records = load_batch_records([path])

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.modelVersion, "runtime-fusion-v1")
        self.assertEqual(record.flatLabel, "Steal")
        self.assertEqual(record.eventFamily, "turnover")
        self.assertEqual(record.confidenceAfterMapping, 0.62)
        self.assertEqual(record.rawVideoMAETopK[0]["label"], "steal")

    def test_temporal_shadow_event_family_preserves_hierarchical_label_and_fallback_clip_id(self) -> None:
        payload = {
            "jobId": "job-shadow-temporal-001",
            "requestId": "req-shadow-temporal-001",
            "uploadTraceId": "upload-shadow-temporal-001",
            "inferenceAttemptId": "attempt-shadow-temporal-001",
            "clips": [
                {
                    "label": "Highlight",
                    "eventFamily": "other",
                    "shotSubtype": None,
                    "outcome": "uncertain",
                    "confidence": 0.41,
                    "clipDurationSeconds": 4.75,
                    "runtimeFusionTemporalShadow": {
                        "runtime_fusion_model_version": "temporal-student-gated-v2",
                        "label": "Highlight",
                        "eventFamily": "shot_attempt",
                        "shotSubtype": "layup",
                        "outcome": "uncertain",
                        "confidenceBeforeMapping": 0.93,
                        "confidenceAfterMapping": 0.41,
                        "confidence": 0.41,
                        "isUncertain": True,
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "shadow-temporal.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            records = load_batch_records([path], shadow_source="runtimeFusionTemporalShadow")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].clipId, "job-shadow-temporal-001:clip-1")
        self.assertEqual(records[0].eventFamily, "shot_attempt")

    def test_applies_manual_other_audit_overrides_from_jsonl(self) -> None:
        payload = {
            "jobId": "job-shadow-audit-001",
            "requestId": "req-shadow-audit-001",
            "uploadTraceId": "upload-shadow-audit-001",
            "inferenceAttemptId": "attempt-shadow-audit-001",
            "clips": [
                {
                    "clipId": "clip-shadow-audit-001",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "shotSubtype": None,
                    "outcome": "uncertain",
                    "confidence": 0.44,
                    "clipDurationSeconds": 4.75,
                    "runtimeFusionTemporalShadow": {
                        "runtime_fusion_model_version": "runtime-fusion-temporal-v1",
                        "label": "Highlight",
                        "eventFamily": "other",
                        "eventFamilyOtherBucket": "setup",
                        "eventFamilyOtherBucketReason": "Set offense with weak event evidence.",
                        "confidenceBeforeMapping": 0.44,
                        "confidenceAfterMapping": 0.44,
                        "confidence": 0.44,
                        "isUncertain": True,
                    },
                }
            ],
        }
        audit_row = {
            "clipId": "clip-shadow-audit-001",
            "manualAuditLabel": "true_negative_non_event",
            "manualAuditRationale": "Manual review marked this as a setup clip.",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path = Path(temp_dir) / "shadow-audit.json"
            audit_path = Path(temp_dir) / "audit.jsonl"
            payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            audit_path.write_text(json.dumps(audit_row) + "\n", encoding="utf-8")
            records = load_batch_records(
                [payload_path],
                shadow_source="runtimeFusionTemporalShadow",
                manual_audits=load_manual_audits([audit_path]),
            )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].otherBucket, "setup")
        self.assertEqual(records[0].manualAuditLabel, "true_negative_non_event")
        self.assertEqual(records[0].manualAuditRationale, "Manual review marked this as a setup clip.")

    def test_reports_candidate_namespace_for_temporal_and_distilled_shadow_payloads(self) -> None:
        payload = {
            "jobId": "job-shadow-namespace-001",
            "requestId": "req-shadow-namespace-001",
            "uploadTraceId": "upload-shadow-namespace-001",
            "inferenceAttemptId": "attempt-shadow-namespace-001",
            "modelVersion": "videomae:test",
            "clips": [
                {
                    "clipId": "clip-shadow-namespace-001",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "shotSubtype": None,
                    "outcome": "uncertain",
                    "confidence": 0.42,
                    "clipDurationSeconds": 4.75,
                    "runtimeFusionTemporalShadow": {
                        "runtime_fusion_model_version": "runtime-fusion-temporal-v1",
                        "label": "Layup",
                        "eventFamily": "shot_attempt",
                        "temporal_student_event_spotter_family": "shot_attempt",
                        "shotSubtype": "layup",
                        "outcome": "made",
                        "confidenceBeforeMapping": 0.73,
                        "confidenceAfterMapping": 0.81,
                        "confidence": 0.81,
                        "isUncertain": False,
                        "runtime_fusion_snapshot": {
                            "videoMAE": [{"label": "layup", "confidence": 0.69}],
                            "xclip": [{"label": "layup", "confidence": 0.48}],
                        },
                    },
                    "runtimeFusionDistilledShadow": {
                        "runtime_fusion_model_version": "runtime-fusion-distilled-v1",
                        "label": "Dunk",
                        "eventFamily": "shot_attempt",
                        "shotSubtype": "dunk",
                        "outcome": "made",
                        "confidenceBeforeMapping": 0.79,
                        "confidenceAfterMapping": 0.86,
                        "confidence": 0.86,
                        "isUncertain": False,
                        "runtime_fusion_snapshot": {
                            "videoMAE": [{"label": "dunk", "confidence": 0.72}],
                            "xclip": [{"label": "dunk", "confidence": 0.55}],
                        },
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "shadow-namespaces.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temporal_records = load_batch_records([path], shadow_source="runtimeFusionTemporalShadow")
            distilled_records = load_batch_records([path], shadow_source="runtimeFusionDistilledShadow")

        self.assertEqual(len(temporal_records), 1)
        self.assertEqual(temporal_records[0].candidateNamespace, "runtimeFusionTemporalShadow")
        self.assertEqual(temporal_records[0].modelVersion, "runtime-fusion-temporal-v1")
        self.assertEqual(temporal_records[0].flatLabel, "Layup")
        self.assertEqual(temporal_records[0].eventSpotterFamily, "shot_attempt")

        self.assertEqual(len(distilled_records), 1)
        self.assertEqual(distilled_records[0].candidateNamespace, "runtimeFusionDistilledShadow")
        self.assertEqual(distilled_records[0].modelVersion, "runtime-fusion-distilled-v1")
        self.assertEqual(distilled_records[0].flatLabel, "Dunk")

    def test_auto_prefers_lora_shadow_payload_when_present(self) -> None:
        payload = {
            "jobId": "job-shadow-lora-001",
            "requestId": "req-shadow-lora-001",
            "uploadTraceId": "upload-shadow-lora-001",
            "inferenceAttemptId": "attempt-shadow-lora-001",
            "modelVersion": "videomae:test",
            "clips": [
                {
                    "clipId": "clip-shadow-lora-001",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "shotSubtype": None,
                    "outcome": "uncertain",
                    "confidence": 0.41,
                    "clipDurationSeconds": 4.75,
                    "runtimeFusionShadow": {
                        "runtime_fusion_model_version": "runtime-fusion-v1",
                        "label": "Highlight",
                        "eventFamily": "other",
                        "outcome": "uncertain",
                        "confidence": 0.41,
                    },
                    "runtimeFusionLoRAShadow": {
                        "runtime_fusion_model_version": "videomae-rslora:test",
                        "label": "Dunk",
                        "eventFamily": "shot_attempt",
                        "shotSubtype": "dunk",
                        "outcome": "made",
                        "confidenceBeforeMapping": 0.77,
                        "confidenceAfterMapping": 0.84,
                        "confidence": 0.84,
                        "isUncertain": False,
                        "runtime_fusion_snapshot": {
                            "videoMAE": [{"label": "dunk", "confidence": 0.7}],
                            "xclip": [{"label": "dunk", "confidence": 0.44}],
                        },
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "shadow-lora.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            records = load_batch_records([path], shadow_source="auto")

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.modelVersion, "videomae-rslora:test")
        self.assertEqual(record.flatLabel, "Dunk")
        self.assertEqual(record.eventFamily, "shot_attempt")
        self.assertEqual(record.rawVideoMAETopK[0]["label"], "dunk")

    def test_builds_phase3d_comparison_summary(self) -> None:
        fixture = self.repo_root() / "services" / "inference" / "tests" / "fixtures" / "shadow_batch_results.json"
        candidate_records = load_batch_records([fixture])
        candidate_report = build_shadow_report(candidate_records)

        baseline_payload = json.loads(fixture.read_text(encoding="utf-8"))
        for clip in baseline_payload["clips"]:
            clip["label"] = "Highlight"
            clip["finalLabel"] = "Highlight"
            clip["eventFamily"] = "other"
            clip["shotSubtype"] = None
            clip["outcome"] = "uncertain"
            clip["confidence"] = 0.38
            clip["confidenceBeforeMapping"] = 0.38
            clip["confidenceAfterMapping"] = 0.38
            clip["isUncertain"] = True

        with tempfile.TemporaryDirectory() as temp_dir:
            baseline_path = Path(temp_dir) / "phase3d-baseline.json"
            baseline_path.write_text(json.dumps(baseline_payload, indent=2), encoding="utf-8")
            baseline_report = build_shadow_report(load_batch_records([baseline_path]))

        comparison = build_shadow_comparison_summary(baseline_report["summary"], candidate_report["summary"])

        self.assertGreater(comparison["mixedBatchLabelSpread"]["uniqueLabelCountDelta"], 0)
        self.assertLess(comparison["flatLabel"]["highlightShareDelta"], 0)
        self.assertLessEqual(comparison["uncertaintyRateDelta"], 0)


if __name__ == "__main__":
    unittest.main()
