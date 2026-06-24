import Foundation

nonisolated enum WorkflowSection: String, CaseIterable, Identifiable, Sendable {
    case uploads
    case review
    case aiEdit
    case exports

    var id: String { rawValue }

    var title: String {
        switch self {
        case .uploads: return "Uploads"
        case .review: return "Review"
        case .aiEdit: return "AI Edit"
        case .exports: return "Exports"
        }
    }
}

nonisolated enum UploadQueuePhase: String, Codable, Sendable, Equatable {
    case empty
    case ready
    case importing
    case uploading
    case analyzing
    case reviewReady
    case failed

    var title: String {
        switch self {
        case .empty: return "No upload"
        case .ready: return "Ready"
        case .importing: return "Importing"
        case .uploading: return "Uploading"
        case .analyzing: return "Analyzing"
        case .reviewReady: return "Review ready"
        case .failed: return "Needs attention"
        }
    }
}

nonisolated struct UploadQueueItem: Identifiable, Equatable, Sendable {
    let id: String
    let title: String
    let phase: UploadQueuePhase
    let status: String
    let progress: Double
    let assetId: String?
    let storageKey: String?
    let proxyKey: String?
    let assetStatus: String?
    let jobId: String?
    let hasSourceObjectKey: Bool
    let clipCount: Int
    let integrityStatus: String?
    let retryCount: Int?
    let retryable: Bool?
    let lastErrorCode: String?
    let renderAttachmentCount: Int
    let contractSummary: String

    var progressPercent: Int {
        Int((min(max(progress, 0), 1) * 100).rounded())
    }
}

nonisolated struct UploadAssetQueueContract: Equatable, Sendable {
    let assetId: String
    let storageKey: String
    let proxyKey: String?
    let status: String
    let uploadedBytes: Int64?
    let fileSizeBytes: Int64?
    var progress: Double? = nil
    var checksumSha256: String? = nil
    var integrityStatus: String? = nil
    let analysisJobId: String?
    let clipCount: Int
    var retryCount: Int? = nil
    var retryable: Bool? = nil
    var lastErrorCode: String? = nil
    var cancellationReason: String? = nil
    var renderAttachmentCount: Int = 0
    let failureReason: String?
}

nonisolated enum UploadQueueProjection {
    static func items(assets: [UploadAssetQueueContract]) -> [UploadQueueItem] {
        assets.map { asset in
            let phase = phase(forAssetStatus: asset.status, clipCount: asset.clipCount, failureReason: asset.failureReason)
            let progress = asset.progress ?? progress(for: phase, uploadedBytes: asset.uploadedBytes, fileSizeBytes: asset.fileSizeBytes)
            return UploadQueueItem(
                id: asset.assetId,
                title: asset.analysisJobId.map { "Cloud job \($0)" } ?? "Asset \(asset.assetId)",
                phase: phase,
                status: statusText(for: asset, phase: phase),
                progress: progress,
                assetId: asset.assetId,
                storageKey: asset.storageKey,
                proxyKey: asset.proxyKey,
                assetStatus: asset.status,
                jobId: asset.analysisJobId,
                hasSourceObjectKey: !asset.storageKey.isEmpty && asset.storageKey != "pending",
                clipCount: asset.clipCount,
                integrityStatus: asset.integrityStatus,
                retryCount: asset.retryCount,
                retryable: asset.retryable,
                lastErrorCode: asset.lastErrorCode,
                renderAttachmentCount: asset.renderAttachmentCount,
                contractSummary: contractSummary(for: asset)
            )
        }
    }

    static func items(
        isVideoLoaded: Bool,
        isImporting: Bool,
        importStatusMessage: String?,
        isAnalyzing: Bool,
        analysisProgress: Double,
        analysisStatusMessage: String,
        cloudAnalysisJobID: String?,
        cloudEditSourceObjectKey: String?,
        clipCount: Int,
        pendingUploadManifestSummary: String?
    ) -> [UploadQueueItem] {
        let phase = phase(
            isVideoLoaded: isVideoLoaded,
            isImporting: isImporting,
            importStatusMessage: importStatusMessage,
            isAnalyzing: isAnalyzing,
            analysisStatusMessage: analysisStatusMessage,
            cloudAnalysisJobID: cloudAnalysisJobID,
            cloudEditSourceObjectKey: cloudEditSourceObjectKey,
            clipCount: clipCount,
            pendingUploadManifestSummary: pendingUploadManifestSummary
        )
        let boundedProgress = progress(for: phase, analysisProgress: analysisProgress, clipCount: clipCount)
        let status = statusText(
            phase: phase,
            importStatusMessage: importStatusMessage,
            analysisStatusMessage: analysisStatusMessage,
            clipCount: clipCount
        )
        let jobLabel = cloudAnalysisJobID.map { "Cloud job \($0)" } ?? "Current upload"

        return [
            UploadQueueItem(
                id: cloudAnalysisJobID ?? "current-upload",
                title: jobLabel,
                phase: phase,
                status: status,
                progress: boundedProgress,
                assetId: nil,
                storageKey: cloudEditSourceObjectKey,
                proxyKey: nil,
                assetStatus: nil,
                jobId: cloudAnalysisJobID,
                hasSourceObjectKey: cloudEditSourceObjectKey != nil,
                clipCount: clipCount,
                integrityStatus: nil,
                retryCount: nil,
                retryable: nil,
                lastErrorCode: nil,
                renderAttachmentCount: 0,
                contractSummary: contractSummary(
                    jobID: cloudAnalysisJobID,
                    hasSourceObjectKey: cloudEditSourceObjectKey != nil,
                    pendingUploadManifestSummary: pendingUploadManifestSummary
                )
            )
        ]
    }

    private static func phase(forAssetStatus status: String, clipCount: Int, failureReason: String?) -> UploadQueuePhase {
        let normalized = status.lowercased()
        if failureReason != nil || normalized.contains("failed") {
            return .failed
        }
        if normalized.contains("cancel") {
            return .failed
        }
        if clipCount > 0 {
            return .reviewReady
        }
        if normalized == "initialized" {
            return .ready
        }
        if normalized == "uploading" {
            return .uploading
        }
        if normalized == "uploaded" || normalized == "processing" {
            return .analyzing
        }
        if normalized == "proxy_ready" || normalized == "ready" {
            return clipCount > 0 ? .reviewReady : .ready
        }
        return .analyzing
    }

    private static func progress(
        for phase: UploadQueuePhase,
        uploadedBytes: Int64?,
        fileSizeBytes: Int64?
    ) -> Double {
        if let uploadedBytes,
           let fileSizeBytes,
           fileSizeBytes > 0,
           phase == .uploading || phase == .importing {
            return min(max(Double(uploadedBytes) / Double(fileSizeBytes), 0.12), 0.72)
        }
        switch phase {
        case .empty: return 0
        case .ready: return 0.08
        case .importing: return 0.12
        case .uploading: return 0.35
        case .analyzing: return 0.78
        case .reviewReady: return 1
        case .failed: return 1
        }
    }

    private static func statusText(for asset: UploadAssetQueueContract, phase: UploadQueuePhase) -> String {
        if let failureReason = asset.failureReason, phase == .failed {
            return "Asset failed: \(failureReason)"
        }
        if let lastErrorCode = asset.lastErrorCode, phase != .reviewReady {
            return asset.retryable == false
                ? "Upload stopped: \(lastErrorCode)"
                : "Upload needs retry: \(lastErrorCode)"
        }
        switch phase {
        case .ready:
            if asset.status.lowercased() == "proxy_ready" || asset.proxyKey != nil {
                return "Asset proxy is ready. AI analysis can start."
            }
            if asset.status.lowercased() == "ready" {
                return "Asset is ready for AI analysis and edit planning."
            }
            return "Asset initialized. Upload can begin."
        case .uploading:
            return "Uploading source asset to storage."
        case .analyzing:
            return asset.proxyKey == nil ? "Backend is preparing proxy media." : "Proxy media is ready for analysis."
        case .reviewReady:
            if asset.clipCount > 0 {
                return "\(asset.clipCount) \(asset.clipCount == 1 ? "clip" : "clips") ready for Review."
            }
            return "Asset proxy is ready. AI analysis can start."
        case .failed:
            return "Upload or post-upload processing needs attention."
        case .empty, .importing:
            return phase.title
        }
    }

    private static func contractSummary(for asset: UploadAssetQueueContract) -> String {
        let proxyState = asset.proxyKey == nil ? "proxy pending" : "proxy ready"
        let integrity = asset.integrityStatus.map { "integrity=\($0)" } ?? "integrity=pending"
        let retry = asset.retryCount.map { "retryCount=\($0)" } ?? "retryCount=0"
        let renders = "renderAttachments=\(max(asset.renderAttachmentCount, 0))"
        return "assetId=\(asset.assetId); status=\(asset.status); \(proxyState); \(integrity); \(retry); \(renders); jobId=\(asset.analysisJobId ?? "pending")"
    }

    private static func phase(
        isVideoLoaded: Bool,
        isImporting: Bool,
        importStatusMessage: String?,
        isAnalyzing: Bool,
        analysisStatusMessage: String,
        cloudAnalysisJobID: String?,
        cloudEditSourceObjectKey: String?,
        clipCount: Int,
        pendingUploadManifestSummary: String?
    ) -> UploadQueuePhase {
        let combinedStatus = [
            importStatusMessage ?? "",
            analysisStatusMessage,
            pendingUploadManifestSummary ?? ""
        ].joined(separator: " ").lowercased()

        if combinedStatus.contains("failed") || combinedStatus.contains("error") {
            return .failed
        }
        if clipCount > 0 {
            return .reviewReady
        }
        if isImporting {
            return .importing
        }
        if isAnalyzing {
            return combinedStatus.contains("upload") || combinedStatus.contains("chunk") ? .uploading : .analyzing
        }
        if hasPendingUploadManifest(pendingUploadManifestSummary) {
            return .uploading
        }
        if cloudAnalysisJobID != nil || cloudEditSourceObjectKey != nil {
            return .analyzing
        }
        if isVideoLoaded {
            return .ready
        }
        return .empty
    }

    private static func progress(
        for phase: UploadQueuePhase,
        analysisProgress: Double,
        clipCount: Int
    ) -> Double {
        switch phase {
        case .empty:
            return 0
        case .ready:
            return 0.08
        case .importing:
            return max(0.05, min(analysisProgress, 0.18))
        case .uploading:
            return max(0.12, min(analysisProgress, 0.72))
        case .analyzing:
            return max(0.28, min(analysisProgress, 0.94))
        case .reviewReady:
            return clipCount > 0 ? 1 : min(max(analysisProgress, 0), 1)
        case .failed:
            return min(max(analysisProgress, 0), 1)
        }
    }

    private static func statusText(
        phase: UploadQueuePhase,
        importStatusMessage: String?,
        analysisStatusMessage: String,
        clipCount: Int
    ) -> String {
        let importMessage = sanitized(importStatusMessage)
        let analysisMessage = sanitized(analysisStatusMessage)

        switch phase {
        case .empty:
            return "Import a video to create a cloud analysis job."
        case .ready:
            return "Video staged. Start AI Analysis when the target team is set."
        case .importing:
            return importMessage ?? "Preparing the video asset."
        case .uploading:
            return importMessage ?? analysisMessage ?? "Sending video to cloud storage."
        case .analyzing:
            return analysisMessage ?? "Cloud analysis is preparing review clips."
        case .reviewReady:
            return "\(clipCount) \(clipCount == 1 ? "clip" : "clips") ready for Review."
        case .failed:
            return importMessage ?? analysisMessage ?? "Upload or analysis needs attention."
        }
    }

    private static func contractSummary(
        jobID: String?,
        hasSourceObjectKey: Bool,
        pendingUploadManifestSummary: String?
    ) -> String {
        let uploadState = hasPendingUploadManifest(pendingUploadManifestSummary) ? "resumable upload manifest" : "analysis job state"
        let sourceState = hasSourceObjectKey ? "source object ready" : "source object pending"
        return "\(uploadState); \(sourceState); jobId=\(jobID ?? "pending")"
    }

    private static func sanitized(_ value: String?) -> String? {
        guard let trimmed = value?.trimmingCharacters(in: .whitespacesAndNewlines), !trimmed.isEmpty else {
            return nil
        }
        return trimmed
    }

    private static func hasPendingUploadManifest(_ summary: String?) -> Bool {
        guard let summary = sanitized(summary)?.lowercased() else { return false }
        return !summary.contains("none")
            && !summary.contains("no pending")
            && !summary.contains("empty")
            && !summary.contains("cleared")
    }
}
