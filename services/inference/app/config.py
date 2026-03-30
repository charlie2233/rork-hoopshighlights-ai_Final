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
    version: str = "0.2.0"

    default_model: str = "videomae"
    comparison_model: str = "xclip"
    model_name_videomae: str = "MCG-NJU/videomae-base-finetuned-kinetics"
    model_name_xclip: str = "microsoft/xclip-base-patch32"
    teacher_model_name: str = "Qwen/Qwen2.5-VL-7B-Instruct"

    callback_secret: str = ""
    ingress_secret: str = ""
    r2_bucket_name: str = ""
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_region_name: str = "auto"

    temp_dir: Path = Field(default=Path("/tmp/hoops-inference"))
    callback_timeout_seconds: float = 20.0
    http_timeout_seconds: float = 60.0
    max_candidates: int = 8
    result_schema_version: str = "2026-03-27"
    heuristic_window_seconds: float = 4.5
    heuristic_stride_seconds: float = 1.5
    ffmpeg_video_preset: str = "veryfast"
    ffmpeg_video_crf: int = 28
    ffmpeg_max_width: int = 1280
    ffmpeg_enable_transcode: bool = True
    perception_sample_frames: int = 12
    perception_overlay_frame_limit: int = 3
    teacher_labeling_enabled: bool = False
    teacher_frame_count: int = 4
    runtime_model_mode: str = "shadow"
    runtime_model_bundle_path: Path = Field(
        default=Path(__file__).resolve().parents[1] / "models" / "runtime_fusion_v1.json"
    )
    videomae_lora_mode: str = "off"
    videomae_lora_bundle_path: Path = Field(
        default=Path(__file__).resolve().parents[1] / "models" / "videomae_lora_v1" / "runtime_bundle.json"
    )

    def ensure_temp_dir(self) -> Path:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        return self.temp_dir

    def has_r2_configuration(self) -> bool:
        return all(
            (
                self.r2_bucket_name.strip(),
                self.r2_endpoint_url.strip(),
                self.r2_access_key_id.strip(),
                self.r2_secret_access_key.strip(),
            )
        )


@lru_cache(maxsize=1)
def get_settings() -> InferenceSettings:
    return InferenceSettings()
