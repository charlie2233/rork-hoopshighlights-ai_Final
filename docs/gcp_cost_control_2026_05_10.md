# GCP Cost Control Update - 2026-05-10

## Project

- Project: `hoopsclips-9d38f`
- Billing account: `01A094-2D70EF-1A37D2`
- Operator account: `charliehan112@gmail.com`

## What changed

### Cloud Run inference idle floor

The staging inference service was kept warm all month:

- Service: `hoopsclips-inference-staging`
- Region: `us-central1`
- Previous minimum instances: `1`
- CPU: `2`
- Memory: `8Gi`

This was the main recurring cost driver. One idle minimum instance at this size is roughly a $60+ monthly Cloud Run cost before other storage/build/logging charges.

Updated:

```bash
gcloud run services update hoopsclips-inference-staging \
  --project=hoopsclips-9d38f \
  --region=us-central1 \
  --min-instances=0
```

Verified after update:

- Latest revision: `hoopsclips-inference-staging-00036-p7l`
- Minimum instances: unset, which means `0`
- Maximum instances: `2`
- CPU: `2`
- Memory: `8Gi`
- `/readyz` returned ready with ffmpeg, ffprobe, callback, ingress, and R2 configured.

Expected impact:

- The clip-detection service remains deployed.
- Idle monthly cost should drop substantially.
- First request after idle may be slower because the model container can cold start.

### Artifact Registry cleanup policy

The `hoopsclips` Docker repository was storing about `105673 MB`. Most of that was old `hoopsclips-inference-staging` images, each about `3.2 GB`.

Added Artifact Registry cleanup policies:

- Delete versions older than `14d`.
- Keep the most recent `5` versions per package.
- Dry run is disabled, so Artifact Registry will apply deletion asynchronously.

Policy:

```json
[
  {
    "name": "delete-versions-older-than-14d",
    "action": {"type": "Delete"},
    "condition": {
      "tagState": "any",
      "olderThan": "14d"
    }
  },
  {
    "name": "keep-most-recent-5-per-package",
    "action": {"type": "Keep"},
    "mostRecentVersions": {
      "keepCount": 5
    }
  }
]
```

Expected impact:

- Current and recent rollback images are retained.
- Older staging images should be removed by Artifact Registry background cleanup.
- Repository storage cost should drop after cleanup runs.

## What did not change

- No Cloud Run service was deleted.
- No secrets were changed.
- No production backend cutover was made.
- The AI Edit rendering service `hoopclips-editing-staging` was left running with its existing config.
- The legacy `hoops-ai-editing-staging` service was not changed.

## Follow-ups

- Watch the billing report over the next 24-48 hours.
- If staging clip detection latency becomes painful, consider using scheduled warm windows instead of `min-instances=1` all month.
- Rotate or remove the old Firebase Admin user-managed service account key if it is no longer needed.
- Add a budget alert for this billing account before external beta.
