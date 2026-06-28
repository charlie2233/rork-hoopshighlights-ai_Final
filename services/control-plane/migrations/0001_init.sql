CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  trace_id TEXT NOT NULL,
  install_id TEXT NOT NULL,
  filename TEXT NOT NULL,
  content_type TEXT NOT NULL,
  file_size_bytes INTEGER NOT NULL,
  duration_seconds REAL NOT NULL,
  app_version TEXT NOT NULL,
  analysis_version TEXT NOT NULL,
  analysis_mode TEXT NOT NULL,
  status TEXT NOT NULL,
  stage TEXT NOT NULL,
  progress REAL NOT NULL DEFAULT 0,
  model_version TEXT,
  failure_reason TEXT,
  error_code TEXT,
  error_message TEXT,
  source_object_key TEXT NOT NULL,
  result_object_key TEXT NOT NULL,
  upload_url TEXT NOT NULL,
  upload_method TEXT NOT NULL,
  upload_headers_json TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  queued_at TEXT,
  started_at TEXT,
  finished_at TEXT,
  updated_at TEXT NOT NULL,
  result_confidence REAL,
  results_json TEXT,
  review_state TEXT NOT NULL DEFAULT 'unreviewed',
  reviewer_notes TEXT,
  promoted_to_training_set INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_created_at
  ON jobs(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_jobs_model_version
  ON jobs(model_version);

CREATE INDEX IF NOT EXISTS idx_jobs_failure_reason
  ON jobs(failure_reason);

CREATE TABLE IF NOT EXISTS job_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  request_id TEXT NOT NULL,
  trace_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  message TEXT NOT NULL,
  payload_json TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_events_job_id_created_at
  ON job_events(job_id, created_at DESC);

CREATE TABLE IF NOT EXISTS clip_reviews (
  clip_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  clip_index INTEGER NOT NULL,
  label TEXT,
  action TEXT,
  review_state TEXT NOT NULL DEFAULT 'unreviewed',
  reviewer_notes TEXT,
  review_feedback_tags_json TEXT,
  promoted_to_training_set INTEGER NOT NULL DEFAULT 0,
  model_version TEXT,
  failure_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clip_reviews_job_id_clip_index
  ON clip_reviews(job_id, clip_index ASC);

CREATE TABLE IF NOT EXISTS metadata_jobs (
  metadata_job_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  status TEXT NOT NULL,
  prompt TEXT,
  result_json TEXT,
  model_version TEXT,
  failure_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metadata_jobs_job_id_created_at
  ON metadata_jobs(job_id, created_at DESC);
