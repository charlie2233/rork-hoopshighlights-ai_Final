ALTER TABLE jobs ADD COLUMN upload_trace_id TEXT;
ALTER TABLE jobs ADD COLUMN inference_attempt_id TEXT;

CREATE INDEX IF NOT EXISTS idx_jobs_upload_trace_id
  ON jobs(upload_trace_id);

CREATE INDEX IF NOT EXISTS idx_jobs_inference_attempt_id
  ON jobs(inference_attempt_id);
