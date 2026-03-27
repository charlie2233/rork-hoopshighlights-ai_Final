from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

import httpx

from .backends.videomae import VideoMAEActionRecognizer
from .backends.xclip import XClipActionRecognizer
from .callback import CallbackClient
from .config import InferenceSettings
from .features import extract_video_features
from .heuristics import ConfidenceReranker, HeuristicCandidateProposer, HeuristicEventInferencer
from .interfaces import ArtifactWriter
from .manifest import LocalArtifactWriter, build_manifest_dict
from .models import (
    ArtifactDescriptor,
    CallbackPayload,
    InferenceDiagnostics,
    InferenceJobRequest,
    InferenceJobResponse,
    InferenceManifest,
    InferenceStatus,
    RankedClip,
)


@dataclass(slots=True)
class InferenceService:
    settings: InferenceSettings
    candidate_proposer: HeuristicCandidateProposer
    primary_recognizer: VideoMAEActionRecognizer
    comparison_recognizer: Optional[XClipActionRecognizer]
    event_inferencer: HeuristicEventInferencer
    reranker: ConfidenceReranker
    artifact_writer: ArtifactWriter
    callback_client: CallbackClient

    async def run(self, request: InferenceJobRequest) -> InferenceJobResponse:
        request_id = request.requestId or uuid4().hex
        model_version = request.modelVersion or self._requested_model_version(request)
        try:
            with tempfile.TemporaryDirectory(prefix="hoops-inference-", dir=str(self.settings.ensure_temp_dir())) as temp_dir_str:
                temp_dir = Path(temp_dir_str)
                source_path = await self._download_source(request.sourceUrl, temp_dir / "source.mp4")
                features = await asyncio.to_thread(extract_video_features, source_path)

                candidates = self.candidate_proposer.propose(features)
                clips = []
                comparison_scores: list[float] = []

                for candidate in candidates[: self.settings.max_candidates]:
                    action = self.primary_recognizer.recognize(candidate, features)
                    comparison = None
                    if self.comparison_recognizer is not None:
                        comparison = self.comparison_recognizer.recognize(candidate, features)
                        comparison_scores.append(comparison.confidence)

                    event = self.event_inferencer.infer(candidate, action, features)
                    clip = RankedClip(
                        clipId=uuid4().hex,
                        startTime=candidate.startTime,
                        endTime=candidate.endTime,
                        confidence=min(max(action.confidence, 0.0), 1.0),
                        resultConfidence=min(max(event.rankScore, 0.0), 1.0),
                        label=action.label,
                        action=action.label,
                        eventType=event.eventType,
                        shotType=event.shotType,
                        makeMiss=event.makeMiss,
                        audioScore=self._score_from_profile(features.audio_energy_profile, candidate.startTime, candidate.endTime),
                        visualScore=self._score_from_profile(features.frame_energy_profile, candidate.startTime, candidate.endTime),
                        motionScore=self._score_from_profile(features.frame_energy_profile, candidate.startTime, candidate.endTime),
                        combinedScore=min(max(candidate.score, 0.0), 1.0),
                        rankScore=event.rankScore,
                        detectionMethod=action.detectionMethod,
                        shouldAutoKeep=event.shouldAutoKeep,
                        shouldEnableSlowMotion=event.shouldEnableSlowMotion,
                        metadata={
                            "request_id": request_id,
                            "analysis_version": request.analysisVersion,
                            "install_id": request.installId,
                            "comparison_model_version": comparison.modelVersion if comparison else None,
                            "comparison_confidence": comparison.confidence if comparison else None,
                            "candidate_reason": candidate.reason,
                            "candidate_source": candidate.source,
                            "action_failure_reason": action.failureReason,
                            "action_metadata": action.metadata,
                            "event_metadata": event.metadata,
                        },
                    )
                    clips.append(clip)

                ranked = self.reranker.rerank(clips)
                result_confidence = self._aggregate_confidence(ranked)
                summary_text = "\n".join(
                    [
                        f"job_id={request.jobId}",
                        f"request_id={request_id}",
                        f"model_version={model_version}",
                        f"clips={len(ranked)}",
                        f"result_confidence={result_confidence:.4f}",
                    ]
                ).encode("utf-8")
                summary_artifact_path = self.artifact_writer.write_artifact(
                    request.jobId,
                    "summary.txt",
                    summary_text,
                    "text/plain",
                )
                artifacts = [
                    ArtifactDescriptor(
                        kind="summary",
                        path=str(summary_artifact_path),
                        mediaType="text/plain",
                        sizeBytes=summary_artifact_path.stat().st_size,
                    ),
                    ArtifactDescriptor(
                        kind="result_manifest",
                        path=f"{request.jobId}/result-manifest.json",
                        mediaType="application/json",
                    ),
                ]
                manifest = InferenceManifest(
                    schemaVersion=self.settings.result_schema_version,
                    jobId=request.jobId,
                    requestId=request_id,
                    modelVersion=model_version,
                    resultConfidence=result_confidence,
                    failureReason=None,
                    generatedAt=datetime.now(timezone.utc),
                    clips=ranked,
                    artifacts=artifacts,
                    diagnostics=InferenceDiagnostics(
                        featureExtractor="ffprobe+opencv",
                        candidateProposer="heuristic-assisted",
                        actionRecognizer=f"videomae:{self.primary_recognizer.model_name}",
                        comparisonRecognizer=f"xclip:{self.comparison_recognizer.model_name}" if self.comparison_recognizer else None,
                        eventInferencer="heuristic-event-inferencer",
                        reranker="confidence-reranker",
                        frameCount=features.frame_count,
                        durationSeconds=features.duration_seconds,
                        fps=features.fps,
                        usedFallback=bool(any(clip.metadata.get("action_failure_reason") for clip in ranked)),
                        comparisonScore=max(comparison_scores) if comparison_scores else None,
                    ),
                )

                manifest_path = self.artifact_writer.write_manifest(build_manifest_dict(manifest), request.jobId)
                callback_payload = CallbackPayload(
                    jobId=request.jobId,
                    status=InferenceStatus.SUCCEEDED,
                    requestId=request_id,
                    modelVersion=model_version,
                    confidence=result_confidence,
                    resultConfidence=result_confidence,
                    result=manifest,
                )
                await self.callback_client.send(str(request.callbackUrl), callback_payload, request.callbackSecret, request_id=request_id)
                return InferenceJobResponse(
                    jobId=request.jobId,
                    status=InferenceStatus.SUCCEEDED.value,
                    requestId=request_id,
                    modelVersion=model_version,
                    confidence=result_confidence,
                    resultConfidence=result_confidence,
                    result=manifest,
                    message=str(manifest_path),
                )
        except Exception as exc:
            failure_reason = f"{exc.__class__.__name__.lower()}"
            failure_summary = f"{exc.__class__.__name__}: {exc}"
            failure_artifact_path = self.artifact_writer.write_artifact(
                request.jobId,
                "failure.txt",
                failure_summary.encode("utf-8"),
                "text/plain",
            )
            manifest = InferenceManifest(
                schemaVersion=self.settings.result_schema_version,
                jobId=request.jobId,
                requestId=request_id,
                modelVersion=model_version,
                resultConfidence=0.0,
                failureReason=failure_reason,
                generatedAt=datetime.now(timezone.utc),
                clips=[],
                artifacts=[
                    ArtifactDescriptor(
                        kind="failure_summary",
                        path=str(failure_artifact_path),
                        mediaType="text/plain",
                        sizeBytes=failure_artifact_path.stat().st_size,
                    )
                ],
                diagnostics=InferenceDiagnostics(
                    featureExtractor="ffprobe+opencv",
                    candidateProposer="heuristic-assisted",
                    actionRecognizer=f"videomae:{self.primary_recognizer.model_name}",
                    comparisonRecognizer=f"xclip:{self.comparison_recognizer.model_name}" if self.comparison_recognizer else None,
                    eventInferencer="heuristic-event-inferencer",
                    reranker="confidence-reranker",
                    usedFallback=True,
                ),
            )
            try:
                callback_payload = CallbackPayload(
                    jobId=request.jobId,
                    status=InferenceStatus.FAILED,
                    requestId=request_id,
                    modelVersion=model_version,
                    failureReason=failure_reason,
                    confidence=0.0,
                    resultConfidence=0.0,
                    result=manifest,
                )
                await self.callback_client.send(str(request.callbackUrl), callback_payload, request.callbackSecret, request_id=request_id)
            except Exception:
                pass
            return InferenceJobResponse(
                jobId=request.jobId,
                status=InferenceStatus.FAILED.value,
                requestId=request_id,
                modelVersion=model_version,
                failureReason=failure_reason,
                confidence=0.0,
                resultConfidence=0.0,
                result=manifest,
                message=failure_summary,
            )

    async def _download_source(self, source_url: str, destination: Path) -> Path:
        async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds, follow_redirects=True) as client:
            response = await client.get(str(source_url))
            response.raise_for_status()
            destination.write_bytes(response.content)
        return destination

    def _requested_model_version(self, request: InferenceJobRequest) -> str:
        requested = (request.requestedModel or self.settings.default_model).lower()
        if requested == "xclip":
            return f"xclip:{self.comparison_recognizer.model_name if self.comparison_recognizer else self.settings.model_name_xclip}"
        return f"videomae:{self.primary_recognizer.model_name}"

    def _aggregate_confidence(self, clips: list[RankedClip]) -> float:
        if not clips:
            return 0.0
        total = sum(clip.resultConfidence for clip in clips)
        return min(max(total / len(clips), 0.0), 1.0)

    def _score_from_profile(self, profile: list[float], start: float, end: float) -> float:
        if not profile:
            return 0.0
        window_mean = sum(profile) / len(profile)
        return min(max(window_mean, 0.0), 1.0)


def build_service(settings: InferenceSettings) -> InferenceService:
    comparison = None
    if settings.comparison_model.lower() == "xclip":
        comparison = XClipActionRecognizer(model_name=settings.model_name_xclip)
    return InferenceService(
        settings=settings,
        candidate_proposer=HeuristicCandidateProposer(
            window_seconds=settings.heuristic_window_seconds,
            stride_seconds=settings.heuristic_stride_seconds,
        ),
        primary_recognizer=VideoMAEActionRecognizer(model_name=settings.model_name_videomae),
        comparison_recognizer=comparison,
        event_inferencer=HeuristicEventInferencer(),
        reranker=ConfidenceReranker(),
        artifact_writer=LocalArtifactWriter(settings.ensure_temp_dir()),
        callback_client=CallbackClient(timeout_seconds=settings.callback_timeout_seconds),
    )
