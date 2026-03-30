from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from services.inference.app.callback import CallbackClient
from services.inference.app.config import InferenceSettings
from datetime import datetime, timezone

from services.inference.app.models import (
    InferenceDiagnostics,
    InferenceJobRequest,
    InferenceManifest,
    LabelScore,
    RankedClip,
    RawLabelScore,
)
from services.inference.app.pipeline import InferenceService, _resolve_trace_fields
from services.inference.app.runtime_model import RuntimeFusionPrediction


class PipelineSourceResolutionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.settings = InferenceSettings()
        self.service = InferenceService(
            settings=self.settings,
            candidate_proposer=Mock(),
            primary_recognizer=Mock(),
            adapted_primary_recognizer=None,
            comparison_recognizer=None,
            event_inferencer=Mock(),
            reranker=Mock(),
            artifact_writer=Mock(),
            callback_client=CallbackClient(timeout_seconds=1.0),
            r2_downloader=None,
        )

    async def test_resolve_source_falls_back_to_source_url_when_r2_is_not_configured(self) -> None:
        request = InferenceJobRequest(
            jobId="job_123",
            sourceObjectKey="uploads/job_123/source.mp4",
            sourceUrl="https://example.com/source.mp4",
            callbackUrl="https://example.com/internal/inference/callback",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "source.mp4"
            self.service._download_source = AsyncMock(return_value=destination)

            resolved = await self.service._resolve_source(request, destination)

            self.assertEqual(resolved, destination)
            self.service._download_source.assert_awaited_once_with("https://example.com/source.mp4", destination)

    async def test_resolve_source_uses_r2_downloader_when_available(self) -> None:
        request = InferenceJobRequest(
            jobId="job_123",
            sourceObjectKey="uploads/job_123/source.mp4",
            sourceUrl="https://example.com/source.mp4",
            callbackUrl="https://example.com/internal/inference/callback",
        )
        downloader = Mock()
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "source.mp4"
            downloader.download.return_value = destination
            self.service.r2_downloader = downloader
            self.service._download_source = AsyncMock(return_value=destination)

            resolved = await self.service._resolve_source(request, destination)

            self.assertEqual(resolved, destination)
            downloader.download.assert_called_once_with("uploads/job_123/source.mp4", destination)
            self.service._download_source.assert_not_awaited()


class PipelineTraceResolutionTests(unittest.TestCase):
    def test_resolve_trace_fields_prefers_distinct_upload_trace_id(self) -> None:
        request = InferenceJobRequest(
            jobId="job_123",
            traceId="trace-123",
            uploadTraceId="upload-456",
            sourceUrl="https://example.com/source.mp4",
            callbackUrl="https://example.com/internal/inference/callback",
        )

        trace_id, upload_trace_id = _resolve_trace_fields(request, "request-789")

        self.assertEqual(trace_id, "trace-123")
        self.assertEqual(upload_trace_id, "upload-456")

    def test_resolve_trace_fields_falls_back_to_trace_id_then_request_id(self) -> None:
        request_with_trace = InferenceJobRequest(
            jobId="job_123",
            traceId="trace-123",
            sourceUrl="https://example.com/source.mp4",
            callbackUrl="https://example.com/internal/inference/callback",
        )
        self.assertEqual(_resolve_trace_fields(request_with_trace, "request-789"), ("trace-123", "trace-123"))

        request_without_trace = InferenceJobRequest(
            jobId="job_123",
            sourceUrl="https://example.com/source.mp4",
            callbackUrl="https://example.com/internal/inference/callback",
        )
        self.assertEqual(_resolve_trace_fields(request_without_trace, "request-789"), ("request-789", "request-789"))


class PipelineCallbackResultsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = InferenceService(
            settings=InferenceSettings(),
            candidate_proposer=Mock(),
            primary_recognizer=Mock(),
            adapted_primary_recognizer=None,
            comparison_recognizer=None,
            event_inferencer=Mock(),
            reranker=Mock(),
            artifact_writer=Mock(),
            callback_client=CallbackClient(timeout_seconds=1.0),
            r2_downloader=None,
        )

    def test_build_callback_results_preserves_windowing_metadata(self) -> None:
        manifest = InferenceManifest(
            schemaVersion="2026-03-27",
            jobId="job_123",
            requestId="request-123",
            uploadTraceId="upload-123",
            inferenceAttemptId="attempt-123",
            modelVersion="videomae:test",
            resultConfidence=0.83,
            failureReason=None,
            generatedAt=datetime.now(timezone.utc),
            clips=[
                RankedClip(
                    clipId="clip-1",
                    startTime=1.0,
                    endTime=6.2,
                    clipDurationSeconds=5.2,
                    eventCenterSeconds=3.7,
                    preRollSeconds=2.2,
                    postRollSeconds=3.0,
                    windowPolicyVersion="basketball-v1",
                    wasMerged=True,
                    sourceEventCount=2,
                    confidence=0.83,
                    resultConfidence=0.83,
                    label="Made Shot",
                    action="Made Shot",
                    canonicalLabel="jumper",
                    eventFamily="shot",
                    eventSubtype=None,
                    shotSubtype="jumper",
                    outcome="made",
                    eventType="perimeter_shot",
                    shotType="jumper",
                    makeMiss="made",
                    confidenceBeforeMapping=0.91,
                    confidenceAfterMapping=0.83,
                    isUncertain=False,
                    audioScore=0.2,
                    visualScore=0.4,
                    motionScore=0.5,
                    combinedScore=0.6,
                    rankScore=0.83,
                    detectionMethod="model",
                    topLabels=[LabelScore(label="jumper", confidence=0.83, rawLabel="jump shot", modelVersion="videomae:test")],
                    comparisonTopLabels=[LabelScore(label="miss", confidence=0.41, rawLabel="missed shot", modelVersion="xclip:test")],
                    rawTopLabels=[RawLabelScore(rawLabel="jump shot", canonicalLabel="jumper", confidence=0.91, modelVersion="videomae:test")],
                    comparisonRawTopLabels=[RawLabelScore(rawLabel="a missed basketball shot", canonicalLabel="miss", confidence=0.41, modelVersion="xclip:test")],
                )
            ],
            artifacts=[],
            diagnostics=InferenceDiagnostics(
                featureExtractor="ffprobe+opencv",
                candidateProposer="heuristic-assisted",
                actionRecognizer="videomae:test",
                eventInferencer="heuristic-event-inferencer",
                reranker="confidence-reranker",
            ),
        )

        callback_results = self.service._build_callback_results(manifest)
        clip = callback_results["clips"][0]

        self.assertEqual(clip["clipDurationSeconds"], 5.2)
        self.assertEqual(clip["eventCenterSeconds"], 3.7)
        self.assertEqual(clip["preRollSeconds"], 2.2)
        self.assertEqual(clip["postRollSeconds"], 3.0)
        self.assertEqual(clip["windowPolicyVersion"], "basketball-v1")
        self.assertTrue(clip["wasMerged"])
        self.assertEqual(clip["sourceEventCount"], 2)
        self.assertEqual(clip["eventFamily"], "shot")
        self.assertEqual(clip["shotSubtype"], "jumper")
        self.assertEqual(clip["outcome"], "made")
        self.assertEqual(clip["confidenceBeforeMapping"], 0.91)
        self.assertEqual(clip["confidenceAfterMapping"], 0.83)
        self.assertEqual(clip["rawTopLabels"][0]["rawLabel"], "jump shot")
        self.assertEqual(clip["comparisonRawTopLabels"][0]["canonicalLabel"], "miss")

    def test_build_callback_results_surfaces_nested_runtime_shadow_metadata(self) -> None:
        manifest = InferenceManifest(
            schemaVersion="2026-03-27",
            jobId="job_123",
            requestId="request-123",
            uploadTraceId="upload-123",
            inferenceAttemptId="attempt-123",
            modelVersion="videomae:test",
            resultConfidence=0.46,
            failureReason=None,
            generatedAt=datetime.now(timezone.utc),
            clips=[
                RankedClip(
                    clipId="clip-1",
                    startTime=0.0,
                    endTime=4.75,
                    clipDurationSeconds=4.75,
                    eventCenterSeconds=2.25,
                    preRollSeconds=2.25,
                    postRollSeconds=2.5,
                    windowPolicyVersion="basketball-v1",
                    wasMerged=False,
                    sourceEventCount=1,
                    confidence=0.46,
                    resultConfidence=0.46,
                    label="Highlight",
                    action="Highlight",
                    canonicalLabel="jumper",
                    eventFamily="shot_attempt",
                    eventSubtype="jumper",
                    shotSubtype="jumper",
                    outcome="uncertain",
                    eventType="shot_attempt",
                    shotType="jumper",
                    makeMiss="unknown",
                    confidenceBeforeMapping=0.61,
                    confidenceAfterMapping=0.46,
                    isUncertain=True,
                    audioScore=0.2,
                    visualScore=0.4,
                    motionScore=0.5,
                    combinedScore=0.6,
                    rankScore=0.46,
                    detectionMethod="model",
                    topLabels=[],
                    comparisonTopLabels=[],
                    rawTopLabels=[],
                    comparisonRawTopLabels=[],
                    metadata={
                        "action_metadata": {
                            "runtimeFusionShadow": {
                                "runtime_fusion_model_version": "runtime-fusion-v1",
                                "label": "Highlight",
                            }
                        }
                    },
                )
            ],
            artifacts=[],
            diagnostics=InferenceDiagnostics(
                featureExtractor="ffprobe+opencv",
                candidateProposer="heuristic-assisted",
                actionRecognizer="videomae:test",
                eventInferencer="heuristic-event-inferencer",
                reranker="confidence-reranker",
            ),
        )

        callback_results = self.service._build_callback_results(manifest)
        clip = callback_results["clips"][0]

        self.assertEqual(
            clip["runtimeFusionShadow"]["runtime_fusion_model_version"],
            "runtime-fusion-v1",
        )

    def test_build_callback_results_surfaces_lora_shadow_metadata(self) -> None:
        manifest = InferenceManifest(
            schemaVersion="2026-03-27",
            jobId="job_123",
            requestId="request-123",
            uploadTraceId="upload-123",
            inferenceAttemptId="attempt-123",
            modelVersion="videomae:test",
            resultConfidence=0.46,
            failureReason=None,
            generatedAt=datetime.now(timezone.utc),
            clips=[
                RankedClip(
                    clipId="clip-1",
                    startTime=0.0,
                    endTime=4.75,
                    clipDurationSeconds=4.75,
                    eventCenterSeconds=2.25,
                    preRollSeconds=2.25,
                    postRollSeconds=2.5,
                    windowPolicyVersion="basketball-v1",
                    wasMerged=False,
                    sourceEventCount=1,
                    confidence=0.46,
                    resultConfidence=0.46,
                    label="Highlight",
                    action="Highlight",
                    canonicalLabel="jumper",
                    eventFamily="shot_attempt",
                    eventSubtype="jumper",
                    shotSubtype="jumper",
                    outcome="uncertain",
                    eventType="shot_attempt",
                    shotType="jumper",
                    makeMiss="unknown",
                    confidenceBeforeMapping=0.61,
                    confidenceAfterMapping=0.46,
                    isUncertain=True,
                    audioScore=0.2,
                    visualScore=0.4,
                    motionScore=0.5,
                    combinedScore=0.6,
                    rankScore=0.46,
                    detectionMethod="model",
                    topLabels=[],
                    comparisonTopLabels=[],
                    rawTopLabels=[],
                    comparisonRawTopLabels=[],
                    metadata={
                        "action_metadata": {
                            "runtimeFusionLoRAShadow": {
                                "runtime_fusion_model_version": "videomae-rslora:test",
                                "label": "Dunk",
                            }
                        }
                    },
                )
            ],
            artifacts=[],
            diagnostics=InferenceDiagnostics(
                featureExtractor="ffprobe+opencv",
                candidateProposer="heuristic-assisted",
                actionRecognizer="videomae:test",
                eventInferencer="heuristic-event-inferencer",
                reranker="confidence-reranker",
            ),
        )

        callback_results = self.service._build_callback_results(manifest)
        clip = callback_results["clips"][0]

        self.assertEqual(
            clip["runtimeFusionLoRAShadow"]["runtime_fusion_model_version"],
            "videomae-rslora:test",
        )


class PipelineRuntimeModelModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = InferenceSettings(runtime_model_mode="shadow")
        self.service = InferenceService(
            settings=self.settings,
            candidate_proposer=Mock(),
            primary_recognizer=Mock(),
            adapted_primary_recognizer=None,
            comparison_recognizer=None,
            event_inferencer=Mock(),
            reranker=Mock(),
            artifact_writer=Mock(),
            callback_client=CallbackClient(timeout_seconds=1.0),
            r2_downloader=None,
        )

    def test_shadow_mode_preserves_structured_label_and_adds_shadow_metadata(self) -> None:
        action = _make_action_stub()
        prediction = RuntimeFusionPrediction(
            model_version="runtime-fusion-v1",
            event_family="turnover",
            outcome="uncertain",
            shot_subtype=None,
            canonical_label="steal",
            display_label="Steal",
            confidence_before_mapping=0.62,
            confidence_after_mapping=0.62,
            event_family_confidence_before_mapping=0.62,
            event_family_confidence_after_mapping=0.62,
            shot_subtype_confidence_before_mapping=None,
            shot_subtype_confidence_after_mapping=None,
            outcome_confidence_before_mapping=0.44,
            outcome_confidence_after_mapping=0.44,
            is_uncertain=True,
            metadata={"runtime_fusion_model_version": "runtime-fusion-v1"},
        )

        resolved = self.service._resolve_runtime_action(
            structured_action=action,
            runtime_prediction=prediction,
            structured_signals={"ballNearRim": 0.12},
            perception={},
        )

        self.assertEqual(resolved.label, "Highlight")
        self.assertIn("runtimeFusionShadow", resolved.metadata)
        self.assertEqual(
            resolved.metadata["runtimeFusionShadow"]["runtime_fusion_model_version"],
            "runtime-fusion-v1",
        )

    def test_primary_mode_promotes_runtime_prediction(self) -> None:
        service = InferenceService(
            settings=InferenceSettings(runtime_model_mode="primary"),
            candidate_proposer=Mock(),
            primary_recognizer=Mock(),
            adapted_primary_recognizer=None,
            comparison_recognizer=None,
            event_inferencer=Mock(),
            reranker=Mock(),
            artifact_writer=Mock(),
            callback_client=CallbackClient(timeout_seconds=1.0),
            r2_downloader=None,
        )
        action = _make_action_stub()
        prediction = RuntimeFusionPrediction(
            model_version="runtime-fusion-v1",
            event_family="shot_attempt",
            outcome="missed",
            shot_subtype="jumper",
            canonical_label="miss",
            display_label="Highlight",
            confidence_before_mapping=0.58,
            confidence_after_mapping=0.46,
            event_family_confidence_before_mapping=0.71,
            event_family_confidence_after_mapping=0.71,
            shot_subtype_confidence_before_mapping=0.49,
            shot_subtype_confidence_after_mapping=0.49,
            outcome_confidence_before_mapping=0.77,
            outcome_confidence_after_mapping=0.77,
            is_uncertain=False,
            metadata={"runtime_fusion_model_version": "runtime-fusion-v1"},
        )

        resolved = service._resolve_runtime_action(
            structured_action=action,
            runtime_prediction=prediction,
            structured_signals={"ballNearRim": 0.67},
            perception={},
        )

        self.assertEqual(resolved.label, "Highlight")
        self.assertEqual(resolved.canonicalLabel, "miss")
        self.assertEqual(resolved.eventFamily, "shot_attempt")
        self.assertEqual(resolved.outcome, "missed")
        self.assertEqual(
            resolved.metadata["runtimeFusionPrimary"]["runtime_fusion_model_version"],
            "runtime-fusion-v1",
        )


def _make_action_stub():
    def model_copy(*, update):
        data = {
            "metadata": {"resolved_by": "structured_basketball_signals"},
            "label": "Highlight",
            "canonicalLabel": "miss",
            "eventFamily": "shot_attempt",
            "eventSubtype": None,
            "shotSubtype": "jumper",
            "outcome": "missed",
            "confidenceBeforeMapping": 0.58,
            "confidenceAfterMapping": 0.46,
            "eventFamilyConfidenceBeforeMapping": 0.61,
            "eventFamilyConfidenceAfterMapping": 0.61,
            "shotSubtypeConfidenceBeforeMapping": 0.49,
            "shotSubtypeConfidenceAfterMapping": 0.49,
            "outcomeConfidenceBeforeMapping": 0.77,
            "outcomeConfidenceAfterMapping": 0.77,
            "isUncertain": False,
        }
        data.update(update)
        return SimpleNamespace(**data)

    return SimpleNamespace(
        metadata={"resolved_by": "structured_basketball_signals"},
        label="Highlight",
        canonicalLabel="miss",
        eventFamily="shot_attempt",
        eventSubtype=None,
        shotSubtype="jumper",
        outcome="missed",
        confidenceBeforeMapping=0.58,
        confidenceAfterMapping=0.46,
        eventFamilyConfidenceBeforeMapping=0.61,
        eventFamilyConfidenceAfterMapping=0.61,
        shotSubtypeConfidenceBeforeMapping=0.49,
        shotSubtypeConfidenceAfterMapping=0.49,
        outcomeConfidenceBeforeMapping=0.77,
        outcomeConfidenceAfterMapping=0.77,
        isUncertain=False,
        model_copy=model_copy,
    )


if __name__ == "__main__":
    unittest.main()
