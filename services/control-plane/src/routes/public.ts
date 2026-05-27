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
  TeamSelection,
  UploadPresignResponse
} from "../types";
import { bootstrapJob, deleteJobState, getJobSnapshot, updateJobState } from "../do/job-state-client";
import { appendJobEvent } from "../db";
import {
  createEditingEditJob,
  createEditingRenderJob,
  getEditingRenderDownloadUrl,
  getEditingVersion,
  getEditingDownloadUrl,
  getEditingEditJob,
  getEditingEditPlan,
  getEditingRenderJob,
  getEditingRevision,
  listEditingRenderJobs,
  listEditingRevisions,
  renderEditingRevision,
  reviseEditingEditJob
} from "../editing/client";
import { createPresignedUploadTarget } from "../r2/presign";
import { emptyResponse, jsonResponse, readJson } from "../utils/request-id";
import { resolveRuntimeConfig } from "../env";
import { recoverStaleProcessingJob } from "../recovery";

const DEFAULT_FREE_DAILY_QUOTA = 3;

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

  if (request.method === "GET" && route === "/editing/version") {
    return getEditingVersion(env, requestId);
  }

  if (request.method === "POST" && (route === "/uploads/presign" || isLegacyPresign)) {
    return handlePresign(request, env, requestId, runtime.schemaVersion, url);
  }

  if (request.method === "POST" && route === "/jobs") {
    return handleFinalizeJob(request, env, ctx, requestId, runtime.schemaVersion, url);
  }

  if (request.method === "POST" && route === "/edit-jobs") {
    const body = await readJson(request);
    return createEditingEditJob(env, requestId, body as never);
  }

  if (request.method === "GET" && route === "/render-jobs") {
    return listEditingRenderJobs(env, requestId, url.searchParams.get("installId"), url.searchParams.get("limit"));
  }

  const renderJobMatch = matchRenderJobPath(route);
  if (renderJobMatch) {
    if (request.method === "GET" && renderJobMatch.kind === "download-url") {
      return getEditingRenderDownloadUrl(env, renderJobMatch.renderJobId, requestId, url.searchParams.get("installId"));
    }
  }

  const editRevisionMatch = matchEditRevisionPath(route);
  if (editRevisionMatch) {
    if (request.method === "POST" && editRevisionMatch.kind === "revise") {
      const body = await readJson(request);
      return reviseEditingEditJob(env, editRevisionMatch.editJobId, requestId, body as never);
    }
    if (request.method === "GET" && editRevisionMatch.kind === "list") {
      return listEditingRevisions(env, editRevisionMatch.editJobId, requestId, url.searchParams.get("installId"));
    }
    if (request.method === "GET" && editRevisionMatch.kind === "get" && editRevisionMatch.revisionId) {
      return getEditingRevision(env, editRevisionMatch.editJobId, editRevisionMatch.revisionId, requestId, url.searchParams.get("installId"));
    }
    if (request.method === "POST" && editRevisionMatch.kind === "render" && editRevisionMatch.revisionId) {
      const body = await readJson(request);
      return renderEditingRevision(env, editRevisionMatch.editJobId, editRevisionMatch.revisionId, requestId, body as never);
    }
  }

  const editRenderMatch = matchEditRenderPath(route);
  if (editRenderMatch) {
    if (request.method === "POST" && editRenderMatch.kind === "render") {
      const body = await readJson(request);
      return createEditingRenderJob(env, editRenderMatch.editJobId, requestId, body as never);
    }
    if (request.method === "GET" && editRenderMatch.kind === "render-status") {
      return getEditingRenderJob(env, editRenderMatch.editJobId, requestId, url.searchParams.get("installId"));
    }
    if (request.method === "GET" && editRenderMatch.kind === "download-url") {
      return getEditingDownloadUrl(env, editRenderMatch.editJobId, requestId, url.searchParams.get("installId"));
    }
  }

  const editJobMatch = matchEditJobPath(route);
  if (editJobMatch) {
    if (request.method === "GET" && editJobMatch.kind === "job") {
      return getEditingEditJob(env, editJobMatch.editJobId, requestId, url.searchParams.get("installId"));
    }
    if (request.method === "GET" && editJobMatch.kind === "plan") {
      return getEditingEditPlan(env, editJobMatch.editJobId, requestId, url.searchParams.get("installId"));
    }
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
      ctx,
      requestId,
      runtime.schemaVersion,
      url,
      jobMatch.jobId,
      body.installId,
      body
    );
  }

  if (request.method === "GET") {
    return handleGetJob(env, ctx, requestId, jobMatch.jobId);
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
    const teamSelection = normalizeTeamSelection(body.teamSelection);

    const jobId = crypto.randomUUID().replace(/-/g, "");
    const traceId = request.headers.get("x-trace-id")?.trim() || requestId;
    const uploadTraceId = crypto.randomUUID().replace(/-/g, "");
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
      uploadTraceId,
      inferenceAttemptId: null,
      acceptedAt: null,
      processingStartedAt: null,
      attemptCount: 0,
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
      teamSelection,
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
      quotaRemainingToday: DEFAULT_FREE_DAILY_QUOTA
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
          resultObjectKey: record.resultObjectKey,
          uploadTraceId
        }
      }
    );

    const response: UploadPresignResponse & CreateCloudAnalysisJobResponse = {
      requestId,
      schemaVersion,
      confidence: null,
      modelVersion: null,
      failureReason: null,
      uploadTraceId,
      inferenceAttemptId: null,
      jobId,
      sourceObjectKey: upload.objectKey,
      resultObjectKey: record.resultObjectKey,
      uploadUrl: upload.uploadUrl,
      uploadMethod: upload.uploadMethod,
      uploadHeaders: upload.uploadHeaders,
      expiresAt: upload.expiresAt,
      status: "upload_pending",
      analysisMode: "cloud",
      pollAfterSeconds: resolveRuntimeConfig(env).defaultPollAfterSeconds,
      quotaRemainingToday: pendingJob.quotaRemainingToday ?? record.quotaRemainingToday ?? DEFAULT_FREE_DAILY_QUOTA
    };
    console.info(
      JSON.stringify({
        requestId,
        jobId,
        traceId,
        uploadTraceId,
        event: "job.presign.created",
        status: "upload_pending"
      })
    );
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
  ctx: ExecutionContext,
  requestId: string,
  schemaVersion: string,
  url: URL,
  pathJobId?: string,
  pathInstallId?: string,
  preReadBody?: CreateCloudJobRequest | StartCloudAnalysisJobRequest
): Promise<Response> {
  try {
    const body: CreateCloudJobRequest | StartCloudAnalysisJobRequest =
      preReadBody ?? (await readJson<CreateCloudJobRequest | StartCloudAnalysisJobRequest>(request));
    const requestedSourceObjectKey =
      "sourceObjectKey" in body && typeof body.sourceObjectKey === "string"
        ? body.sourceObjectKey
        : "uploadObjectKey" in body && typeof body.uploadObjectKey === "string"
          ? body.uploadObjectKey
          : undefined;
    const bodyJobId = "jobId" in body && typeof body.jobId === "string" ? body.jobId : undefined;
    const bodyInstallId = "installId" in body && typeof body.installId === "string" ? body.installId : undefined;
    const jobId = pathJobId ?? bodyJobId ?? deriveJobIdFromObjectKey(requestedSourceObjectKey);
    const installId = pathInstallId ?? bodyInstallId;
    const requestedResultObjectKey = "resultObjectKey" in body && typeof body.resultObjectKey === "string" ? body.resultObjectKey : undefined;
    const requestedTeamSelection = normalizeTeamSelection("teamSelection" in body ? body.teamSelection : undefined);

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

    const recoveredJob = await recoverStaleProcessingJob(env, ctx, job, requestId, "finalize");
    if (recoveredJob.updatedAt !== job.updatedAt || recoveredJob.status !== job.status) {
      console.info(
        JSON.stringify({
          requestId,
          jobId: recoveredJob.jobId,
          traceId: recoveredJob.traceId,
          uploadTraceId: recoveredJob.uploadTraceId ?? null,
          inferenceAttemptId: recoveredJob.inferenceAttemptId ?? null,
          event: "job.timeout.recovered",
          status: recoveredJob.status
        })
      );
      return jsonResponse(toCloudAnalysisJobResponse(recoveredJob, requestId, schemaVersion), { status: 200 }, requestId);
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
      console.info(
        JSON.stringify({
          requestId,
          jobId: job.jobId,
          traceId: job.traceId,
          event: "job.finalize.idempotent",
          status: job.status
        })
      );
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

    const teamSelection = requestedTeamSelection ?? job.teamSelection ?? null;
    const teamSelectionPatchNeeded = JSON.stringify(job.teamSelection ?? null) !== JSON.stringify(teamSelection);
    const teamSelectionJob = teamSelectionPatchNeeded
      ? await updateJobState(
          env,
          job.jobId,
          {
            teamSelection,
            updatedAt: new Date().toISOString()
          },
          {
            requestId,
            traceId: job.traceId,
            eventType: "job.team_selection.updated",
            message: "Team selection stored for analysis dispatch.",
            payload: {
              mode: teamSelection?.mode ?? "all",
              includeUncertain: teamSelection?.includeUncertain ?? null,
              confidenceThreshold: teamSelection?.confidenceThreshold ?? null
            }
          }
        )
      : job;

    const uploadedAt = teamSelectionJob.uploadedAt ?? new Date().toISOString();
    const uploadedJob =
      teamSelectionJob.status === "uploaded"
        ? teamSelectionJob
        : await updateJobState(
            env,
            teamSelectionJob.jobId,
            {
              status: "uploaded",
              stage: "Upload verified",
              progress: Math.max(teamSelectionJob.progress, 0.35),
              uploadedAt,
              teamSelection,
              updatedAt: uploadedAt
            },
            {
              requestId,
              traceId: teamSelectionJob.traceId,
              eventType: "job.uploaded",
              message: "Upload verified before queue dispatch.",
              payload: {
                sourceObjectKey: teamSelectionJob.sourceObjectKey,
                resultObjectKey: teamSelectionJob.resultObjectKey,
                uploadTraceId: teamSelectionJob.uploadTraceId ?? null,
                teamSelectionMode: teamSelection?.mode ?? "all"
              }
            }
          );
    const uploadedSnapshot = (await getJobSnapshot(env, teamSelectionJob.jobId)) ?? uploadedJob;

    if (uploadedSnapshot.queuedAt == null) {
      const queuedAt = new Date().toISOString();
      const queueMessage: QueueJobMessage = {
        kind: "process-job",
        jobId: uploadedSnapshot.jobId,
        requestId,
        uploadTraceId: uploadedSnapshot.uploadTraceId ?? requestId,
        traceId: uploadedSnapshot.traceId,
        schemaVersion,
        sourceObjectKey: uploadedSnapshot.sourceObjectKey,
        resultObjectKey: uploadedSnapshot.resultObjectKey,
        modelVersion: uploadedSnapshot.modelVersion ?? null,
        teamSelection: uploadedSnapshot.teamSelection ?? null
      };

      const queuedJob = await updateJobState(
        env,
        uploadedSnapshot.jobId,
        {
          status: "queued",
          stage: "Queued for inference",
          progress: Math.max(uploadedSnapshot.progress, 0.45),
          queuedAt,
          updatedAt: queuedAt
        },
        {
          requestId,
          traceId: uploadedSnapshot.traceId,
          eventType: "job.queued",
          message: "Job queued for inference dispatch.",
          payload: queueMessage
        }
      );
      const queuedSnapshot = (await getJobSnapshot(env, uploadedSnapshot.jobId)) ?? queuedJob;

      ctx.waitUntil(
        env.ANALYSIS_QUEUE
          .send(queueMessage)
          .catch(async (error) => {
            await appendJobEvent(env.DB, {
              jobId: queuedSnapshot.jobId,
              requestId,
              traceId: queuedSnapshot.traceId,
              eventType: "job.queue_dispatch_failed",
              message: error instanceof Error ? error.message : "Queue dispatch failed.",
              payload: queueMessage,
              createdAt: new Date().toISOString()
            });
          })
      );

      console.info(
        JSON.stringify({
          requestId,
          jobId: queuedSnapshot.jobId,
          traceId: queuedSnapshot.traceId,
          uploadTraceId: queuedSnapshot.uploadTraceId ?? null,
          event: "job.queued",
          status: queuedSnapshot.status
        })
      );

      return jsonResponse(toCloudAnalysisJobResponse(queuedSnapshot, requestId, schemaVersion), { status: 200 }, requestId);
    }

    console.info(
      JSON.stringify({
        requestId,
        jobId: uploadedSnapshot.jobId,
        traceId: uploadedSnapshot.traceId,
        uploadTraceId: uploadedSnapshot.uploadTraceId ?? null,
        event: "job.finalize.idempotent",
        status: uploadedSnapshot.status
      })
    );
    return jsonResponse(toCloudAnalysisJobResponse(uploadedSnapshot, requestId, schemaVersion), { status: 200 }, requestId);
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

async function handleGetJob(env: Env, ctx: ExecutionContext, requestId: string, jobId: string): Promise<Response> {
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

  const recoveredJob = await recoverStaleProcessingJob(env, ctx, job, requestId, "poll");
  const hydrated = await hydrateResultIfNeeded(env, recoveredJob);
  console.info(
    JSON.stringify({
      requestId,
      jobId: hydrated.jobId,
      traceId: hydrated.traceId,
      uploadTraceId: hydrated.uploadTraceId ?? null,
      inferenceAttemptId: hydrated.inferenceAttemptId ?? null,
      event: "job.polled",
      status: hydrated.status
    })
  );
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

function normalizeTeamSelection(value: unknown): TeamSelection | null {
  if (value === null || typeof value !== "object") {
    return null;
  }
  const input = value as {
    mode?: unknown;
    teamId?: unknown;
    label?: unknown;
    colorLabel?: unknown;
    confidenceThreshold?: unknown;
    includeUncertain?: unknown;
  };
  if (input.mode !== "all" && input.mode !== "team") {
    return null;
  }

  const confidenceThreshold =
    typeof input.confidenceThreshold === "number" && Number.isFinite(input.confidenceThreshold)
      ? Math.min(Math.max(input.confidenceThreshold, 0), 1)
      : 0.85;
  return {
    mode: input.mode,
    teamId: typeof input.teamId === "string" && input.teamId.length > 0 ? input.teamId : null,
    label: typeof input.label === "string" && input.label.length > 0 ? input.label : null,
    colorLabel: typeof input.colorLabel === "string" && input.colorLabel.length > 0 ? input.colorLabel : null,
    confidenceThreshold,
    includeUncertain: typeof input.includeUncertain === "boolean" ? input.includeUncertain : true
  };
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

function matchEditRevisionPath(pathname: string): { editJobId: string; revisionId?: string; kind: "revise" | "list" | "get" | "render" } | null {
  const reviseMatch = pathname.match(/^\/edit-jobs\/([^/]+)\/revise$/);
  if (reviseMatch) {
    return { editJobId: reviseMatch[1]!, kind: "revise" };
  }
  const renderMatch = pathname.match(/^\/edit-jobs\/([^/]+)\/revisions\/([^/]+)\/render$/);
  if (renderMatch) {
    return { editJobId: renderMatch[1]!, revisionId: renderMatch[2]!, kind: "render" };
  }
  const revisionMatch = pathname.match(/^\/edit-jobs\/([^/]+)\/revisions\/([^/]+)$/);
  if (revisionMatch) {
    return { editJobId: revisionMatch[1]!, revisionId: revisionMatch[2]!, kind: "get" };
  }
  const listMatch = pathname.match(/^\/edit-jobs\/([^/]+)\/revisions$/);
  if (listMatch) {
    return { editJobId: listMatch[1]!, kind: "list" };
  }
  return null;
}

function matchEditRenderPath(pathname: string): { editJobId: string; kind: "render" | "render-status" | "download-url" } | null {
  const renderMatch = pathname.match(/^\/edit-jobs\/([^/]+)\/render$/);
  if (renderMatch) {
    return { editJobId: renderMatch[1]!, kind: "render" };
  }
  const statusMatch = pathname.match(/^\/edit-jobs\/([^/]+)\/render-status$/);
  if (statusMatch) {
    return { editJobId: statusMatch[1]!, kind: "render-status" };
  }
  const downloadMatch = pathname.match(/^\/edit-jobs\/([^/]+)\/download-url$/);
  if (downloadMatch) {
    return { editJobId: downloadMatch[1]!, kind: "download-url" };
  }
  return null;
}

function matchRenderJobPath(pathname: string): { renderJobId: string; kind: "download-url" } | null {
  const downloadMatch = pathname.match(/^\/render-jobs\/([^/]+)\/download-url$/);
  if (downloadMatch) {
    return { renderJobId: downloadMatch[1]!, kind: "download-url" };
  }
  return null;
}

function matchEditJobPath(pathname: string): { editJobId: string; kind: "job" | "plan" } | null {
  const planMatch = pathname.match(/^\/edit-jobs\/([^/]+)\/plan$/);
  if (planMatch) {
    return { editJobId: planMatch[1]!, kind: "plan" };
  }
  const jobMatch = pathname.match(/^\/edit-jobs\/([^/]+)$/);
  if (jobMatch) {
    return { editJobId: jobMatch[1]!, kind: "job" };
  }
  return null;
}

function isTerminal(status: JobStatus): boolean {
  return status === "completed" || status === "failed" || status === "cancelled" || status === "succeeded" || status === "expired";
}

function deriveJobIdFromObjectKey(objectKey?: string): string | undefined {
  if (!objectKey) {
    return undefined;
  }
  const match = objectKey.match(/^uploads\/([^/]+)\//);
  return match?.[1];
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
    results: job.results
      ? {
          ...job.results,
          teamSelection: job.results.teamSelection ?? job.teamSelection ?? null
        }
      : null,
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
