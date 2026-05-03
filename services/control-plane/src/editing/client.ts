import type { Env } from "../env";
import type {
  CreateEditJobRequest,
  EditingDownloadUrlResponse,
  EditingRenderJobResponse,
  EditJobResponse,
  EditPlanResponse,
  EditRevisionListResponse,
  EditRevisionResponse,
  ReviseEditJobRequest,
  StartEditRevisionRenderRequest,
  StartEditRenderRequest
} from "../types";

export async function createEditingEditJob(
  env: Env,
  requestId: string,
  payload: CreateEditJobRequest
): Promise<Response> {
  if (!env.EDITING_BASE_URL) {
    return editingUnavailable(requestId, "Editing service is not configured.");
  }
  const response = await fetch(`${env.EDITING_BASE_URL.replace(/\/+$/, "")}/v1/edit-jobs`, {
    method: "POST",
    headers: editingHeaders(env, requestId, payload.installId),
    body: JSON.stringify(payload)
  });
  return proxyEditingJsonResponse(response, requestId);
}

export async function getEditingEditJob(
  env: Env,
  editJobId: string,
  requestId: string,
  installId: string | null
): Promise<Response> {
  if (!env.EDITING_BASE_URL) {
    return editingUnavailable(requestId, "Editing service is not configured.");
  }
  const url = new URL(`${env.EDITING_BASE_URL.replace(/\/+$/, "")}/v1/edit-jobs/${encodeURIComponent(editJobId)}`);
  if (installId) {
    url.searchParams.set("installId", installId);
  }
  return proxyEditingJsonResponse(await fetch(url, { headers: editingHeaders(env, requestId, installId) }), requestId);
}

export async function getEditingEditPlan(
  env: Env,
  editJobId: string,
  requestId: string,
  installId: string | null
): Promise<Response> {
  if (!env.EDITING_BASE_URL) {
    return editingUnavailable(requestId, "Editing service is not configured.");
  }
  const url = new URL(`${env.EDITING_BASE_URL.replace(/\/+$/, "")}/v1/edit-jobs/${encodeURIComponent(editJobId)}/plan`);
  if (installId) {
    url.searchParams.set("installId", installId);
  }
  return proxyEditingJsonResponse(await fetch(url, { headers: editingHeaders(env, requestId, installId) }), requestId);
}

export async function createEditingRenderJob(
  env: Env,
  editJobId: string,
  requestId: string,
  payload: StartEditRenderRequest
): Promise<Response> {
  if (!env.EDITING_BASE_URL) {
    return editingUnavailable(requestId, "Editing service is not configured.");
  }
  const response = await fetch(`${env.EDITING_BASE_URL.replace(/\/+$/, "")}/v1/edit-jobs/${encodeURIComponent(editJobId)}/render`, {
    method: "POST",
    headers: editingHeaders(env, requestId),
    body: JSON.stringify({
      installId: payload.installId,
      sourceObjectKey: payload.sourceObjectKey,
      planTier: payload.planTier ?? "free",
      editPlan: payload.editPlan,
      sourceClips: payload.sourceClips ?? [],
      idempotencyKey: payload.idempotencyKey
    })
  });
  return proxyEditingJsonResponse(response, requestId);
}

export async function getEditingRenderJob(
  env: Env,
  editJobId: string,
  requestId: string,
  installId: string | null
): Promise<Response> {
  if (!env.EDITING_BASE_URL) {
    return editingUnavailable(requestId, "Editing service is not configured.");
  }
  const url = new URL(`${env.EDITING_BASE_URL.replace(/\/+$/, "")}/v1/edit-jobs/${encodeURIComponent(editJobId)}/render-status`);
  if (installId) {
    url.searchParams.set("installId", installId);
  }
  return proxyEditingJsonResponse(await fetch(url, { headers: editingHeaders(env, requestId, installId) }), requestId);
}

export async function getEditingDownloadUrl(
  env: Env,
  editJobId: string,
  requestId: string,
  installId: string | null
): Promise<Response> {
  if (!env.EDITING_BASE_URL) {
    return editingUnavailable(requestId, "Editing service is not configured.");
  }
  const url = new URL(`${env.EDITING_BASE_URL.replace(/\/+$/, "")}/v1/edit-jobs/${encodeURIComponent(editJobId)}/download-url`);
  if (installId) {
    url.searchParams.set("installId", installId);
  }
  return proxyEditingJsonResponse(await fetch(url, { headers: editingHeaders(env, requestId, installId) }), requestId);
}

export async function reviseEditingEditJob(
  env: Env,
  editJobId: string,
  requestId: string,
  payload: ReviseEditJobRequest
): Promise<Response> {
  if (!env.EDITING_BASE_URL) {
    return editingUnavailable(requestId, "Editing service is not configured.");
  }
  const response = await fetch(`${env.EDITING_BASE_URL.replace(/\/+$/, "")}/v1/edit-jobs/${encodeURIComponent(editJobId)}/revise`, {
    method: "POST",
    headers: editingHeaders(env, requestId, payload.installId),
    body: JSON.stringify(payload)
  });
  return proxyEditingJsonResponse(response, requestId);
}

export async function listEditingRevisions(
  env: Env,
  editJobId: string,
  requestId: string,
  installId: string | null
): Promise<Response> {
  if (!env.EDITING_BASE_URL) {
    return editingUnavailable(requestId, "Editing service is not configured.");
  }
  const url = new URL(`${env.EDITING_BASE_URL.replace(/\/+$/, "")}/v1/edit-jobs/${encodeURIComponent(editJobId)}/revisions`);
  if (installId) {
    url.searchParams.set("installId", installId);
  }
  return proxyEditingJsonResponse(await fetch(url, { headers: editingHeaders(env, requestId, installId) }), requestId);
}

export async function getEditingRevision(
  env: Env,
  editJobId: string,
  revisionId: string,
  requestId: string,
  installId: string | null
): Promise<Response> {
  if (!env.EDITING_BASE_URL) {
    return editingUnavailable(requestId, "Editing service is not configured.");
  }
  const url = new URL(
    `${env.EDITING_BASE_URL.replace(/\/+$/, "")}/v1/edit-jobs/${encodeURIComponent(editJobId)}/revisions/${encodeURIComponent(revisionId)}`
  );
  if (installId) {
    url.searchParams.set("installId", installId);
  }
  return proxyEditingJsonResponse(await fetch(url, { headers: editingHeaders(env, requestId, installId) }), requestId);
}

export async function renderEditingRevision(
  env: Env,
  editJobId: string,
  revisionId: string,
  requestId: string,
  payload: StartEditRevisionRenderRequest
): Promise<Response> {
  if (!env.EDITING_BASE_URL) {
    return editingUnavailable(requestId, "Editing service is not configured.");
  }
  const response = await fetch(
    `${env.EDITING_BASE_URL.replace(/\/+$/, "")}/v1/edit-jobs/${encodeURIComponent(editJobId)}/revisions/${encodeURIComponent(revisionId)}/render`,
    {
      method: "POST",
      headers: editingHeaders(env, requestId, payload.installId),
      body: JSON.stringify(payload)
    }
  );
  return proxyEditingJsonResponse(response, requestId);
}

function editingHeaders(env: Env, requestId: string, installId?: string | null): Headers {
  const headers = new Headers({
    "content-type": "application/json",
    "x-request-id": requestId,
    "x-trace-id": requestId
  });
  if (env.EDITING_SHARED_SECRET) {
    headers.set("x-hoops-editing-secret", env.EDITING_SHARED_SECRET);
  }
  if (installId) {
    headers.set("x-hoops-install-id", installId);
  }
  return headers;
}

async function proxyEditingJsonResponse(response: Response, requestId: string): Promise<Response> {
  const payload = (await response.json().catch(() => ({ errorCode: "editing_bad_response", errorMessage: "Editing service returned a non-JSON response." }))) as
    | EditingRenderJobResponse
    | EditingDownloadUrlResponse
    | EditJobResponse
    | EditPlanResponse
    | EditRevisionResponse
    | EditRevisionListResponse
    | Record<string, unknown>;
  return Response.json(
    {
      requestId,
      ...payload
    },
    {
      status: response.status,
      headers: {
        "x-request-id": requestId
      }
    }
  );
}

function editingUnavailable(requestId: string, message: string): Response {
  return Response.json(
    {
      requestId,
      errorCode: "editing_service_unconfigured",
      errorMessage: message,
      failureReason: message
    },
    { status: 503, headers: { "x-request-id": requestId } }
  );
}
