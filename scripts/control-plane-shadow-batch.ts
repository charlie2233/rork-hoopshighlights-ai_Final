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
  jobId: string | null;
  requestId: string | null;
  uploadTraceId: string | null;
  inferenceAttemptId: string | null;
  finalStatus: string;
  clipCount: number;
  error: string | null;
}

interface ParsedArgs {
  baseUrl: string;
  outputDir: string;
  manifestPath: string;
  pollIntervalSeconds: number;
  pollTimeoutSeconds: number;
  fetchRetries: number;
  fetchRetryBaseMs: number;
  failFast: boolean;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const manifest = await loadManifest(args.manifestPath);
  await mkdir(args.outputDir, { recursive: true });

  const summaries: BatchResultSummary[] = [];
  for (const [index, item] of manifest.entries()) {
    const result = await runBatchItemSafely(args, item, index);
    summaries.push(result);
    if (args.failFast && result.finalStatus === "runner_failed") {
      break;
    }
  }

  const statusCounts = countBy(summaries.map((summary) => summary.finalStatus));
  console.log(
    JSON.stringify(
      {
        itemCount: summaries.length,
        completedCount: summaries.filter((summary) => summary.finalStatus === "completed").length,
        failedCount: summaries.filter((summary) => summary.finalStatus !== "completed").length,
        statusCounts,
        results: summaries
      },
      null,
      2
    )
  );
}

async function runBatchItemSafely(args: ParsedArgs, item: BatchManifestItem, index: number): Promise<BatchResultSummary> {
  try {
    return await runBatchItem(args, item, index);
  } catch (error) {
    const outputPath = failureOutputPath(args.outputDir, item.file, index);
    const failure = {
      status: "runner_failed",
      file: item.file,
      traceId: item.traceId ?? null,
      error: errorMessage(error),
      failedAt: new Date().toISOString()
    };
    await writeFile(outputPath, JSON.stringify(failure, null, 2), "utf-8");
    console.warn(
      JSON.stringify({
        event: "batch_item_failed",
        file: item.file,
        outputPath,
        error: errorMessage(error)
      })
    );
    return {
      file: item.file,
      outputPath,
      jobId: null,
      requestId: null,
      uploadTraceId: null,
      inferenceAttemptId: null,
      finalStatus: "runner_failed",
      clipCount: 0,
      error: errorMessage(error)
    };
  }
}

async function runBatchItem(args: ParsedArgs, item: BatchManifestItem, index: number): Promise<BatchResultSummary> {
  const upload = await resolveUploadInput(item.file, item.contentType ?? "video/mp4");
  const traceId = item.traceId ?? crypto.randomUUID();
  const createResponse = await fetchJson(
    `${args.baseUrl}/uploads/presign`,
    {
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
        analysisVersion: item.analysisVersion ?? "phase4a"
      }
    },
    args
  );

  const uploadResponse = await fetchWithRetries(createResponse.uploadUrl, {
    method: "PUT",
    headers: {
      "content-type": upload.contentType
    },
    body: upload.body
  }, args);
  if (!uploadResponse.ok) {
    throw new Error(`Upload failed: ${uploadResponse.status} ${uploadResponse.statusText} for ${upload.filename}`);
  }

  const finalizeResponse = await fetchJson(
    `${args.baseUrl}/jobs`,
    {
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
    },
    args
  );
  if (finalizeResponse.status !== "queued") {
    throw new Error(`Expected queued status after finalize, received ${finalizeResponse.status}.`);
  }

  const terminal = await pollHttpJob(`${args.baseUrl}/jobs/${createResponse.jobId}`, {
    ...args,
    traceId
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
    clipCount: clips.length,
    error: null
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
  args: ParsedArgs & { traceId: string }
): Promise<any> {
  const startedAt = Date.now();
  while (true) {
    const response = await fetchJson(url, {
      headers: {
        "x-trace-id": args.traceId
      }
    }, args);
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

async function fetchJson(
  url: string,
  init: { method?: string; headers?: Record<string, string>; body?: unknown } = {},
  retryArgs?: Pick<ParsedArgs, "fetchRetries" | "fetchRetryBaseMs">
): Promise<any> {
  const response = await fetchWithRetries(url, {
    method: init.method ?? "GET",
    headers: init.headers,
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined
  }, retryArgs);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText} for ${url}`);
  }
  return response.json();
}

async function fetchWithRetries(
  url: string,
  init: { method?: string; headers?: Record<string, string>; body?: BodyInit | null },
  retryArgs?: Pick<ParsedArgs, "fetchRetries" | "fetchRetryBaseMs">
): Promise<Response> {
  const maxRetries = Math.max(0, Number(retryArgs?.fetchRetries ?? 4));
  const baseDelayMs = Math.max(50, Number(retryArgs?.fetchRetryBaseMs ?? 500));
  let lastError: unknown = null;
  for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
    try {
      const response = await fetch(url, init);
      if (!isRetryableStatus(response.status) || attempt === maxRetries) {
        return response;
      }
      lastError = new Error(`Retryable HTTP ${response.status} ${response.statusText}`);
    } catch (error) {
      lastError = error;
      if (attempt === maxRetries) {
        break;
      }
    }
    const delayMs = retryDelayMs(baseDelayMs, attempt);
    console.warn(
      JSON.stringify({
        event: "fetch_retry",
        url: redactUrl(url),
        attempt: attempt + 1,
        maxRetries,
        delayMs,
        error: errorMessage(lastError)
      })
    );
    await sleep(delayMs);
  }
  throw new Error(`Request failed after ${maxRetries + 1} attempts for ${redactUrl(url)}: ${errorMessage(lastError)}`);
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
    pollTimeoutSeconds: Number.parseFloat(map.get("--poll-timeout-seconds") ?? "90"),
    fetchRetries: Number.parseInt(map.get("--fetch-retries") ?? "4", 10),
    fetchRetryBaseMs: Number.parseInt(map.get("--fetch-retry-base-ms") ?? "500", 10),
    failFast: map.get("--fail-fast") === "true"
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

function isRetryableStatus(status: number): boolean {
  return status === 408 || status === 425 || status === 429 || (status >= 500 && status <= 599);
}

function retryDelayMs(baseDelayMs: number, attempt: number): number {
  const exponential = baseDelayMs * 2 ** attempt;
  const jitter = Math.floor(Math.random() * Math.min(baseDelayMs, 250));
  return Math.min(exponential + jitter, 8000);
}

function failureOutputPath(outputDir: string, filePath: string, index: number): string {
  const basename = path.basename(filePath).replace(/\.[^.]+$/, "");
  return path.join(outputDir, `${String(index + 1).padStart(2, "0")}-${basename}.runner_failed.json`);
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function redactUrl(url: string): string {
  try {
    const parsed = new URL(url);
    parsed.search = parsed.search ? "?..." : "";
    return parsed.toString();
  } catch {
    return url.split("?")[0] ?? url;
  }
}

function countBy(values: string[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const value of values) {
    counts[value] = (counts[value] ?? 0) + 1;
  }
  return counts;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
