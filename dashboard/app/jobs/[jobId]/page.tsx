import Link from "next/link";
import { headers } from "next/headers";
import { getDashboardEnv, hasControlPlaneConfig } from "@/lib/env";
import { getControlPlaneClient, type DashboardJobDetail } from "@/lib/control-plane";
import { getDemoJobDetail } from "@/lib/demo-data";
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

function formatDuration(startTime: number, endTime: number) {
  return `${startTime.toFixed(1)}s - ${endTime.toFixed(1)}s`;
}

export default async function JobDetailPage({
  params
}: {
  params: { jobId: string };
}) {
  const env = getDashboardEnv();
  const access = resolveDashboardAccess(headers(), env);
  const client = getControlPlaneClient();
  const jobId = params.jobId;

  let job: DashboardJobDetail = getDemoJobDetail(jobId);
  let source = "demo";

  if (hasControlPlaneConfig(env)) {
    try {
      const baseJob = await client.getJob(jobId);
      const assets = await client.getJobAssets(jobId).catch(() => []);
      job = { ...baseJob, assets };
      source = "control-plane";
    } catch {
      job = getDemoJobDetail(jobId);
      source = "demo-fallback";
    }
  } else {
    job = getDemoJobDetail(jobId);
  }

  const clips = job.results?.clips ?? [];
  const assets = job.assets ?? [];

  return (
    <div className="grid" style={{ gap: 20 }}>
      <section className="hero">
        <span className="eyebrow">Job detail</span>
        <h1>{job.sourceFilename ?? job.jobId}</h1>
        <p>
          This page reads job state, clips, artifacts, and diagnostics from the control plane. Review actions are
          forwarded back through the dashboard API, but inference itself stays outside Vercel.
        </p>
        <div className="inline-actions">
          <Link className="button" href="/jobs">
            Back to jobs
          </Link>
          <span className="chip">Source: {source}</span>
          <span className={`status ${job.status}`}>{job.status}</span>
        </div>
      </section>

      <section className="stats">
        <div className="card stat">
          <span className="meta">Progress</span>
          <strong>{Math.round((job.progress ?? 0) * 100)}%</strong>
        </div>
        <div className="card stat">
          <span className="meta">Model</span>
          <strong>{job.modelVersion ?? "pending"}</strong>
        </div>
        <div className="card stat">
          <span className="meta">Confidence</span>
          <strong>{typeof job.confidence === "number" ? `${Math.round(job.confidence * 100)}%` : "—"}</strong>
        </div>
        <div className="card stat">
          <span className="meta">Failure</span>
          <strong>{job.failureReason ?? "none"}</strong>
        </div>
      </section>

      <div className="two-col">
        <section className="card panel">
          <div className="section-title">
            <div>
              <span className="eyebrow">Review</span>
              <h2>Job actions</h2>
            </div>
          </div>

          <div className="stack">
            <form className="inline-form" action={`/api/admin/jobs/${encodeURIComponent(job.jobId)}/review`} method="post">
              <div className="toolbar" style={{ marginBottom: 0 }}>
                <div className="field" style={{ minWidth: 220 }}>
                  <label htmlFor="reviewState">Job review state</label>
                  <select id="reviewState" name="reviewState" defaultValue="approved">
                    <option value="approved">Approved</option>
                    <option value="needs_review">Needs review</option>
                    <option value="rejected">Rejected</option>
                  </select>
                </div>
                <div className="field" style={{ flex: 1, minWidth: 260 }}>
                  <label htmlFor="summary">Summary</label>
                  <input id="summary" name="summary" placeholder="Reviewer summary" />
                </div>
                <div className="field" style={{ flex: 1, minWidth: 260 }}>
                  <label htmlFor="notes">Notes</label>
                  <input id="notes" name="notes" placeholder="Optional notes for the control plane" />
                </div>
              </div>
              <div className="inline-actions">
                <button className="button" type="submit">
                  Save job review
                </button>
              </div>
            </form>

            <form className="inline-form" action={`/api/admin/jobs/${encodeURIComponent(job.jobId)}/metadata`} method="post">
              <div className="toolbar" style={{ marginBottom: 0 }}>
                <div className="field" style={{ flex: 1, minWidth: 260 }}>
                  <label htmlFor="titleHint">Title hint</label>
                  <input id="titleHint" name="titleHint" placeholder="Suggest a highlight reel title" />
                </div>
                <div className="field" style={{ flex: 1, minWidth: 260 }}>
                  <label htmlFor="summaryHint">Summary hint</label>
                  <input id="summaryHint" name="summaryHint" placeholder="Optional summary prompt" />
                </div>
              </div>
              <button className="button" type="submit">
                Request metadata generation
              </button>
            </form>
          </div>
        </section>

        <section className="card panel">
          <div className="section-title">
            <div>
              <span className="eyebrow">Summary</span>
              <h2>Job metadata</h2>
            </div>
          </div>

          <div className="stack">
            <div className="kv">
              <span>Job ID</span>
              <strong>{job.jobId}</strong>
            </div>
            <div className="kv">
              <span>Request ID</span>
              <strong>{job.requestId ?? "pending"}</strong>
            </div>
            <div className="kv">
              <span>Install ID</span>
              <strong>{job.installId ?? "install-scoped"}</strong>
            </div>
            <div className="kv">
              <span>Stage</span>
              <strong>{job.stage}</strong>
            </div>
            <div className="kv">
              <span>Created</span>
              <strong>{formatTime(job.createdAt)}</strong>
            </div>
            <div className="kv">
              <span>Updated</span>
              <strong>{formatTime(job.updatedAt)}</strong>
            </div>
          </div>
        </section>
      </div>

      <section className="card panel">
        <div className="section-title">
          <div>
            <span className="eyebrow">Artifacts</span>
            <h2>Downloads and manifests</h2>
          </div>
          <span className="chip">{assets.length} assets</span>
        </div>

        <div className="asset-list">
          {assets.length === 0 ? (
            <div className="job-row muted-card">
              <strong>No signed assets yet.</strong>
              <span className="subtle">
                The control plane will surface source, result, and derived artifact URLs here once the upload and
                inference path is wired.
              </span>
            </div>
          ) : (
            assets.map((asset) => (
              <div key={asset.assetId} className="asset-row">
                <div className="job-title">
                  <strong>{asset.label}</strong>
                  <span className="meta">
                    {asset.kind} · {asset.contentType ?? "unknown type"}
                  </span>
                </div>
                <div className="inline-actions">
                  <a className="button" href={asset.url} target="_blank" rel="noreferrer">
                    Open
                  </a>
                  <span className="chip">
                    {asset.sizeBytes ? `${Math.round(asset.sizeBytes / 1024)} KB` : "size pending"}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="card panel">
        <div className="section-title">
          <div>
            <span className="eyebrow">Clips</span>
            <h2>Detected highlights</h2>
          </div>
          <span className="chip">{clips.length} clips</span>
        </div>

        <div className="clip-list">
          {clips.length === 0 ? (
            <div className="job-row muted-card">
              <strong>No clips returned yet.</strong>
              <span className="subtle">Once the inference service is connected, clips and review state will surface here.</span>
            </div>
          ) : (
            clips.map((clip) => (
              <article key={clip.clipId} className="clip-row">
                <div className="stack">
                  <div className="clip-header">
                    <div className="job-title">
                      <strong>{clip.label}</strong>
                      <span className="meta">
                        {clip.clipId} · {formatDuration(clip.startTime, clip.endTime)}
                      </span>
                    </div>
                    <span className="chip">Confidence {Math.round((clip.confidence ?? 0) * 100)}%</span>
                  </div>
                  <div className="inline-actions">
                    <span className="chip">Event {clip.eventType ?? "pending"}</span>
                    <span className="chip">Shot {clip.shotType ?? "pending"}</span>
                    <span className="chip">Make/Miss {clip.makeMiss ?? "pending"}</span>
                    <span className="chip">Rank {clip.rankScore?.toFixed(2) ?? "—"}</span>
                  </div>
                  <div className="subtle">
                    Scores: audio {clip.audioScore?.toFixed(2) ?? "—"}, visual {clip.visualScore?.toFixed(2) ?? "—"},
                    motion {clip.motionScore?.toFixed(2) ?? "—"}, combined {clip.combinedScore?.toFixed(2) ?? "—"}.
                  </div>
                </div>

                <form className="clip-form" action={`/api/admin/clips/${encodeURIComponent(clip.clipId)}/review`} method="post">
                  <div className="toolbar" style={{ marginBottom: 0 }}>
                    <div className="field" style={{ minWidth: 160 }}>
                      <label htmlFor={`reviewState-${clip.clipId}`}>Review state</label>
                      <select id={`reviewState-${clip.clipId}`} name="reviewState" defaultValue={clip.reviewState ?? "approved"}>
                        <option value="approved">Approved</option>
                        <option value="needs_review">Needs review</option>
                        <option value="rejected">Rejected</option>
                      </select>
                    </div>
                    <div className="field" style={{ minWidth: 160 }}>
                      <label htmlFor={`correctedLabel-${clip.clipId}`}>Corrected label</label>
                      <input id={`correctedLabel-${clip.clipId}`} name="correctedLabel" defaultValue={clip.correctedLabel ?? ""} placeholder="Optional" />
                    </div>
                  </div>
                  <div className="field">
                    <label htmlFor={`notes-${clip.clipId}`}>Notes</label>
                    <textarea id={`notes-${clip.clipId}`} name="notes" defaultValue={clip.reviewerNotes ?? ""} placeholder="Reviewer notes" />
                  </div>
                  <label className="badge" style={{ width: "fit-content" }}>
                    <input type="checkbox" name="promoteToTrainingSet" defaultChecked={Boolean(clip.promoteToTrainingSet)} />
                    Promote to training set
                  </label>
                  <button className="button" type="submit">
                    Save clip review
                  </button>
                </form>
              </article>
            ))
          )}
        </div>
      </section>

      <section className="card panel">
        <div className="section-title">
          <div>
            <span className="eyebrow">Timeline</span>
            <h2>Job events</h2>
          </div>
        </div>

        <div className="asset-list">
          {(job.timeline ?? []).length === 0 ? (
            <div className="job-row muted-card">
              <strong>No timeline events.</strong>
              <span className="subtle">The control plane will populate the event log for each state transition.</span>
            </div>
          ) : (
            (job.timeline ?? []).map((event) => (
              <div key={`${event.at}-${event.stage}`} className="job-row" style={{ gridTemplateColumns: "0.6fr 0.8fr 1.2fr" }}>
                <span className="meta">{formatTime(event.at)}</span>
                <span className={`status ${event.status}`}>{event.status}</span>
                <span>{event.stage}</span>
              </div>
            ))
          )}
        </div>
      </section>

      {!access.allowed && (
        <section className="card panel muted-card">
          <p className="subtle">Access is currently gated by the internal allowlist helper.</p>
        </section>
      )}
    </div>
  );
}
