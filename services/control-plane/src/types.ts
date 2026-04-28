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

export interface CloudLabelScore {
  label: string;
  confidence: number;
  rawLabel?: string | null;
  modelVersion?: string | null;
}

export interface CloudRawLabelScore {
  rawLabel: string;
  confidence: number;
  canonicalLabel?: string | null;
  modelVersion?: string | null;
}

export interface CloudClip {
  startTime: number;
  endTime: number;
  confidence: number;
  label: string;
  action: string;
  canonicalLabel?: string | null;
  eventFamily?: string | null;
  eventSubtype?: string | null;
  shotSubtype?: string | null;
  outcome?: "made" | "missed" | "blocked" | "uncertain" | null;
  audioScore: number;
  visualScore: number;
  motionScore: number;
  combinedScore: number;
  confidenceBeforeMapping?: number | null;
  confidenceAfterMapping?: number | null;
  eventFamilyConfidenceBeforeMapping?: number | null;
  eventFamilyConfidenceAfterMapping?: number | null;
  shotSubtypeConfidenceBeforeMapping?: number | null;
  shotSubtypeConfidenceAfterMapping?: number | null;
  outcomeConfidenceBeforeMapping?: number | null;
  outcomeConfidenceAfterMapping?: number | null;
  detectionMethod: "cloud" | "ml" | "heuristic";
  shouldAutoKeep: boolean;
  shouldEnableSlowMotion: boolean;
  isUncertain?: boolean | null;
  promptSetVersion?: string | null;
  eventType?: string | null;
  shotType?: string | null;
  makeMiss?: "make" | "miss" | "unknown" | null;
  rankScore?: number | null;
  reviewState?: string | null;
  reviewerNotes?: string | null;
  topLabels?: CloudLabelScore[] | null;
  comparisonTopLabels?: CloudLabelScore[] | null;
  rawTopLabels?: CloudRawLabelScore[] | null;
  comparisonRawTopLabels?: CloudRawLabelScore[] | null;
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
  acceptedAt?: string | null;
  processingStartedAt?: string | null;
  attemptCount?: number | null;
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
  attemptCount?: number | null;
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
  acceptedAt?: string | null;
  processingStartedAt?: string | null;
  attemptCount?: number | null;
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
  attemptCount?: number | null;
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

export type RenderStatus = "render_requested" | "created" | "queued" | "rendering" | "rendered" | "failed" | "cancelled";

export interface EditCandidateClip {
  id: string;
  start: number;
  end: number;
  eventCenter: number;
  label: string;
  confidence?: number;
  excitement?: number;
  watchability?: number;
  motionScore?: number;
  audioPeak?: number;
  combinedScore?: number | null;
  duplicateGroup?: string | null;
}

export interface CreateEditJobRequest {
  videoId: string;
  analysisJobId: string;
  installId: string;
  sourceObjectKey?: string | null;
  preset: "personal_highlight" | "full_game_highlight" | "coach_review" | "fast_break_mix" | "best_five";
  theme?: string | null;
  targetDurationSeconds: number;
  aspectRatio?: "9:16" | "16:9" | "source" | null;
  planTier?: "free" | "pro";
  clips: EditCandidateClip[];
}

export interface EditJobResponse extends ResponseEnvelope {
  editJobId: string;
  videoId: string;
  analysisJobId: string;
  status: string;
  preset: string;
  targetDurationSeconds: number;
  aspectRatio: "9:16" | "16:9" | "source";
  clipCount: number;
  validationErrors?: Array<Record<string, unknown>>;
}

export interface EditPlanResponse extends ResponseEnvelope {
  editJobId: string;
  status: string;
  plan: Record<string, unknown>;
  validationErrors?: Array<Record<string, unknown>>;
}

export interface StartEditRenderRequest {
  installId: string;
  sourceObjectKey?: string | null;
  planTier?: "free" | "pro";
  editPlan?: Record<string, unknown>;
  sourceClips?: EditCandidateClip[];
}

export type EditRevisionCommand =
  | "make_shorter"
  | "make_longer"
  | "make_more_hype"
  | "make_nba_style"
  | "add_more_slow_motion"
  | "remove_weak_clips"
  | "use_original_audio"
  | "switch_format_vertical"
  | "switch_format_widescreen";

export interface ReviseEditJobRequest {
  installId: string;
  command: EditRevisionCommand;
  targetDurationSeconds?: number | null;
  aspectRatio?: "9:16" | "16:9" | "source" | null;
}

export interface StartEditRevisionRenderRequest {
  installId: string;
}

export interface EditRevisionResponse extends ResponseEnvelope {
  revisionId: string;
  editJobId: string;
  basePlanId: string;
  newPlanId: string;
  command: EditRevisionCommand;
  status: "revision_ready" | "revision_failed";
  patch: Record<string, unknown>;
  revisedPlan: Record<string, unknown>;
  validationResult: Record<string, unknown>;
  requiresRerender: boolean;
}

export interface EditRevisionListResponse extends ResponseEnvelope {
  editJobId: string;
  revisions: EditRevisionResponse[];
}

export interface EditingRenderJobResponse extends ResponseEnvelope {
  editJobId: string;
  renderJobId: string;
  renderer: string;
  rendererVersion: string;
  status: RenderStatus;
  outputObjectKey?: string | null;
  renderLogObjectKey?: string | null;
  durationSeconds?: number | null;
  aspectRatio: string;
  traceId: string;
  validationErrors?: Array<Record<string, unknown>>;
}

export interface EditingDownloadUrlResponse {
  editJobId: string;
  renderJobId: string;
  downloadUrl: string;
  outputObjectKey: string;
  contentType: "video/mp4";
  expiresAt: string;
}
