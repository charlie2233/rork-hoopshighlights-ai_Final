import Link from "next/link";
import { headers } from "next/headers";
import { getDashboardEnv, hasControlPlaneConfig } from "@/lib/env";
import { getControlPlaneClient, type DashboardJobSummary } from "@/lib/control-plane";
import { demoJobs } from "@/lib/demo-data";
import { resolveDashboardAccess } from "@/lib/internal-allowlist";

function formatTime(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

function summaryCounts(jobs: DashboardJobSummary[]) {
  return {
    total: jobs.length,
    succeeded: jobs.filter((job) => job.status === "succeeded").length,
    active: jobs.filter((job) => job.status === "queued" || job.status === "processing").length,
    failed: jobs.filter((job) => job.status === "failed").length
  };
}

export default async function HomePage() {
  const env = getDashboardEnv();
  const access = resolveDashboardAccess(headers(), env);
  const client = getControlPlaneClient();

  let jobs = demoJobs;
  let source = "demo";
  if (hasControlPlaneConfig(env)) {
    try {
      jobs = await client.listJobs({ limit: 5 });
      source = "control-plane";
    } catch {
      jobs = demoJobs;
      source = "demo-fallback";
    }
  }

  const counts = summaryCounts(jobs);

  return (
    <div className="grid" style={{ gap: 20 }}>
      <section className="hero">
        <span className="eyebrow">Phase 4 scaffold</span>
        <h1>Review jobs, inspect clips, and keep model operations out of Vercel.</h1>
        <p>
          This dashboard is a privileged client to the Cloudflare control plane. It is built for internal review,
          clip correction, and lightweight metadata generation only. Full inference stays in the dedicated GPU service.
        </p>
        <div className="inline-actions">
          <span className="chip">Access: {access.allowed ? "allowed" : access.reason}</span>
          <span className="chip">Data source: {source}</span>
          <span className="chip">Control plane: {env.controlPlaneBaseUrl || "not configured"}</span>
        </div>
      </section>

      <section className="stats">
        <div className="card stat">
          <span className="meta">Jobs</span>
          <strong>{counts.total}</strong>
        </div>
        <div className="card stat">
          <span className="meta">Active</span>
          <strong>{counts.active}</strong>
        </div>
        <div className="card stat">
          <span className="meta">Succeeded</span>
          <strong>{counts.succeeded}</strong>
        </div>
        <div className="card stat">
          <span className="meta">Failed</span>
          <strong>{counts.failed}</strong>
        </div>
      </section>

      <section className="card panel">
        <div className="section-title">
          <div>
            <span className="eyebrow">Recent</span>
            <h2>Latest review queue</h2>
          </div>
          <Link className="button" href="/jobs">
            Open jobs
          </Link>
        </div>

        <div className="job-list">
          {jobs.map((job) => (
            <Link key={job.jobId} href={`/jobs/${job.jobId}`} className="job-row">
              <div className="job-title">
                <strong>{job.sourceFilename ?? job.jobId}</strong>
                <span className="meta">{job.jobId}</span>
              </div>
              <span className={`status ${job.status}`}>{job.status}</span>
              <div className="kv">
                <span>Model</span>
                <strong>{job.modelVersion ?? "pending"}</strong>
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
          <div className="section-title">
            <h3>Access gating</h3>
          </div>
          <p className="subtle">
            Internal allowlist is not satisfied yet. Configure `ADMIN_ALLOWED_EMAILS` or `ADMIN_ALLOWED_DOMAIN`
            before exposing this dashboard outside local development.
          </p>
        </section>
      )}
    </div>
  );
}
