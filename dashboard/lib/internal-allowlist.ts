import { getDashboardEnv, type DashboardEnv } from "@/lib/env";

const HEADER_CANDIDATES = [
  "x-vercel-user-email",
  "x-vercel-auth-user-email",
  "x-authenticated-user-email",
  "x-forwarded-email",
  "x-user-email"
];

export type DashboardAccess = {
  allowed: boolean;
  email: string | null;
  matchedHeader: string | null;
  reason: string;
};

type HeaderLike = Pick<Headers, "get" | "has">;

function normalizeEmail(value: string | null): string | null {
  const email = value?.trim().toLowerCase() ?? null;
  return email && email.length > 0 ? email : null;
}

function readHeader(headers: HeaderLike, name: string): string | null {
  return normalizeEmail(headers.get(name));
}

export function resolveDashboardAccess(headers: HeaderLike, env: DashboardEnv = getDashboardEnv()): DashboardAccess {
  const matchedHeader = HEADER_CANDIDATES.find((header) => headers.has(header)) ?? null;
  const email = matchedHeader ? readHeader(headers, matchedHeader) : null;

  if (process.env.NODE_ENV !== "production" && env.allowlistedEmails.length === 0 && !env.allowedEmailDomain) {
    return {
      allowed: true,
      email,
      matchedHeader,
      reason: "development-mode"
    };
  }

  if (!email) {
    return {
      allowed: false,
      email: null,
      matchedHeader: null,
      reason: "missing-user-email"
    };
  }

  if (env.allowlistedEmails.includes(email)) {
    return {
      allowed: true,
      email,
      matchedHeader,
      reason: "allowlisted-email"
    };
  }

  if (env.allowedEmailDomain && email.endsWith(`@${env.allowedEmailDomain}`)) {
    return {
      allowed: true,
      email,
      matchedHeader,
      reason: "allowlisted-domain"
    };
  }

  return {
    allowed: false,
    email,
    matchedHeader,
    reason: "email-not-allowed"
  };
}
