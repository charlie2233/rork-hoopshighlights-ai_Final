import type { MessageBatch } from "@cloudflare/workers-types";
import type { Env } from "../env";
import type { QueueJobMessage } from "../types";
import { getJobSnapshot, updateJobState } from "../do/job-state-client";
import { appendJobEvent } from "../db";

export async function handleQueueBatch(batch: MessageBatch<QueueJobMessage>, env: Env): Promise<void> {
  for (const message of batch.messages) {
    if (message.body.kind !== "process-job") {
      continue;
    }

    const job = await getJobSnapshot(env, message.body.jobId);
    if (!job || job.status === "succeeded" || job.status === "failed" || job.status === "expired" || job.status === "cancelled") {
      continue;
    }

    const startedAt = new Date().toISOString();
    await updateJobState(env, message.body.jobId, {
      status: "processing",
      stage: "Dispatching inference service",
      progress: Math.max(job.progress, 0.35),
      startedAt,
      modelVersion: job.modelVersion ?? null
    });
    await appendJobEvent(env.DB, {
      jobId: message.body.jobId,
      requestId: message.body.requestId,
      traceId: job.traceId,
      eventType: "queue.dispatch",
      message: "Queued job dispatched to inference service.",
      payload: message.body,
      createdAt: startedAt
    });

    await dispatchToInferenceService(env, message.body, job.traceId);
  }
  batch.ackAll();
}

async function dispatchToInferenceService(env: Env, message: QueueJobMessage, traceId: string): Promise<void> {
  if (!env.INFERENCE_BASE_URL) {
    return;
  }

  const callbackUrl = message.callbackUrl || `${env.INFERENCE_BASE_URL.replace(/\/$/, "")}/v1/internal/inference/callback/${message.jobId}`;
  await fetch(`${env.INFERENCE_BASE_URL.replace(/\/$/, "")}/v1/internal/inference/jobs/${message.jobId}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-hoops-inference-secret": env.INFERENCE_SHARED_SECRET,
      "x-request-id": message.requestId,
      "x-trace-id": traceId
    },
    body: JSON.stringify({
      jobId: message.jobId,
      installId: message.installId,
      analysisVersion: message.analysisVersion,
      sourceObjectKey: message.sourceObjectKey,
      resultObjectKey: message.resultObjectKey,
      callbackUrl
    })
  });
}
