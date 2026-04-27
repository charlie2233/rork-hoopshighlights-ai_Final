import type { DurableObjectNamespace, D1Database, Queue } from "@cloudflare/workers-types";
import type { DeadLetterQueueMessage, QueueJobMessage } from "./types";

export interface Env {
  APP_ENV: string;
  SCHEMA_VERSION: string;
  DEFAULT_POLL_AFTER_SECONDS: string;
  SIGNED_UPLOAD_TTL_SECONDS: string;
  JOB_TTL_SECONDS: string;
  PROCESSING_TIMEOUT_SECONDS: string;
  MAX_INFERENCE_ATTEMPTS: string;
  MAX_FILE_SIZE_BYTES: string;
  MAX_DURATION_SECONDS: string;
  CONTROL_PLANE_BASE_URL: string;
  ADMIN_API_TOKEN: string;
  CONTROL_PLANE_SHARED_SECRET: string;
  INFERENCE_BASE_URL: string;
  INFERENCE_SHARED_SECRET: string;
  EDITING_BASE_URL: string;
  EDITING_SHARED_SECRET: string;
  R2_ACCOUNT_ID: string;
  R2_UPLOAD_BUCKET_NAME: string;
  R2_RESULT_BUCKET_NAME: string;
  R2_ACCESS_KEY_ID: string;
  R2_SECRET_ACCESS_KEY: string;
  DB: D1Database;
  JOB_STATE: DurableObjectNamespace;
  ANALYSIS_QUEUE: Queue<QueueJobMessage>;
  ANALYSIS_DLQ: Queue<DeadLetterQueueMessage>;
  R2_UPLOADS: R2Bucket;
  R2_RESULTS: R2Bucket;
}

export interface RuntimeConfig {
  appEnv: string;
  schemaVersion: string;
  defaultPollAfterSeconds: number;
  signedUploadTtlSeconds: number;
  jobTtlSeconds: number;
  processingTimeoutSeconds: number;
  maxInferenceAttempts: number;
  maxFileSizeBytes: number;
  maxDurationSeconds: number;
}

export function resolveRuntimeConfig(env: Env): RuntimeConfig {
  return {
    appEnv: env.APP_ENV || "local",
    schemaVersion: env.SCHEMA_VERSION || "phase1a-staging-happy-path",
    defaultPollAfterSeconds: toPositiveInt(env.DEFAULT_POLL_AFTER_SECONDS, 2),
    signedUploadTtlSeconds: toPositiveInt(env.SIGNED_UPLOAD_TTL_SECONDS, 900),
    jobTtlSeconds: toPositiveInt(env.JOB_TTL_SECONDS, 3600),
    processingTimeoutSeconds: toPositiveInt(env.PROCESSING_TIMEOUT_SECONDS, 300),
    maxInferenceAttempts: toPositiveInt(env.MAX_INFERENCE_ATTEMPTS, 3),
    maxFileSizeBytes: toPositiveInt(env.MAX_FILE_SIZE_BYTES, 500 * 1024 * 1024),
    maxDurationSeconds: toPositiveNumber(env.MAX_DURATION_SECONDS, 1800)
  };
}

function toPositiveInt(value: string, fallback: number): number {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function toPositiveNumber(value: string, fallback: number): number {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
