import type { D1Database } from "@cloudflare/workers-types";
import type {
  AdminJobListItem,
  ClipReviewUpdate,
  JobRecord,
  MetadataGenerationRequest,
  MetadataJobRecord,
  AdminReviewUpdate
} from "../types";

type JobRow = Record<string, unknown>;

export async function upsertJobIndex(db: D1Database, job: JobRecord): Promise<void> {
  await db
    .prepare(
      `INSERT INTO jobs (
        job_id, schema_version, request_id, trace_id, install_id, filename, content_type, file_size_bytes,
        duration_seconds, app_version, analysis_version, analysis_mode, status, stage, progress,
        model_version, failure_reason, error_code, error_message, source_object_key,
        result_object_key, upload_url, upload_method, upload_headers_json, expires_at,
        created_at, upload_pending_at, uploaded_at, queued_at, accepted_at, processing_started_at, attempt_count,
        started_at, finished_at, cancelled_at, updated_at, result_confidence,
        upload_trace_id, inference_attempt_id,
        results_json, review_state, reviewer_notes, promoted_to_training_set
      ) VALUES (
      ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8,
        ?9, ?10, ?11, ?12, ?13, ?14, ?15,
        ?16, ?17, ?18, ?19, ?20,
        ?21, ?22, ?23, ?24, ?25, ?26, ?27,
        ?28, ?29, ?30, ?31, ?32, ?33,
        ?34, ?35, ?36, ?37, ?38, ?39, ?40, ?41, ?42, ?43
      )
      ON CONFLICT(job_id) DO UPDATE SET
        schema_version=excluded.schema_version,
        request_id=excluded.request_id,
        trace_id=excluded.trace_id,
        install_id=excluded.install_id,
        filename=excluded.filename,
        content_type=excluded.content_type,
        file_size_bytes=excluded.file_size_bytes,
        duration_seconds=excluded.duration_seconds,
        app_version=excluded.app_version,
        analysis_version=excluded.analysis_version,
        analysis_mode=excluded.analysis_mode,
        status=excluded.status,
        stage=excluded.stage,
        progress=excluded.progress,
        model_version=excluded.model_version,
        failure_reason=excluded.failure_reason,
        error_code=excluded.error_code,
        error_message=excluded.error_message,
        source_object_key=excluded.source_object_key,
        result_object_key=excluded.result_object_key,
        upload_url=excluded.upload_url,
        upload_method=excluded.upload_method,
        upload_headers_json=excluded.upload_headers_json,
        expires_at=excluded.expires_at,
        created_at=excluded.created_at,
        upload_pending_at=excluded.upload_pending_at,
        uploaded_at=excluded.uploaded_at,
        queued_at=excluded.queued_at,
        accepted_at=excluded.accepted_at,
        processing_started_at=excluded.processing_started_at,
        attempt_count=excluded.attempt_count,
        started_at=excluded.started_at,
        finished_at=excluded.finished_at,
        cancelled_at=excluded.cancelled_at,
        updated_at=excluded.updated_at,
        result_confidence=excluded.result_confidence,
        upload_trace_id=excluded.upload_trace_id,
        inference_attempt_id=excluded.inference_attempt_id,
        results_json=excluded.results_json,
        review_state=excluded.review_state,
        reviewer_notes=excluded.reviewer_notes,
        promoted_to_training_set=excluded.promoted_to_training_set`
    )
    .bind(
      job.jobId,
      job.schemaVersion,
      job.requestId,
      job.traceId,
      job.installId,
      job.filename,
      job.contentType,
      job.fileSizeBytes,
      job.durationSeconds,
      job.appVersion,
      job.analysisVersion,
      job.analysisMode,
      job.status,
      job.stage,
      job.progress,
      job.modelVersion ?? null,
      job.failureReason ?? null,
      job.errorCode ?? null,
      job.errorMessage ?? null,
      job.sourceObjectKey,
      job.resultObjectKey,
      job.uploadUrl,
      job.uploadMethod,
      JSON.stringify(job.uploadHeaders),
      job.expiresAt,
      job.createdAt,
      job.uploadPendingAt ?? null,
      job.uploadedAt ?? null,
      job.queuedAt ?? null,
      job.acceptedAt ?? null,
      job.processingStartedAt ?? null,
      job.attemptCount ?? 0,
      job.startedAt ?? null,
      job.finishedAt ?? null,
      job.cancelledAt ?? null,
      job.updatedAt,
      job.confidence ?? job.resultConfidence ?? null,
      job.uploadTraceId ?? null,
      job.inferenceAttemptId ?? null,
      job.results ? JSON.stringify(job.results) : null,
      job.reviewState ?? "unreviewed",
      job.reviewerNotes ?? null,
      job.promotedToTrainingSet ? 1 : 0
    )
    .run();
}

export async function getJobIndex(db: D1Database, jobId: string): Promise<JobRecord | null> {
  const row = await db.prepare(`SELECT * FROM jobs WHERE job_id = ?1`).bind(jobId).first<JobRow>();
  return row ? rowToJobRecord(row) : null;
}

export async function listJobsIndex(
  db: D1Database,
  options: {
    status?: string | null;
    modelVersion?: string | null;
    failureReason?: string | null;
    limit: number;
  }
): Promise<AdminJobListItem[]> {
  const conditions: string[] = [];
  const bindings: unknown[] = [];

  if (options.status) {
    bindings.push(options.status);
    conditions.push(`status = ?${bindings.length}`);
  }
  if (options.modelVersion) {
    bindings.push(options.modelVersion);
    conditions.push(`model_version = ?${bindings.length}`);
  }
  if (options.failureReason) {
    bindings.push(options.failureReason);
    conditions.push(`failure_reason = ?${bindings.length}`);
  }

  bindings.push(options.limit);
  const whereClause = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";
  const rows = await db
    .prepare(
      `SELECT job_id, status, stage, progress, install_id, analysis_version, model_version,
              failure_reason, review_state, created_at, updated_at
       FROM jobs
       ${whereClause}
       ORDER BY created_at DESC
       LIMIT ?${bindings.length}`
    )
    .bind(...bindings)
    .all<JobRow>();

  return (rows.results ?? []).map((row) => ({
    jobId: String(row.job_id),
    status: String(row.status),
    stage: String(row.stage),
    progress: Number(row.progress ?? 0),
    installId: String(row.install_id),
    analysisVersion: String(row.analysis_version),
    modelVersion: row.model_version == null ? null : String(row.model_version),
    failureReason: row.failure_reason == null ? null : String(row.failure_reason),
    reviewState: row.review_state == null ? null : String(row.review_state),
    createdAt: String(row.created_at),
    updatedAt: String(row.updated_at)
  }));
}

export async function appendJobEvent(
  db: D1Database,
  event: {
    jobId: string;
    requestId: string;
    traceId: string;
    eventType: string;
    message: string;
    payload?: unknown;
    createdAt: string;
  }
): Promise<void> {
  await db
    .prepare(
      `INSERT INTO job_events (job_id, request_id, trace_id, event_type, message, payload_json, created_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)`
    )
    .bind(
      event.jobId,
      event.requestId,
      event.traceId,
      event.eventType,
      event.message,
      event.payload ? JSON.stringify(event.payload) : null,
      event.createdAt
    )
    .run();
}

export async function readJobEvents(db: D1Database, jobId: string): Promise<Record<string, unknown>[]> {
  const rows = await db
    .prepare(
      `SELECT event_type, message, payload_json, created_at, request_id, trace_id
       FROM job_events
       WHERE job_id = ?1
       ORDER BY created_at ASC`
    )
    .bind(jobId)
    .all<JobRow>();

  return (rows.results ?? []).map((row) => ({
    eventType: String(row.event_type),
    message: String(row.message),
    payload: parseJson(row.payload_json),
    createdAt: String(row.created_at),
    requestId: String(row.request_id),
    traceId: String(row.trace_id)
  }));
}

export async function upsertJobReview(
  db: D1Database,
  jobId: string,
  update: AdminReviewUpdate
): Promise<void> {
  const current = await getJobIndex(db, jobId);
  if (!current) {
    return;
  }

  const promoted = update.promotedToTrainingSet ?? current.promotedToTrainingSet ?? false;

  await db
    .prepare(
      `UPDATE jobs
       SET review_state = ?2,
           reviewer_notes = ?3,
           promoted_to_training_set = ?4,
           updated_at = ?5
       WHERE job_id = ?1`
    )
    .bind(
      jobId,
      update.reviewState ?? current.reviewState ?? "unreviewed",
      update.reviewerNotes ?? current.reviewerNotes ?? null,
      promoted ? 1 : 0,
      new Date().toISOString()
    )
    .run();
}

export async function upsertClipReview(
  db: D1Database,
  clipId: string,
  jobId: string,
  clipIndex: number,
  update: ClipReviewUpdate,
  modelVersion?: string | null,
  failureReason?: string | null
): Promise<void> {
  const now = new Date().toISOString();
  await db
    .prepare(
      `INSERT INTO clip_reviews (
        clip_id, job_id, clip_index, label, action, review_state, reviewer_notes,
        promoted_to_training_set, model_version, failure_reason, created_at, updated_at
      ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)
      ON CONFLICT(clip_id) DO UPDATE SET
        label=excluded.label,
        action=excluded.action,
        review_state=excluded.review_state,
        reviewer_notes=excluded.reviewer_notes,
        promoted_to_training_set=excluded.promoted_to_training_set,
        model_version=excluded.model_version,
        failure_reason=excluded.failure_reason,
        updated_at=excluded.updated_at`
    )
    .bind(
      clipId,
      jobId,
      clipIndex,
      update.label ?? null,
      update.action ?? null,
      update.reviewState ?? "unreviewed",
      update.reviewerNotes ?? null,
      update.promotedToTrainingSet ? 1 : 0,
      modelVersion ?? null,
      failureReason ?? null,
      now,
      now
    )
    .run();
}

export async function createMetadataJob(
  db: D1Database,
  record: MetadataJobRecord
): Promise<void> {
  await db
    .prepare(
      `INSERT INTO metadata_jobs (
        metadata_job_id, job_id, status, prompt, result_json, model_version, failure_reason, created_at, updated_at
      ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
      ON CONFLICT(metadata_job_id) DO UPDATE SET
        status=excluded.status,
        prompt=excluded.prompt,
        result_json=excluded.result_json,
        model_version=excluded.model_version,
        failure_reason=excluded.failure_reason,
        updated_at=excluded.updated_at`
    )
    .bind(
      record.metadataJobId,
      record.jobId,
      record.status,
      record.prompt ?? null,
      record.resultJson ?? null,
      record.modelVersion ?? null,
      record.failureReason ?? null,
      record.createdAt,
      record.updatedAt
    )
    .run();
}

function rowToJobRecord(row: JobRow): JobRecord {
  const uploadHeaders = parseJson(row.upload_headers_json) as Record<string, string> | null;
  const results = parseJson(row.results_json) as JobRecord["results"];

  return {
    requestId: String(row.request_id),
    schemaVersion: String(row.schema_version ?? "phase1a-staging-happy-path"),
    modelVersion: row.model_version == null ? null : String(row.model_version),
    failureReason: row.failure_reason == null ? null : String(row.failure_reason),
    jobId: String(row.job_id),
    traceId: String(row.trace_id),
    uploadTraceId: row.upload_trace_id == null ? null : String(row.upload_trace_id),
    inferenceAttemptId: row.inference_attempt_id == null ? null : String(row.inference_attempt_id),
    acceptedAt: row.accepted_at == null ? null : String(row.accepted_at),
    processingStartedAt: row.processing_started_at == null ? null : String(row.processing_started_at),
    attemptCount: Number(row.attempt_count ?? 0),
    installId: String(row.install_id),
    filename: String(row.filename),
    contentType: String(row.content_type),
    fileSizeBytes: Number(row.file_size_bytes),
    durationSeconds: Number(row.duration_seconds),
    appVersion: String(row.app_version),
    analysisVersion: String(row.analysis_version),
    analysisMode: "cloud",
    status: String(row.status) as JobRecord["status"],
    stage: String(row.stage),
    progress: Number(row.progress ?? 0),
    createdAt: String(row.created_at),
    uploadPendingAt: row.upload_pending_at == null ? null : String(row.upload_pending_at),
    uploadedAt: row.uploaded_at == null ? null : String(row.uploaded_at),
    queuedAt: row.queued_at == null ? null : String(row.queued_at),
    startedAt: row.started_at == null ? null : String(row.started_at),
    finishedAt: row.finished_at == null ? null : String(row.finished_at),
    cancelledAt: row.cancelled_at == null ? null : String(row.cancelled_at),
    errorCode: row.error_code == null ? null : String(row.error_code),
    errorMessage: row.error_message == null ? null : String(row.error_message),
    sourceObjectKey: String(row.source_object_key),
    resultObjectKey: String(row.result_object_key),
    uploadUrl: String(row.upload_url),
    uploadMethod: String(row.upload_method) as "PUT",
    uploadHeaders: uploadHeaders ?? {},
    expiresAt: String(row.expires_at),
    updatedAt: String(row.updated_at),
    resultConfidence: row.result_confidence == null ? null : Number(row.result_confidence),
    confidence: row.result_confidence == null ? null : Number(row.result_confidence),
    results: results ?? null,
    reviewState: row.review_state == null ? null : String(row.review_state),
    reviewerNotes: row.reviewer_notes == null ? null : String(row.reviewer_notes),
    promotedToTrainingSet: Number(row.promoted_to_training_set ?? 0) === 1
  };
}

function parseJson<T>(value: unknown): T | null {
  if (value == null) {
    return null;
  }
  if (typeof value !== "string" || value.length === 0) {
    return null;
  }
  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}
