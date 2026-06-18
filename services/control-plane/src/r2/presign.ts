import { AwsClient } from "aws4fetch";
import type { Env } from "../env";

export interface PresignedUploadTarget {
  objectKey: string;
  uploadUrl: string;
  uploadMethod: "PUT";
  uploadHeaders: Record<string, string>;
  expiresAt: string;
}

export interface PresignedReadTarget {
  objectKey: string;
  sourceUrl: string;
  expiresAt: string;
}

export interface ResumableUploadTarget {
  uploadId: string;
  chunkSizeBytes: number;
  partCount: number;
  expiresAt: string;
}

export interface PresignedMultipartPartTarget {
  objectKey: string;
  uploadUrl: string;
  uploadMethod: "PUT";
  uploadHeaders: Record<string, string>;
  expiresAt: string;
}

export interface CompletedMultipartUploadPart {
  partNumber: number;
  etag: string;
}

export function buildObjectKey(jobId: string, filename: string): string {
  const safeName = sanitizeFilename(filename);
  return `uploads/${jobId}/${safeName}`;
}

export async function createPresignedUploadTarget(
  env: Env,
  params: {
    jobId: string;
    filename: string;
    contentType: string;
    expiresInSeconds: number;
  }
): Promise<PresignedUploadTarget> {
  const objectKey = buildObjectKey(params.jobId, params.filename);
  const expiresAt = new Date(Date.now() + params.expiresInSeconds * 1000);

  if (!env.R2_ACCOUNT_ID || !env.R2_ACCESS_KEY_ID || !env.R2_SECRET_ACCESS_KEY) {
    return {
      objectKey,
      uploadUrl: `https://r2.local/${env.R2_UPLOAD_BUCKET_NAME}/${objectKey}`,
      uploadMethod: "PUT",
      uploadHeaders: {
        "content-type": params.contentType
      },
      expiresAt: expiresAt.toISOString()
    };
  }

  const client = new AwsClient({
    accessKeyId: env.R2_ACCESS_KEY_ID,
    secretAccessKey: env.R2_SECRET_ACCESS_KEY
  });

  const url = new URL(
    `https://${env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com/${env.R2_UPLOAD_BUCKET_NAME}/${objectKey}`
  );
  const request = new Request(url.toString(), {
    method: "PUT",
    headers: {
      "content-type": params.contentType
    }
  });
  const signed = await client.sign(request, {
    aws: {
      signQuery: true,
      service: "s3",
      region: "auto"
    }
  });

  return {
    objectKey,
    uploadUrl: signed.url,
    uploadMethod: "PUT",
    uploadHeaders: {
      "content-type": params.contentType
    },
    expiresAt: expiresAt.toISOString()
  };
}

export async function createResumableUploadTarget(
  env: Env,
  params: {
    objectKey: string;
    contentType: string;
    fileSizeBytes: number;
    expiresInSeconds: number;
  }
): Promise<ResumableUploadTarget | null> {
  if (!env.R2_ACCOUNT_ID || !env.R2_ACCESS_KEY_ID || !env.R2_SECRET_ACCESS_KEY) {
    return null;
  }

  const expiresAt = new Date(Date.now() + params.expiresInSeconds * 1000);
  const client = new AwsClient({
    accessKeyId: env.R2_ACCESS_KEY_ID,
    secretAccessKey: env.R2_SECRET_ACCESS_KEY
  });
  const url = buildR2ObjectUrl(env, env.R2_UPLOAD_BUCKET_NAME, params.objectKey);
  url.searchParams.set("uploads", "");

  const request = new Request(url.toString(), {
    method: "POST",
    headers: {
      "content-type": params.contentType
    }
  });
  const signed = await client.sign(request, {
    aws: {
      signQuery: true,
      service: "s3",
      region: "auto"
    }
  });

  const response = await fetch(signed);
  if (!response.ok) {
    throw new Error("Could not create resumable upload.");
  }

  const uploadId = parseUploadId(await response.text());
  if (!uploadId) {
    throw new Error("Resumable upload response was missing an upload ID.");
  }

  const chunkSizeBytes = chooseMultipartChunkSize(params.fileSizeBytes);
  return {
    uploadId,
    chunkSizeBytes,
    partCount: Math.ceil(params.fileSizeBytes / chunkSizeBytes),
    expiresAt: expiresAt.toISOString()
  };
}

export async function createPresignedMultipartPartTarget(
  env: Env,
  params: {
    objectKey: string;
    uploadId: string;
    partNumber: number;
    expiresInSeconds: number;
  }
): Promise<PresignedMultipartPartTarget> {
  if (!env.R2_ACCOUNT_ID || !env.R2_ACCESS_KEY_ID || !env.R2_SECRET_ACCESS_KEY) {
    throw new Error("Resumable uploads are unavailable.");
  }

  const expiresAt = new Date(Date.now() + params.expiresInSeconds * 1000);
  const client = new AwsClient({
    accessKeyId: env.R2_ACCESS_KEY_ID,
    secretAccessKey: env.R2_SECRET_ACCESS_KEY
  });
  const url = buildR2ObjectUrl(env, env.R2_UPLOAD_BUCKET_NAME, params.objectKey);
  url.searchParams.set("partNumber", String(params.partNumber));
  url.searchParams.set("uploadId", params.uploadId);
  const request = new Request(url.toString(), { method: "PUT" });
  const signed = await client.sign(request, {
    aws: {
      signQuery: true,
      service: "s3",
      region: "auto"
    }
  });

  return {
    objectKey: params.objectKey,
    uploadUrl: signed.url,
    uploadMethod: "PUT",
    uploadHeaders: {},
    expiresAt: expiresAt.toISOString()
  };
}

export async function completeMultipartUpload(
  env: Env,
  params: {
    objectKey: string;
    uploadId: string;
    parts: CompletedMultipartUploadPart[];
  }
): Promise<void> {
  if (!env.R2_ACCOUNT_ID || !env.R2_ACCESS_KEY_ID || !env.R2_SECRET_ACCESS_KEY) {
    throw new Error("Resumable uploads are unavailable.");
  }

  const client = new AwsClient({
    accessKeyId: env.R2_ACCESS_KEY_ID,
    secretAccessKey: env.R2_SECRET_ACCESS_KEY
  });
  const url = buildR2ObjectUrl(env, env.R2_UPLOAD_BUCKET_NAME, params.objectKey);
  url.searchParams.set("uploadId", params.uploadId);
  const body = buildCompleteMultipartXml(params.parts);
  const request = new Request(url.toString(), {
    method: "POST",
    headers: {
      "content-type": "application/xml"
    },
    body
  });
  const signed = await client.sign(request, {
    aws: {
      signQuery: true,
      service: "s3",
      region: "auto"
    }
  });
  const response = await fetch(signed);
  if (!response.ok) {
    throw new Error("Could not complete resumable upload.");
  }
}

export async function createPresignedReadTarget(
  env: Env,
  params: {
    objectKey: string;
    expiresInSeconds: number;
    bucketName?: string;
  }
): Promise<PresignedReadTarget> {
  const bucketName = params.bucketName ?? env.R2_UPLOAD_BUCKET_NAME;
  const expiresAt = new Date(Date.now() + params.expiresInSeconds * 1000);

  if (!env.R2_ACCOUNT_ID || !env.R2_ACCESS_KEY_ID || !env.R2_SECRET_ACCESS_KEY) {
    return {
      objectKey: params.objectKey,
      sourceUrl: `https://r2.local/${bucketName}/${params.objectKey}`,
      expiresAt: expiresAt.toISOString()
    };
  }

  const client = new AwsClient({
    accessKeyId: env.R2_ACCESS_KEY_ID,
    secretAccessKey: env.R2_SECRET_ACCESS_KEY
  });

  const url = new URL(
    `https://${env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com/${bucketName}/${params.objectKey}`
  );
  const request = new Request(url.toString(), {
    method: "GET"
  });
  const signed = await client.sign(request, {
    aws: {
      signQuery: true,
      service: "s3",
      region: "auto"
    }
  });

  return {
    objectKey: params.objectKey,
    sourceUrl: signed.url,
    expiresAt: expiresAt.toISOString()
  };
}

function buildR2ObjectUrl(env: Env, bucketName: string, objectKey: string): URL {
  return new URL(`https://${env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com/${bucketName}/${objectKey}`);
}

function chooseMultipartChunkSize(fileSizeBytes: number): number {
  const minPartBytes = 8 * 1024 * 1024;
  const maxPartCount = 10000;
  const requiredBytes = Math.ceil(Math.max(fileSizeBytes, 1) / maxPartCount);
  return Math.max(minPartBytes, requiredBytes);
}

function parseUploadId(xml: string): string | null {
  const match = xml.match(/<UploadId>([^<]+)<\/UploadId>/i);
  return match?.[1] ?? null;
}

function buildCompleteMultipartXml(parts: CompletedMultipartUploadPart[]): string {
  const partXml = parts
    .map((part) => {
      return `<Part><PartNumber>${part.partNumber}</PartNumber><ETag>${escapeXml(part.etag)}</ETag></Part>`;
    })
    .join("");
  return `<CompleteMultipartUpload>${partXml}</CompleteMultipartUpload>`;
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function sanitizeFilename(filename: string): string {
  const trimmed = filename.trim().toLowerCase();
  const normalized = trimmed.replace(/[^a-z0-9._-]+/g, "-").replace(/-+/g, "-");
  const withFallback = normalized.replace(/^[-.]+|[-.]+$/g, "");
  return withFallback || "video.mp4";
}
