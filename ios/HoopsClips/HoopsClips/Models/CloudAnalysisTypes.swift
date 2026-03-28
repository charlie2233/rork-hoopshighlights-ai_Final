import Foundation

nonisolated enum AnalysisExecutionMode: String, Codable, Sendable {
    case cloud
    case localFallback
}

nonisolated struct CloudUploadPresignRequest: Codable, Sendable {
    let filename: String
    let contentType: String
    let fileSizeBytes: Int64
    let durationSeconds: Double
    let installId: String
    let appVersion: String
    let analysisVersion: String
}

nonisolated struct CloudUploadPresignResponse: Codable, Sendable {
    let requestId: String
    let jobId: String
    let uploadUrl: String
    let uploadMethod: String
    let uploadHeaders: [String: String]
    let uploadObjectKey: String
    let resultObjectKey: String
    let expiresAt: Date
    var schemaVersion: String? = nil
    var modelVersion: String? = nil
    var uploadTraceId: String? = nil
    var failureReason: String? = nil

    enum CodingKeys: String, CodingKey {
        case requestId
        case jobId
        case uploadUrl
        case uploadMethod
        case uploadHeaders
        case uploadObjectKey = "sourceObjectKey"
        case resultObjectKey
        case expiresAt
        case schemaVersion
        case modelVersion
        case uploadTraceId
        case failureReason
    }
}

nonisolated struct CloudCreateJobRequest: Codable, Sendable {
    let jobId: String
    let installId: String
    let sourceObjectKey: String
    let resultObjectKey: String
}

nonisolated struct CloudCreateJobResponse: Codable, Sendable {
    let requestId: String
    let jobId: String
    let status: String
    var pollAfterSeconds: Int? = nil
    var uploadTraceId: String? = nil
    var inferenceAttemptId: String? = nil
    var modelVersion: String? = nil
    var failureReason: String? = nil
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
    let requestId: String
    let jobId: String
    let uploadUrl: String
    let uploadMethod: String
    let uploadHeaders: [String: String]
    let expiresAt: Date
    let pollAfterSeconds: Int
    let quotaRemainingToday: Int
    let analysisMode: String
    var uploadTraceId: String? = nil
    var inferenceAttemptId: String? = nil
    let modelVersion: String?
    let failureReason: String?
}

nonisolated struct StartCloudAnalysisJobRequest: Codable, Sendable {
    let installId: String
}

nonisolated struct StartCloudAnalysisJobResponse: Codable, Sendable {
    let requestId: String
    let jobId: String
    let status: String
    var uploadTraceId: String? = nil
    var inferenceAttemptId: String? = nil
    let modelVersion: String?
    let failureReason: String?
}

nonisolated struct CloudAnalysisJobResponse: Codable, Sendable {
    let requestId: String
    let jobId: String
    let status: String
    let progress: Double
    let stage: String
    var confidence: Double? = nil
    var errorCode: String? = nil
    var errorMessage: String? = nil
    let analysisVersion: String
    var schemaVersion: String? = nil
    var uploadTraceId: String? = nil
    var inferenceAttemptId: String? = nil
    var results: CloudAnalysisResult? = nil
    var modelVersion: String? = nil
    var failureReason: String? = nil
    var pollAfterSeconds: Int? = nil
}

nonisolated struct CloudAnalysisResult: Codable, Sendable {
    var requestId: String? = nil
    var uploadTraceId: String? = nil
    var inferenceAttemptId: String? = nil
    let clipCount: Int
    let clips: [CloudClip]
    let diagnostics: CloudDiagnostics
    var resultConfidence: Double? = nil
    var confidence: Double? = nil
    var schemaVersion: String? = nil
    var modelVersion: String? = nil
    var failureReason: String? = nil
}

nonisolated struct CloudLabelScore: Codable, Sendable {
    let label: String
    let confidence: Double
    var rawLabel: String? = nil
    var modelVersion: String? = nil
}

nonisolated struct CloudRawLabelScore: Codable, Sendable {
    let rawLabel: String
    let confidence: Double
    var canonicalLabel: String? = nil
    var modelVersion: String? = nil
}

nonisolated struct CloudClip: Codable, Sendable {
    let clipId: String?
    let startTime: Double
    let endTime: Double
    let confidence: Double
    let label: String
    let action: String
    var canonicalLabel: String? = nil
    var eventFamily: String? = nil
    var eventSubtype: String? = nil
    var shotSubtype: String? = nil
    var outcome: String? = nil
    let audioScore: Double
    let visualScore: Double
    let motionScore: Double
    let combinedScore: Double
    var confidenceBeforeMapping: Double? = nil
    var confidenceAfterMapping: Double? = nil
    let detectionMethod: String
    let shouldAutoKeep: Bool
    let shouldEnableSlowMotion: Bool
    var isUncertain: Bool? = nil
    var eventType: String? = nil
    var shotType: String? = nil
    var makeMiss: String? = nil
    var rankScore: Double? = nil
    var reviewStatus: String? = nil
    var topLabels: [CloudLabelScore]? = nil
    var comparisonTopLabels: [CloudLabelScore]? = nil
    var rawTopLabels: [CloudRawLabelScore]? = nil
    var comparisonRawTopLabels: [CloudRawLabelScore]? = nil

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
    var modelVersion: String? = nil
    let usedVideoIntelligence: Bool
    let usedGeminiRelabeling: Bool
    let candidateSegments: Int
    let finalSegments: Int
    var failureReason: String? = nil
}

nonisolated struct CloudAnalysisTraceSnapshot: Codable, Sendable, Equatable {
    var requestId: String
    var uploadTraceId: String?
    var inferenceAttemptId: String?
    var modelVersion: String?
    var failureReason: String?
}

nonisolated struct CloudAnalysisAPIError: Codable, Sendable {
    var requestId: String? = nil
    let errorCode: String
    let errorMessage: String
    var quotaRemainingToday: Int? = nil
    var modelVersion: String? = nil
    var failureReason: String? = nil
}

nonisolated enum CloudAnalysisJobState: String, Codable, Sendable {
    case created
    case uploadPending = "upload_pending"
    case uploaded
    case queued
    case processing
    case completed
    case succeeded
    case failed
    case expired
    case cancelled
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
