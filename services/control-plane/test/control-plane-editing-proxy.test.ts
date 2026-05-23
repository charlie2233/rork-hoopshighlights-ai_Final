import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const { createControlPlaneHarness, invokePublicRoute, parseJsonResponse } = harness;

test("editing version route proxies safe feature flags from internal editing service", async () => {
  const controlPlane = createControlPlaneHarness();
  const originalFetch = globalThis.fetch.bind(globalThis);
  const seen: Array<{ url: string; headers: Record<string, string> }> = [];
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    if (url.origin !== controlPlane.env.EDITING_BASE_URL) {
      return originalFetch(input, init);
    }
    seen.push({
      url: url.toString(),
      headers: Object.fromEntries(request.headers.entries())
    });
    return Response.json({
      service: "hoopclips-editing",
      backendModelVersion: "editing-cloud-v1",
      gitSha: "test-sha",
      featureFlags: {
        aiEditEnabled: true,
        aiEditLiveRenderEnabled: false,
        aiEditRevisionEnabled: true,
        aiEditTemplatePackEnabled: true
      }
    });
  };

  try {
    const response = await invokePublicRoute(
      controlPlane,
      "GET",
      "/v1/editing/version",
      undefined,
      { "x-trace-id": "trace-editing-version" },
      "trace-editing-version"
    );
    const payload = await parseJsonResponse<{
      requestId: string;
      service: string;
      featureFlags: { aiEditLiveRenderEnabled: boolean };
    }>(response);

    assert.equal(response.status, 200);
    assert.equal(payload.requestId, "trace-editing-version");
    assert.equal(payload.service, "hoopclips-editing");
    assert.equal(payload.featureFlags.aiEditLiveRenderEnabled, false);
    assert.equal(seen.length, 1);
    assert.equal(seen[0]!.url, "http://editing.local/version");
    assert.equal(seen[0]!.headers["x-hoops-editing-secret"], controlPlane.env.EDITING_SHARED_SECRET);
    assert.equal(seen[0]!.headers["x-request-id"], "trace-editing-version");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("editing version route fails closed when editing service is unconfigured", async () => {
  const controlPlane = createControlPlaneHarness({ EDITING_BASE_URL: "" });

  const response = await invokePublicRoute(
    controlPlane,
    "GET",
    "/v1/editing/version",
    undefined,
    {},
    "trace-editing-version-unconfigured"
  );
  const payload = await parseJsonResponse<{ errorCode: string }>(response);

  assert.equal(response.status, 503);
  assert.equal(payload.errorCode, "editing_service_unconfigured");
});

test("edit job creation proxies to internal editing service with shared secret", async () => {
  const controlPlane = createControlPlaneHarness();
  const originalFetch = globalThis.fetch.bind(globalThis);
  const seen: Array<{ url: string; headers: Record<string, string>; body: Record<string, unknown> }> = [];
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    if (url.origin !== controlPlane.env.EDITING_BASE_URL) {
      return originalFetch(input, init);
    }
    seen.push({
      url: url.toString(),
      headers: Object.fromEntries(request.headers.entries()),
      body: (await request.json()) as Record<string, unknown>
    });
    return Response.json({
      editJobId: "edit_123",
      videoId: "video_123",
      analysisJobId: "analysis_123",
      status: "plan_ready",
      preset: "personal_highlight",
      targetDurationSeconds: 30,
      aspectRatio: "9:16",
      clipCount: 2,
      validationErrors: []
    });
  };

  try {
    const response = await invokePublicRoute(
      controlPlane,
      "POST",
      "/v1/edit-jobs",
      {
        videoId: "video_123",
        analysisJobId: "analysis_123",
        installId: "install-local-001",
        sourceObjectKey: "uploads/job/source.mp4",
        preset: "personal_highlight",
        targetDurationSeconds: 30,
        aspectRatio: "9:16",
        planTier: "free",
        userPrompt: "Make it more hype and focus on defense.",
        clips: []
      },
      { "x-trace-id": "trace-editing-create" },
      "trace-editing-create"
    );
    const payload = await parseJsonResponse<{ requestId: string; editJobId: string; status: string }>(response);

    assert.equal(response.status, 200);
    assert.equal(payload.requestId, "trace-editing-create");
    assert.equal(payload.editJobId, "edit_123");
    assert.equal(payload.status, "plan_ready");
    assert.equal(seen.length, 1);
    assert.equal(seen[0]!.url, "http://editing.local/v1/edit-jobs");
    assert.equal(seen[0]!.headers["x-hoops-editing-secret"], controlPlane.env.EDITING_SHARED_SECRET);
    assert.equal(seen[0]!.headers["x-hoops-install-id"], "install-local-001");
    assert.equal(seen[0]!.body.userPrompt, "Make it more hype and focus on defense.");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("edit plan route proxies to internal editing service with install id", async () => {
  const controlPlane = createControlPlaneHarness();
  const originalFetch = globalThis.fetch.bind(globalThis);
  const seen: Array<{ url: string; headers: Record<string, string> }> = [];
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    if (url.origin !== controlPlane.env.EDITING_BASE_URL) {
      return originalFetch(input, init);
    }
    seen.push({
      url: url.toString(),
      headers: Object.fromEntries(request.headers.entries())
    });
    return Response.json({
      editJobId: "edit_123",
      status: "plan_ready",
      plan: { renderMode: "cloud_ffmpeg", aspectRatio: "9:16" },
      validationErrors: []
    });
  };

  try {
    const response = await invokePublicRoute(
      controlPlane,
      "GET",
      "/v1/edit-jobs/edit_123/plan?installId=install-local-001",
      undefined,
      { "x-trace-id": "trace-editing-plan" },
      "trace-editing-plan"
    );
    const payload = await parseJsonResponse<{ requestId: string; editJobId: string; plan: Record<string, unknown> }>(response);

    assert.equal(response.status, 200);
    assert.equal(payload.requestId, "trace-editing-plan");
    assert.equal(payload.editJobId, "edit_123");
    assert.equal(payload.plan.aspectRatio, "9:16");
    assert.equal(seen.length, 1);
    assert.equal(seen[0]!.url, "http://editing.local/v1/edit-jobs/edit_123/plan?installId=install-local-001");
    assert.equal(seen[0]!.headers["x-hoops-install-id"], "install-local-001");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("edit job creation accepts and forwards premium template identity fields", async () => {
  const controlPlane = createControlPlaneHarness();
  const originalFetch = globalThis.fetch.bind(globalThis);
  const seen: Array<Record<string, unknown>> = [];
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    if (url.origin !== controlPlane.env.EDITING_BASE_URL) {
      return originalFetch(input, init);
    }
    seen.push((await request.json()) as Record<string, unknown>);
    return Response.json({
      editJobId: "edit_pro_123",
      videoId: "video_123",
      analysisJobId: "analysis_123",
      status: "plan_ready",
      preset: "personal_highlight",
      templateId: "cinematic_mixtape_pro_v1",
      planTier: "pro",
      targetDurationSeconds: 45,
      aspectRatio: "9:16",
      clipCount: 2,
      validationErrors: []
    });
  };

  try {
    const response = await invokePublicRoute(
      controlPlane,
      "POST",
      "/v1/edit-jobs",
      {
        videoId: "video_123",
        analysisJobId: "analysis_123",
        installId: "install-local-001",
        sourceObjectKey: "uploads/job/source.mp4",
        preset: "personal_highlight",
        templateId: "cinematic_mixtape_pro_v1",
        targetDurationSeconds: 45,
        aspectRatio: "9:16",
        planTier: "pro",
        revenueCatAppUserID: "hoops_email_hash",
        clips: []
      },
      { "x-trace-id": "trace-editing-pro-template" },
      "trace-editing-pro-template"
    );
    const payload = await parseJsonResponse<{ requestId: string; editJobId: string; templateId: string }>(response);

    assert.equal(response.status, 200);
    assert.equal(payload.requestId, "trace-editing-pro-template");
    assert.equal(payload.editJobId, "edit_pro_123");
    assert.equal(payload.templateId, "cinematic_mixtape_pro_v1");
    assert.equal(seen[0]!.templateId, "cinematic_mixtape_pro_v1");
    assert.equal(seen[0]!.revenueCatAppUserID, "hoops_email_hash");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("edit render route proxies to internal editing service with shared secret", async () => {
  const controlPlane = createControlPlaneHarness();
  const originalFetch = globalThis.fetch.bind(globalThis);
  const seen: Array<{ url: string; headers: Record<string, string>; body: Record<string, unknown> }> = [];
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    if (url.origin !== controlPlane.env.EDITING_BASE_URL) {
      return originalFetch(input, init);
    }
    seen.push({
      url: url.toString(),
      headers: Object.fromEntries(request.headers.entries()),
      body: (await request.json()) as Record<string, unknown>
    });
    return Response.json({
      editJobId: "edit_123",
      renderJobId: "render_123",
      renderer: "cloud_ffmpeg",
      rendererVersion: "ffmpeg-renderer-v1",
      status: "queued",
      aspectRatio: "9:16",
      traceId: "trace_123"
    });
  };

  try {
    const response = await invokePublicRoute(
      controlPlane,
      "POST",
      "/v1/edit-jobs/edit_123/render",
      {
        installId: "install-local-001",
        sourceObjectKey: "uploads/job/source.mp4",
        planTier: "free",
        editPlan: { aspectRatio: "9:16" },
        sourceClips: []
      },
      { "x-trace-id": "trace-editing-proxy" },
      "trace-editing-proxy"
    );
    const payload = await parseJsonResponse<{ requestId: string; renderJobId: string; status: string }>(response);

    assert.equal(response.status, 200);
    assert.equal(payload.requestId, "trace-editing-proxy");
    assert.equal(payload.renderJobId, "render_123");
    assert.equal(payload.status, "queued");
    assert.equal(seen.length, 1);
    assert.equal(seen[0]!.url, "http://editing.local/v1/edit-jobs/edit_123/render");
    assert.equal(seen[0]!.headers["x-hoops-editing-secret"], controlPlane.env.EDITING_SHARED_SECRET);
    assert.equal(seen[0]!.headers["x-request-id"], "trace-editing-proxy");
    assert.equal(seen[0]!.body.installId, "install-local-001");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("render history route proxies through control-plane without storage internals", async () => {
  const controlPlane = createControlPlaneHarness();
  const originalFetch = globalThis.fetch.bind(globalThis);
  const seen: Array<{ url: string; headers: Record<string, string> }> = [];
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    if (url.origin !== controlPlane.env.EDITING_BASE_URL) {
      return originalFetch(input, init);
    }
    seen.push({
      url: url.toString(),
      headers: Object.fromEntries(request.headers.entries())
    });
    return Response.json({
      installId: "install-local-001",
      generatedAt: "2026-05-22T12:00:00Z",
      renders: [
        {
          editJobId: "edit_123",
          renderJobId: "render_123",
          renderer: "cloud_ffmpeg",
          rendererVersion: "ffmpeg-renderer-v1",
          status: "rendered",
          outputObjectKey: "edits/edit_123/render_jobs/render_123/final.mp4",
          renderLogObjectKey: "edits/edit_123/render_jobs/render_123/render_log.json",
          aspectRatio: "9:16",
          traceId: "trace_123",
          planTier: "free",
          retentionMetadata: {
            expiresAt: "2026-06-05T12:00:00Z",
            renderJobId: "render_123"
          }
        }
      ]
    });
  };

  try {
    const response = await invokePublicRoute(
      controlPlane,
      "GET",
      "/v1/render-jobs?installId=install-local-001&limit=20",
      undefined,
      { "x-trace-id": "trace-render-history" },
      "trace-render-history"
    );
    const payload = await parseJsonResponse<{ requestId: string; renders: Array<{ renderJobId: string }> }>(response);
    const serialized = JSON.stringify(payload);

    assert.equal(response.status, 200);
    assert.equal(payload.requestId, "trace-render-history");
    assert.equal(payload.renders[0]!.renderJobId, "render_123");
    assert.equal(seen.length, 1);
    assert.equal(seen[0]!.url, "http://editing.local/v1/render-jobs?installId=install-local-001&limit=20");
    assert.equal(seen[0]!.headers["x-hoops-editing-secret"], controlPlane.env.EDITING_SHARED_SECRET);
    assert.equal(seen[0]!.headers["x-hoops-install-id"], "install-local-001");
    assert.equal(serialized.includes("outputObjectKey"), false);
    assert.equal(serialized.includes("renderLogObjectKey"), false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("render download route proxies by render id and redacts object key", async () => {
  const controlPlane = createControlPlaneHarness();
  const originalFetch = globalThis.fetch.bind(globalThis);
  const seen: Array<{ url: string; headers: Record<string, string> }> = [];
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    if (url.origin !== controlPlane.env.EDITING_BASE_URL) {
      return originalFetch(input, init);
    }
    seen.push({
      url: url.toString(),
      headers: Object.fromEntries(request.headers.entries())
    });
    return Response.json({
      editJobId: "edit_123",
      renderJobId: "render_123",
      downloadUrl: "https://r2.example/download-tokenized-final-mp4",
      outputObjectKey: "edits/edit_123/render_jobs/render_123/final.mp4",
      contentType: "video/mp4",
      expiresAt: "2026-05-22T12:15:00Z"
    });
  };

  try {
    const response = await invokePublicRoute(
      controlPlane,
      "GET",
      "/v1/render-jobs/render_123/download-url?installId=install-local-001",
      undefined,
      { "x-trace-id": "trace-render-download" },
      "trace-render-download"
    );
    const payload = await parseJsonResponse<{ requestId: string; downloadUrl: string; outputObjectKey?: string }>(response);

    assert.equal(response.status, 200);
    assert.equal(payload.requestId, "trace-render-download");
    assert.equal(payload.downloadUrl.startsWith("https://r2.example/download-tokenized-final-mp4"), true);
    assert.equal(payload.outputObjectKey, undefined);
    assert.equal(seen.length, 1);
    assert.equal(seen[0]!.url, "http://editing.local/v1/render-jobs/render_123/download-url?installId=install-local-001");
    assert.equal(seen[0]!.headers["x-hoops-editing-secret"], controlPlane.env.EDITING_SHARED_SECRET);
    assert.equal(seen[0]!.headers["x-hoops-install-id"], "install-local-001");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("edit revision routes proxy to internal editing service with shared secret", async () => {
  const controlPlane = createControlPlaneHarness();
  const originalFetch = globalThis.fetch.bind(globalThis);
  const seen: Array<{ method: string; url: string; headers: Record<string, string>; body?: Record<string, unknown> }> = [];
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    if (url.origin !== controlPlane.env.EDITING_BASE_URL) {
      return originalFetch(input, init);
    }
    const body = request.method === "GET" ? undefined : ((await request.json()) as Record<string, unknown>);
    seen.push({
      method: request.method,
      url: url.toString(),
      headers: Object.fromEntries(request.headers.entries()),
      body
    });
    if (url.pathname.endsWith("/render")) {
      return Response.json({
        editJobId: "edit_123",
        renderJobId: "render_revision_123",
        renderer: "cloud_ffmpeg",
        rendererVersion: "ffmpeg-renderer-v1",
        status: "queued",
        aspectRatio: "9:16",
        traceId: "trace_revision_render"
      });
    }
    if (url.pathname.endsWith("/revisions")) {
      return Response.json({ editJobId: "edit_123", revisions: [] });
    }
    return Response.json({
      editJobId: "edit_123",
      revisionId: "rev_123",
      basePlanId: "edit_123",
      newPlanId: "edit_123:rev_123",
      command: "make_more_hype",
      status: "revision_ready",
      patch: { version: "edit-plan-patch-v1", operations: [] },
      revisedPlan: { aspectRatio: "9:16" },
      validationResult: { valid: true, errors: [] },
      requiresRerender: true
    });
  };

  try {
    const reviseResponse = await invokePublicRoute(
      controlPlane,
      "POST",
      "/v1/edit-jobs/edit_123/revise",
      { installId: "install-local-001", command: "make_more_hype" },
      { "x-trace-id": "trace-editing-revise" },
      "trace-editing-revise"
    );
    const revisePayload = await parseJsonResponse<{ requestId: string; revisionId: string; status: string }>(reviseResponse);
    assert.equal(reviseResponse.status, 200);
    assert.equal(revisePayload.requestId, "trace-editing-revise");
    assert.equal(revisePayload.revisionId, "rev_123");
    assert.equal(revisePayload.status, "revision_ready");

    const listResponse = await invokePublicRoute(
      controlPlane,
      "GET",
      "/v1/edit-jobs/edit_123/revisions?installId=install-local-001",
      undefined,
      { "x-trace-id": "trace-editing-revisions" },
      "trace-editing-revisions"
    );
    assert.equal(listResponse.status, 200);

    const getResponse = await invokePublicRoute(
      controlPlane,
      "GET",
      "/v1/edit-jobs/edit_123/revisions/rev_123?installId=install-local-001",
      undefined,
      { "x-trace-id": "trace-editing-revision-get" },
      "trace-editing-revision-get"
    );
    assert.equal(getResponse.status, 200);

    const renderResponse = await invokePublicRoute(
      controlPlane,
      "POST",
      "/v1/edit-jobs/edit_123/revisions/rev_123/render",
      { installId: "install-local-001" },
      { "x-trace-id": "trace-editing-revision-render" },
      "trace-editing-revision-render"
    );
    const renderPayload = await parseJsonResponse<{ requestId: string; renderJobId: string; status: string }>(renderResponse);
    assert.equal(renderResponse.status, 200);
    assert.equal(renderPayload.renderJobId, "render_revision_123");
    assert.equal(renderPayload.status, "queued");

    assert.equal(seen.length, 4);
    assert.equal(seen[0]!.url, "http://editing.local/v1/edit-jobs/edit_123/revise");
    assert.equal(seen[0]!.headers["x-hoops-editing-secret"], controlPlane.env.EDITING_SHARED_SECRET);
    assert.equal(seen[0]!.headers["x-hoops-install-id"], "install-local-001");
    assert.equal(seen[0]!.body?.command, "make_more_hype");
    assert.equal(seen[1]!.url, "http://editing.local/v1/edit-jobs/edit_123/revisions?installId=install-local-001");
    assert.equal(seen[2]!.url, "http://editing.local/v1/edit-jobs/edit_123/revisions/rev_123?installId=install-local-001");
    assert.equal(seen[3]!.url, "http://editing.local/v1/edit-jobs/edit_123/revisions/rev_123/render");
    assert.equal(seen[3]!.body?.installId, "install-local-001");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("edit render route fails closed when editing service is unconfigured", async () => {
  const controlPlane = createControlPlaneHarness({ EDITING_BASE_URL: "" });

  const response = await invokePublicRoute(
    controlPlane,
    "POST",
    "/v1/edit-jobs/edit_123/render",
    {
      installId: "install-local-001",
      sourceObjectKey: "uploads/job/source.mp4",
      planTier: "free",
      editPlan: { aspectRatio: "9:16" },
      sourceClips: []
    },
    {},
    "trace-editing-unconfigured"
  );
  const payload = await parseJsonResponse<{ errorCode: string }>(response);

  assert.equal(response.status, 503);
  assert.equal(payload.errorCode, "editing_service_unconfigured");
});


test("edit render route proxies policy failures from editing service", async () => {
  const controlPlane = createControlPlaneHarness();
  const originalFetch = globalThis.fetch.bind(globalThis);
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    if (url.origin !== controlPlane.env.EDITING_BASE_URL) {
      return originalFetch(input, init);
    }
    return Response.json(
      {
        errorCode: "daily_render_limit",
        errorMessage: "Daily AI edit render limit reached for this plan.",
        failureReason: "Daily AI edit render limit reached for this plan."
      },
      { status: 429 }
    );
  };

  try {
    const response = await invokePublicRoute(
      controlPlane,
      "POST",
      "/v1/edit-jobs/edit_123/render",
      {
        installId: "install-local-001",
        sourceObjectKey: "uploads/job/source.mp4",
        planTier: "free",
        editPlan: { aspectRatio: "9:16" },
        sourceClips: []
      },
      { "x-trace-id": "trace-editing-policy-failure" },
      "trace-editing-policy-failure"
    );
    const payload = await parseJsonResponse<{ requestId: string; errorCode: string; failureReason: string }>(response);

    assert.equal(response.status, 429);
    assert.equal(payload.requestId, "trace-editing-policy-failure");
    assert.equal(payload.errorCode, "daily_render_limit");
    assert.match(payload.failureReason, /Daily AI edit render limit/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
