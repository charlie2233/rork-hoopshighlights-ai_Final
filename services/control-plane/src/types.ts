export type JobStatus =
  | "created"
  | "upload_pending"
  | "uploaded"
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "cancelled"
  | "succeeded"
  | "expired";

export interface ResponseEnvelope {
  requestId: string;
  schemaVersion?: string | null;
  confidence?: number | null;
  modelVersion?: string | null;
  failureReason?: string | null;
  uploadTraceId?: string | null;
  inferenceAttemptId?: string | null;
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
  sourceObjectKey?: string | null;
  resultObjectKey?: string | null;
  status?: JobStatus;
}

export interface StartCloudAnalysisJobRequest {
  installId: string;
}

export interface StartCloudAnalysisJobResponse extends ResponseEnvelope {
  jobId: string;
  status: JobStatus;
}

export interface UploadPresignRequest extends CreateCloudAnalysisJobRequest {}

export interface UploadPresignResponse extends ResponseEnvelope {
  jobId: string;
  sourceObjectKey: string;
  resultObjectKey: string;
  uploadUrl: string;
  uploadMethod: "PUT";
  uploadHeaders: Record<string, string>;
  expiresAt: string;
  status: JobStatus;
  analysisMode: "cloud";
}

export interface CreateCloudJobRequest {
  jobId?: string;
  installId: string;
  sourceObjectKey?: string;
  uploadObjectKey?: string;
  resultObjectKey?: string;
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
  sourceObjectKey?: string | null;
  resultObjectKey?: string | null;
  createdAt?: string | null;
  uploadPendingAt?: string | null;
  uploadedAt?: string | null;
  queuedAt?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  cancelledAt?: string | null;
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
  uploadTraceId: string;
  traceId: string;
  schemaVersion: string;
  sourceObjectKey: string;
  resultObjectKey: string;
  modelVersion?: string | null;
}

export interface DeadLetterQueueMessage {
  kind: "dead-letter-job";
  jobId: string;
  requestId: string;
  traceId: string;
  schemaVersion: string;
  sourceObjectKey: string;
  resultObjectKey: string;
  modelVersion?: string | null;
  failureReason: string;
  attempts?: number | null;
}

export interface InferenceCallbackPayload {
  jobId: string;
  status: "processing" | "completed" | "failed" | "cancelled" | "succeeded";
  progress?: number;
  stage?: string;
  modelVersion?: string | null;
  failureReason?: string | null;
  schemaVersion?: string | null;
  resultConfidence?: number | null;
  confidence?: number | null;
  results?: CloudAnalysisResult | null;
  traceId?: string | null;
  requestId?: string | null;
  uploadTraceId?: string | null;
  inferenceAttemptId?: string | null;
}

export interface JobRecord extends ResponseEnvelope {
  jobId: string;
  schemaVersion: string;
  traceId: string;
  uploadTraceId?: string | null;
  inferenceAttemptId?: string | null;
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
  createdAt: string;
  uploadPendingAt?: string | null;
  uploadedAt?: string | null;
  queuedAt?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  cancelledAt?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  sourceObjectKey: string;
  resultObjectKey: string;
  uploadUrl: string;
  uploadMethod: "PUT";
  uploadHeaders: Record<string, string>;
  expiresAt: string;
  updatedAt: string;
  resultConfidence?: number | null;
  results?: CloudAnalysisResult | null;
  reviewState?: string | null;
  reviewerNotes?: string | null;
  promotedToTrainingSet?: boolean;
  quotaRemainingToday?: number | null;
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

export interface InferenceDispatchRequest {
  jobId: string;
  requestId: string;
  uploadTraceId: string;
  inferenceAttemptId: string;
  traceId: string;
  sourceObjectKey: string;
  sourceUrl: string;
  resultObjectKey: string;
  callbackUrl: string;
  callbackSecret: string;
  schemaVersion: string;
  modelVersion: string;
  installId: string;
  appVersion: string;
  analysisVersion: string;
  requestedModel?: string | null;
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
