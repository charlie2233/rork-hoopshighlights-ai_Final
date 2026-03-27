import type { Env } from "../env";
import type {
  CreateCloudAnalysisJobRequest,
  CreateCloudAnalysisJobResponse,
  CloudAnalysisJobResponse,
  JobRecord,
  StartCloudAnalysisJobRequest,
  StartCloudAnalysisJobResponse,
  QueueJobMessage
} from "../types";
import { bootstrapJob, deleteJobState, getJobSnapshot, updateJobState } from "../do/job-state-client";
import { createPresignedUploadTarget } from "../r2/presign";
import { readJson, jsonResponse, emptyResponse } from "../utils/request-id";
import { resolveRuntimeConfig } from "../env";

export async function routePublicRequest(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
  requestId: string
): Promise<Response | null> {
  const url = new URL(request.url);
  if (!url.pathname.startsWith("/v1/analysis/")) {
    return null;
  }

  const runtime = resolveRuntimeConfig(env);

  if (request.method === "POST" && url.pathname === "/v1/analysis/jobs") {
    try {
      const body = await readJson<CreateCloudAnalysisJobRequest>(request);
      validateCreateRequest(body, runtime.maxFileSizeBytes, runtime.maxDurationSeconds);

      const jobId = crypto.randomUUID().replace(/-/g, "");
      const upload = await createPresignedUploadTarget(env, {
        jobId,
        filename: body.filename,
        contentType: body.contentType,
        expiresInSeconds: runtime.signedUploadTtlSeconds
      });

      const now = new Date().toISOString();
      const record: JobRecord = {
        requestId,
        jobId,
        traceId: request.headers.get("x-trace-id")?.trim() || requestId,
        installId: body.installId,
        filename: body.filename,
        contentType: body.contentType,
        fileSizeBytes: body.fileSizeBytes,
        durationSeconds: body.durationSeconds,
        appVersion: body.appVersion,
        analysisVersion: body.analysisVersion,
        analysisMode: "cloud",
        status: "created",
        stage: "Preparing upload",
        progress: 0,
        sourceObjectKey: upload.objectKey,
        resultObjectKey: `results/${jobId}/result.json`,
        uploadUrl: upload.uploadUrl,
        uploadMethod: upload.uploadMethod,
        uploadHeaders: upload.uploadHeaders,
        expiresAt: upload.expiresAt,
        createdAt: now,
        updatedAt: now,
        modelVersion: null,
        failureReason: null,
        resultConfidence: null,
        results: null,
        reviewState: "unreviewed",
        reviewerNotes: null,
        promotedToTrainingSet: false,
        quotaRemainingToday: 5
      };

      const bootstrap = await bootstrapJob(env, record);
      const response: CreateCloudAnalysisJobResponse = {
        requestId,
        modelVersion: bootstrap.modelVersion ?? null,
        failureReason: bootstrap.failureReason ?? null,
        jobId: bootstrap.jobId,
        uploadUrl: bootstrap.uploadUrl,
        uploadMethod: bootstrap.uploadMethod,
        uploadHeaders: bootstrap.uploadHeaders,
        expiresAt: bootstrap.expiresAt,
        pollAfterSeconds: runtime.defaultPollAfterSeconds,
        quotaRemainingToday: bootstrap.quotaRemainingToday ?? 5,
        analysisMode: "cloud"
      };
      return jsonResponse(response, { status: 201 }, requestId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Invalid create job request.";
      return jsonResponse(
        {
          requestId,
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

  const jobMatch = matchJobPath(url.pathname);
  if (!jobMatch) {
    return null;
  }

  if (request.method === "POST" && jobMatch.kind === "start") {
    const body = await readJson<StartCloudAnalysisJobRequest>(request);
    const job = await getJobSnapshot(env, jobMatch.jobId);
    if (!job) {
      return jsonResponse({ requestId, errorCode: "job_not_found", errorMessage: "Cloud analysis job was not found." }, { status: 404 }, requestId);
    }
    if (job.installId !== body.installId) {
      return jsonResponse({ requestId, errorCode: "install_mismatch", errorMessage: "Install ID does not own this analysis job." }, { status: 403 }, requestId);
    }
    if (job.status !== "created") {
      const response: StartCloudAnalysisJobResponse = {
        requestId,
        modelVersion: job.modelVersion ?? null,
        failureReason: job.failureReason ?? null,
        jobId: job.jobId,
        status: job.status
      };
      return jsonResponse(response, { status: 200 }, requestId);
    }

    const uploadExists = await env.R2_UPLOADS.head(job.sourceObjectKey);
    if (!uploadExists) {
      return jsonResponse(
        {
          requestId,
          errorCode: "upload_missing",
          errorMessage: "Upload is missing. Complete the signed upload before starting analysis.",
          failureReason: "Upload is missing. Complete the signed upload before starting analysis."
        },
        { status: 400 },
        requestId
      );
    }

    const queuedAt = new Date().toISOString();
    const queuedJob = await updateJobState(
      env,
      job.jobId,
      {
        status: "queued",
        stage: "Queued on server",
        progress: Math.max(job.progress, 0.28),
        queuedAt,
        updatedAt: queuedAt
      },
      {
        requestId,
        traceId: job.traceId,
        eventType: "job.queued",
        message: "Job queued for inference dispatch.",
        payload: body
      }
    );

    const queueMessage: QueueJobMessage = {
      kind: "process-job",
      jobId: queuedJob.jobId,
      requestId,
      installId: queuedJob.installId,
      analysisVersion: queuedJob.analysisVersion,
      sourceObjectKey: queuedJob.sourceObjectKey,
      resultObjectKey: queuedJob.resultObjectKey,
      callbackUrl: new URL(`/v1/internal/inference/callback/${queuedJob.jobId}`, url.origin).toString()
    };

    ctx.waitUntil(env.ANALYSIS_QUEUE.send(queueMessage));

    const response: StartCloudAnalysisJobResponse = {
      requestId,
      modelVersion: queuedJob.modelVersion ?? null,
      failureReason: queuedJob.failureReason ?? null,
      jobId: queuedJob.jobId,
      status: queuedJob.status
    };
    return jsonResponse(response, { status: 200 }, requestId);
  }

  if (request.method === "GET") {
    const job = await getJobSnapshot(env, jobMatch.jobId);
    if (!job) {
      return jsonResponse({ requestId, errorCode: "job_not_found", errorMessage: "Cloud analysis job was not found." }, { status: 404 }, requestId);
    }
    const response: CloudAnalysisJobResponse = toCloudAnalysisJobResponse(job, requestId);
    return jsonResponse(response, { status: 200 }, requestId);
  }

  if (request.method === "DELETE") {
    const deleted = await deleteJobState(env, jobMatch.jobId);
    if (!deleted) {
      return jsonResponse({ requestId, errorCode: "job_not_found", errorMessage: "Cloud analysis job was not found." }, { status: 404 }, requestId);
    }
    await env.R2_UPLOADS.delete(deleted.sourceObjectKey);
    await env.R2_RESULTS.delete(deleted.resultObjectKey);
    return emptyResponse(204, requestId);
  }

  return null;
}

function validateCreateRequest(
  body: CreateCloudAnalysisJobRequest,
  maxFileSizeBytes: number,
  maxDurationSeconds: number
): void {
  if (!body.filename || !body.contentType || !body.installId || !body.appVersion || !body.analysisVersion) {
    throw new Error("Invalid create job request.");
  }
  if (body.fileSizeBytes <= 0 || body.fileSizeBytes > maxFileSizeBytes) {
    throw new Error("File size exceeds control plane limits.");
  }
  if (body.durationSeconds <= 0 || body.durationSeconds > maxDurationSeconds) {
    throw new Error("Duration exceeds control plane limits.");
  }
}

function matchJobPath(pathname: string): { jobId: string; kind: "get" | "delete" | "start" } | null {
  const startMatch = pathname.match(/^\/v1\/analysis\/jobs\/([^/]+)\/start$/);
  if (startMatch) {
    return { jobId: startMatch[1]!, kind: "start" };
  }

  const jobMatch = pathname.match(/^\/v1\/analysis\/jobs\/([^/]+)$/);
  if (!jobMatch) {
    return null;
  }

  return { jobId: jobMatch[1]!, kind: "get" };
}

function toCloudAnalysisJobResponse(job: JobRecord, requestId: string): CloudAnalysisJobResponse {
  return {
    requestId,
    modelVersion: job.modelVersion ?? null,
    failureReason: job.failureReason ?? null,
    jobId: job.jobId,
    status: job.status,
    progress: job.progress,
    stage: job.stage,
    errorCode: job.errorCode ?? null,
    errorMessage: job.errorMessage ?? null,
    analysisVersion: job.analysisVersion,
    results: job.results ?? null
  };
}
