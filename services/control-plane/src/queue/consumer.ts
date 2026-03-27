import type { MessageBatch } from "@cloudflare/workers-types";
import type { Env } from "../env";
import type { QueueJobMessage } from "../types";
import { getJobSnapshot, updateJobState } from "../do/job-state-client";
import { appendJobEvent } from "../db";
import { buildStubInferenceCallbackPayload } from "../stub/inference";

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
      stage: "Running stub inference",
      progress: Math.max(job.progress, 0.35),
      startedAt,
      modelVersion: job.modelVersion ?? null
    });
    await appendJobEvent(env.DB, {
      jobId: message.body.jobId,
      requestId: message.body.requestId,
      traceId: job.traceId,
      eventType: "queue.dispatch",
      message: "Queued job dispatched to stub inference.",
      payload: message.body,
      createdAt: startedAt
    });

    console.info(
      JSON.stringify({
        requestId: message.body.requestId,
        jobId: message.body.jobId,
        traceId: job.traceId,
        event: "queue.dispatch",
        status: "processing"
      })
    );

    const callbackPayload = buildStubInferenceCallbackPayload(job, message.body);
    await postCompletionCallback(env, message.body, callbackPayload, job.traceId);
  }
  batch.ackAll();
}

async function postCompletionCallback(
  env: Env,
  message: QueueJobMessage,
  callbackPayload: ReturnType<typeof buildStubInferenceCallbackPayload>,
  traceId: string
): Promise<void> {
  const callbackUrl = message.callbackUrl;
  if (!callbackUrl) {
    throw new Error("Missing callback URL for stub inference dispatch.");
  }

  const response = await fetch(callbackUrl, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-hoops-inference-secret": env.CONTROL_PLANE_SHARED_SECRET,
      "x-request-id": message.requestId,
      "x-trace-id": traceId
    },
    body: JSON.stringify(callbackPayload)
  });

  if (!response.ok) {
    const bodyText = await response.text().catch(() => "");
    const failureReason = `Stub inference callback failed with status ${response.status}`;
    await updateJobState(
      env,
      message.jobId,
      {
        status: "failed",
        stage: "Stub inference callback failed",
        progress: Math.max(callbackPayload.resultConfidence ?? 0, 0.35),
        failureReason,
        modelVersion: callbackPayload.modelVersion ?? null,
        results: callbackPayload.results ?? null,
        resultConfidence: callbackPayload.resultConfidence ?? callbackPayload.confidence ?? null,
        updatedAt: new Date().toISOString()
      },
      {
        requestId: message.requestId,
        traceId,
        eventType: "stub.callback.failed",
        message: failureReason,
        payload: { status: response.status, bodyText }
      }
    );

    await appendJobEvent(env.DB, {
      jobId: message.jobId,
      requestId: message.requestId,
      traceId,
      eventType: "stub.callback.failed",
      message: failureReason,
      payload: { status: response.status, bodyText },
      createdAt: new Date().toISOString()
    });

    console.error(
      JSON.stringify({
        requestId: message.requestId,
        jobId: message.jobId,
        traceId,
        event: "stub.callback.failed",
        status: response.status
      })
    );
    return;
  }

  console.info(
    JSON.stringify({
      requestId: message.requestId,
      jobId: message.jobId,
      traceId,
      event: "stub.callback.sent",
      status: "succeeded"
    })
  );
}
