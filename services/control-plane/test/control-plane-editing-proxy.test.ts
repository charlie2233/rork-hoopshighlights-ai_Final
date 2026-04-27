import assert from "node:assert/strict";
import { test } from "node:test";
import harness from "../../../scripts/control-plane-harness";

const { createControlPlaneHarness, invokePublicRoute, parseJsonResponse } = harness;

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
