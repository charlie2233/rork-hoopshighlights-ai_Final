import assert from "node:assert/strict";
import { test } from "node:test";
import { chooseMultipartChunkSize } from "../src/r2/presign";
import harness from "../../../scripts/control-plane-harness";

const {
  createControlPlaneHarness,
  invokePublicRoute,
  parseJsonResponse,
} = harness;

const MEBIBYTE = 1024 * 1024;

test("multipart planner targets about 24 parts for large basketball videos", () => {
  assert.equal(chooseMultipartChunkSize(64 * MEBIBYTE), 8 * MEBIBYTE);
  assert.equal(chooseMultipartChunkSize(128 * MEBIBYTE), 8 * MEBIBYTE);
  assert.equal(chooseMultipartChunkSize(380 * MEBIBYTE), 16 * MEBIBYTE);
  assert.equal(chooseMultipartChunkSize(500 * MEBIBYTE), 24 * MEBIBYTE);
});

test("multipart planner caps preferred memory while preserving the R2 part-count limit", () => {
  assert.equal(chooseMultipartChunkSize(2 * 1024 * MEBIBYTE), 32 * MEBIBYTE);

  const veryLargeUploadBytes = 400 * 1024 * MEBIBYTE;
  const chunkSizeBytes = chooseMultipartChunkSize(veryLargeUploadBytes);
  assert.ok(Math.ceil(veryLargeUploadBytes / chunkSizeBytes) <= 10_000);
});

test("active multipart chunks renew the parent upload lease", async () => {
  const controlPlane = createControlPlaneHarness({
    R2_ACCOUNT_ID: "test-account",
    R2_ACCESS_KEY_ID: "test-access-key",
    R2_SECRET_ACCESS_KEY: "test-secret-key",
  });
  const createResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    "/uploads/presign",
    {
      filename: "slow-full-game.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 380 * MEBIBYTE,
      durationSeconds: 1_800,
      installId: "install-slow-upload",
      appVersion: "1.0.0",
      analysisVersion: "multipart-lease-renewal",
    },
  );
  assert.equal(createResponse.status, 201);
  const createJson = await parseJsonResponse<{ jobId: string }>(createResponse);

  const job = controlPlane.state.jobs.get(createJson.jobId);
  assert.ok(job);
  const nearlyExpiredAt = new Date(Date.now() + 5_000).toISOString();
  controlPlane.state.jobs.set(createJson.jobId, {
    ...job,
    expiresAt: nearlyExpiredAt,
  });

  const partResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    "/uploads/multipart/part",
    {
      jobId: createJson.jobId,
      installId: "install-slow-upload",
      uploadId: "active-multipart-upload",
      partNumber: 2,
    },
  );
  assert.equal(partResponse.status, 201);
  const partJson = await parseJsonResponse<{
    expiresAt: string;
    partNumber: number;
    uploadUrl: string;
  }>(partResponse);
  const renewedJob = controlPlane.state.jobs.get(createJson.jobId);

  assert.equal(partJson.partNumber, 2);
  assert.equal(renewedJob?.expiresAt, partJson.expiresAt);
  assert.ok(Date.parse(partJson.expiresAt) > Date.parse(nearlyExpiredAt));

  const renewalEvent = controlPlane.state.events.find(
    (event) => event.eventType === "job.multipart_upload.lease_renewed",
  );
  assert.equal(renewalEvent?.message, "Active multipart upload lease renewed.");
  assert.equal(JSON.stringify(renewalEvent?.payload).includes(partJson.uploadUrl), false);
});
