import type { Env } from "../env";
import type { AdminJobListItem, AdminReviewUpdate, ClipReviewUpdate, MetadataGenerationRequest, MetadataJobRecord } from "../types";
import {
  createMetadataJob,
  getJobIndex,
  listJobsIndex,
  readJobEvents,
  upsertClipReview,
  upsertJobReview
} from "../db";
import { createPresignedUploadTarget } from "../r2/presign";
import { isSharedSecretAuthorized } from "../utils/auth";
import { emptyResponse, jsonResponse, readJson } from "../utils/request-id";

export async function routeAdminRequest(
  request: Request,
  env: Env,
  requestId: string
): Promise<Response | null> {
  const url = new URL(request.url);
  if (!url.pathname.startsWith("/v1/admin/")) {
    return null;
  }

  if (!isSharedSecretAuthorized(request.headers.get("x-hoops-admin-token"), env.ADMIN_API_TOKEN)) {
    return jsonResponse(
      {
        requestId,
        errorCode: "forbidden",
        errorMessage: "Admin access is not authorized.",
        failureReason: "Admin access is not authorized."
      },
      { status: 403 },
      requestId
    );
  }

  if (request.method === "GET" && url.pathname === "/v1/admin/jobs") {
    const items = await listJobsIndex(env.DB, {
      status: url.searchParams.get("status"),
      modelVersion: url.searchParams.get("modelVersion"),
      failureReason: url.searchParams.get("failureReason"),
      limit: clampLimit(url.searchParams.get("limit"))
    });
    return jsonResponse({ requestId, items } satisfies { requestId: string; items: AdminJobListItem[] }, { status: 200 }, requestId);
  }

  const jobMatch = url.pathname.match(/^\/v1\/admin\/jobs\/([^/]+)(?:\/(assets|review|metadata))?$/);
  if (!jobMatch) {
    const clipMatch = url.pathname.match(/^\/v1\/admin\/clips\/([^/]+)\/review$/);
    if (clipMatch && request.method === "PATCH") {
      return handleClipReview(request, env, clipMatch[1]!, requestId);
    }
    return null;
  }

  const jobId = jobMatch[1]!;
  const suffix = jobMatch[2];

  if (!suffix && request.method === "GET") {
    const job = await getJobIndex(env.DB, jobId);
    if (!job) {
      return jsonResponse({ requestId, errorCode: "job_not_found", errorMessage: "Job not found." }, { status: 404 }, requestId);
    }
    const events = await readJobEvents(env.DB, jobId);
    return jsonResponse({ requestId, job, events }, { status: 200 }, requestId);
  }

  if (suffix === "assets" && request.method === "GET") {
    const job = await getJobIndex(env.DB, jobId);
    if (!job) {
      return jsonResponse({ requestId, errorCode: "job_not_found", errorMessage: "Job not found." }, { status: 404 }, requestId);
    }
    const upload = await createPresignedUploadTarget(env, {
      jobId,
      filename: job.filename,
      contentType: job.contentType,
      expiresInSeconds: 300
    });
    return jsonResponse(
      {
        requestId,
        jobId,
        uploadUrl: upload.uploadUrl,
        resultObjectKey: job.resultObjectKey,
        sourceObjectKey: job.sourceObjectKey
      },
      { status: 200 },
      requestId
    );
  }

  if (suffix === "review" && request.method === "PATCH") {
    const update = await readJson<AdminReviewUpdate>(request);
    await upsertJobReview(env.DB, jobId, update);
    return jsonResponse(
      {
        requestId,
        modelVersion: null,
        failureReason: null,
        jobId,
        reviewState: update.reviewState ?? "unreviewed",
        reviewerNotes: update.reviewerNotes ?? null,
        promotedToTrainingSet: update.promotedToTrainingSet ?? false
      },
      { status: 200 },
      requestId
    );
  }

  if (suffix === "metadata" && request.method === "POST") {
    const job = await getJobIndex(env.DB, jobId);
    if (!job) {
      return jsonResponse({ requestId, errorCode: "job_not_found", errorMessage: "Job not found." }, { status: 404 }, requestId);
    }

    const body = await readJson<MetadataGenerationRequest>(request);
    const metadataJobId = crypto.randomUUID().replace(/-/g, "");
    const now = new Date().toISOString();
    const record: MetadataJobRecord = {
      requestId,
      modelVersion: body.modelVersion ?? job.modelVersion ?? null,
      failureReason: null,
      metadataJobId,
      jobId,
      status: "queued",
      prompt: body.prompt ?? null,
      resultJson: null,
      createdAt: now,
      updatedAt: now
    };
    await createMetadataJob(env.DB, record);
    return jsonResponse({ requestId, metadataJobId, jobId, status: "queued" }, { status: 202 }, requestId);
  }

  return null;
}

async function handleClipReview(request: Request, env: Env, clipId: string, requestId: string): Promise<Response> {
  const update = await readJson<ClipReviewUpdate>(request);
  const url = new URL(request.url);
  const clipIndex =
    typeof update.clipIndex === "number" && Number.isFinite(update.clipIndex)
      ? update.clipIndex
      : Number.parseInt(url.searchParams.get("clipIndex") ?? "0", 10);
  const jobId = update.jobId ?? url.searchParams.get("jobId") ?? "";
  const job = jobId ? await getJobIndex(env.DB, jobId) : null;

  if (!jobId) {
    return jsonResponse(
      {
        requestId,
        modelVersion: null,
        errorCode: "invalid_request",
        errorMessage: "jobId is required for clip review updates.",
        failureReason: "jobId is required for clip review updates."
      },
      { status: 400 },
      requestId
    );
  }

  await upsertClipReview(
    env.DB,
    clipId,
    jobId,
    Number.isFinite(clipIndex) ? clipIndex : 0,
    update,
    job?.modelVersion ?? null,
    job?.failureReason ?? null
  );
  return jsonResponse(
    {
      requestId,
      modelVersion: job?.modelVersion ?? null,
      failureReason: job?.failureReason ?? null,
      clipId,
      reviewState: update.reviewState ?? "unreviewed",
      reviewerNotes: update.reviewerNotes ?? null,
      promotedToTrainingSet: update.promotedToTrainingSet ?? false
    },
    { status: 200 },
    requestId
  );
}

function clampLimit(input: string | null): number {
  const parsed = Number.parseInt(input ?? "", 10);
  if (!Number.isFinite(parsed)) {
    return 50;
  }
  return Math.max(1, Math.min(parsed, 250));
}
