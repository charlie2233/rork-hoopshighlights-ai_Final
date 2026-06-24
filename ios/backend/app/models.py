from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JobStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"

    @property
    def is_terminal(self) -> bool:
        return self in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.EXPIRED}


class AssetStatus(str, Enum):
    INITIALIZED = "initialized"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROXY_READY = "proxy_ready"
    READY = "ready"
    FAILED = "failed"

    @property
    def can_start_analysis(self) -> bool:
        return self in {AssetStatus.PROXY_READY, AssetStatus.READY}


class UploadMode(str, Enum):
    SINGLE = "single"
    MULTIPART = "multipart"


class TeamSelection(APIModel):
    mode: Literal["all", "team"] = "all"
    teamId: Optional[str] = Field(default=None, min_length=1, max_length=80)
    label: Optional[str] = Field(default=None, min_length=1, max_length=80)
    colorLabel: Optional[str] = Field(default=None, min_length=1, max_length=80)
    confidenceThreshold: float = Field(default=0.85, ge=0.5, le=0.99)
    includeUncertain: bool = True

    @model_validator(mode="after")
    def validate_team_selection(self) -> "TeamSelection":
        if self.mode == "team" and not (self.teamId or self.colorLabel):
            raise ValueError("team selection requires a teamId or colorLabel")
        return self


class TeamOption(APIModel):
    teamId: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=80)
    colorLabel: Optional[str] = Field(default=None, max_length=80)
    primaryColorHex: Optional[str] = Field(default=None, max_length=16)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: Literal["quick_scan", "provider", "manual", "unknown"] = "unknown"

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, value: object) -> object:
        if value is None:
            return "unknown"
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or "unknown"
        return value


class ClipTeamAttribution(APIModel):
    teamId: Optional[str] = Field(default=None, min_length=1, max_length=80)
    label: Optional[str] = Field(default=None, min_length=1, max_length=80)
    colorLabel: Optional[str] = Field(default=None, min_length=1, max_length=80)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: Literal["quick_scan", "gpt_frame_review", "provider", "manual", "unknown"] = "unknown"
    evidenceFrameRefs: List[str] = Field(default_factory=list, max_length=8)
    evidenceRoleGroups: List[str] = Field(default_factory=list, max_length=3)

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, value: object) -> object:
        if value is None:
            return "unknown"
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or "unknown"
        return value


class CreateCloudAnalysisJobRequest(APIModel):
    filename: str = Field(min_length=1, max_length=255)
    contentType: str = Field(min_length=1, max_length=120)
    fileSizeBytes: int = Field(gt=0)
    durationSeconds: float = Field(gt=0.0)
    installId: str = Field(min_length=8, max_length=128)
    appVersion: str = Field(min_length=1, max_length=64)
    analysisVersion: str = Field(min_length=1, max_length=64)
    teamSelection: Optional[TeamSelection] = None
    assetId: Optional[str] = Field(default=None, min_length=1, max_length=128)
    storageKey: Optional[str] = Field(default=None, min_length=1, max_length=512)


class CreateCloudAnalysisJobResponse(APIModel):
    jobId: str
    assetId: Optional[str] = None
    storageKey: Optional[str] = None
    uploadUrl: str
    uploadMethod: str = "PUT"
    uploadHeaders: Dict[str, str]
    expiresAt: datetime
    pollAfterSeconds: int
    quotaRemainingToday: int
    analysisMode: str = "cloud"


class StartCloudAnalysisJobRequest(APIModel):
    installId: str = Field(min_length=8, max_length=128)
    teamSelection: Optional[TeamSelection] = None


class StartCloudAnalysisJobResponse(APIModel):
    jobId: str
    status: str


class ScanCloudAnalysisTeamsRequest(APIModel):
    installId: str = Field(min_length=8, max_length=128)


class ScanCloudAnalysisSourceRequest(APIModel):
    jobId: str = Field(min_length=1, max_length=128)
    requestId: Optional[str] = Field(default=None, min_length=1, max_length=128)
    uploadTraceId: Optional[str] = Field(default=None, min_length=1, max_length=128)
    traceId: Optional[str] = Field(default=None, min_length=1, max_length=128)
    installId: str = Field(min_length=8, max_length=128)
    assetId: Optional[str] = Field(default=None, min_length=1, max_length=128)
    storageKey: Optional[str] = Field(default=None, min_length=1, max_length=512)
    sourceUrl: Optional[str] = Field(default=None, min_length=8)
    sourceObjectKey: Optional[str] = Field(default=None, max_length=512)
    filename: str = Field(default="source.mp4", min_length=1, max_length=255)
    contentType: Optional[str] = Field(default=None, max_length=120)
    durationSeconds: float = Field(gt=0.0)
    appVersion: Optional[str] = Field(default=None, max_length=64)
    analysisVersion: Optional[str] = Field(default=None, max_length=64)
    schemaVersion: Optional[str] = Field(default=None, max_length=64)
    modelVersion: Optional[str] = Field(default=None, max_length=120)


class InferenceDispatchRequest(APIModel):
    jobId: str = Field(min_length=1, max_length=128)
    requestId: str = Field(min_length=1, max_length=128)
    uploadTraceId: str = Field(min_length=1, max_length=128)
    inferenceAttemptId: str = Field(min_length=1, max_length=128)
    traceId: str = Field(min_length=1, max_length=128)
    filename: str = Field(default="source.mp4", min_length=1, max_length=255)
    contentType: Optional[str] = Field(default="video/mp4", max_length=120)
    fileSizeBytes: Optional[int] = Field(default=None, gt=0)
    durationSeconds: float = Field(gt=0.0)
    assetId: Optional[str] = Field(default=None, min_length=1, max_length=128)
    storageKey: Optional[str] = Field(default=None, min_length=1, max_length=512)
    sourceObjectKey: Optional[str] = Field(default=None, min_length=1, max_length=512)
    sourceUrl: Optional[str] = Field(default=None, min_length=8)
    resultObjectKey: str = Field(min_length=1, max_length=512)
    callbackUrl: str = Field(min_length=8)
    callbackSecret: str = Field(min_length=1, max_length=256)
    schemaVersion: str = Field(min_length=1, max_length=64)
    modelVersion: str = Field(min_length=1, max_length=120)
    installId: str = Field(min_length=8, max_length=128)
    appVersion: str = Field(min_length=1, max_length=64)
    analysisVersion: str = Field(min_length=1, max_length=64)
    teamSelection: Optional[TeamSelection] = None
    requestedModel: Optional[str] = Field(default=None, max_length=80)
    attemptCount: Optional[int] = Field(default=None, ge=0)


class ScanCloudAnalysisTeamsResponse(APIModel):
    jobId: str
    status: Literal["scanned", "unavailable"]
    detectedTeams: List[TeamOption] = Field(default_factory=list)


class CloudNativeShotSignals(APIModel):
    isShotLike: bool = False
    leadInSeconds: float = Field(default=0.0, ge=0.0)
    followThroughSeconds: float = Field(default=0.0, ge=0.0)
    setupContextScore: float = Field(default=0.0, ge=0.0, le=1.0)
    outcomeContextScore: float = Field(default=0.0, ge=0.0, le=1.0)
    eventCenterQuality: float = Field(default=0.0, ge=0.0, le=1.0)
    contextQualityScore: float = Field(default=0.0, ge=0.0, le=1.0)
    timingWindowOk: bool = False
    outcome: Literal["made", "missed", "blocked", "uncertain", "not_shot"] = "uncertain"
    outcomeConfidence: float = Field(default=0.0, ge=0.0, le=1.0)
    outcomeEvidenceSource: Literal[
        "label_only",
        "native_shot_signals",
        "defensive_event",
        "gpt_shot_tracking",
        "gpt_defensive_tracking",
        "non_shot",
        "uncertain",
        "not_shot",
    ] = "uncertain"
    outcomeReliabilityScore: float = Field(default=0.0, ge=0.0, le=1.0)


AudioCueType = Literal["spike", "cluster", "super_loud_cluster", "swell", "steady_noise", "none"]


class CloudLabelScore(APIModel):
    label: str = Field(min_length=1, max_length=80)
    confidence: float = Field(ge=0.0, le=1.0)
    rawLabel: Optional[str] = Field(default=None, min_length=1, max_length=120)
    modelVersion: Optional[str] = Field(default=None, min_length=1, max_length=120)


class CloudRawLabelScore(APIModel):
    rawLabel: str = Field(min_length=1, max_length=120)
    confidence: float = Field(ge=0.0, le=1.0)
    canonicalLabel: Optional[str] = Field(default=None, min_length=1, max_length=80)
    modelVersion: Optional[str] = Field(default=None, min_length=1, max_length=120)


DetectionPipelineStage = Literal["proposal", "embedding_rerank", "classifier", "merge", "taxonomy"]
DetectionStageStatus = Literal["applied", "fallback", "skipped", "unavailable"]


class DetectionStageProvenance(APIModel):
    stage: DetectionPipelineStage
    status: DetectionStageStatus = "applied"
    source: str = Field(min_length=1, max_length=80)
    modelId: Optional[str] = Field(default=None, min_length=1, max_length=160)
    modelVersion: Optional[str] = Field(default=None, min_length=1, max_length=160)
    adapter: Optional[str] = Field(default=None, min_length=1, max_length=80)
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    rank: Optional[int] = Field(default=None, ge=1)
    rawLabel: Optional[str] = Field(default=None, min_length=1, max_length=120)
    details: Dict[str, Any] = Field(default_factory=dict)


class CloudClipProvenance(APIModel):
    proposal: DetectionStageProvenance
    embeddingRerank: Optional[DetectionStageProvenance] = None
    classifier: Optional[DetectionStageProvenance] = None
    merge: Optional[DetectionStageProvenance] = None
    taxonomy: Optional[DetectionStageProvenance] = None


class CloudClipScores(APIModel):
    proposalScore: float = Field(ge=0.0, le=1.0)
    embeddingScore: float = Field(default=0.0, ge=0.0, le=1.0)
    classifierScore: float = Field(default=0.0, ge=0.0, le=1.0)
    mergeScore: float = Field(default=0.0, ge=0.0, le=1.0)
    finalScore: float = Field(ge=0.0, le=1.0)


class CloudClip(APIModel):
    startTime: float
    endTime: float
    eventCenter: Optional[float] = None
    confidence: float
    label: str
    action: str
    canonicalLabel: Optional[str] = Field(default=None, min_length=1, max_length=80)
    eventFamily: Optional[str] = Field(default=None, min_length=1, max_length=80)
    eventSubtype: Optional[str] = Field(default=None, min_length=1, max_length=80)
    shotSubtype: Optional[str] = Field(default=None, min_length=1, max_length=80)
    outcome: Optional[Literal["made", "missed", "blocked", "uncertain"]] = None
    audioScore: float
    visualScore: float
    motionScore: float
    combinedScore: float
    confidenceBeforeMapping: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidenceAfterMapping: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    eventFamilyConfidenceBeforeMapping: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    eventFamilyConfidenceAfterMapping: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    shotSubtypeConfidenceBeforeMapping: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    shotSubtypeConfidenceAfterMapping: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    outcomeConfidenceBeforeMapping: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    outcomeConfidenceAfterMapping: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    audioCueType: Optional[AudioCueType] = None
    audioCueConfidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    audioCueTime: Optional[float] = Field(default=None, ge=0.0)
    detectionMethod: str = "cloud"
    shouldAutoKeep: bool
    shouldEnableSlowMotion: bool
    isUncertain: Optional[bool] = None
    promptSetVersion: Optional[str] = Field(default=None, min_length=1, max_length=80)
    eventType: Optional[str] = Field(default=None, min_length=1, max_length=80)
    shotType: Optional[str] = Field(default=None, min_length=1, max_length=80)
    makeMiss: Optional[Literal["make", "miss", "unknown"]] = None
    rankScore: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    reviewState: Optional[str] = Field(default=None, min_length=1, max_length=80)
    reviewerNotes: Optional[str] = Field(default=None, max_length=500)
    topLabels: Optional[List[CloudLabelScore]] = None
    comparisonTopLabels: Optional[List[CloudLabelScore]] = None
    rawTopLabels: Optional[List[CloudRawLabelScore]] = None
    comparisonRawTopLabels: Optional[List[CloudRawLabelScore]] = None
    pipelineStage: Optional[Literal["proposal", "embedding_rerank", "classified", "merged_candidate"]] = None
    pipelineVersion: Optional[str] = Field(default=None, min_length=1, max_length=80)
    provenance: Optional[CloudClipProvenance] = None
    scores: Optional[CloudClipScores] = None
    nativeShotSignals: Optional[CloudNativeShotSignals] = None
    teamAttribution: Optional[ClipTeamAttribution] = None
    teamAttributionStatus: Optional[Literal["all", "matched", "opponent", "uncertain"]] = None


class DetectionPipelineSummary(APIModel):
    pipelineVersion: str = Field(min_length=1, max_length=80)
    stages: List[DetectionPipelineStage]
    proposalCount: int = Field(ge=0)
    rerankedCount: int = Field(ge=0)
    classifiedCount: int = Field(ge=0)
    mergedCandidateCount: int = Field(ge=0)
    models: Dict[str, str] = Field(default_factory=dict)
    taxonomyVersion: str = Field(min_length=1, max_length=80)
    fallbackUsed: bool = False
    fallbackReasons: List[str] = Field(default_factory=list)


class CloudDiagnostics(APIModel):
    processingMs: int
    backendModelVersion: str
    usedVideoIntelligence: bool
    usedGeminiRelabeling: bool
    candidateSegments: int
    finalSegments: int
    proposalSegments: int = 0
    embeddedSegments: int = 0
    classifiedSegments: int = 0
    mergedCandidateSegments: int = 0
    usedSemanticRerank: bool = False
    taxonomyVersion: Optional[str] = None
    usedTeamQuickScan: bool = False
    preTeamFilterSegments: int = 0
    teamMatchedCandidateSegments: int = 0
    teamUncertainCandidateSegments: int = 0
    teamOpponentFilteredSegments: int = 0
    teamMatchedReviewSegments: int = 0
    teamUncertainReviewSegments: int = 0
    defensiveReviewSegments: int = 0
    blockReviewSegments: int = 0
    stealReviewSegments: int = 0
    forcedTurnoverReviewSegments: int = 0
    defensiveStopReviewSegments: int = 0
    audioReactionReviewSegments: int = 0


class CloudAnalysisResult(APIModel):
    analysisJobId: Optional[str] = None
    assetId: Optional[str] = None
    assetStorageKey: Optional[str] = None
    storageKey: Optional[str] = None
    proxyStorageKey: Optional[str] = None
    assetStatus: Optional[str] = None
    uploadedBytes: Optional[int] = None
    fileSizeBytes: Optional[int] = None
    assetFailureReason: Optional[str] = None
    sourceObjectKey: Optional[str] = None
    clipCount: int
    clips: List[CloudClip]
    diagnostics: CloudDiagnostics
    resultConfidence: float = Field(default=0.0, ge=0.0, le=1.0)
    candidateClips: Optional[List[CloudClip]] = None
    pipeline: Optional[DetectionPipelineSummary] = None
    detectedTeams: List[TeamOption] = Field(default_factory=list)
    teamSelection: Optional[TeamSelection] = None


class CloudAnalysisJobResponse(APIModel):
    jobId: str
    assetId: Optional[str] = None
    storageKey: Optional[str] = None
    status: str
    progress: float
    stage: str
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None
    analysisVersion: str
    assetId: Optional[str] = None
    storageKey: Optional[str] = None
    results: Optional[CloudAnalysisResult] = None
    sourceObjectKey: Optional[str] = None
    resultObjectKey: Optional[str] = None


class UploadInitRequest(APIModel):
    filename: str = Field(min_length=1, max_length=255)
    contentType: str = Field(min_length=1, max_length=120)
    fileSizeBytes: int = Field(gt=0)
    durationSeconds: float = Field(gt=0.0)
    installId: str = Field(min_length=8, max_length=128)
    appVersion: str = Field(default="local", min_length=1, max_length=64)
    analysisVersion: str = Field(default="cloud-v1", min_length=1, max_length=64)
    uploadPreference: Literal["single", "multipart", "auto"] = "auto"
    partSizeBytes: Optional[int] = Field(default=None, gt=0)


class UploadTargetResponse(APIModel):
    uploadUrl: str
    uploadMethod: str = "PUT"
    uploadHeaders: Dict[str, str] = Field(default_factory=dict)
    partNumber: Optional[int] = None


class MultipartUploadResponse(APIModel):
    uploadId: str
    partSizeBytes: int
    partCount: int
    parts: List[UploadTargetResponse]


class UploadInitResponse(APIModel):
    assetId: str
    storageKey: str
    status: str
    uploadMode: str
    uploadUrl: Optional[str] = None
    uploadMethod: str = "PUT"
    uploadHeaders: Dict[str, str] = Field(default_factory=dict)
    multipart: Optional[MultipartUploadResponse] = None
    expiresAt: datetime
    pollAfterSeconds: int
    uploadState: str


class UploadPartCommit(APIModel):
    partNumber: int = Field(ge=1)
    etag: Optional[str] = Field(default=None, max_length=256)
    sizeBytes: Optional[int] = Field(default=None, ge=0)


class UploadCompleteRequest(APIModel):
    installId: str = Field(min_length=8, max_length=128)
    uploadId: Optional[str] = Field(default=None, min_length=1, max_length=256)
    parts: List[UploadPartCommit] = Field(default_factory=list)


class AssetArtifactsResponse(APIModel):
    proxyStorageKey: Optional[str] = None
    thumbnailStorageKeys: List[str] = Field(default_factory=list)
    waveformStorageKey: Optional[str] = None


class AssetResponse(APIModel):
    assetId: str
    installId: str
    filename: str
    contentType: str
    fileSizeBytes: int
    durationSeconds: float
    storageKey: str
    status: str
    uploadMode: str
    uploadedBytes: int
    artifacts: AssetArtifactsResponse
    createdAt: datetime
    updatedAt: datetime
    failureReason: Optional[str] = None


AssetRecord = AssetResponse


class UploadCompleteResponse(APIModel):
    assetId: str
    storageKey: str
    status: str
    artifacts: AssetArtifactsResponse
    pollAfterSeconds: int


class CreateAssetAnalysisJobRequest(APIModel):
    installId: str = Field(min_length=8, max_length=128)
    appVersion: Optional[str] = Field(default=None, max_length=64)
    analysisVersion: Optional[str] = Field(default=None, max_length=64)
    teamSelection: Optional[TeamSelection] = None


class CreateAssetAnalysisJobResponse(APIModel):
    jobId: str
    assetId: str
    storageKey: str
    status: str
    pollAfterSeconds: int
    quotaRemainingToday: int
    analysisMode: str = "cloud"


class ErrorResponse(APIModel):
    errorCode: str
    errorMessage: str
    quotaRemainingToday: Optional[int] = None


@dataclass(frozen=True)
class PreparedUpload:
    object_key: str
    upload_url: str
    upload_headers: Dict[str, str]
    expires_at: datetime


@dataclass
class MaterializedSource:
    local_path: Path
    cleanup_after_use: bool = False

    def cleanup(self) -> None:
        if not self.cleanup_after_use:
            return
        try:
            if self.local_path.exists():
                self.local_path.unlink()
            parent = self.local_path.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass


@dataclass
class CandidateWindow:
    start_time: float
    end_time: float
    peak_time: float
    audio_score: float
    visual_score: float
    motion_score: float
    combined_score: float
    event_context_score: float = 0.0
    audio_pop_score: float = 0.0
    audio_pop_time: Optional[float] = None
    audio_cue_type: Optional[str] = None
    audio_cue_confidence: float = 0.0


@dataclass
class StoredJob:
    job_id: str
    install_id: str
    filename: str
    content_type: str
    file_size_bytes: int
    duration_seconds: float
    app_version: str
    analysis_version: str
    created_at: datetime
    expires_at: datetime
    object_key: str
    upload_headers: Dict[str, str] = field(default_factory=dict)
    asset_id: Optional[str] = None
    storage_key: Optional[str] = None
    team_selection: Optional[TeamSelection] = None
    detected_teams: List[TeamOption] = field(default_factory=list)
    team_scan_status: Optional[str] = None
    status: JobStatus = JobStatus.CREATED
    progress: float = 0.0
    stage: str = "Preparing upload"
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    results: Optional[CloudAnalysisResult] = None
    storage_path: Optional[str] = None
    quota_remaining_today: int = 0

    def to_job_response(self) -> CloudAnalysisJobResponse:
        return CloudAnalysisJobResponse(
            jobId=self.job_id,
            assetId=self.asset_id or self.job_id,
            storageKey=self.storage_key,
            status=self.status.value,
            progress=round(self.progress, 4),
            stage=self.stage,
            errorCode=self.error_code,
            errorMessage=self.error_message,
            analysisVersion=self.analysis_version,
            results=self.results,
            sourceObjectKey=self.object_key,
            resultObjectKey=None,
        )


@dataclass
class StoredAsset:
    asset_id: str
    install_id: str
    filename: str
    content_type: str
    file_size_bytes: int
    duration_seconds: float
    app_version: str
    analysis_version: str
    storage_key: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    upload_mode: UploadMode = UploadMode.SINGLE
    status: AssetStatus = AssetStatus.INITIALIZED
    uploaded_bytes: int = 0
    proxy_storage_key: Optional[str] = None
    thumbnail_storage_keys: List[str] = field(default_factory=list)
    waveform_storage_key: Optional[str] = None
    failure_reason: Optional[str] = None

    @property
    def analysis_storage_key(self) -> str:
        return self.proxy_storage_key or self.storage_key

    def artifacts_response(self) -> AssetArtifactsResponse:
        return AssetArtifactsResponse(
            proxyStorageKey=self.proxy_storage_key,
            thumbnailStorageKeys=self.thumbnail_storage_keys,
            waveformStorageKey=self.waveform_storage_key,
        )

    def to_response(self) -> AssetResponse:
        return AssetResponse(
            assetId=self.asset_id,
            installId=self.install_id,
            filename=self.filename,
            contentType=self.content_type,
            fileSizeBytes=self.file_size_bytes,
            durationSeconds=self.duration_seconds,
            storageKey=self.storage_key,
            status=self.status.value,
            uploadMode=self.upload_mode.value,
            uploadedBytes=self.uploaded_bytes,
            artifacts=self.artifacts_response(),
            createdAt=self.created_at,
            updatedAt=self.updated_at,
            failureReason=self.failure_reason,
        )


@dataclass
class StoredAsset:
    asset_id: str
    install_id: str
    filename: str
    content_type: str
    file_size_bytes: int
    duration_seconds: float
    app_version: str
    analysis_version: str
    storage_key: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    upload_mode: UploadMode = UploadMode.SINGLE
    status: AssetStatus = AssetStatus.INITIALIZED
    upload_id: Optional[str] = None
    part_size_bytes: Optional[int] = None
    part_count: Optional[int] = None
    uploaded_bytes: int = 0
    parts: Dict[int, str] = field(default_factory=dict)
    proxy_storage_key: Optional[str] = None
    thumbnail_storage_keys: List[str] = field(default_factory=list)
    waveform_storage_key: Optional[str] = None
    failure_reason: Optional[str] = None

    @property
    def analysis_storage_key(self) -> str:
        return self.proxy_storage_key or self.storage_key

    def artifacts_response(self) -> AssetArtifactsResponse:
        return AssetArtifactsResponse(
            proxyStorageKey=self.proxy_storage_key,
            thumbnailStorageKeys=list(self.thumbnail_storage_keys),
            waveformStorageKey=self.waveform_storage_key,
        )

    def to_response(self) -> AssetResponse:
        return AssetResponse(
            assetId=self.asset_id,
            installId=self.install_id,
            filename=self.filename,
            contentType=self.content_type,
            fileSizeBytes=self.file_size_bytes,
            durationSeconds=self.duration_seconds,
            storageKey=self.storage_key,
            status=self.status.value,
            uploadMode=self.upload_mode.value,
            uploadedBytes=self.uploaded_bytes,
            artifacts=self.artifacts_response(),
            createdAt=self.created_at,
            updatedAt=self.updated_at,
            failureReason=self.failure_reason,
        )


class APIError(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        error_message: str,
        quota_remaining_today: Optional[int] = None,
    ) -> None:
        super().__init__(error_message)
        self.status_code = status_code
        self.error_code = error_code
        self.error_message = error_message
        self.quota_remaining_today = quota_remaining_today

    def to_response(self) -> ErrorResponse:
        return ErrorResponse(
            errorCode=self.error_code,
            errorMessage=self.error_message,
            quotaRemainingToday=self.quota_remaining_today,
        )


class PipelineError(Exception):
    def __init__(self, error_code: str, error_message: str) -> None:
        super().__init__(error_message)
        self.error_code = error_code
        self.error_message = error_message


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def now_utc() -> datetime:
    from datetime import timezone

    return datetime.now(tz=timezone.utc)
