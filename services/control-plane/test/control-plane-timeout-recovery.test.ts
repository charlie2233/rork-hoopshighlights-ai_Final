import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const {
  buildSuccessCallbackPayload,
  createControlPlaneHarness,
  invokeInternalRoute,
  invokePublicRoute,
  parseJsonResponse,
  uploadObject,
} = harness;

function promoteQueuedJobToStaleProcessing(
  harness: ReturnType<typeof createControlPlaneHarness>,
  jobId: string,
): {
  oldAttemptId: string;
} {
  const job = harness.state.jobs.get(jobId);
  if (!job) {
    throw new Error("Job not found.");
  }

  const staleAt = new Date(Date.now() - 10 * 60 * 1000).toISOString();
  const oldAttemptId = "attempt-stale-001";
  harness.state.jobs.set(jobId, {
    ...job,
    status: "processing",
    stage: "Running external inference service",
    progress: 0.62,
    acceptedAt: staleAt,
    processingStartedAt: staleAt,
    startedAt: staleAt,
    attemptCount: 1,
    inferenceAttemptId: oldAttemptId,
    updatedAt: staleAt,
  });

  return { oldAttemptId };
}

test("stale processing jobs are re-queued and complete on the next accepted attempt", async () => {
  const harness = createControlPlaneHarness({
    PROCESSING_TIMEOUT_SECONDS: "1",
    MAX_INFERENCE_ATTEMPTS: "2",
  });

  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "sample-game.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-local-001",
      appVersion: "1.0.0",
      analysisVersion: "phase2b",
    },
    { "x-trace-id": "trace-timeout-retry" },
  );
  const createJson = await parseJsonResponse<{
    jobId: string;
    sourceObjectKey: string;
    uploadUrl: string;
  }>(createResponse);

  await uploadObject(
    harness,
    createJson.uploadUrl,
    new TextEncoder().encode("sample basketball clip"),
  );

  const startResponse = await invokePublicRoute(
    harness,
    "POST",
    "/jobs",
    {
      jobId: createJson.jobId,
      installId: "install-local-001",
      sourceObjectKey: createJson.sourceObjectKey,
    },
    { "x-trace-id": "trace-timeout-retry" },
  );
  assert.equal(startResponse.status, 200);
  await harness.flush();
  harness.state.queueMessages.length = 0;

  const { oldAttemptId } = promoteQueuedJobToStaleProcessing(
    harness,
    createJson.jobId,
  );

  const recoveryResponse = await invokePublicRoute(
    harness,
    "GET",
    `/jobs/${createJson.jobId}`,
  );
  assert.equal(recoveryResponse.status, 200);
  const recoveryJson = await parseJsonResponse<{
    status: string;
    attemptCount: number | null;
    acceptedAt: string | null;
    processingStartedAt: string | null;
    inferenceAttemptId: string | null;
  }>(recoveryResponse);

  assert.equal(recoveryJson.status, "queued");
  assert.equal(recoveryJson.attemptCount, 1);
  assert.equal(recoveryJson.acceptedAt, null);
  assert.equal(recoveryJson.processingStartedAt, null);
  assert.equal(typeof recoveryJson.inferenceAttemptId, "string");

  const staleCallbackPayload = buildSuccessCallbackPayload({
    jobId: createJson.jobId,
    requestId: "trace-timeout-retry-stale",
    modelVersion: "videomae:MCG-NJU/videomae-base-finetuned-kinetics",
    inferenceAttemptId: oldAttemptId,
  });
  const staleCallbackResponse = await invokeInternalRoute(
    harness,
    "POST",
    "/internal/inference/callback",
    staleCallbackPayload,
    {
      "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET,
      "x-trace-id": "trace-timeout-retry-stale",
    },
    "trace-timeout-retry-stale",
  );
  assert.equal(staleCallbackResponse.status, 200);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "queued");
  assert.equal(harness.state.jobs.get(createJson.jobId)?.attemptCount, 1);
  assert.equal(harness.state.deadLetterMessages.length, 0);

  await harness.flush();
  const drained = await harness.drainQueue();
  assert.equal(drained, 1);
  assert.equal(harness.state.inferenceDispatches[0]?.jobStatus, "queued");
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "completed");
  assert.equal(harness.state.jobs.get(createJson.jobId)?.attemptCount, 2);
  assert.equal(
    typeof harness.state.jobs.get(createJson.jobId)?.acceptedAt,
    "string",
  );
  assert.equal(
    typeof harness.state.jobs.get(createJson.jobId)?.processingStartedAt,
    "string",
  );
  assert.equal(harness.state.deadLetterMessages.length, 0);

  const finalResponse = await invokePublicRoute(
    harness,
    "GET",
    `/jobs/${createJson.jobId}`,
  );
  const finalJson = await parseJsonResponse<{
    status: string;
    results: { clipCount: number } | null;
  }>(finalResponse);
  assert.equal(finalJson.status, "completed");
  assert.equal(finalJson.results?.clipCount, 1);
});

test("fresh inference heartbeats keep long-running processing jobs alive", async () => {
  const harness = createControlPlaneHarness({
    PROCESSING_TIMEOUT_SECONDS: "1",
    MAX_INFERENCE_ATTEMPTS: "2",
  });

  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "sample-game.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-local-001",
      appVersion: "1.0.0",
      analysisVersion: "phase2b",
    },
    { "x-trace-id": "trace-timeout-heartbeat" },
  );
  const createJson = await parseJsonResponse<{
    jobId: string;
    sourceObjectKey: string;
    uploadUrl: string;
  }>(createResponse);

  await uploadObject(
    harness,
    createJson.uploadUrl,
    new TextEncoder().encode("sample basketball clip"),
  );
  await invokePublicRoute(
    harness,
    "POST",
    "/jobs",
    {
      jobId: createJson.jobId,
      installId: "install-local-001",
      sourceObjectKey: createJson.sourceObjectKey,
    },
    { "x-trace-id": "trace-timeout-heartbeat" },
  );
  await harness.flush();
  harness.state.queueMessages.length = 0;

  promoteQueuedJobToStaleProcessing(harness, createJson.jobId);

  const heartbeatResponse = await invokeInternalRoute(
    harness,
    "POST",
    `/internal/inference/heartbeat/${createJson.jobId}`,
    { stage: "Analyzing in cloud" },
    {
      "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET,
      "x-trace-id": "trace-timeout-heartbeat",
    },
    "trace-timeout-heartbeat",
  );
  assert.equal(heartbeatResponse.status, 200);
  const heartbeatJson = await parseJsonResponse<{
    status: string;
    stage: string;
    processingStartedAt: string | null;
  }>(heartbeatResponse);
  assert.equal(heartbeatJson.status, "processing");
  assert.equal(heartbeatJson.stage, "Analyzing in cloud");
  assert.equal(typeof heartbeatJson.processingStartedAt, "string");

  const recoveryResponse = await invokePublicRoute(
    harness,
    "GET",
    `/jobs/${createJson.jobId}`,
  );
  assert.equal(recoveryResponse.status, 200);
  const recoveryJson = await parseJsonResponse<{
    status: string;
    attemptCount: number | null;
    stage: string;
  }>(recoveryResponse);
  assert.equal(recoveryJson.status, "processing");
  assert.equal(recoveryJson.attemptCount, 1);
  assert.equal(recoveryJson.stage, "Analyzing in cloud");
  assert.equal(harness.state.queueMessages.length, 0);
  assert.equal(harness.state.deadLetterMessages.length, 0);
});

test("fresh processing callbacks keep long-running processing jobs alive", async () => {
  const harness = createControlPlaneHarness({
    PROCESSING_TIMEOUT_SECONDS: "1",
    MAX_INFERENCE_ATTEMPTS: "2",
  });

  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "sample-game.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-local-001",
      appVersion: "1.0.0",
      analysisVersion: "phase2b",
    },
    { "x-trace-id": "trace-timeout-processing-callback" },
  );
  const createJson = await parseJsonResponse<{
    jobId: string;
    sourceObjectKey: string;
    uploadUrl: string;
  }>(createResponse);

  await uploadObject(
    harness,
    createJson.uploadUrl,
    new TextEncoder().encode("sample basketball clip"),
  );
  await invokePublicRoute(
    harness,
    "POST",
    "/jobs",
    {
      jobId: createJson.jobId,
      installId: "install-local-001",
      sourceObjectKey: createJson.sourceObjectKey,
    },
    { "x-trace-id": "trace-timeout-processing-callback" },
  );
  await harness.flush();
  harness.state.queueMessages.length = 0;

  const { oldAttemptId } = promoteQueuedJobToStaleProcessing(
    harness,
    createJson.jobId,
  );

  const progressResponse = await invokeInternalRoute(
    harness,
    "POST",
    "/internal/inference/callback",
    {
      jobId: createJson.jobId,
      requestId: "trace-timeout-processing-callback-progress",
      status: "processing",
      stage: "Analyzing in cloud",
      progress: 0.72,
      schemaVersion: "phase2b",
      modelVersion: "editing-cloud-v1",
      uploadTraceId: "upload-trace-processing-callback",
      inferenceAttemptId: oldAttemptId,
      traceId: "trace-timeout-processing-callback",
    },
    {
      "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET,
      "x-trace-id": "trace-timeout-processing-callback-progress",
    },
    "trace-timeout-processing-callback-progress",
  );
  assert.equal(progressResponse.status, 200);
  const progressJson = await parseJsonResponse<{
    status: string;
    stage: string;
    progress: number;
  }>(progressResponse);
  assert.equal(progressJson.status, "processing");
  assert.equal(progressJson.stage, "Analyzing in cloud");
  assert.equal(progressJson.progress, 0.72);

  const recoveryResponse = await invokePublicRoute(
    harness,
    "GET",
    `/jobs/${createJson.jobId}`,
  );
  assert.equal(recoveryResponse.status, 200);
  const recoveryJson = await parseJsonResponse<{
    status: string;
    attemptCount: number | null;
    stage: string;
  }>(recoveryResponse);
  assert.equal(recoveryJson.status, "processing");
  assert.equal(recoveryJson.attemptCount, 1);
  assert.equal(recoveryJson.stage, "Analyzing in cloud");
  assert.equal(harness.state.queueMessages.length, 0);
  assert.equal(harness.state.deadLetterMessages.length, 0);
});

test("selected-team editing jobs use the longer selected-team processing timeout", async () => {
  const harness = createControlPlaneHarness({
    PROCESSING_TIMEOUT_SECONDS: "1",
    SELECTED_TEAM_PROCESSING_TIMEOUT_SECONDS: "3600",
    MAX_INFERENCE_ATTEMPTS: "1",
  });

  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "sample-game.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-local-001",
      appVersion: "1.0.0",
      analysisVersion: "phase2b",
    },
    { "x-trace-id": "trace-selected-team-timeout" },
  );
  const createJson = await parseJsonResponse<{
    jobId: string;
    sourceObjectKey: string;
    uploadUrl: string;
  }>(createResponse);

  await uploadObject(
    harness,
    createJson.uploadUrl,
    new TextEncoder().encode("sample basketball clip"),
  );
  await invokePublicRoute(
    harness,
    "POST",
    "/jobs",
    {
      jobId: createJson.jobId,
      installId: "install-local-001",
      sourceObjectKey: createJson.sourceObjectKey,
    },
    { "x-trace-id": "trace-selected-team-timeout" },
  );
  await harness.flush();
  harness.state.queueMessages.length = 0;

  promoteQueuedJobToStaleProcessing(harness, createJson.jobId);
  const job = harness.state.jobs.get(createJson.jobId);
  if (!job) {
    throw new Error("Job not found.");
  }
  harness.state.jobs.set(createJson.jobId, {
    ...job,
    teamSelection: {
      mode: "team",
      teamId: "team_light",
      colorLabel: "white",
      confidenceThreshold: 0.85,
      includeUncertain: true,
    },
  });

  const recoveryResponse = await invokePublicRoute(
    harness,
    "GET",
    `/jobs/${createJson.jobId}`,
  );
  assert.equal(recoveryResponse.status, 200);
  const recoveryJson = await parseJsonResponse<{
    status: string;
    attemptCount: number | null;
    stage: string;
  }>(recoveryResponse);
  assert.equal(recoveryJson.status, "processing");
  assert.equal(recoveryJson.attemptCount, 1);
  assert.equal(recoveryJson.stage, "Running external inference service");
  assert.equal(harness.state.queueMessages.length, 0);
  assert.equal(harness.state.deadLetterMessages.length, 0);
});

test("late callbacks do not regress attemptCount after retry acceptance", async () => {
  const harness = createControlPlaneHarness({
    PROCESSING_TIMEOUT_SECONDS: "1",
    MAX_INFERENCE_ATTEMPTS: "2",
  });

  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "sample-game.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-local-001",
      appVersion: "1.0.0",
      analysisVersion: "phase2b",
    },
    { "x-trace-id": "trace-timeout-late-callback" },
  );
  const createJson = await parseJsonResponse<{
    jobId: string;
    sourceObjectKey: string;
    uploadUrl: string;
  }>(createResponse);

  await uploadObject(
    harness,
    createJson.uploadUrl,
    new TextEncoder().encode("sample basketball clip"),
  );
  await invokePublicRoute(
    harness,
    "POST",
    "/jobs",
    {
      jobId: createJson.jobId,
      installId: "install-local-001",
      sourceObjectKey: createJson.sourceObjectKey,
    },
    { "x-trace-id": "trace-timeout-late-callback" },
  );
  await harness.flush();
  harness.state.queueMessages.length = 0;

  const job = harness.state.jobs.get(createJson.jobId);
  if (!job) {
    throw new Error("Job not found.");
  }

  const activeAttemptId = "attempt-active-002";
  const staleAt = new Date(Date.now() - 10 * 60 * 1000).toISOString();
  harness.state.jobs.set(createJson.jobId, {
    ...job,
    status: "processing",
    stage: "Running external inference service",
    progress: 0.84,
    acceptedAt: staleAt,
    processingStartedAt: staleAt,
    startedAt: staleAt,
    attemptCount: 2,
    inferenceAttemptId: activeAttemptId,
    updatedAt: staleAt,
  });

  const lateCallbackPayload = buildSuccessCallbackPayload({
    jobId: createJson.jobId,
    requestId: "trace-timeout-late-callback-result",
    modelVersion: "videomae:MCG-NJU/videomae-base-finetuned-kinetics",
    inferenceAttemptId: activeAttemptId,
    attemptCount: 1,
  });

  const lateCallbackResponse = await invokeInternalRoute(
    harness,
    "POST",
    "/internal/inference/callback",
    lateCallbackPayload,
    {
      "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET,
      "x-trace-id": "trace-timeout-late-callback-result",
    },
    "trace-timeout-late-callback-result",
  );

  assert.equal(lateCallbackResponse.status, 200);
  const lateCallbackJson = await parseJsonResponse<{
    status: string;
    attemptCount: number | null;
    acceptedAt: string | null;
    processingStartedAt: string | null;
  }>(lateCallbackResponse);

  assert.equal(lateCallbackJson.status, "completed");
  assert.equal(lateCallbackJson.attemptCount, 2);
  assert.equal(typeof lateCallbackJson.acceptedAt, "string");
  assert.equal(typeof lateCallbackJson.processingStartedAt, "string");
  assert.equal(harness.state.jobs.get(createJson.jobId)?.attemptCount, 2);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "completed");
});

test("exhausted stale processing retries fail terminally with a timeout reason", async () => {
  const harness = createControlPlaneHarness({
    PROCESSING_TIMEOUT_SECONDS: "1",
    MAX_INFERENCE_ATTEMPTS: "1",
  });

  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "sample-game.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-local-001",
      appVersion: "1.0.0",
      analysisVersion: "phase2b",
    },
  );
  const createJson = await parseJsonResponse<{
    jobId: string;
    sourceObjectKey: string;
    uploadUrl: string;
  }>(createResponse);

  await uploadObject(
    harness,
    createJson.uploadUrl,
    new TextEncoder().encode("sample basketball clip"),
  );
  await invokePublicRoute(harness, "POST", "/jobs", {
    jobId: createJson.jobId,
    installId: "install-local-001",
    sourceObjectKey: createJson.sourceObjectKey,
  });
  await harness.flush();
  harness.state.queueMessages.length = 0;

  promoteQueuedJobToStaleProcessing(harness, createJson.jobId);

  const recoveryResponse = await invokePublicRoute(
    harness,
    "GET",
    `/jobs/${createJson.jobId}`,
  );
  assert.equal(recoveryResponse.status, 200);
  const recoveryJson = await parseJsonResponse<{
    status: string;
    failureReason: string | null;
    errorCode: string | null;
  }>(recoveryResponse);

  assert.equal(recoveryJson.status, "failed");
  assert.match(recoveryJson.failureReason ?? "", /timed out/i);
  assert.equal(recoveryJson.errorCode, "failed_timeout");
  assert.equal(harness.state.deadLetterMessages.length, 1);
  assert.equal(harness.state.queueMessages.length, 0);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "failed");
});
