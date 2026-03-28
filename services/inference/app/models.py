from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InferenceStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class InferenceJobRequest(APIModel):
    jobId: str = Field(min_length=1, max_length=128)
    requestId: Optional[str] = None
    schemaVersion: Optional[str] = None
    uploadTraceId: Optional[str] = None
    inferenceAttemptId: Optional[str] = None
    sourceObjectKey: Optional[str] = None
    sourceUrl: Optional[AnyHttpUrl] = None
    callbackUrl: AnyHttpUrl
    modelVersion: Optional[str] = None
    callbackSecret: Optional[str] = Field(default=None, min_length=8, max_length=256)
    resultObjectKey: Optional[str] = None
    installId: Optional[str] = None
    appVersion: Optional[str] = None
    analysisVersion: Optional[str] = None
    requestedModel: Optional[str] = None
    traceId: Optional[str] = None

    @model_validator(mode="after")
    def validate_source(self) -> "InferenceJobRequest":
        if not self.sourceObjectKey and not self.sourceUrl:
            raise ValueError("sourceObjectKey or sourceUrl is required")
        return self


class CandidateWindow(APIModel):
    candidateId: str
    startTime: float = Field(ge=0.0)
    endTime: float = Field(gt=0.0)
    score: float = Field(ge=0.0, le=1.0)
    source: str = "heuristic"
    reason: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LabelScore(APIModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    rawLabel: Optional[str] = None
    modelVersion: Optional[str] = None


class RawLabelScore(APIModel):
    rawLabel: str
    confidence: float = Field(ge=0.0, le=1.0)
    canonicalLabel: Optional[str] = None
    modelVersion: Optional[str] = None


class ActionPrediction(APIModel):
    label: str
    canonicalLabel: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    modelVersion: str
    detectionMethod: str = "model"
    failureReason: Optional[str] = None
    topLabels: list[LabelScore] = Field(default_factory=list)
    rawTopLabels: list[RawLabelScore] = Field(default_factory=list)
    eventFamily: Optional[str] = None
    eventSubtype: Optional[str] = None
    shotSubtype: Optional[str] = None
    outcome: Optional[str] = None
    confidenceBeforeMapping: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidenceAfterMapping: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    isUncertain: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventPrediction(APIModel):
    eventFamily: str
    eventSubtype: Optional[str] = None
    shotSubtype: Optional[str] = None
    outcome: str
    eventType: str
    shotType: str
    makeMiss: str
    confidence: float = Field(ge=0.0, le=1.0)
    confidenceBeforeMapping: float = Field(ge=0.0, le=1.0)
    confidenceAfterMapping: float = Field(ge=0.0, le=1.0)
    rankScore: float = Field(ge=0.0, le=1.0)
    isUncertain: bool = False
    shouldAutoKeep: bool = True
    shouldEnableSlowMotion: bool = False
    reviewState: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RankedClip(APIModel):
    clipId: str
    startTime: float = Field(ge=0.0)
    endTime: float = Field(gt=0.0)
    clipDurationSeconds: float = Field(ge=0.0)
    eventCenterSeconds: float = Field(ge=0.0)
    preRollSeconds: float = Field(ge=0.0)
    postRollSeconds: float = Field(ge=0.0)
    windowPolicyVersion: str
    wasMerged: bool = False
    sourceEventCount: int = Field(default=1, ge=1)
    confidence: float = Field(ge=0.0, le=1.0)
    resultConfidence: float = Field(ge=0.0, le=1.0)
    label: str
    action: str
    canonicalLabel: Optional[str] = None
    eventFamily: Optional[str] = None
    eventSubtype: Optional[str] = None
    shotSubtype: Optional[str] = None
    outcome: Optional[str] = None
    eventType: str
    shotType: str
    makeMiss: str
    confidenceBeforeMapping: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidenceAfterMapping: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    isUncertain: bool = False
    audioScore: float = Field(ge=0.0, le=1.0)
    visualScore: float = Field(ge=0.0, le=1.0)
    motionScore: float = Field(ge=0.0, le=1.0)
    combinedScore: float = Field(ge=0.0, le=1.0)
    rankScore: float = Field(ge=0.0, le=1.0)
    detectionMethod: str = "model"
    shouldAutoKeep: bool = True
    shouldEnableSlowMotion: bool = False
    reviewState: Optional[str] = None
    reviewerNotes: Optional[str] = None
    topLabels: list[LabelScore] = Field(default_factory=list)
    comparisonTopLabels: list[LabelScore] = Field(default_factory=list)
    rawTopLabels: list[RawLabelScore] = Field(default_factory=list)
    comparisonRawTopLabels: list[RawLabelScore] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactDescriptor(APIModel):
    kind: str
    path: str
    mediaType: str = "application/json"
    sizeBytes: Optional[int] = None
    sha256: Optional[str] = None


class InferenceDiagnostics(APIModel):
    featureExtractor: str
    candidateProposer: str
    actionRecognizer: str
    comparisonRecognizer: Optional[str] = None
    eventInferencer: str
    reranker: str
    frameCount: int = 0
    durationSeconds: float = 0.0
    fps: float = 0.0
    usedFallback: bool = False
    comparisonScore: Optional[float] = None


class InferenceManifest(APIModel):
    schemaVersion: str
    jobId: str
    requestId: str
    uploadTraceId: Optional[str] = None
    inferenceAttemptId: Optional[str] = None
    modelVersion: str
    resultConfidence: float = Field(ge=0.0, le=1.0)
    failureReason: Optional[str] = None
    generatedAt: datetime
    clips: list[RankedClip] = Field(default_factory=list)
    artifacts: list[ArtifactDescriptor] = Field(default_factory=list)
    diagnostics: InferenceDiagnostics


class InferenceJobResponse(APIModel):
    jobId: str
    status: str
    requestId: str
    uploadTraceId: Optional[str] = None
    inferenceAttemptId: Optional[str] = None
    modelVersion: Optional[str] = None
    failureReason: Optional[str] = None
    confidence: Optional[float] = None
    resultConfidence: Optional[float] = None
    result: Optional[InferenceManifest] = None
    message: Optional[str] = None


class CallbackPayload(APIModel):
    jobId: str
    status: InferenceStatus
    requestId: str
    uploadTraceId: Optional[str] = None
    inferenceAttemptId: Optional[str] = None
    modelVersion: str
    schemaVersion: Optional[str] = None
    failureReason: Optional[str] = None
    confidence: Optional[float] = None
    resultConfidence: Optional[float] = None
    result: Optional[InferenceManifest] = None
    results: Optional[dict[str, Any]] = None
    traceId: Optional[str] = None


class CallbackAcknowledgement(APIModel):
    jobId: str
    accepted: bool
    status: str
    requestId: str
