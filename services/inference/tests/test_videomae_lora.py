from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from services.inference.training.videomae_lora import (
    VIDEO_LORA_SCHEMA_VERSION,
    BasketballClipExample,
    BasketballLabelSpaces,
    build_basketball_label_spaces,
    build_videomae_lora_examples,
    build_videomae_lora_manifest,
    export_lora_logits_artifacts,
    load_videomae_lora_export,
    normalize_label,
)


class VideoMAELoRATests(unittest.TestCase):
    def test_normalize_label(self) -> None:
        self.assertEqual(normalize_label("Made Shot"), "made_shot")
        self.assertEqual(normalize_label(None), "unknown")

    def test_build_examples_has_video_backed_and_disagreement_entries(self) -> None:
        examples, label_spaces = build_videomae_lora_examples(Path("/Users/hanfei/rork-hoopshighlights-ai_Final"))
        self.assertGreater(len(examples), 0)
        self.assertIn("shot_attempt", label_spaces.event_family)
        self.assertTrue(any(example.source_kind == "disagreement" for example in examples))
        self.assertTrue(any(example.video_available for example in examples))
        self.assertTrue(any(not example.video_available for example in examples))

    def test_manifest_marks_gold_anchor_and_schema_version(self) -> None:
        repo_root = Path("/Users/hanfei/rork-hoopshighlights-ai_Final")
        examples, label_spaces = build_videomae_lora_examples(repo_root)
        manifest = build_videomae_lora_manifest(repo_root=repo_root, examples=examples, label_spaces=label_spaces)
        self.assertEqual(manifest["schemaVersion"], VIDEO_LORA_SCHEMA_VERSION)
        self.assertGreater(manifest["summary"]["videoAvailableExamples"], 0)
        self.assertIn("gold", manifest["summary"]["sourceCounts"])

    def test_can_load_exported_lora_dataset(self) -> None:
        repo_root = Path("/Users/hanfei/rork-hoopshighlights-ai_Final")
        examples, manifest = load_videomae_lora_export(repo_root)
        self.assertGreater(len(examples), 0)
        self.assertEqual(manifest["datasetVersion"], "videomae-lora-v1")
        self.assertTrue(any(example.video_available for example in examples))
        self.assertTrue(any(not example.video_available for example in examples))

    def test_export_logit_artifacts_writes_expected_files(self) -> None:
        label_spaces = BasketballLabelSpaces(
            event_family=("shot_attempt", "other"),
            outcome=("made", "uncertain"),
            shot_subtype=("null", "dunk"),
        )
        manifest = {
            "schemaVersion": VIDEO_LORA_SCHEMA_VERSION,
            "sourceDataset": "services/inference/datasets",
            "summary": {"tinySmoke": True},
        }
        predictions = [
            {
                "clipId": "clip-1",
                "displayLabel": "Dunk",
                "eventFamily": "shot_attempt",
                "outcome": "made",
                "shotSubtype": "dunk",
                "confidenceBeforeMapping": 0.74,
                "confidenceAfterMapping": 0.81,
                "clipDurationSeconds": 4.8,
                "isUncertain": False,
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = export_lora_logits_artifacts(
                output_dir=Path(tmpdir),
                label_spaces=label_spaces,
                manifest=manifest,
                baseline_predictions=predictions,
                rslora_predictions=predictions,
                baseline_metrics={"eventFamily": {"accuracy": 1.0}, "outcome": {"accuracy": 1.0}, "shotSubtype": {"accuracy": 1.0}},
                rslora_metrics={"eventFamily": {"accuracy": 1.0}, "outcome": {"accuracy": 1.0}, "shotSubtype": {"accuracy": 1.0}},
                baseline_training={"meanLoss": 0.1},
                rslora_training={"meanLoss": 0.05},
            )
            paths = {artifact.path.name for artifact in artifacts}
            self.assertIn("baseline_logits.jsonl", paths)
            self.assertIn("rslora_logits.jsonl", paths)
            self.assertTrue((Path(tmpdir) / "comparison_report.md").exists())
            self.assertTrue((Path(tmpdir) / "baseline_logits.jsonl").read_text().strip())


if __name__ == "__main__":
    unittest.main()
