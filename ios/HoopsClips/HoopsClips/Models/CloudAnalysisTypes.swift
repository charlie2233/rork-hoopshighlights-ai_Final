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

nonisolated struct CreateCloudAnalysisJobResponse: Codable, Sendable {
    let jobId: String
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
    let sourceObjectKey: String?
    let clipCount: Int
    let clips: [CloudClip]
    let diagnostics: CloudDiagnostics
    var detectedTeams: [CloudTeamOption] = []
    var teamSelection: HighlightTeamSelection? = nil

    init(
        analysisJobId: String? = nil,
        sourceObjectKey: String? = nil,
        clipCount: Int,
        clips: [CloudClip],
        diagnostics: CloudDiagnostics,
        detectedTeams: [CloudTeamOption] = [],
        teamSelection: HighlightTeamSelection? = nil
    ) {
        self.analysisJobId = analysisJobId
        self.sourceObjectKey = sourceObjectKey
        self.clipCount = clipCount
        self.clips = clips
        self.diagnostics = diagnostics
        self.detectedTeams = detectedTeams
        self.teamSelection = teamSelection
    }

    enum CodingKeys: String, CodingKey {
        case analysisJobId
        case sourceObjectKey
        case clipCount
        case clips
        case diagnostics
        case detectedTeams
        case teamSelection
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        analysisJobId = try container.decodeIfPresent(String.self, forKey: .analysisJobId)
        sourceObjectKey = try container.decodeIfPresent(String.self, forKey: .sourceObjectKey)
        clipCount = try container.decode(Int.self, forKey: .clipCount)
        clips = try container.decode([CloudClip].self, forKey: .clips)
        diagnostics = try container.decode(CloudDiagnostics.self, forKey: .diagnostics)
        detectedTeams = try container.decodeIfPresent([CloudTeamOption].self, forKey: .detectedTeams) ?? []
        teamSelection = try container.decodeIfPresent(HighlightTeamSelection.self, forKey: .teamSelection)
    }

    func withJobMetadata(analysisJobId: String, sourceObjectKey: String?) -> CloudAnalysisResult {
        CloudAnalysisResult(
            analysisJobId: analysisJobId,
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
            return "The video upload did not complete."
        case .timedOut:
            return "Cloud analysis is taking longer than expected. Reopen the project from History and try again, or choose a shorter video."
        case .quotaExceeded(let remaining):
            if let remaining {
                return "Cloud analysis quota exceeded. Remaining today: \(remaining)."
            }
            return "Cloud analysis quota exceeded."
        case .backend(_, let message):
            return message
        case .network(let description):
            return description
        }
    }
}
