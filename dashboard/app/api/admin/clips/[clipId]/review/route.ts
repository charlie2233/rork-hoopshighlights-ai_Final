import { NextRequest } from "next/server";
import { getControlPlaneClient } from "@/lib/control-plane";
import { readSubmission, redirectBack, respondWithAccessGate } from "@/app/api/admin/_shared";

async function handle(request: NextRequest, params: { clipId: string }) {
  const gate = respondWithAccessGate(request, "/jobs");
  if (gate) return gate;

  const body = await readSubmission(request);
  const client = getControlPlaneClient();

  await client.reviewClip(params.clipId, {
    reviewState: body.reviewState,
    notes: body.notes,
    correctedLabel: body.correctedLabel,
    promoteToTrainingSet: body.promoteToTrainingSet === "on" || body.promoteToTrainingSet === "true",
    eventType: body.eventType,
    shotType: body.shotType,
    makeMiss: body.makeMiss
  });

  return redirectBack(request, "/jobs", {
    updated: "clip-review"
  });
}

export function POST(request: NextRequest, context: { params: { clipId: string } }) {
  return handle(request, context.params);
}

export function PATCH(request: NextRequest, context: { params: { clipId: string } }) {
  return handle(request, context.params);
}
