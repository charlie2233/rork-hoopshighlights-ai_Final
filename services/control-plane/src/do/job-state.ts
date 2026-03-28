import { DurableObject } from "cloudflare:workers";
import { appendJobEvent, getJobIndex, upsertJobIndex } from "../db";
import type { Env } from "../env";
import { jsonResponse } from "../utils/request-id";
import type { JobBootstrapInput, JobMutationInput, JobRecord } from "../types";

const STATUS_ORDER: Record<JobRecord["status"], number> = {
  created: 0,
  upload_pending: 1,
  uploaded: 2,
  queued: 3,
  processing: 4,
  completed: 5,
  failed: 5,
  cancelled: 5,
  succeeded: 5,
  expired: 5
};

const TERMINAL_STATUSES = new Set<JobRecord["status"]>(["completed", "failed", "cancelled", "succeeded", "expired"]);

export class JobStateDO extends DurableObject<Env> {
  async fetch(request: Request): Promise<Response> {
    const requestId = request.headers.get("x-request-id")?.trim() || crypto.randomUUID();
    const url = new URL(request.url);

    try {
      if (request.method === "GET" && url.pathname === "/snapshot") {
        const job = await this.loadJob();
        if (!job) {
          return jsonResponse({ requestId, errorCode: "job_not_found", errorMessage: "Job not found." }, { status: 404 }, requestId);
        }
        return jsonResponse(job, { status: 200 }, requestId);
      }

      if (request.method === "POST" && url.pathname === "/bootstrap") {
        const input = (await request.json()) as JobBootstrapInput;
        const existing = await this.loadJob();
        if (existing) {
          return jsonResponse(existing, { status: 200 }, requestId);
        }
        await this.saveJob(input.record);
        return jsonResponse(input.record, { status: 201 }, requestId);
      }

      if (request.method === "PATCH" && url.pathname === "/patch") {
        const input = (await request.json()) as JobMutationInput;
        const job = await this.loadJob();
        if (!job) {
          return jsonResponse({ requestId, errorCode: "job_not_found", errorMessage: "Job not found." }, { status: 404 }, requestId);
        }
        const updated = await this.applyPatch(job, input.patch);
        await appendJobEvent(this.env.DB, {
          jobId: job.jobId,
          requestId: input.requestId ?? requestId,
          traceId: input.traceId ?? job.traceId,
          eventType: input.eventType ?? "job.patch",
          message: input.message ?? "Job state updated.",
          payload: input.payload ?? input.patch,
          createdAt: new Date().toISOString()
        });
        return jsonResponse(updated, { status: 200 }, requestId);
      }

      if (request.method === "DELETE" && url.pathname === "/delete") {
        const job = await this.loadJob();
        if (!job) {
          return jsonResponse({ requestId, errorCode: "job_not_found", errorMessage: "Job not found." }, { status: 404 }, requestId);
        }
        const updated = await this.applyPatch(job, {
          status: "cancelled",
          failureReason: "Job deleted by caller.",
          cancelledAt: new Date().toISOString(),
          finishedAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        });
        return jsonResponse(updated, { status: 200 }, requestId);
      }

      return jsonResponse({ requestId, errorCode: "not_found", errorMessage: "Unknown Durable Object action." }, { status: 404 }, requestId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Durable Object request failed.";
      return jsonResponse({ requestId, errorCode: "do_error", errorMessage: message }, { status: 500 }, requestId);
    }
  }

  private async loadJob(): Promise<JobRecord | null> {
    const stored = await this.ctx.storage.get<JobRecord>("job");
    return stored ?? null;
  }

  private async saveJob(job: JobRecord): Promise<void> {
    await this.ctx.storage.put("job", job);
    await upsertJobIndex(this.env.DB, job);
    await appendJobEvent(this.env.DB, {
      jobId: job.jobId,
      requestId: job.requestId,
      traceId: job.traceId,
      eventType: "job.bootstrap",
      message: "Job bootstrap recorded in Durable Object.",
      payload: job,
      createdAt: job.createdAt
    });
  }

  private async applyPatch(job: JobRecord, patch: Partial<JobRecord>): Promise<JobRecord> {
    const updated = this.mergeJob(job, patch);
    await this.ctx.storage.put("job", updated);
    await upsertJobIndex(this.env.DB, updated);
    return updated;
  }

  private mergeJob(job: JobRecord, patch: Partial<JobRecord>): JobRecord {
    const currentStatus = normalizeStatus(job.status);
    const requestedStatus = normalizeStatus(patch.status ?? job.status);

    if (TERMINAL_STATUSES.has(currentStatus) && requestedStatus !== currentStatus) {
      return job;
    }

    if (
      !TERMINAL_STATUSES.has(currentStatus) &&
      STATUS_ORDER[requestedStatus] < STATUS_ORDER[currentStatus] &&
      !isAllowedRetryRegression(currentStatus, requestedStatus, patch)
    ) {
      return job;
    }

    const now = patch.updatedAt ?? new Date().toISOString();
    const requestedAttemptCount = resolveAttemptCount(job.attemptCount ?? 0, patch.attemptCount, requestedStatus);
    const merged: JobRecord = {
      ...job,
      ...patch,
      status: requestedStatus,
      schemaVersion: patch.schemaVersion ?? job.schemaVersion,
      confidence: patch.confidence ?? patch.resultConfidence ?? job.confidence ?? job.resultConfidence ?? null,
      resultConfidence: patch.resultConfidence ?? patch.confidence ?? job.resultConfidence ?? job.confidence ?? null,
      createdAt: patch.createdAt ?? job.createdAt,
      uploadPendingAt: resolveTimestamp(job.uploadPendingAt, patch.uploadPendingAt, requestedStatus === "upload_pending"),
      uploadedAt: resolveTimestamp(job.uploadedAt, patch.uploadedAt, requestedStatus === "uploaded"),
      queuedAt: resolveTimestamp(job.queuedAt, patch.queuedAt, requestedStatus === "queued"),
      acceptedAt: resolveNullableTimestamp(job.acceptedAt, patch.acceptedAt, requestedStatus === "processing"),
      processingStartedAt: resolveNullableTimestamp(job.processingStartedAt, patch.processingStartedAt, requestedStatus === "processing"),
      attemptCount: requestedAttemptCount,
      startedAt: resolveTimestamp(job.startedAt, patch.startedAt, requestedStatus === "processing"),
      finishedAt: resolveTimestamp(job.finishedAt, patch.finishedAt, requestedStatus === "completed" || requestedStatus === "failed" || requestedStatus === "succeeded" || requestedStatus === "expired"),
      cancelledAt: resolveTimestamp(job.cancelledAt, patch.cancelledAt, requestedStatus === "cancelled" || requestedStatus === "expired"),
      updatedAt: now
    };

    if (requestedStatus === "completed" && merged.finishedAt == null) {
      merged.finishedAt = now;
    }
    if (requestedStatus === "failed" && merged.finishedAt == null) {
      merged.finishedAt = now;
    }
    if (requestedStatus === "cancelled" && merged.cancelledAt == null) {
      merged.cancelledAt = now;
      if (merged.finishedAt == null) {
        merged.finishedAt = now;
      }
    }
    if (requestedStatus === "expired" && merged.cancelledAt == null) {
      merged.cancelledAt = now;
      if (merged.finishedAt == null) {
        merged.finishedAt = now;
      }
    }

    return merged;
  }
}

function normalizeStatus(status: JobRecord["status"]): JobRecord["status"] {
  if (status === "succeeded") {
    return "completed";
  }
  if (status === "expired") {
    return "cancelled";
  }
  return status;
}

function resolveTimestamp(
  current: string | null | undefined,
  incoming: string | null | undefined,
  isTransition: boolean
): string | null {
  if (incoming === null) {
    return null;
  }
  if (incoming) {
    return incoming;
  }
  if (current) {
    return current;
  }
  return isTransition ? new Date().toISOString() : null;
}

function resolveNullableTimestamp(
  current: string | null | undefined,
  incoming: string | null | undefined,
  isTransition: boolean
): string | null {
  if (incoming === null) {
    return null;
  }
  if (incoming) {
    return incoming;
  }
  if (current) {
    return current;
  }
  return isTransition ? new Date().toISOString() : null;
}

function resolveAttemptCount(
  current: number,
  incoming: number | null | undefined,
  requestedStatus: JobRecord["status"]
): number {
  if (typeof incoming === "number" && Number.isFinite(incoming) && incoming >= 0) {
    return Math.floor(incoming);
  }
  if (requestedStatus === "processing") {
    return Math.max(current, 1);
  }
  return Math.max(current, 0);
}

function isAllowedRetryRegression(
  currentStatus: JobRecord["status"],
  requestedStatus: JobRecord["status"],
  patch: Partial<JobRecord>
): boolean {
  return (
    currentStatus === "processing" &&
    requestedStatus === "queued" &&
    typeof patch.stage === "string" &&
    patch.stage.startsWith("Retrying stale inference")
  );
}
