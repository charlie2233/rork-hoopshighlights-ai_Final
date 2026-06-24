import Foundation

nonisolated enum HighlightTeamSelectionMode: String, Codable, Sendable, CaseIterable {
    case all
    case team
}

nonisolated struct HighlightTeamSelection: Codable, Sendable, Equatable {
    var mode: HighlightTeamSelectionMode = .all
    var teamId: String?
    var label: String?
    var colorLabel: String?
    var primaryColorHex: String?
    var confidenceThreshold: Double = 0.85
    var includeUncertain: Bool = true

    static let allTeams = HighlightTeamSelection(mode: .all)

    static let defaultChoices: [HighlightTeamSelection] = [
        .allTeams,
        HighlightTeamSelection(mode: .team, teamId: "team_dark", label: "Dark jerseys", colorLabel: "black"),
        HighlightTeamSelection(mode: .team, teamId: "team_light", label: "Light jerseys", colorLabel: "white")
    ]

    var selectionKey: String {
        if mode == .all { return "all" }
        return teamId ?? colorLabel ?? label ?? "team"
    }

    var accessibilityIdentifier: String {
        "analysis.teamTarget.choice.\(automationIdentifierSuffix)"
    }

    var displayTitle: String {
        if mode == .all { return "All teams" }
        return label ?? colorLabel ?? teamId ?? "Selected team"
    }

    var displaySubtitle: String {
        if mode == .all {
            return "Solo clips, personal highlights, or both teams"
        }
        return includeUncertain ? "Keep uncertain clips for review" : "Only confident matches"
    }

    enum CodingKeys: String, CodingKey {
        case mode
        case teamId
        case label
        case colorLabel
        case primaryColorHex
        case confidenceThreshold
        case includeUncertain
    }

    init(
        mode: HighlightTeamSelectionMode = .all,
        teamId: String? = nil,
        label: String? = nil,
        colorLabel: String? = nil,
        primaryColorHex: String? = nil,
        confidenceThreshold: Double = 0.85,
        includeUncertain: Bool = true
    ) {
        self.mode = mode
        self.teamId = teamId
        self.label = label
        self.colorLabel = colorLabel
        self.primaryColorHex = primaryColorHex
        self.confidenceThreshold = confidenceThreshold
        self.includeUncertain = includeUncertain
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        mode = try container.decodeIfPresent(HighlightTeamSelectionMode.self, forKey: .mode) ?? .all
        teamId = try container.decodeIfPresent(String.self, forKey: .teamId)
        label = try container.decodeIfPresent(String.self, forKey: .label)
        colorLabel = try container.decodeIfPresent(String.self, forKey: .colorLabel)
        primaryColorHex = try container.decodeIfPresent(String.self, forKey: .primaryColorHex)
        confidenceThreshold = try container.decodeIfPresent(Double.self, forKey: .confidenceThreshold) ?? 0.85
        includeUncertain = try container.decodeIfPresent(Bool.self, forKey: .includeUncertain) ?? true
    }

    private var automationIdentifierSuffix: String {
        let rawValue = selectionKey.lowercased()
        let mapped = rawValue.unicodeScalars.map { scalar in
            let value = scalar.value
            let isDigit = value >= 48 && value <= 57
            let isLowercaseASCII = value >= 97 && value <= 122
            return isDigit || isLowercaseASCII ? String(scalar) : "-"
        }.joined()
        let collapsed = mapped
            .split(separator: "-", omittingEmptySubsequences: true)
            .joined(separator: "-")
        return collapsed.isEmpty ? "team" : collapsed
    }
}

nonisolated struct CloudTeamOption: Codable, Sendable, Equatable {
    let teamId: String
    let label: String
    let colorLabel: String?
    let primaryColorHex: String?
    let confidence: Double
    let source: String?
}

nonisolated enum HighlightTeamTargetCopy {
    static func detectedStatusText(teamLabels: [String], requiresSelection: Bool) -> String {
        if requiresSelection {
            return "Choose one team or All teams."
        }

        let teamCount = teamLabels.count
        if teamCount == 1 {
            return "1 team found. Choose it or All teams."
        }
        if teamCount > 1 {
            return "\(teamCount) teams found. Choose one or All teams."
        }
        return "Teams found. Choose one or All teams."
    }
}

nonisolated struct ClipTeamAttribution: Codable, Sendable, Equatable {
    var teamId: String?
    var label: String?
    var colorLabel: String?
    var confidence: Double
    var source: String?
    var evidenceFrameRefs: [String]? = nil
    var evidenceRoleGroups: [String]? = nil
}

nonisolated enum AnalysisExecutionMode: String, Codable, Sendable {
    case cloud
    case local
    case localFallback
}

nonisolated struct CreateCloudAnalysisJobRequest: Codable, Sendable {
    let filename: String
    let contentType: String
    let fileSizeBytes: Int64
    let durationSeconds: Double
    let installId: String
    let appVersion: String
    let analysisVersion: String
    var teamSelection: HighlightTeamSelection? = nil
    var uploadPreference: String? = "resumable"
}

nonisolated struct CloudAnalysisCapabilitiesResponse: Codable, Sendable {
    let maxFileSizeBytes: Int64
    let maxDurationSeconds: Double
    let resumableUploadThresholdBytes: Int64
    let supportsResumableUpload: Bool
    let recommendedUploadPreference: String?
    let signedUploadTtlSeconds: Int
    let defaultPollAfterSeconds: Int
    let analysisMode: String
    let supportsMultipartUpload: Bool?
    let multipartThresholdBytes: Int64?
    let recommendedPartSizeBytes: Int?
    let minPartSizeBytes: Int?
    let maxPartSizeBytes: Int?
    let maxConcurrentPartUploads: Int?
    let supportsChecksumSha256: Bool?
    let supportsCancellation: Bool?
    let supportsIdempotentComplete: Bool?
}

nonisolated struct CreateCloudAnalysisJobResponse: Codable, Sendable {
    let jobId: String
    let assetId: String?
    let storageKey: String?
    let uploadUrl: String
    let uploadMethod: String
    let uploadHeaders: [String: String]
    let expiresAt: Date
    let pollAfterSeconds: Int
    let quotaRemainingToday: Int
    let analysisMode: String
    let sourceObjectKey: String?
    let resultObjectKey: String?
    let resumableUpload: CloudResumableUpload?

    init(
        jobId: String,
        assetId: String? = nil,
        storageKey: String? = nil,
        uploadUrl: String,
        uploadMethod: String,
        uploadHeaders: [String: String],
        expiresAt: Date,
        pollAfterSeconds: Int,
        quotaRemainingToday: Int,
        analysisMode: String,
        sourceObjectKey: String? = nil,
        resultObjectKey: String? = nil,
        resumableUpload: CloudResumableUpload? = nil
    ) {
        self.jobId = jobId
        self.assetId = assetId
        self.storageKey = storageKey
        self.uploadUrl = uploadUrl
        self.uploadMethod = uploadMethod
        self.uploadHeaders = uploadHeaders
        self.expiresAt = expiresAt
        self.pollAfterSeconds = pollAfterSeconds
        self.quotaRemainingToday = quotaRemainingToday
        self.analysisMode = analysisMode
        self.sourceObjectKey = sourceObjectKey
        self.resultObjectKey = resultObjectKey
        self.resumableUpload = resumableUpload
    }
}

nonisolated struct CloudAssetUploadInitRequest: Codable, Sendable {
    let filename: String
    let contentType: String
    let fileSizeBytes: Int64
    let durationSeconds: Double
    let installId: String
    let appVersion: String
    let analysisVersion: String
    var uploadPreference: String? = "auto"
    var partSizeBytes: Int? = nil
}

nonisolated struct CloudAssetUploadTarget: Codable, Sendable {
    let uploadUrl: String
    let uploadMethod: String
    let uploadHeaders: [String: String]
    let partNumber: Int?
}

nonisolated struct CloudAssetMultipartUpload: Codable, Sendable {
    let uploadId: String
    let partSizeBytes: Int
    let partCount: Int
    let parts: [CloudAssetUploadTarget]
}

nonisolated struct CloudAssetUploadInitResponse: Codable, Sendable {
    let assetId: String
    let storageKey: String
    let status: String
    let uploadMode: String
    let uploadUrl: String?
    let uploadMethod: String
    let uploadHeaders: [String: String]
    let multipart: CloudAssetMultipartUpload?
    let expiresAt: Date
    let pollAfterSeconds: Int
    let uploadState: String
}

nonisolated struct CloudAssetUploadCompleteRequest: Codable, Sendable {
    let installId: String
    let uploadId: String?
    let parts: [CloudMultipartCompletedPart]
}

nonisolated struct CloudAssetUploadCancelRequest: Codable, Sendable {
    let installId: String
    let reason: String?
}

nonisolated struct CloudAssetArtifacts: Codable, Sendable {
    let proxyStorageKey: String?
    let thumbnailStorageKeys: [String]
    let waveformStorageKey: String?
}

nonisolated struct CloudAssetRenderAttachment: Codable, Sendable {
    let editJobId: String?
    let renderJobId: String?
    let status: String
    let outputStorageKey: String?
    let downloadUrl: String?
    let updatedAt: Date?
}

nonisolated struct CloudAssetUploadCompleteResponse: Codable, Sendable {
    let assetId: String
    let storageKey: String
    let sourceObjectKey: String?
    let proxyKey: String?
    let status: String
    let progress: Double?
    let checksumSha256: String?
    let integrityStatus: String?
    let retryCount: Int?
    let retryable: Bool?
    let lastErrorCode: String?
    let artifacts: CloudAssetArtifacts
    let pollAfterSeconds: Int
}

nonisolated struct CloudAssetStatusResponse: Codable, Sendable {
    let assetId: String
    let installId: String
    let filename: String
    let contentType: String
    let fileSizeBytes: Int64
    let durationSeconds: Double
    let storageKey: String
    let sourceObjectKey: String?
    let proxyKey: String?
    let status: String
    let uploadMode: String
    let uploadedBytes: Int64
    let progress: Double?
    let checksumSha256: String?
    let integrityStatus: String?
    let analysisJobId: String?
    let renderAttachments: [CloudAssetRenderAttachment]?
    let retryCount: Int?
    let retryable: Bool?
    let lastErrorCode: String?
    let cancellationReason: String?
    let cancelledAt: Date?
    let artifacts: CloudAssetArtifacts
    let createdAt: Date
    let updatedAt: Date
    let failureReason: String?
}

typealias AssetRecord = CloudAssetStatusResponse

nonisolated struct CloudAssetAnalysisJobRequest: Codable, Sendable {
    let installId: String
    let appVersion: String?
    let analysisVersion: String?
    var teamSelection: HighlightTeamSelection? = nil
}

nonisolated struct CloudAssetAnalysisJobResponse: Codable, Sendable {
    let jobId: String
    let assetId: String
    let storageKey: String
    let sourceObjectKey: String?
    let status: String
    let pollAfterSeconds: Int
    let quotaRemainingToday: Int
    let analysisMode: String
}

nonisolated struct CloudResumableUpload: Codable, Sendable {
    let uploadId: String
    let chunkSizeBytes: Int
    let partCount: Int
    let expiresAt: Date
}

nonisolated struct CloudMultipartPartRequest: Codable, Sendable {
    let jobId: String
    let installId: String
    let uploadId: String
    let partNumber: Int
}

nonisolated struct CloudMultipartPartResponse: Codable, Sendable {
    let jobId: String
    let partNumber: Int
    let uploadUrl: String
    let uploadMethod: String
    let uploadHeaders: [String: String]
    let expiresAt: Date
}

nonisolated struct CloudMultipartCompleteRequest: Codable, Sendable {
    let jobId: String
    let installId: String
    let uploadId: String
    let parts: [CloudMultipartCompletedPart]
}

nonisolated struct CloudMultipartCompletedPart: Codable, Sendable {
    let partNumber: Int
    let etag: String
}

nonisolated struct StartCloudAnalysisJobRequest: Codable, Sendable {
    let installId: String
    var teamSelection: HighlightTeamSelection? = nil
}

nonisolated struct StartCloudAnalysisJobResponse: Codable, Sendable {
    let jobId: String
    let status: String
}

nonisolated struct ScanCloudAnalysisTeamsRequest: Codable, Sendable {
    let installId: String
}

nonisolated struct ScanCloudAnalysisTeamsResponse: Codable, Sendable {
    let jobId: String
    let status: String
    let detectedTeams: [CloudTeamOption]
}

nonisolated struct PreparedCloudAnalysisJob: Sendable {
    let sourceURL: URL
    let job: CreateCloudAnalysisJobResponse
    let detectedTeams: [CloudTeamOption]
}

nonisolated struct CloudAnalysisJobResponse: Codable, Sendable {
    let jobId: String
    let assetId: String?
    let storageKey: String?
    let status: String
    let progress: Double
    let stage: String
    let errorCode: String?
    let errorMessage: String?
    let analysisVersion: String
    let results: CloudAnalysisResult?
    let sourceObjectKey: String?
    let resultObjectKey: String?

    init(
        jobId: String,
        assetId: String? = nil,
        storageKey: String? = nil,
        status: String,
        progress: Double,
        stage: String,
        errorCode: String?,
        errorMessage: String?,
        analysisVersion: String,
        results: CloudAnalysisResult?,
        sourceObjectKey: String? = nil,
        resultObjectKey: String? = nil
    ) {
        self.jobId = jobId
        self.assetId = assetId
        self.storageKey = storageKey
        self.status = status
        self.progress = progress
        self.stage = stage
        self.errorCode = errorCode
        self.errorMessage = errorMessage
        self.analysisVersion = analysisVersion
        self.results = results
        self.sourceObjectKey = sourceObjectKey
        self.resultObjectKey = resultObjectKey
    }
}

nonisolated struct CloudAnalysisResult: Codable, Sendable {
    let analysisJobId: String?
    let assetId: String?
    let assetStorageKey: String?
    let storageKey: String?
    let proxyStorageKey: String?
    let assetStatus: String?
    let uploadedBytes: Int64?
    let fileSizeBytes: Int64?
    let assetProgress: Double?
    let assetChecksumSha256: String?
    let assetIntegrityStatus: String?
    let assetRetryCount: Int?
    let assetRetryable: Bool?
    let assetLastErrorCode: String?
    let assetCancellationReason: String?
    let assetRenderAttachmentCount: Int?
    let assetFailureReason: String?
    let sourceObjectKey: String?
    let clipCount: Int
    let clips: [CloudClip]
    let diagnostics: CloudDiagnostics
    var detectedTeams: [CloudTeamOption] = []
    var teamSelection: HighlightTeamSelection? = nil
    var assetUploadedBytes: Int64? { uploadedBytes }
    var assetFileSizeBytes: Int64? { fileSizeBytes }

    init(
        analysisJobId: String? = nil,
        assetId: String? = nil,
        assetStorageKey: String? = nil,
        storageKey: String? = nil,
        proxyStorageKey: String? = nil,
        assetStatus: String? = nil,
        uploadedBytes: Int64? = nil,
        fileSizeBytes: Int64? = nil,
        assetProgress: Double? = nil,
        assetChecksumSha256: String? = nil,
        assetIntegrityStatus: String? = nil,
        assetRetryCount: Int? = nil,
        assetRetryable: Bool? = nil,
        assetLastErrorCode: String? = nil,
        assetCancellationReason: String? = nil,
        assetRenderAttachmentCount: Int? = nil,
        assetFailureReason: String? = nil,
        sourceObjectKey: String? = nil,
        assetUploadedBytes: Int64? = nil,
        assetFileSizeBytes: Int64? = nil,
        clipCount: Int,
        clips: [CloudClip],
        diagnostics: CloudDiagnostics,
        detectedTeams: [CloudTeamOption] = [],
        teamSelection: HighlightTeamSelection? = nil
    ) {
        self.analysisJobId = analysisJobId
        self.assetId = assetId
        self.assetStorageKey = assetStorageKey
        self.storageKey = storageKey
        self.proxyStorageKey = proxyStorageKey
        self.assetStatus = assetStatus
        self.uploadedBytes = uploadedBytes ?? assetUploadedBytes
        self.fileSizeBytes = fileSizeBytes ?? assetFileSizeBytes
        self.assetProgress = assetProgress
        self.assetChecksumSha256 = assetChecksumSha256
        self.assetIntegrityStatus = assetIntegrityStatus
        self.assetRetryCount = assetRetryCount
        self.assetRetryable = assetRetryable
        self.assetLastErrorCode = assetLastErrorCode
        self.assetCancellationReason = assetCancellationReason
        self.assetRenderAttachmentCount = assetRenderAttachmentCount
        self.assetFailureReason = assetFailureReason
        self.sourceObjectKey = sourceObjectKey
        self.clipCount = clipCount
        self.clips = clips
        self.diagnostics = diagnostics
        self.detectedTeams = detectedTeams
        self.teamSelection = teamSelection
    }

    enum CodingKeys: String, CodingKey {
        case analysisJobId
        case assetId
        case assetStorageKey
        case storageKey
        case proxyStorageKey
        case assetStatus
        case uploadedBytes
        case fileSizeBytes
        case assetProgress
        case progress
        case assetChecksumSha256
        case checksumSha256
        case assetIntegrityStatus
        case integrityStatus
        case assetRetryCount
        case retryCount
        case assetRetryable
        case retryable
        case assetLastErrorCode
        case lastErrorCode
        case assetCancellationReason
        case cancellationReason
        case assetRenderAttachmentCount
        case renderAttachmentCount
        case renderAttachments
        case assetFailureReason
        case sourceObjectKey
        case status
        case assetUploadedBytes
        case assetFileSizeBytes
        case failureReason
        case clipCount
        case clips
        case diagnostics
        case detectedTeams
        case teamSelection
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        analysisJobId = try container.decodeIfPresent(String.self, forKey: .analysisJobId)
        assetId = try container.decodeIfPresent(String.self, forKey: .assetId)
        storageKey = try container.decodeIfPresent(String.self, forKey: .storageKey)
        proxyStorageKey = try container.decodeIfPresent(String.self, forKey: .proxyStorageKey)
        assetFailureReason = try container.decodeIfPresent(String.self, forKey: .assetFailureReason)
            ?? container.decodeIfPresent(String.self, forKey: .failureReason)
        sourceObjectKey = try container.decodeIfPresent(String.self, forKey: .sourceObjectKey)
        assetStorageKey = try container.decodeIfPresent(String.self, forKey: .assetStorageKey)
            ?? container.decodeIfPresent(String.self, forKey: .storageKey)
        assetStatus = try container.decodeIfPresent(String.self, forKey: .assetStatus)
            ?? container.decodeIfPresent(String.self, forKey: .status)
        uploadedBytes = try container.decodeIfPresent(Int64.self, forKey: .assetUploadedBytes)
            ?? container.decodeIfPresent(Int64.self, forKey: .uploadedBytes)
        fileSizeBytes = try container.decodeIfPresent(Int64.self, forKey: .assetFileSizeBytes)
            ?? container.decodeIfPresent(Int64.self, forKey: .fileSizeBytes)
        assetProgress = try container.decodeIfPresent(Double.self, forKey: .assetProgress)
            ?? container.decodeIfPresent(Double.self, forKey: .progress)
        assetChecksumSha256 = try container.decodeIfPresent(String.self, forKey: .assetChecksumSha256)
            ?? container.decodeIfPresent(String.self, forKey: .checksumSha256)
        assetIntegrityStatus = try container.decodeIfPresent(String.self, forKey: .assetIntegrityStatus)
            ?? container.decodeIfPresent(String.self, forKey: .integrityStatus)
        assetRetryCount = try container.decodeIfPresent(Int.self, forKey: .assetRetryCount)
            ?? container.decodeIfPresent(Int.self, forKey: .retryCount)
        assetRetryable = try container.decodeIfPresent(Bool.self, forKey: .assetRetryable)
            ?? container.decodeIfPresent(Bool.self, forKey: .retryable)
        assetLastErrorCode = try container.decodeIfPresent(String.self, forKey: .assetLastErrorCode)
            ?? container.decodeIfPresent(String.self, forKey: .lastErrorCode)
        assetCancellationReason = try container.decodeIfPresent(String.self, forKey: .assetCancellationReason)
            ?? container.decodeIfPresent(String.self, forKey: .cancellationReason)
        if let explicitCount = try container.decodeIfPresent(Int.self, forKey: .assetRenderAttachmentCount)
            ?? container.decodeIfPresent(Int.self, forKey: .renderAttachmentCount) {
            assetRenderAttachmentCount = explicitCount
        } else {
            assetRenderAttachmentCount = try container.decodeIfPresent([CloudAssetRenderAttachment].self, forKey: .renderAttachments)?.count
        }
        clipCount = try container.decode(Int.self, forKey: .clipCount)
        clips = try container.decode([CloudClip].self, forKey: .clips)
        diagnostics = try container.decode(CloudDiagnostics.self, forKey: .diagnostics)
        detectedTeams = try container.decodeIfPresent([CloudTeamOption].self, forKey: .detectedTeams) ?? []
        teamSelection = try container.decodeIfPresent(HighlightTeamSelection.self, forKey: .teamSelection)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encodeIfPresent(analysisJobId, forKey: .analysisJobId)
        try container.encodeIfPresent(sourceObjectKey, forKey: .sourceObjectKey)
        try container.encodeIfPresent(assetId, forKey: .assetId)
        try container.encodeIfPresent(assetStorageKey, forKey: .assetStorageKey)
        try container.encodeIfPresent(proxyStorageKey, forKey: .proxyStorageKey)
        try container.encodeIfPresent(assetStatus, forKey: .assetStatus)
        try container.encodeIfPresent(uploadedBytes, forKey: .uploadedBytes)
        try container.encodeIfPresent(fileSizeBytes, forKey: .fileSizeBytes)
        try container.encodeIfPresent(assetProgress, forKey: .assetProgress)
        try container.encodeIfPresent(assetChecksumSha256, forKey: .assetChecksumSha256)
        try container.encodeIfPresent(assetIntegrityStatus, forKey: .assetIntegrityStatus)
        try container.encodeIfPresent(assetRetryCount, forKey: .assetRetryCount)
        try container.encodeIfPresent(assetRetryable, forKey: .assetRetryable)
        try container.encodeIfPresent(assetLastErrorCode, forKey: .assetLastErrorCode)
        try container.encodeIfPresent(assetCancellationReason, forKey: .assetCancellationReason)
        try container.encodeIfPresent(assetRenderAttachmentCount, forKey: .assetRenderAttachmentCount)
        try container.encodeIfPresent(assetFailureReason, forKey: .assetFailureReason)
        try container.encode(clipCount, forKey: .clipCount)
        try container.encode(clips, forKey: .clips)
        try container.encode(diagnostics, forKey: .diagnostics)
        try container.encode(detectedTeams, forKey: .detectedTeams)
        try container.encodeIfPresent(teamSelection, forKey: .teamSelection)
    }

    func withJobMetadata(analysisJobId: String, sourceObjectKey: String?) -> CloudAnalysisResult {
        CloudAnalysisResult(
            analysisJobId: analysisJobId,
            assetId: assetId,
            assetStorageKey: assetStorageKey,
            storageKey: storageKey,
            proxyStorageKey: proxyStorageKey,
            assetStatus: assetStatus,
            uploadedBytes: uploadedBytes,
            fileSizeBytes: fileSizeBytes,
            assetProgress: assetProgress,
            assetChecksumSha256: assetChecksumSha256,
            assetIntegrityStatus: assetIntegrityStatus,
            assetRetryCount: assetRetryCount,
            assetRetryable: assetRetryable,
            assetLastErrorCode: assetLastErrorCode,
            assetCancellationReason: assetCancellationReason,
            assetRenderAttachmentCount: assetRenderAttachmentCount,
            assetFailureReason: assetFailureReason,
            sourceObjectKey: sourceObjectKey ?? self.sourceObjectKey,
            clipCount: clipCount,
            clips: clips,
            diagnostics: diagnostics,
            detectedTeams: detectedTeams,
            teamSelection: teamSelection
        )
    }
}

nonisolated struct NativeShotSignals: Codable, Sendable, Equatable {
    let isShotLike: Bool
    let leadInSeconds: Double
    let followThroughSeconds: Double
    let setupContextScore: Double
    let outcomeContextScore: Double
    let eventCenterQuality: Double
    let contextQualityScore: Double
    let timingWindowOk: Bool
    let outcome: String
    let outcomeConfidence: Double
    var outcomeEvidenceSource: String? = nil
    var outcomeReliabilityScore: Double? = nil
}

nonisolated struct CloudClip: Codable, Sendable {
    let startTime: Double
    let endTime: Double
    let eventCenter: Double?
    let confidence: Double
    let label: String
    let action: String
    let audioScore: Double
    let visualScore: Double
    let motionScore: Double
    let combinedScore: Double
    let audioCueType: String?
    let audioCueConfidence: Double?
    let audioCueTime: Double?
    let detectionMethod: String
    let shouldAutoKeep: Bool
    let shouldEnableSlowMotion: Bool
    var nativeShotSignals: NativeShotSignals? = nil
    var teamAttribution: ClipTeamAttribution? = nil
    var teamAttributionStatus: String? = nil

    func makeClip() -> Clip {
        let resolvedAction = HighlightAction(rawValue: action)
            ?? HighlightAction.allCases.first(where: { $0.rawValue.localizedCaseInsensitiveCompare(action) == .orderedSame })
            ?? .unknown
        let resolvedMethod = DetectionMethod(rawValue: detectionMethod) ?? .cloud
        return Clip(
            startTime: startTime,
            endTime: endTime,
            eventCenter: eventCenter,
            action: resolvedAction,
            confidence: confidence,
            isKept: shouldAutoKeep,
            label: label,
            audioScore: audioScore,
            visualScore: visualScore,
            motionScore: motionScore,
            combinedScore: combinedScore,
            audioCueType: audioCueType,
            audioCueConfidence: audioCueConfidence,
            audioCueTime: audioCueTime,
            isSlowMotionEnabled: shouldEnableSlowMotion,
            detectionMethod: resolvedMethod,
            nativeShotSignals: nativeShotSignals,
            teamAttribution: teamAttribution,
            teamAttributionStatus: teamAttributionStatus
        )
    }
}

nonisolated struct CloudDiagnostics: Codable, Sendable {
    let processingMs: Int
    let backendModelVersion: String
    let usedVideoIntelligence: Bool
    let usedGeminiRelabeling: Bool
    let candidateSegments: Int
    let finalSegments: Int
    let usedTeamQuickScan: Bool?
    let preTeamFilterSegments: Int?
    let teamMatchedCandidateSegments: Int?
    let teamUncertainCandidateSegments: Int?
    let teamOpponentFilteredSegments: Int?
    let teamMatchedReviewSegments: Int?
    let teamUncertainReviewSegments: Int?
    let defensiveReviewSegments: Int?
    let blockReviewSegments: Int?
    let stealReviewSegments: Int?
    let forcedTurnoverReviewSegments: Int?
    let defensiveStopReviewSegments: Int?
}

nonisolated struct CloudAnalysisAPIError: Codable, Sendable {
    let errorCode: String
    let errorMessage: String
    let quotaRemainingToday: Int?
}

nonisolated enum CloudAnalysisJobState: String, Codable, Sendable {
    case created
    case queued
    case processing
    case succeeded
    case failed
    case expired
}

nonisolated enum CloudAnalysisError: Error, LocalizedError, Sendable {
    case notConfigured
    case invalidVideo
    case invalidResponse
    case uploadFailed
    case timedOut
    case quotaExceeded(Int?)
    case backend(code: String, message: String)
    case network(String)

    var errorDescription: String? {
        switch self {
        case .notConfigured:
            return "Cloud analysis is not configured yet."
        case .invalidVideo:
            return "The selected video could not be prepared for cloud analysis."
        case .invalidResponse:
            return "The analysis server returned an invalid response."
        case .uploadFailed:
            return "The video upload did not complete. Stay on Wi-Fi and retry; saved chunks can resume with fast lanes when the server provides a resumable upload plan."
        case .timedOut:
            return "Cloud analysis is taking longer than expected. Reopen the project from History and try again, or choose a shorter video."
        case .quotaExceeded(let remaining):
            if let remaining {
                return "Cloud analysis quota exceeded. Remaining today: \(remaining)."
            }
            return "Cloud analysis quota exceeded."
        case .backend(let code, let message):
            switch code.lowercased() {
            case "file_too_large":
                return "This video is over the cloud upload limit for this environment. Try a smaller export, or raise the backend upload limit before retrying."
            case "unsupported_duration", "video_too_long", "duration_too_long":
                return "This video is longer than the cloud analysis limit for this environment. Trim it or raise the backend duration limit before retrying."
            case "empty_upload":
                return "The server received an empty upload. Re-import the video from Photos or Files, stay on Wi-Fi, and retry."
            case "upload_expired":
                return "Upload expired. Tap AI Analysis again to start a fresh cloud upload."
            default:
                return message
            }
        case .network(let description):
            return description
        }
    }

    var backgroundUploadProofSummary: String {
        switch self {
        case .notConfigured:
            return "kind=not_configured retryable=false privacy=no_urls_no_object_keys"
        case .invalidVideo:
            return "kind=invalid_video retryable=false privacy=no_urls_no_object_keys"
        case .invalidResponse:
            return "kind=invalid_response retryable=true privacy=no_urls_no_object_keys"
        case .uploadFailed:
            return "kind=upload_failed retryable=true next=wifi_retry_or_fast_resumable_plan savedChunks=possible privacy=no_urls_no_object_keys"
        case .timedOut:
            return "kind=timed_out retryable=true next=history_reopen_or_retry privacy=no_urls_no_object_keys"
        case .quotaExceeded(let remaining):
            let remainingText = remaining.map { String($0) } ?? "unknown"
            return "kind=quota_exceeded retryable=false remainingToday=\(remainingText) privacy=no_urls_no_object_keys"
        case .backend(let code, _):
            return "kind=backend code=\(Self.safeProofValue(code)) category=\(Self.backendProofCategory(for: code)) privacy=no_urls_no_object_keys"
        case .network(let description):
            return "kind=network category=\(Self.networkProofCategory(for: description)) retryable=true privacy=no_urls_no_object_keys"
        }
    }

    private static func backendProofCategory(for code: String) -> String {
        switch code.lowercased() {
        case "file_too_large":
            return "file_size_policy"
        case "unsupported_duration", "video_too_long", "duration_too_long":
            return "duration_policy"
        case "empty_upload":
            return "empty_upload"
        case "upload_expired":
            return "upload_expired"
        case let value where value.contains("http_"):
            return "http_status"
        default:
            return "backend"
        }
    }

    private static func networkProofCategory(for description: String) -> String {
        let normalized = description.lowercased()
        if normalized.contains("cancel") {
            return "cancelled"
        }
        if normalized.contains("timed out") || normalized.contains("timeout") {
            return "timeout"
        }
        if normalized.contains("offline") || normalized.contains("internet") || normalized.contains("network") {
            return "connectivity"
        }
        return "network_error"
    }

    private static func safeProofValue(_ value: String) -> String {
        let compact = value
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: "_")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !compact.isEmpty else {
            return "none"
        }
        return String(compact.prefix(48))
    }
}
