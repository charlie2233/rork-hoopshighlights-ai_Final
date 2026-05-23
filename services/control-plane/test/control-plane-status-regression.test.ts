import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const {
  buildFailureCallbackPayload,
  buildSuccessCallbackPayload,
  createControlPlaneHarness,
  invokeInternalRoute,
  invokePublicRoute,
  parseJsonResponse,
  uploadObject
} = harness;

test("stale failure callbacks do not regress a completed job", async () => {
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
    { "x-trace-id": "trace-status-regression" }
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
    { "x-trace-id": "trace-status-regression" }
  );
  assert.equal(startResponse.status, 200);

  const successPayload = buildSuccessCallbackPayload({
    jobId: createJson.jobId,
    requestId: "trace-status-regression",
    modelVersion: "stub-inference-v1+phase1b",
    resultConfidence: 0.92
  });
  const successResponse = await invokeInternalRoute(
    harness,
    "POST",
    "/internal/inference/callback",
    successPayload,
    { "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET, "x-trace-id": "trace-status-regression" },
    "trace-status-regression"
  );
  assert.equal(successResponse.status, 200);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "completed");
  assert.equal(harness.state.deadLetterMessages.length, 0);

  const failurePayload = buildFailureCallbackPayload({
    jobId: createJson.jobId,
    requestId: "trace-status-regression-late-failure",
    failureReason: "Late callback retry should be ignored.",
    modelVersion: "stub-inference-v1+phase1b"
  });
  const failureResponse = await invokeInternalRoute(
    harness,
    "POST",
    "/internal/inference/callback",
    failurePayload,
    { "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET, "x-trace-id": "trace-status-regression-late-failure" },
    "trace-status-regression-late-failure"
  );

  const failureJson = await parseJsonResponse<{ status: string; failureReason: string | null }>(failureResponse);
  assert.equal(failureResponse.status, 200);
  assert.equal(failureJson.status, "completed");
  assert.equal(failureJson.failureReason, null);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "completed");
  assert.equal(harness.state.jobs.get(createJson.jobId)?.failureReason, null);
  assert.equal(harness.state.deadLetterMessages.length, 0);
  assert.equal(
    harness.state.events.filter((event) => event.eventType === "inference.callback.received").length,
    1
  );
});
