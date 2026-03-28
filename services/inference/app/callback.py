from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from .models import CallbackPayload


@dataclass
class CallbackClient:
    timeout_seconds: float = 20.0
    user_agent: str = "hoops-inference/0.1"

    async def send(self, callback_url: str, payload: CallbackPayload, secret: Optional[str], request_id: Optional[str] = None) -> None:
        if not secret:
            raise ValueError("callback secret is required")
        headers = {
            "content-type": "application/json",
            "x-hoops-callback-secret": secret,
            "x-hoops-request-id": request_id or payload.requestId,
            "user-agent": self.user_agent,
        }
        if payload.uploadTraceId:
            headers["x-hoops-upload-trace-id"] = payload.uploadTraceId
        if payload.inferenceAttemptId:
            headers["x-hoops-inference-attempt-id"] = payload.inferenceAttemptId
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(callback_url, headers=headers, json=payload.model_dump(mode="json", exclude_none=True))
            response.raise_for_status()
