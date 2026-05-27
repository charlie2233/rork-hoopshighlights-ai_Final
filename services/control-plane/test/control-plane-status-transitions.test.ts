import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const {
  createControlPlaneHarness,
  invokeInternalRoute,
  invokePublicRoute,
  parseJsonResponse,
  uploadObject
} = harness;

test("control plane happy path advances upload_pending -> uploaded -> queued -> processing -> completed", async () => {
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
      analysisVersion: "phase1a"
    },
    { "x-trace-id": "trace-happy-path" }
  );
  assert.equal(createResponse.status, 201);
  const createJson = await parseJsonResponse<{
    jobId: string;
    sourceObjectKey: string;
    uploadUrl: string;
    status: string;
    uploadTraceId: string | null;
  }>(createResponse);

  await uploadObject(harness, createJson.uploadUrl, new TextEncoder().encode("sample basketball clip"));
  assert.equal(createJson.sourceObjectKey.length > 0, true);
  assert.equal(createJson.status, "upload_pending");
  assert.equal(typeof createJson.uploadTraceId, "string");
  const uploadPendingEvent = harness.state.events.find((event) => event.eventType === "job.upload_pending");
  assert.equal(JSON.stringify(uploadPendingEvent?.payload ?? {}).includes("uploadUrl"), false);

  const finalizeResponse = await invokePublicRoute(
    harness,
    "POST",
    "/jobs",
    {
      jobId: createJson.jobId,
      installId: "install-local-001",
      sourceObjectKey: createJson.sourceObjectKey
    },
    { "x-trace-id": "trace-happy-path" }
  );
  assert.equal(finalizeResponse.status, 200);
  const finalizeJson = await parseJsonResponse<{ status: string }>(finalizeResponse);
  assert.equal(finalizeJson.status, "queued");
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "queued");
  assert.equal(harness.state.queueMessages.length, 1);
  assert.equal("callbackUrl" in harness.state.queueMessages[0], false);
  assert.equal("installId" in harness.state.queueMessages[0], false);
  assert.equal("analysisVersion" in harness.state.queueMessages[0], false);
  assert.deepEqual(Object.keys(harness.state.queueMessages[0] ?? {}).sort(), [
    "jobId",
    "kind",
    "modelVersion",
    "requestId",
    "resultObjectKey",
    "schemaVersion",
    "sourceObjectKey",
    "teamSelection",
    "traceId",
    "uploadTraceId"
  ]);

  const processedMessages = await harness.drainQueue();
  assert.equal(processedMessages, 1);
  assert.equal(harness.state.inferenceDispatches.length, 1);
  assert.equal(harness.state.inferenceDispatches[0]?.jobId, createJson.jobId);
  assert.equal(harness.state.inferenceDispatches[0]?.requestId.length > 0, true);
  assert.equal(harness.state.inferenceDispatches[0]?.jobStatus, "queued");
  assert.equal(harness.state.inferenceDispatches[0]?.uploadTraceId, createJson.uploadTraceId);
  assert.equal(typeof harness.state.inferenceDispatches[0]?.inferenceAttemptId, "string");
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "completed");
  assert.equal(harness.state.jobs.get(createJson.jobId)?.attemptCount, 1);
  assert.equal(typeof harness.state.jobs.get(createJson.jobId)?.acceptedAt, "string");
  assert.equal(typeof harness.state.jobs.get(createJson.jobId)?.processingStartedAt, "string");
  assert.equal(typeof harness.state.jobs.get(createJson.jobId)?.uploadTraceId, "string");
  assert.equal(typeof harness.state.jobs.get(createJson.jobId)?.inferenceAttemptId, "string");

  const finalResponse = await invokePublicRoute(harness, "GET", `/jobs/${createJson.jobId}`);
  assert.equal(finalResponse.status, 200);
  const finalJson = await parseJsonResponse<{
    status: string;
    modelVersion: string | null;
    failureReason: string | null;
    uploadTraceId: string | null;
    inferenceAttemptId: string | null;
    attemptCount: number | null;
    acceptedAt: string | null;
    processingStartedAt: string | null;
    results: { clipCount: number; resultConfidence: number } | null;
  }>(finalResponse);

  assert.equal(finalJson.status, "completed");
  assert.equal(finalJson.modelVersion, "videomae:MCG-NJU/videomae-base-finetuned-kinetics");
  assert.equal(finalJson.failureReason, null);
  assert.equal(typeof finalJson.uploadTraceId, "string");
  assert.equal(typeof finalJson.inferenceAttemptId, "string");
  assert.equal(finalJson.attemptCount, 1);
  assert.equal(typeof finalJson.acceptedAt, "string");
  assert.equal(typeof finalJson.processingStartedAt, "string");
  assert.equal(finalJson.results?.clipCount, 1);
  assert.equal(typeof finalJson.results?.resultConfidence, "number");
});

test("control plane preserves selected team intent through queued inference", async () => {
  const harness = createControlPlaneHarness();
  const teamSelection = {
    mode: "team",
    teamId: "team_dark",
    label: "Dark jerseys",
    colorLabel: "black",
    confidenceThreshold: 0.85,
    includeUncertain: true
  };

  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "selected-team-game.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-local-team",
      appVersion: "1.0.0",
      analysisVersion: "phase-team"
    },
    { "x-trace-id": "trace-selected-team" }
  );
  assert.equal(createResponse.status, 201);
  const createJson = await parseJsonResponse<{
    jobId: string;
    sourceObjectKey: string;
    uploadUrl: string;
  }>(createResponse);

  await uploadObject(harness, createJson.uploadUrl, new TextEncoder().encode("selected team basketball clip"));

  const scanResponse = await invokePublicRoute(
    harness,
    "POST",
    `/jobs/${createJson.jobId}/team-scan`,
    {
      installId: "install-local-team",
      detectedTeams: [
        {
          teamId: "team_dark",
          label: "Dark jerseys",
          colorLabel: "black",
          primaryColorHex: "#111111",
          confidence: 0.93,
          source: "quick_scan"
        },
        {
          teamId: "team_light",
          label: "Light jerseys",
          colorLabel: "white",
          primaryColorHex: "#f4f4f4",
          confidence: 0.91,
          source: "quick_scan"
        }
      ]
    },
    { "x-trace-id": "trace-selected-team" }
  );
  assert.equal(scanResponse.status, 200);
  const scanJson = await parseJsonResponse<{ status: string; detectedTeams: Array<{ teamId: string }> }>(scanResponse);
  assert.equal(scanJson.status, "scanned");
  assert.deepEqual(scanJson.detectedTeams.map((team) => team.teamId), ["team_dark", "team_light"]);

  const startResponse = await invokePublicRoute(
    harness,
    "POST",
    `/jobs/${createJson.jobId}/start`,
    {
      installId: "install-local-team",
      teamSelection
    },
    { "x-trace-id": "trace-selected-team" }
  );
  assert.equal(startResponse.status, 200);

  const storedJob = harness.state.jobs.get(createJson.jobId);
  assert.deepEqual(storedJob?.teamSelection, teamSelection);
  assert.equal(storedJob?.teamScanStatus, "scanned");
  assert.deepEqual(storedJob?.detectedTeams?.map((team) => team.teamId), ["team_dark", "team_light"]);
  assert.equal(harness.state.queueMessages.length, 1);
  assert.deepEqual(harness.state.queueMessages[0]?.teamSelection, teamSelection);

  const processedMessages = await harness.drainQueue();
  assert.equal(processedMessages, 1);
  assert.deepEqual(harness.state.inferenceDispatches[0]?.body.teamSelection, teamSelection);

  const finalResponse = await invokePublicRoute(harness, "GET", `/jobs/${createJson.jobId}`);
  assert.equal(finalResponse.status, 200);
  const finalJson = await parseJsonResponse<{
    status: string;
    results: { teamSelection?: typeof teamSelection | null } | null;
  }>(finalResponse);
  assert.equal(finalJson.status, "completed");
  assert.deepEqual(finalJson.results?.teamSelection, teamSelection);
});

test("control plane proxies team scan to inference service before selected team start", async () => {
  const harness = createControlPlaneHarness({ APP_ENV: "staging" });
  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "worker-team-scan.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-worker-team",
      appVersion: "1.0.0",
      analysisVersion: "phase-team"
    },
    { "x-trace-id": "trace-worker-team-scan" }
  );
  const createJson = await parseJsonResponse<{ jobId: string; uploadUrl: string }>(createResponse);
  await uploadObject(harness, createJson.uploadUrl, new TextEncoder().encode("worker team scan basketball clip"));

  const providerRequests: Array<{ url: string; headers: Record<string, string>; body: Record<string, unknown> }> = [];
  const originalFetch = globalThis.fetch.bind(globalThis);
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    if (url.origin === harness.env.INFERENCE_BASE_URL && url.pathname === "/v1/team-scan") {
      const body = (await request.json()) as Record<string, unknown>;
      providerRequests.push({
        url: url.toString(),
        headers: Object.fromEntries(request.headers.entries()),
        body
      });
      assert.equal(body.jobId, createJson.jobId);
      assert.equal(body.installId, "install-worker-team");
      assert.equal(body.filename, "worker-team-scan.mp4");
      assert.equal(body.durationSeconds, 24);
      assert.equal(typeof body.sourceUrl, "string");
      assert.equal(String(body.sourceUrl).includes("/uploads/"), true);
      assert.equal(request.headers.get("x-hoops-inference-secret"), harness.env.INFERENCE_SHARED_SECRET);
      return Response.json({
        jobId: createJson.jobId,
        status: "scanned",
        detectedTeams: [
          {
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            primaryColorHex: "#111111",
            confidence: 0.93,
            source: "quick_scan"
          }
        ]
      });
    }
    return originalFetch(input, init);
  };

  try {
    const scanResponse = await invokePublicRoute(harness, "POST", `/jobs/${createJson.jobId}/team-scan`, {
      installId: "install-worker-team"
    });
    assert.equal(scanResponse.status, 200);
    const scanJson = await parseJsonResponse<{ status: string; detectedTeams: Array<{ teamId: string }> }>(scanResponse);
    assert.equal(scanJson.status, "scanned");
    assert.deepEqual(scanJson.detectedTeams.map((team) => team.teamId), ["team_dark"]);
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(providerRequests.length, 1);
  const startResponse = await invokePublicRoute(harness, "POST", `/jobs/${createJson.jobId}/start`, {
    installId: "install-worker-team",
    teamSelection: {
      mode: "team",
      teamId: "team_dark",
      label: "Dark jerseys",
      colorLabel: "black",
      includeUncertain: true
    }
  });
  assert.equal(startResponse.status, 200);
  assert.equal(harness.state.queueMessages.length, 1);
  assert.deepEqual(harness.state.queueMessages[0]?.teamSelection?.teamId, "team_dark");
});

test("control plane rejects selected team start until a team scan stores detected teams", async () => {
  const harness = createControlPlaneHarness();
  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "selected-team-no-scan.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-no-scan",
      appVersion: "1.0.0",
      analysisVersion: "phase-team"
    }
  );
  const createJson = await parseJsonResponse<{ jobId: string; uploadUrl: string }>(createResponse);
  await uploadObject(harness, createJson.uploadUrl, new TextEncoder().encode("selected team no scan"));

  const startResponse = await invokePublicRoute(harness, "POST", `/jobs/${createJson.jobId}/start`, {
    installId: "install-no-scan",
    teamSelection: {
      mode: "team",
      teamId: "team_dark",
      label: "Dark jerseys",
      colorLabel: "black",
      confidenceThreshold: 0.85,
      includeUncertain: true
    }
  });

  assert.equal(startResponse.status, 400);
  const startJson = await parseJsonResponse<{ errorCode: string }>(startResponse);
  assert.equal(startJson.errorCode, "team_scan_required");
  assert.equal(harness.state.queueMessages.length, 0);
  assert.equal(harness.state.jobs.get(createJson.jobId)?.status, "upload_pending");
});

test("control plane rejects selected team start when the chosen team was not scanned", async () => {
  const harness = createControlPlaneHarness();
  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "selected-team-mismatch.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-team-mismatch",
      appVersion: "1.0.0",
      analysisVersion: "phase-team"
    }
  );
  const createJson = await parseJsonResponse<{ jobId: string; uploadUrl: string }>(createResponse);
  await uploadObject(harness, createJson.uploadUrl, new TextEncoder().encode("selected team mismatch"));

  const scanResponse = await invokePublicRoute(harness, "POST", `/jobs/${createJson.jobId}/team-scan`, {
    installId: "install-team-mismatch",
    detectedTeams: [
      {
        teamId: "team_dark",
        label: "Dark jerseys",
        colorLabel: "black",
        primaryColorHex: "#111111",
        confidence: 0.93,
        source: "quick_scan"
      }
    ]
  });
  assert.equal(scanResponse.status, 200);

  const startResponse = await invokePublicRoute(harness, "POST", `/jobs/${createJson.jobId}/start`, {
    installId: "install-team-mismatch",
    teamSelection: {
      mode: "team",
      teamId: "team_light",
      label: "Light jerseys",
      colorLabel: "white",
      confidenceThreshold: 0.85,
      includeUncertain: true
    }
  });

  assert.equal(startResponse.status, 400);
  const startJson = await parseJsonResponse<{ errorCode: string }>(startResponse);
  assert.equal(startJson.errorCode, "team_selection_unavailable");
  assert.equal(harness.state.queueMessages.length, 0);
});

test("control plane accepts selected team with equivalent jersey color alias", async () => {
  const harness = createControlPlaneHarness();
  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "selected-team-alias.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-team-alias",
      appVersion: "1.0.0",
      analysisVersion: "phase-team"
    }
  );
  const createJson = await parseJsonResponse<{ jobId: string; uploadUrl: string }>(createResponse);
  await uploadObject(harness, createJson.uploadUrl, new TextEncoder().encode("selected team alias"));

  const scanResponse = await invokePublicRoute(harness, "POST", `/jobs/${createJson.jobId}/team-scan`, {
    installId: "install-team-alias",
    detectedTeams: [
      {
        teamId: "team_black",
        label: "Black jerseys",
        colorLabel: "black",
        primaryColorHex: "#111111",
        confidence: 0.93,
        source: "quick_scan"
      }
    ]
  });
  assert.equal(scanResponse.status, 200);

  const startResponse = await invokePublicRoute(harness, "POST", `/jobs/${createJson.jobId}/start`, {
    installId: "install-team-alias",
    teamSelection: {
      mode: "team",
      teamId: "team_dark",
      label: "Dark jerseys",
      colorLabel: "dark",
      confidenceThreshold: 0.85,
      includeUncertain: true
    }
  });

  assert.equal(startResponse.status, 200);
  assert.equal(harness.state.queueMessages.length, 1);
  assert.equal(harness.state.queueMessages[0]?.teamSelection?.teamId, "team_dark");
  assert.equal(harness.state.queueMessages[0]?.teamSelection?.colorLabel, "dark");
});

test("control plane rejects selected team when team id has an explicit color conflict", async () => {
  const harness = createControlPlaneHarness();
  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "selected-team-conflict.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-team-conflict",
      appVersion: "1.0.0",
      analysisVersion: "phase-team"
    }
  );
  const createJson = await parseJsonResponse<{ jobId: string; uploadUrl: string }>(createResponse);
  await uploadObject(harness, createJson.uploadUrl, new TextEncoder().encode("selected team conflict"));

  const scanResponse = await invokePublicRoute(harness, "POST", `/jobs/${createJson.jobId}/team-scan`, {
    installId: "install-team-conflict",
    detectedTeams: [
      {
        teamId: "team_dark",
        label: "Dark jerseys",
        colorLabel: "black",
        primaryColorHex: "#111111",
        confidence: 0.93,
        source: "quick_scan"
      }
    ]
  });
  assert.equal(scanResponse.status, 200);

  const startResponse = await invokePublicRoute(harness, "POST", `/jobs/${createJson.jobId}/start`, {
    installId: "install-team-conflict",
    teamSelection: {
      mode: "team",
      teamId: "team_dark",
      label: "Light jerseys",
      colorLabel: "white",
      confidenceThreshold: 0.85,
      includeUncertain: true
    }
  });

  assert.equal(startResponse.status, 400);
  const startJson = await parseJsonResponse<{ errorCode: string }>(startResponse);
  assert.equal(startJson.errorCode, "team_selection_unavailable");
  assert.equal(harness.state.queueMessages.length, 0);
});

test("control plane allows all-teams analysis without a team scan", async () => {
  const harness = createControlPlaneHarness();
  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "all-teams-no-scan.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-all-teams",
      appVersion: "1.0.0",
      analysisVersion: "phase-team"
    }
  );
  const createJson = await parseJsonResponse<{ jobId: string; uploadUrl: string }>(createResponse);
  await uploadObject(harness, createJson.uploadUrl, new TextEncoder().encode("all teams no scan"));

  const startResponse = await invokePublicRoute(harness, "POST", `/jobs/${createJson.jobId}/start`, {
    installId: "install-all-teams",
    teamSelection: {
      mode: "all"
    }
  });
  assert.equal(startResponse.status, 200);
  assert.equal(harness.state.queueMessages.length, 1);
  assert.deepEqual(harness.state.queueMessages[0]?.teamSelection, {
    mode: "all",
    teamId: null,
    label: null,
    colorLabel: null,
    confidenceThreshold: 0.85,
    includeUncertain: true
  });
});

test("legacy inference manifest preserves team and timing metadata", async () => {
  const harness = createControlPlaneHarness();
  const teamSelection = {
    mode: "team",
    teamId: "team_light",
    label: "Light jerseys",
    colorLabel: "white",
    confidenceThreshold: 0.85,
    includeUncertain: true
  };

  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: "legacy-team-manifest.mp4",
      contentType: "video/mp4",
      fileSizeBytes: 10485760,
      durationSeconds: 24,
      installId: "install-legacy-team",
      appVersion: "1.0.0",
      analysisVersion: "phase-team-manifest",
      teamSelection
    }
  );
  const createJson = await parseJsonResponse<{
    jobId: string;
    sourceObjectKey: string;
    uploadUrl: string;
  }>(createResponse);

  await uploadObject(harness, createJson.uploadUrl, new TextEncoder().encode("legacy team manifest basketball clip"));

  const scanResponse = await invokePublicRoute(
    harness,
    "POST",
    `/jobs/${createJson.jobId}/team-scan`,
    {
      installId: "install-legacy-team",
      detectedTeams: [
        {
          teamId: "team_light",
          label: "Light jerseys",
          colorLabel: "white",
          primaryColorHex: "#f4f4f4",
          confidence: 0.93,
          source: "quick_scan"
        }
      ]
    }
  );
  assert.equal(scanResponse.status, 200);

  const startResponse = await invokePublicRoute(
    harness,
    "POST",
    "/jobs",
    {
      jobId: createJson.jobId,
      installId: "install-legacy-team",
      sourceObjectKey: createJson.sourceObjectKey
    }
  );
  assert.equal(startResponse.status, 200);

  const callbackResponse = await invokeInternalRoute(
    harness,
    "POST",
    "/internal/inference/callback",
    {
      jobId: createJson.jobId,
      status: "succeeded",
      requestId: "legacy-team-manifest",
      modelVersion: "legacy-manifest-v1",
      resultConfidence: 0.92,
      result: {
        modelVersion: "legacy-manifest-v1",
        resultConfidence: 0.92,
        teamSelection,
        detectedTeams: [
          {
            teamId: "team_light",
            label: "Light jerseys",
            colorLabel: "white",
            primaryColorHex: "#f4f4f4",
            confidence: 0.93,
            source: "quick_scan"
          }
        ],
        clips: [
          {
            startTime: 4,
            endTime: 9,
            eventCenter: 6.25,
            confidence: 0.91,
            label: "Steal",
            action: "Steal",
            audioScore: 0.44,
            visualScore: 0.86,
            motionScore: 0.82,
            combinedScore: 0.88,
            detectionMethod: "cloud",
            shouldAutoKeep: true,
            shouldEnableSlowMotion: false,
            nativeShotSignals: {
              isShotLike: false,
              leadInSeconds: 1.8,
              followThroughSeconds: 2.7,
              setupContextScore: 0.9,
              outcomeContextScore: 0.85,
              eventCenterQuality: 0.88,
              contextQualityScore: 0.9,
              timingWindowOk: true,
              outcome: "not_shot",
              outcomeConfidence: 1
            },
            teamAttribution: {
              teamId: "team_light",
              label: "Light jerseys",
              colorLabel: "white",
              confidence: 0.89,
              source: "gpt_frame_review"
            },
            teamAttributionStatus: "matched"
          }
        ]
      }
    },
    { "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET }
  );
  assert.equal(callbackResponse.status, 200);

  const finalResponse = await invokePublicRoute(harness, "GET", `/jobs/${createJson.jobId}`);
  const finalJson = await parseJsonResponse<{
    results: {
      detectedTeams?: Array<{ primaryColorHex?: string | null }> | null;
      teamSelection?: typeof teamSelection | null;
      clips: Array<{
        eventCenter?: number | null;
        nativeShotSignals?: { timingWindowOk: boolean } | null;
        teamAttribution?: { teamId?: string | null } | null;
        teamAttributionStatus?: string | null;
      }>;
    } | null;
  }>(finalResponse);

  assert.deepEqual(finalJson.results?.teamSelection, teamSelection);
  assert.equal(finalJson.results?.detectedTeams?.[0]?.primaryColorHex, "#f4f4f4");
  assert.equal(finalJson.results?.clips[0]?.eventCenter, 6.25);
  assert.equal(finalJson.results?.clips[0]?.nativeShotSignals?.timingWindowOk, true);
  assert.equal(finalJson.results?.clips[0]?.teamAttribution?.teamId, "team_light");
  assert.equal(finalJson.results?.clips[0]?.teamAttributionStatus, "matched");
});
