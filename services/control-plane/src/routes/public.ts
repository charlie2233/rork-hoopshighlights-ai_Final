import type { Env } from "../env";
import type {
  AssetAnalysisJobResponse,
  AssetStatus,
  AssetStatusResponse,
  CloudAnalysisCapabilitiesResponse,
  CloudAnalysisJobResponse,
  CreateCloudAnalysisJobRequest,
  CreateCloudAnalysisJobResponse,
  CreateAssetAnalysisJobRequest,
  CreateCloudJobRequest,
  InferenceTeamScanRequest,
  JobRecord,
  JobStatus,
  MultipartUploadCompleteRequest,
  MultipartUploadPartRequest,
  QueueJobMessage,
  ScanCloudAnalysisTeamsRequest,
  ScanCloudAnalysisTeamsResponse,
  StartCloudAnalysisJobRequest,
  StartCloudAnalysisJobResponse,
  TeamOption,
  TeamSelection,
  UploadCompleteRequest,
  UploadCompleteResponse,
  UploadInitRequest,
  UploadInitResponse,
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
import {
  completeMultipartUpload,
  createPresignedMultipartPartTarget,
  createPresignedReadTarget,
  createPresignedUploadTarget,
  createResumableUploadTarget
} from "../r2/presign";
import { emptyResponse, jsonResponse, readJson } from "../utils/request-id";
import { resolveRuntimeConfig } from "../env";
import { recoverStaleProcessingJob } from "../recovery";
import { teamIdentityMatches } from "../team-identity";

const DEFAULT_FREE_DAILY_QUOTA = 3;
const RESUMABLE_UPLOAD_THRESHOLD_BYTES = 64 * 1024 * 1024;

class PresignValidationError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number = 400
  ) {
    super(message);
  }
}

function handleCapabilities(
  requestId: string,
  runtime: ReturnType<typeof resolveRuntimeConfig>
): Response {
  const response: CloudAnalysisCapabilitiesResponse = {
    requestId,
    schemaVersion: runtime.schemaVersion,
    confidence: null,
    modelVersion: null,
    failureReason: null,
    maxFileSizeBytes: runtime.maxFileSizeBytes,
    maxDurationSeconds: runtime.maxDurationSeconds,
    resumableUploadThresholdBytes: RESUMABLE_UPLOAD_THRESHOLD_BYTES,
    supportsResumableUpload: true,
    recommendedUploadPreference: "resumable",
    signedUploadTtlSeconds: runtime.signedUploadTtlSeconds,
    defaultPollAfterSeconds: runtime.defaultPollAfterSeconds,
    analysisMode: "cloud",
    supportsMultipartUpload: true,
    multipartThresholdBytes: RESUMABLE_UPLOAD_THRESHOLD_BYTES,
    recommendedPartSizeBytes: RESUMABLE_UPLOAD_THRESHOLD_BYTES,
    minPartSizeBytes: 5 * 1024 * 1024,
    maxPartSizeBytes: Math.max(RESUMABLE_UPLOAD_THRESHOLD_BYTES, 64 * 1024 * 1024),
    maxConcurrentPartUploads: 3,
    supportsChecksumSha256: true,
    supportsCancellation: false,
    supportsIdempotentComplete: true
  };
  return jsonResponse(response, { status: 200 }, requestId);
}

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

  if (request.method === "GET" && route === "/capabilities") {
    return handleCapabilities(requestId, runtime);
  }

  if (request.method === "POST" && route === "/uploads/init") {
    return handleAssetUploadInit(request, env, requestId, runtime.schemaVersion);
  }

  if (request.method === "POST" && (route === "/uploads/presign" || isLegacyPresign)) {
    return handlePresign(request, env, requestId, runtime.schemaVersion, url);
  }

  if (request.method === "POST" && route === "/uploads/multipart/part") {
    return handleMultipartPart(request, env, requestId, runtime.schemaVersion);
  }

  if (request.method === "POST" && route === "/uploads/multipart/complete") {
    return handleMultipartComplete(request, env, requestId, runtime.schemaVersion);
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

  const assetMatch = matchAssetPath(route);
  if (assetMatch) {
    if (request.method === "GET" && assetMatch.kind === "status") {
      return handleAssetStatus(env, requestId, runtime.schemaVersion, assetMatch.assetId, url.searchParams.get("installId"));
    }
    if (request.method === "POST" && assetMatch.kind === "complete") {
      return handleAssetUploadComplete(request, env, requestId, runtime.schemaVersion, assetMatch.assetId);
    }
    if (request.method === "POST" && assetMatch.kind === "analysis-jobs") {
      const body = await readJson<CreateAssetAnalysisJobRequest>(request);
      return handleAssetAnalysisJob(request, env, ctx, requestId, runtime.schemaVersion, url, assetMatch.assetId, body);
    }
    if (request.method === "POST" && assetMatch.kind === "team-scan") {
      const body = await readJson<ScanCloudAnalysisTeamsRequest>(request);
      return handleTeamScanJob(env, requestId, runtime.schemaVersion, assetMatch.assetId, body);
    }
  }

  const jobMatch = matchJobPath(route);
  if (!jobMatch) {
    return null;
  }

  if (request.method === "POST" && jobMatch.kind === "team-scan") {
    const body = await readJson<ScanCloudAnalysisTeamsRequest>(request);
    return handleTeamScanJob(env, requestId, runtime.schemaVersion, jobMatch.jobId, body);
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

async function handleAssetUploadInit(
  request: Request,
  env: Env,
  requestId: string,
  schemaVersion: string
): Promise<Response> {
  const body = await readJson<UploadInitRequest>(request);
  const legacyUploadPreference =
    body.uploadPreference === "single"
      ? "single"
      : body.uploadPreference === "multipart" || body.uploadPreference === "auto"
        ? "resumable"
        : null;
  const legacyHeaders = new Headers(request.headers);
  legacyHeaders.delete("content-length");
  const legacyRequest = new Request(request.url, {
    method: "POST",
    headers: legacyHeaders,
    body: JSON.stringify({
      filename: body.filename,
      contentType: body.contentType,
      fileSizeBytes: body.fileSizeBytes,
      durationSeconds: body.durationSeconds,
      installId: body.installId,
      appVersion: body.appVersion,
      analysisVersion: body.analysisVersion,
      uploadPreference: legacyUploadPreference
    } satisfies CreateCloudAnalysisJobRequest)
  });
  const presignResponse = await handlePresign(legacyRequest, env, requestId, schemaVersion, new URL(request.url));
  if (!presignResponse.ok) {
    return presignResponse;
  }

  const presign = (await presignResponse.json()) as UploadPresignResponse & CreateCloudAnalysisJobResponse;
  const multipart =
    presign.resumableUpload && presign.sourceObjectKey
      ? {
          uploadId: presign.resumableUpload.uploadId,
          partSizeBytes: presign.resumableUpload.chunkSizeBytes,
          partCount: presign.resumableUpload.partCount,
          parts: await buildAssetMultipartPartTargets(env, presign.sourceObjectKey, presign.resumableUpload.uploadId, presign.resumableUpload.partCount)
        }
      : null;
  const uploadMode: UploadInitResponse["uploadMode"] = multipart ? "multipart" : "single";
  const response: UploadInitResponse = {
    requestId,
    schemaVersion,
    confidence: presign.confidence ?? null,
    modelVersion: presign.modelVersion ?? null,
    failureReason: presign.failureReason ?? null,
    uploadTraceId: presign.uploadTraceId ?? null,
    inferenceAttemptId: presign.inferenceAttemptId ?? null,
    assetId: presign.assetId ?? presign.jobId,
    storageKey: presign.sourceObjectKey ?? "",
    status: "initialized",
    uploadMode,
    uploadUrl: uploadMode === "single" ? presign.uploadUrl : null,
    uploadMethod: presign.uploadMethod,
    uploadHeaders: uploadMode === "single" ? presign.uploadHeaders : {},
    multipart,
    expiresAt: presign.resumableUpload?.expiresAt ?? presign.expiresAt,
    pollAfterSeconds: presign.pollAfterSeconds,
    uploadState: "waiting_for_client_upload"
  };
  return jsonResponse(response, { status: 201 }, requestId);
}

async function buildAssetMultipartPartTargets(
  env: Env,
  sourceObjectKey: string,
  uploadId: string,
  partCount: number
): Promise<NonNullable<UploadInitResponse["multipart"]>["parts"]> {
  const parts: NonNullable<UploadInitResponse["multipart"]>["parts"] = [];
  for (let partNumber = 1; partNumber <= partCount; partNumber += 1) {
    const target = await createPresignedMultipartPartTarget(env, {
      objectKey: sourceObjectKey,
      uploadId,
      partNumber,
      expiresInSeconds: resolveRuntimeConfig(env).signedUploadTtlSeconds
    });
    parts.push({
      uploadUrl: target.uploadUrl,
      uploadMethod: target.uploadMethod,
      uploadHeaders: target.uploadHeaders,
      partNumber
    });
  }
  return parts;
}

async function handleAssetUploadComplete(
  request: Request,
  env: Env,
  requestId: string,
  schemaVersion: string,
  assetId: string
): Promise<Response> {
  try {
    const body = await readJson<UploadCompleteRequest>(request);
    if (!body.installId) {
      throw new Error("installId is required.");
    }
    const jobOrResponse = await getUploadOwnedJob(env, requestId, schemaVersion, assetId, body.installId, {
      allowReadyUploadStatuses: true
    });
    if (jobOrResponse instanceof Response) {
      return jobOrResponse;
    }
    if (isReadyUploadStatus(jobOrResponse.status)) {
      return jsonResponse(
        toAssetUploadCompleteResponse(jobOrResponse, requestId, schemaVersion, resolveRuntimeConfig(env).defaultPollAfterSeconds),
        { status: 200 },
        requestId
      );
    }

    const parts = (body.parts ?? [])
      .map((part) => ({
        partNumber: Number(part.partNumber),
        etag: typeof part.etag === "string" ? part.etag.trim() : ""
      }))
      .filter((part) => Number.isInteger(part.partNumber) && part.partNumber > 0 && part.etag.length > 0)
      .sort((a, b) => a.partNumber - b.partNumber);
    if ((body.parts ?? []).length !== parts.length) {
      throw new Error("Each uploaded part needs a partNumber and ETag.");
    }

    let uploadAlreadyAssembled = (await env.R2_UPLOADS.head(jobOrResponse.sourceObjectKey)) != null;
    if (body.uploadId && parts.length > 0 && !uploadAlreadyAssembled) {
      try {
        await completeMultipartUpload(env, {
          objectKey: jobOrResponse.sourceObjectKey,
          uploadId: body.uploadId,
          parts
        });
      } catch (error) {
        uploadAlreadyAssembled = (await env.R2_UPLOADS.head(jobOrResponse.sourceObjectKey)) != null;
        if (!uploadAlreadyAssembled) {
          throw error;
        }
      }
    }

    const uploadExists = (await env.R2_UPLOADS.head(jobOrResponse.sourceObjectKey)) != null;
    if (!uploadExists) {
      throw new Error("Upload is missing. Complete the signed upload before completing the asset.");
    }

    const now = new Date().toISOString();
    const patched = await updateJobState(
      env,
      jobOrResponse.jobId,
      {
        status: "uploaded",
        stage: body.uploadId ? "Resumable upload assembled" : "Upload verified",
        progress: Math.max(jobOrResponse.progress, 0.35),
        uploadedAt: jobOrResponse.uploadedAt ?? now,
        updatedAt: now
      },
      {
        requestId,
        traceId: jobOrResponse.traceId,
        eventType: body.uploadId ? "asset.multipart_upload.completed" : "asset.upload.completed",
        message: body.uploadId
          ? uploadAlreadyAssembled
            ? "Asset resumable upload was already assembled."
            : "Asset resumable upload parts assembled."
          : "Asset upload verified.",
        payload: {
          partCount: parts.length,
          alreadyAssembled: uploadAlreadyAssembled,
          uploadTraceId: jobOrResponse.uploadTraceId ?? null
        }
      }
    );

    return jsonResponse(
      toAssetUploadCompleteResponse(patched, requestId, schemaVersion, resolveRuntimeConfig(env).defaultPollAfterSeconds),
      { status: 200 },
      requestId
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid asset upload complete request.";
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

async function handleAssetStatus(
  env: Env,
  requestId: string,
  schemaVersion: string,
  assetId: string,
  installId: string | null
): Promise<Response> {
  const job = await getJobSnapshot(env, assetId);
  if (!job) {
    return jsonResponse(
      {
        requestId,
        schemaVersion,
        confidence: null,
        modelVersion: null,
        errorCode: "asset_not_found",
        errorMessage: "Asset was not found.",
        failureReason: "Asset was not found."
      },
      { status: 404 },
      requestId
    );
  }
  if (installId && job.installId !== installId) {
    return jsonResponse(
      {
        requestId,
        schemaVersion,
        confidence: null,
        modelVersion: job.modelVersion ?? null,
        errorCode: "install_mismatch",
        errorMessage: "Install ID does not own this asset.",
        failureReason: "Install ID does not own this asset."
      },
      { status: 403 },
      requestId
    );
  }
  return jsonResponse(toAssetStatusResponse(job, requestId, schemaVersion), { status: 200 }, requestId);
}

async function handleAssetAnalysisJob(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
  requestId: string,
  schemaVersion: string,
  url: URL,
  assetId: string,
  body: CreateAssetAnalysisJobRequest
): Promise<Response> {
  const finalizeResponse = await handleFinalizeJob(
    request,
    env,
    ctx,
    requestId,
    schemaVersion,
    url,
    assetId,
    body.installId,
    {
      installId: body.installId,
      teamSelection: body.teamSelection
    }
  );
  if (!finalizeResponse.ok) {
    return finalizeResponse;
  }
  const job = (await finalizeResponse.json()) as CloudAnalysisJobResponse;
  const response: AssetAnalysisJobResponse = {
    requestId,
    schemaVersion,
    confidence: job.confidence ?? null,
    modelVersion: job.modelVersion ?? null,
    failureReason: job.failureReason ?? null,
    uploadTraceId: job.uploadTraceId ?? null,
    inferenceAttemptId: job.inferenceAttemptId ?? null,
    jobId: job.jobId,
    assetId: job.assetId ?? assetId,
    storageKey: job.sourceObjectKey ?? null,
    sourceObjectKey: job.sourceObjectKey ?? null,
    status: job.status,
    pollAfterSeconds: resolveRuntimeConfig(env).defaultPollAfterSeconds,
    quotaRemainingToday: DEFAULT_FREE_DAILY_QUOTA,
    analysisMode: "cloud"
  };
  return jsonResponse(response, { status: 200 }, requestId);
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
    const resumableUpload = await maybeCreateResumableUpload(env, body, upload.objectKey);

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
      assetId: jobId,
      storageKey: upload.objectKey,
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
      detectedTeams: null,
      teamScanStatus: null,
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
      assetId: jobId,
      storageKey: null,
      sourceObjectKey: upload.objectKey,
      resultObjectKey: record.resultObjectKey,
      uploadUrl: upload.uploadUrl,
      uploadMethod: upload.uploadMethod,
      uploadHeaders: upload.uploadHeaders,
      expiresAt: upload.expiresAt,
      resumableUpload,
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
    const validationError = error instanceof PresignValidationError ? error : null;
    const message = validationError?.message ?? (error instanceof Error ? error.message : "Invalid upload presign request.");
    return jsonResponse(
      {
        requestId,
        schemaVersion,
        confidence: null,
        modelVersion: null,
        errorCode: validationError?.code ?? "invalid_request",
        errorMessage: message,
        failureReason: message
      },
      { status: validationError?.status ?? 400 },
      requestId
    );
  }
}

async function handleMultipartPart(
  request: Request,
  env: Env,
  requestId: string,
  schemaVersion: string
): Promise<Response> {
  try {
    const body = await readJson<MultipartUploadPartRequest>(request);
    if (!body.jobId || !body.installId || !body.uploadId || !Number.isInteger(body.partNumber) || body.partNumber < 1) {
      throw new Error("jobId, installId, uploadId, and partNumber are required.");
    }

    const jobOrResponse = await getUploadOwnedJob(env, requestId, schemaVersion, body.jobId, body.installId);
    if (jobOrResponse instanceof Response) {
      return jobOrResponse;
    }

    const target = await createPresignedMultipartPartTarget(env, {
      objectKey: jobOrResponse.sourceObjectKey,
      uploadId: body.uploadId,
      partNumber: body.partNumber,
      expiresInSeconds: resolveRuntimeConfig(env).signedUploadTtlSeconds
    });

    return jsonResponse(
      {
        requestId,
        schemaVersion,
        confidence: null,
        modelVersion: jobOrResponse.modelVersion ?? null,
        failureReason: null,
        uploadTraceId: jobOrResponse.uploadTraceId ?? null,
        jobId: jobOrResponse.jobId,
        partNumber: body.partNumber,
        uploadUrl: target.uploadUrl,
        uploadMethod: target.uploadMethod,
        uploadHeaders: target.uploadHeaders,
        expiresAt: target.expiresAt
      },
      { status: 201 },
      requestId
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid resumable upload part request.";
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

async function handleMultipartComplete(
  request: Request,
  env: Env,
  requestId: string,
  schemaVersion: string
): Promise<Response> {
  try {
    const body = await readJson<MultipartUploadCompleteRequest>(request);
    if (!body.jobId || !body.installId || !body.uploadId || !Array.isArray(body.parts) || body.parts.length === 0) {
      throw new Error("jobId, installId, uploadId, and uploaded parts are required.");
    }
    const parts = body.parts
      .map((part) => ({
        partNumber: Number(part.partNumber),
        etag: typeof part.etag === "string" ? part.etag.trim() : ""
      }))
      .filter((part) => Number.isInteger(part.partNumber) && part.partNumber > 0 && part.etag.length > 0)
      .sort((a, b) => a.partNumber - b.partNumber);
    if (parts.length !== body.parts.length) {
      throw new Error("Each uploaded part needs a partNumber and ETag.");
    }

    const jobOrResponse = await getUploadOwnedJob(env, requestId, schemaVersion, body.jobId, body.installId);
    if (jobOrResponse instanceof Response) {
      return jobOrResponse;
    }

    let uploadAlreadyAssembled = (await env.R2_UPLOADS.head(jobOrResponse.sourceObjectKey)) != null;
    if (!uploadAlreadyAssembled) {
      try {
        await completeMultipartUpload(env, {
          objectKey: jobOrResponse.sourceObjectKey,
          uploadId: body.uploadId,
          parts
        });
      } catch (error) {
        uploadAlreadyAssembled = (await env.R2_UPLOADS.head(jobOrResponse.sourceObjectKey)) != null;
        if (!uploadAlreadyAssembled) {
          throw error;
        }
      }
    }

    const now = new Date().toISOString();
    const patched = await updateJobState(
      env,
      jobOrResponse.jobId,
      {
        stage: "Resumable upload assembled",
        progress: Math.max(jobOrResponse.progress, 0.32),
        updatedAt: now
      },
      {
        requestId,
        traceId: jobOrResponse.traceId,
        eventType: "job.multipart_upload.completed",
        message: uploadAlreadyAssembled
          ? "Resumable upload was already assembled."
          : "Resumable upload parts assembled.",
        payload: {
          partCount: parts.length,
          alreadyAssembled: uploadAlreadyAssembled,
          uploadTraceId: jobOrResponse.uploadTraceId ?? null
        }
      }
    );

    return jsonResponse(toCloudAnalysisJobResponse(patched, requestId, schemaVersion), { status: 200 }, requestId);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid resumable upload complete request.";
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
      if (isOpenUploadStatus(job.status) && isUploadWindowExpired(job)) {
        return jsonResponse(
          {
            requestId,
            schemaVersion,
            confidence: null,
            modelVersion: job.modelVersion ?? null,
            errorCode: "upload_expired",
            errorMessage: "This upload expired. Start a fresh cloud analysis upload.",
            failureReason: "This upload expired. Start a fresh cloud analysis upload."
          },
          { status: 410 },
          requestId
        );
      }
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
    const teamSelectionError = validateScanBackedTeamSelection(job, teamSelection, requestId, schemaVersion);
    if (teamSelectionError) {
      return teamSelectionError;
    }
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
        assetId: uploadedSnapshot.assetId ?? uploadedSnapshot.jobId,
        storageKey: uploadedSnapshot.storageKey ?? uploadedSnapshot.sourceObjectKey,
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

async function handleTeamScanJob(
  env: Env,
  requestId: string,
  schemaVersion: string,
  jobId: string,
  body: ScanCloudAnalysisTeamsRequest
): Promise<Response> {
  if (!body || typeof body.installId !== "string" || body.installId.trim().length === 0) {
    return jsonResponse(
      {
        requestId,
        schemaVersion,
        confidence: null,
        modelVersion: null,
        errorCode: "invalid_request",
        errorMessage: "installId is required.",
        failureReason: "installId is required."
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

  if (job.installId !== body.installId) {
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

  if (job.status !== "created" && job.status !== "upload_pending") {
    return jsonResponse(
      {
        requestId,
        schemaVersion,
        confidence: null,
        modelVersion: job.modelVersion ?? null,
        errorCode: "job_already_started",
        errorMessage: "Team scan is only available before analysis starts.",
        failureReason: "Team scan is only available before analysis starts."
      },
      { status: 400 },
      requestId
    );
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
        errorMessage: "Upload is missing. Complete the signed upload before scanning teams.",
        failureReason: "Upload is missing. Complete the signed upload before scanning teams."
      },
      { status: 400 },
      requestId
    );
  }

  const runtime = resolveRuntimeConfig(env);
  const localDetectedTeams = (body as ScanCloudAnalysisTeamsRequest & { detectedTeams?: unknown }).detectedTeams;
  const normalizedLocalDetectedTeams = normalizeTeamOptions(localDetectedTeams);
  const scanResult =
    runtime.appEnv === "local" && localDetectedTeams !== undefined
      ? {
          status: normalizedLocalDetectedTeams.length > 0 ? ("scanned" as const) : ("unavailable" as const),
          detectedTeams: normalizedLocalDetectedTeams,
          modelVersion: job.modelVersion ?? null
        }
      : await requestInferenceTeamScan(env, job, requestId, schemaVersion);
  const detectedTeams = scanResult.detectedTeams;
  const status = scanResult.status;
  const now = new Date().toISOString();
  const updated = await updateJobState(
    env,
    job.jobId,
    {
      detectedTeams,
      teamScanStatus: status,
      stage: status === "scanned" ? "Team scan complete" : "Team scan unavailable",
      progress: Math.max(job.progress, 0.24),
      updatedAt: now
    },
    {
      requestId,
      traceId: job.traceId,
      eventType: "job.team_scan.completed",
      message: status === "scanned" ? "Team scan detected jersey-color teams." : "Team scan did not detect selectable teams.",
      payload: {
        status,
        detectedTeamCount: detectedTeams.length
      }
    }
  );

  const response: ScanCloudAnalysisTeamsResponse = {
    requestId,
    schemaVersion,
    confidence: null,
    modelVersion: scanResult.modelVersion ?? updated.modelVersion ?? null,
    failureReason: null,
    uploadTraceId: updated.uploadTraceId ?? null,
    inferenceAttemptId: updated.inferenceAttemptId ?? null,
    jobId: updated.jobId,
    status,
    detectedTeams
  };
  return jsonResponse(response, { status: 200 }, requestId);
}

async function requestInferenceTeamScan(
  env: Env,
  job: JobRecord,
  requestId: string,
  schemaVersion: string
): Promise<{
  status: ScanCloudAnalysisTeamsResponse["status"];
  detectedTeams: TeamOption[];
  modelVersion?: string | null;
}> {
  const providers = teamScanProviders(env);
  if (providers.length === 0) {
    return { status: "unavailable", detectedTeams: [], modelVersion: job.modelVersion ?? null };
  }

  try {
    const readTarget = await createPresignedReadTarget(env, {
      objectKey: job.sourceObjectKey,
      expiresInSeconds: Math.max(resolveRuntimeConfig(env).jobTtlSeconds, 3600),
      bucketName: env.R2_UPLOAD_BUCKET_NAME
    });
    const payload: InferenceTeamScanRequest = {
      jobId: job.jobId,
      assetId: job.assetId ?? job.jobId,
      storageKey: job.storageKey ?? job.sourceObjectKey,
      requestId,
      uploadTraceId: job.uploadTraceId ?? requestId,
      traceId: job.traceId,
      sourceObjectKey: job.sourceObjectKey,
      sourceUrl: readTarget.sourceUrl,
      filename: job.filename,
      contentType: job.contentType,
      durationSeconds: job.durationSeconds,
      installId: job.installId,
      appVersion: job.appVersion,
      analysisVersion: job.analysisVersion,
      schemaVersion,
      modelVersion: job.modelVersion ?? null
    };
    for (const provider of providers) {
      const result = await requestTeamScanProvider(provider, payload, job, requestId);
      if (result.status === "scanned") {
        return result;
      }
    }
  } catch {
    // Fall through to the unavailable response below. Do not include source URLs or object keys in public errors.
  }

  return { status: "unavailable", detectedTeams: [], modelVersion: job.modelVersion ?? null };
}

interface TeamScanProvider {
  baseUrl: string;
  secret: string;
  includeInternalSecret: boolean;
}

function teamScanProviders(env: Env): TeamScanProvider[] {
  const providers: TeamScanProvider[] = [];
  if (env.INFERENCE_BASE_URL) {
    providers.push({
      baseUrl: env.INFERENCE_BASE_URL,
      secret: env.INFERENCE_SHARED_SECRET || env.CONTROL_PLANE_SHARED_SECRET,
      includeInternalSecret: false
    });
  }
  if (env.EDITING_BASE_URL) {
    providers.push({
      baseUrl: env.EDITING_BASE_URL,
      secret: env.EDITING_SHARED_SECRET || env.INFERENCE_SHARED_SECRET || env.CONTROL_PLANE_SHARED_SECRET,
      includeInternalSecret: true
    });
  }
  return providers.filter((provider) => provider.baseUrl.trim().length > 0 && provider.secret.trim().length > 0);
}

async function requestTeamScanProvider(
  provider: TeamScanProvider,
  payload: InferenceTeamScanRequest,
  job: JobRecord,
  requestId: string
): Promise<{
  status: ScanCloudAnalysisTeamsResponse["status"];
  detectedTeams: TeamOption[];
  modelVersion?: string | null;
}> {
  try {
    const headers: Record<string, string> = {
      "content-type": "application/json",
      "x-hoops-inference-secret": provider.secret,
      "x-request-id": requestId,
      "x-trace-id": job.traceId,
      "x-hoops-upload-trace-id": job.uploadTraceId ?? requestId
    };
    if (provider.includeInternalSecret) {
      headers["x-hoops-internal-secret"] = provider.secret;
    }
    const response = await fetch(new URL("/v1/team-scan", provider.baseUrl).toString(), {
      method: "POST",
      headers,
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      return { status: "unavailable", detectedTeams: [], modelVersion: job.modelVersion ?? null };
    }

    const parsed = (await response.json()) as Partial<ScanCloudAnalysisTeamsResponse>;
    const detectedTeams = normalizeTeamOptions(parsed.detectedTeams);
    const status: ScanCloudAnalysisTeamsResponse["status"] =
      parsed.status === "scanned" && detectedTeams.length > 0 ? "scanned" : "unavailable";
    const modelVersion =
      typeof parsed.modelVersion === "string" && parsed.modelVersion.trim().length > 0
        ? parsed.modelVersion.trim()
        : job.modelVersion ?? null;
    return { status, detectedTeams, modelVersion };
  } catch {
    return { status: "unavailable", detectedTeams: [], modelVersion: job.modelVersion ?? null };
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
    throw new PresignValidationError("invalid_request", "Invalid upload presign request.");
  }
  if (body.fileSizeBytes <= 0 || body.fileSizeBytes > maxFileSizeBytes) {
    throw new PresignValidationError("file_too_large", "Video exceeds the deployed cloud upload size limit.");
  }
  if (body.durationSeconds <= 0 || body.durationSeconds > maxDurationSeconds) {
    throw new PresignValidationError("unsupported_duration", "Video exceeds the deployed cloud analysis duration limit.");
  }
}

async function maybeCreateResumableUpload(
  env: Env,
  body: CreateCloudAnalysisJobRequest,
  objectKey: string
) {
  if (body.uploadPreference !== "resumable" || body.fileSizeBytes < RESUMABLE_UPLOAD_THRESHOLD_BYTES) {
    return null;
  }

  try {
    return await createResumableUploadTarget(env, {
      objectKey,
      contentType: body.contentType,
      fileSizeBytes: body.fileSizeBytes,
      expiresInSeconds: resolveRuntimeConfig(env).signedUploadTtlSeconds
    });
  } catch {
    return null;
  }
}

async function getUploadOwnedJob(
  env: Env,
  requestId: string,
  schemaVersion: string,
  jobId: string,
  installId: string,
  options?: { allowReadyUploadStatuses?: boolean }
): Promise<JobRecord | Response> {
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
  if (isOpenUploadStatus(job.status) && isUploadWindowExpired(job)) {
    return jsonResponse(
      {
        requestId,
        schemaVersion,
        confidence: null,
        modelVersion: job.modelVersion ?? null,
        errorCode: "upload_expired",
        errorMessage: "This upload expired. Start a fresh cloud analysis upload.",
        failureReason: "This upload expired. Start a fresh cloud analysis upload."
      },
      { status: 410 },
      requestId
    );
  }
  if (options?.allowReadyUploadStatuses && isReadyUploadStatus(job.status)) {
    return job;
  }
  if (isTerminal(job.status) || job.status === "queued" || job.status === "processing") {
    return jsonResponse(
      {
        requestId,
        schemaVersion,
        confidence: null,
        modelVersion: job.modelVersion ?? null,
        errorCode: "upload_closed",
        errorMessage: "This upload can no longer be changed.",
        failureReason: "This upload can no longer be changed."
      },
      { status: 409 },
      requestId
    );
  }

  return job;
}

function isOpenUploadStatus(status: JobStatus): boolean {
  return status === "created" || status === "upload_pending";
}

function isReadyUploadStatus(status: JobStatus): boolean {
  return status === "queued" || status === "processing" || status === "completed" || status === "succeeded";
}

function isUploadWindowExpired(job: JobRecord): boolean {
  if (!job.expiresAt) {
    return false;
  }

  const expiresAtMs = Date.parse(job.expiresAt);
  return Number.isFinite(expiresAtMs) && expiresAtMs <= Date.now();
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

function normalizeTeamOptions(value: unknown): TeamOption[] {
  if (!Array.isArray(value)) {
    return [];
  }

  const teams: TeamOption[] = [];
  for (const entry of value) {
    if (entry === null || typeof entry !== "object") {
      continue;
    }
    const input = entry as {
      teamId?: unknown;
      label?: unknown;
      colorLabel?: unknown;
      primaryColorHex?: unknown;
      confidence?: unknown;
      source?: unknown;
    };
    const teamId = coerceString(input.teamId);
    const label = coerceString(input.label);
    if (!teamId || !label) {
      continue;
    }

    teams.push({
      teamId,
      label,
      colorLabel: coerceString(input.colorLabel),
      primaryColorHex: coerceString(input.primaryColorHex),
      confidence: clamp01(typeof input.confidence === "number" && Number.isFinite(input.confidence) ? input.confidence : 0),
      source: coerceString(input.source)
    });
  }
  return teams;
}

function validateScanBackedTeamSelection(
  job: JobRecord,
  selection: TeamSelection | null,
  requestId: string,
  schemaVersion: string
): Response | null {
  if (!selection || selection.mode !== "team") {
    return null;
  }

  const detectedTeams = job.detectedTeams ?? job.results?.detectedTeams ?? [];
  if (detectedTeams.length === 0) {
    return jsonResponse(
      {
        requestId,
        schemaVersion,
        confidence: null,
        modelVersion: job.modelVersion ?? null,
        errorCode: "team_scan_required",
        errorMessage: "Run the cloud team scan and choose one of the detected jersey-color teams before selected-team analysis.",
        failureReason: "Run the cloud team scan and choose one of the detected jersey-color teams before selected-team analysis."
      },
      { status: 400 },
      requestId
    );
  }

  const matchesDetectedTeam = detectedTeams.some((team) => {
    return teamIdentityMatches({
      selectedTeamId: selection.teamId,
      selectedColorLabel: selection.colorLabel,
      selectedLabel: selection.label,
      candidateTeamId: team.teamId,
      candidateColorLabel: team.colorLabel,
      candidateLabel: team.label
    });
  });

  if (matchesDetectedTeam) {
    return null;
  }

  return jsonResponse(
    {
      requestId,
      schemaVersion,
      confidence: null,
      modelVersion: job.modelVersion ?? null,
      errorCode: "team_selection_unavailable",
      errorMessage: "Selected team must match a jersey-color team from the cloud scan.",
      failureReason: "Selected team must match a jersey-color team from the cloud scan."
    },
    { status: 400 },
    requestId
  );
}

function coerceString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function clamp01(value: number): number {
  return Math.min(Math.max(value, 0), 1);
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

function matchJobPath(pathname: string): { jobId: string; kind: "get" | "delete" | "start" | "team-scan" } | null {
  const teamScanMatch = pathname.match(/^\/jobs\/([^/]+)\/team-scan$/);
  if (teamScanMatch) {
    return { jobId: teamScanMatch[1]!, kind: "team-scan" };
  }

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

function matchAssetPath(pathname: string): { assetId: string; kind: "status" | "complete" | "analysis-jobs" | "team-scan" } | null {
  const completeMatch = pathname.match(/^\/uploads\/([^/]+)\/complete$/);
  if (completeMatch) {
    return { assetId: decodeURIComponent(completeMatch[1]!), kind: "complete" };
  }

  const analysisJobMatch = pathname.match(/^\/assets\/([^/]+)\/analysis-jobs$/);
  if (analysisJobMatch) {
    return { assetId: decodeURIComponent(analysisJobMatch[1]!), kind: "analysis-jobs" };
  }

  const teamScanMatch = pathname.match(/^\/assets\/([^/]+)\/team-scan$/);
  if (teamScanMatch) {
    return { assetId: decodeURIComponent(teamScanMatch[1]!), kind: "team-scan" };
  }

  const statusMatch = pathname.match(/^\/assets\/([^/]+)$/);
  if (statusMatch) {
    return { assetId: decodeURIComponent(statusMatch[1]!), kind: "status" };
  }

  return null;
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

function toAssetStatusResponse(
  job: JobRecord,
  requestId: string,
  schemaVersion: string | null
): AssetStatusResponse {
  const status = assetStatusForJob(job);
  const ready = status === "ready" || status === "proxy_ready";
  return {
    requestId,
    schemaVersion: schemaVersion ?? job.schemaVersion,
    confidence: job.confidence ?? job.resultConfidence ?? null,
    modelVersion: job.modelVersion ?? null,
    failureReason: job.failureReason ?? null,
    uploadTraceId: job.uploadTraceId ?? null,
    inferenceAttemptId: job.inferenceAttemptId ?? null,
    assetId: job.assetId ?? job.jobId,
    installId: job.installId,
    filename: job.filename,
    contentType: job.contentType,
    fileSizeBytes: job.fileSizeBytes,
    durationSeconds: job.durationSeconds,
    storageKey: null,
    sourceObjectKey: job.sourceObjectKey,
    proxyKey: null,
    status,
    uploadMode: job.uploadUrl ? "single" : "multipart",
    uploadedBytes: ready ? job.fileSizeBytes : 0,
    progress: ready ? 1 : clamp01(job.progress),
    checksumSha256: null,
    integrityStatus: "unavailable",
    analysisJobId: hasAnalysisStarted(job.status) ? job.jobId : null,
    renderAttachments: [],
    retryCount: job.attemptCount ?? 0,
    retryable: !isTerminal(job.status),
    lastErrorCode: job.errorCode ?? null,
    cancellationReason: job.status === "cancelled" ? job.failureReason ?? "cancelled" : null,
    cancelledAt: job.cancelledAt ?? null,
    artifacts: {
      proxyStorageKey: null,
      thumbnailStorageKeys: [],
      waveformStorageKey: null
    },
    createdAt: job.createdAt,
    updatedAt: job.updatedAt
  };
}

function toAssetUploadCompleteResponse(
  job: JobRecord,
  requestId: string,
  schemaVersion: string | null,
  pollAfterSeconds: number
): UploadCompleteResponse {
  const asset = toAssetStatusResponse(job, requestId, schemaVersion);
  return {
    requestId,
    schemaVersion: asset.schemaVersion,
    confidence: asset.confidence ?? null,
    modelVersion: asset.modelVersion ?? null,
    failureReason: asset.failureReason ?? null,
    uploadTraceId: asset.uploadTraceId ?? null,
    inferenceAttemptId: asset.inferenceAttemptId ?? null,
    assetId: asset.assetId,
    storageKey: null,
    sourceObjectKey: asset.sourceObjectKey,
    proxyKey: asset.proxyKey,
    status: asset.status,
    progress: asset.progress,
    checksumSha256: asset.checksumSha256,
    integrityStatus: asset.integrityStatus,
    retryCount: asset.retryCount,
    retryable: asset.retryable,
    lastErrorCode: asset.lastErrorCode,
    artifacts: asset.artifacts,
    pollAfterSeconds
  };
}

function assetStatusForJob(job: JobRecord): AssetStatus {
  switch (job.status) {
    case "created":
      return "initialized";
    case "upload_pending":
      return "uploading";
    case "failed":
    case "expired":
      return "failed";
    case "cancelled":
      return "cancelled";
    case "uploaded":
    case "queued":
    case "processing":
    case "completed":
    case "succeeded":
      return "ready";
  }
}

function hasAnalysisStarted(status: JobStatus): boolean {
  return status === "queued" || status === "processing" || status === "completed" || status === "succeeded" || status === "failed" || status === "expired";
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
    assetId: job.assetId ?? job.jobId,
    storageKey: null,
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
