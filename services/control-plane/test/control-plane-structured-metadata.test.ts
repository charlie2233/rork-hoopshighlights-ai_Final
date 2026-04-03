import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const {
  buildSuccessCallbackPayload,
  createControlPlaneHarness,
  invokeInternalRoute,
  invokePublicRoute,
  parseJsonResponse,
  uploadObject
} = harness;

test("structured teacher metadata stays additive in the callback contract", async () => {
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
      analysisVersion: "phase1b"
    },
    { "x-trace-id": "trace-structured-metadata" }
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
    },
    { "x-trace-id": "trace-structured-metadata" }
  );
  assert.equal(startResponse.status, 200);

  const callbackPayload = buildSuccessCallbackPayload({
    jobId: createJson.jobId,
    requestId: "trace-structured-metadata",
    modelVersion: "teacher-audit-v1",
    resultConfidence: 0.84
  }) as any;

  if (callbackPayload.results?.clips?.[0]) {
    const clip = callbackPayload.results.clips[0] as Record<string, unknown>;
    clip.structuredSignals = {
      ballNearRim: 0.82,
      ballThroughHoopLikelihood: 0.11,
      possessionChangeLikelihood: 0.06,
      transitionLikelihood: 0.04
    };
    clip.teacherSuggestion = {
      eventFamily: "shot_attempt",
      outcome: "missed",
      shotSubtype: "jumper",
      confidence: 0.93,
      evidence: ["ball near rim", "no make"],
      promptSetVersion: "qwen-basketball-teacher-v1"
    };
    clip.runtimeFusionTemporalShadow = {
      modelVersion: "temporal-event-detector-tridet-open-set-v1",
      label: "Shot Attempt",
      canonicalLabel: "shot_attempt",
      eventFamily: "shot_attempt",
      outcome: "uncertain",
      shotSubtype: null,
      isUncertain: true,
      temporal_event_detector_shot_specialist_used: true,
      temporal_event_detector_shot_specialist_abstained: true,
      metadata: {
        temporal_event_detector_proposal_accepted: false,
        temporal_event_detector_proposal_acceptance_score: 0.41,
        temporal_event_detector_proposal_rejector_label: "dead_ball",
        temporal_event_detector_proposal_ranker_label: "secondary",
        temporal_event_detector_proposal_acceptor_label: "reject"
      }
    };
  }

  const callbackResponse = await invokeInternalRoute(
    harness,
    "POST",
    "/internal/inference/callback",
    callbackPayload,
    { "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET, "x-trace-id": "trace-structured-metadata" },
    "trace-structured-metadata"
  );
  assert.equal(callbackResponse.status, 200);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "completed");

  const jobResponse = await invokePublicRoute(
    harness,
    "GET",
    `/jobs/${createJson.jobId}`,
    undefined,
    { "x-trace-id": "trace-structured-metadata-poll" }
  );
  const jobJson = await parseJsonResponse<{
    requestId: string;
    uploadTraceId?: string | null;
    inferenceAttemptId?: string | null;
    modelVersion?: string | null;
    failureReason?: string | null;
    results?: {
      clipCount: number;
      clips: Array<{ label: string; rawTopLabels?: Array<{ rawLabel: string }> | null }>;
    } | null;
  }>(jobResponse);

  assert.equal(jobJson.requestId.length > 0, true);
  assert.equal(typeof jobJson.uploadTraceId, "string");
  assert.equal((jobJson.uploadTraceId ?? "").length > 0, true);
  assert.equal(jobJson.inferenceAttemptId, null);
  assert.equal(jobJson.modelVersion, "teacher-audit-v1");
  assert.equal(jobJson.failureReason, null);
  assert.equal(jobJson.results?.clipCount, 1);
  assert.equal(jobJson.results?.clips[0]?.label, "made_shot");
  assert.equal(
    (jobJson.results?.clips?.[0] as Record<string, unknown> | undefined)?.runtimeFusionTemporalShadow !== undefined,
    true
  );
  assert.equal(
    ((jobJson.results?.clips?.[0] as Record<string, unknown> | undefined)?.runtimeFusionTemporalShadow as Record<string, unknown>)
      ?.temporal_event_detector_shot_specialist_abstained,
    true
  );
  assert.equal(
    ((jobJson.results?.clips?.[0] as Record<string, unknown> | undefined)?.runtimeFusionTemporalShadow as Record<string, unknown>)
      ?.label,
    "Shot Attempt"
  );
});
