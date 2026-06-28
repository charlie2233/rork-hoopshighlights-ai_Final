# Edit Plan Schema

The canonical edit plan is backend-owned. iOS requests and displays it but does not generate production edit plans locally.

## Request

Swift request type: `CreateCloudEditJobRequest`

Fields:

- `videoId`
- `analysisJobId`
- `installId`
- `assetId`
- `sourceObjectKey`
- `sourceClipIds`
- `preset`
- `templateId`
- `targetDurationSeconds`
- `aspectRatio`
- `planTier`
- `revenueCatAppUserID`
- `userPrompt`
- `teamSelection`
- `clips`

Each candidate clip carries timing, confidence, excitement/watchability scores, audio cues, duplicate group, review decision, feedback tags, native shot signals, team attribution, and team attribution status.

## Asset Job Compatibility

Swift adapter type: `CloudEditAssetJobContract`

Fields:

- `assetId`
- `sourceObjectKey`
- `analysisJobId`
- `sourceClipIds`
- `style`
- `targetDurationSeconds`
- `aspectRatio`

This adapter mirrors the asset-first request fields now sent by iOS. The live editing request remains additive: `assetId` and `sourceClipIds` are present for upload/edit integration, while `sourceObjectKey` and full candidate `clips` remain for current planning, validation, and render compatibility.

## Plan

Backend plan type: `EditPlan`

Fields:

- `version`
- `editJobId`
- `videoId`
- `analysisJobId`
- `preset`
- `templateId`
- `theme`
- `captionStyle`
- `targetDurationSeconds`
- `aspectRatio`
- `renderMode`
- `audio`
- `clips`
- `intro`
- `outro`
- `watermark`

Plan clips include source timing, event center, timeline timing, label, caption, crop mode, and effects.

## Render

Render status values come from the editing service:

- `render_requested`
- `created`
- `queued`
- `rendering`
- `rendered`
- `failed`
- `failed_timeout`
- `cancelled`

iOS also uses UI-only planning states such as `planning` and `plan_ready` before a service render job exists.

`HighlightsViewModel.latestCloudEditRenderStatus` mirrors the visible AI Edit render status into Exports. AI Edit still owns cloud render requests and polling; Exports only displays render state and handles downloaded MP4 preview, save, and share actions.
