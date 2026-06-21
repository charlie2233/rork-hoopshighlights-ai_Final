import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const {
  createControlPlaneHarness,
  invokePublicRoute,
  parseJsonResponse,
  uploadObject,
} = harness;

test("multipart complete is idempotent when the assembled source object already exists", async () => {
  const controlPlane = createControlPlaneHarness();

  const createResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    "/uploads/presign",
    {
      filename: "background-resume-game.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-background-resume",
      appVersion: "1.0.0",
      analysisVersion: "background-upload-idempotency",
    },
    { "x-trace-id": "trace-background-upload-idempotency" },
  );
  assert.equal(createResponse.status, 201);
  const createJson = await parseJsonResponse<{
    jobId: string;
    sourceObjectKey: string;
    uploadUrl: string;
    status: string;
  }>(createResponse);

  await uploadObject(
    controlPlane,
    createJson.uploadUrl,
    new TextEncoder().encode("already assembled background upload"),
  );

  const completeResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    "/uploads/multipart/complete",
    {
      jobId: createJson.jobId,
      installId: "install-background-resume",
      uploadId: "duplicate-background-upload",
      parts: [{ partNumber: 1, etag: "etag-1" }],
    },
    { "x-trace-id": "trace-background-upload-idempotency" },
  );

  assert.equal(completeResponse.status, 200);
  const completeJson = await parseJsonResponse<{ status: string }>(
    completeResponse,
  );
  assert.equal(completeJson.status, createJson.status);

  const completeEvent = controlPlane.state.events.find(
    (event) => event.eventType === "job.multipart_upload.completed",
  );
  assert.equal(completeEvent?.message, "Resumable upload was already assembled.");
  assert.deepEqual(
    completeEvent?.payload,
    {
      partCount: 1,
      alreadyAssembled: true,
      uploadTraceId: controlPlane.state.jobs.get(createJson.jobId)?.uploadTraceId ?? null,
    },
  );

  const serializedPayloads = JSON.stringify(
    controlPlane.state.events.map((event) => event.payload),
  );
  assert.equal(serializedPayloads.includes(createJson.uploadUrl), false);
  assert.equal(serializedPayloads.includes(createJson.sourceObjectKey), false);
});
