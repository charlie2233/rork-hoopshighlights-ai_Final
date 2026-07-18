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

test("an expired multipart upload can renew its lease for the next chunk", async () => {
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
  const createJson = await parseJsonResponse<{ jobId: string; uploadUrl: string }>(createResponse);
  assert.equal(new URL(createJson.uploadUrl).searchParams.get("X-Amz-Expires"), "3600");

  const job = controlPlane.state.jobs.get(createJson.jobId);
  assert.ok(job);
  const expiredAt = new Date(Date.now() - 5_000).toISOString();
  controlPlane.state.jobs.set(createJson.jobId, {
    ...job,
    expiresAt: expiredAt,
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
  assert.equal(new URL(partJson.uploadUrl).searchParams.get("X-Amz-Expires"), "3600");
  assert.equal(renewedJob?.expiresAt, partJson.expiresAt);
  assert.ok(Date.parse(partJson.expiresAt) > Date.parse(expiredAt));

  const renewalEvent = controlPlane.state.events.find(
    (event) => event.eventType === "job.multipart_upload.lease_renewed",
  );
  assert.equal(renewalEvent?.message, "Active multipart upload lease renewed.");
  assert.equal(JSON.stringify(renewalEvent?.payload).includes(partJson.uploadUrl), false);
});

test("multipart renewal is rejected after the bounded post-expiry grace", async () => {
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
      filename: "abandoned-full-game.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 380 * MEBIBYTE,
      durationSeconds: 1_800,
      installId: "install-abandoned-upload",
      appVersion: "1.0.0",
      analysisVersion: "multipart-bounded-renewal",
    },
  );
  assert.equal(createResponse.status, 201);
  const createJson = await parseJsonResponse<{ jobId: string }>(createResponse);

  const job = controlPlane.state.jobs.get(createJson.jobId);
  assert.ok(job);
  controlPlane.state.jobs.set(createJson.jobId, {
    ...job,
    expiresAt: new Date(Date.now() - (3_600_000 + 5_000)).toISOString(),
  });

  const partResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    "/uploads/multipart/part",
    {
      jobId: createJson.jobId,
      installId: "install-abandoned-upload",
      uploadId: "abandoned-multipart-upload",
      partNumber: 2,
    },
  );
  assert.equal(partResponse.status, 410);
  const partJson = await parseJsonResponse<{ errorCode: string }>(partResponse);
  assert.equal(partJson.errorCode, "upload_expired");
});

test("an expired single upload remains closed when its object is missing", async () => {
  const controlPlane = createControlPlaneHarness();
  const createResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    "/uploads/presign",
    {
      filename: "single-clip.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 4 * MEBIBYTE,
      durationSeconds: 30,
      installId: "install-expired-single",
      appVersion: "1.0.0",
      analysisVersion: "single-expiry-contract",
    },
  );
  assert.equal(createResponse.status, 201);
  const createJson = await parseJsonResponse<{ jobId: string; sourceObjectKey: string }>(createResponse);

  const job = controlPlane.state.jobs.get(createJson.jobId);
  assert.ok(job);
  controlPlane.state.jobs.set(createJson.jobId, {
    ...job,
    expiresAt: new Date(Date.now() - 5_000).toISOString(),
  });

  const finalizeResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    "/jobs",
    {
      jobId: createJson.jobId,
      installId: "install-expired-single",
      sourceObjectKey: createJson.sourceObjectKey,
    },
  );
  assert.equal(finalizeResponse.status, 410);
  const finalizeJson = await parseJsonResponse<{ errorCode: string }>(finalizeResponse);
  assert.equal(finalizeJson.errorCode, "upload_expired");
});
