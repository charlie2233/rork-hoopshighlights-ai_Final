import type { Env } from "../env";
import type { CloudAnalysisJobResponse, CloudAnalysisResult, CloudClip, InferenceCallbackPayload, JobRecord, JobStatus } from "../types";
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
  const normalizedResult = normalizeCallbackResult(payload, requestId);
  const resultConfidence =
    payload.confidence ??
    payload.resultConfidence ??
    normalizedResult?.resultConfidence ??
    job.resultConfidence ??
    null;
  const failureReason = payload.failureReason ?? job.failureReason ?? null;
  const modelVersion = payload.modelVersion ?? job.modelVersion ?? null;
  const responseSchemaVersion = payload.schemaVersion ?? job.schemaVersion;
  const incomingAttemptId = payload.inferenceAttemptId ?? null;
  const currentAttemptId = job.inferenceAttemptId ?? null;
  const now = new Date().toISOString();

  if (currentAttemptId && incomingAttemptId && incomingAttemptId !== currentAttemptId) {
    console.info(
      JSON.stringify({
        requestId,
        jobId,
        traceId: payload.traceId ?? job.traceId,
        uploadTraceId: payload.uploadTraceId ?? job.uploadTraceId ?? null,
        inferenceAttemptId: incomingAttemptId,
        currentInferenceAttemptId: currentAttemptId,
        event: "inference.callback.stale_attempt",
        status: currentStatus
      })
    );
    return jsonResponse(toCloudAnalysisJobResponse(job, requestId, responseSchemaVersion), { status: 200 }, requestId);
  }

  if (isTerminalStatus(currentStatus) && normalizedStatus !== currentStatus) {
    console.warn(
      JSON.stringify({
        requestId,
        jobId,
        traceId: payload.traceId ?? job.traceId,
        uploadTraceId: payload.uploadTraceId ?? job.uploadTraceId ?? null,
        inferenceAttemptId: payload.inferenceAttemptId ?? job.inferenceAttemptId ?? null,
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
        uploadTraceId: payload.uploadTraceId ?? job.uploadTraceId ?? null,
        inferenceAttemptId: payload.inferenceAttemptId ?? job.inferenceAttemptId ?? null,
        event: "inference.callback.duplicate",
        status: currentStatus
      })
    );
    return jsonResponse(toCloudAnalysisJobResponse(job, requestId, responseSchemaVersion), { status: 200 }, requestId);
  }

  if (normalizedResult && (!isTerminalStatus(currentStatus) || normalizedStatus === currentStatus || !job.results)) {
    await env.R2_RESULTS.put(job.resultObjectKey, JSON.stringify(normalizedResult), {
      httpMetadata: {
        contentType: "application/json; charset=utf-8"
      }
    });
  }

  const patched = await updateJobState(
    env,
    jobId,
    buildCallbackPatch(job, normalizedStatus, now, modelVersion, failureReason, resultConfidence, normalizedResult, payload),
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
      uploadTraceId: payload.uploadTraceId ?? job.uploadTraceId ?? null,
      inferenceAttemptId: payload.inferenceAttemptId ?? job.inferenceAttemptId ?? null,
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
      acceptedAt: job.acceptedAt ?? startedAt,
      startedAt,
      processingStartedAt: startedAt,
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
      uploadTraceId: job.uploadTraceId ?? null,
      inferenceAttemptId: job.inferenceAttemptId ?? null,
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
  normalizedResult: CloudAnalysisResult | null,
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
    attemptCount: resolveAttemptCount(job.attemptCount ?? 0, payload.attemptCount),
    results: normalizedResult ?? job.results ?? null,
    uploadTraceId: payload.uploadTraceId ?? job.uploadTraceId ?? null,
    inferenceAttemptId: payload.inferenceAttemptId ?? job.inferenceAttemptId ?? null,
    updatedAt: timestamp
  };

  if (status === "processing") {
    patch.startedAt = job.startedAt ?? timestamp;
    patch.acceptedAt = job.acceptedAt ?? timestamp;
    patch.processingStartedAt = job.processingStartedAt ?? timestamp;
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

function resolveAttemptCount(current: number, incoming: number | null | undefined): number {
  const normalizedCurrent = Math.max(0, Math.floor(current));
  if (typeof incoming === "number" && Number.isFinite(incoming)) {
    return Math.max(normalizedCurrent, Math.max(0, Math.floor(incoming)));
  }
  return normalizedCurrent;
}

function normalizeCallbackResult(payload: InferenceCallbackPayload, requestId: string): CloudAnalysisResult | null {
  if (isCloudAnalysisResult(payload.results)) {
    return payload.results;
  }

  const manifest = (payload as InferenceCallbackPayload & { result?: unknown }).result;
  if (!isInferenceManifest(manifest)) {
    return null;
  }

  const clips = manifest.clips.map(normalizeManifestClip);
  const backendModelVersion = coerceString(manifest.modelVersion) ?? payload.modelVersion ?? "unknown";
  const resultConfidence =
    payload.resultConfidence ??
    payload.confidence ??
    coerceNumber(manifest.resultConfidence) ??
    (clips.length ? clips.reduce((sum, clip) => sum + clip.confidence, 0) / clips.length : 0);

  return {
    requestId: payload.requestId ?? requestId,
    confidence: resultConfidence,
    modelVersion: backendModelVersion,
    failureReason: coerceString(manifest.failureReason) ?? payload.failureReason ?? null,
    clipCount: clips.length,
    clips,
    diagnostics: {
      processingMs: 0,
      backendModelVersion,
      usedVideoIntelligence: false,
      usedGeminiRelabeling: false,
      candidateSegments: clips.length,
      finalSegments: clips.length
    },
    resultConfidence
  };
}

function normalizeManifestClip(value: InferenceManifestClipLike): CloudClip {
  const startTime = coerceNumber(value.startTime) ?? 0;
  const endTime = Math.max(coerceNumber(value.endTime) ?? startTime, startTime);
  const confidence = clamp01(coerceNumber(value.confidence) ?? coerceNumber(value.resultConfidence) ?? 0);
  const label = coerceString(value.label) ?? coerceString(value.action) ?? "Unknown";
  const action = coerceString(value.action) ?? label;

  return {
    startTime,
    endTime,
    confidence,
    label,
    action,
    canonicalLabel: coerceString(value.canonicalLabel) ?? null,
    eventFamily: coerceString(value.eventFamily) ?? null,
    eventSubtype: coerceString(value.eventSubtype) ?? null,
    shotSubtype: coerceString(value.shotSubtype) ?? null,
    outcome: normalizeOutcome(value.outcome),
    audioScore: clamp01(coerceNumber(value.audioScore) ?? 0),
    visualScore: clamp01(coerceNumber(value.visualScore) ?? 0),
    motionScore: clamp01(coerceNumber(value.motionScore) ?? 0),
    combinedScore: clamp01(coerceNumber(value.combinedScore) ?? confidence),
    confidenceBeforeMapping: coerceNumber(value.confidenceBeforeMapping) ?? null,
    confidenceAfterMapping: coerceNumber(value.confidenceAfterMapping) ?? null,
    eventFamilyConfidenceBeforeMapping: coerceNumber(value.eventFamilyConfidenceBeforeMapping) ?? null,
    eventFamilyConfidenceAfterMapping: coerceNumber(value.eventFamilyConfidenceAfterMapping) ?? null,
    shotSubtypeConfidenceBeforeMapping: coerceNumber(value.shotSubtypeConfidenceBeforeMapping) ?? null,
    shotSubtypeConfidenceAfterMapping: coerceNumber(value.shotSubtypeConfidenceAfterMapping) ?? null,
    outcomeConfidenceBeforeMapping: coerceNumber(value.outcomeConfidenceBeforeMapping) ?? null,
    outcomeConfidenceAfterMapping: coerceNumber(value.outcomeConfidenceAfterMapping) ?? null,
    detectionMethod: coerceString(value.detectionMethod) === "heuristic" ? "heuristic" : "cloud",
    shouldAutoKeep: coerceBoolean(value.shouldAutoKeep) ?? confidence >= 0.7,
    shouldEnableSlowMotion: coerceBoolean(value.shouldEnableSlowMotion) ?? false,
    isUncertain: coerceBoolean(value.isUncertain) ?? null,
    promptSetVersion: coerceString(value.promptSetVersion) ?? null,
    eventType: coerceString(value.eventType) ?? null,
    shotType: coerceString(value.shotType) ?? null,
    makeMiss: normalizeMakeMiss(value.makeMiss),
    rankScore: coerceNumber(value.rankScore) ?? null,
    reviewState: coerceString(value.reviewState) ?? null,
    reviewerNotes: coerceString(value.reviewerNotes) ?? null,
    topLabels: normalizeLabelScores(value.topLabels),
    comparisonTopLabels: normalizeLabelScores(value.comparisonTopLabels),
    rawTopLabels: normalizeRawLabelScores(value.rawTopLabels),
    comparisonRawTopLabels: normalizeRawLabelScores(value.comparisonRawTopLabels)
  };
}

function isCloudAnalysisResult(value: unknown): value is CloudAnalysisResult {
  return value !== null && typeof value === "object" && "clipCount" in value && "clips" in value;
}

type InferenceManifestLike = {
  modelVersion?: unknown;
  resultConfidence?: unknown;
  failureReason?: unknown;
  clips: InferenceManifestClipLike[];
};

type InferenceManifestClipLike = {
  startTime?: unknown;
  endTime?: unknown;
  confidence?: unknown;
  resultConfidence?: unknown;
  label?: unknown;
  action?: unknown;
  canonicalLabel?: unknown;
  eventFamily?: unknown;
  eventSubtype?: unknown;
  shotSubtype?: unknown;
  outcome?: unknown;
  audioScore?: unknown;
  visualScore?: unknown;
  motionScore?: unknown;
  combinedScore?: unknown;
  confidenceBeforeMapping?: unknown;
  confidenceAfterMapping?: unknown;
  eventFamilyConfidenceBeforeMapping?: unknown;
  eventFamilyConfidenceAfterMapping?: unknown;
  shotSubtypeConfidenceBeforeMapping?: unknown;
  shotSubtypeConfidenceAfterMapping?: unknown;
  outcomeConfidenceBeforeMapping?: unknown;
  outcomeConfidenceAfterMapping?: unknown;
  detectionMethod?: unknown;
  shouldAutoKeep?: unknown;
  shouldEnableSlowMotion?: unknown;
  isUncertain?: unknown;
  promptSetVersion?: unknown;
  eventType?: unknown;
  shotType?: unknown;
  makeMiss?: unknown;
  rankScore?: unknown;
  reviewState?: unknown;
  reviewerNotes?: unknown;
  topLabels?: unknown;
  comparisonTopLabels?: unknown;
  rawTopLabels?: unknown;
  comparisonRawTopLabels?: unknown;
};

function isInferenceManifest(value: unknown): value is InferenceManifestLike {
  return value !== null && typeof value === "object" && Array.isArray((value as { clips?: unknown }).clips);
}

function normalizeMakeMiss(value: unknown): "make" | "miss" | "unknown" | null {
  if (value === "make" || value === "miss" || value === "unknown") {
    return value;
  }
  if (value === "made") {
    return "make";
  }
  if (value === "missed") {
    return "miss";
  }
  return null;
}

function normalizeOutcome(value: unknown): "made" | "missed" | "blocked" | "uncertain" | null {
  if (value === "made" || value === "missed" || value === "blocked" || value === "uncertain") {
    return value;
  }
  return null;
}

function normalizeLabelScores(value: unknown): CloudClip["topLabels"] {
  if (!Array.isArray(value)) {
    return null;
  }
  const scores: NonNullable<CloudClip["topLabels"]> = [];
  for (const entry of value) {
    if (entry === null || typeof entry !== "object") {
      continue;
    }
    scores.push({
      label: coerceString((entry as { label?: unknown }).label) ?? "unknown",
      confidence: clamp01(coerceNumber((entry as { confidence?: unknown }).confidence) ?? 0),
      rawLabel: coerceString((entry as { rawLabel?: unknown }).rawLabel) ?? null,
      modelVersion: coerceString((entry as { modelVersion?: unknown }).modelVersion) ?? null
    });
  }
  return scores;
}

function normalizeRawLabelScores(value: unknown): CloudClip["rawTopLabels"] {
  if (!Array.isArray(value)) {
    return null;
  }
  const scores: NonNullable<CloudClip["rawTopLabels"]> = [];
  for (const entry of value) {
    if (entry === null || typeof entry !== "object") {
      continue;
    }
    const rawLabel = coerceString((entry as { rawLabel?: unknown }).rawLabel);
    if (!rawLabel) {
      continue;
    }
    scores.push({
      rawLabel,
      confidence: clamp01(coerceNumber((entry as { confidence?: unknown }).confidence) ?? 0),
      canonicalLabel: coerceString((entry as { canonicalLabel?: unknown }).canonicalLabel) ?? null,
      modelVersion: coerceString((entry as { modelVersion?: unknown }).modelVersion) ?? null
    });
  }
  return scores;
}

function coerceString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function coerceNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function coerceBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function clamp01(value: number): number {
  return Math.min(Math.max(value, 0), 1);
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
    uploadTraceId: job.uploadTraceId ?? null,
    inferenceAttemptId: job.inferenceAttemptId ?? null,
    acceptedAt: job.acceptedAt ?? null,
    processingStartedAt: job.processingStartedAt ?? null,
    attemptCount: job.attemptCount ?? 0,
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
