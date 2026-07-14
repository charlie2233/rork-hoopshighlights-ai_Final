import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const {
  buildFailureCallbackPayload,
  createControlPlaneHarness,
  invokeInternalRoute,
  invokePublicRoute,
  parseJsonResponse,
  uploadObject
} = harness;

test("control plane failure path keeps the job failed and exposes failureReason", async () => {
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
    }
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
    }
  );
  assert.equal(startResponse.status, 200);
  await parseJsonResponse<{ status: string }>(startResponse);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "queued");

  const callbackResponse = await invokeInternalRoute(
    harness,
    "POST",
    "/internal/inference/callback",
    buildFailureCallbackPayload({
      jobId: createJson.jobId,
      requestId: "trace-failure-path",
      failureReason: "GPU worker timed out.",
      modelVersion: "video-mae-stub-v1"
    }),
    { "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET }
  );
  const callbackJson = await parseJsonResponse<{ status: string; failureReason: string | null }>(callbackResponse);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "failed");
  assert.equal(callbackJson.failureReason, "GPU worker timed out.");

  const finalResponse = await invokePublicRoute(
    harness,
    "GET",
    `/jobs/${createJson.jobId}?installId=install-local-001`,
  );
  const finalJson = await parseJsonResponse<{
    status: string;
    failureReason: string | null;
    results: unknown | null;
  }>(finalResponse);

  assert.equal(finalJson.status, "failed");
  assert.equal(finalJson.failureReason, "GPU worker timed out.");
  assert.equal(finalJson.results, null);
});
