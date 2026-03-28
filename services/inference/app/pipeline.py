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
from .ffmpeg_tools import prepare_media_source
from .features import extract_video_features
from .labels import aggregate_label_scores
from .heuristics import ConfidenceReranker, HeuristicCandidateProposer, HeuristicEventInferencer
from .interfaces import ArtifactWriter
from .manifest import LocalArtifactWriter, build_manifest_dict
from .windowing import WindowedClipDraft, window_and_merge_clips
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
from .storage import R2Downloader


@dataclass
class InferenceService:
    settings: InferenceSettings
    candidate_proposer: HeuristicCandidateProposer
    primary_recognizer: VideoMAEActionRecognizer
    comparison_recognizer: Optional[XClipActionRecognizer]
    event_inferencer: HeuristicEventInferencer
    reranker: ConfidenceReranker
    artifact_writer: ArtifactWriter
    callback_client: CallbackClient
    r2_downloader: Optional[R2Downloader] = None

    async def run(self, request: InferenceJobRequest) -> InferenceJobResponse:
        request_id = request.requestId or uuid4().hex
        upload_trace_id = request.traceId or request.uploadTraceId or request_id
        inference_attempt_id = request.inferenceAttemptId or uuid4().hex
        model_version = request.modelVersion or self._requested_model_version(request)
        trace_id = upload_trace_id
        callback_secret = request.callbackSecret or self.settings.callback_secret
        try:
            with tempfile.TemporaryDirectory(prefix="hoops-inference-", dir=str(self.settings.ensure_temp_dir())) as temp_dir_str:
                temp_dir = Path(temp_dir_str)
                source_path = await self._resolve_source(request, temp_dir / "source.mp4")
                preparation = await asyncio.to_thread(
                    prepare_media_source,
                    source_path,
                    temp_dir / "ffmpeg",
                    enable_transcode=self.settings.ffmpeg_enable_transcode,
                    max_width=self.settings.ffmpeg_max_width,
                    video_preset=self.settings.ffmpeg_video_preset,
                    video_crf=self.settings.ffmpeg_video_crf,
                )
                features = await asyncio.to_thread(extract_video_features, preparation.prepared_path)

                candidates = self.candidate_proposer.propose(features)
                clip_drafts: list[WindowedClipDraft] = []
                comparison_scores: list[float] = []

                for candidate in candidates[: self.settings.max_candidates]:
                    primary_action = self.primary_recognizer.recognize(candidate, features)
                    comparison = None
                    if self.comparison_recognizer is not None:
                        comparison = self.comparison_recognizer.recognize(candidate, features)
                        comparison_scores.append(comparison.confidence)

                    action = self._resolve_action(primary_action, comparison)
                    event = self.event_inferencer.infer(candidate, action, features)
                    clip_drafts.append(
                        WindowedClipDraft(
                            clipId=uuid4().hex,
                            sourceStartSeconds=candidate.startTime,
                            sourceEndSeconds=candidate.endTime,
                            label=action.label,
                            action=action.label,
                            canonicalLabel=action.canonicalLabel,
                            eventType=event.eventType,
                            shotType=event.shotType,
                            makeMiss=event.makeMiss,
                            confidence=min(max(action.confidence, 0.0), 1.0),
                            resultConfidence=min(max(event.rankScore, 0.0), 1.0),
                            audioScore=self._score_from_profile(
                                features.audio_energy_profile, candidate.startTime, candidate.endTime
                            ),
                            visualScore=self._score_from_profile(
                                features.frame_energy_profile, candidate.startTime, candidate.endTime
                            ),
                            motionScore=self._score_from_profile(
                                features.frame_energy_profile, candidate.startTime, candidate.endTime
                            ),
                            combinedScore=min(max(candidate.score, 0.0), 1.0),
                            rankScore=event.rankScore,
                            detectionMethod=action.detectionMethod,
                            shouldAutoKeep=event.shouldAutoKeep,
                            shouldEnableSlowMotion=event.shouldEnableSlowMotion,
                            topLabels=action.topLabels,
                            comparisonTopLabels=comparison.topLabels if comparison else [],
                            metadata={
                                "request_id": request_id,
                                "upload_trace_id": upload_trace_id,
                                "inference_attempt_id": inference_attempt_id,
                                "analysis_version": request.analysisVersion,
                                "install_id": request.installId,
                                "source_object_key": request.sourceObjectKey,
                                "comparison_model_version": comparison.modelVersion if comparison else None,
                                "comparison_confidence": comparison.confidence if comparison else None,
                                "comparison_label": comparison.label if comparison else None,
                                "comparison_canonical_label": comparison.canonicalLabel if comparison else None,
                                "candidate_reason": candidate.reason,
                                "candidate_source": candidate.source,
                                "action_failure_reason": action.failureReason,
                                "action_metadata": action.metadata,
                                "event_metadata": event.metadata,
                                "source_object_key": request.sourceObjectKey,
                                "prepared_with_ffmpeg": preparation.used_transcode,
                                "ffmpeg_available": preparation.ffmpeg_available,
                            },
                        )
                    )

                ranked = self.reranker.rerank(
                    window_and_merge_clips(
                        clip_drafts,
                        source_duration_seconds=features.duration_seconds,
                    )
                )
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
                    uploadTraceId=upload_trace_id,
                    inferenceAttemptId=inference_attempt_id,
                    modelVersion=model_version,
                    resultConfidence=result_confidence,
                    failureReason=None,
                    generatedAt=datetime.now(timezone.utc),
                    clips=ranked,
                    artifacts=artifacts,
                    diagnostics=InferenceDiagnostics(
                        featureExtractor="ffprobe+opencv+ffmpeg" if preparation.used_transcode else "ffprobe+opencv",
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
                    uploadTraceId=upload_trace_id,
                    inferenceAttemptId=inference_attempt_id,
                    modelVersion=model_version,
                    schemaVersion=self.settings.result_schema_version,
                    confidence=result_confidence,
                    resultConfidence=result_confidence,
                    result=manifest,
                    traceId=trace_id,
                )
                await self.callback_client.send(str(request.callbackUrl), callback_payload, callback_secret, request_id=request_id)
                return InferenceJobResponse(
                    jobId=request.jobId,
                    status=InferenceStatus.SUCCEEDED.value,
                    requestId=request_id,
                    uploadTraceId=upload_trace_id,
                    inferenceAttemptId=inference_attempt_id,
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
                uploadTraceId=upload_trace_id,
                inferenceAttemptId=inference_attempt_id,
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
                    uploadTraceId=upload_trace_id,
                    inferenceAttemptId=inference_attempt_id,
                    modelVersion=model_version,
                    schemaVersion=self.settings.result_schema_version,
                    failureReason=failure_reason,
                    confidence=0.0,
                    resultConfidence=0.0,
                    result=manifest,
                    traceId=trace_id,
                )
                await self.callback_client.send(str(request.callbackUrl), callback_payload, callback_secret, request_id=request_id)
            except Exception:
                pass
            return InferenceJobResponse(
                jobId=request.jobId,
                status=InferenceStatus.FAILED.value,
                requestId=request_id,
                uploadTraceId=upload_trace_id,
                inferenceAttemptId=inference_attempt_id,
                modelVersion=model_version,
                failureReason=failure_reason,
                confidence=0.0,
                resultConfidence=0.0,
                result=manifest,
                message=failure_summary,
            )

    async def _resolve_source(self, request: InferenceJobRequest, destination: Path) -> Path:
        if request.sourceObjectKey:
            if self.r2_downloader:
                return await asyncio.to_thread(self.r2_downloader.download, request.sourceObjectKey, destination)
            if not request.sourceUrl:
                raise RuntimeError("R2 sourceObjectKey was provided but R2 is not configured.")

        if not request.sourceUrl:
            raise RuntimeError("Source video is unavailable.")

        return await self._download_source(str(request.sourceUrl), destination)

    async def _download_source(self, source_url: str, destination: Path) -> Path:
        async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds, follow_redirects=True) as client:
            response = await client.get(str(source_url))
            response.raise_for_status()
            destination.write_bytes(response.content)
        return destination

    def _requested_model_version(self, request: InferenceJobRequest) -> str:
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

    def _resolve_action(self, primary_action, comparison_action):
        if comparison_action is None:
            return primary_action

        primary_confidence = float(getattr(primary_action, "confidence", 0.0))
        comparison_confidence = float(getattr(comparison_action, "confidence", 0.0))
        chosen = comparison_action if comparison_confidence > primary_confidence + 0.08 else primary_action
        chosen_source = "xclip" if chosen is comparison_action else "videomae"

        merged_top_labels = aggregate_label_scores(
            list(getattr(primary_action, "topLabels", [])) + list(getattr(comparison_action, "topLabels", []))
        )
        metadata = {
            **dict(getattr(primary_action, "metadata", {}) or {}),
            "primary_label": getattr(primary_action, "label", None),
            "primary_canonical_label": getattr(primary_action, "canonicalLabel", None),
            "primary_model_version": getattr(primary_action, "modelVersion", None),
            "primary_failure_reason": getattr(primary_action, "failureReason", None),
            "comparison_label": getattr(comparison_action, "label", None),
            "comparison_canonical_label": getattr(comparison_action, "canonicalLabel", None),
            "comparison_model_version": getattr(comparison_action, "modelVersion", None),
            "comparison_failure_reason": getattr(comparison_action, "failureReason", None),
            "resolved_by": chosen_source,
        }

        if hasattr(chosen, "model_copy"):
            return chosen.model_copy(update={"topLabels": merged_top_labels, "metadata": metadata})
        return chosen


def build_service(settings: InferenceSettings) -> InferenceService:
    comparison = None
    if settings.comparison_model.lower() == "xclip":
        comparison = XClipActionRecognizer(model_name=settings.model_name_xclip)
    r2_downloader = None
    if settings.has_r2_configuration():
        r2_downloader = R2Downloader(
            endpoint_url=settings.r2_endpoint_url,
            bucket_name=settings.r2_bucket_name,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            region_name=settings.r2_region_name,
        )
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
        r2_downloader=r2_downloader,
    )
