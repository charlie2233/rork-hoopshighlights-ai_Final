from __future__ import annotations

from fastapi import FastAPI

from .api import router
from .config import get_settings


settings = get_settings()
app = FastAPI(title="Hoops AI API", version=settings.backend_model_version)
app.include_router(router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": settings.service_name,
        "status": "ok",
        "analysisMode": "cloud",
        "version": settings.backend_model_version,
    }


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
    }
