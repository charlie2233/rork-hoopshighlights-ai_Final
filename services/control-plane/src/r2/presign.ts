import { AwsClient } from "aws4fetch";
import type { Env } from "../env";

export interface PresignedUploadTarget {
  objectKey: string;
  uploadUrl: string;
  uploadMethod: "PUT";
  uploadHeaders: Record<string, string>;
  expiresAt: string;
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

function sanitizeFilename(filename: string): string {
  const trimmed = filename.trim().toLowerCase();
  const normalized = trimmed.replace(/[^a-z0-9._-]+/g, "-").replace(/-+/g, "-");
  const withFallback = normalized.replace(/^[-.]+|[-.]+$/g, "");
  return withFallback || "video.mp4";
}
