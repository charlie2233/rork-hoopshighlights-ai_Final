import Foundation

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
        resultObjectKey: String? = nil
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
    }
}

nonisolated struct StartCloudAnalysisJobRequest: Codable, Sendable {
    let installId: String
}

nonisolated struct StartCloudAnalysisJobResponse: Codable, Sendable {
    let jobId: String
    let status: String
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

    init(
        analysisJobId: String? = nil,
        sourceObjectKey: String? = nil,
        clipCount: Int,
        clips: [CloudClip],
        diagnostics: CloudDiagnostics
    ) {
        self.analysisJobId = analysisJobId
        self.sourceObjectKey = sourceObjectKey
        self.clipCount = clipCount
        self.clips = clips
        self.diagnostics = diagnostics
    }

    func withJobMetadata(analysisJobId: String, sourceObjectKey: String?) -> CloudAnalysisResult {
        CloudAnalysisResult(
            analysisJobId: analysisJobId,
            sourceObjectKey: sourceObjectKey ?? self.sourceObjectKey,
            clipCount: clipCount,
            clips: clips,
            diagnostics: diagnostics
        )
    }
}

nonisolated struct CloudClip: Codable, Sendable {
    let startTime: Double
    let endTime: Double
    let confidence: Double
    let label: String
    let action: String
    let audioScore: Double
    let visualScore: Double
    let motionScore: Double
    let combinedScore: Double
    let detectionMethod: String
    let shouldAutoKeep: Bool
    let shouldEnableSlowMotion: Bool

    func makeClip() -> Clip {
        let resolvedAction = HighlightAction(rawValue: action)
            ?? HighlightAction.allCases.first(where: { $0.rawValue.localizedCaseInsensitiveCompare(action) == .orderedSame })
            ?? .unknown
        let resolvedMethod = DetectionMethod(rawValue: detectionMethod) ?? .cloud
        return Clip(
            startTime: startTime,
            endTime: endTime,
            action: resolvedAction,
            confidence: confidence,
            isKept: shouldAutoKeep,
            label: label,
            audioScore: audioScore,
            visualScore: visualScore,
            motionScore: motionScore,
            combinedScore: combinedScore,
            isSlowMotionEnabled: shouldEnableSlowMotion,
            detectionMethod: resolvedMethod
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
            return "Cloud analysis took too long and timed out."
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
