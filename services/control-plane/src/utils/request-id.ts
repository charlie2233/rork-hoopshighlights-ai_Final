export function resolveRequestId(request: Request): string {
  const existing = request.headers.get("x-request-id")?.trim();
  return existing ? existing : crypto.randomUUID();
}

export function withRequestIdHeaders(requestId: string, headers?: HeadersInit): Headers {
  const responseHeaders = new Headers(headers);
  responseHeaders.set("x-request-id", requestId);
  return responseHeaders;
}

export function jsonResponse<T>(body: T, init: ResponseInit = {}, requestId: string): Response {
  const headers = withRequestIdHeaders(requestId, init.headers);
  headers.set("content-type", "application/json; charset=utf-8");
  return Response.json(body, { ...init, headers });
}

export function emptyResponse(status: number, requestId: string): Response {
  return new Response(null, {
    status,
    headers: withRequestIdHeaders(requestId)
  });
}

export async function readJson<T>(request: Request): Promise<T> {
  return (await request.json()) as T;
}
