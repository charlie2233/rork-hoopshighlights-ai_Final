import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const {
  buildSuccessCallbackPayload,
  createControlPlaneHarness,
  invokeInternalRoute,
  invokePublicRoute,
  parseJsonResponse,
  uploadObject
} = harness;

test("duplicate inference callback delivery is idempotent for a completed job", async () => {
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
      analysisVersion: "phase1b"
    },
    { "x-trace-id": "trace-duplicate-callback" }
  );
  const createJson = await parseJsonResponse<{ jobId: string; sourceObjectKey: string; uploadUrl: string }>(createResponse);

  await uploadObject(harness, createJson.uploadUrl, new TextEncoder().encode("sample basketball clip"));

  const startResponse = await invokePublicRoute(
    harness,
    "POST",
    "/jobs",
    {
      jobId: createJson.jobId,
      installId: "install-local-001",
      sourceObjectKey: createJson.sourceObjectKey
    },
    { "x-trace-id": "trace-duplicate-callback" }
  );
  assert.equal(startResponse.status, 200);

  const callbackPayload = buildSuccessCallbackPayload({
    jobId: createJson.jobId,
    requestId: "trace-duplicate-callback",
    modelVersion: "stub-inference-v1+phase1b",
    resultConfidence: 0.93
  });

  const firstCallback = await invokeInternalRoute(
    harness,
    "POST",
    "/internal/inference/callback",
    callbackPayload,
    { "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET, "x-trace-id": "trace-duplicate-callback" },
    "trace-duplicate-callback"
  );
  assert.equal(firstCallback.status, 200);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "completed");
  assert.equal(harness.state.events.filter((event) => event.eventType === "inference.callback.received").length, 1);

  const secondCallback = await invokeInternalRoute(
    harness,
    "POST",
    "/internal/inference/callback",
    callbackPayload,
    { "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET, "x-trace-id": "trace-duplicate-callback" },
    "trace-duplicate-callback-duplicate"
  );
  assert.equal(secondCallback.status, 200);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "completed");
  assert.equal(harness.state.events.filter((event) => event.eventType === "inference.callback.received").length, 1);
  assert.equal(harness.state.deadLetterMessages.length, 0);
});
