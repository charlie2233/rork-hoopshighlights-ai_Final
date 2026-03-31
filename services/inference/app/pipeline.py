from __future__ import annotations

import asyncio
import json
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
from .distilled_clip_encoder import (
    DistilledClipEncoderBundle,
    DistilledClipEncoderPrediction,
    get_distilled_clip_encoder_bundle,
)
from .ffmpeg_tools import prepare_media_source
from .features import extract_video_features
from .labels import blend_label_scores, blend_raw_label_scores, derive_basketball_taxonomy
from .heuristics import ConfidenceReranker, HeuristicCandidateProposer, HeuristicEventInferencer
from .interfaces import ArtifactWriter, Perceptor, TeacherLabeler
from .manifest import LocalArtifactWriter, build_manifest_dict
from .perception import HeuristicBasketballPerceptor
from .perception_features import PerceptionObservation, derive_perception_features
from .runtime_model import (
    RuntimeFusionBundle,
    RuntimeFusionPrediction,
    build_runtime_snapshot,
    get_runtime_fusion_bundle,
)
from .runtime_models.temporal_student import (
    TemporalStudentBundle,
    TemporalStudentObservation,
    get_temporal_student_bundle,
)
from .structured_signals import derive_structured_decision, derive_structured_signals
from .teacher import QwenTeacherLabeler
from .temporal_encoder import (
    TemporalEncoderBundle,
    TemporalObservation,
    get_temporal_encoder_bundle,
)
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
    adapted_primary_recognizer: Optional[VideoMAEActionRecognizer]
    comparison_recognizer: Optional[XClipActionRecognizer]
    event_inferencer: HeuristicEventInferencer
    reranker: ConfidenceReranker
    artifact_writer: ArtifactWriter
    callback_client: CallbackClient
    r2_downloader: Optional[R2Downloader] = None
    perceptor: Optional[Perceptor] = None
    teacher_labeler: Optional[TeacherLabeler] = None
    runtime_model: Optional[RuntimeFusionBundle] = None
    temporal_encoder: Optional[TemporalEncoderBundle | TemporalStudentBundle] = None
    distilled_clip_encoder: Optional[DistilledClipEncoderBundle] = None

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
                candidate_actions: list[tuple[object, object, object | None, object | None]] = []
                artifact_descriptors: list[ArtifactDescriptor] = []

                for candidate in candidates:
                    primary_action = self.primary_recognizer.recognize(candidate, features)
                    adapted_primary_action = None
                    if self.adapted_primary_recognizer is not None:
                        adapted_primary_action = self.adapted_primary_recognizer.recognize(candidate, features)
                    comparison = None
                    if self.comparison_recognizer is not None:
                        comparison = self.comparison_recognizer.recognize(candidate, features)
                        comparison_scores.append(comparison.confidence)

                    candidate_actions.append((candidate, primary_action, comparison, adapted_primary_action))

                candidate_actions = self._apply_temporal_aggregation(candidate_actions)

                for candidate, primary_action, comparison, adapted_primary_action in candidate_actions:
                    lora_mode = self.settings.videomae_lora_mode.lower()
                    baseline_action = self._resolve_action(primary_action, comparison)
                    adapted_action = self._resolve_action(adapted_primary_action, comparison) if adapted_primary_action else None
                    use_adapted_primary = adapted_action is not None and lora_mode in {"primary", "live"}
                    base_action = adapted_action if use_adapted_primary else baseline_action
                    active_primary_action = adapted_primary_action if use_adapted_primary else primary_action
                    perception = self._analyze_perception(preparation.prepared_path, candidate)
                    overlay_artifacts = self._persist_perception_overlays(
                        request.jobId,
                        candidate.candidateId,
                        perception,
                    )
                    artifact_descriptors.extend(overlay_artifacts)
                    structured_signals = derive_structured_signals(
                        candidate_metadata={"perception": perception},
                        action=base_action,
                    )
                    structured_decision = derive_structured_decision(
                        signals=structured_signals,
                        action=base_action,
                    )
                    teacher_suggestion = self._derive_teacher_suggestion(
                        source_path=preparation.prepared_path,
                        candidate=candidate,
                        action=base_action,
                        perception=perception,
                        structured_signals=structured_signals.as_metadata(),
                    )
                    runtime_prediction = self._predict_runtime_fusion(
                        action=base_action,
                        primary_action=active_primary_action,
                        comparison_action=comparison,
                        structured_signals=structured_signals.as_metadata(),
                        candidate=candidate,
                        perception=perception,
                    )
                    lora_runtime_shadow = None
                    if adapted_action is not None and lora_mode == "shadow":
                        lora_runtime_shadow = self._predict_runtime_fusion(
                            action=adapted_action,
                            primary_action=adapted_primary_action,
                            comparison_action=comparison,
                            structured_signals=structured_signals.as_metadata(),
                            candidate=candidate,
                            perception=perception,
                        )
                    structured_action = self._apply_structured_decision(
                        action=base_action,
                        decision=structured_decision,
                        structured_signals=structured_signals.as_metadata(),
                        perception=perception,
                        teacher_suggestion=teacher_suggestion,
                    )
                    temporal_runtime_shadow = self._predict_temporal_shadow(
                        action=structured_action,
                        primary_action=active_primary_action,
                        comparison_action=comparison,
                        structured_signals=structured_signals.as_metadata(),
                        candidate=candidate,
                        perception=perception,
                    )
                    distilled_runtime_shadow = self._predict_distilled_shadow(
                        action=structured_action,
                        primary_action=active_primary_action,
                        comparison_action=comparison,
                        structured_signals=structured_signals.as_metadata(),
                        candidate=candidate,
                        perception=perception,
                    )
                    action = self._resolve_runtime_action(
                        structured_action=structured_action,
                        runtime_prediction=runtime_prediction,
                        structured_signals=structured_signals.as_metadata(),
                        perception=perception,
                    )
                    if lora_runtime_shadow is not None:
                        action = self._attach_runtime_shadow(
                            action=action,
                            runtime_prediction=lora_runtime_shadow,
                            structured_signals=structured_signals.as_metadata(),
                            perception=perception,
                            key="runtimeFusionLoRAShadow",
                        )
                    if temporal_runtime_shadow is not None:
                        action = self._attach_candidate_shadow(
                            action=action,
                            shadow_payload=_temporal_shadow_payload(temporal_runtime_shadow),
                            structured_signals=structured_signals.as_metadata(),
                            perception=perception,
                            key="runtimeFusionTemporalShadow",
                        )
                    if distilled_runtime_shadow is not None:
                        action = self._attach_candidate_shadow(
                            action=action,
                            shadow_payload=_distilled_shadow_payload(distilled_runtime_shadow),
                            structured_signals=structured_signals.as_metadata(),
                            perception=perception,
                            key="runtimeFusionDistilledShadow",
                        )
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
                                "perception_summary": _summarize_perception(perception),
                                "structured_signals": structured_signals.as_metadata(),
                                "teacher_suggestion": teacher_suggestion,
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
                ] + artifact_descriptors
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
                        actionRecognizer=self._action_recognizer_name(),
                        comparisonRecognizer=f"xclip:{self.comparison_recognizer.model_name}" if self.comparison_recognizer else None,
                        eventInferencer="structured-basketball-signals",
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
                    actionRecognizer=self._action_recognizer_name(),
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
        if self.runtime_model is not None and self.settings.runtime_model_mode.lower() in {"primary", "live"}:
            return self.runtime_model.model_version
        if self.adapted_primary_recognizer is not None and self.settings.videomae_lora_mode.lower() in {"primary", "live"}:
            return self.adapted_primary_recognizer.resolved_model_version()
        return self.primary_recognizer.resolved_model_version()

    def _action_recognizer_name(self) -> str:
        if self.runtime_model is not None and self.settings.runtime_model_mode.lower() in {"primary", "live"}:
            return f"runtime-fusion:{self.runtime_model.model_version}"
        if self.adapted_primary_recognizer is not None and self.settings.videomae_lora_mode.lower() in {"primary", "live"}:
            return self.adapted_primary_recognizer.resolved_model_version()
        return self.primary_recognizer.resolved_model_version()

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

    def _analyze_perception(self, source_path: Path, candidate) -> dict[str, object]:
        if self.perceptor is None:
            return {}
        try:
            return dict(self.perceptor.analyze(source_path, candidate))
        except Exception as exc:
            return {"failureReason": f"perception_failed:{exc.__class__.__name__}"}

    def _persist_perception_overlays(
        self,
        job_id: str,
        candidate_id: str,
        perception: dict[str, object],
    ) -> list[ArtifactDescriptor]:
        overlay_paths = perception.get("overlayPaths")
        if not isinstance(overlay_paths, list):
            return []

        artifacts: list[ArtifactDescriptor] = []
        persisted_paths: list[str] = []
        for index, overlay_path in enumerate(overlay_paths):
            if not isinstance(overlay_path, str) or not overlay_path:
                continue
            source = Path(overlay_path)
            if not source.exists():
                continue
            artifact_name = f"{candidate_id}-overlay-{index + 1}.jpg"
            persisted = self.artifact_writer.write_artifact(
                job_id,
                artifact_name,
                source.read_bytes(),
                "image/jpeg",
            )
            persisted_paths.append(str(persisted))
            artifacts.append(
                ArtifactDescriptor(
                    kind="perception_overlay",
                    path=str(persisted),
                    mediaType="image/jpeg",
                    sizeBytes=persisted.stat().st_size,
                )
            )
        if persisted_paths:
            perception["overlayPaths"] = persisted_paths
        return artifacts

    def _derive_teacher_suggestion(
        self,
        *,
        source_path: Path,
        candidate,
        action,
        perception: dict[str, object],
        structured_signals: dict[str, object],
    ) -> dict[str, object] | None:
        if self.teacher_labeler is None or not self.settings.teacher_labeling_enabled:
            return None
        try:
            return dict(
                self.teacher_labeler.suggest(
                    source_path,
                    candidate,
                    {
                        "structuredSignals": structured_signals,
                        "actionSummary": {
                            "label": getattr(action, "label", None),
                            "canonicalLabel": getattr(action, "canonicalLabel", None),
                            "eventFamily": getattr(action, "eventFamily", None),
                            "shotSubtype": getattr(action, "shotSubtype", None),
                            "outcome": getattr(action, "outcome", None),
                            "topLabels": [
                                item.model_dump(mode="json")
                                for item in list(getattr(action, "topLabels", []))[:3]
                            ],
                            "rawTopLabels": [
                                item.model_dump(mode="json")
                                for item in list(getattr(action, "rawTopLabels", []))[:3]
                            ],
                        },
                        "perceptionSummary": _summarize_perception(perception),
                    },
                )
            )
        except Exception as exc:
            return {"status": "unavailable", "failureReason": f"teacher_failed:{exc.__class__.__name__}"}

    def _apply_structured_decision(
        self,
        *,
        action,
        decision,
        structured_signals: dict[str, object],
        perception: dict[str, object],
        teacher_suggestion: dict[str, object] | None,
    ):
        metadata = {
            **dict(getattr(action, "metadata", {}) or {}),
            "resolved_by": "structured_basketball_signals",
            "structuredSignals": structured_signals,
            "perceptionSummary": _summarize_perception(perception),
            "teacherSuggestion": teacher_suggestion,
        }
        if hasattr(action, "model_copy"):
            return action.model_copy(
                update={
                    "label": decision.displayLabel,
                    "canonicalLabel": decision.canonicalLabel,
                    "confidence": decision.confidenceAfterMapping,
                    "eventFamily": decision.eventFamily,
                    "eventSubtype": decision.eventSubtype,
                    "shotSubtype": decision.shotSubtype,
                    "outcome": decision.outcome,
                    "confidenceBeforeMapping": decision.confidenceBeforeMapping,
                    "confidenceAfterMapping": decision.confidenceAfterMapping,
                    "eventFamilyConfidenceBeforeMapping": decision.eventFamilyConfidenceBeforeMapping,
                    "eventFamilyConfidenceAfterMapping": decision.eventFamilyConfidenceAfterMapping,
                    "shotSubtypeConfidenceBeforeMapping": decision.shotSubtypeConfidenceBeforeMapping,
                    "shotSubtypeConfidenceAfterMapping": decision.shotSubtypeConfidenceAfterMapping,
                    "outcomeConfidenceBeforeMapping": decision.outcomeConfidenceBeforeMapping,
                    "outcomeConfidenceAfterMapping": decision.outcomeConfidenceAfterMapping,
                    "isUncertain": decision.isUncertain,
                    "metadata": metadata,
                }
            )
        return action

    def _predict_runtime_fusion(
        self,
        *,
        action,
        primary_action,
        comparison_action,
        structured_signals: dict[str, object],
        candidate,
        perception: dict[str, object],
    ) -> RuntimeFusionPrediction | None:
        if self.runtime_model is None:
            return None
        try:
            snapshot = build_runtime_snapshot(
                action=action,
                primary_action=primary_action,
                comparison_action=comparison_action,
                structured_signals=structured_signals,
                source_kind="runtime",
                source_domain=self.settings.environment,
                source_set="runtime_inference",
                human_verified=False,
                ball_visible=_perception_visible(perception, "basketball"),
                hoop_visible=_perception_visible(perception, "rim"),
                clip_duration_seconds=max(candidate.endTime - candidate.startTime, 0.0),
                event_center_seconds=round((candidate.startTime + candidate.endTime) / 2.0, 4),
                pre_roll_seconds=0.0,
                post_roll_seconds=0.0,
                source_event_count=1,
                was_merged=False,
            )
            return self.runtime_model.predict_from_snapshot(snapshot)
        except Exception as exc:
            if hasattr(action, "model_copy"):
                metadata = {
                    **dict(getattr(action, "metadata", {}) or {}),
                    "runtimeFusionFailureReason": f"{exc.__class__.__name__}",
                }
                return None
            return None

    def _predict_temporal_shadow(
        self,
        *,
        action,
        primary_action,
        comparison_action,
        structured_signals: dict[str, object],
        candidate,
        perception: dict[str, object],
    ):
        if self.temporal_encoder is None or self.settings.temporal_encoder_mode.lower() != "shadow":
            return None
        try:
            if isinstance(self.temporal_encoder, TemporalStudentBundle):
                observations = _build_temporal_student_observations(
                    action=action,
                    primary_action=primary_action,
                    comparison_action=comparison_action,
                    candidate=candidate,
                    structured_signals=structured_signals,
                    perception=perception,
                    environment=self.settings.environment,
                )
            else:
                observations = _build_temporal_observations(
                    candidate=candidate,
                    structured_signals=structured_signals,
                    perception=perception,
                )
            if not observations:
                return None
            return self.temporal_encoder.predict(observations)
        except Exception:
            return None

    def _predict_distilled_shadow(
        self,
        *,
        action,
        primary_action,
        comparison_action,
        structured_signals: dict[str, object],
        candidate,
        perception: dict[str, object],
    ) -> DistilledClipEncoderPrediction | None:
        if self.distilled_clip_encoder is None or self.settings.distilled_clip_encoder_mode.lower() != "shadow":
            return None
        try:
            snapshot = _build_distilled_shadow_snapshot(
                action=action,
                primary_action=primary_action,
                comparison_action=comparison_action,
                structured_signals=structured_signals,
                candidate=candidate,
                perception=perception,
                environment=self.settings.environment,
            )
            return self.distilled_clip_encoder.predict_from_snapshot(snapshot)
        except Exception:
            return None

    def _resolve_runtime_action(
        self,
        *,
        structured_action,
        runtime_prediction: RuntimeFusionPrediction | None,
        structured_signals: dict[str, object],
        perception: dict[str, object],
    ):
        if runtime_prediction is None:
            return structured_action

        mode = self.settings.runtime_model_mode.lower()
        runtime_metadata = {
            **runtime_prediction.metadata,
            "structuredSignals": structured_signals,
            "perceptionSummary": _summarize_perception(perception),
        }
        if mode == "shadow":
            if hasattr(structured_action, "model_copy"):
                metadata = {
                    **dict(getattr(structured_action, "metadata", {}) or {}),
                    "runtimeFusionShadow": runtime_metadata,
                }
                return structured_action.model_copy(update={"metadata": metadata})
            return structured_action
        if mode not in {"primary", "live"}:
            return structured_action

        event_family = _blend_event_family(structured_action, runtime_prediction)
        outcome = _blend_outcome(structured_action, runtime_prediction, event_family)
        shot_subtype = _blend_shot_subtype(structured_action, runtime_prediction, event_family)
        canonical_label, display_label = _blend_display_label(event_family, outcome, shot_subtype)
        family_before = max(
            float(getattr(structured_action, "eventFamilyConfidenceBeforeMapping", 0.0) or 0.0),
            float(runtime_prediction.event_family_confidence_before_mapping or 0.0),
        )
        family_after = max(
            float(getattr(structured_action, "eventFamilyConfidenceAfterMapping", 0.0) or 0.0),
            float(runtime_prediction.event_family_confidence_after_mapping or 0.0),
        )
        shot_before = _blend_confidence(
            getattr(structured_action, "shotSubtypeConfidenceBeforeMapping", None),
            runtime_prediction.shot_subtype_confidence_before_mapping,
            present=shot_subtype is not None,
        )
        shot_after = _blend_confidence(
            getattr(structured_action, "shotSubtypeConfidenceAfterMapping", None),
            runtime_prediction.shot_subtype_confidence_after_mapping,
            present=shot_subtype is not None,
        )
        outcome_before = max(
            float(getattr(structured_action, "outcomeConfidenceBeforeMapping", 0.0) or 0.0),
            float(runtime_prediction.outcome_confidence_before_mapping or 0.0),
        )
        outcome_after = max(
            float(getattr(structured_action, "outcomeConfidenceAfterMapping", 0.0) or 0.0),
            float(runtime_prediction.outcome_confidence_after_mapping or 0.0),
        )
        is_uncertain = outcome == "uncertain" or (display_label == "Highlight" and event_family in {"other", "shot_attempt"})
        confidence_after = _blend_display_confidence(
            display_label=display_label,
            family_after=family_after,
            shot_after=shot_after,
            outcome_after=outcome_after,
            is_uncertain=is_uncertain,
        )
        confidence_before = max(
            float(getattr(structured_action, "confidenceBeforeMapping", 0.0) or 0.0),
            float(runtime_prediction.confidence_before_mapping or 0.0),
        )

        if hasattr(structured_action, "model_copy"):
            metadata = {
                **dict(getattr(structured_action, "metadata", {}) or {}),
                "runtimeFusionPrimary": runtime_metadata,
                "runtimeFusionLive": runtime_metadata,
                "resolved_by": "runtime_fusion_model",
            }
            return structured_action.model_copy(
                update={
                    "label": display_label,
                    "canonicalLabel": canonical_label,
                    "confidence": confidence_after,
                    "modelVersion": runtime_prediction.model_version,
                    "detectionMethod": "runtime_fusion",
                    "eventFamily": event_family,
                    "eventSubtype": _event_subtype_for_family(
                        event_family,
                        shot_subtype,
                        outcome,
                    ),
                    "shotSubtype": shot_subtype,
                    "outcome": outcome,
                    "confidenceBeforeMapping": confidence_before,
                    "confidenceAfterMapping": confidence_after,
                    "eventFamilyConfidenceBeforeMapping": family_before,
                    "eventFamilyConfidenceAfterMapping": family_after,
                    "shotSubtypeConfidenceBeforeMapping": shot_before,
                    "shotSubtypeConfidenceAfterMapping": shot_after,
                    "outcomeConfidenceBeforeMapping": outcome_before,
                    "outcomeConfidenceAfterMapping": outcome_after,
                    "isUncertain": is_uncertain,
                    "metadata": metadata,
                }
            )
        return structured_action

    def _attach_runtime_shadow(
        self,
        *,
        action,
        runtime_prediction: RuntimeFusionPrediction,
        structured_signals: dict[str, object],
        perception: dict[str, object],
        key: str,
    ):
        runtime_metadata = {
            **runtime_prediction.metadata,
            "structuredSignals": structured_signals,
            "perceptionSummary": _summarize_perception(perception),
        }
        if hasattr(action, "model_copy"):
            metadata = {
                **dict(getattr(action, "metadata", {}) or {}),
                key: runtime_metadata,
            }
            return action.model_copy(update={"metadata": metadata})
        return action

    def _attach_candidate_shadow(
        self,
        *,
        action,
        shadow_payload: dict[str, object],
        structured_signals: dict[str, object],
        perception: dict[str, object],
        key: str,
    ):
        runtime_metadata = {
            **shadow_payload,
            "structuredSignals": structured_signals,
            "perceptionSummary": _summarize_perception(perception),
        }
        if hasattr(action, "model_copy"):
            metadata = {
                **dict(getattr(action, "metadata", {}) or {}),
                key: runtime_metadata,
            }
            return action.model_copy(update={"metadata": metadata})
        return action

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
        primary_metadata = dict(getattr(primary_action, "metadata", {}) or {})
        comparison_metadata = dict(getattr(comparison_action, "metadata", {}) or {})
        taxonomy = derive_basketball_taxonomy(
            best.label,
            best.confidence,
            merged_top_labels,
            raw_top_labels=merged_raw_top_labels,
            prompt_set_version=getattr(comparison_action, "promptSetVersion", None),
        )
        metadata = {
            **primary_metadata,
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
            "calibration_version": primary_metadata.get("calibration_version"),
            "calibrated_confidence": primary_metadata.get("calibrated_confidence"),
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

        aggregated: list[tuple[object, object, object | None, object | None]] = []
        for index, (candidate, primary_action, comparison_action, adapted_primary_action) in enumerate(candidate_actions):
            aggregated_primary = self._aggregate_action_over_neighbors(index, candidate_actions, primary_action, slot=1)
            aggregated_comparison = None
            if comparison_action is not None:
                aggregated_comparison = self._aggregate_action_over_neighbors(index, candidate_actions, comparison_action, slot=2)
            aggregated_adapted = None
            if adapted_primary_action is not None:
                aggregated_adapted = self._aggregate_action_over_neighbors(index, candidate_actions, adapted_primary_action, slot=3)
            aggregated.append((candidate, aggregated_primary, aggregated_comparison, aggregated_adapted))
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

        action_metadata = dict(getattr(action, "metadata", {}) or {})
        taxonomy = derive_basketball_taxonomy(
            best.label,
            best.confidence,
            blended_top_labels,
            raw_top_labels=blended_raw_top_labels,
            prompt_set_version=getattr(action, "promptSetVersion", None),
        )
        metadata = {
            **action_metadata,
            "temporal_aggregation": {
                "member_candidate_ids": member_candidate_ids,
                "member_count": len(member_candidate_ids),
                "total_weight": round(total_weight, 4),
            },
            "calibration_version": action_metadata.get("calibration_version"),
            "calibrated_confidence": action_metadata.get("calibrated_confidence"),
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
                "runtimeFusionShadow": _runtime_metadata_from_clip(clip, "runtimeFusionShadow"),
                "runtimeFusionLoRAShadow": _runtime_metadata_from_clip(clip, "runtimeFusionLoRAShadow"),
                "runtimeFusionTemporalShadow": _runtime_metadata_from_clip(clip, "runtimeFusionTemporalShadow"),
                "runtimeFusionDistilledShadow": _runtime_metadata_from_clip(clip, "runtimeFusionDistilledShadow"),
                "runtimeFusionPrimary": (
                    _runtime_metadata_from_clip(clip, "runtimeFusionPrimary")
                    or _runtime_metadata_from_clip(clip, "runtimeFusionLive")
                ),
                "runtimeFusionLive": _runtime_metadata_from_clip(clip, "runtimeFusionLive"),
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
                "runtimeModelMode": self.settings.runtime_model_mode,
                "runtimeModelVersion": getattr(self.runtime_model, "model_version", None),
                "temporalEncoderMode": self.settings.temporal_encoder_mode,
                "temporalEncoderVersion": getattr(self.temporal_encoder, "model_version", None),
                "distilledClipEncoderMode": self.settings.distilled_clip_encoder_mode,
                "distilledClipEncoderVersion": getattr(self.distilled_clip_encoder, "model_version", None),
                "videoMAELoraMode": self.settings.videomae_lora_mode,
                "videoMAELoraVersion": (
                    self.adapted_primary_recognizer.resolved_model_version()
                    if self.adapted_primary_recognizer is not None
                    else None
                ),
            },
            "resultConfidence": manifest.resultConfidence,
        }


def build_service(settings: InferenceSettings) -> InferenceService:
    comparison = None
    if settings.comparison_model.lower() == "xclip":
        comparison = XClipActionRecognizer(model_name=settings.model_name_xclip)
    adapted_primary = None
    if settings.videomae_lora_mode.lower() in {"shadow", "primary", "live"} and settings.videomae_lora_bundle_path.exists():
        adapted_primary = VideoMAEActionRecognizer(
            model_name=settings.model_name_videomae,
            lora_bundle_path=str(settings.videomae_lora_bundle_path),
        )
    teacher_labeler = None
    if settings.teacher_labeling_enabled:
        teacher_labeler = QwenTeacherLabeler(
            model_name=settings.teacher_model_name,
            frame_count=settings.teacher_frame_count,
        )
    r2_downloader = None
    if settings.has_r2_configuration():
        r2_downloader = R2Downloader(
            endpoint_url=settings.r2_endpoint_url,
            bucket_name=settings.r2_bucket_name,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            region_name=settings.r2_region_name,
        )
    runtime_model = None
    if settings.runtime_model_mode.lower() in {"shadow", "primary", "live"}:
        runtime_model = get_runtime_fusion_bundle(str(settings.runtime_model_bundle_path))
    temporal_encoder = None
    if settings.temporal_encoder_mode.lower() in {"shadow", "primary", "live"}:
        temporal_encoder = _load_temporal_shadow_bundle(settings.temporal_encoder_bundle_path)
    distilled_clip_encoder = None
    if settings.distilled_clip_encoder_mode.lower() in {"shadow", "primary", "live"}:
        distilled_clip_encoder = get_distilled_clip_encoder_bundle(str(settings.distilled_clip_encoder_bundle_path))
    return InferenceService(
        settings=settings,
        candidate_proposer=HeuristicCandidateProposer(
            window_seconds=settings.heuristic_window_seconds,
            stride_seconds=settings.heuristic_stride_seconds,
        ),
        primary_recognizer=VideoMAEActionRecognizer(model_name=settings.model_name_videomae),
        adapted_primary_recognizer=adapted_primary,
        comparison_recognizer=comparison,
        event_inferencer=HeuristicEventInferencer(),
        reranker=ConfidenceReranker(),
        artifact_writer=LocalArtifactWriter(settings.ensure_temp_dir()),
        callback_client=CallbackClient(timeout_seconds=settings.callback_timeout_seconds),
        r2_downloader=r2_downloader,
        perceptor=HeuristicBasketballPerceptor(
            sample_frames=settings.perception_sample_frames,
            overlay_frame_limit=settings.perception_overlay_frame_limit,
        ),
        teacher_labeler=teacher_labeler,
        runtime_model=runtime_model,
        temporal_encoder=temporal_encoder,
        distilled_clip_encoder=distilled_clip_encoder,
    )


def _build_temporal_observations(
    *,
    candidate,
    structured_signals: dict[str, object],
    perception: dict[str, object],
) -> list[TemporalObservation]:
    grouped_frames = _perception_frame_observations(perception)
    summary_features = _perception_summary_features(perception)
    clip_center = round((float(candidate.startTime) + float(candidate.endTime)) / 2.0, 4)
    if not grouped_frames:
        return [
            TemporalObservation(
                timestamp_seconds=clip_center,
                structured_signals=dict(structured_signals),
                perception_features=dict(summary_features),
            )
        ]

    observations: list[TemporalObservation] = []
    for index, frame_observations in enumerate(grouped_frames):
        window_start = max(0, index - 1)
        window_stop = min(len(grouped_frames), index + 2)
        local_features = derive_perception_features(
            grouped_frames[window_start:window_stop],
            ball_labels=("basketball", "ball"),
            rim_labels=("rim", "hoop"),
            player_labels=("player", "players"),
            defender_labels=("defender",),
        )
        frame_timestamp = float(frame_observations[0].timestamp_seconds)
        local_structured = {
            **dict(structured_signals),
            "ballNearRim": max(float(structured_signals.get("ballNearRim") or 0.0), local_features.ballNearRim),
            "ballAboveRim": max(float(structured_signals.get("ballAboveRim") or 0.0), local_features.ballAboveRim),
            "ballArcApex": max(float(structured_signals.get("ballArcApex") or 0.0), local_features.ballAboveRim),
            "ballThroughHoopLikelihood": max(
                float(structured_signals.get("ballThroughHoopLikelihood") or 0.0),
                local_features.ballThroughHoopLikelihood,
            ),
            "possessionChangeLikelihood": max(
                float(structured_signals.get("possessionChangeLikelihood") or 0.0),
                local_features.possessionChangeLikelihood,
            ),
            "transitionLikelihood": max(
                float(structured_signals.get("transitionLikelihood") or 0.0),
                local_features.transitionSpeedScore,
            ),
            "playerToRimDistance": local_features.playerToRimDistance,
            "ballCarrierSpeed": max(float(structured_signals.get("ballCarrierSpeed") or 0.0), local_features.ballCarrierSpeed),
            "transitionSpeedScore": max(
                float(structured_signals.get("transitionSpeedScore") or 0.0),
                local_features.transitionSpeedScore,
            ),
            "defenderProximityAtShot": max(
                float(structured_signals.get("defenderProximityAtShot") or 0.0),
                local_features.defenderProximityAtShot,
            ),
            "shotReleaseCandidate": max(
                float(structured_signals.get("shotReleaseCandidate") or 0.0),
                local_features.shotReleaseCandidate,
            ),
            "samePlayContinuityScore": max(
                float(structured_signals.get("samePlayContinuityScore") or 0.0),
                local_features.samePlayContinuityScore,
            ),
        }
        observations.append(
            TemporalObservation(
                timestamp_seconds=frame_timestamp,
                structured_signals=local_structured,
                perception_features=dict(summary_features),
            )
        )
    return observations


def _build_temporal_student_observations(
    *,
    action,
    primary_action,
    comparison_action,
    candidate,
    structured_signals: dict[str, object],
    perception: dict[str, object],
    environment: str,
) -> list[TemporalStudentObservation]:
    grouped_frames = _perception_frame_observations(perception)
    summary_features = _perception_summary_features(perception)
    perception_summary = _summarize_perception(perception)
    raw_runtime_outputs = {
        "label": getattr(action, "label", None),
        "canonicalLabel": getattr(action, "canonicalLabel", None),
        "displayLabel": getattr(action, "label", None),
        "confidence": getattr(action, "confidence", None),
        "eventFamily": getattr(action, "eventFamily", None),
        "outcome": getattr(action, "outcome", None),
        "shotSubtype": getattr(action, "shotSubtype", None),
        "modelVersion": getattr(action, "modelVersion", None),
        "topKLabels": [item.model_dump(mode="json") for item in list(getattr(action, "topLabels", []))],
        "rawTopLabels": [item.model_dump(mode="json") for item in list(getattr(action, "rawTopLabels", []))],
        "videoMAE": {
            "modelVersion": getattr(primary_action, "modelVersion", None),
            "topK": [item.model_dump(mode="json") for item in list(getattr(primary_action, "topLabels", []))],
            "topLabel": _top_shadow_label(getattr(primary_action, "topLabels", [])),
        },
        "xclip": {
            "modelVersion": getattr(comparison_action, "modelVersion", None),
            "topK": [item.model_dump(mode="json") for item in list(getattr(comparison_action, "topLabels", []))],
            "topLabel": _top_shadow_label(getattr(comparison_action, "topLabels", [])),
        },
    }
    clip_duration = max(float(candidate.endTime) - float(candidate.startTime), 0.0)
    event_center = round((float(candidate.startTime) + float(candidate.endTime)) / 2.0, 4)
    runtime_base = {
        "sourceKind": "runtime",
        "sourceDomain": environment,
        "sourceSet": "runtime_inference",
        "sourceRef": getattr(candidate, "candidateId", None),
        "humanVerified": False,
        "clipDurationSeconds": clip_duration,
        "eventCenterSeconds": event_center,
        "preRollSeconds": 0.0,
        "postRollSeconds": 0.0,
        "sourceEventCount": 1,
        "wasMerged": False,
        "ballVisible": _perception_visible(perception, "basketball"),
        "hoopVisible": _perception_visible(perception, "rim"),
    }
    if not grouped_frames:
        return [
            TemporalStudentObservation(
                timestamp_seconds=event_center,
                structured_signals=dict(structured_signals),
                perception_features=dict(summary_features),
                detection_features=_temporal_student_detection_features(
                    perception_summary=perception_summary,
                    summary_features=summary_features,
                ),
                tracking_features=_temporal_student_tracking_features(
                    perception_summary=perception_summary,
                    summary_features=summary_features,
                ),
                runtime_features=_temporal_student_runtime_features(
                    runtime_base=runtime_base,
                    raw_runtime_outputs=raw_runtime_outputs,
                ),
            )
        ]

    observations: list[TemporalStudentObservation] = []
    for frame_observations in grouped_frames:
        frame_timestamp = float(frame_observations[0].timestamp_seconds)
        local_features = derive_perception_features(
            [frame_observations],
            ball_labels=("basketball", "ball"),
            rim_labels=("rim", "hoop"),
            player_labels=("player", "players"),
            defender_labels=("defender",),
        )
        local_structured = {
            **dict(structured_signals),
            "ballNearRim": max(float(structured_signals.get("ballNearRim") or 0.0), local_features.ballNearRim),
            "ballAboveRim": max(float(structured_signals.get("ballAboveRim") or 0.0), local_features.ballAboveRim),
            "ballArcApex": max(float(structured_signals.get("ballArcApex") or 0.0), local_features.ballAboveRim),
            "ballThroughHoopLikelihood": max(
                float(structured_signals.get("ballThroughHoopLikelihood") or 0.0),
                local_features.ballThroughHoopLikelihood,
            ),
            "possessionChangeLikelihood": max(
                float(structured_signals.get("possessionChangeLikelihood") or 0.0),
                local_features.possessionChangeLikelihood,
            ),
            "transitionLikelihood": max(
                float(structured_signals.get("transitionLikelihood") or 0.0),
                local_features.transitionSpeedScore,
            ),
            "playerToRimDistance": local_features.playerToRimDistance,
            "ballCarrierSpeed": max(float(structured_signals.get("ballCarrierSpeed") or 0.0), local_features.ballCarrierSpeed),
            "transitionSpeedScore": max(
                float(structured_signals.get("transitionSpeedScore") or 0.0),
                local_features.transitionSpeedScore,
            ),
            "defenderProximityAtShot": max(
                float(structured_signals.get("defenderProximityAtShot") or 0.0),
                local_features.defenderProximityAtShot,
            ),
            "shotReleaseCandidate": max(
                float(structured_signals.get("shotReleaseCandidate") or 0.0),
                local_features.shotReleaseCandidate,
            ),
            "samePlayContinuityScore": max(
                float(structured_signals.get("samePlayContinuityScore") or 0.0),
                local_features.samePlayContinuityScore,
            ),
        }
        observations.append(
            TemporalStudentObservation(
                timestamp_seconds=frame_timestamp,
                structured_signals=local_structured,
                perception_features=dict(summary_features),
                detection_features=_temporal_student_detection_features(
                    perception_summary=perception_summary,
                    summary_features=summary_features,
                ),
                tracking_features=_temporal_student_tracking_features(
                    perception_summary=perception_summary,
                    summary_features=summary_features,
                ),
                runtime_features=_temporal_student_runtime_features(
                    runtime_base=runtime_base,
                    raw_runtime_outputs=raw_runtime_outputs,
                ),
            )
        )
    return observations


def _build_distilled_shadow_snapshot(
    *,
    action,
    primary_action,
    comparison_action,
    structured_signals: dict[str, object],
    candidate,
    perception: dict[str, object],
    environment: str,
) -> dict[str, object]:
    summary_features = _perception_summary_features(perception)
    raw_runtime_outputs = {
        "label": getattr(action, "label", None),
        "canonicalLabel": getattr(action, "canonicalLabel", None),
        "confidence": getattr(action, "confidence", None),
        "eventFamily": getattr(action, "eventFamily", None),
        "outcome": getattr(action, "outcome", None),
        "shotSubtype": getattr(action, "shotSubtype", None),
        "modelVersion": getattr(action, "modelVersion", None),
        "topKLabels": [item.model_dump(mode="json") for item in list(getattr(action, "topLabels", []))],
        "rawTopLabels": [item.model_dump(mode="json") for item in list(getattr(action, "rawTopLabels", []))],
        "videoMAE": {
            "modelVersion": getattr(primary_action, "modelVersion", None),
            "topK": [item.model_dump(mode="json") for item in list(getattr(primary_action, "topLabels", []))],
        },
        "xclip": {
            "modelVersion": getattr(comparison_action, "modelVersion", None),
            "topK": [item.model_dump(mode="json") for item in list(getattr(comparison_action, "topLabels", []))],
        },
    }
    snapshot = {
        "sourceKind": "runtime",
        "sourceDomain": environment,
        "sourceSet": "runtime_inference",
        "sourceRefKind": "candidate_window",
        "sourceRef": getattr(candidate, "candidateId", None),
        "humanVerified": False,
        "ballVisible": _perception_visible(perception, "basketball"),
        "hoopVisible": _perception_visible(perception, "rim"),
        "clipDurationSeconds": max(float(candidate.endTime) - float(candidate.startTime), 0.0),
        "eventCenterSeconds": round((float(candidate.startTime) + float(candidate.endTime)) / 2.0, 4),
        "preRollSeconds": 0.0,
        "postRollSeconds": 0.0,
        "sourceEventCount": 1,
        "wasMerged": False,
        "priorityScore": float(getattr(candidate, "score", 0.0) or 0.0),
        "structuredSignals": {
            **dict(structured_signals),
            "basketballConfidence": summary_features.get("basketballConfidence", 0.0),
            "rimConfidence": summary_features.get("rimConfidence", 0.0),
            "playerCount": summary_features.get("playerCount", 0.0),
            "trackedPlayerCount": summary_features.get("trackedPlayerCount", 0.0),
            "trackedBallConfidence": summary_features.get("trackedBallConfidence", 0.0),
        },
        "rawRuntimeOutputs": raw_runtime_outputs,
        "comparisonRawTopLabels": [item.model_dump(mode="json") for item in list(getattr(comparison_action, "rawTopLabels", []))],
        "rawTopLabels": [item.model_dump(mode="json") for item in list(getattr(action, "rawTopLabels", []))],
    }
    return snapshot


def _load_temporal_shadow_bundle(path: Path) -> TemporalEncoderBundle | TemporalStudentBundle | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    schema_version = str(payload.get("schemaVersion") or "")
    feature_schema_version = str(payload.get("featureSchemaVersion") or "")
    if "temporal-student" in schema_version or "temporal-student" in feature_schema_version:
        return get_temporal_student_bundle(str(path))
    return get_temporal_encoder_bundle(str(path))


def _resolve_trace_fields(request: InferenceJobRequest, request_id: str) -> tuple[str, str]:
    trace_id = request.traceId or request_id
    upload_trace_id = request.uploadTraceId or trace_id
    return trace_id, upload_trace_id


def _summarize_perception(perception: dict[str, object]) -> dict[str, object]:
    detection_counts = perception.get("detectionCounts")
    track_counts = perception.get("trackCounts")
    return {
        "sampledFrameCount": perception.get("sampledFrameCount"),
        "frameWidth": perception.get("frameWidth"),
        "frameHeight": perception.get("frameHeight"),
        "detectionCounts": detection_counts if isinstance(detection_counts, dict) else {},
        "trackCounts": track_counts if isinstance(track_counts, dict) else {},
        "primaryBallTrackId": perception.get("primaryBallTrackId"),
        "primaryRimTrackId": perception.get("primaryRimTrackId"),
        "overlayPaths": perception.get("overlayPaths") if isinstance(perception.get("overlayPaths"), list) else [],
        "failureReason": perception.get("failureReason"),
    }


def _temporal_shadow_payload(prediction) -> dict[str, object]:
    metadata = dict(getattr(prediction, "metadata", {}) or {})
    return {
        "modelVersion": getattr(prediction, "modelVersion", None),
        "label": getattr(prediction, "label", None),
        "canonicalLabel": getattr(prediction, "canonicalLabel", None),
        "confidence": getattr(prediction, "confidence", None),
        "eventFamily": getattr(prediction, "eventFamily", None),
        "shotSubtype": getattr(prediction, "shotSubtype", None),
        "outcome": getattr(prediction, "outcome", None),
        "confidenceBeforeMapping": getattr(prediction, "confidenceBeforeMapping", None),
        "confidenceAfterMapping": getattr(prediction, "confidenceAfterMapping", None),
        "eventFamilyConfidenceBeforeMapping": getattr(prediction, "eventFamilyConfidenceBeforeMapping", None),
        "eventFamilyConfidenceAfterMapping": getattr(prediction, "eventFamilyConfidenceAfterMapping", None),
        "shotSubtypeConfidenceBeforeMapping": getattr(prediction, "shotSubtypeConfidenceBeforeMapping", None),
        "shotSubtypeConfidenceAfterMapping": getattr(prediction, "shotSubtypeConfidenceAfterMapping", None),
        "outcomeConfidenceBeforeMapping": getattr(prediction, "outcomeConfidenceBeforeMapping", None),
        "outcomeConfidenceAfterMapping": getattr(prediction, "outcomeConfidenceAfterMapping", None),
        "isUncertain": getattr(prediction, "isUncertain", None),
        **metadata,
    }


def _distilled_shadow_payload(prediction: DistilledClipEncoderPrediction) -> dict[str, object]:
    metadata = dict(prediction.metadata or {})
    return {
        "modelVersion": prediction.model_version,
        "label": prediction.display_label,
        "canonicalLabel": prediction.canonical_label,
        "confidence": prediction.confidence_after_mapping,
        "eventFamily": prediction.event_family,
        "shotSubtype": prediction.shot_subtype,
        "outcome": prediction.outcome,
        "confidenceBeforeMapping": prediction.confidence_before_mapping,
        "confidenceAfterMapping": prediction.confidence_after_mapping,
        "eventFamilyConfidenceBeforeMapping": prediction.event_family_confidence_before_mapping,
        "eventFamilyConfidenceAfterMapping": prediction.event_family_confidence_after_mapping,
        "shotSubtypeConfidenceBeforeMapping": prediction.shot_subtype_confidence_before_mapping,
        "shotSubtypeConfidenceAfterMapping": prediction.shot_subtype_confidence_after_mapping,
        "outcomeConfidenceBeforeMapping": prediction.outcome_confidence_before_mapping,
        "outcomeConfidenceAfterMapping": prediction.outcome_confidence_after_mapping,
        "isUncertain": prediction.is_uncertain,
        "rawHeadPredictions": {
            key: value.as_dict() for key, value in prediction.raw_head_predictions.items()
        },
        **metadata,
    }


def _perception_frame_observations(perception: dict[str, object]) -> list[list[PerceptionObservation]]:
    frames = perception.get("frames")
    if not isinstance(frames, list):
        return []
    grouped: list[list[PerceptionObservation]] = []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        detections = frame.get("detections")
        if not isinstance(detections, list):
            continue
        timestamp_seconds = float(frame.get("timestampSeconds") or 0.0)
        observations: list[PerceptionObservation] = []
        for detection in detections:
            if not isinstance(detection, dict):
                continue
            label = str(detection.get("label") or "").strip()
            box = detection.get("box")
            if not label or not isinstance(box, dict):
                continue
            observations.append(
                PerceptionObservation(
                    label=label,
                    bbox=(
                        float(box.get("x1") or 0.0),
                        float(box.get("y1") or 0.0),
                        float(box.get("x2") or 0.0),
                        float(box.get("y2") or 0.0),
                    ),
                    confidence=float(detection.get("confidence") or 0.0),
                    timestamp_seconds=timestamp_seconds,
                    track_id=detection.get("trackId"),
                )
            )
        if observations:
            grouped.append(observations)
    return grouped


def _perception_summary_features(perception: dict[str, object]) -> dict[str, float]:
    detection_counts = perception.get("detectionCounts")
    detection_counts = detection_counts if isinstance(detection_counts, dict) else {}
    track_counts = perception.get("trackCounts")
    track_counts = track_counts if isinstance(track_counts, dict) else {}
    tracks = perception.get("tracks")
    tracks = tracks if isinstance(tracks, list) else []
    return {
        "basketballConfidence": _primary_detection_confidence(perception, "basketball"),
        "rimConfidence": _primary_detection_confidence(perception, "rim"),
        "playerCount": float(detection_counts.get("player", 0) or 0.0),
        "trackedPlayerCount": float(track_counts.get("player", 0) or 0.0),
        "trackedBallConfidence": _track_average_confidence(tracks, perception.get("primaryBallTrackId")),
    }


def _temporal_student_detection_features(
    *,
    perception_summary: dict[str, object],
    summary_features: dict[str, float],
) -> dict[str, object]:
    detection_counts = perception_summary.get("detectionCounts")
    detection_counts = detection_counts if isinstance(detection_counts, dict) else {}
    frame_count = max(float(perception_summary.get("sampledFrameCount") or 0.0), 1.0)
    total_detections = sum(float(value or 0.0) for value in detection_counts.values())
    return {
        "ballVisible": bool(detection_counts.get("basketball", 0)),
        "hoopVisible": bool(detection_counts.get("rim", 0)),
        "ballDetectionConfidence": summary_features.get("basketballConfidence", 0.0),
        "hoopDetectionConfidence": summary_features.get("rimConfidence", 0.0),
        "ballTrackCount": float(detection_counts.get("basketball", 0) or 0.0),
        "rimTrackCount": float(detection_counts.get("rim", 0) or 0.0),
        "detectionDensity": round(total_detections / frame_count, 4),
    }


def _temporal_student_tracking_features(
    *,
    perception_summary: dict[str, object],
    summary_features: dict[str, float],
) -> dict[str, object]:
    track_counts = perception_summary.get("trackCounts")
    track_counts = track_counts if isinstance(track_counts, dict) else {}
    total_tracks = sum(float(value or 0.0) for value in track_counts.values())
    return {
        "playerTrackCount": float(track_counts.get("player", 0) or 0.0),
        "trackedPlayerCount": summary_features.get("trackedPlayerCount", 0.0),
        "trackedBallConfidence": summary_features.get("trackedBallConfidence", 0.0),
        "trackingContinuity": 1.0 if total_tracks > 0 else 0.0,
        "trackingDensity": round(total_tracks / max(len(track_counts), 1), 4),
        "ballTrackCount": float(track_counts.get("basketball", 0) or 0.0),
        "rimTrackCount": float(track_counts.get("rim", 0) or 0.0),
    }


def _temporal_student_runtime_features(
    *,
    runtime_base: dict[str, object],
    raw_runtime_outputs: dict[str, object],
) -> dict[str, object]:
    return {
        **runtime_base,
        "label": raw_runtime_outputs.get("label"),
        "canonicalLabel": raw_runtime_outputs.get("canonicalLabel"),
        "displayLabel": raw_runtime_outputs.get("displayLabel"),
        "confidence": raw_runtime_outputs.get("confidence"),
        "eventFamily": raw_runtime_outputs.get("eventFamily"),
        "outcome": raw_runtime_outputs.get("outcome"),
        "shotSubtype": raw_runtime_outputs.get("shotSubtype"),
        "topCount": len(raw_runtime_outputs.get("topKLabels") or []),
        "videoMAE": raw_runtime_outputs.get("videoMAE"),
        "xclip": raw_runtime_outputs.get("xclip"),
    }


def _top_shadow_label(labels: object) -> str | None:
    if not isinstance(labels, list) or not labels:
        return None
    first = labels[0]
    if hasattr(first, "label"):
        return getattr(first, "label")
    if isinstance(first, dict):
        return str(first.get("label") or "") or None
    return None


def _primary_detection_confidence(perception: dict[str, object], label: str) -> float:
    frames = perception.get("frames")
    if not isinstance(frames, list):
        return 0.0
    wanted = label.lower()
    best = 0.0
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        detections = frame.get("detections")
        if not isinstance(detections, list):
            continue
        for detection in detections:
            if not isinstance(detection, dict):
                continue
            if str(detection.get("label") or "").lower() != wanted:
                continue
            best = max(best, float(detection.get("confidence") or 0.0))
    return round(best, 4)


def _track_average_confidence(tracks: list[object], track_id: object) -> float:
    if track_id is None:
        return 0.0
    wanted = str(track_id)
    for track in tracks:
        if not isinstance(track, dict):
            continue
        if str(track.get("trackId") or "") != wanted:
            continue
        return round(float(track.get("averageConfidence") or 0.0), 4)
    return 0.0


def _event_subtype_for_family(event_family: str, shot_subtype: str | None, outcome: str) -> str | None:
    if event_family == "defensive_event":
        return "block" if outcome == "blocked" else None
    if event_family == "turnover":
        return "steal"
    if event_family == "transition":
        return "fast_break"
    return shot_subtype


def _perception_visible(perception: dict[str, object], label: str) -> bool | None:
    detection_counts = perception.get("detectionCounts")
    track_counts = perception.get("trackCounts")
    if isinstance(detection_counts, dict) and detection_counts.get(label):
        return True
    if isinstance(track_counts, dict) and track_counts.get(label):
        return True
    return False


def _blend_event_family(structured_action, runtime_prediction: RuntimeFusionPrediction) -> str:
    structured_family = getattr(structured_action, "eventFamily", None) or "other"
    structured_confidence = float(getattr(structured_action, "eventFamilyConfidenceAfterMapping", 0.0) or 0.0)
    runtime_family = runtime_prediction.event_family
    runtime_confidence = float(runtime_prediction.event_family_confidence_after_mapping or 0.0)
    if runtime_family in {"other", structured_family}:
        return structured_family if structured_family != "other" else runtime_family
    if runtime_confidence >= max(structured_confidence + 0.05, 0.58):
        return runtime_family
    return structured_family


def _blend_outcome(structured_action, runtime_prediction: RuntimeFusionPrediction, event_family: str) -> str:
    if event_family == "defensive_event":
        if runtime_prediction.outcome == "blocked":
            return "blocked"
        structured_outcome = getattr(structured_action, "outcome", None) or "uncertain"
        return "blocked" if structured_outcome == "blocked" else "uncertain"
    if event_family != "shot_attempt":
        return "uncertain"

    structured_outcome = getattr(structured_action, "outcome", None) or "uncertain"
    structured_confidence = float(getattr(structured_action, "outcomeConfidenceAfterMapping", 0.0) or 0.0)
    runtime_outcome = runtime_prediction.outcome
    runtime_confidence = float(runtime_prediction.outcome_confidence_after_mapping or 0.0)

    if structured_outcome == "missed" and runtime_outcome == "made" and runtime_confidence < 0.85:
        return structured_outcome
    if runtime_outcome != "uncertain" and runtime_confidence >= max(structured_confidence + 0.04, 0.62):
        return runtime_outcome
    return structured_outcome


def _blend_shot_subtype(structured_action, runtime_prediction: RuntimeFusionPrediction, event_family: str) -> str | None:
    if event_family != "shot_attempt":
        return None
    structured_subtype = getattr(structured_action, "shotSubtype", None)
    structured_confidence = float(getattr(structured_action, "shotSubtypeConfidenceAfterMapping", 0.0) or 0.0)
    runtime_subtype = runtime_prediction.shot_subtype
    runtime_confidence = float(runtime_prediction.shot_subtype_confidence_after_mapping or 0.0)
    if runtime_subtype and runtime_confidence >= max(structured_confidence + 0.05, 0.58):
        return runtime_subtype
    return structured_subtype


def _blend_display_label(event_family: str, outcome: str, shot_subtype: str | None) -> tuple[str, str]:
    if event_family == "turnover":
        return "steal", "Steal"
    if event_family == "transition":
        return "fast break", "Fast Break"
    if event_family == "defensive_event":
        return ("block", "Block") if outcome == "blocked" else ("uncertain", "Highlight")
    if event_family != "shot_attempt":
        return "uncertain", "Highlight"
    if outcome == "missed":
        return "miss", "Highlight"
    if outcome == "blocked":
        return "block", "Block"
    if shot_subtype == "dunk" and outcome == "made":
        return "dunk", "Dunk"
    if shot_subtype == "layup" and outcome == "made":
        return "layup", "Layup"
    if shot_subtype == "three" and outcome == "made":
        return "three", "Three Pointer"
    if shot_subtype == "putback" and outcome == "made":
        return "putback", "Made Shot"
    if outcome == "made":
        return shot_subtype or "jumper", "Made Shot"
    return shot_subtype or "uncertain", "Highlight"


def _blend_confidence(structured_value, runtime_value, *, present: bool) -> float | None:
    if not present:
        return None
    return max(float(structured_value or 0.0), float(runtime_value or 0.0))


def _blend_display_confidence(
    *,
    display_label: str,
    family_after: float,
    shot_after: float | None,
    outcome_after: float,
    is_uncertain: bool,
) -> float:
    shot_confidence = float(shot_after or 0.0)
    if display_label in {"Steal", "Fast Break"}:
        confidence = family_after
    elif display_label == "Block":
        confidence = max(family_after, outcome_after)
    elif display_label in {"Dunk", "Layup", "Three Pointer"}:
        confidence = max(family_after, shot_confidence)
    elif display_label == "Made Shot":
        confidence = min(max(family_after, shot_confidence), max(outcome_after, 0.3))
    else:
        confidence = max(family_after, shot_confidence, outcome_after)
    if is_uncertain and display_label == "Highlight":
        confidence = min(confidence, 0.46)
    return round(min(max(confidence, 0.0), 1.0), 4)


def _runtime_metadata_from_clip(clip, key: str):
    metadata = getattr(clip, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    if metadata.get(key) is not None:
        return metadata.get(key)
    action_metadata = metadata.get("action_metadata")
    if isinstance(action_metadata, dict):
        return action_metadata.get(key)
    return None
