export type JobStatus = "created" | "queued" | "processing" | "succeeded" | "failed" | "expired" | "cancelled";

export interface ResponseEnvelope {
  requestId: string;
  modelVersion?: string | null;
  failureReason?: string | null;
}

export interface CreateCloudAnalysisJobRequest {
  filename: string;
  contentType: string;
  fileSizeBytes: number;
  durationSeconds: number;
  installId: string;
  appVersion: string;
  analysisVersion: string;
}

export interface CreateCloudAnalysisJobResponse extends ResponseEnvelope {
  jobId: string;
  uploadUrl: string;
  uploadMethod: "PUT";
  uploadHeaders: Record<string, string>;
  expiresAt: string;
  pollAfterSeconds: number;
  quotaRemainingToday: number;
  analysisMode: "cloud";
}

export interface StartCloudAnalysisJobRequest {
  installId: string;
}

export interface StartCloudAnalysisJobResponse extends ResponseEnvelope {
  jobId: string;
  status: JobStatus;
}

export interface CloudClip {
  startTime: number;
  endTime: number;
  confidence: number;
  label: string;
  action: string;
  audioScore: number;
  visualScore: number;
  motionScore: number;
  combinedScore: number;
  detectionMethod: "cloud" | "ml" | "heuristic";
  shouldAutoKeep: boolean;
  shouldEnableSlowMotion: boolean;
  eventType?: string | null;
  shotType?: string | null;
  makeMiss?: "make" | "miss" | "unknown" | null;
  rankScore?: number | null;
  reviewState?: string | null;
  reviewerNotes?: string | null;
}

export interface CloudDiagnostics {
  processingMs: number;
  backendModelVersion: string;
  usedVideoIntelligence: boolean;
  usedGeminiRelabeling: boolean;
  candidateSegments: number;
  finalSegments: number;
}

export interface CloudAnalysisResult extends ResponseEnvelope {
  clipCount: number;
  clips: CloudClip[];
  diagnostics: CloudDiagnostics;
  resultConfidence: number;
}

export interface CloudAnalysisJobResponse extends ResponseEnvelope {
  jobId: string;
  status: JobStatus;
  progress: number;
  stage: string;
  errorCode?: string | null;
  errorMessage?: string | null;
  analysisVersion: string;
  results?: CloudAnalysisResult | null;
}

export interface ErrorResponse extends ResponseEnvelope {
  errorCode: string;
  errorMessage: string;
  quotaRemainingToday?: number | null;
}

export interface QueueJobMessage {
  kind: "process-job";
  jobId: string;
  requestId: string;
  installId: string;
  analysisVersion: string;
  sourceObjectKey: string;
  resultObjectKey: string;
  callbackUrl: string;
}

export interface InferenceCallbackPayload {
  jobId: string;
  status: "processing" | "succeeded" | "failed";
  progress?: number;
  stage?: string;
  modelVersion?: string | null;
  failureReason?: string | null;
  resultConfidence?: number | null;
  results?: CloudAnalysisResult | null;
  traceId?: string | null;
  requestId?: string | null;
}

export interface JobRecord extends ResponseEnvelope {
  jobId: string;
  traceId: string;
  installId: string;
  filename: string;
  contentType: string;
  fileSizeBytes: number;
  durationSeconds: number;
  appVersion: string;
  analysisVersion: string;
  analysisMode: "cloud";
  status: JobStatus;
  stage: string;
  progress: number;
  errorCode?: string | null;
  errorMessage?: string | null;
  sourceObjectKey: string;
  resultObjectKey: string;
  uploadUrl: string;
  uploadMethod: "PUT";
  uploadHeaders: Record<string, string>;
  expiresAt: string;
  createdAt: string;
  queuedAt?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  updatedAt: string;
  resultConfidence?: number | null;
  results?: CloudAnalysisResult | null;
  reviewState?: string | null;
  reviewerNotes?: string | null;
  promotedToTrainingSet?: boolean;
  quotaRemainingToday?: number | null;
  modelVersion?: string | null;
  failureReason?: string | null;
}

export interface JobBootstrapInput {
  record: JobRecord;
}

export interface JobMutationInput {
  requestId?: string;
  traceId?: string;
  patch: Partial<JobRecord>;
  eventType?: string;
  message?: string;
  payload?: unknown;
}

export interface AdminJobListItem {
  jobId: string;
  status: string;
  stage: string;
  progress: number;
  installId: string;
  analysisVersion: string;
  modelVersion?: string | null;
  failureReason?: string | null;
  reviewState?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface AdminReviewUpdate {
  reviewState?: string;
  reviewerNotes?: string;
  promotedToTrainingSet?: boolean;
}

export interface ClipReviewUpdate {
  reviewState?: string;
  reviewerNotes?: string;
  promotedToTrainingSet?: boolean;
  label?: string;
  action?: string;
  jobId?: string;
  clipIndex?: number;
}

export interface MetadataGenerationRequest {
  prompt?: string;
  modelVersion?: string | null;
  sourceArtifacts?: string[];
}

export interface MetadataJobRecord extends ResponseEnvelope {
  metadataJobId: string;
  jobId: string;
  status: "queued" | "processing" | "succeeded" | "failed";
  prompt?: string | null;
  resultJson?: string | null;
  createdAt: string;
  updatedAt: string;
}
