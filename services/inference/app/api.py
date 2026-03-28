from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, FastAPI, Header, HTTPException, status

from .config import InferenceSettings, get_settings
from .models import InferenceJobRequest, InferenceJobResponse
from .pipeline import build_service


def create_app(settings: InferenceSettings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = FastAPI(
        title=resolved_settings.service_name,
        version=resolved_settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    router = APIRouter()
    service = build_service(resolved_settings)

    def require_ingress_secret(provided_secret: Optional[str]) -> None:
        expected_secret = resolved_settings.ingress_secret.strip()
        if not expected_secret:
            return
        if provided_secret != expected_secret:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid inference secret")

    @router.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": resolved_settings.service_name}

    @router.get("/readyz")
    async def readyz() -> dict[str, str]:
        resolved_settings.ensure_temp_dir()
        return {
            "status": "ready",
            "service": resolved_settings.service_name,
            "ffmpeg": "available" if _which("ffmpeg") else "missing",
            "ffprobe": "available" if _which("ffprobe") else "missing",
            "r2": "configured" if resolved_settings.has_r2_configuration() else "unconfigured",
        }

    @router.get("/version")
    async def version() -> dict[str, Any]:
        return {
            "serviceName": resolved_settings.service_name,
            "version": resolved_settings.version,
            "defaultModel": resolved_settings.default_model,
            "comparisonModel": resolved_settings.comparison_model,
            "modelNameVideoMAE": resolved_settings.model_name_videomae,
            "modelNameXClip": resolved_settings.model_name_xclip,
            "resultSchemaVersion": resolved_settings.result_schema_version,
        }

    @router.post("/v1/analyze", response_model=InferenceJobResponse)
    async def analyze(
        request: InferenceJobRequest,
        x_hoops_inference_secret: Optional[str] = Header(default=None),
    ) -> InferenceJobResponse:
        require_ingress_secret(x_hoops_inference_secret)
        return await service.run(request)

    @router.post("/v1/inference/run", response_model=InferenceJobResponse)
    async def run_inference(
        request: InferenceJobRequest,
        x_hoops_inference_secret: Optional[str] = Header(default=None),
    ) -> InferenceJobResponse:
        require_ingress_secret(x_hoops_inference_secret)
        return await service.run(request)

    app.include_router(router)
    return app


def _which(command: str) -> bool:
    import shutil

    return shutil.which(command) is not None
