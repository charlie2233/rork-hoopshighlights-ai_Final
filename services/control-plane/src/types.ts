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

export type AssetStatus =
  | "initialized"
  | "uploading"
  | "uploaded"
  | "processing"
  | "proxy_ready"
  | "ready"
  | "failed";

export type ReviewFeedbackTag =
  | "duplicate"
  | "wrong_team"
  | "bad_window"
  | "wrong_label"
  | "low_quality";

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
  teamSelection?: TeamSelection | null;
  uploadPreference?: "single" | "resumable" | null;
  assetId?: string | null;
  storageKey?: string | null;
}

export interface CloudAnalysisCapabilitiesResponse extends ResponseEnvelope {
  maxFileSizeBytes: number;
  maxDurationSeconds: number;
  resumableUploadThresholdBytes: number;
  supportsResumableUpload: boolean;
  recommendedUploadPreference: "resumable";
  signedUploadTtlSeconds: number;
  defaultPollAfterSeconds: number;
  analysisMode: "cloud";
}

export interface CreateCloudAnalysisJobResponse extends ResponseEnvelope {
  jobId: string;
  assetId?: string | null;
  storageKey?: string | null;
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
  resumableUpload?: ResumableUploadDescriptor | null;
}

export interface AssetArtifacts {
  proxyStorageKey?: string | null;
  thumbnailStorageKeys: string[];
  waveformStorageKey?: string | null;
}

export interface AssetRecord {
  assetId: string;
  installId: string;
  filename: string;
  contentType: string;
  fileSizeBytes: number;
  durationSeconds: number;
  storageKey: string;
  status: AssetStatus;
  uploadMode: "single" | "multipart";
  uploadedBytes: number;
  artifacts: AssetArtifacts;
  createdAt: string;
  updatedAt: string;
  failureReason?: string | null;
}

export interface UploadInitRequest {
  filename: string;
  contentType: string;
  fileSizeBytes: number;
  durationSeconds: number;
  installId: string;
  appVersion: string;
  analysisVersion: string;
  uploadPreference?: "single" | "multipart" | "auto" | null;
  partSizeBytes?: number | null;
}

export interface UploadTargetResponse {
  uploadUrl: string;
  uploadMethod: "PUT";
  uploadHeaders: Record<string, string>;
  partNumber?: number | null;
}

export interface MultipartUploadResponse {
  uploadId: string;
  partSizeBytes: number;
  partCount: number;
  parts: UploadTargetResponse[];
}

export interface UploadInitResponse extends ResponseEnvelope {
  assetId: string;
  storageKey: string;
  status: AssetStatus;
  uploadMode: "single" | "multipart";
  uploadUrl?: string | null;
  uploadMethod: "PUT";
  uploadHeaders: Record<string, string>;
  multipart?: MultipartUploadResponse | null;
  expiresAt: string;
  pollAfterSeconds: number;
  uploadState: string;
}

export interface UploadCompleteRequest {
  installId: string;
  uploadId?: string | null;
  parts?: Array<{
    partNumber: number;
    etag?: string | null;
    sizeBytes?: number | null;
  }>;
}

export interface UploadCompleteResponse extends ResponseEnvelope {
  assetId: string;
  storageKey: string;
  status: AssetStatus;
  artifacts: AssetArtifacts;
  pollAfterSeconds: number;
}

export interface AssetStatusResponse extends AssetRecord, ResponseEnvelope {}

export interface CreateAssetAnalysisJobRequest {
  installId: string;
  appVersion?: string | null;
  analysisVersion?: string | null;
  teamSelection?: TeamSelection | null;
}

export interface AssetAnalysisJobResponse extends ResponseEnvelope {
  jobId: string;
  assetId: string;
  storageKey: string;
  status: JobStatus;
  pollAfterSeconds: number;
  quotaRemainingToday: number;
  analysisMode: "cloud";
}

export interface StartCloudAnalysisJobRequest {
  installId: string;
  teamSelection?: TeamSelection | null;
}

export interface StartCloudAnalysisJobResponse extends ResponseEnvelope {
  jobId: string;
  status: JobStatus;
}

export interface ScanCloudAnalysisTeamsRequest {
  installId: string;
}

export interface ScanCloudAnalysisTeamsResponse extends ResponseEnvelope {
  jobId: string;
  status: "scanned" | "unavailable";
  detectedTeams: TeamOption[];
}

export interface InferenceTeamScanRequest {
  jobId: string;
  assetId?: string | null;
  storageKey?: string | null;
  requestId: string;
  uploadTraceId: string;
  traceId: string;
  sourceObjectKey: string;
  sourceUrl: string;
  filename: string;
  contentType: string;
  durationSeconds: number;
  installId: string;
  appVersion: string;
  analysisVersion: string;
  schemaVersion: string;
  modelVersion?: string | null;
}

export interface UploadPresignRequest extends CreateCloudAnalysisJobRequest {}

export interface UploadPresignResponse extends ResponseEnvelope {
  jobId: string;
  assetId?: string | null;
  storageKey?: string | null;
  sourceObjectKey: string;
  resultObjectKey: string;
  uploadUrl: string;
  uploadMethod: "PUT";
  uploadHeaders: Record<string, string>;
  expiresAt: string;
  status: JobStatus;
  analysisMode: "cloud";
  resumableUpload?: ResumableUploadDescriptor | null;
}

export interface ResumableUploadDescriptor {
  uploadId: string;
  chunkSizeBytes: number;
  partCount: number;
  expiresAt: string;
}

export interface MultipartUploadPartRequest {
  jobId: string;
  installId: string;
  uploadId: string;
  partNumber: number;
}

export interface MultipartUploadPartResponse extends ResponseEnvelope {
  jobId: string;
  partNumber: number;
  uploadUrl: string;
  uploadMethod: "PUT";
  uploadHeaders: Record<string, string>;
  expiresAt: string;
}

export interface MultipartUploadCompleteRequest {
  jobId: string;
  installId: string;
  uploadId: string;
  parts: Array<{
    partNumber: number;
    etag: string;
  }>;
}

export interface CreateCloudJobRequest {
  jobId?: string;
  installId: string;
  sourceObjectKey?: string;
  uploadObjectKey?: string;
  resultObjectKey?: string;
  teamSelection?: TeamSelection | null;
}

export interface TeamSelection {
  mode: "all" | "team";
  teamId?: string | null;
  label?: string | null;
  colorLabel?: string | null;
  confidenceThreshold?: number | null;
  includeUncertain?: boolean | null;
}

export interface TeamOption {
  teamId: string;
  label: string;
  colorLabel?: string | null;
  primaryColorHex?: string | null;
  confidence: number;
  source?: string | null;
}

export interface ClipTeamAttribution {
  teamId?: string | null;
  label?: string | null;
  colorLabel?: string | null;
  confidence: number;
  source?: string | null;
  evidenceFrameRefs?: string[] | null;
  evidenceRoleGroups?: string[] | null;
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
  eventCenter?: number | null;
  confidence: number;
  label: string;
  action: string;
  canonicalLabel?: string | null;
  eventFamily?: string | null;
  eventSubtype?: string | null;
  shotSubtype?: string | null;
  outcome?: "made" | "missed" | "blocked" | "uncertain" | null;
  audioScore: number;
  audioCueType?: "spike" | "cluster" | "super_loud_cluster" | "swell" | "steady_noise" | "none" | null;
  audioCueConfidence?: number | null;
  audioCueTime?: number | null;
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
  reviewFeedbackTags?: ReviewFeedbackTag[] | null;
  topLabels?: CloudLabelScore[] | null;
  comparisonTopLabels?: CloudLabelScore[] | null;
  rawTopLabels?: CloudRawLabelScore[] | null;
  comparisonRawTopLabels?: CloudRawLabelScore[] | null;
  nativeShotSignals?: NativeShotSignals | null;
  teamAttribution?: ClipTeamAttribution | null;
  teamAttributionStatus?: "all" | "matched" | "opponent" | "uncertain" | null;
}

export interface NativeShotSignals {
  isShotLike: boolean;
  leadInSeconds: number;
  followThroughSeconds: number;
  setupContextScore: number;
  outcomeContextScore: number;
  eventCenterQuality: number;
  contextQualityScore: number;
  timingWindowOk: boolean;
  outcome: "made" | "missed" | "blocked" | "uncertain" | "not_shot";
  outcomeConfidence: number;
  outcomeEvidenceSource?: "label_only" | "native_shot_signals" | "defensive_event" | "gpt_shot_tracking" | "gpt_defensive_tracking" | "non_shot" | "uncertain" | "not_shot";
  outcomeReliabilityScore?: number;
}

export interface CloudDiagnostics {
  processingMs: number;
  backendModelVersion: string;
  usedVideoIntelligence: boolean;
  usedGeminiRelabeling: boolean;
  candidateSegments: number;
  finalSegments: number;
  usedTeamQuickScan?: boolean;
  preTeamFilterSegments?: number;
  teamMatchedCandidateSegments?: number;
  teamUncertainCandidateSegments?: number;
  teamOpponentFilteredSegments?: number;
  teamMatchedReviewSegments?: number;
  teamUncertainReviewSegments?: number;
  defensiveReviewSegments?: number;
  blockReviewSegments?: number;
  stealReviewSegments?: number;
  forcedTurnoverReviewSegments?: number;
  defensiveStopReviewSegments?: number;
}

export interface CloudAnalysisResult extends ResponseEnvelope {
  analysisJobId?: string | null;
  assetId?: string | null;
  assetStorageKey?: string | null;
  storageKey?: string | null;
  proxyStorageKey?: string | null;
  assetStatus?: AssetStatus | string | null;
  uploadedBytes?: number | null;
  fileSizeBytes?: number | null;
  assetFailureReason?: string | null;
  sourceObjectKey?: string | null;
  clipCount: number;
  clips: CloudClip[];
  diagnostics: CloudDiagnostics;
  resultConfidence: number;
  detectedTeams?: TeamOption[] | null;
  teamSelection?: TeamSelection | null;
}

export interface CloudAnalysisJobResponse extends ResponseEnvelope {
  jobId: string;
  assetId?: string | null;
  storageKey?: string | null;
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
  assetId?: string | null;
  storageKey?: string | null;
  requestId: string;
  uploadTraceId: string;
  traceId: string;
  schemaVersion: string;
  sourceObjectKey: string;
  resultObjectKey: string;
  modelVersion?: string | null;
  teamSelection?: TeamSelection | null;
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
  assetId?: string | null;
  storageKey?: string | null;
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
  assetId?: string | null;
  storageKey?: string | null;
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
  teamSelection?: TeamSelection | null;
  detectedTeams?: TeamOption[] | null;
  teamScanStatus?: "scanned" | "unavailable" | null;
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
  assetId?: string | null;
  storageKey?: string | null;
  requestId: string;
  uploadTraceId: string;
  inferenceAttemptId: string;
  traceId: string;
  filename?: string;
  contentType?: string;
  fileSizeBytes?: number;
  durationSeconds?: number;
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
  teamSelection?: TeamSelection | null;
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
  reviewFeedbackTags?: ReviewFeedbackTag[];
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

export type RenderStatus = "render_requested" | "created" | "queued" | "rendering" | "rendered" | "failed" | "failed_timeout" | "cancelled";
export type EditPlanTier = "free" | "pro" | "internal" | "dev";

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
  audioCueType?: "spike" | "cluster" | "super_loud_cluster" | "swell" | "steady_noise" | "none" | null;
  audioCueConfidence?: number | null;
  audioCueTime?: number | null;
  combinedScore?: number | null;
  duplicateGroup?: string | null;
  nativeShotSignals?: NativeShotSignals | null;
  teamAttribution?: ClipTeamAttribution | null;
  teamAttributionStatus?: "all" | "matched" | "opponent" | "uncertain" | null;
}

export interface CreateEditJobRequest {
  videoId: string;
  analysisJobId: string;
  installId: string;
  sourceObjectKey?: string | null;
  preset: "personal_highlight" | "full_game_highlight" | "coach_review" | "fast_break_mix" | "best_five";
  templateId?:
    | "personal_highlight_v1"
    | "full_game_highlight_v1"
    | "coach_review_v1"
    | "recruiting_reel_pro_v1"
    | "cinematic_mixtape_pro_v1"
    | "nba_recap_pro_v1"
    | "team_highlight_pro_v1"
    | null;
  theme?: string | null;
  targetDurationSeconds: number;
  aspectRatio?: "9:16" | "16:9" | "source" | null;
  planTier?: EditPlanTier;
  revenueCatAppUserID?: string | null;
  userPrompt?: string | null;
  teamSelection?: TeamSelection | null;
  clips: EditCandidateClip[];
}

export interface EditJobResponse extends ResponseEnvelope {
  editJobId: string;
  videoId: string;
  analysisJobId: string;
  status: string;
  preset: string;
  templateId?: string | null;
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
  planTier?: EditPlanTier;
  revenueCatAppUserID?: string | null;
  idempotencyKey?: string | null;
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
  idempotencyKey?: string | null;
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
  revisionPlanner?: "deterministic_patch" | "gpt_patch";
  gptRevisionPatchApplied?: boolean;
  gptRevisionPatchStatus?: "not_requested" | "disabled" | "fallback" | "applied" | "rejected";
  gptRevisionPatchFallbackReason?: string | null;
}

export interface EditRevisionListResponse extends ResponseEnvelope {
  editJobId: string;
  revisions: EditRevisionResponse[];
}

export interface EditingVersionResponse extends ResponseEnvelope {
  service?: string;
  backendModelVersion?: string;
  gitSha?: string;
  featureFlags?: Record<string, unknown>;
}

export interface EditingRenderJobResponse extends ResponseEnvelope {
  editJobId: string;
  revisionId?: string | null;
  renderJobId: string;
  renderer: string;
  rendererVersion: string;
  planVersion?: string | null;
  templateId?: string | null;
  status: RenderStatus;
  outputObjectKey?: string | null;
  renderLogObjectKey?: string | null;
  durationSeconds?: number | null;
  aspectRatio: string;
  traceId: string;
  validationErrors?: Array<Record<string, unknown>>;
  planTier?: EditPlanTier;
  policy?: Record<string, unknown>;
  retryCount?: number;
  outputBytes?: number | null;
  retentionMetadata?: Record<string, unknown> | null;
}

export interface EditingRenderJobListResponse extends ResponseEnvelope {
  installId: string;
  generatedAt: string;
  renders: EditingRenderJobResponse[];
}

export interface EditingDownloadUrlResponse {
  editJobId: string;
  renderJobId: string;
  downloadUrl: string;
  outputObjectKey?: string;
  contentType: "video/mp4";
  expiresAt: string;
}
