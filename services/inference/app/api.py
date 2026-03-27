from __future__ import annotations

from fastapi import APIRouter, FastAPI

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

    @router.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/readyz")
    async def readyz() -> dict[str, str]:
        resolved_settings.ensure_temp_dir()
        return {"status": "ready"}

    @router.post("/v1/inference/run", response_model=InferenceJobResponse)
    async def run_inference(request: InferenceJobRequest) -> InferenceJobResponse:
        return await service.run(request)

    app.include_router(router)
    return app
