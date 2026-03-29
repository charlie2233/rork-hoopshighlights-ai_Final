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
from .labels import blend_label_scores, blend_raw_label_scores, derive_basketball_taxonomy
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
        trace_id, upload_trace_id = _resolve_trace_fields(request, request_id)
        inference_attempt_id = request.inferenceAttemptId or uuid4().hex
        model_version = request.modelVersion or self._requested_model_version(request)
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

                candidates = self.candidate_proposer.propose(features)[: self.settings.max_candidates]
                clip_drafts: list[WindowedClipDraft] = []
                comparison_scores: list[float] = []
                candidate_actions: list[tuple[object, object, object | None]] = []

                for candidate in candidates:
                    primary_action = self.primary_recognizer.recognize(candidate, features)
                    comparison = None
                    if self.comparison_recognizer is not None:
                        comparison = self.comparison_recognizer.recognize(candidate, features)
                        comparison_scores.append(comparison.confidence)

                    candidate_actions.append((candidate, primary_action, comparison))

                candidate_actions = self._apply_temporal_aggregation(candidate_actions)

                for candidate, primary_action, comparison in candidate_actions:
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
                            eventFamily=event.eventFamily,
                            eventSubtype=event.eventSubtype,
                            shotSubtype=event.shotSubtype,
                            outcome=event.outcome,
                            eventType=event.eventType,
                            shotType=event.shotType,
                            makeMiss=event.makeMiss,
                            confidence=min(max(action.confidence, 0.0), 1.0),
                            resultConfidence=min(max(event.rankScore, 0.0), 1.0),
                            confidenceBeforeMapping=event.confidenceBeforeMapping,
                            confidenceAfterMapping=event.confidenceAfterMapping,
                            eventFamilyConfidenceBeforeMapping=getattr(action, "eventFamilyConfidenceBeforeMapping", None),
                            eventFamilyConfidenceAfterMapping=getattr(action, "eventFamilyConfidenceAfterMapping", None),
                            shotSubtypeConfidenceBeforeMapping=getattr(action, "shotSubtypeConfidenceBeforeMapping", None),
                            shotSubtypeConfidenceAfterMapping=getattr(action, "shotSubtypeConfidenceAfterMapping", None),
                            outcomeConfidenceBeforeMapping=getattr(action, "outcomeConfidenceBeforeMapping", None),
                            outcomeConfidenceAfterMapping=getattr(action, "outcomeConfidenceAfterMapping", None),
                            isUncertain=event.isUncertain,
                            promptSetVersion=getattr(action, "promptSetVersion", None),
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
                            rawTopLabels=primary_action.rawTopLabels,
                            comparisonRawTopLabels=comparison.rawTopLabels if comparison else [],
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
                                "comparison_event_family": comparison.eventFamily if comparison else None,
                                "comparison_event_subtype": comparison.eventSubtype if comparison else None,
                                "comparison_shot_subtype": comparison.shotSubtype if comparison else None,
                                "comparison_outcome": comparison.outcome if comparison else None,
                                "prompt_set_version": getattr(action, "promptSetVersion", None),
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
                callback_results = self._build_callback_results(manifest)
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
                    results=callback_results,
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
                callback_results = self._build_callback_results(manifest)
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
                    results=callback_results,
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

        merged_top_labels = blend_label_scores(
            (
                (1.0, list(getattr(primary_action, "topLabels", []))),
                (1.15, list(getattr(comparison_action, "topLabels", []))),
            )
        )
        merged_raw_top_labels = blend_raw_label_scores(
            (
                (1.0, list(getattr(primary_action, "rawTopLabels", []))),
                (1.15, list(getattr(comparison_action, "rawTopLabels", []))),
            )
        )
        best = merged_top_labels[0] if merged_top_labels else getattr(primary_action, "topLabels", [None])[0]
        if best is None:
            return primary_action
        taxonomy = derive_basketball_taxonomy(
            best.label,
            best.confidence,
            merged_top_labels,
            raw_top_labels=merged_raw_top_labels,
            prompt_set_version=getattr(comparison_action, "promptSetVersion", None),
        )
        metadata = {
            **dict(getattr(primary_action, "metadata", {}) or {}),
            "primary_label": getattr(primary_action, "label", None),
            "primary_canonical_label": getattr(primary_action, "canonicalLabel", None),
            "primary_event_family": getattr(primary_action, "eventFamily", None),
            "primary_event_subtype": getattr(primary_action, "eventSubtype", None),
            "primary_shot_subtype": getattr(primary_action, "shotSubtype", None),
            "primary_outcome": getattr(primary_action, "outcome", None),
            "primary_model_version": getattr(primary_action, "modelVersion", None),
            "primary_failure_reason": getattr(primary_action, "failureReason", None),
            "comparison_label": getattr(comparison_action, "label", None),
            "comparison_canonical_label": getattr(comparison_action, "canonicalLabel", None),
            "comparison_event_family": getattr(comparison_action, "eventFamily", None),
            "comparison_event_subtype": getattr(comparison_action, "eventSubtype", None),
            "comparison_shot_subtype": getattr(comparison_action, "shotSubtype", None),
            "comparison_outcome": getattr(comparison_action, "outcome", None),
            "comparison_model_version": getattr(comparison_action, "modelVersion", None),
            "comparison_prompt_set_version": getattr(comparison_action, "promptSetVersion", None),
            "comparison_failure_reason": getattr(comparison_action, "failureReason", None),
            "resolved_by": "hierarchical_combination",
        }

        if hasattr(primary_action, "model_copy"):
            return primary_action.model_copy(
                update={
                    "label": taxonomy.display_label,
                    "canonicalLabel": taxonomy.canonical_label,
                    "confidence": taxonomy.confidence_after_mapping,
                    "topLabels": merged_top_labels,
                    "rawTopLabels": merged_raw_top_labels,
                    "promptSetVersion": getattr(comparison_action, "promptSetVersion", None),
                    "eventFamily": taxonomy.event_family,
                    "eventSubtype": taxonomy.event_subtype,
                    "shotSubtype": taxonomy.shot_subtype,
                    "outcome": taxonomy.outcome,
                    "confidenceBeforeMapping": taxonomy.confidence_before_mapping,
                    "confidenceAfterMapping": taxonomy.confidence_after_mapping,
                    "eventFamilyConfidenceBeforeMapping": taxonomy.event_family_confidence_before_mapping,
                    "eventFamilyConfidenceAfterMapping": taxonomy.event_family_confidence_after_mapping,
                    "shotSubtypeConfidenceBeforeMapping": taxonomy.shot_subtype_confidence_before_mapping,
                    "shotSubtypeConfidenceAfterMapping": taxonomy.shot_subtype_confidence_after_mapping,
                    "outcomeConfidenceBeforeMapping": taxonomy.outcome_confidence_before_mapping,
                    "outcomeConfidenceAfterMapping": taxonomy.outcome_confidence_after_mapping,
                    "isUncertain": taxonomy.is_uncertain,
                    "metadata": metadata,
                }
            )
        return primary_action

    def _apply_temporal_aggregation(self, candidate_actions):
        if not candidate_actions:
            return candidate_actions

        aggregated: list[tuple[object, object, object | None]] = []
        for index, (candidate, primary_action, comparison_action) in enumerate(candidate_actions):
            aggregated_primary = self._aggregate_action_over_neighbors(index, candidate_actions, primary_action, slot=1)
            aggregated_comparison = None
            if comparison_action is not None:
                aggregated_comparison = self._aggregate_action_over_neighbors(index, candidate_actions, comparison_action, slot=2)
            aggregated.append((candidate, aggregated_primary, aggregated_comparison))
        return aggregated

    def _aggregate_action_over_neighbors(self, index, candidate_actions, action, *, slot: int):
        weighted_top_labels = []
        weighted_raw_top_labels = []
        member_candidate_ids: list[str] = []
        total_weight = 0.0
        current_candidate = candidate_actions[index][0]

        for other_index, candidate_action in enumerate(candidate_actions):
            other_candidate = candidate_action[0]
            other_action = candidate_action[slot]
            if other_action is None:
                continue
            weight = self._temporal_weight(current_candidate, other_candidate, is_self=index == other_index)
            if weight <= 0:
                continue
            total_weight += weight
            member_candidate_ids.append(other_candidate.candidateId)
            weighted_top_labels.append((weight, list(getattr(other_action, "topLabels", []))))
            weighted_raw_top_labels.append((weight, list(getattr(other_action, "rawTopLabels", []))))

        blended_top_labels = blend_label_scores(weighted_top_labels) or list(getattr(action, "topLabels", []))
        blended_raw_top_labels = blend_raw_label_scores(weighted_raw_top_labels) or list(getattr(action, "rawTopLabels", []))
        best = blended_top_labels[0] if blended_top_labels else None
        if best is None or not hasattr(action, "model_copy"):
            return action

        taxonomy = derive_basketball_taxonomy(
            best.label,
            best.confidence,
            blended_top_labels,
            raw_top_labels=blended_raw_top_labels,
            prompt_set_version=getattr(action, "promptSetVersion", None),
        )
        metadata = {
            **dict(getattr(action, "metadata", {}) or {}),
            "temporal_aggregation": {
                "member_candidate_ids": member_candidate_ids,
                "member_count": len(member_candidate_ids),
                "total_weight": round(total_weight, 4),
            },
        }
        return action.model_copy(
            update={
                "label": taxonomy.display_label,
                "canonicalLabel": taxonomy.canonical_label,
                "confidence": taxonomy.confidence_after_mapping,
                "topLabels": blended_top_labels,
                "rawTopLabels": blended_raw_top_labels,
                "eventFamily": taxonomy.event_family,
                "eventSubtype": taxonomy.event_subtype,
                "shotSubtype": taxonomy.shot_subtype,
                "outcome": taxonomy.outcome,
                "confidenceBeforeMapping": taxonomy.confidence_before_mapping,
                "confidenceAfterMapping": taxonomy.confidence_after_mapping,
                "eventFamilyConfidenceBeforeMapping": taxonomy.event_family_confidence_before_mapping,
                "eventFamilyConfidenceAfterMapping": taxonomy.event_family_confidence_after_mapping,
                "shotSubtypeConfidenceBeforeMapping": taxonomy.shot_subtype_confidence_before_mapping,
                "shotSubtypeConfidenceAfterMapping": taxonomy.shot_subtype_confidence_after_mapping,
                "outcomeConfidenceBeforeMapping": taxonomy.outcome_confidence_before_mapping,
                "outcomeConfidenceAfterMapping": taxonomy.outcome_confidence_after_mapping,
                "isUncertain": taxonomy.is_uncertain,
                "metadata": metadata,
            }
        )

    def _temporal_weight(self, current_candidate, other_candidate, *, is_self: bool) -> float:
        if is_self:
            return 1.0

        current_duration = max(current_candidate.endTime - current_candidate.startTime, 0.001)
        other_duration = max(other_candidate.endTime - other_candidate.startTime, 0.001)
        overlap = max(
            0.0,
            min(current_candidate.endTime, other_candidate.endTime)
            - max(current_candidate.startTime, other_candidate.startTime),
        )
        if overlap > 0:
            overlap_ratio = overlap / max(current_duration, other_duration)
            base_weight = 0.55 + (0.25 * min(max(overlap_ratio, 0.0), 1.0))
        else:
            gap = max(
                other_candidate.startTime - current_candidate.endTime,
                current_candidate.startTime - other_candidate.endTime,
                0.0,
            )
            if gap > max(self.settings.heuristic_stride_seconds * 1.5, 2.25):
                return 0.0
            base_weight = max(0.0, 0.5 - (0.15 * gap))

        return round(base_weight * (0.7 + (0.3 * min(max(other_candidate.score, 0.0), 1.0))), 4)

    def _build_callback_results(self, manifest: InferenceManifest) -> dict[str, object]:
        clips = [
            {
                "startTime": clip.startTime,
                "endTime": clip.endTime,
                "clipDurationSeconds": clip.clipDurationSeconds,
                "eventCenterSeconds": clip.eventCenterSeconds,
                "preRollSeconds": clip.preRollSeconds,
                "postRollSeconds": clip.postRollSeconds,
                "windowPolicyVersion": clip.windowPolicyVersion,
                "wasMerged": clip.wasMerged,
                "sourceEventCount": clip.sourceEventCount,
                "confidence": clip.confidence,
                "confidenceBeforeMapping": clip.confidenceBeforeMapping,
                "confidenceAfterMapping": clip.confidenceAfterMapping,
                "eventFamilyConfidenceBeforeMapping": clip.eventFamilyConfidenceBeforeMapping,
                "eventFamilyConfidenceAfterMapping": clip.eventFamilyConfidenceAfterMapping,
                "shotSubtypeConfidenceBeforeMapping": clip.shotSubtypeConfidenceBeforeMapping,
                "shotSubtypeConfidenceAfterMapping": clip.shotSubtypeConfidenceAfterMapping,
                "outcomeConfidenceBeforeMapping": clip.outcomeConfidenceBeforeMapping,
                "outcomeConfidenceAfterMapping": clip.outcomeConfidenceAfterMapping,
                "label": clip.label,
                "action": clip.action,
                "canonicalLabel": clip.canonicalLabel,
                "eventFamily": clip.eventFamily,
                "eventSubtype": clip.eventSubtype,
                "shotSubtype": clip.shotSubtype,
                "outcome": clip.outcome,
                "audioScore": clip.audioScore,
                "visualScore": clip.visualScore,
                "motionScore": clip.motionScore,
                "combinedScore": clip.combinedScore,
                "detectionMethod": "cloud" if clip.detectionMethod == "model" else clip.detectionMethod,
                "shouldAutoKeep": clip.shouldAutoKeep,
                "shouldEnableSlowMotion": clip.shouldEnableSlowMotion,
                "isUncertain": clip.isUncertain,
                "promptSetVersion": clip.promptSetVersion,
                "eventType": clip.eventType,
                "shotType": clip.shotType,
                "makeMiss": clip.makeMiss,
                "rankScore": clip.rankScore,
                "reviewState": clip.reviewState,
                "reviewerNotes": clip.reviewerNotes,
                "topLabels": [item.model_dump(mode="json") for item in clip.topLabels],
                "comparisonTopLabels": [item.model_dump(mode="json") for item in clip.comparisonTopLabels],
                "rawTopLabels": [item.model_dump(mode="json") for item in clip.rawTopLabels],
                "comparisonRawTopLabels": [item.model_dump(mode="json") for item in clip.comparisonRawTopLabels],
            }
            for clip in manifest.clips
        ]
        return {
            "requestId": manifest.requestId,
            "confidence": manifest.resultConfidence,
            "modelVersion": manifest.modelVersion,
            "failureReason": manifest.failureReason,
            "clipCount": len(clips),
            "clips": clips,
            "diagnostics": {
                "processingMs": 0,
                "backendModelVersion": manifest.modelVersion,
                "usedVideoIntelligence": False,
                "usedGeminiRelabeling": False,
                "candidateSegments": len(clips),
                "finalSegments": len(clips),
            },
            "resultConfidence": manifest.resultConfidence,
        }


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


def _resolve_trace_fields(request: InferenceJobRequest, request_id: str) -> tuple[str, str]:
    trace_id = request.traceId or request_id
    upload_trace_id = request.uploadTraceId or trace_id
    return trace_id, upload_trace_id
