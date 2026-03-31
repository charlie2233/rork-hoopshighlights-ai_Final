from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.datasets import annotation_template, build_phase4_pseudo_label_bundle
from services.inference.scripts.build_phase4_pseudo_labels import main as build_phase4_pseudo_labels_main


class Phase4PseudoLabelTests(unittest.TestCase):
    @staticmethod
    def repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def _make_row(
        self,
        *,
        clip_id: str,
        source_domain: str,
        human_verified: bool,
        teacher_confidence: float,
        event_family: str,
        outcome: str,
        shot_subtype: str | None,
        runtime_label: str,
        teacher_notes: str,
    ):
        row = annotation_template(clip_id=clip_id, source_domain=source_domain)
        row.humanVerified = human_verified
        row.eventFamily = event_family
        row.outcome = outcome
        row.shotSubtype = shot_subtype
        row.teacherConfidence = teacher_confidence
        row.ballVisible = True
        row.hoopVisible = True
        row.ballNearRim = 0.84 if event_family == "shot_attempt" else 0.14
        row.ballThroughHoopLikelihood = 0.78 if outcome == "made" else 0.08
        row.possessionChangeLikelihood = 0.11
        row.transitionLikelihood = 0.12
        row.reviewerNotes = teacher_notes
        row.rawRuntimeOutputs = {
            "label": runtime_label,
            "confidence": 0.51,
            "eventFamily": "other",
            "outcome": "uncertain",
            "shotSubtype": None,
        }
        row.rawTeacherOutputs = {
            "confidence": teacher_confidence,
            "eventFamily": event_family,
            "outcome": outcome,
            "shotSubtype": shot_subtype,
            "notes": teacher_notes,
        }
        return row

    def test_build_phase4_pseudo_label_bundle_gates_teacher_backed_in_domain_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_dir = Path(tmp_dir)
            input_path = temp_dir / "phase4_inputs.jsonl"
            rows = [
                self._make_row(
                    clip_id="gold-anchor-001",
                    source_domain="live_staging",
                    human_verified=True,
                    teacher_confidence=1.0,
                    event_family="shot_attempt",
                    outcome="made",
                    shot_subtype="layup",
                    runtime_label="Highlight",
                    teacher_notes="Gold anchor retained separately.",
                ),
                self._make_row(
                    clip_id="teacher-retained-001",
                    source_domain="live_staging",
                    human_verified=False,
                    teacher_confidence=0.93,
                    event_family="shot_attempt",
                    outcome="made",
                    shot_subtype="dunk",
                    runtime_label="Highlight",
                    teacher_notes="Clear made dunk with strong teacher confidence.",
                ),
                self._make_row(
                    clip_id="teacher-low-confidence-001",
                    source_domain="live_staging",
                    human_verified=False,
                    teacher_confidence=0.63,
                    event_family="shot_attempt",
                    outcome="missed",
                    shot_subtype="jumper",
                    runtime_label="Highlight",
                    teacher_notes="Low-confidence missed jumper should be filtered.",
                ),
                self._make_row(
                    clip_id="teacher-outside-domain-001",
                    source_domain="benchmark_eval",
                    human_verified=False,
                    teacher_confidence=0.97,
                    event_family="transition",
                    outcome="uncertain",
                    shot_subtype=None,
                    runtime_label="Fast Break",
                    teacher_notes="Teacher-backed but not in the allowed in-domain slice.",
                ),
            ]
            input_path.write_text(
                "\n".join(json.dumps(row.to_dict(), sort_keys=True) for row in rows),
                encoding="utf-8",
            )

            output_dir = temp_dir / "out"
            manifest = build_phase4_pseudo_label_bundle(
                self.repo_root(),
                output_dir,
                input_paths=[input_path],
                min_teacher_confidence=0.82,
                source_domains=("live_staging",),
            )

            self.assertEqual(manifest["datasetVersion"], "phase4-pseudo-label-v1")
            self.assertEqual(manifest["summary"]["goldAnchorRecords"], 1)
            self.assertEqual(manifest["summary"]["pseudoLabelRecords"], 1)
            self.assertEqual(manifest["summary"]["filteredRecords"], 2)
            self.assertEqual(manifest["summary"]["trainingEligibleRecords"], 1)
            self.assertEqual(manifest["summary"]["teacherSeparatedRecords"], 1)

            gold_rows = [
                json.loads(line)
                for line in (output_dir / "gold_anchor_records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            pseudo_rows = [
                json.loads(line)
                for line in (output_dir / "pseudo_label_records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            filtered_rows = [
                json.loads(line)
                for line in (output_dir / "filtered_records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            self.assertEqual(len(gold_rows), 1)
            self.assertEqual(len(pseudo_rows), 1)
            self.assertEqual(len(filtered_rows), 2)

            gold_row = gold_rows[0]
            pseudo_row = pseudo_rows[0]
            filtered_reasons = {row["gateReason"] for row in filtered_rows}

            self.assertEqual(gold_row["selectedLabelSource"], "gold")
            self.assertEqual(gold_row["recordType"], "gold_anchor")
            self.assertFalse(gold_row["trainingEligible"])
            self.assertTrue(gold_row["humanVerified"])
            self.assertEqual(pseudo_row["selectedLabelSource"], "teacher")
            self.assertEqual(pseudo_row["recordType"], "pseudo_label")
            self.assertTrue(pseudo_row["confidenceGatePassed"])
            self.assertTrue(pseudo_row["trainingEligible"])
            self.assertEqual(pseudo_row["teacherEventFamily"], "shot_attempt")
            self.assertEqual(pseudo_row["selectedDisplayLabel"], "Dunk")
            self.assertEqual(pseudo_row["rawTeacherOutputs"]["confidence"], 0.93)
            self.assertIn("below_confidence_gate", filtered_reasons)
            self.assertIn("outside_in_domain_slice", filtered_reasons)

    def test_phase4_cli_writes_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_dir = Path(tmp_dir)
            input_path = temp_dir / "phase4_inputs.json"
            row = self._make_row(
                clip_id="cli-retained-001",
                source_domain="live_staging",
                human_verified=False,
                teacher_confidence=0.91,
                event_family="shot_attempt",
                outcome="made",
                shot_subtype="layup",
                runtime_label="Highlight",
                teacher_notes="CLI smoke row.",
            )
            input_path.write_text(json.dumps([row.to_dict()], indent=2, sort_keys=True), encoding="utf-8")

            import sys

            argv = sys.argv
            try:
                sys.argv = [
                    "build_phase4_pseudo_labels.py",
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(temp_dir / "out"),
                    "--source-domains",
                    "live_staging",
                ]
                self.assertEqual(build_phase4_pseudo_labels_main(), 0)
            finally:
                sys.argv = argv

            out_dir = temp_dir / "out"
            self.assertTrue((out_dir / "manifest.json").exists())
            self.assertTrue((out_dir / "all_records.jsonl").exists())
            self.assertTrue((out_dir / "gold_anchor_records.jsonl").exists())
            self.assertTrue((out_dir / "pseudo_label_records.jsonl").exists())
            self.assertTrue((out_dir / "filtered_records.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
