import type { Env } from "./env";
import { resolveRequestId, jsonResponse } from "./utils/request-id";
import { routePublicRequest } from "./routes/public";
import { routeInternalRequest } from "./routes/internal";
import { routeAdminRequest } from "./routes/admin";
import { handleQueueBatch } from "./queue/consumer";
import type { QueueJobMessage } from "./types";
import type { MessageBatch } from "@cloudflare/workers-types";

export { JobStateDO } from "./do/job-state";

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const requestId = resolveRequestId(request);

    try {
      const publicResponse = await routePublicRequest(request, env, ctx, requestId);
      if (publicResponse) {
        return publicResponse;
      }

      const internalResponse = await routeInternalRequest(request, env, requestId);
      if (internalResponse) {
        return internalResponse;
      }

      const adminResponse = await routeAdminRequest(request, env, requestId);
      if (adminResponse) {
        return adminResponse;
      }

      return jsonResponse(
        {
          requestId,
          errorCode: "not_found",
          errorMessage: "Route not found.",
          failureReason: "Route not found."
        },
        { status: 404 },
        requestId
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected control plane failure.";
      return jsonResponse(
        {
          requestId,
          errorCode: "internal_error",
          errorMessage: message,
          failureReason: message
        },
        { status: 500 },
        requestId
      );
    }
  },
  async queue(batch: MessageBatch<QueueJobMessage>, env: Env): Promise<void> {
    await handleQueueBatch(batch, env);
  }
};
