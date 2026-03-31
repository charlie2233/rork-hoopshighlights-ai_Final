from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.inference.app.distilled_clip_encoder import build_distilled_clip_feature_dict
from services.inference.app.runtime_models.teacher_distilled_student import (
    TEACHER_DISTILLED_STUDENT_BUNDLE_PATH,
    load_teacher_distilled_student_bundle,
)
from services.inference.scripts.train_basketball_runtime_candidates import build_summary
import services.inference.training.teacher_distilled_student as training
from services.inference.training.teacher_distilled_student import (
    TEACHER_DISTILLED_STUDENT_FEATURE_VERSION,
    TEACHER_DISTILLED_STUDENT_MODEL_VERSION,
    TEACHER_DISTILLED_STUDENT_SCHEMA_VERSION,
    TeacherDistilledStudentResult,
    build_teacher_distilled_student_bundle,
    fit_teacher_distilled_student,
)
from services.inference.training.distilled_clip_encoder import DistilledClipTrainingExample


class TeacherDistilledStudentTests(unittest.TestCase):
    @staticmethod
    def repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def _example(
        self,
        *,
        clip_id: str,
        source_kind: str,
        source_domain: str,
        source_set: str,
        split: str,
        weight: float,
        event_family: str,
        outcome: str,
        shot_subtype: str | None,
        label_source: str,
        teacher_confidence: float | None,
        human_verified: bool,
        raw_runtime_outputs: dict[str, object],
        raw_teacher_outputs: dict[str, object] | None,
        clip_duration_seconds: float,
        event_center_seconds: float,
        pre_roll_seconds: float,
        post_roll_seconds: float,
        source_event_count: int,
        was_merged: bool,
        ball_visible: bool,
        hoop_visible: bool,
        ball_near_rim: float,
        ball_through_hoop_likelihood: float,
        possession_change_likelihood: float,
        transition_likelihood: float,
    ) -> DistilledClipTrainingExample:
        snapshot = {
            "sourceKind": source_kind,
            "sourceDomain": source_domain,
            "sourceSet": source_set,
            "humanVerified": human_verified,
            "ballVisible": ball_visible,
            "hoopVisible": hoop_visible,
            "ballNearRim": ball_near_rim,
            "ballThroughHoopLikelihood": ball_through_hoop_likelihood,
            "possessionChangeLikelihood": possession_change_likelihood,
            "transitionLikelihood": transition_likelihood,
            "clipDurationSeconds": clip_duration_seconds,
            "eventCenterSeconds": event_center_seconds,
            "preRollSeconds": pre_roll_seconds,
            "postRollSeconds": post_roll_seconds,
            "sourceEventCount": source_event_count,
            "wasMerged": was_merged,
            "rawRuntimeOutputs": raw_runtime_outputs,
        }
        return DistilledClipTrainingExample(
            clip_id=clip_id,
            source_kind=source_kind,
            source_domain=source_domain,
            source_set=source_set,
            split=split,
            weight=weight,
            ignored=weight <= 0.0,
            event_family=event_family,
            outcome=outcome,
            shot_subtype=shot_subtype,
            label_source=label_source,
            teacher_confidence=teacher_confidence,
            human_verified=human_verified,
            raw_runtime_outputs=raw_runtime_outputs,
            raw_teacher_outputs=raw_teacher_outputs,
            features=build_distilled_clip_feature_dict(snapshot),
        )

    def _augmented_examples(self) -> list[DistilledClipTrainingExample]:
        examples = [
            self._example(
                clip_id="gold-dunk-train",
                source_kind="gold",
                source_domain="broadcast:gold",
                source_set="gold_set",
                split="train",
                weight=4.0,
                event_family="shot_attempt",
                outcome="made",
                shot_subtype="dunk",
                label_source="human",
                teacher_confidence=None,
                human_verified=True,
                raw_runtime_outputs={
                    "label": "Dunk",
                    "eventFamily": "shot_attempt",
                    "outcome": "made",
                    "shotSubtype": "dunk",
                    "clipDurationSeconds": 4.9,
                    "eventCenterSeconds": 2.3,
                    "preRollSeconds": 2.2,
                    "postRollSeconds": 2.7,
                    "sourceEventCount": 1,
                    "wasMerged": False,
                    "topKLabels": ["dunk", "layup", "jumper"],
                    "videoMAE": {"topK": [{"label": "dunk", "confidence": 0.92}]},
                    "xclip": {"topK": [{"label": "dunk", "confidence": 0.81}]},
                },
                raw_teacher_outputs={
                    "confidence": 0.97,
                    "evidence": {
                        "structuredSignals": {
                            "ballNearRim": 0.91,
                            "ballThroughHoopLikelihood": 0.88,
                            "possessionChangeLikelihood": 0.08,
                            "transitionLikelihood": 0.04,
                        },
                        "perceptionSummary": {"ballVisible": True, "hoopVisible": True},
                    },
                    "pseudoLabel": {"eligible": True},
                },
                clip_duration_seconds=4.9,
                event_center_seconds=2.3,
                pre_roll_seconds=2.2,
                post_roll_seconds=2.7,
                source_event_count=1,
                was_merged=False,
                ball_visible=True,
                hoop_visible=True,
                ball_near_rim=0.91,
                ball_through_hoop_likelihood=0.88,
                possession_change_likelihood=0.08,
                transition_likelihood=0.04,
            ),
            self._example(
                clip_id="silver-layup-train",
                source_kind="silver",
                source_domain="teacher:high",
                source_set="silver_set",
                split="train",
                weight=1.5,
                event_family="shot_attempt",
                outcome="missed",
                shot_subtype="layup",
                label_source="teacher",
                teacher_confidence=0.93,
                human_verified=False,
                raw_runtime_outputs={
                    "label": "Highlight",
                    "eventFamily": "shot_attempt",
                    "outcome": "uncertain",
                    "shotSubtype": "layup",
                    "clipDurationSeconds": 4.8,
                    "eventCenterSeconds": 2.4,
                    "preRollSeconds": 2.1,
                    "postRollSeconds": 2.7,
                    "sourceEventCount": 1,
                    "wasMerged": False,
                    "topKLabels": ["layup", "jumper", "playing basketball"],
                },
                raw_teacher_outputs={
                    "confidence": 0.93,
                    "eventFamily": "shot_attempt",
                    "outcome": "missed",
                    "shotSubtype": "layup",
                    "evidence": {
                        "structuredSignals": {
                            "ballNearRim": 0.79,
                            "ballThroughHoopLikelihood": 0.14,
                            "possessionChangeLikelihood": 0.24,
                            "transitionLikelihood": 0.05,
                        },
                        "perceptionSummary": {"ballVisible": True, "hoopVisible": True},
                    },
                    "pseudoLabel": {"eligible": True},
                },
                clip_duration_seconds=4.8,
                event_center_seconds=2.4,
                pre_roll_seconds=2.1,
                post_roll_seconds=2.7,
                source_event_count=1,
                was_merged=False,
                ball_visible=True,
                hoop_visible=True,
                ball_near_rim=0.79,
                ball_through_hoop_likelihood=0.14,
                possession_change_likelihood=0.24,
                transition_likelihood=0.05,
            ),
            self._example(
                clip_id="disagreement-turnover",
                source_kind="disagreement",
                source_domain="hard_negative:replay",
                source_set="disagreement_queue",
                split="train",
                weight=0.7,
                event_family="turnover",
                outcome="uncertain",
                shot_subtype=None,
                label_source="teacher",
                teacher_confidence=0.91,
                human_verified=False,
                raw_runtime_outputs={
                    "label": "Highlight",
                    "eventFamily": "other",
                    "outcome": "uncertain",
                    "shotSubtype": None,
                    "clipDurationSeconds": 4.6,
                    "eventCenterSeconds": 2.2,
                    "preRollSeconds": 2.0,
                    "postRollSeconds": 2.6,
                    "sourceEventCount": 1,
                    "wasMerged": False,
                    "topKLabels": ["playing basketball", "dribbling basketball", "fast break"],
                },
                raw_teacher_outputs={
                    "confidence": 0.91,
                    "eventFamily": "turnover",
                    "outcome": "uncertain",
                    "shotSubtype": None,
                    "reasons": ["runtime teacher disagree", "app facing highlight only"],
                    "evidence": {
                        "structuredSignals": {
                            "ballNearRim": 0.04,
                            "ballThroughHoopLikelihood": 0.02,
                            "possessionChangeLikelihood": 0.66,
                            "transitionLikelihood": 0.32,
                        },
                        "perceptionSummary": {"ballVisible": True, "hoopVisible": False},
                    },
                    "pseudoLabel": {"eligible": False},
                },
                clip_duration_seconds=4.6,
                event_center_seconds=2.2,
                pre_roll_seconds=2.0,
                post_roll_seconds=2.6,
                source_event_count=1,
                was_merged=False,
                ball_visible=True,
                hoop_visible=False,
                ball_near_rim=0.04,
                ball_through_hoop_likelihood=0.02,
                possession_change_likelihood=0.66,
                transition_likelihood=0.32,
            ),
            self._example(
                clip_id="gold-steal-eval",
                source_kind="gold",
                source_domain="broadcast:gold",
                source_set="gold_set",
                split="val",
                weight=4.0,
                event_family="turnover",
                outcome="uncertain",
                shot_subtype=None,
                label_source="human",
                teacher_confidence=None,
                human_verified=True,
                raw_runtime_outputs={
                    "label": "Steal",
                    "eventFamily": "turnover",
                    "outcome": "uncertain",
                    "shotSubtype": None,
                    "clipDurationSeconds": 5.1,
                    "eventCenterSeconds": 2.5,
                    "preRollSeconds": 2.4,
                    "postRollSeconds": 2.7,
                    "sourceEventCount": 1,
                    "wasMerged": False,
                    "topKLabels": ["steal", "fast break", "block"],
                },
                raw_teacher_outputs=None,
                clip_duration_seconds=5.1,
                event_center_seconds=2.5,
                pre_roll_seconds=2.4,
                post_roll_seconds=2.7,
                source_event_count=1,
                was_merged=False,
                ball_visible=True,
                hoop_visible=False,
                ball_near_rim=0.06,
                ball_through_hoop_likelihood=0.01,
                possession_change_likelihood=0.72,
                transition_likelihood=0.51,
            ),
        ]
        return [training._augment_example(example) for example in examples]

    def test_teacher_distilled_student_uses_candidate_windows_and_weights_hard_examples(self) -> None:
        raw_examples = self._augmented_examples()
        self.assertGreater(raw_examples[2].weight, 0.7)

        bundle, manifest = fit_teacher_distilled_student(raw_examples)
        evaluation_rows, baseline_metrics, distilled_metrics, comparison = training.evaluate_teacher_distilled_student(bundle, raw_examples)
        snapshot = {
            "sourceKind": "live",
            "sourceDomain": "staging:smoke",
            "sourceSet": "mixed",
            "humanVerified": False,
            "ballVisible": True,
            "hoopVisible": True,
            "ballNearRim": 0.93,
            "ballThroughHoopLikelihood": 0.88,
            "possessionChangeLikelihood": 0.05,
            "transitionLikelihood": 0.03,
            "clipDurationSeconds": 4.9,
            "eventCenterSeconds": 2.3,
            "preRollSeconds": 2.2,
            "postRollSeconds": 2.7,
            "sourceEventCount": 1,
            "wasMerged": False,
            "rawRuntimeOutputs": {
                "label": "Dunk",
                "eventFamily": "shot_attempt",
                "outcome": "made",
                "shotSubtype": "dunk",
                "topKLabels": ["dunk", "layup", "jumper"],
                "videoMAE": {"topK": [{"label": "dunk", "confidence": 0.95}]},
                "xclip": {"topK": [{"label": "dunk", "confidence": 0.83}]},
            },
        }
        prediction = bundle.predict_from_snapshot(snapshot)

        self.assertEqual(bundle.schema_version, TEACHER_DISTILLED_STUDENT_SCHEMA_VERSION)
        self.assertEqual(bundle.feature_version, TEACHER_DISTILLED_STUDENT_FEATURE_VERSION)
        self.assertEqual(bundle.model_version, TEACHER_DISTILLED_STUDENT_MODEL_VERSION)
        self.assertIn("clipDurationSeconds", bundle.feature_names)
        self.assertGreaterEqual(manifest["summary"]["activeExamples"], 1)
        self.assertGreaterEqual(len(evaluation_rows), 1)
        self.assertIn("eventFamilyDelta", comparison)
        self.assertIn("eventCenterSeconds", bundle.feature_names)
        self.assertEqual(prediction.event_family, "shot_attempt")
        self.assertEqual(prediction.outcome, "made")
        self.assertEqual(prediction.shot_subtype, "dunk")
        self.assertEqual(prediction.display_label, "Dunk")
        self.assertFalse(prediction.is_uncertain)
        self.assertIn("distilledClipEncoderSchemaVersion", prediction.metadata)
        self.assertEqual(prediction.metadata["distilledClipEncoderSchemaVersion"], bundle.schema_version)
        self.assertGreaterEqual(baseline_metrics["sampleCount"], 1)
        self.assertGreaterEqual(distilled_metrics["sampleCount"], 1)

    def test_build_helper_writes_bundle_manifest_and_report(self) -> None:
        augmented = self._augmented_examples()
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            with patch.object(training, "load_teacher_distilled_examples", return_value=augmented):
                result = build_teacher_distilled_student_bundle(self.repo_root(), output_dir)

            self.assertIsInstance(result, TeacherDistilledStudentResult)
            self.assertTrue((output_dir / "bundle.json").exists())
            self.assertTrue((output_dir / "manifest.json").exists())
            self.assertTrue((output_dir / "report.md").exists())
            self.assertEqual(result.manifest["schemaVersion"], TEACHER_DISTILLED_STUDENT_SCHEMA_VERSION)
            self.assertGreater(result.manifest["summary"]["activeWeight"], 0.0)
            self.assertIn("flatLabelSpreadDelta", result.comparison)

    def test_runtime_wrapper_loads_saved_bundle(self) -> None:
        augmented = self._augmented_examples()
        bundle, _ = fit_teacher_distilled_student(augmented)
        with tempfile.TemporaryDirectory() as tmp_dir:
            model_path = Path(tmp_dir) / "teacher_distilled_clip_student_v1.json"
            bundle.save(model_path)
            loaded = load_teacher_distilled_student_bundle(model_path)

        self.assertEqual(loaded.model_version, bundle.model_version)
        self.assertEqual(loaded.schema_version, bundle.schema_version)
        self.assertEqual(loaded.feature_version, bundle.feature_version)
        self.assertEqual(TEACHER_DISTILLED_STUDENT_BUNDLE_PATH.name, "teacher_distilled_clip_student_v1.json")

    def test_candidate_comparison_prefers_teacher_distilled_student(self) -> None:
        summary = build_summary(
            baseline_metrics={
                "eventFamilyAccuracy": 0.62,
                "outcomeAccuracy": 0.58,
                "shotSubtypeAccuracy": 0.31,
                "flatLabelSpread": 2,
                "uncertaintyRate": 0.9,
            },
            temporal_metrics={
                "eventFamilyAccuracy": 0.67,
                "outcomeAccuracy": 0.61,
                "shotSubtypeAccuracy": 0.35,
                "flatLabelSpread": 3,
                "uncertaintyRate": 0.72,
            },
            distilled_metrics={
                "eventFamilyAccuracy": 0.74,
                "outcomeAccuracy": 0.69,
                "shotSubtypeAccuracy": 0.41,
                "flatLabelSpread": 4,
                "uncertaintyRate": 0.55,
            },
        )

        self.assertEqual(summary["scoreboard"]["phase3e2Baseline"]["eventFamilyAccuracy"], 0.62)
        self.assertEqual(summary["winner"], "teacherDistilledStudent")
        self.assertGreater(summary["winnerScore"], 0.0)


if __name__ == "__main__":
    unittest.main()
