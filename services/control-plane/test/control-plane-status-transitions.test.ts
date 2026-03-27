import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const {
  buildHeartbeatPayload,
  buildSuccessCallbackPayload,
  createControlPlaneHarness,
  invokeInternalRoute,
  invokePublicRoute,
  parseJsonResponse,
  uploadObject
} = harness;

test("control plane happy path advances created -> upload_pending -> processing -> completed", async () => {
  const harness = createControlPlaneHarness();

  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/v1/analysis/jobs",
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
  const createJson = await parseJsonResponse<{ jobId: string; sourceObjectKey: string; uploadUrl: string }>(createResponse);

  await uploadObject(harness, createJson.sourceObjectKey, new TextEncoder().encode("sample basketball clip"));
  assert.equal(createJson.sourceObjectKey.length > 0, true);

  const startResponse = await invokePublicRoute(
    harness,
    "POST",
    `/v1/analysis/jobs/${createJson.jobId}/start`,
    { installId: "install-local-001" },
    { "x-trace-id": "trace-happy-path" }
  );
  await parseJsonResponse<{ status: string }>(startResponse);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "upload_pending");
  assert.equal(harness.state.queueMessages.length, 0);

  const heartbeatResponse = await invokeInternalRoute(
    harness,
    "POST",
    `/v1/internal/inference/heartbeat/${createJson.jobId}`,
    buildHeartbeatPayload("Inference running", 0.61),
    { "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET }
  );
  const heartbeatJson = await parseJsonResponse<{ status: string; stage: string; progress: number }>(heartbeatResponse);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "processing");
  assert.equal(heartbeatJson.stage, "Inference running");
  assert.equal(heartbeatJson.progress, 0.61);

  const callbackResponse = await invokeInternalRoute(
    harness,
    "POST",
    `/v1/internal/inference/callback/${createJson.jobId}`,
    buildSuccessCallbackPayload({
      jobId: createJson.jobId,
      requestId: "trace-happy-path",
      modelVersion: "video-mae-stub-v1"
    }),
    { "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET }
  );
  const callbackJson = await parseJsonResponse<{ status: string; modelVersion: string | null; failureReason: string | null }>(callbackResponse);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "completed");
  assert.equal(callbackJson.modelVersion, "video-mae-stub-v1");
  assert.equal(callbackJson.failureReason, null);

  const finalResponse = await invokePublicRoute(harness, "GET", `/v1/analysis/jobs/${createJson.jobId}`);
  const finalJson = await parseJsonResponse<{
    status: string;
    modelVersion: string | null;
    failureReason: string | null;
    results: { clipCount: number; resultConfidence: number } | null;
  }>(finalResponse);

  assert.equal(finalJson.status, "completed");
  assert.equal(finalJson.modelVersion, "video-mae-stub-v1");
  assert.equal(finalJson.failureReason, null);
  assert.equal(finalJson.results?.clipCount, 1);
  assert.equal(finalJson.results?.resultConfidence, 0.91);
});
