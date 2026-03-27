import type { Env } from "../env";
import type { CloudAnalysisJobResponse, InferenceCallbackPayload, JobRecord, JobStatus } from "../types";
import { getJobSnapshot, updateJobState } from "../do/job-state-client";
import { appendJobEvent } from "../db";
import { isSharedSecretAuthorized } from "../utils/auth";
import { jsonResponse, readJson } from "../utils/request-id";

export async function routeInternalRequest(
  request: Request,
  env: Env,
  requestId: string
): Promise<Response | null> {
  const url = new URL(request.url);
  const path = normalizeInternalPath(url.pathname);

  if (request.method !== "POST") {
    return null;
  }

  if (path === "/internal/inference/callback") {
    return handleCallback(request, env, requestId, null);
  }

  const callbackMatch = path.match(/^\/internal\/inference\/callback\/([^/]+)$/);
  if (callbackMatch) {
    return handleCallback(request, env, requestId, callbackMatch[1]!);
  }

  const heartbeatMatch = path.match(/^\/internal\/inference\/heartbeat\/([^/]+)$/);
  if (heartbeatMatch) {
    return handleHeartbeat(request, env, heartbeatMatch[1]!, requestId);
  }

  return null;
}

async function handleCallback(
  request: Request,
  env: Env,
  requestId: string,
  pathJobId: string | null
): Promise<Response> {
  const callbackSecret = env.INFERENCE_SHARED_SECRET || env.CONTROL_PLANE_SHARED_SECRET;
  if (!isSharedSecretAuthorized(request.headers.get("x-hoops-inference-secret"), callbackSecret)) {
    return jsonResponse(
      {
        requestId,
        schemaVersion: null,
        confidence: null,
        errorCode: "forbidden",
        errorMessage: "Invalid inference callback secret.",
        failureReason: "Invalid inference callback secret."
      },
      { status: 403 },
      requestId
    );
  }

  const payload = await readJson<InferenceCallbackPayload>(request);
  const jobId = pathJobId ?? payload.jobId;
  if (!jobId) {
    return jsonResponse(
      {
        requestId,
        schemaVersion: null,
        confidence: null,
        errorCode: "invalid_request",
        errorMessage: "jobId is required for inference callbacks.",
        failureReason: "jobId is required for inference callbacks."
      },
      { status: 400 },
      requestId
    );
  }

  const job = await getJobSnapshot(env, jobId);
  if (!job) {
    return jsonResponse(
      {
        requestId,
        schemaVersion: payload.schemaVersion ?? null,
        confidence: payload.confidence ?? payload.resultConfidence ?? null,
        errorCode: "job_not_found",
        errorMessage: "Cloud analysis job was not found.",
        failureReason: "Cloud analysis job was not found."
      },
      { status: 404 },
      requestId
    );
  }

  const normalizedStatus = normalizeCallbackStatus(payload.status);
  const currentStatus = normalizeStoredStatus(job.status);
  const resultConfidence = payload.confidence ?? payload.resultConfidence ?? payload.results?.resultConfidence ?? job.resultConfidence ?? null;
  const failureReason = payload.failureReason ?? job.failureReason ?? null;
  const modelVersion = payload.modelVersion ?? job.modelVersion ?? null;
  const responseSchemaVersion = payload.schemaVersion ?? job.schemaVersion;
  const now = new Date().toISOString();

  if (isTerminalStatus(currentStatus) && normalizedStatus !== currentStatus) {
    console.warn(
      JSON.stringify({
        requestId,
        jobId,
        traceId: payload.traceId ?? job.traceId,
        event: "inference.callback.ignored",
        currentStatus,
        requestedStatus: normalizedStatus
      })
    );
    return jsonResponse(toCloudAnalysisJobResponse(job, requestId, responseSchemaVersion), { status: 200 }, requestId);
  }

  if (isTerminalStatus(currentStatus) && normalizedStatus === currentStatus) {
    console.info(
      JSON.stringify({
        requestId,
        jobId,
        traceId: payload.traceId ?? job.traceId,
        event: "inference.callback.duplicate",
        status: currentStatus
      })
    );
    return jsonResponse(toCloudAnalysisJobResponse(job, requestId, responseSchemaVersion), { status: 200 }, requestId);
  }

  if (payload.results && (!isTerminalStatus(currentStatus) || normalizedStatus === currentStatus || !job.results)) {
    await env.R2_RESULTS.put(job.resultObjectKey, JSON.stringify(payload.results), {
      httpMetadata: {
        contentType: "application/json; charset=utf-8"
      }
    });
  }

  const patched = await updateJobState(
    env,
    jobId,
    buildCallbackPatch(job, normalizedStatus, now, modelVersion, failureReason, resultConfidence, payload),
    {
      requestId: payload.requestId ?? requestId,
      traceId: payload.traceId ?? job.traceId,
      eventType: "inference.callback",
      message:
        normalizedStatus === "failed"
          ? "Inference callback reported failure."
          : normalizedStatus === "cancelled"
            ? "Inference callback reported cancellation."
            : normalizedStatus === "processing"
              ? "Inference callback reported progress."
              : "Inference callback reported success.",
      payload
    }
  );

  await appendJobEvent(env.DB, {
    jobId,
    requestId: payload.requestId ?? requestId,
    traceId: payload.traceId ?? job.traceId,
    eventType: "inference.callback.received",
    message:
      normalizedStatus === "failed"
        ? "Inference callback reported failure."
        : normalizedStatus === "cancelled"
          ? "Inference callback reported cancellation."
          : normalizedStatus === "processing"
            ? "Inference callback reported progress."
            : "Inference callback reported success.",
    payload,
    createdAt: now
  });

  console.info(
    JSON.stringify({
      requestId,
      jobId,
      traceId: payload.traceId ?? job.traceId,
      event: "inference.callback",
      status: normalizedStatus
    })
  );

  return jsonResponse(toCloudAnalysisJobResponse(patched, requestId, responseSchemaVersion), { status: 200 }, requestId);
}

async function handleHeartbeat(request: Request, env: Env, jobId: string, requestId: string): Promise<Response> {
  const callbackSecret = env.INFERENCE_SHARED_SECRET || env.CONTROL_PLANE_SHARED_SECRET;
  if (!isSharedSecretAuthorized(request.headers.get("x-hoops-inference-secret"), callbackSecret)) {
    return jsonResponse(
      {
        requestId,
        schemaVersion: null,
        confidence: null,
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
    return jsonResponse(
      {
        requestId,
        schemaVersion: null,
        confidence: null,
        errorCode: "job_not_found",
        errorMessage: "Cloud analysis job was not found.",
        failureReason: "Cloud analysis job was not found."
      },
      { status: 404 },
      requestId
    );
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

  console.info(
    JSON.stringify({
      requestId,
      jobId,
      traceId: job.traceId,
      event: "inference.heartbeat",
      status: "processing",
      progress: updated.progress
    })
  );

  return jsonResponse(toCloudAnalysisJobResponse(updated, requestId, updated.schemaVersion), { status: 200 }, requestId);
}

function normalizeInternalPath(pathname: string): string {
  if (pathname.startsWith("/v1/internal/")) {
    return pathname.replace(/^\/v1/, "");
  }
  return pathname;
}

function normalizeCallbackStatus(status: InferenceCallbackPayload["status"]): JobStatus {
  if (status === "succeeded") {
    return "completed";
  }
  return status;
}

function normalizeStoredStatus(status: JobStatus): JobStatus {
  if (status === "succeeded") {
    return "completed";
  }
  if (status === "expired") {
    return "cancelled";
  }
  return status;
}

function isTerminalStatus(status: JobStatus): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}

function buildCallbackPatch(
  job: JobRecord,
  status: JobStatus,
  timestamp: string,
  modelVersion: string | null,
  failureReason: string | null,
  resultConfidence: number | null,
  payload: InferenceCallbackPayload
): Partial<JobRecord> {
  const patch: Partial<JobRecord> = {
    status,
    schemaVersion: payload.schemaVersion ?? job.schemaVersion,
    stage:
      payload.stage ??
      (status === "failed"
        ? "Inference failed"
        : status === "cancelled"
          ? "Inference cancelled"
          : status === "processing"
            ? "Inference in progress"
            : "Inference complete"),
    progress:
      typeof payload.progress === "number"
        ? payload.progress
        : status === "processing"
          ? Math.max(job.progress, 0.85)
          : status === "failed"
            ? job.progress
            : 1,
    modelVersion,
    failureReason,
    resultConfidence,
    confidence: resultConfidence,
    results: payload.results ?? job.results ?? null,
    updatedAt: timestamp
  };

  if (status === "processing") {
    patch.startedAt = job.startedAt ?? timestamp;
  }
  if (status === "completed") {
    patch.finishedAt = timestamp;
  }
  if (status === "failed") {
    patch.finishedAt = timestamp;
  }
  if (status === "cancelled") {
    patch.cancelledAt = timestamp;
    patch.finishedAt = timestamp;
  }

  return patch;
}

function toCloudAnalysisJobResponse(
  job: JobRecord,
  requestId: string,
  schemaVersion: string | null
): CloudAnalysisJobResponse {
  return {
    requestId,
    schemaVersion: schemaVersion ?? job.schemaVersion,
    confidence: job.confidence ?? job.resultConfidence ?? null,
    modelVersion: job.modelVersion ?? null,
    failureReason: job.failureReason ?? null,
    jobId: job.jobId,
    status: job.status,
    progress: job.progress,
    stage: job.stage,
    errorCode: job.errorCode ?? null,
    errorMessage: job.errorMessage ?? null,
    analysisVersion: job.analysisVersion,
    results: job.results ?? null,
    sourceObjectKey: job.sourceObjectKey,
    resultObjectKey: job.resultObjectKey,
    createdAt: job.createdAt,
    uploadPendingAt: job.uploadPendingAt ?? null,
    uploadedAt: job.uploadedAt ?? null,
    queuedAt: job.queuedAt ?? null,
    startedAt: job.startedAt ?? null,
    finishedAt: job.finishedAt ?? null,
    cancelledAt: job.cancelledAt ?? null
  };
}
