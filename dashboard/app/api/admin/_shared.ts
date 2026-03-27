import { NextRequest, NextResponse } from "next/server";
import { resolveDashboardAccess } from "@/lib/internal-allowlist";

export async function readSubmission(request: NextRequest): Promise<Record<string, string>> {
  const contentType = request.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    const payload = (await request.json().catch(() => ({}))) as Record<string, unknown>;
    return Object.fromEntries(
      Object.entries(payload).map(([key, value]) => [key, typeof value === "string" ? value : String(value ?? "")])
    );
  }

  const formData = await request.formData();
  return Object.fromEntries(
    Array.from(formData.entries()).map(([key, value]) => [key, value instanceof File ? value.name : String(value)])
  );
}

function redirectTarget(request: NextRequest, fallbackPath: string) {
  const referer = request.headers.get("referer");
  if (referer) {
    try {
      const candidate = new URL(referer);
      if (candidate.origin === new URL(request.url).origin) {
        return candidate;
      }
    } catch {
      // Fall through to the internal fallback path.
    }
  }

  return new URL(fallbackPath, request.url);
}

export function respondWithAccessGate(request: NextRequest, fallbackPath: string) {
  const access = resolveDashboardAccess(request.headers);
  if (access.allowed) {
    return null;
  }

  const url = redirectTarget(request, fallbackPath);
  url.searchParams.set("access", access.reason);
  const accept = request.headers.get("accept") ?? "";
  if (accept.includes("application/json")) {
    return NextResponse.json({ error: access.reason }, { status: 403 });
  }

  return NextResponse.redirect(url);
}

export function redirectBack(request: NextRequest, fallbackPath: string, query?: Record<string, string>) {
  const url = redirectTarget(request, fallbackPath);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value) {
      url.searchParams.set(key, value);
    }
  }
  return NextResponse.redirect(url);
}
