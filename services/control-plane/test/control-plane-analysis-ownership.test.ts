import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const {
  createControlPlaneHarness,
  invokePublicRoute,
  parseJsonResponse,
  uploadObject,
} = harness;

test("analysis job reads and deletes require the owning install ID", async () => {
  const controlPlane = createControlPlaneHarness();
  const ownerInstallId = "install-owner-001";
  const createResponse = await invokePublicRoute(
    controlPlane,
    "POST",
    "/uploads/presign",
    {
      filename: "ownership-check.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 1024,
      durationSeconds: 12,
      installId: ownerInstallId,
      appVersion: "1.0.0",
      analysisVersion: "ownership-v1",
    },
  );
  assert.equal(createResponse.status, 201);
  const createJson = await parseJsonResponse<{ jobId: string; uploadUrl: string }>(createResponse);
  await uploadObject(
    controlPlane,
    createJson.uploadUrl,
    new TextEncoder().encode("ownership check clip"),
  );

  const missingOwnerRead = await invokePublicRoute(
    controlPlane,
    "GET",
    `/jobs/${createJson.jobId}`,
  );
  assert.equal(missingOwnerRead.status, 400);
  assert.equal(
    (await parseJsonResponse<{ errorCode: string }>(missingOwnerRead)).errorCode,
    "invalid_request",
  );

  const wrongOwnerRead = await invokePublicRoute(
    controlPlane,
    "GET",
    `/jobs/${createJson.jobId}?installId=install-other-002`,
  );
  assert.equal(wrongOwnerRead.status, 403);
  assert.equal(
    (await parseJsonResponse<{ errorCode: string }>(wrongOwnerRead)).errorCode,
    "install_mismatch",
  );

  const ownerRead = await invokePublicRoute(
    controlPlane,
    "GET",
    `/jobs/${createJson.jobId}?installId=${ownerInstallId}`,
  );
  assert.equal(ownerRead.status, 200);

  const missingOwnerDelete = await invokePublicRoute(
    controlPlane,
    "DELETE",
    `/jobs/${createJson.jobId}`,
  );
  assert.equal(missingOwnerDelete.status, 400);

  const wrongOwnerDelete = await invokePublicRoute(
    controlPlane,
    "DELETE",
    `/jobs/${createJson.jobId}?installId=install-other-002`,
  );
  assert.equal(wrongOwnerDelete.status, 403);

  const stillOwned = await invokePublicRoute(
    controlPlane,
    "GET",
    `/jobs/${createJson.jobId}?installId=${ownerInstallId}`,
  );
  assert.equal(stillOwned.status, 200);

  const ownerDelete = await invokePublicRoute(
    controlPlane,
    "DELETE",
    `/jobs/${createJson.jobId}?installId=${ownerInstallId}`,
  );
  assert.equal(ownerDelete.status, 204);
  assert.equal(controlPlane.state.jobs.get(createJson.jobId)?.status, "cancelled");
  assert.equal(controlPlane.state.uploads.size, 0);

  const deletedRead = await invokePublicRoute(
    controlPlane,
    "GET",
    `/jobs/${createJson.jobId}?installId=${ownerInstallId}`,
  );
  assert.equal(deletedRead.status, 200);
  assert.equal(
    (await parseJsonResponse<{ status: string }>(deletedRead)).status,
    "cancelled",
  );
});
