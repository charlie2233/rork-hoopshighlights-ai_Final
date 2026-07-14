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

  const pollResponse = await invokePublicRoute(
    controlPlane,
    "GET",
    `/jobs/${createJson.jobId}?installId=install-asset-compat`,
  );
  const pollJson = await parseJsonResponse<{ assetId: string; storageKey: string | null }>(pollResponse);
  assert.equal(pollJson.assetId, createJson.assetId);
  assert.equal(pollJson.storageKey, null);
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
