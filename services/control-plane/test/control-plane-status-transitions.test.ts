import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const {
  createControlPlaneHarness,
  invokePublicRoute,
  parseJsonResponse,
  uploadObject
} = harness;

test("control plane happy path advances upload_pending -> uploaded -> queued -> processing -> completed", async () => {
  const harness = createControlPlaneHarness();

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
      analysisVersion: "phase1a"
    },
    { "x-trace-id": "trace-happy-path" }
  );
  assert.equal(createResponse.status, 201);
  const createJson = await parseJsonResponse<{
    jobId: string;
    sourceObjectKey: string;
    uploadUrl: string;
    status: string;
    uploadTraceId: string | null;
  }>(createResponse);

  await uploadObject(harness, createJson.uploadUrl, new TextEncoder().encode("sample basketball clip"));
  assert.equal(createJson.sourceObjectKey.length > 0, true);
  assert.equal(createJson.status, "upload_pending");
  assert.equal(typeof createJson.uploadTraceId, "string");

  const finalizeResponse = await invokePublicRoute(
    harness,
    "POST",
    "/jobs",
    {
      jobId: createJson.jobId,
      installId: "install-local-001",
      sourceObjectKey: createJson.sourceObjectKey
    },
    { "x-trace-id": "trace-happy-path" }
  );
  assert.equal(finalizeResponse.status, 200);
  const finalizeJson = await parseJsonResponse<{ status: string }>(finalizeResponse);
  assert.equal(finalizeJson.status, "queued");
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "queued");
  assert.equal(harness.state.queueMessages.length, 1);
  assert.equal("callbackUrl" in harness.state.queueMessages[0], false);
  assert.equal("installId" in harness.state.queueMessages[0], false);
  assert.equal("analysisVersion" in harness.state.queueMessages[0], false);
  assert.deepEqual(Object.keys(harness.state.queueMessages[0] ?? {}).sort(), [
    "jobId",
    "kind",
    "modelVersion",
    "requestId",
    "resultObjectKey",
    "schemaVersion",
    "sourceObjectKey",
    "traceId",
    "uploadTraceId"
  ]);

  const processedMessages = await harness.drainQueue();
  assert.equal(processedMessages, 1);
  assert.equal(harness.state.inferenceDispatches.length, 1);
  assert.equal(harness.state.inferenceDispatches[0]?.jobId, createJson.jobId);
  assert.equal(harness.state.inferenceDispatches[0]?.requestId.length > 0, true);
  assert.equal(harness.state.inferenceDispatches[0]?.jobStatus, "queued");
  assert.equal(harness.state.inferenceDispatches[0]?.uploadTraceId, createJson.uploadTraceId);
  assert.equal(typeof harness.state.inferenceDispatches[0]?.inferenceAttemptId, "string");
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "completed");
  assert.equal(harness.state.jobs.get(createJson.jobId)?.attemptCount, 1);
  assert.equal(typeof harness.state.jobs.get(createJson.jobId)?.acceptedAt, "string");
  assert.equal(typeof harness.state.jobs.get(createJson.jobId)?.processingStartedAt, "string");
  assert.equal(typeof harness.state.jobs.get(createJson.jobId)?.uploadTraceId, "string");
  assert.equal(typeof harness.state.jobs.get(createJson.jobId)?.inferenceAttemptId, "string");

  const finalResponse = await invokePublicRoute(harness, "GET", `/jobs/${createJson.jobId}`);
  assert.equal(finalResponse.status, 200);
  const finalJson = await parseJsonResponse<{
    status: string;
    modelVersion: string | null;
    failureReason: string | null;
    uploadTraceId: string | null;
    inferenceAttemptId: string | null;
    attemptCount: number | null;
    acceptedAt: string | null;
    processingStartedAt: string | null;
    results: { clipCount: number; resultConfidence: number } | null;
  }>(finalResponse);

  assert.equal(finalJson.status, "completed");
  assert.equal(finalJson.modelVersion, "videomae:MCG-NJU/videomae-base-finetuned-kinetics");
  assert.equal(finalJson.failureReason, null);
  assert.equal(typeof finalJson.uploadTraceId, "string");
  assert.equal(typeof finalJson.inferenceAttemptId, "string");
  assert.equal(finalJson.attemptCount, 1);
  assert.equal(typeof finalJson.acceptedAt, "string");
  assert.equal(typeof finalJson.processingStartedAt, "string");
  assert.equal(finalJson.results?.clipCount, 1);
  assert.equal(typeof finalJson.results?.resultConfidence, "number");
});
