import { NextRequest, NextResponse } from "next/server";
import { getControlPlaneClient } from "@/lib/control-plane";
import { readSubmission, redirectBack, respondWithAccessGate } from "@/app/api/admin/_shared";

async function handle(request: NextRequest, params: { jobId: string }) {
  const gate = respondWithAccessGate(request, `/jobs/${params.jobId}`);
  if (gate) return gate;

  const body = await readSubmission(request);
  const client = getControlPlaneClient();

  await client.reviewJob(params.jobId, {
    reviewState: body.reviewState,
    summary: body.summary,
    notes: body.notes,
    failureReason: body.failureReason,
    modelVersion: body.modelVersion
  });

  return redirectBack(request, `/jobs/${params.jobId}`, {
    updated: "job-review"
  });
}

export function POST(request: NextRequest, context: { params: { jobId: string } }) {
  return handle(request, context.params);
}

export function PATCH(request: NextRequest, context: { params: { jobId: string } }) {
  return handle(request, context.params);
}
