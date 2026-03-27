from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class InferenceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOOPS_INFERENCE_",
        env_file=".env",
        extra="ignore",
    )

    service_name: str = "hoops-inference-service"
    environment: str = "local"
    version: str = "0.1.0"

    default_model: str = "videomae"
    comparison_model: str = "xclip"
    model_name_videomae: str = "MCG-NJU/videomae-base-finetuned-kinetics"
    model_name_xclip: str = "microsoft/xclip-base-patch32"

    temp_dir: Path = Field(default=Path("/tmp/hoops-inference"))
    callback_timeout_seconds: float = 20.0
    http_timeout_seconds: float = 60.0
    max_candidates: int = 8
    result_schema_version: str = "2026-03-27"
    heuristic_window_seconds: float = 4.5
    heuristic_stride_seconds: float = 1.5

    def ensure_temp_dir(self) -> Path:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        return self.temp_dir


@lru_cache(maxsize=1)
def get_settings() -> InferenceSettings:
    return InferenceSettings()
