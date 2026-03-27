from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os
from typing import Optional


@dataclass(frozen=True)
class Settings:
    service_name: str
    environment: str
    host_base_url: str
    cloud_run_base_url: str
    upload_root: Path
    external_repo_root: Path
    internal_process_secret: Optional[str]
    gcp_project_id: Optional[str]
    gcp_region: str
    gcs_bucket_name: str
    firestore_jobs_collection: str
    firestore_usage_collection: str
    cloud_tasks_queue: str
    enable_local_upload_emulation: bool
    detection_provider: str
    post_ranking_provider: str
    hoopcut_repo_path: Optional[Path]
    hoopcut_python_bin: Optional[str]
    autohighlight_repo_path: Optional[Path]
    autohighlight_python_bin: Optional[str]
    daily_quota: int
    rolling_quota_hours: int
    default_poll_after_seconds: int
    job_ttl_seconds: int
    signed_upload_ttl_seconds: int
    max_file_size_bytes: int
    max_duration_seconds: float
    min_clip_duration_seconds: float
    max_clip_duration_seconds: float
    clip_padding_seconds: float
    max_returned_clips: int
    backend_model_version: str
    use_gemini_relabeling: bool

    @property
    def is_local(self) -> bool:
        return self.environment == "local"

    @property
    def cloud_tasks_parent(self) -> Optional[str]:
        if not self.gcp_project_id:
            return None
        return "projects/{project}/locations/{region}/queues/{queue}".format(
            project=self.gcp_project_id,
            region=self.gcp_region,
            queue=self.cloud_tasks_queue,
        )

    @property
    def local_upload_url_template(self) -> str:
        return "{base}/v1/internal/uploads/{{job_id}}".format(base=self.host_base_url)

    @property
    def hoopcut_is_configured(self) -> bool:
        return self.hoopcut_repo_path is not None and self.hoopcut_python_bin is not None

    @property
    def autohighlight_is_configured(self) -> bool:
        return self.autohighlight_repo_path is not None and self.autohighlight_python_bin is not None


def _resolve_optional_path(value: Optional[str]) -> Optional[Path]:
    if not value:
        return None
    return Path(value).expanduser().resolve()


def _resolve_optional_python(env_key: str, default_venv_dir: Path) -> Optional[str]:
    explicit = os.getenv(env_key)
    if explicit:
        return str(Path(explicit).expanduser().resolve())

    interpreter = default_venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    pip_binary = default_venv_dir / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")
    if interpreter.exists() and pip_binary.exists():
        return str(interpreter.resolve())

    return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = os.getenv("HOOPS_ENVIRONMENT", os.getenv("ENV", "local")).strip().lower() or "local"
    host_base_url = os.getenv("HOOPS_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    cloud_run_base_url = os.getenv("HOOPS_CLOUD_RUN_BASE_URL", host_base_url).rstrip("/")

    upload_root = Path(os.getenv("HOOPS_UPLOAD_ROOT", "/tmp/hoops-ai")).resolve()
    upload_root.mkdir(parents=True, exist_ok=True)

    backend_root = Path(__file__).resolve().parents[1]
    external_repo_root = Path(
        os.getenv("HOOPS_EXTERNAL_REPO_ROOT", str(backend_root / ".external"))
    ).expanduser().resolve()
    default_venv_root = Path(os.getenv("HOOPS_EXTERNAL_VENV_ROOT", str(backend_root / ".venvs"))).expanduser().resolve()

    explicit_local_upload = os.getenv("HOOPS_ENABLE_LOCAL_UPLOAD_EMULATION")
    if explicit_local_upload is not None:
        enable_local_upload_emulation = explicit_local_upload.strip().lower() == "true"
    else:
        enable_local_upload_emulation = environment == "local"

    detection_provider = os.getenv("HOOPS_DETECTION_PROVIDER", "hybrid").strip().lower() or "hybrid"
    post_ranking_provider = os.getenv("HOOPS_POST_RANKING_PROVIDER", "native").strip().lower() or "native"

    default_hoopcut_repo = external_repo_root / "HoopCut_FH"
    default_autohighlight_repo = external_repo_root / "autohighlight"

    hoopcut_repo_path = _resolve_optional_path(os.getenv("HOOPS_HOOPCUT_REPO_PATH"))
    if hoopcut_repo_path is None and default_hoopcut_repo.exists():
        hoopcut_repo_path = default_hoopcut_repo

    autohighlight_repo_path = _resolve_optional_path(os.getenv("HOOPS_AUTOHIGHLIGHT_REPO_PATH"))
    if autohighlight_repo_path is None and default_autohighlight_repo.exists():
        autohighlight_repo_path = default_autohighlight_repo

    hoopcut_python_bin = _resolve_optional_python(
        "HOOPS_HOOPCUT_PYTHON",
        default_venv_root / "hoopcut",
    )
    autohighlight_python_bin = _resolve_optional_python(
        "HOOPS_AUTOHIGHLIGHT_PYTHON",
        default_venv_root / "autohighlight",
    )

    project_id = (
        os.getenv("HOOPS_GCP_PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCP_PROJECT")
        or None
    )

    return Settings(
        service_name="hoops-ai-api",
        environment=environment,
        host_base_url=host_base_url,
        cloud_run_base_url=cloud_run_base_url,
        upload_root=upload_root,
        external_repo_root=external_repo_root,
        internal_process_secret=os.getenv("HOOPS_INTERNAL_PROCESS_SECRET") or None,
        gcp_project_id=project_id,
        gcp_region=os.getenv("HOOPS_GCP_REGION", "us-central1"),
        gcs_bucket_name=os.getenv("HOOPS_GCS_BUCKET", "charlie-hoops-ai-analysis-temp"),
        firestore_jobs_collection=os.getenv("HOOPS_FIRESTORE_JOBS_COLLECTION", "analysisJobs"),
        firestore_usage_collection=os.getenv("HOOPS_FIRESTORE_USAGE_COLLECTION", "usageCounters"),
        cloud_tasks_queue=os.getenv("HOOPS_CLOUD_TASKS_QUEUE", "analysis-jobs"),
        enable_local_upload_emulation=enable_local_upload_emulation,
        detection_provider=detection_provider,
        post_ranking_provider=post_ranking_provider,
        hoopcut_repo_path=hoopcut_repo_path,
        hoopcut_python_bin=hoopcut_python_bin,
        autohighlight_repo_path=autohighlight_repo_path,
        autohighlight_python_bin=autohighlight_python_bin,
        daily_quota=int(os.getenv("HOOPS_DAILY_QUOTA", "5")),
        rolling_quota_hours=int(os.getenv("HOOPS_ROLLING_QUOTA_HOURS", "24")),
        default_poll_after_seconds=int(os.getenv("HOOPS_POLL_AFTER_SECONDS", "2")),
        job_ttl_seconds=int(os.getenv("HOOPS_JOB_TTL_SECONDS", "3600")),
        signed_upload_ttl_seconds=int(os.getenv("HOOPS_SIGNED_UPLOAD_TTL_SECONDS", "900")),
        max_file_size_bytes=int(os.getenv("HOOPS_MAX_FILE_SIZE_BYTES", str(500 * 1024 * 1024))),
        max_duration_seconds=float(os.getenv("HOOPS_MAX_DURATION_SECONDS", "1800")),
        min_clip_duration_seconds=float(os.getenv("HOOPS_MIN_CLIP_SECONDS", "2.0")),
        max_clip_duration_seconds=float(os.getenv("HOOPS_MAX_CLIP_SECONDS", "15.0")),
        clip_padding_seconds=float(os.getenv("HOOPS_CLIP_PADDING_SECONDS", "0.35")),
        max_returned_clips=int(os.getenv("HOOPS_MAX_RETURNED_CLIPS", "8")),
        backend_model_version=os.getenv("HOOPS_BACKEND_MODEL_VERSION", "cloud-v1"),
        use_gemini_relabeling=os.getenv("HOOPS_USE_GEMINI_RELABELING", "false").lower() == "true",
    )
