import { DurableObject } from "cloudflare:workers";
import { appendJobEvent, getJobIndex, upsertJobIndex } from "../db";
import type { Env } from "../env";
import { jsonResponse } from "../utils/request-id";
import type { JobBootstrapInput, JobMutationInput, JobRecord } from "../types";

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
          status: "expired",
          failureReason: "Job deleted by caller.",
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
    const updated: JobRecord = {
      ...job,
      ...patch,
      updatedAt: patch.updatedAt ?? new Date().toISOString()
    };
    await this.ctx.storage.put("job", updated);
    await upsertJobIndex(this.env.DB, updated);
    return updated;
  }
}
