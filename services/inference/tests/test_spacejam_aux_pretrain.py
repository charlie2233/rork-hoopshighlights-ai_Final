from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.training.spacejam_aux_pretrain import (
    DEFAULT_SPACEJAM_LABEL_MAP,
    load_spacejam_aux_pretrain_config,
    load_spacejam_clip_examples,
    render_spacejam_aux_experiment_report,
    run_spacejam_aux_pretrain_experiment,
)


class SpaceJamAuxPretrainTests(unittest.TestCase):
    def test_spacejam_adapter_maps_only_conservative_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            manifest_path = tmp / "spacejam.json"
            manifest_path.write_text(
                json.dumps(
                    [
                        {"clipId": "spacejam-shoot-001", "label": "Shoot", "clipPath": "clips/shoot.mp4"},
                        {"clipId": "spacejam-rest-001", "label": "No Action", "clipPath": "clips/rest.mp4"},
                        {"clipId": "spacejam-dunk-001", "label": "Dunk", "clipPath": "clips/dunk.mp4"},
                    ]
                ),
                encoding="utf-8",
            )

            imported = load_spacejam_clip_examples(manifest_path)

        self.assertEqual(len(imported.examples), 2)
        self.assertEqual(imported.examples[0].auxiliary_label, "shot_candidate_aux")
        self.assertEqual(imported.examples[1].auxiliary_label, "coarse_non_event_aux")
        self.assertEqual(imported.skipped_label_counts, {"Dunk": 1})

    def test_spacejam_adapter_skips_joint_rows_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            manifest_path = tmp / "spacejam.jsonl"
            manifest_path.write_text(
                "\n".join(
                    [
                        json.dumps({"id": "clip-001", "label": "Shoot", "path": "clips/001.mp4"}),
                        json.dumps({"id": "joint-001", "label": "Shoot", "path": "joints/001.npy"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            imported = load_spacejam_clip_examples(manifest_path, ignore_joints=True)

        self.assertEqual(len(imported.examples), 1)
        self.assertEqual(imported.skipped_joint_rows, 1)

    def test_config_loader_normalizes_label_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            config_path = tmp / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "spacejam-aux-pretrain-v1",
                        "featureFlag": "spacejam_aux_pretrain_v1",
                        "enabled": True,
                        "spacejam": {
                            "manifestPath": "missing.json",
                            "labelMap": {"Shoot": "shot_candidate_aux", "No Action": "coarse_non_event_aux"},
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_spacejam_aux_pretrain_config(config_path)

        self.assertEqual(config.label_map, DEFAULT_SPACEJAM_LABEL_MAP)
        self.assertTrue(config.enabled)

    def test_experiment_blocks_cleanly_when_manifest_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            config_path = tmp / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "spacejam-aux-pretrain-v1",
                        "featureFlag": "spacejam_aux_pretrain_v1",
                        "enabled": True,
                        "spacejam": {
                            "manifestPath": "missing/spacejam.json",
                            "labelMap": {"Shoot": "shot_candidate_aux", "No Action": "coarse_non_event_aux"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            baseline = {
                "proposalAcceptanceRate": 0.55,
                "familyGateOpenRate": 0.55,
                "shotHeadInvocationRate": 0.45,
                "dominantFlatLabelShare": 0.55,
                "rawEventFamilyOtherRate": 0.45,
                "uncertaintyRate": 0.64,
                "acceptedShotOutcomeAccuracy": 1.0,
                "brierScore": 0.0077,
                "eceLite": 0.0456,
                "flatLabelDistribution": {"Highlight": 6, "Made Shot": 3},
                "highlightDominance": 0.55,
                "missVsMadeConfusion": 0,
            }

            result = run_spacejam_aux_pretrain_experiment(
                Path("/Users/hanfei/rork-hoopshighlights-ai_Final"),
                config_path=config_path,
                baseline_metrics=baseline,
            )

        self.assertEqual(result.status, "blocked_missing_spacejam_manifest")
        self.assertEqual(result.recommendation, "revise")
        self.assertIsNone(result.after_metrics)
        report = render_spacejam_aux_experiment_report(result)
        self.assertIn("blocked_missing_spacejam_manifest", report)
        self.assertIn("proposalAcceptanceRate", report)


if __name__ == "__main__":
    unittest.main()
