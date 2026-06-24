import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";
import { routeAdminRequest } from "../src/routes/admin";

const {
  createControlPlaneHarness,
  invokePublicRoute,
  parseJsonResponse,
  uploadObject,
} = harness;

test("control plane keeps asset aliases while preserving redacted public storage keys", async () => {
  const controlPlane = createControlPlaneHarness();

  const createResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    "/uploads/presign",
    {
      filename: "asset-compat.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 1024,
      durationSeconds: 12,
      installId: "install-asset-compat",
      appVersion: "1.0.0",
      analysisVersion: "asset-v1",
    },
  );

  assert.equal(createResponse.status, 201);
  const createJson = await parseJsonResponse<{
    jobId: string;
    assetId: string;
    storageKey: string | null;
    sourceObjectKey: string;
    uploadUrl: string;
  }>(createResponse);
  assert.equal(createJson.assetId, createJson.jobId);
  assert.equal(createJson.storageKey, null);

  await uploadObject(
    controlPlane,
    createJson.uploadUrl,
    new TextEncoder().encode("asset compatibility clip"),
  );
  const startResponse = await invokePublicRoute(controlPlane, "POST", "/jobs", {
    jobId: createJson.jobId,
    installId: "install-asset-compat",
    sourceObjectKey: createJson.sourceObjectKey,
  });
  assert.equal(startResponse.status, 200);
  assert.equal(controlPlane.state.queueMessages[0]?.assetId, createJson.assetId);
  assert.equal(controlPlane.state.queueMessages[0]?.storageKey, createJson.sourceObjectKey);

  await controlPlane.drainQueue();
  assert.equal(controlPlane.state.inferenceDispatches[0]?.body.assetId, createJson.assetId);
  assert.equal(controlPlane.state.inferenceDispatches[0]?.body.storageKey, createJson.sourceObjectKey);

  const pollResponse = await invokePublicRoute(controlPlane, "GET", `/jobs/${createJson.jobId}`);
  const pollJson = await parseJsonResponse<{ assetId: string; storageKey: string | null }>(pollResponse);
  assert.equal(pollJson.assetId, createJson.assetId);
  assert.equal(pollJson.storageKey, null);
});

test("canonical asset upload routes bridge to the Worker R2 job flow", async () => {
  const controlPlane = createControlPlaneHarness();

  const initResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    "/uploads/init",
    {
      filename: "asset-canonical.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 2048,
      durationSeconds: 18,
      installId: "install-asset-canonical",
      appVersion: "1.0.0",
      analysisVersion: "asset-v1",
      uploadPreference: "single",
    },
  );

  assert.equal(initResponse.status, 201);
  const initJson = await parseJsonResponse<{
    assetId: string;
    storageKey: string;
    status: string;
    uploadMode: string;
    uploadUrl: string;
    uploadMethod: string;
    uploadHeaders: Record<string, string>;
  }>(initResponse);
  assert.equal(initJson.status, "initialized");
  assert.equal(initJson.uploadMode, "single");
  assert.equal(initJson.uploadMethod, "PUT");
  assert.equal(initJson.storageKey.length > 0, true);
  assert.equal(initJson.assetId.length > 0, true);

  await uploadObject(
    controlPlane,
    initJson.uploadUrl,
    new TextEncoder().encode("canonical asset upload clip"),
  );

  const completeResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    `/uploads/${initJson.assetId}/complete`,
    {
      installId: "install-asset-canonical",
    },
  );
  assert.equal(completeResponse.status, 200);
  const completeJson = await parseJsonResponse<{
    assetId: string;
    storageKey: string | null;
    sourceObjectKey: string;
    status: string;
    integrityStatus: string;
  }>(completeResponse);
  assert.equal(completeJson.assetId, initJson.assetId);
  assert.equal(completeJson.storageKey, null);
  assert.equal(completeJson.sourceObjectKey, initJson.storageKey);
  assert.equal(completeJson.status, "ready");
  assert.equal(completeJson.integrityStatus, "unavailable");

  const duplicateCompleteResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    `/uploads/${initJson.assetId}/complete`,
    {
      installId: "install-asset-canonical",
    },
  );
  assert.equal(duplicateCompleteResponse.status, 200);
  const duplicateCompleteJson = await parseJsonResponse<{ assetId: string; status: string }>(duplicateCompleteResponse);
  assert.equal(duplicateCompleteJson.assetId, initJson.assetId);
  assert.equal(duplicateCompleteJson.status, "ready");

  const statusResponse = await invokePublicRoute(
    controlPlane,
    "GET",
    `/assets/${initJson.assetId}?installId=install-asset-canonical`,
  );
  assert.equal(statusResponse.status, 200);
  const statusJson = await parseJsonResponse<{
    assetId: string;
    storageKey: string | null;
    sourceObjectKey: string;
    status: string;
    uploadedBytes: number;
  }>(statusResponse);
  assert.equal(statusJson.assetId, initJson.assetId);
  assert.equal(statusJson.storageKey, null);
  assert.equal(statusJson.sourceObjectKey, initJson.storageKey);
  assert.equal(statusJson.status, "ready");
  assert.equal(statusJson.uploadedBytes, 2048);

  const analysisResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    `/assets/${initJson.assetId}/analysis-jobs`,
    {
      installId: "install-asset-canonical",
      appVersion: "1.0.0",
      analysisVersion: "asset-v1",
    },
  );
  assert.equal(analysisResponse.status, 200);
  const analysisJson = await parseJsonResponse<{
    jobId: string;
    assetId: string;
    storageKey: string;
    sourceObjectKey: string;
    status: string;
  }>(analysisResponse);
  assert.equal(analysisJson.jobId, initJson.assetId);
  assert.equal(analysisJson.assetId, initJson.assetId);
  assert.equal(analysisJson.storageKey, initJson.storageKey);
  assert.equal(analysisJson.sourceObjectKey, initJson.storageKey);
  assert.equal(analysisJson.status, "queued");
  assert.equal(controlPlane.state.queueMessages[0]?.assetId, initJson.assetId);
  assert.equal(controlPlane.state.queueMessages[0]?.storageKey, initJson.storageKey);

  const lateCompleteResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    `/uploads/${initJson.assetId}/complete`,
    {
      installId: "install-asset-canonical",
    },
  );
  assert.equal(lateCompleteResponse.status, 200);
  const lateCompleteJson = await parseJsonResponse<{ assetId: string; status: string }>(lateCompleteResponse);
  assert.equal(lateCompleteJson.assetId, initJson.assetId);
  assert.equal(lateCompleteJson.status, "ready");

  const legacyPollResponse = await invokePublicRoute(controlPlane, "GET", `/jobs/${initJson.assetId}`);
  const legacyPollJson = await parseJsonResponse<{ jobId: string; status: string }>(legacyPollResponse);
  assert.equal(legacyPollJson.jobId, initJson.assetId);
  assert.equal(legacyPollJson.status, "queued");
});

test("admin clip review echoes and stores canonical review feedback tags", async () => {
  const controlPlane = createControlPlaneHarness();
  const capturedBinds: unknown[][] = [];
  const db = {
    prepare() {
      return {
        bind(...values: unknown[]) {
          capturedBinds.push(values);
          return {
            async run() {
              return { success: true } as const;
            },
            async first() {
              return null;
            },
            async all() {
              return { results: [] };
            },
          };
        },
      };
    },
  } as typeof controlPlane.env.DB;

  const request = new Request("http://control-plane.local/v1/admin/clips/clip_123/review?jobId=job_123&clipIndex=2", {
    method: "PATCH",
    headers: {
      "content-type": "application/json",
      "x-hoops-admin-token": controlPlane.env.ADMIN_API_TOKEN,
    },
    body: JSON.stringify({
      reviewState: "reviewed",
      reviewerNotes: "calibration sample",
      reviewFeedbackTags: ["duplicate", "wrong_team", "bad_window", "wrong_label", "low_quality", "ignored"],
    }),
  });

  const response = await routeAdminRequest(
    request,
    { ...controlPlane.env, DB: db },
    "request-admin-tags",
  );
  assert.equal(response?.status, 200);
  const payload = await parseJsonResponse<{ reviewFeedbackTags: string[] }>(response!);
  assert.deepEqual(payload.reviewFeedbackTags, [
    "duplicate",
    "wrong_team",
    "bad_window",
    "wrong_label",
    "low_quality",
  ]);
  assert.equal(
    capturedBinds.some((values) => values.includes(JSON.stringify(payload.reviewFeedbackTags))),
    true,
  );
});
