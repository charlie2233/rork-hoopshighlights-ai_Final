from __future__ import annotations

from typing import Dict, Optional

from fastapi import FastAPI

from .api import create_router
from .config import Settings, get_settings
from .render_storage import RenderStorage
from .renderers.ffmpeg_renderer import ffmpeg_diagnostics


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_settings.validate()
    app = FastAPI(title="Hoops AI API", version=resolved_settings.backend_model_version)
    app.include_router(create_router(resolved_settings))

    @app.get("/")
    async def root() -> Dict[str, str]:
        return {
            "service": resolved_settings.service_name,
            "status": "ok",
        }

    @app.get("/healthz")
    async def healthz() -> Dict[str, str]:
        return {
            "status": "ok",
            "service": resolved_settings.service_name,
        }

    @app.get("/readyz")
    async def readyz() -> Dict[str, object]:
        ffmpeg = ffmpeg_diagnostics()
        storage = RenderStorage(resolved_settings).diagnostics()
        ready = (
            bool(ffmpeg["ffmpegAvailable"])
            and bool(ffmpeg["ffprobeAvailable"])
            and bool(storage["providerReady"])
            and bool(storage["uploadRootWritable"])
        )
        return {
            "status": "ok" if ready else "degraded",
            "service": resolved_settings.service_name,
            "environment": resolved_settings.environment,
            "ffmpeg": ffmpeg,
            "renderStorage": storage,
        }

    @app.get("/version")
    async def version() -> Dict[str, object]:
        return {
            "service": resolved_settings.service_name,
            "backendModelVersion": resolved_settings.backend_model_version,
            "environment": resolved_settings.environment,
            "ffmpeg": ffmpeg_diagnostics(),
        }

    return app


app = create_app()
