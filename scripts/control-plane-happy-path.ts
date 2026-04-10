import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import {
  createControlPlaneHarness,
  invokePublicRoute,
  parseJsonResponse,
  uploadObject
} from "./control-plane-harness";

interface FlowSummary {
  mode: "local" | "http";
  jobId: string;
  uploadKey: string;
  uploadTraceId: string | null;
  inferenceAttemptId: string | null;
  attemptCount: number | null;
  acceptedAt: string | null;
  processingStartedAt: string | null;
  queueMessageCount?: number;
  finalStatus: string;
  modelVersion: string | null;
  clipCount: number | null;
  clips: Array<{
    clipId: string;
    finalLabel: string;
    clipDurationSeconds: number | null;
    wasMerged: boolean;
    sourceEventCount: number | null;
  }>;
  requestIds: {
    presign: string;
    finalize: string;
    callback: string | null;
    poll: string;
  };
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const baseUrl = args.baseUrl ?? process.env.CONTROL_PLANE_BASE_URL ?? "";
  const mode = baseUrl ? "http" : "local";
  const upload = await resolveUploadInput(args);

  const summary = mode === "http" ? await runHttpHappyPath(baseUrl, args, upload) : await runLocalHappyPath(args, upload);
  console.log(JSON.stringify(summary, null, 2));
}

async function runLocalHappyPath(args: ParsedArgs, upload: UploadInput): Promise<FlowSummary> {
  const harness = createControlPlaneHarness({
    APP_ENV: "local",
    CONTROL_PLANE_SHARED_SECRET: args.sharedSecret ?? "local-control-plane-secret",
    ADMIN_API_TOKEN: args.adminToken ?? "local-admin-token"
  });

  const createResponse = await invokePublicRoute(
    harness,
    "POST",
    "/uploads/presign",
    {
      filename: upload.filename,
      contentType: upload.contentType,
      fileSizeBytes: upload.fileSizeBytes,
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
    requestId: string;
  }>(createResponse);

  const uploadKey = createJson.sourceObjectKey;
  await uploadObject(harness, createJson.uploadUrl, upload.body);

  const finalizeResponse = await invokePublicRoute(
    harness,
    "POST",
    "/jobs",
    {
      jobId: createJson.jobId,
      installId: args.installId,
      sourceObjectKey: createJson.sourceObjectKey
    },
    { "x-trace-id": args.traceId }
  );
  const finalizeJson = await parseJsonResponse<{ status: string; requestId: string }>(finalizeResponse);
  if (finalizeJson.status !== "queued") {
    throw new Error(`Expected queued status after finalize, received ${finalizeJson.status}.`);
  }

  const processedMessages = await harness.drainQueue();
  const finalJson = await pollLocalJob(harness, createJson.jobId, args);
  const callbackRequestId = harness.state.callbackRequests.at(-1)?.requestId ?? null;
  const summaryClips = summarizeClips(finalJson.results?.clips ?? []);

  return {
    mode: "local",
    jobId: createJson.jobId,
    uploadKey,
    uploadTraceId: finalJson.uploadTraceId ?? null,
    inferenceAttemptId: finalJson.inferenceAttemptId ?? null,
    attemptCount: finalJson.attemptCount ?? null,
    acceptedAt: finalJson.acceptedAt ?? null,
    processingStartedAt: finalJson.processingStartedAt ?? null,
    queueMessageCount: processedMessages,
    finalStatus: finalJson.status,
    modelVersion: finalJson.modelVersion ?? null,
    clipCount: finalJson.results?.clipCount ?? null,
    clips: summaryClips,
    requestIds: {
      presign: createJson.requestId,
      finalize: finalizeJson.requestId ?? args.traceId,
      callback: callbackRequestId ?? finalizeJson.requestId ?? args.traceId,
      poll: finalJson.requestId ?? args.traceId
    }
  };
}

async function runHttpHappyPath(baseUrl: string, args: ParsedArgs, upload: UploadInput): Promise<FlowSummary> {
  const createResponse = await fetchJson(`${baseUrl}/uploads/presign`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-trace-id": args.traceId
    },
    body: {
      filename: upload.filename,
      contentType: upload.contentType,
      fileSizeBytes: upload.fileSizeBytes,
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
      "content-type": upload.contentType
    },
    body: upload.body
  });

  const finalizeResponse = await fetchJson(`${baseUrl}/jobs`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-trace-id": args.traceId
    },
    body: {
      jobId: createResponse.jobId,
      installId: args.installId,
      sourceObjectKey: createResponse.sourceObjectKey
    }
  });
  if (finalizeResponse.status !== "queued") {
    throw new Error(`Expected queued status after finalize, received ${finalizeResponse.status}.`);
  }

  const finalResponse = await pollHttpJob(`${baseUrl}/jobs/${createResponse.jobId}`, args);
  const summaryClips = summarizeClips(finalResponse.results?.clips ?? []);
  const callbackRequestId =
    typeof finalResponse.results?.requestId === "string" && finalResponse.results.requestId.length > 0
      ? finalResponse.results.requestId
      : finalizeResponse.requestId ?? args.traceId;

  return {
    mode: "http",
    jobId: createResponse.jobId,
    uploadKey,
    uploadTraceId: finalResponse.uploadTraceId ?? null,
    inferenceAttemptId: finalResponse.inferenceAttemptId ?? null,
    attemptCount: finalResponse.attemptCount ?? null,
    acceptedAt: finalResponse.acceptedAt ?? null,
    processingStartedAt: finalResponse.processingStartedAt ?? null,
    finalStatus: finalResponse.status,
    modelVersion: finalResponse.modelVersion ?? null,
    clipCount: finalResponse.results?.clipCount ?? null,
    clips: summaryClips,
    requestIds: {
      presign: createResponse.requestId ?? args.traceId,
      finalize: finalizeResponse.requestId ?? args.traceId,
      callback: callbackRequestId,
      poll: finalResponse.requestId ?? args.traceId
    }
  };
}

async function pollLocalJob(
  harness: ReturnType<typeof createControlPlaneHarness>,
  jobId: string,
  args: ParsedArgs
): Promise<any> {
  const startedAt = Date.now();

  while (true) {
    const response = await invokePublicRoute(harness, "GET", `/jobs/${jobId}`, undefined, { "x-trace-id": args.traceId });
    const payload = await parseJsonResponse<any>(response);
    if (isTerminalStatus(payload.status)) {
      return payload;
    }
    if (Date.now() - startedAt > args.pollTimeoutSeconds * 1000) {
      throw new Error(`Timed out waiting for local terminal job status for ${jobId}.`);
    }
    await sleep(Math.max(args.pollIntervalSeconds, 0.2) * 1000);
  }
}

async function pollHttpJob(url: string, args: ParsedArgs): Promise<any> {
  const startedAt = Date.now();

  while (true) {
    const response = await fetchJson(url, {
      headers: {
        "x-trace-id": args.traceId
      }
    });
    if (isTerminalStatus(response.status)) {
      return response;
    }
    if (Date.now() - startedAt > args.pollTimeoutSeconds * 1000) {
      throw new Error(`Timed out waiting for terminal job status for ${url}.`);
    }
    const pollDelaySeconds = Number(response.pollAfterSeconds ?? args.pollIntervalSeconds);
    await sleep(Math.max(pollDelaySeconds, 0.2) * 1000);
  }
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
  filePath?: string;
  installId: string;
  filename: string;
  contentType: string;
  fileSizeBytes: number;
  durationSeconds: number;
  appVersion: string;
  analysisVersion: string;
  modelVersion: string;
  traceId: string;
  pollIntervalSeconds: number;
  pollTimeoutSeconds: number;
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
    filePath: map.get("--file"),
    installId: map.get("--install-id") ?? "install-local-001",
    filename: map.get("--filename") ?? "sample-game.mp4",
    contentType: map.get("--content-type") ?? "video/mp4",
    fileSizeBytes: Number.parseInt(map.get("--file-size-bytes") ?? "10485760", 10),
    durationSeconds: Number.parseFloat(map.get("--duration-seconds") ?? "24"),
    appVersion: map.get("--app-version") ?? "1.0.0",
    analysisVersion: map.get("--analysis-version") ?? "phase4a",
    modelVersion: map.get("--model-version") ?? "video-mae-stub-v1",
    traceId: map.get("--trace-id") ?? crypto.randomUUID(),
    pollIntervalSeconds: Number.parseFloat(map.get("--poll-interval-seconds") ?? "1"),
    pollTimeoutSeconds: Number.parseFloat(map.get("--poll-timeout-seconds") ?? "30")
  };
}

interface UploadInput {
  filename: string;
  contentType: string;
  fileSizeBytes: number;
  body: Uint8Array;
}

async function resolveUploadInput(args: ParsedArgs): Promise<UploadInput> {
  if (!args.filePath) {
    return {
      filename: args.filename,
      contentType: args.contentType,
      fileSizeBytes: args.fileSizeBytes,
      body: new TextEncoder().encode("fake basketball clip")
    };
  }

  const resolvedPath = path.resolve(args.filePath);
  const [body, stats] = await Promise.all([readFile(resolvedPath), stat(resolvedPath)]);

  return {
    filename: path.basename(resolvedPath),
    contentType: args.contentType,
    fileSizeBytes: Number(stats.size),
    body
  };
}

function isTerminalStatus(status: string): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}

function summarizeClips(clips: Array<any>): FlowSummary["clips"] {
  return clips.map((clip, index) => ({
    clipId: String(clip.clipId ?? clip.id ?? `clip-${index + 1}`),
    finalLabel: String(clip.label ?? clip.finalLabel ?? clip.action ?? "unknown"),
    clipDurationSeconds: clip.clipDurationSeconds != null ? Number(clip.clipDurationSeconds) : null,
    wasMerged: Boolean(clip.wasMerged ?? false),
    sourceEventCount: clip.sourceEventCount != null ? Number(clip.sourceEventCount) : null
  }));
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
