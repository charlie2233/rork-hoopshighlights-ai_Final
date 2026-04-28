import Foundation

enum CloudEditPreset: String, Codable, CaseIterable, Identifiable, Sendable {
    case personalHighlight = "personal_highlight"
    case fullGameHighlight = "full_game_highlight"
    case coachReview = "coach_review"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .personalHighlight:
            return "Personal Highlight"
        case .fullGameHighlight:
            return "Full Game Highlight"
        case .coachReview:
            return "Coach Review"
        }
    }

    var subtitle: String {
        switch self {
        case .personalHighlight:
            return "Vertical hype reel with captions, slow motion, and a Hoopclips outro."
        case .fullGameHighlight:
            return "Widescreen recap with cleaner pacing and more game audio."
        case .coachReview:
            return "Simple chronological review with minimal styling."
        }
    }

    var aspectRatio: CloudEditAspectRatio {
        switch self {
        case .personalHighlight:
            return .vertical
        case .fullGameHighlight, .coachReview:
            return .widescreen
        }
    }

    var durationOptions: [Int] {
        switch self {
        case .personalHighlight:
            return [15, 30, 45]
        case .fullGameHighlight:
            return [60, 90, 120]
        case .coachReview:
            return [60, 120, 180]
        }
    }
}

enum CloudEditAspectRatio: String, Codable, Sendable {
    case vertical = "9:16"
    case widescreen = "16:9"
    case source
}

enum CloudEditPlanTier: String, Codable, Sendable {
    case free
    case pro
}

enum CloudEditRenderState: String, Codable, Sendable {
    case planning
    case planReady = "plan_ready"
    case created
    case queued
    case rendering
    case rendered
    case failed
    case cancelled

    var displayLabel: String {
        switch self {
        case .planning:
            return "Planning"
        case .planReady:
            return "Plan ready"
        case .created:
            return "Created"
        case .queued:
            return "Queued"
        case .rendering:
            return "Rendering"
        case .rendered:
            return "Rendered"
        case .failed:
            return "Failed"
        case .cancelled:
            return "Cancelled"
        }
    }
}

struct CloudEditCandidateClip: Codable, Sendable {
    let id: String
    let start: Double
    let end: Double
    let eventCenter: Double
    let label: String
    let confidence: Double
    let excitement: Double
    let watchability: Double
    let motionScore: Double
    let audioPeak: Double
    let combinedScore: Double?
    let duplicateGroup: String?
}

struct CreateCloudEditJobRequest: Codable, Sendable {
    let videoId: String
    let analysisJobId: String
    let installId: String
    let sourceObjectKey: String
    let preset: String
    let targetDurationSeconds: Int
    let aspectRatio: CloudEditAspectRatio
    let planTier: CloudEditPlanTier
    let clips: [CloudEditCandidateClip]
}

struct CloudEditJobResponse: Codable, Sendable {
    let editJobId: String
    let videoId: String
    let analysisJobId: String
    let status: String
    let preset: String
    let targetDurationSeconds: Int
    let aspectRatio: CloudEditAspectRatio
    let clipCount: Int
    let validationErrors: [CloudEditValidationIssue]?
}

struct CloudEditPlanResponse: Codable, Sendable {
    let editJobId: String
    let status: String
    let plan: CloudEditPlanSummary
    let validationErrors: [CloudEditValidationIssue]?
}

struct CloudEditPlanSummary: Codable, Sendable {
    let version: String
    let editJobId: String
    let videoId: String
    let analysisJobId: String
    let preset: String
    let theme: String
    let targetDurationSeconds: Int
    let aspectRatio: CloudEditAspectRatio
    let renderMode: String
    let audio: CloudEditPlanAudio
    let clips: [CloudEditPlanClip]
    let intro: CloudEditTimedTemplate
    let outro: CloudEditTimedTemplate
    let watermark: CloudEditWatermark
}

struct CloudEditPlanAudio: Codable, Sendable {
    let mode: String
    let musicTrackId: String
    let musicVolume: Double
    let gameAudioVolume: Double
}

struct CloudEditPlanClip: Codable, Sendable {
    let clipId: String
    let label: String
    let caption: String
    let sourceStart: Double
    let sourceEnd: Double
    let eventCenter: Double
    let timelineStart: Double
    let timelineEnd: Double
    let cropMode: String
    let effects: [CloudEditPlanEffect]
}

struct CloudEditPlanEffect: Codable, Sendable {
    let type: String
    let at: Double?
    let sourceStart: Double?
    let sourceEnd: Double?
    let speed: Double?
    let strength: Double?
}

struct CloudEditTimedTemplate: Codable, Sendable {
    let enabled: Bool
    let durationSeconds: Double
    let templateId: String
}

struct CloudEditWatermark: Codable, Sendable {
    let enabled: Bool
    let position: String
}

struct CloudEditRenderRequest: Codable, Sendable {
    let installId: String
    let sourceObjectKey: String
    let planTier: CloudEditPlanTier
    let editPlan: CloudEditPlanSummary
    let sourceClips: [CloudEditCandidateClip]
}

struct CloudEditRenderStatusResponse: Codable, Sendable {
    let editJobId: String
    let renderJobId: String
    let renderer: String
    let rendererVersion: String
    let status: CloudEditRenderState
    let outputObjectKey: String?
    let renderLogObjectKey: String?
    let durationSeconds: Double?
    let aspectRatio: CloudEditAspectRatio
    let traceId: String
    let failureReason: String?
    let validationErrors: [CloudEditValidationIssue]?
}

struct CloudEditDownloadResponse: Codable, Sendable {
    let editJobId: String
    let renderJobId: String
    let downloadUrl: String
    let outputObjectKey: String
    let contentType: String
    let expiresAt: Date
}

struct CloudEditValidationIssue: Codable, Sendable {
    let field: String
    let code: String
    let message: String
}

struct CloudEditAPIError: Codable, Sendable {
    let errorCode: String
    let errorMessage: String
    let failureReason: String?
}

enum CloudEditError: Error, LocalizedError, Sendable {
    case notConfigured
    case invalidResponse
    case missingSourceObject
    case timedOut
    case backend(code: String, message: String)
    case network(String)

    var errorDescription: String? {
        switch self {
        case .notConfigured:
            return "Cloud AI editing is not configured in this build."
        case .invalidResponse:
            return "The editing service returned an invalid response."
        case .missingSourceObject:
            return "This project needs a cloud-uploaded source video before Hoopclips can render an AI edit."
        case .timedOut:
            return "Cloud rendering took too long. Try again with a shorter edit."
        case .backend(_, let message):
            return message
        case .network(let description):
            return description
        }
    }
}
