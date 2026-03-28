import type { MessageBatch } from "@cloudflare/workers-types";
import type { Env } from "../env";
import type { InferenceDispatchRequest, JobRecord, QueueJobMessage } from "../types";
import { getJobSnapshot, updateJobState } from "../do/job-state-client";
import { appendJobEvent } from "../db";
import { createPresignedReadTarget } from "../r2/presign";
import { resolveRuntimeConfig } from "../env";

export async function handleQueueBatch(batch: MessageBatch<QueueJobMessage>, env: Env): Promise<void> {
  for (const message of batch.messages) {
    if (message.body.kind !== "process-job") {
      continue;
    }

    let currentJob: JobRecord | null = null;
    let inferenceAttemptId: string | null = null;

    try {
      currentJob = await getJobSnapshot(env, message.body.jobId);
      if (
        !currentJob ||
        currentJob.status === "processing" ||
        currentJob.status === "completed" ||
        currentJob.status === "succeeded" ||
        currentJob.status === "failed" ||
        currentJob.status === "expired" ||
        currentJob.status === "cancelled"
      ) {
        continue;
      }

      inferenceAttemptId = currentJob.inferenceAttemptId ?? crypto.randomUUID().replace(/-/g, "");
      const startedAt = new Date().toISOString();
      const modelVersion = currentJob.modelVersion ?? message.body.modelVersion ?? `external:${resolveInferenceServiceName(env)}`;

      const processingJob = await updateJobState(
        env,
        message.body.jobId,
        {
          status: "processing",
          stage: "Dispatching job to external inference service",
          progress: Math.max(currentJob.progress, 0.5),
          startedAt,
          modelVersion,
          uploadTraceId: currentJob.uploadTraceId ?? message.body.uploadTraceId ?? null,
          inferenceAttemptId
        },
        {
          requestId: message.body.requestId,
          traceId: message.body.traceId || currentJob.traceId,
          eventType: "queue.dispatch",
          message: "Job marked processing before external inference dispatch.",
          payload: {
            jobId: message.body.jobId,
            requestId: message.body.requestId,
            traceId: message.body.traceId || currentJob.traceId,
            uploadTraceId: currentJob.uploadTraceId ?? message.body.uploadTraceId ?? null,
            inferenceAttemptId,
            modelVersion
          }
        }
      );

      await appendJobEvent(env.DB, {
        jobId: message.body.jobId,
        requestId: message.body.requestId,
        traceId: message.body.traceId || currentJob.traceId,
        eventType: "queue.dispatch",
        message: "Job dispatched to external inference service.",
        payload: {
          jobId: message.body.jobId,
          requestId: message.body.requestId,
          traceId: message.body.traceId || currentJob.traceId,
          uploadTraceId: processingJob.uploadTraceId ?? message.body.uploadTraceId ?? null,
          inferenceAttemptId,
          modelVersion
        },
        createdAt: startedAt
      });

      const dispatchRequest = await buildInferenceDispatchRequest(env, processingJob, message.body, inferenceAttemptId);
      const response = await fetch(dispatchRequest.url, {
        method: "POST",
        headers: dispatchRequest.headers,
        body: JSON.stringify(dispatchRequest.body)
      });

      if (!response.ok) {
        const bodyText = await response.text().catch(() => "");
        throw new Error(`External inference dispatch failed with status ${response.status}${bodyText ? `: ${bodyText}` : ""}`);
      }

      await appendJobEvent(env.DB, {
        jobId: message.body.jobId,
        requestId: message.body.requestId,
        traceId: message.body.traceId || currentJob.traceId,
        eventType: "queue.dispatch.accepted",
        message: "External inference service accepted job.",
        payload: {
          status: response.status,
          jobId: message.body.jobId,
          requestId: message.body.requestId,
          uploadTraceId: processingJob.uploadTraceId ?? message.body.uploadTraceId ?? null,
          inferenceAttemptId,
          modelVersion
        },
        createdAt: new Date().toISOString()
      });

      console.info(
        JSON.stringify({
          requestId: message.body.requestId,
          jobId: message.body.jobId,
          traceId: message.body.traceId || currentJob.traceId,
          uploadTraceId: processingJob.uploadTraceId ?? message.body.uploadTraceId ?? null,
          inferenceAttemptId,
          event: "queue.dispatch.accepted",
          status: response.status
        })
      );
    } catch (error) {
      const failureReason = error instanceof Error ? error.message : "Queue dispatch failed.";
      if (currentJob) {
        const failedAt = new Date().toISOString();
        await updateJobState(
          env,
          message.body.jobId,
          {
            status: "failed",
            stage: "External inference dispatch failed",
            progress: Math.max(currentJob.progress, 0.5),
            failureReason,
            modelVersion: currentJob.modelVersion ?? message.body.modelVersion ?? null,
            updatedAt: failedAt
          },
          {
            requestId: message.body.requestId,
            traceId: message.body.traceId || currentJob.traceId,
            eventType: "queue.dispatch.failed",
            message: failureReason,
            payload: {
              jobId: message.body.jobId,
              requestId: message.body.requestId,
              traceId: message.body.traceId || currentJob.traceId,
              uploadTraceId: currentJob.uploadTraceId ?? message.body.uploadTraceId ?? null,
              inferenceAttemptId,
              modelVersion: currentJob.modelVersion ?? message.body.modelVersion ?? null
            }
          }
        );

        await appendJobEvent(env.DB, {
          jobId: message.body.jobId,
          requestId: message.body.requestId,
          traceId: message.body.traceId || currentJob.traceId,
          eventType: "queue.dispatch.failed",
          message: failureReason,
          payload: {
            jobId: message.body.jobId,
            requestId: message.body.requestId,
            traceId: message.body.traceId || currentJob.traceId,
            uploadTraceId: currentJob.uploadTraceId ?? message.body.uploadTraceId ?? null,
            inferenceAttemptId,
            modelVersion: currentJob.modelVersion ?? message.body.modelVersion ?? null
          },
          createdAt: new Date().toISOString()
        });

        await sendDeadLetterRecord(env, {
          kind: "dead-letter-job",
          jobId: message.body.jobId,
          requestId: message.body.requestId,
          traceId: message.body.traceId || currentJob.traceId,
          schemaVersion: message.body.schemaVersion,
          sourceObjectKey: message.body.sourceObjectKey,
          resultObjectKey: message.body.resultObjectKey,
          modelVersion: currentJob.modelVersion ?? message.body.modelVersion ?? null,
          failureReason,
          attempts: null
        }).catch((dlqError) => {
          console.error(
            JSON.stringify({
              requestId: message.body.requestId,
              jobId: message.body.jobId,
              traceId: message.body.traceId || currentJob?.traceId,
              event: "dead_letter.enqueue_failed",
              message: dlqError instanceof Error ? dlqError.message : "Failed to enqueue dead-letter record."
            })
          );
        });
      }
      console.error(
        JSON.stringify({
          requestId: message.body.requestId,
          jobId: message.body.jobId,
          event: "queue.dispatch.error",
          message: failureReason
        })
      );
    }
  }
  batch.ackAll();
}

async function buildInferenceDispatchRequest(
  env: Env,
  job: JobRecord,
  message: QueueJobMessage,
  inferenceAttemptId: string
): Promise<{ url: string; headers: Record<string, string>; body: InferenceDispatchRequest }> {
  if (!env.INFERENCE_BASE_URL) {
    throw new Error("Missing inference service base URL.");
  }

  const callbackUrl = new URL("/internal/inference/callback", env.CONTROL_PLANE_BASE_URL).toString();
  const callbackSecret = env.INFERENCE_SHARED_SECRET || env.CONTROL_PLANE_SHARED_SECRET;
  const readTarget = await createPresignedReadTarget(env, {
    objectKey: job.sourceObjectKey,
    expiresInSeconds: Math.max(resolveRuntimeConfig(env).jobTtlSeconds, 3600),
    bucketName: env.R2_UPLOAD_BUCKET_NAME
  });

  const modelVersion = job.modelVersion ?? message.modelVersion ?? `external:${resolveInferenceServiceName(env)}`;
  const body: InferenceDispatchRequest = {
    jobId: job.jobId,
    requestId: message.requestId,
    uploadTraceId: job.uploadTraceId ?? message.uploadTraceId,
    inferenceAttemptId,
    traceId: job.traceId,
    sourceObjectKey: job.sourceObjectKey,
    sourceUrl: readTarget.sourceUrl,
    resultObjectKey: job.resultObjectKey,
    callbackUrl,
    callbackSecret,
    schemaVersion: job.schemaVersion,
    modelVersion,
    installId: job.installId,
    appVersion: job.appVersion,
    analysisVersion: job.analysisVersion,
    requestedModel: job.modelVersion ?? message.modelVersion ?? null
  };

  return {
    url: new URL("/v1/analyze", env.INFERENCE_BASE_URL).toString(),
    headers: {
      "content-type": "application/json",
      "x-hoops-inference-secret": callbackSecret,
      "x-request-id": message.requestId,
      "x-trace-id": job.traceId,
      "x-hoops-upload-trace-id": job.uploadTraceId ?? message.uploadTraceId,
      "x-hoops-inference-attempt-id": inferenceAttemptId
    },
    body
  };
}

async function sendDeadLetterRecord(
  env: Env,
  payload: {
    kind: "dead-letter-job";
    jobId: string;
    requestId: string;
    traceId: string;
    schemaVersion: string;
    sourceObjectKey: string;
    resultObjectKey: string;
    modelVersion?: string | null;
    failureReason: string;
    attempts?: number | null;
  }
): Promise<void> {
  await env.ANALYSIS_DLQ.send(payload);
}

function resolveInferenceServiceName(env: Env): string {
  try {
    return new URL(env.INFERENCE_BASE_URL).hostname || "service";
  } catch {
    return "service";
  }
}
