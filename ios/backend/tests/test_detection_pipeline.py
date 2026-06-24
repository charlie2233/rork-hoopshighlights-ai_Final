from __future__ import annotations

from pathlib import Path
import sys
import unittest

from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "ios" / "backend"))

from app.detection_pipeline import run_staged_detection_pipeline  # noqa: E402
from app.model_registry import ModelRegistry, disabled_embedding_adapter, openclip_embedding_adapter, siglip_embedding_adapter  # noqa: E402
from app.models import CandidateWindow, CloudClip  # noqa: E402
from app.taxonomy import load_default_taxonomy  # noqa: E402


def _window(start: float, combined: float, *, event_context: float = 0.7, audio_pop: float = 0.2) -> CandidateWindow:
    return CandidateWindow(
        start_time=start,
        end_time=start + 5.0,
        peak_time=start + 2.2,
        audio_score=0.62,
        visual_score=0.66,
        motion_score=0.72,
        combined_score=combined,
        event_context_score=event_context,
        audio_pop_score=audio_pop,
        audio_pop_time=start + 2.4,
        audio_cue_type="cluster",
        audio_cue_confidence=0.7,
    )


class DetectionPipelineTests(unittest.TestCase):
    def test_schema_rejects_unknown_clip_fields(self) -> None:
        with self.assertRaises(ValidationError):
            CloudClip.model_validate(
                {
                    "startTime": 0.0,
                    "endTime": 4.0,
                    "confidence": 0.9,
                    "label": "Dunk",
                    "action": "Dunk",
                    "audioScore": 0.4,
                    "visualScore": 0.7,
                    "motionScore": 0.8,
                    "combinedScore": 0.82,
                    "detectionMethod": "cloud",
                    "shouldAutoKeep": True,
                    "shouldEnableSlowMotion": True,
                    "unexpected": "forbidden",
                }
            )

    def test_pipeline_outputs_multiple_candidates_with_provenance(self) -> None:
        result = run_staged_detection_pipeline(
            [_window(0.0, 0.91), _window(8.0, 0.76, audio_pop=0.74)],
            registry=ModelRegistry(embedding=openclip_embedding_adapter()),
            clip_limit=8,
            source_identity={"jobId": "job_test", "assetId": "asset_test", "uploadTraceId": "upload_test"},
        )

        self.assertEqual(len(result.clips), 2)
        self.assertEqual(result.summary.pipelineVersion, "detection-pipeline-v2")
        self.assertEqual(result.summary.proposalCount, 2)
        self.assertEqual(result.summary.rerankedCount, 2)
        self.assertEqual(result.summary.models["classifier"], "r2plus1d-baseline-v1")
        first = result.clips[0]
        self.assertEqual(first.pipelineStage, "merged_candidate")
        self.assertIsNotNone(first.provenance)
        self.assertEqual(first.provenance.proposal.stage, "proposal")
        self.assertEqual(first.provenance.embeddingRerank.adapter, "openclip")
        self.assertIsNotNone(first.scores)
        self.assertGreater(first.scores.finalScore, 0.0)
        self.assertTrue(first.canonicalLabel)
        self.assertTrue(first.id.startswith("clip_"))
        self.assertEqual(first.clipId, first.id)
        self.assertIsNotNone(first.rerankEvidence)
        self.assertEqual(first.rerankEvidence.sourceIdentity["jobId"], "job_test")
        self.assertEqual(first.rerankEvidence.sourceIdentity["assetId"], "asset_test")
        self.assertGreaterEqual(first.rerankEvidence.embeddingScore, 0.0)
        self.assertGreaterEqual(len(first.rerankEvidence.textMatches), 1)

    def test_label_mapping_uses_product_taxonomy(self) -> None:
        taxonomy = load_default_taxonomy()
        mapping = taxonomy.map_label("3pt", 0.82)
        self.assertEqual(mapping.product_label, "Three Pointer")
        self.assertEqual(mapping.canonical_label, "three_pointer")
        self.assertEqual(mapping.event_family, "shot")

    def test_embedding_fallback_is_explicit(self) -> None:
        result = run_staged_detection_pipeline(
            [_window(0.0, 0.7)],
            registry=ModelRegistry(embedding=disabled_embedding_adapter()),
            clip_limit=4,
        )

        self.assertTrue(result.summary.fallbackUsed)
        self.assertIn("embedding_adapter_unavailable", result.summary.fallbackReasons)
        self.assertEqual(result.clips[0].provenance.embeddingRerank.status, "fallback")
        self.assertTrue(result.clips[0].rerankEvidence.killSwitch)
        self.assertEqual(result.clips[0].rerankEvidence.fallbackReason, "embedding_adapter_unavailable")

    def test_siglip_adapter_interface_is_supported(self) -> None:
        result = run_staged_detection_pipeline(
            [_window(0.0, 0.72)],
            registry=ModelRegistry(embedding=siglip_embedding_adapter()),
            clip_limit=4,
        )

        self.assertEqual(result.clips[0].provenance.embeddingRerank.adapter, "siglip")


if __name__ == "__main__":
    unittest.main()
