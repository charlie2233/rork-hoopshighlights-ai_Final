import type { CloudClip, CloudAnalysisResult, InferenceCallbackPayload, JobRecord, QueueJobMessage } from "../types";

type SeededRng = () => number;

const STUB_MODEL_VERSION = "stub-inference-v1";
const LABELS = ["Made Shot", "Fast Break", "Dunk", "Layup", "Steal", "Block", "Three Pointer"] as const;

export function buildStubInferenceCallbackPayload(job: JobRecord, message: QueueJobMessage): InferenceCallbackPayload {
  const seed = hashString([job.jobId, message.requestId, job.installId, job.analysisVersion].join("|"));
  const rng = createSeededRng(seed);
  const clipCount = job.durationSeconds >= 240 ? 3 : 2;
  const clips = buildStubClips(job, rng, clipCount);
  const resultConfidence = roundToFour(clips.reduce((sum, clip) => sum + clip.confidence, 0) / clips.length);
  const diagnostics = {
    processingMs: 625 + (seed % 400),
    backendModelVersion: `${STUB_MODEL_VERSION}+${job.analysisVersion}`,
    usedVideoIntelligence: false,
    usedGeminiRelabeling: false,
    candidateSegments: clips.length,
    finalSegments: clips.length
  };

  const result: CloudAnalysisResult = {
    requestId: message.requestId,
    clipCount: clips.length,
    clips,
    diagnostics,
    resultConfidence
  };

  return {
    jobId: job.jobId,
    status: "succeeded",
    requestId: message.requestId,
    modelVersion: diagnostics.backendModelVersion,
    confidence: resultConfidence,
    resultConfidence,
    results: result
  };
}

function buildStubClips(job: JobRecord, rng: SeededRng, clipCount: number): CloudClip[] {
  const duration = Math.max(job.durationSeconds, 30);
  const span = Math.max(4, Math.min(12, duration * 0.18));
  const step = duration / (clipCount + 1);
  const clips: CloudClip[] = [];

  for (let index = 0; index < clipCount; index += 1) {
    const startBase = Math.max(0, step * (index + 0.55));
    const jitter = (rng() - 0.5) * Math.min(2.5, duration * 0.05);
    const startTime = clamp(startBase + jitter, 0, Math.max(0, duration - span));
    const endTime = clamp(startTime + span, startTime + 1, duration);
    const label = LABELS[Math.floor(rng() * LABELS.length) % LABELS.length]!;
    const confidence = roundToFour(0.78 + rng() * 0.17);
    const motionScore = roundToFour(0.6 + rng() * 0.3);
    const visualScore = roundToFour(0.55 + rng() * 0.35);
    const audioScore = roundToFour(0.45 + rng() * 0.3);
    const combinedScore = roundToFour((motionScore + visualScore + audioScore) / 3);
    const rankScore = roundToFour(Math.min(1, combinedScore + 0.05 + rng() * 0.1));
    const eventType = inferEventType(label);

    clips.push({
      startTime: roundToFour(startTime),
      endTime: roundToFour(endTime),
      confidence,
      label,
      action: label,
      audioScore,
      visualScore,
      motionScore,
      combinedScore,
      detectionMethod: "cloud",
      shouldAutoKeep: confidence >= 0.82,
      shouldEnableSlowMotion: label === "Dunk",
      eventType,
      shotType: inferShotType(label),
      makeMiss: label === "Made Shot" || label === "Three Pointer" || label === "Layup" ? "make" : "unknown",
      rankScore,
      reviewState: "unreviewed",
      reviewerNotes: null
    });
  }

  return clips;
}

function inferEventType(label: string): string {
  switch (label) {
    case "Made Shot":
    case "Three Pointer":
    case "Layup":
    case "Dunk":
      return "shot";
    case "Fast Break":
      return "transition";
    case "Steal":
      return "defense";
    case "Block":
      return "defense";
    default:
      return "highlight";
  }
}

function inferShotType(label: string): string {
  switch (label) {
    case "Three Pointer":
      return "three_pointer";
    case "Layup":
      return "layup";
    case "Dunk":
      return "dunk";
    case "Made Shot":
      return "field_goal";
    default:
      return "unknown";
  }
}

function createSeededRng(seed: number): SeededRng {
  let state = seed >>> 0;
  return () => {
    state += 0x6D2B79F5;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(input: string): number {
  let hash = 2166136261;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function clamp(value: number, lower: number, upper: number): number {
  return Math.max(lower, Math.min(upper, value));
}

function roundToFour(value: number): number {
  return Math.round(value * 10000) / 10000;
}
