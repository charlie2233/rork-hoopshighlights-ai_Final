import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const { createControlPlaneHarness, invokePublicRoute, parseJsonResponse } = harness;

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
