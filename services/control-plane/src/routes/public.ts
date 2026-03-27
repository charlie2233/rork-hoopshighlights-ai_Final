import type { Env } from "../env";
import type {
  CloudAnalysisJobResponse,
  CreateCloudAnalysisJobRequest,
  CreateCloudAnalysisJobResponse,
  CreateCloudJobRequest,
  JobRecord,
  JobStatus,
  QueueJobMessage,
  StartCloudAnalysisJobRequest,
  StartCloudAnalysisJobResponse,
  UploadPresignResponse
} from "../types";
import { bootstrapJob, deleteJobState, getJobSnapshot, updateJobState } from "../do/job-state-client";
import { appendJobEvent } from "../db";
import { createPresignedUploadTarget } from "../r2/presign";
import { emptyResponse, jsonResponse, readJson } from "../utils/request-id";
import { resolveRuntimeConfig } from "../env";

export async function routePublicRequest(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
  requestId: string
): Promise<Response | null> {
  const url = new URL(request.url);
  const runtime = resolveRuntimeConfig(env);
  const route = normalizePublicPath(url.pathname);
  const isLegacyPresign = request.method === "POST" && url.pathname === "/v1/analysis/jobs";

  if (request.method === "POST" && (route === "/uploads/presign" || isLegacyPresign)) {
    return handlePresign(request, env, requestId, runtime.schemaVersion, url);
  }

  if (request.method === "POST" && route === "/jobs") {
    return handleFinalizeJob(request, env, requestId, runtime.schemaVersion, url, ctx);
  }

  const jobMatch = matchJobPath(route);
  if (!jobMatch) {
    return null;
  }

  if (request.method === "POST" && jobMatch.kind === "start") {
    const body = await readJson<StartCloudAnalysisJobRequest>(request);
    return handleFinalizeJob(
      request,
      env,
      requestId,
      runtime.schemaVersion,
      url,
      ctx,
      jobMatch.jobId,
      body.installId
    );
  }

  if (request.method === "GET") {
    return handleGetJob(env, requestId, jobMatch.jobId);
  }

  if (request.method === "DELETE") {
    return handleCancelJob(env, requestId, jobMatch.jobId);
  }

  return null;
}

async function handlePresign(
  request: Request,
  env: Env,
  requestId: string,
  schemaVersion: string,
  url: URL
): Promise<Response> {
  try {
    const body = await readJson<CreateCloudAnalysisJobRequest>(request);
    validateCreateRequest(body, resolveRuntimeConfig(env).maxFileSizeBytes, resolveRuntimeConfig(env).maxDurationSeconds);

    const jobId = crypto.randomUUID().replace(/-/g, "");
    const traceId = request.headers.get("x-trace-id")?.trim() || requestId;
    const upload = await createPresignedUploadTarget(env, {
      jobId,
      filename: body.filename,
      contentType: body.contentType,
      expiresInSeconds: resolveRuntimeConfig(env).signedUploadTtlSeconds
    });

    const now = new Date().toISOString();
    const record: JobRecord = {
      requestId,
      schemaVersion,
      confidence: null,
      modelVersion: null,
      failureReason: null,
      jobId,
      traceId,
      installId: body.installId,
      filename: body.filename,
      contentType: body.contentType,
      fileSizeBytes: body.fileSizeBytes,
      durationSeconds: body.durationSeconds,
      appVersion: body.appVersion,
      analysisVersion: body.analysisVersion,
      analysisMode: "cloud",
      status: "created",
      stage: "Created upload record",
      progress: 0,
      createdAt: now,
      uploadPendingAt: null,
      uploadedAt: null,
      queuedAt: null,
      startedAt: null,
      finishedAt: null,
      cancelledAt: null,
      errorCode: null,
      errorMessage: null,
      sourceObjectKey: upload.objectKey,
      resultObjectKey: `results/${jobId}/result.json`,
      uploadUrl: upload.uploadUrl,
      uploadMethod: upload.uploadMethod,
      uploadHeaders: upload.uploadHeaders,
      expiresAt: upload.expiresAt,
      updatedAt: now,
      resultConfidence: null,
      results: null,
      reviewState: "unreviewed",
      reviewerNotes: null,
      promotedToTrainingSet: false,
      quotaRemainingToday: 5
    };

    const bootstrap = await bootstrapJob(env, record);
    const uploadPendingAt = new Date().toISOString();
    const pendingJob = await updateJobState(
      env,
      bootstrap.jobId,
      {
        status: "upload_pending",
        stage: "Waiting for upload",
        progress: 0.08,
        uploadPendingAt,
        updatedAt: uploadPendingAt
      },
      {
        requestId,
        traceId,
        eventType: "job.upload_pending",
        message: "Upload presign created.",
        payload: {
          uploadUrl: upload.uploadUrl,
          sourceObjectKey: upload.objectKey,
          resultObjectKey: record.resultObjectKey
        }
      }
    );

    const response: UploadPresignResponse & CreateCloudAnalysisJobResponse = {
      requestId,
      schemaVersion,
      confidence: null,
      modelVersion: null,
      failureReason: null,
      jobId: pendingJob.jobId,
      sourceObjectKey: pendingJob.sourceObjectKey,
      resultObjectKey: pendingJob.resultObjectKey,
      uploadUrl: pendingJob.uploadUrl,
      uploadMethod: pendingJob.uploadMethod,
      uploadHeaders: pendingJob.uploadHeaders,
      expiresAt: pendingJob.expiresAt,
      status: pendingJob.status,
      analysisMode: "cloud",
      pollAfterSeconds: resolveRuntimeConfig(env).defaultPollAfterSeconds,
      quotaRemainingToday: pendingJob.quotaRemainingToday ?? 5
    };
    return jsonResponse(response, { status: 201 }, requestId);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid upload presign request.";
    return jsonResponse(
      {
        requestId,
        schemaVersion,
        confidence: null,
        modelVersion: null,
        errorCode: "invalid_request",
        errorMessage: message,
        failureReason: message
      },
      { status: 400 },
      requestId
    );
  }
}

async function handleFinalizeJob(
  request: Request,
  env: Env,
  requestId: string,
  schemaVersion: string,
  url: URL,
  ctx: ExecutionContext,
  pathJobId?: string,
  pathInstallId?: string
): Promise<Response> {
  try {
    const body = await readJson<CreateCloudJobRequest | StartCloudAnalysisJobRequest>(request);
    const jobId = pathJobId ?? ("jobId" in body ? body.jobId : undefined);
    const installId = pathInstallId ?? ("installId" in body ? body.installId : undefined);
    const requestedSourceObjectKey = "sourceObjectKey" in body ? body.sourceObjectKey : undefined;
    const requestedResultObjectKey = "resultObjectKey" in body ? body.resultObjectKey : undefined;

    if (!jobId || !installId) {
      return jsonResponse(
        {
          requestId,
          schemaVersion,
          confidence: null,
          modelVersion: null,
          errorCode: "invalid_request",
          errorMessage: "jobId and installId are required.",
          failureReason: "jobId and installId are required."
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
          schemaVersion,
          confidence: null,
          modelVersion: null,
          errorCode: "job_not_found",
          errorMessage: "Cloud analysis job was not found.",
          failureReason: "Cloud analysis job was not found."
        },
        { status: 404 },
        requestId
      );
    }

    if (job.installId !== installId) {
      return jsonResponse(
        {
          requestId,
          schemaVersion,
          confidence: null,
          modelVersion: job.modelVersion ?? null,
          errorCode: "install_mismatch",
          errorMessage: "Install ID does not own this analysis job.",
          failureReason: "Install ID does not own this analysis job."
        },
        { status: 403 },
        requestId
      );
    }

    if (requestedSourceObjectKey && requestedSourceObjectKey !== job.sourceObjectKey) {
      return jsonResponse(
        {
          requestId,
          schemaVersion,
          confidence: null,
          modelVersion: job.modelVersion ?? null,
          errorCode: "source_mismatch",
          errorMessage: "Source object key does not match the presigned upload.",
          failureReason: "Source object key does not match the presigned upload."
        },
        { status: 400 },
        requestId
      );
    }
    if (requestedResultObjectKey && requestedResultObjectKey !== job.resultObjectKey) {
      return jsonResponse(
        {
          requestId,
          schemaVersion,
          confidence: null,
          modelVersion: job.modelVersion ?? null,
          errorCode: "result_mismatch",
          errorMessage: "Result object key does not match the job record.",
          failureReason: "Result object key does not match the job record."
        },
        { status: 400 },
        requestId
      );
    }

    if (isTerminal(job.status) || job.status === "queued" || job.status === "processing") {
      return jsonResponse(toCloudAnalysisJobResponse(job, requestId, schemaVersion), { status: 200 }, requestId);
    }

    const uploadExists = await env.R2_UPLOADS.head(job.sourceObjectKey);
    if (!uploadExists) {
      return jsonResponse(
        {
          requestId,
          schemaVersion,
          confidence: null,
          modelVersion: job.modelVersion ?? null,
          errorCode: "upload_missing",
          errorMessage: "Upload is missing. Complete the signed upload before starting analysis.",
          failureReason: "Upload is missing. Complete the signed upload before starting analysis."
        },
        { status: 400 },
        requestId
      );
    }

    const uploadedAt = job.uploadedAt ?? new Date().toISOString();
    const uploadedJob = job.status === "uploaded"
      ? job
      : await updateJobState(
          env,
          job.jobId,
          {
            status: "uploaded",
            stage: "Upload verified",
            progress: Math.max(job.progress, 0.35),
            uploadedAt,
            updatedAt: uploadedAt
          },
          {
            requestId,
            traceId: job.traceId,
            eventType: "job.uploaded",
            message: "Upload verified before queue dispatch.",
            payload: {
              sourceObjectKey: job.sourceObjectKey,
              resultObjectKey: job.resultObjectKey
            }
          }
        );

    if (uploadedJob.queuedAt == null) {
      const queuedAt = new Date().toISOString();
      const queueMessage: QueueJobMessage = {
        kind: "process-job",
        jobId: uploadedJob.jobId,
        requestId,
        schemaVersion,
        installId: uploadedJob.installId,
        analysisVersion: uploadedJob.analysisVersion,
        sourceObjectKey: uploadedJob.sourceObjectKey,
        resultObjectKey: uploadedJob.resultObjectKey,
        callbackUrl: new URL("/internal/inference/callback", url.origin).toString(),
        uploadUrl: uploadedJob.uploadUrl
      };

      const queuedJob = await updateJobState(
        env,
        uploadedJob.jobId,
        {
          status: "queued",
          stage: "Queued for inference",
          progress: Math.max(uploadedJob.progress, 0.45),
          queuedAt,
          updatedAt: queuedAt
        },
        {
          requestId,
          traceId: uploadedJob.traceId,
          eventType: "job.queued",
          message: "Job queued for inference dispatch.",
          payload: queueMessage
        }
      );

      ctx.waitUntil(
        env.ANALYSIS_QUEUE
          .send(queueMessage)
          .catch(async (error) => {
            await appendJobEvent(env.DB, {
              jobId: queuedJob.jobId,
              requestId,
              traceId: queuedJob.traceId,
              eventType: "job.queue_dispatch_failed",
              message: error instanceof Error ? error.message : "Queue dispatch failed.",
              payload: queueMessage,
              createdAt: new Date().toISOString()
            });
          })
      );

      return jsonResponse(toCloudAnalysisJobResponse(queuedJob, requestId, schemaVersion), { status: 200 }, requestId);
    }

    return jsonResponse(toCloudAnalysisJobResponse(uploadedJob, requestId, schemaVersion), { status: 200 }, requestId);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid job request.";
    return jsonResponse(
      {
        requestId,
        schemaVersion,
        confidence: null,
        modelVersion: null,
        errorCode: "invalid_request",
        errorMessage: message,
        failureReason: message
      },
      { status: 400 },
      requestId
    );
  }
}

async function handleGetJob(env: Env, requestId: string, jobId: string): Promise<Response> {
  const job = await getJobSnapshot(env, jobId);
  if (!job) {
    return jsonResponse(
      {
        requestId,
        schemaVersion: null,
        confidence: null,
        modelVersion: null,
        errorCode: "job_not_found",
        errorMessage: "Cloud analysis job was not found.",
        failureReason: "Cloud analysis job was not found."
      },
      { status: 404 },
      requestId
    );
  }

  const hydrated = await hydrateResultIfNeeded(env, job);
  return jsonResponse(toCloudAnalysisJobResponse(hydrated, requestId, hydrated.schemaVersion), { status: 200 }, requestId);
}

async function handleCancelJob(env: Env, requestId: string, jobId: string): Promise<Response> {
  const deleted = await deleteJobState(env, jobId);
  if (!deleted) {
    return jsonResponse(
      {
        requestId,
        schemaVersion: null,
        confidence: null,
        modelVersion: null,
        errorCode: "job_not_found",
        errorMessage: "Cloud analysis job was not found.",
        failureReason: "Cloud analysis job was not found."
      },
      { status: 404 },
      requestId
    );
  }
  await env.R2_UPLOADS.delete(deleted.sourceObjectKey);
  await env.R2_RESULTS.delete(deleted.resultObjectKey);
  return emptyResponse(204, requestId);
}

function validateCreateRequest(
  body: CreateCloudAnalysisJobRequest,
  maxFileSizeBytes: number,
  maxDurationSeconds: number
): void {
  if (!body.filename || !body.contentType || !body.installId || !body.appVersion || !body.analysisVersion) {
    throw new Error("Invalid upload presign request.");
  }
  if (body.fileSizeBytes <= 0 || body.fileSizeBytes > maxFileSizeBytes) {
    throw new Error("File size exceeds control plane limits.");
  }
  if (body.durationSeconds <= 0 || body.durationSeconds > maxDurationSeconds) {
    throw new Error("Duration exceeds control plane limits.");
  }
}

function normalizePublicPath(pathname: string): string {
  if (pathname.startsWith("/v1/analysis/")) {
    return pathname.replace(/^\/v1\/analysis/, "");
  }
  if (pathname.startsWith("/v1/")) {
    return pathname.replace(/^\/v1/, "");
  }
  return pathname;
}

function matchJobPath(pathname: string): { jobId: string; kind: "get" | "delete" | "start" } | null {
  const startMatch = pathname.match(/^\/jobs\/([^/]+)\/start$/);
  if (startMatch) {
    return { jobId: startMatch[1]!, kind: "start" };
  }

  const jobMatch = pathname.match(/^\/jobs\/([^/]+)$/);
  if (!jobMatch) {
    return null;
  }

  return { jobId: jobMatch[1]!, kind: "get" };
}

function isTerminal(status: JobStatus): boolean {
  return status === "completed" || status === "failed" || status === "cancelled" || status === "succeeded" || status === "expired";
}

async function hydrateResultIfNeeded(env: Env, job: JobRecord): Promise<JobRecord> {
  if (job.results || !isTerminal(job.status)) {
    return job;
  }

  const stored = await env.R2_RESULTS.get(job.resultObjectKey);
  if (!stored) {
    return job;
  }

  const text = await stored.text();
  if (!text) {
    return job;
  }

  try {
    const parsed = JSON.parse(text) as JobRecord["results"] | { results?: JobRecord["results"] };
    const result = isResultPayload(parsed) ? parsed : parsed.results ?? null;
    if (!result) {
      return job;
    }
    return {
      ...job,
      results: result,
      resultConfidence: result.resultConfidence ?? job.resultConfidence ?? null,
      confidence: result.confidence ?? result.resultConfidence ?? job.confidence ?? job.resultConfidence ?? null,
      modelVersion: result.modelVersion ?? job.modelVersion ?? null,
      failureReason: result.failureReason ?? job.failureReason ?? null
    };
  } catch {
    return job;
  }
}

function isResultPayload(value: unknown): value is JobRecord["results"] {
  return value !== null && typeof value === "object" && "clipCount" in value && "clips" in value;
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
