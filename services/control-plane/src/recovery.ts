import type { ExecutionContext } from "@cloudflare/workers-types";
import { appendJobEvent } from "./db";
import { updateJobState } from "./do/job-state-client";
import type { Env } from "./env";
import { resolveRuntimeConfig } from "./env";
import type { JobRecord, QueueJobMessage } from "./types";

export async function recoverStaleProcessingJob(
  env: Env,
  ctx: ExecutionContext,
  job: JobRecord,
  requestId: string,
  trigger: "poll" | "finalize",
): Promise<JobRecord> {
  const runtime = resolveRuntimeConfig(env);
  const now = new Date().toISOString();
  const processingStartedAt =
    job.processingStartedAt ?? job.acceptedAt ?? job.startedAt ?? null;
  const lastProgressAt = latestTimestamp(processingStartedAt, job.updatedAt);
  const timeoutSeconds = effectiveProcessingTimeoutSeconds(job, runtime);

  if (
    job.status === "processing" &&
    processingStartedAt &&
    isOlderThan(lastProgressAt, timeoutSeconds)
  ) {
    return scheduleRetryForStaleProcessing(
      env,
      ctx,
      job,
      requestId,
      trigger,
      runtime.maxInferenceAttempts,
      timeoutSeconds,
      processingStartedAt,
      now,
    );
  }

  return job;
}

async function scheduleRetryForStaleProcessing(
  env: Env,
  ctx: ExecutionContext,
  job: JobRecord,
  requestId: string,
  trigger: "poll" | "finalize",
  maxInferenceAttempts: number,
  timeoutSeconds: number,
  processingStartedAt: string,
  now: string,
): Promise<JobRecord> {
  const attemptCount = Math.max(job.attemptCount ?? 0, 1);

  if (attemptCount >= maxInferenceAttempts) {
    const failureReason = `Inference callback timed out after ${attemptCount} accepted attempts.`;
    const failedJob = await updateJobState(
      env,
      job.jobId,
      {
        status: "failed",
        stage: "Inference timed out",
        progress: Math.max(job.progress, 0.85),
        failureReason,
        errorCode: "failed_timeout",
        errorMessage: failureReason,
        finishedAt: now,
        updatedAt: now,
      },
      {
        requestId,
        traceId: job.traceId,
        eventType: "job.processing.timeout_exhausted",
        message: failureReason,
        payload: {
          jobId: job.jobId,
          requestId,
          traceId: job.traceId,
          trigger,
          attemptCount,
          maxInferenceAttempts,
        },
      },
    );

    await env.ANALYSIS_DLQ.send({
      kind: "dead-letter-job",
      jobId: job.jobId,
      requestId,
      traceId: job.traceId,
      schemaVersion: job.schemaVersion,
      sourceObjectKey: job.sourceObjectKey,
      resultObjectKey: job.resultObjectKey,
      modelVersion: job.modelVersion ?? null,
      failureReason,
      attempts: attemptCount,
    });

    return failedJob;
  }

  const nextInferenceAttemptId = crypto.randomUUID().replace(/-/g, "");
  const queuedJob = await updateJobState(
    env,
    job.jobId,
    {
      status: "queued",
      stage: "Retrying stale inference dispatch",
      progress: Math.max(job.progress, 0.45),
      queuedAt: now,
      acceptedAt: null,
      processingStartedAt: null,
      attemptCount,
      startedAt: null,
      failureReason: null,
      errorCode: null,
      errorMessage: null,
      inferenceAttemptId: nextInferenceAttemptId,
      updatedAt: now,
    },
    {
      requestId,
      traceId: job.traceId,
      eventType: "job.processing.timed_out",
      message: "Processing timed out; retry scheduled.",
      payload: {
        jobId: job.jobId,
        requestId,
        traceId: job.traceId,
        trigger,
        attemptCount,
        processingStartedAt,
        timeoutSeconds,
        inferenceAttemptId: nextInferenceAttemptId,
      },
    },
  );

  return requestQueueDispatchRetry(
    env,
    ctx,
    queuedJob,
    requestId,
    trigger,
    now,
  );
}

async function requestQueueDispatchRetry(
  env: Env,
  ctx: ExecutionContext,
  job: JobRecord,
  requestId: string,
  trigger: "poll" | "finalize",
  now: string,
): Promise<JobRecord> {
  if (!job.inferenceAttemptId) {
    return job;
  }

  const queueMessage: QueueJobMessage = {
    kind: "process-job",
    jobId: job.jobId,
    requestId,
    uploadTraceId: job.uploadTraceId ?? requestId,
    traceId: job.traceId,
    schemaVersion: job.schemaVersion,
    sourceObjectKey: job.sourceObjectKey,
    resultObjectKey: job.resultObjectKey,
    modelVersion: job.modelVersion ?? null,
    teamSelection: job.teamSelection ?? null,
  };

  const refreshedJob = await updateJobState(
    env,
    job.jobId,
    {
      queuedAt: now,
      updatedAt: now,
    },
    {
      requestId,
      traceId: job.traceId,
      eventType: "job.processing.retry_dispatch_requested",
      message: "Retry dispatch requested for queued stale attempt.",
      payload: {
        ...queueMessage,
        attemptCount: job.attemptCount ?? 0,
        inferenceAttemptId: job.inferenceAttemptId,
      },
    },
  );

  ctx.waitUntil(
    env.ANALYSIS_QUEUE.send(queueMessage)
      .then(async () => {
        await appendJobEvent(env.DB, {
          jobId: job.jobId,
          requestId,
          traceId: job.traceId,
          eventType:
            trigger === "poll"
              ? "job.processing.retry_dispatched"
              : "job.processing.retry_dispatched",
          message: "Retry dispatch queued after stale processing timeout.",
          payload: {
            ...queueMessage,
            attemptCount: job.attemptCount ?? 0,
            inferenceAttemptId: job.inferenceAttemptId,
          },
          createdAt: now,
        });
      })
      .catch(async (error) => {
        await appendJobEvent(env.DB, {
          jobId: job.jobId,
          requestId,
          traceId: job.traceId,
          eventType: "job.processing.retry_dispatch_failed",
          message:
            error instanceof Error ? error.message : "Retry dispatch failed.",
          payload: {
            ...queueMessage,
            attemptCount: job.attemptCount ?? 0,
            inferenceAttemptId: job.inferenceAttemptId,
          },
          createdAt: now,
        });
      }),
  );

  return refreshedJob;
}

function isOlderThan(timestamp: string, ageSeconds: number): boolean {
  const parsed = Date.parse(timestamp);
  if (!Number.isFinite(parsed)) {
    return false;
  }
  return Date.now() - parsed >= ageSeconds * 1000;
}

function effectiveProcessingTimeoutSeconds(
  job: JobRecord,
  runtime: ReturnType<typeof resolveRuntimeConfig>,
): number {
  if (job.teamSelection?.mode === "team") {
    return Math.max(
      runtime.processingTimeoutSeconds,
      runtime.selectedTeamProcessingTimeoutSeconds,
    );
  }
  return runtime.processingTimeoutSeconds;
}

function latestTimestamp(
  ...timestamps: Array<string | null | undefined>
): string {
  let latestValue: string | null = null;
  let latestMs = Number.NEGATIVE_INFINITY;
  for (const timestamp of timestamps) {
    if (!timestamp) {
      continue;
    }
    const parsed = Date.parse(timestamp);
    if (!Number.isFinite(parsed)) {
      continue;
    }
    if (parsed >= latestMs) {
      latestMs = parsed;
      latestValue = timestamp;
    }
  }
  return latestValue ?? new Date(0).toISOString();
}
