import Foundation
import Testing
@testable import HoopsClips

@Suite(.serialized)
struct WorkflowStateTests {
    @Test func uploadQueueProjectionConsumesCanonicalAssetContracts() {
        let items = UploadQueueProjection.items(assets: [
            UploadAssetQueueContract(
                assetId: "asset_123",
                storageKey: "assets/asset_123/source/game.mp4",
                proxyKey: "assets/asset_123/proxy/proxy.mp4",
                status: "proxy_ready",
                uploadedBytes: 42_000_000,
                fileSizeBytes: 42_000_000,
                progress: 1,
                checksumSha256: "abc123",
                integrityStatus: "verified",
                analysisJobId: "job_123",
                clipCount: 0,
                retryCount: 0,
                retryable: false,
                lastErrorCode: nil,
                renderAttachmentCount: 1,
                failureReason: nil
            )
        ])

        #expect(items.count == 1)
        #expect(items[0].id == "asset_123")
        #expect(items[0].assetId == "asset_123")
        #expect(items[0].storageKey == "assets/asset_123/source/game.mp4")
        #expect(items[0].proxyKey == "assets/asset_123/proxy/proxy.mp4")
        #expect(items[0].assetStatus == "proxy_ready")
        #expect(items[0].phase == .ready)
        #expect(items[0].status == "Asset proxy is ready. AI analysis can start.")
        #expect(items[0].contractSummary.contains("assetId=asset_123"))
        #expect(items[0].contractSummary.contains("proxy ready"))
        #expect(items[0].contractSummary.contains("integrity=verified"))
        #expect(items[0].contractSummary.contains("retryCount=0"))
        #expect(items[0].contractSummary.contains("renderAttachments=1"))
    }

    @Test func uploadQueueProjectionUsesAssetIdForStableMultiItemIdentity() {
        let items = UploadQueueProjection.items(assets: [
            UploadAssetQueueContract(
                assetId: "asset_one",
                storageKey: "assets/asset_one/source/game.mp4",
                proxyKey: nil,
                status: "uploading",
                uploadedBytes: 10,
                fileSizeBytes: 100,
                analysisJobId: "shared_job",
                clipCount: 0,
                failureReason: nil
            ),
            UploadAssetQueueContract(
                assetId: "asset_two",
                storageKey: "assets/asset_two/source/game.mp4",
                proxyKey: nil,
                status: "uploading",
                uploadedBytes: 25,
                fileSizeBytes: 100,
                analysisJobId: "shared_job",
                clipCount: 0,
                failureReason: nil
            )
        ])

        #expect(items.map(\.id) == ["asset_one", "asset_two"])
    }

    @Test func uploadQueueProjectionShowsReviewReadyAfterClipsArrive() {
        let items = UploadQueueProjection.items(assets: [
            UploadAssetQueueContract(
                assetId: "asset_456",
                storageKey: "assets/asset_456/proxy/proxy.mp4",
                proxyKey: "assets/asset_456/proxy/proxy.mp4",
                status: "ready",
                uploadedBytes: nil,
                fileSizeBytes: nil,
                analysisJobId: "job_456",
                clipCount: 3,
                failureReason: nil
            )
        ])

        #expect(items[0].phase == .reviewReady)
        #expect(items[0].clipCount == 3)
        #expect(items[0].status == "3 clips ready for Review.")
    }

    @Test func uploadQueueProjectionUsesCloudJobAndSourceContracts() {
        let items = UploadQueueProjection.items(
            isVideoLoaded: true,
            isImporting: false,
            importStatusMessage: nil,
            isAnalyzing: false,
            analysisProgress: 1,
            analysisStatusMessage: "Found 3 highlights",
            cloudAnalysisJobID: "analysis_123",
            cloudEditSourceObjectKey: "uploads/redacted/source.mp4",
            clipCount: 3,
            pendingUploadManifestSummary: "none"
        )

        #expect(items.count == 1)
        #expect(items[0].id == "analysis_123")
        #expect(items[0].phase == .reviewReady)
        #expect(items[0].progress == 1)
        #expect(items[0].hasSourceObjectKey)
        #expect(items[0].contractSummary.contains("jobId=analysis_123"))
        #expect(items[0].contractSummary.contains("source object ready"))
    }

    @Test func uploadQueueProjectionKeepsResumableUploadVisible() {
        let items = UploadQueueProjection.items(
            isVideoLoaded: true,
            isImporting: false,
            importStatusMessage: nil,
            isAnalyzing: false,
            analysisProgress: 0.22,
            analysisStatusMessage: "Background upload still running",
            cloudAnalysisJobID: "analysis_pending",
            cloudEditSourceObjectKey: nil,
            clipCount: 0,
            pendingUploadManifestSummary: "pending=true source=available chunks=12"
        )

        #expect(items[0].phase == .uploading)
        #expect(items[0].progress >= 0.12)
        #expect(!items[0].hasSourceObjectKey)
        #expect(items[0].contractSummary.contains("resumable upload manifest"))
    }

    @Test @MainActor func reviewBoundaryNudgesClampClipTiming() {
        let tempRoot = URL.temporaryDirectory
            .appending(path: "hoopclips-workflow-state-\(UUID().uuidString)", directoryHint: .isDirectory)
        defer { try? FileManager.default.removeItem(at: tempRoot) }

        let viewModel = HighlightsViewModel(projectStore: ProjectHistoryStore(libraryRootURL: tempRoot))
        viewModel.videoDuration = 12
        let clip = Clip(
            startTime: 2,
            endTime: 5,
            eventCenter: 4,
            action: .madeShot,
            confidence: 0.8,
            isKept: true,
            label: "Made Shot",
            combinedScore: 0.84
        )
        viewModel.analysisService.clips = [clip]

        let earlierStart = viewModel.nudgeClipStart(clip, by: -3)
        #expect(earlierStart?.startTime == 0)
        #expect(earlierStart?.eventCenter == 4)

        let tooShortEnd = viewModel.nudgeClipEnd(earlierStart ?? clip, by: -10)
        #expect(tooShortEnd?.endTime == 0.25)
        #expect(tooShortEnd?.eventCenter == 0.25)

        let laterEnd = viewModel.nudgeClipEnd(tooShortEnd ?? clip, by: 20)
        #expect(laterEnd?.endTime == 12)
    }

    @Test func cloudEditRequestExposesAssetJobCompatibilityContract() {
        let candidate = CloudEditCandidateClip(
            id: "clip_1",
            start: 1,
            end: 4,
            eventCenter: 2.5,
            label: "made_shot",
            confidence: 0.91,
            excitement: 0.88,
            watchability: 0.83,
            motionScore: 0.72,
            audioPeak: 0.44,
            audioCueType: nil,
            audioCueConfidence: nil,
            audioCueTime: nil,
            combinedScore: 0.86,
            duplicateGroup: nil,
            userReviewDecision: "keep",
            reviewFeedbackTags: nil
        )
        let request = CreateCloudEditJobRequest(
            videoId: "video_123",
            analysisJobId: "job_123",
            installId: "install_123",
            sourceObjectKey: "assets/asset_123/proxy/proxy.mp4",
            preset: "personal_highlight",
            templateId: "player_highlights",
            targetDurationSeconds: 45,
            aspectRatio: .vertical,
            planTier: .free,
            revenueCatAppUserID: nil,
            userPrompt: nil,
            clips: [candidate]
        )

        let contract = request.assetJobContract(assetId: "asset_123")
        #expect(contract.assetId == "asset_123")
        #expect(contract.sourceObjectKey == "assets/asset_123/proxy/proxy.mp4")
        #expect(contract.analysisJobId == "job_123")
        #expect(contract.sourceClipIds == ["clip_1"])
        #expect(contract.style == "personal_highlight")
        #expect(contract.targetDurationSeconds == 45)
    }

    @Test func cloudAssetUploadResponsesDecode() throws {
        let capabilitiesPayload = """
        {
          "maxFileSizeBytes": 2147483648,
          "maxDurationSeconds": 4500,
          "resumableUploadThresholdBytes": 67108864,
          "supportsResumableUpload": true,
          "recommendedUploadPreference": "resumable",
          "signedUploadTtlSeconds": 900,
          "defaultPollAfterSeconds": 1,
          "analysisMode": "cloud",
          "supportsMultipartUpload": true,
          "multipartThresholdBytes": 67108864,
          "recommendedPartSizeBytes": 67108864,
          "minPartSizeBytes": 5242880,
          "maxPartSizeBytes": 67108864,
          "maxConcurrentPartUploads": 3,
          "supportsChecksumSha256": true,
          "supportsCancellation": true,
          "supportsIdempotentComplete": true
        }
        """
        let initPayload = """
        {
          "assetId": "asset_123",
          "storageKey": "assets/asset_123/source/game.mp4",
          "status": "initialized",
          "uploadMode": "multipart",
          "uploadUrl": null,
          "uploadMethod": "PUT",
          "uploadHeaders": {},
          "multipart": {
            "uploadId": "upload_123",
            "partSizeBytes": 5242880,
            "partCount": 2,
            "parts": [
              {"partNumber": 1, "uploadUrl": "https://analysis.hoopsclips.test/asset/part/1", "uploadMethod": "PUT", "uploadHeaders": {}},
              {"partNumber": 2, "uploadUrl": "https://analysis.hoopsclips.test/asset/part/2", "uploadMethod": "PUT", "uploadHeaders": {}}
            ]
          },
          "expiresAt": "2026-05-26T20:00:00Z",
          "pollAfterSeconds": 1,
          "uploadState": "waiting_for_client_upload"
        }
        """
        let completePayload = """
        {
          "assetId": "asset_123",
          "storageKey": "assets/asset_123/source/game.mp4",
          "status": "proxy_ready",
          "sourceObjectKey": "assets/asset_123/source/game.mp4",
          "proxyKey": "assets/asset_123/proxy/proxy.mp4",
          "progress": 1.0,
          "checksumSha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
          "integrityStatus": "verified",
          "retryCount": 0,
          "retryable": false,
          "lastErrorCode": null,
          "artifacts": {
            "proxyStorageKey": "assets/asset_123/proxy/proxy.mp4",
            "thumbnailStorageKeys": ["assets/asset_123/thumbnails/0001.jpg"],
            "waveformStorageKey": "assets/asset_123/metadata/waveform.json"
          },
          "pollAfterSeconds": 1
        }
        """
        let analysisPayload = """
        {
          "jobId": "job_asset_123",
          "assetId": "asset_123",
          "storageKey": "assets/asset_123/proxy/proxy.mp4",
          "sourceObjectKey": "assets/asset_123/proxy/proxy.mp4",
          "status": "queued",
          "pollAfterSeconds": 1,
          "quotaRemainingToday": 2,
          "analysisMode": "cloud"
        }
        """
        let statusPayload = """
        {
          "assetId": "asset_123",
          "installId": "install-123456",
          "filename": "game.mp4",
          "contentType": "video/mp4",
          "fileSizeBytes": 10485760,
          "durationSeconds": 42,
          "storageKey": "assets/asset_123/source/game.mp4",
          "sourceObjectKey": "assets/asset_123/source/game.mp4",
          "proxyKey": "assets/asset_123/proxy/proxy.mp4",
          "status": "proxy_ready",
          "uploadMode": "multipart",
          "uploadedBytes": 10485760,
          "progress": 1.0,
          "checksumSha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
          "integrityStatus": "verified",
          "analysisJobId": "job_asset_123",
          "renderAttachments": [{"editJobId": "edit_1", "renderJobId": "render_1", "status": "rendered"}],
          "retryCount": 1,
          "retryable": false,
          "lastErrorCode": null,
          "cancellationReason": null,
          "cancelledAt": null,
          "artifacts": {
            "proxyStorageKey": "assets/asset_123/proxy/proxy.mp4",
            "thumbnailStorageKeys": [],
            "waveformStorageKey": null
          },
          "createdAt": "2026-05-26T20:00:00Z",
          "updatedAt": "2026-05-26T20:01:00Z",
          "failureReason": null
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let capabilities = try decoder.decode(CloudAnalysisCapabilitiesResponse.self, from: Data(capabilitiesPayload.utf8))
        #expect(capabilities.supportsMultipartUpload == true)
        #expect(capabilities.supportsChecksumSha256 == true)
        #expect(capabilities.maxConcurrentPartUploads == 3)

        let upload = try decoder.decode(CloudAssetUploadInitResponse.self, from: Data(initPayload.utf8))
        #expect(upload.assetId == "asset_123")
        #expect(upload.multipart?.partCount == 2)
        #expect(upload.multipart?.parts.first?.partNumber == 1)

        let complete = try decoder.decode(CloudAssetUploadCompleteResponse.self, from: Data(completePayload.utf8))
        #expect(complete.status == "proxy_ready")
        #expect(complete.artifacts.proxyStorageKey == "assets/asset_123/proxy/proxy.mp4")
        #expect(complete.sourceObjectKey == "assets/asset_123/source/game.mp4")
        #expect(complete.proxyKey == "assets/asset_123/proxy/proxy.mp4")
        #expect(complete.integrityStatus == "verified")
        #expect(complete.retryable == false)

        let analysis = try decoder.decode(CloudAssetAnalysisJobResponse.self, from: Data(analysisPayload.utf8))
        #expect(analysis.assetId == "asset_123")
        #expect(analysis.storageKey == "assets/asset_123/proxy/proxy.mp4")
        #expect(analysis.sourceObjectKey == "assets/asset_123/proxy/proxy.mp4")

        let status = try decoder.decode(CloudAssetStatusResponse.self, from: Data(statusPayload.utf8))
        #expect(status.proxyKey == "assets/asset_123/proxy/proxy.mp4")
        #expect(status.integrityStatus == "verified")
        #expect(status.analysisJobId == "job_asset_123")
        #expect(status.renderAttachments?.count == 1)
        #expect(status.retryCount == 1)
    }

    @Test func reviewFeedbackTagsExposeFiveCanonicalValues() {
        #expect(ClipReviewFeedbackTag.allCases.map(\.rawValue) == [
            "duplicate",
            "wrong_team",
            "bad_window",
            "wrong_label",
            "low_quality"
        ])
    }
}
