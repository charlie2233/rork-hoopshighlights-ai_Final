import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const { createControlPlaneHarness, invokePublicRoute, parseJsonResponse, uploadObject } = harness;

test("queue callback failures write a dead-letter record and fail the job", async () => {
  const harness = createControlPlaneHarness({
    CONTROL_PLANE_BASE_URL: "http://127.0.0.1:1"
  });

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
    }
  );
  const createJson = await parseJsonResponse<{ jobId: string; sourceObjectKey: string; uploadUrl: string }>(createResponse);

  await uploadObject(harness, createJson.uploadUrl, new TextEncoder().encode("sample basketball clip"));

  const startResponse = await invokePublicRoute(harness, "POST", "/jobs", {
    jobId: createJson.jobId,
    installId: "install-local-001",
    sourceObjectKey: createJson.sourceObjectKey
  });
  assert.equal(startResponse.status, 200);

  const drained = await harness.drainQueue();
  assert.equal(drained, 1);
  assert.equal(harness.state.inferenceDispatches[0]?.jobStatus, "queued");
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "failed");
  const failureReason = harness.state.jobs.get(createJson.jobId)?.failureReason ?? "";
  assert.match(failureReason, /External inference dispatch failed with status 502/);
  assert.doesNotMatch(failureReason, /callback_unreachable/);
  assert.equal(harness.state.deadLetterMessages.length, 1);
  assert.equal(harness.state.deadLetterMessages[0]?.jobId, createJson.jobId);
  assert.equal(harness.state.deadLetterMessages[0]?.failureReason, harness.state.jobs.get(createJson.jobId)?.failureReason);

  const persistedFailureText = JSON.stringify({
    job: harness.state.jobs.get(createJson.jobId),
    events: harness.state.events.filter((event) => event.jobId === createJson.jobId),
    deadLetter: harness.state.deadLetterMessages[0]
  });
  assert.doesNotMatch(persistedFailureText, /callback_unreachable/);
});
