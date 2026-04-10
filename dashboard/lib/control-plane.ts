import { getDashboardEnv, hasControlPlaneConfig, type DashboardEnv } from "@/lib/env";

export type JobStatus = "created" | "queued" | "processing" | "succeeded" | "failed" | "expired" | "cancelled";

export type DashboardClip = {
  clipId: string;
  startTime: number;
  endTime: number;
  label: string;
  action: string;
  confidence: number;
  eventType?: string | null;
  shotType?: string | null;
  makeMiss?: string | null;
  rankScore?: number | null;
  audioScore?: number | null;
  visualScore?: number | null;
  motionScore?: number | null;
  combinedScore?: number | null;
  reviewState?: string | null;
  reviewerNotes?: string | null;
  correctedLabel?: string | null;
  promoteToTrainingSet?: boolean | null;
  detectionMethod?: string | null;
};

export type DashboardAsset = {
  assetId: string;
  kind: string;
  label: string;
  url: string;
  contentType?: string | null;
  sizeBytes?: number | null;
};

export type DashboardJobSummary = {
  requestId?: string | null;
  jobId: string;
  status: JobStatus | string;
  stage: string;
  progress: number;
  createdAt?: string | null;
  updatedAt?: string | null;
  analysisVersion?: string | null;
  modelVersion?: string | null;
  failureReason?: string | null;
  confidence?: number | null;
  clipCount?: number | null;
  installId?: string | null;
  sourceFilename?: string | null;
};

export type DashboardJobDetail = DashboardJobSummary & {
  results?: {
    clipCount: number;
    clips: DashboardClip[];
    diagnostics?: {
      processingMs?: number | null;
      backendModelVersion?: string | null;
      modelVersion?: string | null;
      failureReason?: string | null;
      usedVideoIntelligence?: boolean | null;
      usedGeminiRelabeling?: boolean | null;
      candidateSegments?: number | null;
      finalSegments?: number | null;
    };
  } | null;
  assets?: DashboardAsset[];
  timeline?: Array<{
    at: string;
    status: string;
    stage: string;
    message?: string | null;
  }>;
};

export type DashboardJobsQuery = {
  status?: string;
  query?: string;
  limit?: number;
};

export type JobReviewPayload = {
  reviewState?: string;
  summary?: string;
  notes?: string;
  failureReason?: string;
  modelVersion?: string;
};

export type ClipReviewPayload = {
  reviewState?: string;
  notes?: string;
  correctedLabel?: string;
  promoteToTrainingSet?: boolean;
  eventType?: string;
  shotType?: string;
  makeMiss?: string;
};

export type MetadataRequestPayload = {
  titleHint?: string;
  summaryHint?: string;
  source?: string;
};

export class ControlPlaneError extends Error {
  readonly status: number;
  readonly requestId: string | null;

  constructor(message: string, status = 500, requestId: string | null = null) {
    super(message);
    this.name = "ControlPlaneError";
    this.status = status;
    this.requestId = requestId;
  }
}

function makeRequestId(): string {
  return crypto.randomUUID();
}

function createUrl(env: DashboardEnv, path: string, query?: Record<string, string | number | undefined>) {
  if (!env.controlPlaneBaseUrl) {
    throw new ControlPlaneError("Control plane base URL is not configured.");
  }

  const url = new URL(path, env.controlPlaneBaseUrl.endsWith("/") ? env.controlPlaneBaseUrl : `${env.controlPlaneBaseUrl}/`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === "") continue;
      url.searchParams.set(key, String(value));
    }
  }

  return url;
}

async function readErrorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      const payload = (await response.json()) as { errorMessage?: string; message?: string };
      return payload.errorMessage ?? payload.message ?? `Request failed with status ${response.status}.`;
    } catch {
      return `Request failed with status ${response.status}.`;
    }
  }

  const text = await response.text().catch(() => "");
  return text.trim() || `Request failed with status ${response.status}.`;
}

export class ControlPlaneClient {
  constructor(private readonly env: DashboardEnv = getDashboardEnv()) {}

  get isConfigured(): boolean {
    return hasControlPlaneConfig(this.env);
  }

  private buildHeaders(extra?: HeadersInit, requestId = makeRequestId()): Headers {
    if (!this.env.controlPlaneServiceToken) {
      throw new ControlPlaneError("Control plane service token is not configured.");
    }

    const headers = new Headers(extra);
    headers.set("authorization", `Bearer ${this.env.controlPlaneServiceToken}`);
    headers.set("accept", "application/json");
    headers.set("x-request-id", requestId);
    return headers;
  }

  private async request<T>(path: string, init?: RequestInit, query?: Record<string, string | number | undefined>): Promise<T> {
    const requestId = makeRequestId();
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.env.requestTimeoutMs);

    try {
      const response = await fetch(createUrl(this.env, path, query), {
        ...init,
        signal: controller.signal,
        headers: this.buildHeaders(init?.headers, requestId)
      });

      if (!response.ok) {
        throw new ControlPlaneError(await readErrorMessage(response), response.status, requestId);
      }

      if (response.status === 204) {
        return undefined as T;
      }

      return (await response.json()) as T;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new ControlPlaneError("Control plane request timed out.", 504, requestId);
      }
      if (error instanceof ControlPlaneError) {
        throw error;
      }
      throw new ControlPlaneError(error instanceof Error ? error.message : "Unexpected control plane error.", 500, requestId);
    } finally {
      clearTimeout(timeout);
    }
  }

  async listJobs(query: DashboardJobsQuery = {}): Promise<DashboardJobSummary[]> {
    return this.request<DashboardJobSummary[]>("/v1/admin/jobs", undefined, {
      status: query.status,
      query: query.query,
      limit: query.limit ?? 12
    });
  }

  async getJob(jobId: string): Promise<DashboardJobDetail> {
    return this.request<DashboardJobDetail>(`/v1/admin/jobs/${encodeURIComponent(jobId)}`);
  }

  async getJobAssets(jobId: string): Promise<DashboardAsset[]> {
    return this.request<DashboardAsset[]>(`/v1/admin/jobs/${encodeURIComponent(jobId)}/assets`);
  }

  async reviewJob(jobId: string, payload: JobReviewPayload): Promise<DashboardJobDetail> {
    return this.request<DashboardJobDetail>(`/v1/admin/jobs/${encodeURIComponent(jobId)}/review`, {
      method: "PATCH",
      body: JSON.stringify(payload),
      headers: {
        "content-type": "application/json"
      }
    });
  }

  async reviewClip(clipId: string, payload: ClipReviewPayload): Promise<DashboardClip> {
    return this.request<DashboardClip>(`/v1/admin/clips/${encodeURIComponent(clipId)}/review`, {
      method: "PATCH",
      body: JSON.stringify(payload),
      headers: {
        "content-type": "application/json"
      }
    });
  }

  async requestMetadata(jobId: string, payload: MetadataRequestPayload): Promise<{ jobId: string; status: string; requestId?: string | null }> {
    return this.request<{ jobId: string; status: string; requestId?: string | null }>(
      `/v1/admin/jobs/${encodeURIComponent(jobId)}/metadata`,
      {
        method: "POST",
        body: JSON.stringify(payload),
        headers: {
          "content-type": "application/json"
        }
      }
    );
  }
}

export function getControlPlaneClient() {
  return new ControlPlaneClient();
}
