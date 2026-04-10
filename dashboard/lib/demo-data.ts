import type { DashboardJobDetail, DashboardJobSummary } from "@/lib/control-plane";

const now = new Date();
const recently = (minutesAgo: number) => new Date(now.getTime() - minutesAgo * 60_000).toISOString();

export const demoJobs: DashboardJobSummary[] = [
  {
    requestId: "req_demo_001",
    jobId: "job_demo_final_buzzer",
    status: "succeeded",
    stage: "Finalized clips",
    progress: 1,
    createdAt: recently(42),
    updatedAt: recently(12),
    analysisVersion: "cloud-v1",
    modelVersion: "videoMAE-v0.1+reranker-v0.1",
    confidence: 0.91,
    clipCount: 7,
    installId: "demo-install-a",
    sourceFilename: "lakers-vs-celtics.mp4"
  },
  {
    requestId: "req_demo_002",
    jobId: "job_demo_q4_comeback",
    status: "processing",
    stage: "Action recognition",
    progress: 0.63,
    createdAt: recently(18),
    updatedAt: recently(3),
    analysisVersion: "cloud-v1",
    modelVersion: "videoMAE-v0.1",
    confidence: 0.74,
    clipCount: 3,
    installId: "demo-install-b",
    sourceFilename: "playoffs-round-1.mov"
  }
];

export function getDemoJobDetail(jobId: string): DashboardJobDetail {
  const base = demoJobs.find((job) => job.jobId === jobId) ?? demoJobs[0];

  return {
    ...base,
    results: {
      clipCount: 4,
      clips: [
        {
          clipId: `${jobId}-clip-1`,
          startTime: 18.4,
          endTime: 23.2,
          label: "Made Shot",
          action: "Made Shot",
          confidence: 0.89,
          eventType: "shot",
          shotType: "midrange",
          makeMiss: "make",
          rankScore: 0.91,
          audioScore: 0.58,
          visualScore: 0.76,
          motionScore: 0.69,
          combinedScore: 0.84,
          reviewState: "approved",
          reviewerNotes: "Strong body language and scoreboard reaction.",
          correctedLabel: "Made Shot",
          promoteToTrainingSet: true,
          detectionMethod: "learned"
        },
        {
          clipId: `${jobId}-clip-2`,
          startTime: 41.0,
          endTime: 46.6,
          label: "Fast Break",
          action: "Fast Break",
          confidence: 0.78,
          eventType: "transition",
          shotType: "drive",
          makeMiss: null,
          rankScore: 0.73,
          audioScore: 0.43,
          visualScore: 0.66,
          motionScore: 0.81,
          combinedScore: 0.77,
          reviewState: "needs_review",
          reviewerNotes: null,
          correctedLabel: null,
          promoteToTrainingSet: false,
          detectionMethod: "learned"
        }
      ],
      diagnostics: {
        processingMs: 8421,
        backendModelVersion: "videoMAE-v0.1+reranker-v0.1",
        modelVersion: "videoMAE-v0.1+reranker-v0.1",
        candidateSegments: 12,
        finalSegments: 4,
        usedVideoIntelligence: false,
        usedGeminiRelabeling: false
      }
    },
    assets: [
      {
        assetId: `${jobId}-thumb`,
        kind: "thumbnail",
        label: "Poster frame",
        url: "https://example.com/thumbnail.jpg",
        contentType: "image/jpeg",
        sizeBytes: 193_248
      },
      {
        assetId: `${jobId}-manifest`,
        kind: "result-manifest",
        label: "Result manifest",
        url: "https://example.com/result.json",
        contentType: "application/json",
        sizeBytes: 4_192
      }
    ],
    timeline: [
      { at: recently(18), status: "created", stage: "Accepted upload request" },
      { at: recently(17), status: "queued", stage: "Queued on Cloudflare" },
      { at: recently(15), status: "processing", stage: "Candidate proposal" },
      { at: recently(12), status: "succeeded", stage: "Finalized clips" }
    ]
  };
}
