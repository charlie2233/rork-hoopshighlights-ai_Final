# HoopsClips Detection V2 Contract

Branch: `feat/detection-v2`

## Pipeline Contract

Detection is staged and cloud-backend owned:

1. `proposal`: audio/visual windows or provider candidates identify likely event windows.
2. `embedding_rerank`: CLIP-like semantic adapter reranks proposals against basketball product labels.
3. `classifier`: baseline video classifier emits raw event labels and top-label scores.
4. `merge`: overlapping candidates are merged into final reviewable clip candidates.
5. `taxonomy`: research/raw labels map to product labels and canonical metadata.

## New Direct Detection API

`POST /v2/detection/analyze`

Request:

```json
{
  "jobId": "job_detection_123",
  "requestId": "request_123",
  "uploadTraceId": "upload_trace_123",
  "traceId": "trace_123",
  "installId": "install_12345678",
  "sourceUrl": "https://signed-upload-read-url.example/video.mp4",
  "sourceObjectKey": "uploads/install_123/source.mp4",
  "filename": "source.mp4",
  "contentType": "video/mp4",
  "durationSeconds": 42.5,
  "appVersion": "1.0.0",
  "analysisVersion": "detection-v2",
  "schemaVersion": "2026-06-23",
  "modelVersion": "detection-pipeline-v2"
}
```

Response:

```json
{
  "clipCount": 2,
  "clips": [
    {
      "startTime": 1.2,
      "endTime": 6.8,
      "eventCenter": 4.1,
      "confidence": 0.88,
      "label": "Dunk",
      "action": "Dunk",
      "canonicalLabel": "dunk",
      "eventFamily": "shot",
      "eventSubtype": "finish",
      "shotSubtype": "dunk",
      "outcome": "made",
      "audioScore": 0.7,
      "visualScore": 0.8,
      "motionScore": 0.82,
      "combinedScore": 0.86,
      "detectionMethod": "cloud",
      "shouldAutoKeep": true,
      "shouldEnableSlowMotion": true,
      "rankScore": 0.9,
      "pipelineStage": "merged_candidate",
      "pipelineVersion": "detection-pipeline-v2",
      "topLabels": [{"label": "Dunk", "confidence": 0.92, "rawLabel": "Dunk", "modelVersion": "r2plus1d-baseline-v1"}],
      "rawTopLabels": [{"rawLabel": "Dunk", "confidence": 0.92, "canonicalLabel": "dunk", "modelVersion": "r2plus1d-baseline-v1"}],
      "scores": {
        "proposalScore": 0.86,
        "embeddingScore": 0.84,
        "classifierScore": 0.9,
        "mergeScore": 0.88,
        "finalScore": 0.88
      },
      "provenance": {
        "proposal": {"stage": "proposal", "status": "applied", "source": "native_audio_visual_windows", "score": 0.86, "rank": 1},
        "embeddingRerank": {"stage": "embedding_rerank", "status": "applied", "source": "clip_like_semantic_adapter", "modelId": "openclip-adapter", "modelVersion": "openclip-siglip-compatible-v1", "adapter": "openclip", "score": 0.84, "rank": 1},
        "classifier": {"stage": "classifier", "status": "applied", "source": "baseline_video_classifier", "modelId": "r2plus1d-baseline", "modelVersion": "r2plus1d-baseline-v1", "adapter": "r2plus1d", "rawLabel": "Dunk", "score": 0.9},
        "merge": {"stage": "merge", "status": "applied", "source": "temporal_merge", "score": 0.88, "rank": 1},
        "taxonomy": {"stage": "taxonomy", "status": "applied", "source": "basketball-detection-taxonomy-v1", "rawLabel": "Dunk"}
      }
    }
  ],
  "candidateClips": [
    {
      "startTime": 1.2,
      "endTime": 6.8,
      "eventCenter": 4.1,
      "confidence": 0.88,
      "label": "Dunk",
      "action": "Dunk",
      "canonicalLabel": "dunk",
      "eventFamily": "shot",
      "eventSubtype": "finish",
      "shotSubtype": "dunk",
      "outcome": "made",
      "audioScore": 0.7,
      "visualScore": 0.8,
      "motionScore": 0.82,
      "combinedScore": 0.86,
      "detectionMethod": "cloud",
      "shouldAutoKeep": true,
      "shouldEnableSlowMotion": true,
      "rankScore": 0.9,
      "pipelineStage": "merged_candidate",
      "pipelineVersion": "detection-pipeline-v2",
      "scores": {
        "proposalScore": 0.86,
        "embeddingScore": 0.84,
        "classifierScore": 0.9,
        "mergeScore": 0.88,
        "finalScore": 0.88
      },
      "provenance": {
        "proposal": {"stage": "proposal", "status": "applied", "source": "native_audio_visual_windows", "score": 0.86, "rank": 1},
        "embeddingRerank": {"stage": "embedding_rerank", "status": "applied", "source": "clip_like_semantic_adapter", "adapter": "openclip", "score": 0.84, "rank": 1},
        "classifier": {"stage": "classifier", "status": "applied", "source": "baseline_video_classifier", "adapter": "r2plus1d", "rawLabel": "Dunk", "score": 0.9},
        "merge": {"stage": "merge", "status": "applied", "source": "temporal_merge", "score": 0.88, "rank": 1},
        "taxonomy": {"stage": "taxonomy", "status": "applied", "source": "basketball-detection-taxonomy-v1", "rawLabel": "Dunk"}
      }
    }
  ],
  "diagnostics": {
    "processingMs": 1250,
    "backendModelVersion": "cloud-v1+detection-pipeline-v2",
    "usedVideoIntelligence": false,
    "usedGeminiRelabeling": false,
    "candidateSegments": 12,
    "finalSegments": 2,
    "proposalSegments": 12,
    "embeddedSegments": 12,
    "classifiedSegments": 12,
    "mergedCandidateSegments": 2,
    "usedSemanticRerank": true,
    "taxonomyVersion": "basketball-detection-taxonomy-v1"
  },
  "resultConfidence": 0.84,
  "pipeline": {
    "pipelineVersion": "detection-pipeline-v2",
    "stages": ["proposal", "embedding_rerank", "classifier", "merge"],
    "proposalCount": 12,
    "rerankedCount": 12,
    "classifiedCount": 12,
    "mergedCandidateCount": 2,
    "models": {
      "classifier": "r2plus1d-baseline-v1",
      "embedding": "openclip-siglip-compatible-v1"
    },
    "taxonomyVersion": "basketball-detection-taxonomy-v1",
    "fallbackUsed": false,
    "fallbackReasons": []
  },
  "detectedTeams": [],
  "teamSelection": null
}
```

## Compatibility Layer

Existing clients remain supported:

- `POST /v1/analysis/jobs` is unchanged.
- `POST /v1/analysis/jobs/{jobId}/start` is unchanged.
- `GET /v1/analysis/jobs/{jobId}` is unchanged.
- `POST /v1/analyze` still accepts Worker dispatch and posts callbacks.
- `POST /api/ai/analyze` is a legacy alias for the cloud upload job creation contract.
- `GET /api/ai/result/{jobId}` is a legacy alias for the cloud job status/result contract.

Old result readers can continue reading `results.clipCount`, `results.clips`, and `results.diagnostics`. New readers should prefer `results.candidateClips` when present; it has the same item shape as `results.clips` plus provenance and pipeline scores.

## Fallback Contract

Missing inference/editing providers must fail the queued job instead of returning synthetic stub AI. Embedding fallback is allowed only inside `provenance.embeddingRerank.status="fallback"` and must set `pipeline.fallbackUsed=true` with a reason such as `embedding_adapter_unavailable`.
