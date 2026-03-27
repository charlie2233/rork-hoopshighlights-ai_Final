import type { Env } from "../env";
import type { JobMutationInput, JobRecord, JobBootstrapInput } from "../types";

function doStub(env: Env, jobId: string): ReturnType<Env["JOB_STATE"]["get"]> {
  return env.JOB_STATE.get(env.JOB_STATE.idFromName(jobId));
}

export async function bootstrapJob(env: Env, record: JobRecord): Promise<JobRecord> {
  const response = await doStub(env, record.jobId).fetch("https://do/bootstrap", {
    method: "POST",
    headers: {
      "content-type": "application/json"
    },
    body: JSON.stringify({ record } satisfies JobBootstrapInput)
  });
  return (await response.json()) as JobRecord;
}

export async function getJobSnapshot(env: Env, jobId: string): Promise<JobRecord | null> {
  const response = await doStub(env, jobId).fetch("https://do/snapshot", { method: "GET" });
  if (response.status === 404) {
    return null;
  }
  return (await response.json()) as JobRecord;
}

export async function updateJobState(
  env: Env,
  jobId: string,
  patch: Partial<JobRecord>,
  input?: {
    requestId?: string;
    traceId?: string;
    eventType?: string;
    message?: string;
    payload?: unknown;
  }
): Promise<JobRecord> {
  const response = await doStub(env, jobId).fetch("https://do/patch", {
    method: "PATCH",
    headers: {
      "content-type": "application/json"
    },
    body: JSON.stringify({
      patch,
      requestId: input?.requestId ?? "",
      traceId: input?.traceId ?? "",
      eventType: input?.eventType,
      message: input?.message,
      payload: input?.payload
    } satisfies JobMutationInput)
  });
  return (await response.json()) as JobRecord;
}

export async function deleteJobState(env: Env, jobId: string): Promise<JobRecord | null> {
  const response = await doStub(env, jobId).fetch("https://do/delete", { method: "DELETE" });
  if (response.status === 404) {
    return null;
  }
  return (await response.json()) as JobRecord;
}
