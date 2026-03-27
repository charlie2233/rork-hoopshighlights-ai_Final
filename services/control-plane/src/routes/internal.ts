import type { Env } from "../env";
import type { InferenceCallbackPayload } from "../types";
import { getJobSnapshot, updateJobState } from "../do/job-state-client";
import { appendJobEvent } from "../db";
import { isSharedSecretAuthorized } from "../utils/auth";
import { emptyResponse, jsonResponse, readJson } from "../utils/request-id";

export async function routeInternalRequest(
  request: Request,
  env: Env,
  requestId: string
): Promise<Response | null> {
  const url = new URL(request.url);
  if (!url.pathname.startsWith("/v1/internal/inference/")) {
    return null;
  }

  if (request.method === "POST") {
    const callbackMatch = url.pathname.match(/^\/v1\/internal\/inference\/callback\/([^/]+)$/);
    if (callbackMatch) {
      return handleCallback(request, env, callbackMatch[1]!, requestId);
    }

    const heartbeatMatch = url.pathname.match(/^\/v1\/internal\/inference\/heartbeat\/([^/]+)$/);
    if (heartbeatMatch) {
      return handleHeartbeat(request, env, heartbeatMatch[1]!, requestId);
    }
  }

  return null;
}

async function handleCallback(request: Request, env: Env, jobId: string, requestId: string): Promise<Response> {
  if (!isSharedSecretAuthorized(request.headers.get("x-hoops-inference-secret"), env.CONTROL_PLANE_SHARED_SECRET)) {
    return jsonResponse(
      {
        requestId,
        errorCode: "forbidden",
        errorMessage: "Invalid inference callback secret.",
        failureReason: "Invalid inference callback secret."
      },
      { status: 403 },
      requestId
    );
  }

  const payload = await readJson<InferenceCallbackPayload>(request);
  const job = await getJobSnapshot(env, jobId);
  if (!job) {
    return jsonResponse({ requestId, errorCode: "job_not_found", errorMessage: "Cloud analysis job was not found." }, { status: 404 }, requestId);
  }

  const finishedAt = new Date().toISOString();
  const patched = await updateJobState(
    env,
    jobId,
    {
      status: payload.status === "failed" ? "failed" : "succeeded",
      stage: payload.stage ?? (payload.status === "failed" ? "Inference failed" : "Finalizing clips"),
      progress: typeof payload.progress === "number" ? payload.progress : payload.status === "failed" ? job.progress : 0.98,
      modelVersion: payload.modelVersion ?? job.modelVersion ?? null,
      failureReason: payload.failureReason ?? job.failureReason ?? null,
      resultConfidence: payload.resultConfidence ?? job.resultConfidence ?? null,
      results: payload.results ?? job.results ?? null,
      finishedAt,
      updatedAt: finishedAt
    },
    {
      requestId: payload.requestId ?? requestId,
      traceId: payload.traceId ?? job.traceId,
      eventType: "inference.callback",
      message: payload.status === "failed" ? "Inference callback reported failure." : "Inference callback reported success.",
      payload
    }
  );

  await appendJobEvent(env.DB, {
    jobId,
    requestId: payload.requestId ?? requestId,
    traceId: payload.traceId ?? job.traceId,
    eventType: "inference.callback.received",
    message: payload.status === "failed" ? "Inference callback reported failure." : "Inference callback reported success.",
    payload,
    createdAt: finishedAt
  });

  return jsonResponse(
    {
      requestId,
      jobId: patched.jobId,
      status: patched.status,
      modelVersion: patched.modelVersion ?? null,
      failureReason: patched.failureReason ?? null
    },
    { status: 200 },
    requestId
  );
}

async function handleHeartbeat(request: Request, env: Env, jobId: string, requestId: string): Promise<Response> {
  if (!isSharedSecretAuthorized(request.headers.get("x-hoops-inference-secret"), env.CONTROL_PLANE_SHARED_SECRET)) {
    return jsonResponse(
      {
        requestId,
        errorCode: "forbidden",
        errorMessage: "Invalid inference heartbeat secret.",
        failureReason: "Invalid inference heartbeat secret."
      },
      { status: 403 },
      requestId
    );
  }

  const payload = await readJson<{ progress?: number; stage?: string }>(request);
  const job = await getJobSnapshot(env, jobId);
  if (!job) {
    return jsonResponse({ requestId, errorCode: "job_not_found", errorMessage: "Cloud analysis job was not found." }, { status: 404 }, requestId);
  }

  const startedAt = job.startedAt ?? new Date().toISOString();
  const updated = await updateJobState(
    env,
    jobId,
    {
      status: "processing",
      stage: payload.stage ?? job.stage,
      progress: typeof payload.progress === "number" ? payload.progress : job.progress,
      startedAt,
      updatedAt: startedAt
    },
    {
      requestId,
      traceId: job.traceId,
      eventType: "inference.heartbeat",
      message: "Inference heartbeat received.",
      payload
    }
  );

  await appendJobEvent(env.DB, {
    jobId,
    requestId,
    traceId: job.traceId,
    eventType: "inference.heartbeat.received",
    message: "Inference heartbeat received.",
    payload,
    createdAt: startedAt
  });

  return jsonResponse(
    {
      requestId,
      jobId: updated.jobId,
      status: updated.status,
      stage: updated.stage,
      progress: updated.progress
    },
    { status: 200 },
    requestId
  );
}
