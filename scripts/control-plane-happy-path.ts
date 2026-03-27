import {
  buildHeartbeatPayload,
  buildSuccessCallbackPayload,
  createControlPlaneHarness,
  invokeInternalRoute,
  invokePublicRoute,
  parseJsonResponse,
  uploadObject
} from "./control-plane-harness";

interface FlowSummary {
  mode: "local" | "http";
  jobId: string;
  uploadKey: string;
  queueMessageCount?: number;
  finalStatus: string;
  modelVersion: string | null;
  clipCount: number | null;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const baseUrl = args.baseUrl ?? process.env.CONTROL_PLANE_BASE_URL ?? "";
  const mode = baseUrl ? "http" : "local";

  const summary = mode === "http" ? await runHttpHappyPath(baseUrl, args) : await runLocalHappyPath(args);
  console.log(JSON.stringify(summary, null, 2));
}

async function runLocalHappyPath(args: ParsedArgs): Promise<FlowSummary> {
  const harness = createControlPlaneHarness({
    APP_ENV: "local",
    CONTROL_PLANE_SHARED_SECRET: args.sharedSecret ?? "local-control-plane-secret",
    ADMIN_API_TOKEN: args.adminToken ?? "local-admin-token"
  });

  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/v1/analysis/jobs",
    {
      filename: args.filename,
      contentType: args.contentType,
      fileSizeBytes: args.fileSizeBytes,
      durationSeconds: args.durationSeconds,
      installId: args.installId,
      appVersion: args.appVersion,
      analysisVersion: args.analysisVersion
    },
    { "x-trace-id": args.traceId }
  );
  const createJson = await parseJsonResponse<{
    jobId: string;
    sourceObjectKey: string;
    uploadUrl: string;
  }>(createResponse);

  const uploadKey = createJson.sourceObjectKey;
  await uploadObject(harness, uploadKey, new TextEncoder().encode("fake basketball clip"));

  const startResponse = await invokePublicRoute(
    harness,
    "POST",
    `/v1/analysis/jobs/${createJson.jobId}/start`,
    { installId: args.installId },
    { "x-trace-id": args.traceId }
  );
  const startJson = await parseJsonResponse<{ status: string }>(startResponse);

  const heartbeatResponse = await invokeInternalRoute(
    harness,
    "POST",
    `/v1/internal/inference/heartbeat/${createJson.jobId}`,
    buildHeartbeatPayload(),
    { "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET }
  );
  await parseJsonResponse(heartbeatResponse);

  const callbackResponse = await invokeInternalRoute(
    harness,
    "POST",
    `/v1/internal/inference/callback/${createJson.jobId}`,
    buildSuccessCallbackPayload({
      jobId: createJson.jobId,
      requestId: args.traceId,
      modelVersion: args.modelVersion
    }),
    { "x-hoops-inference-secret": harness.env.INFERENCE_SHARED_SECRET }
  );
  const callbackJson = await parseJsonResponse<{ modelVersion: string | null; status: string }>(callbackResponse);

  const finalResponse = await invokePublicRoute(harness, "GET", `/v1/analysis/jobs/${createJson.jobId}`);
  const finalJson = await parseJsonResponse<{ status: string; results?: { clipCount: number | null } | null }>(finalResponse);

  return {
    mode: "local",
    jobId: createJson.jobId,
    uploadKey,
    queueMessageCount: harness.state.queueMessages.length,
    finalStatus: finalJson.status,
    modelVersion: callbackJson.modelVersion,
    clipCount: finalJson.results?.clipCount ?? null
  };
}

async function runHttpHappyPath(baseUrl: string, args: ParsedArgs): Promise<FlowSummary> {
  const createResponse = await fetchJson(`${baseUrl}/v1/analysis/jobs`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-trace-id": args.traceId
    },
    body: {
      filename: args.filename,
      contentType: args.contentType,
      fileSizeBytes: args.fileSizeBytes,
      durationSeconds: args.durationSeconds,
      installId: args.installId,
      appVersion: args.appVersion,
      analysisVersion: args.analysisVersion
    }
  });

  const uploadKey = createResponse.sourceObjectKey;
  await fetch(createResponse.uploadUrl, {
    method: "PUT",
    headers: {
      "content-type": args.contentType
    },
    body: new TextEncoder().encode("fake basketball clip")
  });

  const startResponse = await fetchJson(`${baseUrl}/v1/analysis/jobs/${createResponse.jobId}/start`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-trace-id": args.traceId
    },
    body: { installId: args.installId }
  });

  const callbackResponse = await fetchJson(`${baseUrl}/v1/internal/inference/callback/${createResponse.jobId}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-hoops-inference-secret": args.sharedSecret ?? "inference-secret",
      "x-trace-id": args.traceId
    },
    body: buildSuccessCallbackPayload({
      jobId: createResponse.jobId,
      requestId: args.traceId,
      modelVersion: args.modelVersion
    })
  });

  const finalResponse = await fetchJson(`${baseUrl}/v1/analysis/jobs/${createResponse.jobId}`);

  return {
    mode: "http",
    jobId: createResponse.jobId,
    uploadKey,
    finalStatus: finalResponse.status,
    modelVersion: callbackResponse.modelVersion ?? null,
    clipCount: finalResponse.results?.clipCount ?? null
  };
}

async function fetchJson(url: string, init: RequestInit & { body?: unknown } = {}): Promise<any> {
  const headers = new Headers(init.headers ?? {});
  let body = init.body;
  if (body && typeof body !== "string" && !(body instanceof Blob) && !(body instanceof FormData)) {
    headers.set("content-type", "application/json");
    body = JSON.stringify(body);
  }

  const response = await fetch(url, { ...init, headers, body });
  if (!response.ok) {
    throw new Error(`Request to ${url} failed with ${response.status}`);
  }
  return response.json();
}

interface ParsedArgs {
  baseUrl?: string;
  sharedSecret?: string;
  adminToken?: string;
  installId: string;
  filename: string;
  contentType: string;
  fileSizeBytes: number;
  durationSeconds: number;
  appVersion: string;
  analysisVersion: string;
  modelVersion: string;
  traceId: string;
}

function parseArgs(argv: string[]): ParsedArgs {
  const map = new Map<string, string>();
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token?.startsWith("--")) {
      continue;
    }
    const [key, inlineValue] = token.split("=", 2);
    if (inlineValue) {
      map.set(key, inlineValue);
      continue;
    }
    const next = argv[index + 1];
    if (next && !next.startsWith("--")) {
      map.set(key, next);
      index += 1;
    } else {
      map.set(key, "true");
    }
  }

  return {
    baseUrl: map.get("--base-url"),
    sharedSecret: map.get("--shared-secret"),
    adminToken: map.get("--admin-token"),
    installId: map.get("--install-id") ?? "install-local-001",
    filename: map.get("--filename") ?? "sample-game.mp4",
    contentType: map.get("--content-type") ?? "video/mp4",
    fileSizeBytes: Number.parseInt(map.get("--file-size-bytes") ?? "10485760", 10),
    durationSeconds: Number.parseFloat(map.get("--duration-seconds") ?? "24"),
    appVersion: map.get("--app-version") ?? "1.0.0",
    analysisVersion: map.get("--analysis-version") ?? "phase1a",
    modelVersion: map.get("--model-version") ?? "video-mae-stub-v1",
    traceId: map.get("--trace-id") ?? crypto.randomUUID()
  };
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
