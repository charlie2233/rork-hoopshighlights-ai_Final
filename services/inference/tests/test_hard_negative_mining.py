from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.datasets.hard_negative_mining import (
    build_hard_negative_queue,
    build_hard_negative_report,
    load_live_payloads,
    normalize_payload,
    render_markdown,
    write_artifacts,
)
from services.inference.scripts.build_hard_negative_queue import main as build_cli_main


class HardNegativeMiningTests(unittest.TestCase):
    @staticmethod
    def repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def test_builds_queue_from_live_payloads_and_scores_low_margin(self) -> None:
        payload = {
            "jobId": "job-live-001",
            "requestId": "req-live-001",
            "uploadTraceId": "upload-live-001",
            "inferenceAttemptId": "attempt-live-001",
            "modelVersion": "runtime:v1",
            "clips": [
                {
                    "clipId": "clip-highlight-001",
                    "finalLabel": "Highlight",
                    "eventFamily": "other",
                    "outcome": "uncertain",
                    "clipDurationSeconds": 6.0,
                    "wasMerged": True,
                    "sourceEventCount": 3,
                    "confidence": 0.41,
                    "confidenceBeforeMapping": 0.38,
                    "confidenceAfterMapping": 0.41,
                    "resultConfidence": 0.41,
                    "rawTopLabels": [
                        {"label": "highlight", "confidence": 0.41},
                        {"label": "uncertain", "confidence": 0.37},
                    ],
                    "comparisonRawTopLabels": [
                        {"label": "transition", "confidence": 0.39},
                        {"label": "highlight", "confidence": 0.31},
                    ],
                },
                {
                    "clipId": "clip-shot-low-margin-001",
                    "finalLabel": "Made Shot",
                    "eventFamily": "shot_attempt",
                    "outcome": "made",
                    "clipDurationSeconds": 5.5,
                    "wasMerged": False,
                    "sourceEventCount": 1,
                    "confidence": 0.72,
                    "confidenceBeforeMapping": 0.67,
                    "confidenceAfterMapping": 0.72,
                    "resultConfidence": 0.72,
                    "rawTopLabels": [
                        {"label": "made", "confidence": 0.45},
                        {"label": "missed", "confidence": 0.39},
                        {"label": "layup", "confidence": 0.2},
                    ],
                },
                {
                    "clipId": "clip-fastbreak-001",
                    "finalLabel": "Fast Break",
                    "eventFamily": "transition",
                    "outcome": "uncertain",
                    "clipDurationSeconds": 4.25,
                    "wasMerged": False,
                    "sourceEventCount": 1,
                    "confidence": 0.88,
                    "confidenceBeforeMapping": 0.82,
                    "confidenceAfterMapping": 0.88,
                    "resultConfidence": 0.88,
                    "rawTopLabels": [
                        {"label": "transition", "confidence": 0.71},
                        {"label": "steal", "confidence": 0.23},
                    ],
                },
            ],
        }

        clips = normalize_payload(payload)
        queue = build_hard_negative_queue(clips)

        self.assertEqual([item.clip_id for item in queue], [
            "clip-highlight-001",
            "clip-shot-low-margin-001",
        ])
        self.assertIn("final_label_highlight", queue[0].priority_reasons)
        self.assertIn("event_family_other", queue[0].priority_reasons)
        self.assertIn("merged_multi_event", queue[0].priority_reasons)
        self.assertIn("low_margin", queue[1].priority_reasons)
        self.assertGreater(queue[0].sample_weight, queue[1].sample_weight)
        self.assertEqual(queue[0].review_bucket, "cross_model_disagreement")
        self.assertEqual(queue[1].review_bucket, "low_margin")

    def test_report_and_markdown_include_training_ready_weights(self) -> None:
        payload = {
            "jobId": "job-live-002",
            "requestId": "req-live-002",
            "uploadTraceId": "upload-live-002",
            "inferenceAttemptId": "attempt-live-002",
            "modelVersion": "runtime:v1",
            "clips": [
                {
                    "clipId": "clip-other-001",
                    "finalLabel": "Highlight",
                    "eventFamily": "other",
                    "outcome": "uncertain",
                    "clipDurationSeconds": 6.0,
                    "confidence": 0.43,
                    "rawTopLabels": [
                        {"label": "highlight", "confidence": 0.43},
                        {"label": "turnover", "confidence": 0.28},
                    ],
                }
            ],
        }

        report = build_hard_negative_report(normalize_payload(payload))
        markdown = render_markdown(report)

        self.assertEqual(report.summary["queuedClips"], 1)
        self.assertEqual(report.summary["queueVersion"], "hard-negative-v1")
        self.assertIn("training-ready", markdown.lower())
        self.assertIn("clip-other-001", markdown)
        self.assertGreater(report.queue[0].training_weight, 1.0)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            queue_path, training_path, md_path = write_artifacts(output_dir, report)
            self.assertTrue(queue_path.exists())
            self.assertTrue(training_path.exists())
            self.assertTrue(md_path.exists())
            payload = json.loads((output_dir / "hard_negative_queue_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["queuedClips"], 1)

    def test_loads_shadow_fixture_and_falls_back_to_thin_job_summaries(self) -> None:
        shadow_fixture = self.repo_root() / "services" / "inference" / "tests" / "fixtures" / "shadow_batch_results.json"
        live_summary = {
            "jobId": "job-thin-001",
            "requestId": "req-thin-001",
            "uploadTraceId": "upload-thin-001",
            "inferenceAttemptId": "attempt-thin-001",
            "modelVersion": "runtime:v1",
            "clips": [
                {"clipId": "clip-thin-001", "finalLabel": "Highlight", "clipDurationSeconds": 4.5, "wasMerged": False, "sourceEventCount": 1},
                {"clipId": "clip-thin-002", "finalLabel": "Fast Break", "clipDurationSeconds": 4.0, "wasMerged": False, "sourceEventCount": 1},
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            thin_path = temp / "thin.json"
            thin_path.write_text(json.dumps(live_summary, indent=2), encoding="utf-8")
            records = load_live_payloads([shadow_fixture, thin_path])

        self.assertGreaterEqual(len(records), 6)
        self.assertTrue(any(item.final_label == "Highlight" for item in records))
        self.assertTrue(any(item.margin is not None for item in records))

    def test_cli_writes_queue_artifacts(self) -> None:
        payload = {
            "jobId": "job-cli-001",
            "requestId": "req-cli-001",
            "uploadTraceId": "upload-cli-001",
            "inferenceAttemptId": "attempt-cli-001",
            "modelVersion": "runtime:v1",
            "clips": [
                {
                    "clipId": "clip-cli-001",
                    "finalLabel": "Highlight",
                    "eventFamily": "other",
                    "outcome": "uncertain",
                    "clipDurationSeconds": 5.0,
                    "confidence": 0.44,
                    "rawTopLabels": [
                        {"label": "highlight", "confidence": 0.44},
                        {"label": "uncertain", "confidence": 0.33},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            input_path = temp / "input.json"
            input_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            import sys

            argv = sys.argv
            try:
                sys.argv = [
                    "build_hard_negative_queue.py",
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(temp / "out"),
                    "--top-k",
                    "5",
                ]
                self.assertEqual(build_cli_main(), 0)
            finally:
                sys.argv = argv

            out_dir = temp / "out"
            self.assertTrue((out_dir / "hard_negative_queue.jsonl").exists())
            self.assertTrue((out_dir / "hard_negative_training.jsonl").exists())
            self.assertTrue((out_dir / "hard_negative_queue.md").exists())
            queue_rows = [json.loads(line) for line in (out_dir / "hard_negative_queue.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(queue_rows), 1)
            self.assertGreater(queue_rows[0]["sample_weight"], 1.0)


if __name__ == "__main__":
    unittest.main()
