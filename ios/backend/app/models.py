from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ClipTeamAttribution(APIModel):
    teamId: Optional[str] = Field(default=None, min_length=1, max_length=80)
    label: Optional[str] = Field(default=None, min_length=1, max_length=80)
    colorLabel: Optional[str] = Field(default=None, min_length=1, max_length=80)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: Literal["quick_scan", "gpt_frame_review", "provider", "manual", "unknown"] = "unknown"


class CreateCloudAnalysisJobRequest(APIModel):
    filename: str = Field(min_length=1, max_length=255)
    contentType: str = Field(min_length=1, max_length=120)
    fileSizeBytes: int = Field(gt=0)
    durationSeconds: float = Field(gt=0.0)
    installId: str = Field(min_length=8, max_length=128)
    appVersion: str = Field(min_length=1, max_length=64)
    analysisVersion: str = Field(min_length=1, max_length=64)
    teamSelection: Optional[TeamSelection] = None


class CreateCloudAnalysisJobResponse(APIModel):
    jobId: str
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
    installId: str = Field(min_length=8, max_length=128)
    sourceUrl: str = Field(min_length=8)
    sourceObjectKey: Optional[str] = Field(default=None, max_length=512)
    filename: str = Field(default="source.mp4", min_length=1, max_length=255)
    contentType: Optional[str] = Field(default=None, max_length=120)
    durationSeconds: float = Field(gt=0.0)
    appVersion: Optional[str] = Field(default=None, max_length=64)
    analysisVersion: Optional[str] = Field(default=None, max_length=64)


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


class CloudClip(APIModel):
    startTime: float
    endTime: float
    eventCenter: Optional[float] = None
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
    nativeShotSignals: Optional[CloudNativeShotSignals] = None
    teamAttribution: Optional[ClipTeamAttribution] = None
    teamAttributionStatus: Optional[Literal["all", "matched", "opponent", "uncertain"]] = None


class CloudDiagnostics(APIModel):
    processingMs: int
    backendModelVersion: str
    usedVideoIntelligence: bool
    usedGeminiRelabeling: bool
    candidateSegments: int
    finalSegments: int
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


class CloudAnalysisResult(APIModel):
    clipCount: int
    clips: List[CloudClip]
    diagnostics: CloudDiagnostics
    detectedTeams: List[TeamOption] = Field(default_factory=list)
    teamSelection: Optional[TeamSelection] = None


class CloudAnalysisJobResponse(APIModel):
    jobId: str
    status: str
    progress: float
    stage: str
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None
    analysisVersion: str
    results: Optional[CloudAnalysisResult] = None


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
            status=self.status.value,
            progress=round(self.progress, 4),
            stage=self.stage,
            errorCode=self.error_code,
            errorMessage=self.error_message,
            analysisVersion=self.analysis_version,
            results=self.results,
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
