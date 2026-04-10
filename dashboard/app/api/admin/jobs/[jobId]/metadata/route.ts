import { NextRequest } from "next/server";
import { getControlPlaneClient } from "@/lib/control-plane";
import { readSubmission, redirectBack, respondWithAccessGate } from "@/app/api/admin/_shared";

export async function POST(request: NextRequest, context: { params: { jobId: string } }) {
  const gate = respondWithAccessGate(request, `/jobs/${context.params.jobId}`);
  if (gate) return gate;

  const body = await readSubmission(request);
  const client = getControlPlaneClient();

  await client.requestMetadata(context.params.jobId, {
    titleHint: body.titleHint,
    summaryHint: body.summaryHint,
    source: body.source ?? "manual"
  });

  return redirectBack(request, `/jobs/${context.params.jobId}`, {
    updated: "metadata-requested"
  });
}

export function PATCH(request: NextRequest, context: { params: { jobId: string } }) {
  return POST(request, context);
}
