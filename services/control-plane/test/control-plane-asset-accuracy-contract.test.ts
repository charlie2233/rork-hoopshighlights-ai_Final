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

test("canonical asset routes complete, scan, and start analysis without legacy fallback", async () => {
  const controlPlane = createControlPlaneHarness();
  const installId = "install-asset-canonical";

  const initResponse = await invokePublicRoute(controlPlane, "POST", "/uploads/init", {
    filename: "asset-canonical.mp4",
    contentType: "video/mp4",
    fileSizeBytes: 2048,
    durationSeconds: 18,
    installId,
    appVersion: "1.0.0",
    analysisVersion: "asset-v1",
    uploadPreference: "single",
  });

  assert.equal(initResponse.status, 201);
  const initJson = await parseJsonResponse<{
    assetId: string;
    storageKey: string;
    status: string;
    uploadMode: string;
    uploadUrl: string;
    uploadMethod: string;
  }>(initResponse);
  assert.equal(initJson.status, "initialized");
  assert.equal(initJson.uploadMode, "single");
  assert.equal(initJson.uploadMethod, "PUT");
  assert.equal(initJson.storageKey.length > 0, true);

  await uploadObject(
    controlPlane,
    initJson.uploadUrl,
    new TextEncoder().encode("canonical asset upload clip"),
  );

  const completeResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    `/uploads/${initJson.assetId}/complete`,
    { installId },
  );
  assert.equal(completeResponse.status, 200);
  const completeJson = await parseJsonResponse<{
    assetId: string;
    storageKey: string;
    status: string;
  }>(completeResponse);
  assert.equal(completeJson.assetId, initJson.assetId);
  assert.equal(completeJson.storageKey, initJson.storageKey);
  assert.equal(completeJson.status, "ready");

  const duplicateCompleteResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    `/uploads/${initJson.assetId}/complete`,
    { installId },
  );
  assert.equal(duplicateCompleteResponse.status, 200);

  const missingOwnerResponse = await invokePublicRoute(
    controlPlane,
    "GET",
    `/assets/${initJson.assetId}`,
  );
  assert.equal(missingOwnerResponse.status, 400);
  const wrongOwnerResponse = await invokePublicRoute(
    controlPlane,
    "GET",
    `/assets/${initJson.assetId}?installId=another-install`,
  );
  assert.equal(wrongOwnerResponse.status, 403);

  const statusResponse = await invokePublicRoute(
    controlPlane,
    "GET",
    `/assets/${initJson.assetId}?installId=${installId}`,
  );
  assert.equal(statusResponse.status, 200);
  const statusJson = await parseJsonResponse<{
    assetId: string;
    storageKey: string;
    status: string;
    uploadedBytes: number;
  }>(statusResponse);
  assert.equal(statusJson.assetId, initJson.assetId);
  assert.equal(statusJson.storageKey, initJson.storageKey);
  assert.equal(statusJson.status, "ready");
  assert.equal(statusJson.uploadedBytes, 2048);

  const teamScanResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    `/assets/${initJson.assetId}/team-scan`,
    {
      installId,
      detectedTeams: [
        {
          teamId: "team-white",
          label: "White jerseys",
          colorLabel: "white",
          confidence: 0.94,
          source: "test",
        },
      ],
    },
  );
  assert.equal(teamScanResponse.status, 200);
  const teamScanJson = await parseJsonResponse<{ status: string; detectedTeams: unknown[] }>(teamScanResponse);
  assert.equal(teamScanJson.status, "scanned");
  assert.equal(teamScanJson.detectedTeams.length, 1);

  const analysisResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    `/assets/${initJson.assetId}/analysis-jobs`,
    {
      installId,
      appVersion: "1.0.0",
      analysisVersion: "asset-v1",
    },
  );
  assert.equal(analysisResponse.status, 200);
  const analysisJson = await parseJsonResponse<{
    jobId: string;
    assetId: string;
    storageKey: string;
    status: string;
  }>(analysisResponse);
  assert.equal(analysisJson.jobId, initJson.assetId);
  assert.equal(analysisJson.assetId, initJson.assetId);
  assert.equal(analysisJson.storageKey, initJson.storageKey);
  assert.equal(analysisJson.status, "queued");
  assert.equal(controlPlane.state.queueMessages[0]?.assetId, initJson.assetId);
  assert.equal(controlPlane.state.queueMessages[0]?.storageKey, initJson.storageKey);

  const lateCompleteResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    `/uploads/${initJson.assetId}/complete`,
    { installId },
  );
  assert.equal(lateCompleteResponse.status, 200);
  const lateCompleteJson = await parseJsonResponse<{ status: string }>(lateCompleteResponse);
  assert.equal(lateCompleteJson.status, "ready");

  const legacyPollResponse = await invokePublicRoute(
    controlPlane,
    "GET",
    `/jobs/${initJson.assetId}?installId=${installId}`,
  );
  const legacyPollJson = await parseJsonResponse<{ storageKey: string | null; status: string }>(legacyPollResponse);
  assert.equal(legacyPollJson.storageKey, null);
  assert.equal(legacyPollJson.status, "queued");
});

test("canonical multipart init returns every signed part target in one response", async () => {
  const originalFetch = globalThis.fetch;
  let multipartStorageKey = "";
  let multipartUploads: Map<string, Uint8Array> | null = null;
  globalThis.fetch = async (input, init) => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    if (request.method === "POST" && url.searchParams.has("uploads")) {
      return new Response("<InitiateMultipartUploadResult><UploadId>upload-canonical-123</UploadId></InitiateMultipartUploadResult>", {
        status: 200,
        headers: { "content-type": "application/xml" },
      });
    }
    if (request.method === "POST" && url.searchParams.get("uploadId") === "upload-canonical-123") {
      multipartUploads?.set(multipartStorageKey, new TextEncoder().encode("assembled multipart upload"));
      return new Response("<CompleteMultipartUploadResult><ETag>assembled-etag</ETag></CompleteMultipartUploadResult>", {
        status: 200,
        headers: { "content-type": "application/xml" },
      });
    }
    throw new Error(`Unexpected fetch in multipart init test: ${request.method} ${url.pathname}`);
  };

  try {
    const controlPlane = createControlPlaneHarness({
      R2_ACCOUNT_ID: "account-test",
      R2_ACCESS_KEY_ID: "access-test",
      R2_SECRET_ACCESS_KEY: "secret-test",
    });
    const initResponse = await invokePublicRoute(controlPlane, "POST", "/uploads/init", {
      filename: "asset-multipart.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 128 * 1024 * 1024,
      durationSeconds: 300,
      installId: "install-asset-multipart",
      appVersion: "1.0.0",
      analysisVersion: "asset-v1",
      uploadPreference: "multipart",
      partSizeBytes: 16 * 1024 * 1024,
    });

    assert.equal(initResponse.status, 201);
    const initJson = await parseJsonResponse<{
      uploadMode: string;
      uploadUrl: string | null;
      assetId: string;
      storageKey: string;
      multipart: {
        uploadId: string;
        partSizeBytes: number;
        partCount: number;
        parts: Array<{ partNumber: number; uploadMethod: string; uploadUrl: string }>;
      };
    }>(initResponse);
    assert.equal(initJson.uploadMode, "multipart");
    assert.equal(initJson.uploadUrl, null);
    assert.equal(initJson.multipart.uploadId, "upload-canonical-123");
    assert.equal(initJson.multipart.partSizeBytes, 16 * 1024 * 1024);
    assert.equal(initJson.multipart.partCount, 8);
    assert.deepEqual(initJson.multipart.parts.map((part) => part.partNumber), [1, 2, 3, 4, 5, 6, 7, 8]);
    assert.equal(initJson.multipart.parts.every((part) => part.uploadMethod === "PUT"), true);
    assert.equal(initJson.multipart.parts.every((part) => part.uploadUrl.includes("uploadId=upload-canonical-123")), true);

    multipartStorageKey = initJson.storageKey;
    multipartUploads = controlPlane.state.uploads;
    const completeResponse = await invokePublicRoute(
      controlPlane,
      "POST",
      `/uploads/${initJson.assetId}/complete`,
      {
        installId: "install-asset-multipart",
        uploadId: initJson.multipart.uploadId,
        parts: initJson.multipart.parts.map((part) => ({
          partNumber: part.partNumber,
          etag: `etag-${part.partNumber}`,
        })),
      },
    );
    assert.equal(completeResponse.status, 200);
    const completeJson = await parseJsonResponse<{ storageKey: string; status: string }>(completeResponse);
    assert.equal(completeJson.storageKey, initJson.storageKey);
    assert.equal(completeJson.status, "ready");
  } finally {
    globalThis.fetch = originalFetch;
  }
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
