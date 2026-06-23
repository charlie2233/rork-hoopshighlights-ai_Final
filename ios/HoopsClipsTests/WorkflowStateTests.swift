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
                analysisJobId: "job_123",
                clipCount: 0,
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

    @Test func cloudAssetUploadResponsesDecode() throws {
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
          "status": "queued",
          "pollAfterSeconds": 1,
          "quotaRemainingToday": 2,
          "analysisMode": "cloud"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let upload = try decoder.decode(CloudAssetUploadInitResponse.self, from: Data(initPayload.utf8))
        #expect(upload.assetId == "asset_123")
        #expect(upload.multipart?.partCount == 2)
        #expect(upload.multipart?.parts.first?.partNumber == 1)

        let complete = try decoder.decode(CloudAssetUploadCompleteResponse.self, from: Data(completePayload.utf8))
        #expect(complete.status == "proxy_ready")
        #expect(complete.artifacts.proxyStorageKey == "assets/asset_123/proxy/proxy.mp4")

        let analysis = try decoder.decode(CloudAssetAnalysisJobResponse.self, from: Data(analysisPayload.utf8))
        #expect(analysis.assetId == "asset_123")
        #expect(analysis.storageKey == "assets/asset_123/proxy/proxy.mp4")
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
