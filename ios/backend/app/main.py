from __future__ import annotations

from typing import Dict, Optional

from fastapi import FastAPI

from .api import create_router
from .config import Settings, get_settings


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = FastAPI(title="Hoops AI API", version=resolved_settings.backend_model_version)
    app.include_router(create_router(resolved_settings))

    @app.get("/")
    async def root() -> Dict[str, str]:
        return {
            "service": resolved_settings.service_name,
            "status": "ok",
            "analysisMode": "cloud",
            "version": resolved_settings.backend_model_version,
        }

    @app.get("/healthz")
    async def healthz() -> Dict[str, str]:
        return {
            "status": "ok",
            "service": resolved_settings.service_name,
        }

    return app


app = create_app()
