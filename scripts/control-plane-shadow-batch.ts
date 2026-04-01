import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";

interface BatchManifestItem {
  file: string;
  traceId?: string;
  installId?: string;
  appVersion?: string;
  analysisVersion?: string;
  durationSeconds?: number;
  contentType?: string;
  expectedLabel?: string;
  expectedEventFamily?: string;
  expectedOutcome?: string;
  expectedShotSubtype?: string | null;
  sourceDomain?: string;
}

interface BatchResultSummary {
  file: string;
  outputPath: string;
  jobId: string;
  requestId: string | null;
  uploadTraceId: string | null;
  inferenceAttemptId: string | null;
  finalStatus: string;
  clipCount: number;
}

interface ParsedArgs {
  baseUrl: string;
  outputDir: string;
  manifestPath: string;
  pollIntervalSeconds: number;
  pollTimeoutSeconds: number;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const manifest = await loadManifest(args.manifestPath);
  await mkdir(args.outputDir, { recursive: true });

  const summaries: BatchResultSummary[] = [];
  for (const [index, item] of manifest.entries()) {
    const result = await runBatchItem(args, item, index);
    summaries.push(result);
  }

  console.log(
    JSON.stringify(
      {
        itemCount: summaries.length,
        results: summaries
      },
      null,
      2
    )
  );
}

async function runBatchItem(args: ParsedArgs, item: BatchManifestItem, index: number): Promise<BatchResultSummary> {
  const upload = await resolveUploadInput(item.file, item.contentType ?? "video/mp4");
  const traceId = item.traceId ?? crypto.randomUUID();
  const createResponse = await fetchJson(`${args.baseUrl}/uploads/presign`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-trace-id": traceId
    },
    body: {
      filename: upload.filename,
      contentType: upload.contentType,
      fileSizeBytes: upload.fileSizeBytes,
      durationSeconds: item.durationSeconds ?? 24,
      installId: item.installId ?? "install-local-001",
      appVersion: item.appVersion ?? "1.0.0",
      analysisVersion: item.analysisVersion ?? "phase4"
    }
  });

  await fetch(createResponse.uploadUrl, {
    method: "PUT",
    headers: {
      "content-type": upload.contentType
    },
    body: upload.body
  });

  const finalizeResponse = await fetchJson(`${args.baseUrl}/jobs`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-trace-id": traceId
    },
    body: {
      jobId: createResponse.jobId,
      installId: item.installId ?? "install-local-001",
      sourceObjectKey: createResponse.sourceObjectKey
    }
  });
  if (finalizeResponse.status !== "queued") {
    throw new Error(`Expected queued status after finalize, received ${finalizeResponse.status}.`);
  }

  const terminal = await pollHttpJob(`${args.baseUrl}/jobs/${createResponse.jobId}`, {
    traceId,
    pollIntervalSeconds: args.pollIntervalSeconds,
    pollTimeoutSeconds: args.pollTimeoutSeconds
  });
  annotateExpectedLabels(terminal, item);

  const basename = path.basename(item.file).replace(/\.[^.]+$/, "");
  const outputPath = path.join(args.outputDir, `${String(index + 1).padStart(2, "0")}-${basename}.json`);
  await writeFile(outputPath, JSON.stringify(terminal, null, 2), "utf-8");

  const clips = extractClips(terminal);
  return {
    file: item.file,
    outputPath,
    jobId: String(terminal.jobId ?? createResponse.jobId),
    requestId: firstString(terminal.requestId, terminal.results?.requestId, finalizeResponse.requestId, createResponse.requestId),
    uploadTraceId: firstString(terminal.uploadTraceId, terminal.results?.uploadTraceId),
    inferenceAttemptId: firstString(terminal.inferenceAttemptId, terminal.results?.inferenceAttemptId),
    finalStatus: String(terminal.status ?? "unknown"),
    clipCount: clips.length
  };
}

function annotateExpectedLabels(payload: any, item: BatchManifestItem): void {
  const clips = extractClips(payload);
  for (const clip of clips) {
    if (item.expectedLabel) {
      clip.expectedLabel = item.expectedLabel;
    }
    if (item.expectedEventFamily) {
      clip.expectedEventFamily = item.expectedEventFamily;
    }
    if (item.expectedOutcome) {
      clip.expectedOutcome = item.expectedOutcome;
    }
    if (item.expectedShotSubtype !== undefined) {
      clip.expectedShotSubtype = item.expectedShotSubtype;
    }
    if (item.sourceDomain) {
      clip.sourceDomain = item.sourceDomain;
    }
  }
}

function extractClips(payload: any): Array<Record<string, unknown>> {
  if (Array.isArray(payload?.clips)) {
    return payload.clips as Array<Record<string, unknown>>;
  }
  if (Array.isArray(payload?.results?.clips)) {
    return payload.results.clips as Array<Record<string, unknown>>;
  }
  return [];
}

async function loadManifest(manifestPath: string): Promise<BatchManifestItem[]> {
  const resolvedPath = path.resolve(manifestPath);
  const payload = JSON.parse(await readFile(resolvedPath, "utf-8"));
  if (!Array.isArray(payload) || payload.some((item) => !item || typeof item !== "object" || typeof item.file !== "string")) {
    throw new Error("Manifest must be a JSON array of objects with a string 'file' field.");
  }
  return payload as BatchManifestItem[];
}

async function resolveUploadInput(filePath: string, contentType: string): Promise<{
  filename: string;
  contentType: string;
  fileSizeBytes: number;
  body: Uint8Array;
}> {
  const resolvedPath = path.resolve(filePath);
  const [body, stats] = await Promise.all([readFile(resolvedPath), stat(resolvedPath)]);
  return {
    filename: path.basename(resolvedPath),
    contentType,
    fileSizeBytes: Number(stats.size),
    body
  };
}

async function pollHttpJob(
  url: string,
  args: { traceId: string; pollIntervalSeconds: number; pollTimeoutSeconds: number }
): Promise<any> {
  const startedAt = Date.now();
  while (true) {
    const response = await fetchJson(url, {
      headers: {
        "x-trace-id": args.traceId
      }
    });
    if (isTerminalStatus(String(response.status ?? ""))) {
      return response;
    }
    if (Date.now() - startedAt > args.pollTimeoutSeconds * 1000) {
      throw new Error(`Timed out waiting for terminal job status for ${url}.`);
    }
    const delaySeconds = Number(response.pollAfterSeconds ?? args.pollIntervalSeconds);
    await sleep(Math.max(delaySeconds, 0.2) * 1000);
  }
}

async function fetchJson(url: string, init: { method?: string; headers?: Record<string, string>; body?: unknown } = {}): Promise<any> {
  const response = await fetch(url, {
    method: init.method ?? "GET",
    headers: init.headers,
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText} for ${url}`);
  }
  return response.json();
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

  const baseUrl = map.get("--base-url");
  const outputDir = map.get("--output-dir");
  const manifestPath = map.get("--manifest");
  if (!baseUrl || !outputDir || !manifestPath) {
    throw new Error("--base-url, --output-dir, and --manifest are required.");
  }

  return {
    baseUrl,
    outputDir,
    manifestPath,
    pollIntervalSeconds: Number.parseFloat(map.get("--poll-interval-seconds") ?? "1"),
    pollTimeoutSeconds: Number.parseFloat(map.get("--poll-timeout-seconds") ?? "90")
  };
}

function firstString(...values: Array<unknown>): string | null {
  for (const value of values) {
    if (typeof value === "string" && value.length > 0) {
      return value;
    }
  }
  return null;
}

function isTerminalStatus(status: string): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
