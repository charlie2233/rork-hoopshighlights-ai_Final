import type { ExecutionContext } from "@cloudflare/workers-types";
import { redactJobEventPayload } from "../services/control-plane/src/db/index.ts";
import type { Env } from "../services/control-plane/src/env.ts";
import type {
  CloudAnalysisResult,
  CloudClip,
  DeadLetterQueueMessage,
  InferenceCallbackPayload,
  JobRecord,
  QueueJobMessage,
} from "../services/control-plane/src/types.ts";

export interface HarnessState {
  jobs: Map<string, JobRecord>;
  events: HarnessEvent[];
  uploads: Map<string, Uint8Array>;
  queueMessages: QueueJobMessage[];
  deadLetterMessages: DeadLetterQueueMessage[];
  callbackRequests: HarnessCallbackRequest[];
  inferenceDispatches: HarnessInferenceDispatch[];
}

export interface HarnessEvent {
  jobId: string;
  requestId: string;
  traceId: string;
  eventType: string;
  message: string;
  payload: unknown;
  createdAt: string;
}

export interface HarnessCallbackRequest {
  jobId: string;
  requestId: string;
  traceId: string;
}

export interface HarnessInferenceDispatch {
  jobId: string;
  requestId: string;
  uploadTraceId: string;
  inferenceAttemptId: string;
  traceId: string;
  jobStatus: string | undefined;
  url: string;
  headers: Record<string, string>;
  body: Record<string, unknown>;
}

export interface ControlPlaneHarness {
  env: Env;
  state: HarnessState;
  ctx: ExecutionContext;
  flush(): Promise<void>;
  drainQueue(): Promise<number>;
  request(path: string, init?: RequestInit): Request;
}

interface RouteModules {
  routePublicRequest: typeof import("../services/control-plane/src/routes/public.ts").routePublicRequest;
  routeInternalRequest: typeof import("../services/control-plane/src/routes/internal.ts").routeInternalRequest;
  handleQueueBatch: typeof import("../services/control-plane/src/queue/consumer.ts").handleQueueBatch;
}

const BASE_URL = "http://control-plane.local";
const INTERNAL_SECRET = "local-control-plane-secret";
const ADMIN_TOKEN = "local-admin-token";
let routeModulesPromise: Promise<RouteModules> | null = null;

export function createControlPlaneHarness(
  overrides: Partial<Env> = {},
): ControlPlaneHarness {
  const state: HarnessState = {
    jobs: new Map(),
    events: [],
    uploads: new Map(),
    queueMessages: [],
    deadLetterMessages: [],
    callbackRequests: [],
    inferenceDispatches: [],
  };
  const pending: Promise<unknown>[] = [];

  const env = {
    APP_ENV: "local",
    DEFAULT_POLL_AFTER_SECONDS: "2",
    SIGNED_UPLOAD_TTL_SECONDS: "900",
    JOB_TTL_SECONDS: "3600",
    PROCESSING_TIMEOUT_SECONDS: "300",
    SELECTED_TEAM_PROCESSING_TIMEOUT_SECONDS: "1800",
    MAX_INFERENCE_ATTEMPTS: "3",
    MAX_FILE_SIZE_BYTES: "524288000",
    MAX_DURATION_SECONDS: "1800",
    CONTROL_PLANE_BASE_URL: BASE_URL,
    ADMIN_API_TOKEN: ADMIN_TOKEN,
    CONTROL_PLANE_SHARED_SECRET: INTERNAL_SECRET,
    INFERENCE_BASE_URL: "http://inference.local",
    INFERENCE_SHARED_SECRET: "inference-secret",
    EDITING_BASE_URL: "http://editing.local",
    EDITING_SHARED_SECRET: "editing-secret",
    R2_ACCOUNT_ID: "",
    R2_UPLOAD_BUCKET_NAME: "hoopsclips-uploads",
    R2_RESULT_BUCKET_NAME: "hoopsclips-results",
    R2_ACCESS_KEY_ID: "",
    R2_SECRET_ACCESS_KEY: "",
    DB: createMockDb(state),
    JOB_STATE: createMockJobStateNamespace(state),
    ANALYSIS_QUEUE: createMockQueue(state),
    ANALYSIS_DLQ: createMockDeadLetterQueue(state),
    R2_UPLOADS: createMockBucket(state.uploads),
    R2_RESULTS: createMockBucket(new Map()),
    ...overrides,
  } as Env;

  const ctx: ExecutionContext = {
    waitUntil(promise: Promise<unknown>): void {
      pending.push(promise);
    },
    passThroughOnException(): void {
      return;
    },
  } as ExecutionContext;

  return {
    env,
    state,
    ctx,
    async flush(): Promise<void> {
      while (pending.length > 0) {
        await Promise.allSettled(pending.splice(0, pending.length));
      }
    },
    async drainQueue(): Promise<number> {
      const { handleQueueBatch, routeInternalRequest } = await loadRoutes();
      const queued = state.queueMessages.splice(0, state.queueMessages.length);
      if (queued.length === 0) {
        return 0;
      }

      const originalFetch = globalThis.fetch.bind(globalThis);
      globalThis.fetch = async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const request =
          input instanceof Request ? input : new Request(input, init);
        const url = new URL(request.url);
        if (url.origin === BASE_URL) {
          const requestId =
            request.headers.get("x-request-id")?.trim() || crypto.randomUUID();
          const callbackMatch = url.pathname.match(
            /^\/internal\/inference\/callback(?:\/([^/]+))?$/,
          );
          if (callbackMatch) {
            state.callbackRequests.push({
              jobId: callbackMatch[1] ?? "unknown",
              requestId,
              traceId: request.headers.get("x-trace-id")?.trim() || "",
            });
          }
          const internalResponse = await routeInternalRequest(
            request,
            env,
            requestId,
          );
          if (!internalResponse) {
            return new Response("Not found", { status: 404 });
          }
          return internalResponse;
        }
        if (url.origin === env.INFERENCE_BASE_URL) {
          const body = (await request.json()) as Record<string, unknown>;
          const requestId = String(
            body.requestId ??
              request.headers.get("x-request-id") ??
              crypto.randomUUID(),
          );
          const uploadTraceId = String(
            body.uploadTraceId ??
              request.headers.get("x-hoops-upload-trace-id") ??
              "",
          );
          const inferenceAttemptId = String(
            body.inferenceAttemptId ??
              request.headers.get("x-hoops-inference-attempt-id") ??
              "",
          );
          const traceId = String(
            body.traceId ?? request.headers.get("x-trace-id") ?? "",
          );

          state.inferenceDispatches.push({
            jobId: String(body.jobId ?? "unknown"),
            requestId,
            uploadTraceId,
            inferenceAttemptId,
            traceId,
            jobStatus: state.jobs.get(String(body.jobId ?? "unknown"))?.status,
            url: url.toString(),
            headers: Object.fromEntries(request.headers.entries()),
            body,
          });

          if (
            env.APP_ENV === "staging" &&
            (body.teamSelection as { mode?: string } | undefined)?.mode ===
              "team"
          ) {
            return Response.json(
              {
                requestId,
                errorCode: "unsupported_team_selection",
                errorMessage:
                  "Legacy inference does not accept selected-team dispatch.",
              },
              { status: 422 },
            );
          }

          const callbackPayload = buildSuccessCallbackPayload({
            jobId: String(body.jobId ?? "unknown"),
            requestId,
            modelVersion: String(body.modelVersion ?? "external-videomae-v1"),
            resultConfidence: 0.91,
            attemptCount:
              typeof body.attemptCount === "number"
                ? body.attemptCount
                : undefined,
          }) as InferenceCallbackPayload & {
            uploadTraceId?: string;
            inferenceAttemptId?: string;
          };
          callbackPayload.uploadTraceId = uploadTraceId;
          callbackPayload.inferenceAttemptId = inferenceAttemptId;

          if (typeof body.callbackUrl === "string") {
            const callbackOrigin = new URL(body.callbackUrl).origin;
            if (callbackOrigin !== BASE_URL) {
              return Response.json(
                { error: "callback_unreachable" },
                { status: 502 },
              );
            }

            const callbackRequest = new Request(body.callbackUrl, {
              method: "POST",
              headers: {
                "content-type": "application/json",
                "x-hoops-inference-secret": String(body.callbackSecret ?? ""),
                "x-request-id": requestId,
                "x-trace-id": traceId,
                "x-hoops-upload-trace-id": uploadTraceId,
                "x-hoops-inference-attempt-id": inferenceAttemptId,
              },
              body: JSON.stringify(callbackPayload),
            });
            const callbackResponse = await routeInternalRequest(
              callbackRequest,
              env,
              requestId,
            );
            if (!callbackResponse || !callbackResponse.ok) {
              return Response.json(
                {
                  error: "callback_failed",
                  status: callbackResponse?.status ?? 500,
                },
                { status: 502 },
              );
            }
          }

          return Response.json(
            {
              jobId: String(body.jobId ?? "unknown"),
              requestId,
              uploadTraceId,
              inferenceAttemptId,
              modelVersion: String(body.modelVersion ?? "external-videomae-v1"),
              accepted: true,
            },
            { status: 202 },
          );
        }
        return originalFetch(input, init);
      };

      try {
        await handleQueueBatch(
          {
            messages: queued.map((body, index) => ({
              id: `${body.jobId}-${index}`,
              timestamp: new Date(),
              attempts: 1,
              body,
              ack() {
                return;
              },
              retry() {
                return;
              },
            })),
            queue: "hoopsclips-analysis",
            retryAll() {
              return;
            },
            ackAll() {
              return;
            },
          } as never,
          env,
        );
        await this.flush();
      } finally {
        globalThis.fetch = originalFetch;
      }

      return queued.length;
    },
    request(path: string, init: RequestInit = {}): Request {
      return buildRequest(path, init);
    },
  };
}

export async function invokePublicRoute(
  harness: ControlPlaneHarness,
  method: string,
  path: string,
  body?: unknown,
  headers: HeadersInit = {},
  requestId = crypto.randomUUID(),
): Promise<Response> {
  const { routePublicRequest } = await loadRoutes();
  const request = buildRequest(path, { method, body, headers });
  const response = await routePublicRequest(
    request,
    harness.env,
    harness.ctx,
    requestId,
  );
  await harness.flush();
  if (!response) {
    throw new Error(`No public route matched ${method} ${path}`);
  }
  return response;
}

export async function invokeInternalRoute(
  harness: ControlPlaneHarness,
  method: string,
  path: string,
  body?: unknown,
  headers: HeadersInit = {},
  requestId = crypto.randomUUID(),
): Promise<Response> {
  const { routeInternalRequest } = await loadRoutes();
  const request = buildRequest(path, { method, body, headers });
  const response = await routeInternalRequest(request, harness.env, requestId);
  await harness.flush();
  if (!response) {
    throw new Error(`No internal route matched ${method} ${path}`);
  }
  return response;
}

async function loadRoutes(): Promise<RouteModules> {
  if (!routeModulesPromise) {
    routeModulesPromise = Promise.all([
      import(
        new URL(
          "../services/control-plane/src/routes/public.ts",
          import.meta.url,
        ).href
      ),
      import(
        new URL(
          "../services/control-plane/src/routes/internal.ts",
          import.meta.url,
        ).href
      ),
      import(
        new URL(
          "../services/control-plane/src/queue/consumer.ts",
          import.meta.url,
        ).href
      ),
    ]).then(([publicModule, internalModule, queueModule]) => ({
      routePublicRequest: publicModule.routePublicRequest,
      routeInternalRequest: internalModule.routeInternalRequest,
      handleQueueBatch: queueModule.handleQueueBatch,
    }));
  }
  return routeModulesPromise;
}

export function parseJsonResponse<T>(response: Response): Promise<T> {
  return response.json() as Promise<T>;
}

export function uploadObject(
  harness: ControlPlaneHarness,
  uploadUrl: string,
  body: BodyInit,
): Promise<void> {
  const key = extractObjectKey(uploadUrl);
  return harness.env.R2_UPLOADS.put(key, body);
}

export function extractObjectKey(uploadUrl: string): string {
  if (!uploadUrl.includes("://")) {
    return uploadUrl.replace(/^\/+/, "");
  }
  try {
    const url = new URL(uploadUrl);
    const segments = url.pathname.split("/").filter(Boolean);
    return segments.slice(1).join("/");
  } catch {
    return uploadUrl
      .replace(/^https?:\/\/[^/]+\//, "")
      .replace(/^[^/]+\//, "")
      .replace(/^\/+/, "");
  }
}

export function buildSuccessCallbackPayload(params: {
  jobId: string;
  requestId: string;
  modelVersion: string;
  resultConfidence?: number;
  failureReason?: string | null;
  uploadTraceId?: string | null;
  inferenceAttemptId?: string | null;
  attemptCount?: number | null;
}): InferenceCallbackPayload {
  return {
    jobId: params.jobId,
    requestId: params.requestId,
    status: "succeeded",
    stage: "Finalizing clips",
    progress: 0.98,
    modelVersion: params.modelVersion,
    failureReason: params.failureReason ?? null,
    resultConfidence: params.resultConfidence ?? 0.91,
    attemptCount: params.attemptCount ?? null,
    uploadTraceId: params.uploadTraceId ?? null,
    inferenceAttemptId: params.inferenceAttemptId ?? null,
    results: buildSampleResult(
      params.jobId,
      params.requestId,
      params.modelVersion,
      params.resultConfidence ?? 0.91,
    ),
  };
}

export function buildFailureCallbackPayload(params: {
  jobId: string;
  requestId: string;
  failureReason: string;
  modelVersion?: string | null;
  uploadTraceId?: string | null;
  inferenceAttemptId?: string | null;
  attemptCount?: number | null;
}): InferenceCallbackPayload {
  return {
    jobId: params.jobId,
    requestId: params.requestId,
    status: "failed",
    stage: "Inference failed",
    progress: 0.77,
    modelVersion: params.modelVersion ?? "stub-inference-v1",
    failureReason: params.failureReason,
    attemptCount: params.attemptCount ?? null,
    uploadTraceId: params.uploadTraceId ?? null,
    inferenceAttemptId: params.inferenceAttemptId ?? null,
    resultConfidence: 0,
    results: null,
  };
}

export function buildHeartbeatPayload(
  stage = "Inference running",
  progress = 0.55,
): { stage: string; progress: number } {
  return { stage, progress };
}

export function buildSampleResult(
  jobId: string,
  requestId: string,
  modelVersion: string,
  resultConfidence = 0.91,
): CloudAnalysisResult {
  const clip: CloudClip = {
    startTime: 12.4,
    endTime: 18.2,
    confidence: 0.94,
    label: "made_shot",
    action: "made_shot",
    audioScore: 0.12,
    visualScore: 0.89,
    motionScore: 0.74,
    combinedScore: 0.88,
    detectionMethod: "ml",
    shouldAutoKeep: true,
    shouldEnableSlowMotion: false,
    eventType: "shot",
    shotType: "jump_shot",
    makeMiss: "make",
    rankScore: 0.97,
    reviewState: "unreviewed",
    reviewerNotes: null,
  };

  return {
    requestId,
    jobId,
    modelVersion,
    failureReason: null,
    clipCount: 1,
    clips: [clip],
    diagnostics: {
      processingMs: 1250,
      backendModelVersion: modelVersion,
      usedVideoIntelligence: false,
      usedGeminiRelabeling: false,
      candidateSegments: 1,
      finalSegments: 1,
    },
    resultConfidence,
  };
}

function createMockQueue(state: HarnessState): Env["ANALYSIS_QUEUE"] {
  return {
    async send(message: QueueJobMessage): Promise<void> {
      state.queueMessages.push(message);
    },
  } as Env["ANALYSIS_QUEUE"];
}

function createMockDeadLetterQueue(state: HarnessState): Env["ANALYSIS_DLQ"] {
  return {
    async send(message: DeadLetterQueueMessage): Promise<void> {
      state.deadLetterMessages.push(message);
    },
  } as Env["ANALYSIS_DLQ"];
}

function createMockBucket(store: Map<string, Uint8Array>): R2Bucket {
  return {
    async get(key: string): Promise<R2ObjectBody | null> {
      const bytes = store.get(key);
      if (!bytes) {
        return null;
      }
      const text = new TextDecoder().decode(bytes);
      return {
        key,
        text: async () => text,
      } as R2ObjectBody;
    },
    async head(key: string): Promise<R2ObjectBody | null> {
      if (!store.has(key)) {
        return null;
      }
      return { key } as R2ObjectBody;
    },
    async delete(key: string): Promise<void> {
      store.delete(key);
    },
    async put(key: string, value: BodyInit): Promise<R2ObjectBody> {
      store.set(key, await toBytes(value));
      return { key } as R2ObjectBody;
    },
  } as R2Bucket;
}

function createMockDb(state: HarnessState): Env["DB"] {
  return {
    prepare(sql: string) {
      return {
        bind(...values: unknown[]) {
          return {
            async run() {
              if (sql.includes("INSERT INTO job_events")) {
                const payloadJson = values[5];
                state.events.push({
                  jobId: String(values[0]),
                  requestId: String(values[1]),
                  traceId: String(values[2]),
                  eventType: String(values[3]),
                  message: String(values[4]),
                  payload: payloadJson ? JSON.parse(String(payloadJson)) : null,
                  createdAt: String(values[6]),
                });
              }
              return { success: true } as const;
            },
          };
        },
      };
    },
  } as Env["DB"];
}

function createMockJobStateNamespace(state: HarnessState): Env["JOB_STATE"] {
  return {
    idFromName(name: string) {
      return {
        name,
        toString: () => name,
        equals: (other: { toString: () => string }) =>
          other.toString() === name,
      } as never;
    },
    get(id: { name?: string; toString(): string }) {
      const jobId = id.name ?? id.toString();
      return {
        async fetch(
          input: RequestInfo | URL,
          init?: RequestInit,
        ): Promise<Response> {
          const request = new Request(input, init);
          const url = new URL(request.url);
          if (request.method === "POST" && url.pathname === "/bootstrap") {
            const body = (await request.json()) as { record: JobRecord };
            if (!state.jobs.has(body.record.jobId)) {
              state.jobs.set(body.record.jobId, body.record);
              state.events.push({
                jobId: body.record.jobId,
                requestId: body.record.requestId,
                traceId: body.record.traceId,
                eventType: "job.bootstrap",
                message: "Job bootstrap recorded in Durable Object.",
                payload: redactJobEventPayload(body.record),
                createdAt: body.record.createdAt,
              });
            }
            return Response.json(
              state.jobs.get(body.record.jobId) ?? body.record,
              { status: 201 },
            );
          }

          if (request.method === "GET" && url.pathname === "/snapshot") {
            const job = state.jobs.get(jobId);
            if (!job) {
              return Response.json(
                {
                  requestId: crypto.randomUUID(),
                  errorCode: "job_not_found",
                  errorMessage: "Job not found.",
                },
                { status: 404 },
              );
            }
            return Response.json(job, { status: 200 });
          }

          if (request.method === "PATCH" && url.pathname === "/patch") {
            const body = (await request.json()) as {
              patch: Partial<JobRecord>;
              requestId?: string;
              traceId?: string;
              eventType?: string;
              message?: string;
              payload?: unknown;
            };
            const job = state.jobs.get(jobId);
            if (!job) {
              return Response.json(
                {
                  requestId: crypto.randomUUID(),
                  errorCode: "job_not_found",
                  errorMessage: "Job not found.",
                },
                { status: 404 },
              );
            }
            const updated: JobRecord = {
              ...job,
              ...body.patch,
              updatedAt: body.patch.updatedAt ?? new Date().toISOString(),
            };
            state.jobs.set(jobId, updated);
            state.events.push({
              jobId,
              requestId: body.requestId ?? job.requestId,
              traceId: body.traceId ?? job.traceId,
              eventType: body.eventType ?? "job.patch",
              message: body.message ?? "Job state updated.",
              payload: redactJobEventPayload(body.payload ?? body.patch),
              createdAt: updated.updatedAt,
            });
            return Response.json(updated, { status: 200 });
          }

          if (request.method === "DELETE" && url.pathname === "/delete") {
            const job = state.jobs.get(jobId);
            if (!job) {
              return Response.json(
                {
                  requestId: crypto.randomUUID(),
                  errorCode: "job_not_found",
                  errorMessage: "Job not found.",
                },
                { status: 404 },
              );
            }
            const updated: JobRecord = {
              ...job,
              status: "expired",
              failureReason: "Job deleted by caller.",
              finishedAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            };
            state.jobs.set(jobId, updated);
            state.events.push({
              jobId,
              requestId: job.requestId,
              traceId: job.traceId,
              eventType: "job.deleted",
              message: "Job deleted by caller.",
              payload: null,
              createdAt: updated.updatedAt,
            });
            return Response.json(updated, { status: 200 });
          }

          return Response.json(
            {
              requestId: crypto.randomUUID(),
              errorCode: "not_found",
              errorMessage: "Unknown Durable Object action.",
            },
            { status: 404 },
          );
        },
      };
    },
  } as Env["JOB_STATE"];
}

function buildRequest(path: string, init: RequestInit = {}): Request {
  const url = new URL(path, BASE_URL).toString();
  const headers = new Headers(init.headers ?? {});
  let body = init.body;

  if (
    body &&
    !(body instanceof FormData) &&
    !(body instanceof Blob) &&
    typeof body !== "string"
  ) {
    headers.set("content-type", "application/json");
    body = JSON.stringify(body);
  }

  return new Request(url, {
    ...init,
    headers,
    body,
  });
}

async function toBytes(body: BodyInit): Promise<Uint8Array> {
  if (typeof body === "string") {
    return new TextEncoder().encode(body);
  }
  if (body instanceof Uint8Array) {
    return body;
  }
  if (body instanceof ArrayBuffer) {
    return new Uint8Array(body);
  }
  if (body instanceof Blob) {
    return new Uint8Array(await body.arrayBuffer());
  }
  return new TextEncoder().encode(String(body));
}

export default {
  createControlPlaneHarness,
  invokePublicRoute,
  invokeInternalRoute,
  parseJsonResponse,
  uploadObject,
  extractObjectKey,
  drainQueue: (harness: ControlPlaneHarness) => harness.drainQueue(),
  buildSuccessCallbackPayload,
  buildFailureCallbackPayload,
  buildHeartbeatPayload,
  buildSampleResult,
};
