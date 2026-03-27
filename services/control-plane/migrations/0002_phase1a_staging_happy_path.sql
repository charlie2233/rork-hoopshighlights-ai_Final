ALTER TABLE jobs ADD COLUMN schema_version TEXT NOT NULL DEFAULT 'phase1a-staging-happy-path';
ALTER TABLE jobs ADD COLUMN upload_pending_at TEXT;
ALTER TABLE jobs ADD COLUMN uploaded_at TEXT;
ALTER TABLE jobs ADD COLUMN cancelled_at TEXT;
