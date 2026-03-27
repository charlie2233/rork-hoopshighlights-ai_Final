export type DashboardEnv = {
  dashboardName: string;
  environment: string;
  controlPlaneBaseUrl: string;
  controlPlaneServiceToken: string;
  allowlistedEmails: string[];
  allowedEmailDomain: string | null;
  openAiApiKey: string | null;
  requestTimeoutMs: number;
};

function splitCsv(value: string | undefined): string[] {
  return (value ?? "")
    .split(",")
    .map((entry) => entry.trim().toLowerCase())
    .filter(Boolean);
}

function trimOrNull(value: string | undefined): string | null {
  const trimmed = (value ?? "").trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function getDashboardEnv(): DashboardEnv {
  const controlPlaneBaseUrl = (process.env.CLOUDFLARE_CONTROL_PLANE_BASE_URL ?? "").trim().replace(/\/+$/, "");
  const controlPlaneServiceToken = (process.env.CLOUDFLARE_SERVICE_TOKEN ?? "").trim();
  const parsedTimeout = Number.parseInt(process.env.DASHBOARD_REQUEST_TIMEOUT_MS ?? "15000", 10);

  return {
    dashboardName: (process.env.NEXT_PUBLIC_DASHBOARD_NAME ?? "HoopsClips Review").trim(),
    environment: (process.env.NEXT_PUBLIC_DASHBOARD_ENV ?? process.env.VERCEL_ENV ?? process.env.NODE_ENV ?? "development").trim(),
    controlPlaneBaseUrl,
    controlPlaneServiceToken,
    allowlistedEmails: splitCsv(process.env.ADMIN_ALLOWED_EMAILS),
    allowedEmailDomain: trimOrNull(process.env.ADMIN_ALLOWED_DOMAIN)?.toLowerCase() ?? null,
    openAiApiKey: trimOrNull(process.env.OPENAI_API_KEY),
    requestTimeoutMs: Number.isFinite(parsedTimeout) && parsedTimeout > 0 ? parsedTimeout : 15000
  };
}

export function hasControlPlaneConfig(env: DashboardEnv = getDashboardEnv()): boolean {
  return env.controlPlaneBaseUrl.length > 0 && env.controlPlaneServiceToken.length > 0;
}
