import type { MessageBatch } from "@cloudflare/workers-types";
import type { Env } from "../env";
import type { JobRecord, QueueJobMessage } from "../types";
import { getJobSnapshot, updateJobState } from "../do/job-state-client";
import { appendJobEvent } from "../db";
import { buildStubInferenceCallbackPayload } from "../stub/inference";

export async function handleQueueBatch(batch: MessageBatch<QueueJobMessage>, env: Env): Promise<void> {
  for (const message of batch.messages) {
    if (message.body.kind !== "process-job") {
      continue;
    }

    let currentJob: JobRecord | null = null;
    let callbackPayload: ReturnType<typeof buildStubInferenceCallbackPayload> | null = null;

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

      const startedAt = new Date().toISOString();
      await updateJobState(env, message.body.jobId, {
        status: "processing",
        stage: "Running stub inference",
        progress: Math.max(currentJob.progress, 0.35),
        startedAt,
        modelVersion: currentJob.modelVersion ?? message.body.modelVersion ?? null
      });
      await appendJobEvent(env.DB, {
        jobId: message.body.jobId,
        requestId: message.body.requestId,
        traceId: message.body.traceId || currentJob.traceId,
        eventType: "queue.dispatch",
        message: "Queued job dispatched to stub inference.",
        payload: message.body,
        createdAt: startedAt
      });

      console.info(
        JSON.stringify({
          requestId: message.body.requestId,
          jobId: message.body.jobId,
          traceId: message.body.traceId || currentJob.traceId,
          event: "queue.dispatch",
          status: "processing"
        })
      );

      callbackPayload = buildStubInferenceCallbackPayload(currentJob, message.body);
      await postCompletionCallback(env, message.body, callbackPayload, currentJob.traceId);
    } catch (error) {
      const failureReason = error instanceof Error ? error.message : "Queue dispatch failed.";
      if (currentJob) {
        const failedAt = new Date().toISOString();
        await updateJobState(
          env,
          message.body.jobId,
          {
            status: "failed",
            stage: "Queue dispatch failed",
            progress: Math.max(currentJob.progress, 0.35),
            failureReason,
            modelVersion: currentJob.modelVersion ?? message.body.modelVersion ?? null,
            updatedAt: failedAt
          },
          {
            requestId: message.body.requestId,
            traceId: message.body.traceId || currentJob.traceId,
            eventType: "queue.dispatch.failed",
            message: failureReason,
            payload: message.body
          }
        );

        await appendJobEvent(env.DB, {
          jobId: message.body.jobId,
          requestId: message.body.requestId,
          traceId: message.body.traceId || currentJob.traceId,
          eventType: "queue.dispatch.failed",
          message: failureReason,
          payload: message.body,
          createdAt: failedAt
        });

        await sendDeadLetterRecord(env, {
          kind: "dead-letter-job",
          jobId: message.body.jobId,
          requestId: message.body.requestId,
          traceId: message.body.traceId || currentJob.traceId,
          schemaVersion: message.body.schemaVersion,
          sourceObjectKey: message.body.sourceObjectKey,
          resultObjectKey: message.body.resultObjectKey,
          modelVersion: callbackPayload?.modelVersion ?? currentJob.modelVersion ?? message.body.modelVersion ?? null,
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

async function postCompletionCallback(
  env: Env,
  message: QueueJobMessage,
  callbackPayload: ReturnType<typeof buildStubInferenceCallbackPayload>,
  traceId: string
): Promise<void> {
  if (!env.CONTROL_PLANE_BASE_URL) {
    throw new Error("Missing control plane base URL for stub inference dispatch.");
  }
  const callbackUrl = new URL("/internal/inference/callback", env.CONTROL_PLANE_BASE_URL).toString();

  const response = await fetch(callbackUrl, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-hoops-inference-secret": env.INFERENCE_SHARED_SECRET || env.CONTROL_PLANE_SHARED_SECRET,
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

    await sendDeadLetterRecord(env, {
      kind: "dead-letter-job",
      jobId: message.jobId,
      requestId: message.requestId,
      traceId,
      schemaVersion: message.schemaVersion,
      sourceObjectKey: message.sourceObjectKey,
      resultObjectKey: message.resultObjectKey,
      modelVersion: callbackPayload.modelVersion ?? message.modelVersion ?? null,
      failureReason,
      attempts: null
    }).catch((dlqError) => {
      console.error(
        JSON.stringify({
          requestId: message.requestId,
          jobId: message.jobId,
          traceId,
          event: "dead_letter.enqueue_failed",
          message: dlqError instanceof Error ? dlqError.message : "Failed to enqueue dead-letter record."
        })
      );
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
