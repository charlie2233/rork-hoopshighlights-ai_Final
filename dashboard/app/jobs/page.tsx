import Link from "next/link";
import { headers } from "next/headers";
import { getDashboardEnv, hasControlPlaneConfig } from "@/lib/env";
import { getControlPlaneClient, type DashboardJobSummary } from "@/lib/control-plane";
import { demoJobs } from "@/lib/demo-data";
import { resolveDashboardAccess } from "@/lib/internal-allowlist";

function firstValue(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

function formatTime(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

function scoreLabel(job: DashboardJobSummary) {
  return typeof job.confidence === "number" ? `${Math.round(job.confidence * 100)}%` : "—";
}

export default async function JobsPage({
  searchParams
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const env = getDashboardEnv();
  const access = resolveDashboardAccess(headers(), env);
  const client = getControlPlaneClient();
  const query = firstValue(searchParams?.query);
  const status = firstValue(searchParams?.status);

  let jobs = demoJobs;
  let source = "demo";

  if (hasControlPlaneConfig(env)) {
    try {
      jobs = await client.listJobs({
        query: query || undefined,
        status: status || undefined,
        limit: 25
      });
      source = "control-plane";
    } catch {
      jobs = demoJobs;
      source = "demo-fallback";
    }
  }

  return (
    <div className="grid" style={{ gap: 20 }}>
      <section className="hero">
        <span className="eyebrow">Jobs</span>
        <h1>Filter, inspect, and hand off review actions.</h1>
        <p>
          Jobs remain the top-level unit of control-plane state. This view is intentionally simple: the dashboard reads
          the authoritative state from the control plane and forwards review mutations back through the admin API.
        </p>
        <div className="inline-actions">
          <span className="chip">Source: {source}</span>
          <span className="chip">Access: {access.allowed ? "allowed" : access.reason}</span>
        </div>
      </section>

      <section className="card panel">
        <form className="toolbar" method="get">
          <div className="field" style={{ minWidth: 260 }}>
            <label htmlFor="query">Search</label>
            <input id="query" name="query" defaultValue={query} placeholder="Filename, job id, install id" />
          </div>
          <div className="field" style={{ minWidth: 180 }}>
            <label htmlFor="status">Status</label>
            <select id="status" name="status" defaultValue={status}>
              <option value="">All</option>
              <option value="created">Created</option>
              <option value="queued">Queued</option>
              <option value="processing">Processing</option>
              <option value="succeeded">Succeeded</option>
              <option value="failed">Failed</option>
              <option value="expired">Expired</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
          <button className="button" type="submit">
            Apply
          </button>
        </form>

        <div className="job-list">
          {jobs.map((job) => (
            <Link key={job.jobId} href={`/jobs/${job.jobId}`} className="job-row">
              <div className="job-title">
                <strong>{job.sourceFilename ?? job.jobId}</strong>
                <span className="meta">
                  {job.jobId} · {job.installId ?? "install-scoped"} · {job.requestId ?? "pending request id"}
                </span>
              </div>
              <span className={`status ${job.status}`}>{job.status}</span>
              <div className="kv">
                <span>Model</span>
                <strong>{job.modelVersion ?? "pending"}</strong>
              </div>
              <div className="kv">
                <span>Confidence</span>
                <strong>{scoreLabel(job)}</strong>
              </div>
              <div className="kv">
                <span>Updated</span>
                <strong>{formatTime(job.updatedAt ?? job.createdAt)}</strong>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {!access.allowed && (
        <section className="card panel muted-card">
          <p className="subtle">
            This page is available in local development, but internal allowlist rules will gate it in production.
          </p>
        </section>
      )}
    </div>
  );
}
