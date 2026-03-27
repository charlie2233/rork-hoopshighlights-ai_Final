from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JobStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.EXPIRED, JobStatus.CANCELLED}


class CreateCloudAnalysisJobRequest(APIModel):
    filename: str = Field(min_length=1, max_length=255)
    contentType: str = Field(min_length=1, max_length=120)
    fileSizeBytes: int = Field(gt=0)
    durationSeconds: float = Field(gt=0.0)
    installId: str = Field(min_length=8, max_length=128)
    appVersion: str = Field(min_length=1, max_length=64)
    analysisVersion: str = Field(min_length=1, max_length=64)


class CreateCloudAnalysisJobResponse(APIModel):
    requestId: str
    jobId: str
    uploadUrl: str
    uploadMethod: str = "PUT"
    uploadHeaders: Dict[str, str]
    expiresAt: datetime
    pollAfterSeconds: int
    quotaRemainingToday: int
    analysisMode: str = "cloud"
    modelVersion: Optional[str] = None
    failureReason: Optional[str] = None


class StartCloudAnalysisJobRequest(APIModel):
    installId: str = Field(min_length=8, max_length=128)


class StartCloudAnalysisJobResponse(APIModel):
    requestId: str
    jobId: str
    status: str
    modelVersion: Optional[str] = None
    failureReason: Optional[str] = None


class CloudClip(APIModel):
    clipId: str = Field(default_factory=lambda: uuid4().hex)
    startTime: float
    endTime: float
    confidence: float
    label: str
    action: str
    audioScore: float
    visualScore: float
    motionScore: float
    combinedScore: float
    detectionMethod: str = "cloud"
    shouldAutoKeep: bool
    shouldEnableSlowMotion: bool
    eventType: Optional[str] = None
    shotType: Optional[str] = None
    makeMiss: Optional[str] = None
    rankScore: Optional[float] = None
    reviewStatus: Optional[str] = None


class CloudDiagnostics(APIModel):
    processingMs: int
    backendModelVersion: str
    modelVersion: Optional[str] = None
    usedVideoIntelligence: bool
    usedGeminiRelabeling: bool
    candidateSegments: int
    finalSegments: int
    failureReason: Optional[str] = None


class CloudAnalysisResult(APIModel):
    clipCount: int
    clips: List[CloudClip]
    diagnostics: CloudDiagnostics
    resultConfidence: float = 0.0
    modelVersion: Optional[str] = None
    failureReason: Optional[str] = None


class CloudAnalysisJobResponse(APIModel):
    requestId: str
    jobId: str
    status: str
    progress: float
    stage: str
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None
    analysisVersion: str
    results: Optional[CloudAnalysisResult] = None
    modelVersion: Optional[str] = None
    failureReason: Optional[str] = None


class ErrorResponse(APIModel):
    requestId: str
    errorCode: str
    errorMessage: str
    quotaRemainingToday: Optional[int] = None
    modelVersion: Optional[str] = None
    failureReason: Optional[str] = None


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
    status: JobStatus = JobStatus.CREATED
    progress: float = 0.0
    stage: str = "Preparing upload"
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    model_version: Optional[str] = None
    failure_reason: Optional[str] = None
    trace_id: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    worker_version: Optional[str] = None
    result_object_key: Optional[str] = None
    attempt: int = 0
    results: Optional[CloudAnalysisResult] = None
    storage_path: Optional[str] = None
    quota_remaining_today: int = 0

    def to_job_response(self, request_id: str) -> CloudAnalysisJobResponse:
        resolved_model_version = self.model_version
        resolved_failure_reason = self.failure_reason or self.error_code
        if self.results is not None:
            resolved_model_version = self.results.modelVersion or resolved_model_version
            resolved_failure_reason = self.results.failureReason or resolved_failure_reason
        return CloudAnalysisJobResponse(
            requestId=request_id,
            jobId=self.job_id,
            status=self.status.value,
            progress=round(self.progress, 4),
            stage=self.stage,
            errorCode=self.error_code,
            errorMessage=self.error_message,
            analysisVersion=self.analysis_version,
            results=self.results,
            modelVersion=resolved_model_version,
            failureReason=resolved_failure_reason,
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
            requestId="",
            errorCode=self.error_code,
            errorMessage=self.error_message,
            quotaRemainingToday=self.quota_remaining_today,
            failureReason=self.error_code,
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
