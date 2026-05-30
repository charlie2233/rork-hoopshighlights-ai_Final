import type { MessageBatch } from "@cloudflare/workers-types";
import type { Env } from "../env";
import type {
  InferenceDispatchRequest,
  JobRecord,
  QueueJobMessage,
} from "../types";
import { getJobSnapshot, updateJobState } from "../do/job-state-client";
import { appendJobEvent } from "../db";
import { createPresignedReadTarget } from "../r2/presign";
import { resolveRuntimeConfig } from "../env";

const DEFAULT_INFERENCE_MODEL_VERSION =
  "videomae:MCG-NJU/videomae-base-finetuned-kinetics";

interface AnalysisDispatchProvider {
  name: "inference" | "editing";
  baseUrl: string;
  ingressSecret: string;
}

export async function handleQueueBatch(
  batch: MessageBatch<QueueJobMessage>,
  env: Env,
): Promise<void> {
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

      inferenceAttemptId =
        currentJob.inferenceAttemptId ?? crypto.randomUUID().replace(/-/g, "");
      const startedAt = new Date().toISOString();
      const modelVersion =
        currentJob.modelVersion ??
        message.body.modelVersion ??
        DEFAULT_INFERENCE_MODEL_VERSION;
      const currentAttemptCount = Math.max(currentJob.attemptCount ?? 0, 0);

      const dispatchingJob = await updateJobState(
        env,
        message.body.jobId,
        {
          stage: "Dispatching job to external inference service",
          progress: Math.max(currentJob.progress, 0.5),
          modelVersion,
          uploadTraceId:
            currentJob.uploadTraceId ?? message.body.uploadTraceId ?? null,
          inferenceAttemptId,
          attemptCount: currentAttemptCount,
        },
        {
          requestId: message.body.requestId,
          traceId: message.body.traceId || currentJob.traceId,
          eventType: "queue.dispatch",
          message: "Job queued for external inference dispatch.",
          payload: {
            jobId: message.body.jobId,
            requestId: message.body.requestId,
            traceId: message.body.traceId || currentJob.traceId,
            uploadTraceId:
              currentJob.uploadTraceId ?? message.body.uploadTraceId ?? null,
            inferenceAttemptId,
            modelVersion,
          },
        },
      );
      const dispatchingSnapshot =
        (await getJobSnapshot(env, message.body.jobId)) ?? dispatchingJob;

      await appendJobEvent(env.DB, {
        jobId: message.body.jobId,
        requestId: message.body.requestId,
        traceId: message.body.traceId || currentJob.traceId,
        eventType: "queue.dispatch",
        message: "Job queued for external inference dispatch.",
        payload: {
          jobId: message.body.jobId,
          requestId: message.body.requestId,
          traceId: message.body.traceId || currentJob.traceId,
          uploadTraceId:
            dispatchingSnapshot.uploadTraceId ??
            message.body.uploadTraceId ??
            null,
          inferenceAttemptId,
          modelVersion,
        },
        createdAt: startedAt,
      });

      const dispatchRequest = await buildInferenceDispatchRequest(
        env,
        dispatchingSnapshot,
        message.body,
        inferenceAttemptId,
      );
      const dispatchResult = await dispatchAnalysisJob(env, dispatchRequest);

      await appendJobEvent(env.DB, {
        jobId: message.body.jobId,
        requestId: message.body.requestId,
        traceId: message.body.traceId || currentJob.traceId,
        eventType: "queue.dispatch.accepted",
        message: "External inference service accepted job.",
        payload: {
          status: dispatchResult.status,
          jobId: message.body.jobId,
          requestId: message.body.requestId,
          uploadTraceId:
            dispatchingSnapshot.uploadTraceId ??
            message.body.uploadTraceId ??
            null,
          inferenceAttemptId,
          modelVersion,
          provider: dispatchResult.provider,
        },
        createdAt: new Date().toISOString(),
      });

      console.info(
        JSON.stringify({
          requestId: message.body.requestId,
          jobId: message.body.jobId,
          traceId: message.body.traceId || currentJob.traceId,
          uploadTraceId:
            dispatchingSnapshot.uploadTraceId ??
            message.body.uploadTraceId ??
            null,
          inferenceAttemptId,
          event: "queue.dispatch.accepted",
          status: dispatchResult.status,
          provider: dispatchResult.provider,
        }),
      );

      const postAcceptJob = await getJobSnapshot(env, message.body.jobId);
      if (postAcceptJob) {
        const acceptedAttemptCount =
          Math.max(postAcceptJob.attemptCount ?? currentAttemptCount, 0) + 1;
        const acceptancePatch: Partial<JobRecord> = {
          acceptedAt: startedAt,
          processingStartedAt: startedAt,
          attemptCount: acceptedAttemptCount,
          modelVersion,
          uploadTraceId:
            dispatchingSnapshot.uploadTraceId ??
            message.body.uploadTraceId ??
            null,
          inferenceAttemptId,
        };

        if (
          postAcceptJob.status !== "completed" &&
          postAcceptJob.status !== "failed" &&
          postAcceptJob.status !== "cancelled" &&
          postAcceptJob.status !== "succeeded" &&
          postAcceptJob.status !== "expired"
        ) {
          acceptancePatch.status = "processing";
          acceptancePatch.stage = "Running external inference service";
          acceptancePatch.progress = Math.max(postAcceptJob.progress, 0.6);
          acceptancePatch.startedAt = startedAt;
        }

        await updateJobState(env, message.body.jobId, acceptancePatch, {
          requestId: message.body.requestId,
          traceId: message.body.traceId || currentJob.traceId,
          eventType: "queue.dispatch.accepted",
          message: "External inference service accepted job.",
          payload: {
            status: dispatchResult.status,
            jobId: message.body.jobId,
            requestId: message.body.requestId,
            uploadTraceId:
              dispatchingSnapshot.uploadTraceId ??
              message.body.uploadTraceId ??
              null,
            inferenceAttemptId,
            modelVersion,
            provider: dispatchResult.provider,
          },
        });
      }
    } catch (error) {
      const failureReason =
        error instanceof Error ? error.message : "Queue dispatch failed.";
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
            modelVersion:
              currentJob.modelVersion ??
              message.body.modelVersion ??
              DEFAULT_INFERENCE_MODEL_VERSION,
            updatedAt: failedAt,
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
              uploadTraceId:
                currentJob.uploadTraceId ?? message.body.uploadTraceId ?? null,
              inferenceAttemptId,
              modelVersion:
                currentJob.modelVersion ??
                message.body.modelVersion ??
                DEFAULT_INFERENCE_MODEL_VERSION,
            },
          },
        );

        // Dispatch failure occurs before the external service accepts the job.
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
            uploadTraceId:
              currentJob.uploadTraceId ?? message.body.uploadTraceId ?? null,
            inferenceAttemptId,
            modelVersion:
              currentJob.modelVersion ??
              message.body.modelVersion ??
              DEFAULT_INFERENCE_MODEL_VERSION,
          },
          createdAt: new Date().toISOString(),
        });

        await sendDeadLetterRecord(env, {
          kind: "dead-letter-job",
          jobId: message.body.jobId,
          requestId: message.body.requestId,
          traceId: message.body.traceId || currentJob.traceId,
          schemaVersion: message.body.schemaVersion,
          sourceObjectKey: message.body.sourceObjectKey,
          resultObjectKey: message.body.resultObjectKey,
          modelVersion:
            currentJob.modelVersion ??
            message.body.modelVersion ??
            DEFAULT_INFERENCE_MODEL_VERSION,
          failureReason,
          attempts: null,
        }).catch((dlqError) => {
          console.error(
            JSON.stringify({
              requestId: message.body.requestId,
              jobId: message.body.jobId,
              traceId: message.body.traceId || currentJob?.traceId,
              event: "dead_letter.enqueue_failed",
              message:
                dlqError instanceof Error
                  ? dlqError.message
                  : "Failed to enqueue dead-letter record.",
            }),
          );
        });
      }
      console.error(
        JSON.stringify({
          requestId: message.body.requestId,
          jobId: message.body.jobId,
          event: "queue.dispatch.error",
          message: failureReason,
        }),
      );
    }
  }
  batch.ackAll();
}

async function buildInferenceDispatchRequest(
  env: Env,
  job: JobRecord,
  message: QueueJobMessage,
  inferenceAttemptId: string,
): Promise<{ callbackSecret: string; body: InferenceDispatchRequest }> {
  const callbackUrl = new URL(
    "/internal/inference/callback",
    env.CONTROL_PLANE_BASE_URL,
  ).toString();
  const callbackSecret =
    env.INFERENCE_SHARED_SECRET || env.CONTROL_PLANE_SHARED_SECRET;
  const readTarget = await createPresignedReadTarget(env, {
    objectKey: job.sourceObjectKey,
    expiresInSeconds: Math.max(resolveRuntimeConfig(env).jobTtlSeconds, 3600),
    bucketName: env.R2_UPLOAD_BUCKET_NAME,
  });

  const modelVersion =
    job.modelVersion ?? message.modelVersion ?? DEFAULT_INFERENCE_MODEL_VERSION;
  const body: InferenceDispatchRequest = {
    jobId: job.jobId,
    requestId: message.requestId,
    uploadTraceId: job.uploadTraceId ?? message.uploadTraceId,
    inferenceAttemptId,
    traceId: job.traceId,
    filename: job.filename,
    contentType: job.contentType,
    fileSizeBytes: job.fileSizeBytes,
    durationSeconds: job.durationSeconds,
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
    teamSelection: job.teamSelection ?? message.teamSelection ?? null,
    requestedModel: modelVersion.startsWith("xclip:") ? "xclip" : "videomae",
  };

  return {
    callbackSecret,
    body,
  };
}

async function dispatchAnalysisJob(
  env: Env,
  dispatchRequest: { callbackSecret: string; body: InferenceDispatchRequest },
): Promise<{ provider: AnalysisDispatchProvider["name"]; status: number }> {
  const providers = analysisDispatchProviders(env, dispatchRequest.body);
  if (providers.length === 0) {
    if (isSelectedTeamAnalysis(dispatchRequest.body)) {
      throw new Error(
        "Missing editing service base URL for selected-team analysis.",
      );
    }
    throw new Error("Missing inference service base URL.");
  }

  let lastFailure: {
    provider: AnalysisDispatchProvider["name"];
    status: number;
  } | null = null;
  for (const provider of providers) {
    const body = analysisDispatchBodyForProvider(
      dispatchRequest.body,
      provider,
    );
    const response = await fetch(
      new URL("/v1/analyze", provider.baseUrl).toString(),
      {
        method: "POST",
        headers: analysisDispatchHeaders(dispatchRequest, provider),
        body: JSON.stringify(body),
      },
    );

    if (response.ok) {
      return { provider: provider.name, status: response.status };
    }

    lastFailure = { provider: provider.name, status: response.status };
    if (!shouldTryNextAnalysisProvider(response.status)) {
      break;
    }
  }

  if (lastFailure) {
    throw new Error(
      `External inference dispatch failed with status ${lastFailure.status}.`,
    );
  }
  throw new Error("External inference dispatch failed.");
}

function analysisDispatchBodyForProvider(
  body: InferenceDispatchRequest,
  provider: AnalysisDispatchProvider,
): InferenceDispatchRequest {
  if (provider.name === "editing") {
    return body;
  }

  const legacyBody: InferenceDispatchRequest = {
    jobId: body.jobId,
    requestId: body.requestId,
    uploadTraceId: body.uploadTraceId,
    inferenceAttemptId: body.inferenceAttemptId,
    traceId: body.traceId,
    sourceObjectKey: body.sourceObjectKey,
    sourceUrl: body.sourceUrl,
    resultObjectKey: body.resultObjectKey,
    callbackUrl: body.callbackUrl,
    callbackSecret: body.callbackSecret,
    schemaVersion: body.schemaVersion,
    modelVersion: body.modelVersion,
    installId: body.installId,
    appVersion: body.appVersion,
    analysisVersion: body.analysisVersion,
    requestedModel: body.requestedModel,
    attemptCount: body.attemptCount,
  };

  if (body.teamSelection?.mode === "team") {
    legacyBody.teamSelection = body.teamSelection;
  }

  return legacyBody;
}

function analysisDispatchHeaders(
  dispatchRequest: { callbackSecret: string; body: InferenceDispatchRequest },
  provider: AnalysisDispatchProvider,
): Record<string, string> {
  return {
    "content-type": "application/json",
    "x-hoops-inference-secret": provider.ingressSecret,
    "x-request-id": dispatchRequest.body.requestId,
    "x-trace-id": dispatchRequest.body.traceId,
    "x-hoops-upload-trace-id": dispatchRequest.body.uploadTraceId,
    "x-hoops-inference-attempt-id": dispatchRequest.body.inferenceAttemptId,
  };
}

function analysisDispatchProviders(
  env: Env,
  body: InferenceDispatchRequest,
): AnalysisDispatchProvider[] {
  const inferenceProvider: AnalysisDispatchProvider | null =
    env.INFERENCE_BASE_URL &&
    (env.INFERENCE_SHARED_SECRET || env.CONTROL_PLANE_SHARED_SECRET)
      ? {
          name: "inference" as const,
          baseUrl: env.INFERENCE_BASE_URL,
          ingressSecret:
            env.INFERENCE_SHARED_SECRET || env.CONTROL_PLANE_SHARED_SECRET,
        }
      : null;
  const editingProvider: AnalysisDispatchProvider | null =
    env.EDITING_BASE_URL &&
    (env.EDITING_SHARED_SECRET ||
      env.INFERENCE_SHARED_SECRET ||
      env.CONTROL_PLANE_SHARED_SECRET)
      ? {
          name: "editing" as const,
          baseUrl: env.EDITING_BASE_URL,
          ingressSecret:
            env.EDITING_SHARED_SECRET ||
            env.INFERENCE_SHARED_SECRET ||
            env.CONTROL_PLANE_SHARED_SECRET,
        }
      : null;
  const providers = isSelectedTeamAnalysis(body)
    ? [editingProvider].filter(
        (provider): provider is AnalysisDispatchProvider => provider !== null,
      )
    : [inferenceProvider, editingProvider].filter(
        (provider): provider is AnalysisDispatchProvider => provider !== null,
      );
  return providers.filter(
    (provider) =>
      provider.baseUrl.trim().length > 0 &&
      provider.ingressSecret.trim().length > 0,
  );
}

function isSelectedTeamAnalysis(body: InferenceDispatchRequest): boolean {
  return body.teamSelection?.mode === "team";
}

function shouldTryNextAnalysisProvider(status: number): boolean {
  return status === 404 || status === 405 || status === 422 || status === 501;
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
  },
): Promise<void> {
  await env.ANALYSIS_DLQ.send(payload);
}
