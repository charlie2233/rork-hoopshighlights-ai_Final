from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Sequence

from .model_registry import EmbeddingRerankResult, ModelRegistry, default_model_registry
from .models import (
    CandidateWindow,
    CloudClip,
    CloudClipProvenance,
    CloudRerankEvidence,
    CloudRerankTextMatch,
    CloudClipScores,
    CloudLabelScore,
    CloudRawLabelScore,
    DetectionPipelineSummary,
    DetectionStageProvenance,
    clamp,
)
from .taxonomy import BasketballTaxonomy, TaxonomyMapping, load_default_taxonomy


PIPELINE_VERSION = "detection-pipeline-v2"


@dataclass(frozen=True)
class DetectionPipelineResult:
    clips: list[CloudClip]
    summary: DetectionPipelineSummary


def run_staged_detection_pipeline(
    windows: Sequence[CandidateWindow],
    *,
    registry: ModelRegistry | None = None,
    taxonomy: BasketballTaxonomy | None = None,
    clip_limit: int,
    source_identity: dict[str, str] | None = None,
) -> DetectionPipelineResult:
    resolved_registry = registry or default_model_registry()
    resolved_taxonomy = taxonomy or load_default_taxonomy()
    prompts = _taxonomy_prompt_labels(resolved_taxonomy)
    identity = _clean_source_identity(source_identity)
    reranked = resolved_registry.embedding.rerank(windows, prompts)
    rerank_by_index = {item.index: item for item in reranked}
    ordered_indexes = [item.index for item in reranked] or list(range(len(windows)))
    fallback_reasons = sorted({item.fallback_reason for item in reranked if item.fallback_reason})

    clips: list[CloudClip] = []
    for output_rank, index in enumerate(ordered_indexes[: max(0, clip_limit)], start=1):
        if index < 0 or index >= len(windows):
            continue
        window = windows[index]
        classification = resolved_registry.classifier.classify(window)
        mapping = resolved_taxonomy.map_label(classification.raw_label, classification.confidence)
        rerank = rerank_by_index.get(index)
        clips.append(
            _enrich_classified_clip(
                classification.clip,
                mapping=mapping,
                proposal_index=index,
                output_rank=output_rank,
                window=window,
                rerank=rerank,
                classifier_model_id=classification.model.model_id,
                classifier_model_version=classification.model.version,
                classifier_adapter=classification.model.adapter,
                classifier_top_labels=classification.top_labels,
                source_identity=identity,
            )
        )

    summary = DetectionPipelineSummary(
        pipelineVersion=PIPELINE_VERSION,
        stages=["proposal", "embedding_rerank", "classifier", "merge"],
        proposalCount=len(windows),
        rerankedCount=len(reranked),
        classifiedCount=len(clips),
        mergedCandidateCount=len(clips),
        models=resolved_registry.model_versions(),
        taxonomyVersion=resolved_taxonomy.schema_version,
        fallbackUsed=bool(fallback_reasons),
        fallbackReasons=fallback_reasons,
    )
    return DetectionPipelineResult(clips=clips, summary=summary)


def annotate_external_clips(
    clips: Sequence[CloudClip],
    *,
    taxonomy: BasketballTaxonomy | None = None,
    source: str,
    model_version: str,
    source_identity: dict[str, str] | None = None,
) -> DetectionPipelineResult:
    resolved_taxonomy = taxonomy or load_default_taxonomy()
    identity = _clean_source_identity(source_identity)
    annotated: list[CloudClip] = []
    for rank, clip in enumerate(clips, start=1):
        mapping = resolved_taxonomy.map_label(clip.label, clip.confidence)
        proposal_score = _clip_proposal_score(clip)
        classifier_score = clamp(clip.confidence, 0.0, 1.0)
        final_score = clamp((proposal_score * 0.34) + (clip.combinedScore * 0.36) + (classifier_score * 0.3), 0.0, 1.0)
        annotated.append(
            _apply_taxonomy(
                clip,
                mapping=mapping,
                confidence=final_score,
                rank=rank,
                top_labels=((clip.label, clip.confidence),),
                raw_model_version=model_version,
                provenance=CloudClipProvenance(
                    proposal=DetectionStageProvenance(
                        stage="proposal",
                        source=source,
                        status="applied",
                        score=proposal_score,
                        rank=rank,
                        details={
                            "startTime": clip.startTime,
                            "endTime": clip.endTime,
                            "eventCenter": clip.eventCenter,
                        },
                    ),
                    embeddingRerank=DetectionStageProvenance(
                        stage="embedding_rerank",
                        source="external_provider",
                        status="skipped",
                        modelVersion=model_version,
                        score=clip.rankScore,
                        rank=rank,
                    ),
                    classifier=DetectionStageProvenance(
                        stage="classifier",
                        source=source,
                        status="applied",
                        modelVersion=model_version,
                        rawLabel=clip.label,
                        score=clip.confidence,
                    ),
                    merge=DetectionStageProvenance(
                        stage="merge",
                        source="temporal_merge",
                        status="applied",
                        score=final_score,
                        rank=rank,
                    ),
                    taxonomy=DetectionStageProvenance(
                        stage="taxonomy",
                        source=resolved_taxonomy.schema_version,
                        status="applied",
                        rawLabel=clip.label,
                        details={"matchedAlias": mapping.matched_alias},
                    ),
                ),
                scores=CloudClipScores(
                    proposalScore=proposal_score,
                    embeddingScore=clip.rankScore or clip.combinedScore,
                    classifierScore=classifier_score,
                    mergeScore=final_score,
                    finalScore=final_score,
                ),
                source_identity=identity,
            )
        )

    summary = DetectionPipelineSummary(
        pipelineVersion=PIPELINE_VERSION,
        stages=["proposal", "embedding_rerank", "classifier", "merge"],
        proposalCount=len(clips),
        rerankedCount=len(clips),
        classifiedCount=len(clips),
        mergedCandidateCount=len(clips),
        models={"classifier": model_version, "embedding": "external_provider"},
        taxonomyVersion=resolved_taxonomy.schema_version,
        fallbackUsed=False,
        fallbackReasons=[],
    )
    return DetectionPipelineResult(clips=annotated, summary=summary)


def pipeline_summary_for_clips(
    clips: Sequence[CloudClip],
    *,
    taxonomy_version: str,
    model_version: str,
    fallback_reason: str | None = None,
) -> DetectionPipelineSummary:
    return DetectionPipelineSummary(
        pipelineVersion=PIPELINE_VERSION,
        stages=["proposal", "embedding_rerank", "classifier", "merge"],
        proposalCount=len(clips),
        rerankedCount=len(clips),
        classifiedCount=len(clips),
        mergedCandidateCount=len(clips),
        models={"classifier": model_version, "embedding": "not_available"},
        taxonomyVersion=taxonomy_version,
        fallbackUsed=fallback_reason is not None,
        fallbackReasons=[fallback_reason] if fallback_reason else [],
    )


def with_merge_provenance(clip: CloudClip, *, rank: int, merged_from: int = 1) -> CloudClip:
    provenance = clip.provenance
    if provenance is None:
        return clip
    final_score = clip.scores.finalScore if clip.scores else clip.combinedScore
    return clip.model_copy(
        update={
            "pipelineStage": "merged_candidate",
            "provenance": provenance.model_copy(
                update={
                    "merge": DetectionStageProvenance(
                        stage="merge",
                        source="temporal_merge",
                        status="applied",
                        score=final_score,
                        rank=rank,
                        details={"mergedFrom": merged_from},
                    )
                }
            ),
        }
    )


def _enrich_classified_clip(
    clip: CloudClip,
    *,
    mapping: TaxonomyMapping,
    proposal_index: int,
    output_rank: int,
    window: CandidateWindow,
    rerank: EmbeddingRerankResult | None,
    classifier_model_id: str,
    classifier_model_version: str,
    classifier_adapter: str,
    classifier_top_labels: tuple[tuple[str, float], ...],
    source_identity: dict[str, str],
) -> CloudClip:
    proposal_score = clamp(window.combined_score, 0.0, 1.0)
    embedding_score = rerank.score if rerank is not None else proposal_score
    classifier_score = clamp(clip.confidence, 0.0, 1.0)
    final_score = round(
        clamp((proposal_score * 0.28) + (embedding_score * 0.28) + (classifier_score * 0.34) + (window.event_context_score * 0.1), 0.0, 1.0),
        4,
    )
    return _apply_taxonomy(
        clip,
        mapping=mapping,
        confidence=final_score,
        rank=output_rank,
        top_labels=classifier_top_labels,
        raw_model_version=classifier_model_version,
        source_identity=source_identity,
        provenance=CloudClipProvenance(
            proposal=DetectionStageProvenance(
                stage="proposal",
                source="native_audio_visual_windows",
                status="applied",
                score=proposal_score,
                rank=proposal_index + 1,
                details={
                    "startTime": round(window.start_time, 3),
                    "endTime": round(window.end_time, 3),
                    "peakTime": round(window.peak_time, 3),
                    "eventContextScore": round(window.event_context_score, 4),
                },
            ),
            embeddingRerank=DetectionStageProvenance(
                stage="embedding_rerank",
                source="clip_like_semantic_adapter",
                status="fallback" if rerank and rerank.fallback_reason else "applied",
                modelId=rerank.model.model_id if rerank else None,
                modelVersion=rerank.model.version if rerank else None,
                adapter=rerank.model.adapter if rerank else None,
                score=embedding_score,
                rank=rerank.rank if rerank else output_rank,
                details={
                    "promptLabel": rerank.prompt_label if rerank else mapping.product_label,
                    "latencyMs": rerank.latency_ms if rerank else None,
                    "fallbackReason": rerank.fallback_reason if rerank else None,
                },
            ),
            classifier=DetectionStageProvenance(
                stage="classifier",
                source="baseline_video_classifier",
                status="applied",
                modelId=classifier_model_id,
                modelVersion=classifier_model_version,
                adapter=classifier_adapter,
                rawLabel=clip.label,
                score=classifier_score,
            ),
            merge=DetectionStageProvenance(
                stage="merge",
                source="temporal_merge",
                status="applied",
                score=final_score,
                rank=output_rank,
            ),
            taxonomy=DetectionStageProvenance(
                stage="taxonomy",
                source=mapping.taxonomy_version,
                status="applied",
                rawLabel=clip.label,
                details={"matchedAlias": mapping.matched_alias},
            ),
        ),
        scores=CloudClipScores(
            proposalScore=proposal_score,
            embeddingScore=embedding_score,
            classifierScore=classifier_score,
            mergeScore=final_score,
            finalScore=final_score,
        ),
    )


def _apply_taxonomy(
    clip: CloudClip,
    *,
    mapping: TaxonomyMapping,
    confidence: float,
    rank: int,
    top_labels: tuple[tuple[str, float], ...],
    raw_model_version: str,
    source_identity: dict[str, str],
    provenance: CloudClipProvenance,
    scores: CloudClipScores,
) -> CloudClip:
    mapped_confidence = round(clamp(confidence * mapping.confidence_multiplier, 0.0, 1.0), 4)
    make_miss = {"made": "make", "missed": "miss"}.get(mapping.outcome, "unknown")
    evidence = _rerank_evidence_for_clip(
        mapping=mapping,
        provenance=provenance,
        scores=scores,
        source_identity=source_identity,
    )
    candidate_id = clip.id or _stable_candidate_id(source_identity, clip=clip, rank=rank, label=mapping.canonical_label)
    return clip.model_copy(
        update={
            "id": candidate_id,
            "clipId": clip.clipId or candidate_id,
            "confidence": mapped_confidence,
            "label": mapping.product_label,
            "action": mapping.product_label,
            "canonicalLabel": mapping.canonical_label,
            "eventFamily": mapping.event_family,
            "eventSubtype": mapping.event_subtype,
            "shotSubtype": mapping.shot_subtype,
            "outcome": mapping.outcome,
            "confidenceBeforeMapping": clip.confidence,
            "confidenceAfterMapping": mapped_confidence,
            "eventFamilyConfidenceBeforeMapping": clip.confidence,
            "eventFamilyConfidenceAfterMapping": mapped_confidence,
            "shotSubtypeConfidenceBeforeMapping": clip.confidence if mapping.shot_subtype else None,
            "shotSubtypeConfidenceAfterMapping": mapped_confidence if mapping.shot_subtype else None,
            "outcomeConfidenceBeforeMapping": clip.confidence,
            "outcomeConfidenceAfterMapping": mapped_confidence,
            "isUncertain": mapping.outcome == "uncertain" or mapped_confidence < 0.62,
            "promptSetVersion": mapping.taxonomy_version,
            "eventType": mapping.event_family,
            "shotType": mapping.shot_subtype,
            "makeMiss": make_miss,
            "rankScore": scores.finalScore,
            "reviewState": clip.reviewState or "unreviewed",
            "topLabels": [
                CloudLabelScore(label=label, confidence=round(clamp(score, 0.0, 1.0), 4), rawLabel=label, modelVersion=raw_model_version)
                for label, score in top_labels[:5]
            ],
            "rawTopLabels": [
                CloudRawLabelScore(
                    rawLabel=label,
                    confidence=round(clamp(score, 0.0, 1.0), 4),
                    canonicalLabel=load_default_taxonomy().map_label(label, score).canonical_label,
                    modelVersion=raw_model_version,
                )
                for label, score in top_labels[:5]
            ],
            "pipelineStage": "merged_candidate",
            "pipelineVersion": PIPELINE_VERSION,
            "provenance": provenance,
            "scores": scores,
            "rerankEvidence": evidence,
            "shouldAutoKeep": clip.shouldAutoKeep and mapped_confidence >= 0.58,
            "shouldEnableSlowMotion": clip.shouldEnableSlowMotion and mapped_confidence >= 0.58,
        }
    )


def _taxonomy_prompt_labels(taxonomy: BasketballTaxonomy) -> list[str]:
    labels = sorted(set(taxonomy.prompt_labels()))
    return labels or ["Highlight"]


def _clip_proposal_score(clip: CloudClip) -> float:
    return round(clamp((clip.combinedScore * 0.5) + (clip.motionScore * 0.2) + (clip.visualScore * 0.2) + (clip.audioScore * 0.1), 0.0, 1.0), 4)


def _rerank_evidence_for_clip(
    *,
    mapping: TaxonomyMapping,
    provenance: CloudClipProvenance,
    scores: CloudClipScores,
    source_identity: dict[str, str],
) -> CloudRerankEvidence:
    rerank = provenance.embeddingRerank
    prompt_label = mapping.product_label
    fallback_reason: str | None = None
    provider = "not_available"
    model = "not_available"
    adapter: str | None = None
    kill_switch = False
    latency_ms: int | None = None
    if rerank is not None:
        provider = rerank.adapter or rerank.source
        model = rerank.modelVersion or rerank.modelId or rerank.source
        adapter = rerank.adapter
        prompt_label = str(rerank.details.get("promptLabel") or mapping.product_label)
        latency_value = rerank.details.get("latencyMs")
        latency_ms = latency_value if isinstance(latency_value, int) else None
        fallback_reason = _fallback_reason_for_stage(rerank)
        kill_switch = rerank.status in {"fallback", "skipped", "unavailable"}
    return CloudRerankEvidence(
        provider=provider,
        model=model,
        adapter=adapter,
        promptVersion=mapping.taxonomy_version,
        killSwitch=kill_switch,
        embeddingScore=scores.embeddingScore,
        textMatches=[
            CloudRerankTextMatch(label=prompt_label, score=scores.embeddingScore, promptType="basketball_taxonomy"),
        ],
        errorBuckets=_candidate_error_buckets(mapping, provenance),
        sourceIdentity=source_identity,
        latencyMs=latency_ms,
        fallbackReason=fallback_reason,
    )


def _fallback_reason_for_stage(stage: DetectionStageProvenance) -> str | None:
    if stage.status == "applied":
        return None
    if isinstance(stage.details.get("fallbackReason"), str):
        return str(stage.details["fallbackReason"])
    return stage.status


def _candidate_error_buckets(mapping: TaxonomyMapping, provenance: CloudClipProvenance) -> list[str]:
    buckets: list[str] = []
    proposal = provenance.proposal
    details = proposal.details
    start = _coerce_float(details.get("startTime"))
    end = _coerce_float(details.get("endTime"))
    peak = _coerce_float(details.get("peakTime") or details.get("eventCenter"))
    if start is not None and end is not None and peak is not None:
        lead = peak - start
        follow = end - peak
        if lead < 0.6 or follow < 0.5:
            buckets.append("bad_window")
        else:
            buckets.append("boundary_ok")
    if mapping.event_family == "reaction":
        buckets.append("crowd_reaction")
    if mapping.outcome == "uncertain":
        buckets.append("outcome_uncertain")
    return buckets or ["unbucketed"]


def _stable_candidate_id(source_identity: dict[str, str], *, clip: CloudClip, rank: int, label: str) -> str:
    source_key = (
        source_identity.get("jobId")
        or source_identity.get("assetId")
        or source_identity.get("sourceObjectKey")
        or source_identity.get("storageKey")
        or "analysis"
    )
    raw = f"{source_key}|{rank}|{clip.startTime:.3f}|{clip.endTime:.3f}|{label}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"clip_{digest}"


def _clean_source_identity(source_identity: dict[str, str] | None) -> dict[str, str]:
    if not source_identity:
        return {}
    safe_keys = {
        "jobId",
        "requestId",
        "traceId",
        "uploadTraceId",
        "inferenceAttemptId",
        "installId",
        "assetId",
        "storageKey",
        "sourceObjectKey",
        "filename",
    }
    cleaned: dict[str, str] = {}
    for key in safe_keys:
        value = source_identity.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            cleaned[key] = text[:512]
    return cleaned


def _coerce_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
