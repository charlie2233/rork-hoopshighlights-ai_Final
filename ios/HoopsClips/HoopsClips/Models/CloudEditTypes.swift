import Foundation

enum CloudEditPreset: String, Codable, CaseIterable, Identifiable, Sendable {
    case personalHighlight = "personal_highlight"
    case fullGameHighlight = "full_game_highlight"
    case coachReview = "coach_review"

    var id: String { rawValue }

    var templateID: String {
        switch self {
        case .personalHighlight:
            return "personal_highlight_v1"
        case .fullGameHighlight:
            return "full_game_highlight_v1"
        case .coachReview:
            return "coach_review_v1"
        }
    }

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

    var icon: String {
        switch self {
        case .personalHighlight:
            return "bolt.fill"
        case .fullGameHighlight:
            return "sportscourt.fill"
        case .coachReview:
            return "clipboard.fill"
        }
    }

    var subtitle: String {
        switch self {
        case .personalHighlight:
            return "Fast vertical hype reel"
        case .fullGameHighlight:
            return "Clean game recap"
        case .coachReview:
            return "Simple chronological film review"
        }
    }

    var bestFor: String {
        switch self {
        case .personalHighlight:
            return "Best for TikTok, Instagram, and recruiting"
        case .fullGameHighlight:
            return "Best for recaps, YouTube, and team sharing"
        case .coachReview:
            return "Best for coaches, trainers, and parents"
        }
    }

    var styleSummary: String {
        switch self {
        case .personalHighlight:
            return "Best plays first, bold captions, slow motion, music-forward."
        case .fullGameHighlight:
            return "Game-flow order, cleaner captions, subtle effects, louder game audio."
        case .coachReview:
            return "Chronological, original audio, minimal captions, restrained effects."
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

    var title: String {
        switch self {
        case .vertical:
            return "Vertical"
        case .widescreen:
            return "Widescreen"
        case .source:
            return "Source"
        }
    }

    var subtitle: String {
        switch self {
        case .vertical:
            return "9:16 social reel"
        case .widescreen:
            return "16:9 game recap"
        case .source:
            return "Use source framing"
        }
    }

    var icon: String {
        switch self {
        case .vertical:
            return "rectangle.portrait.fill"
        case .widescreen:
            return "rectangle.fill"
        case .source:
            return "aspectratio.fill"
        }
    }
}

enum CloudEditPlanTier: String, Codable, Sendable {
    case free
    case pro
}

enum CloudEditRenderState: String, Codable, Sendable {
    case renderRequested = "render_requested"
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
        case .renderRequested:
            return "Render requested"
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

enum CloudEditRevisionCommand: String, Codable, CaseIterable, Identifiable, Sendable {
    case makeShorter = "make_shorter"
    case makeLonger = "make_longer"
    case makeMoreHype = "make_more_hype"
    case makeNBAStyle = "make_nba_style"
    case addMoreSlowMotion = "add_more_slow_motion"
    case removeWeakClips = "remove_weak_clips"
    case useOriginalAudio = "use_original_audio"
    case switchFormatVertical = "switch_format_vertical"
    case switchFormatWidescreen = "switch_format_widescreen"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .makeShorter:
            return "Shorter"
        case .makeLonger:
            return "Longer"
        case .makeMoreHype:
            return "More Hype"
        case .makeNBAStyle:
            return "NBA Style"
        case .addMoreSlowMotion:
            return "More Slow-Mo"
        case .removeWeakClips:
            return "Remove Weak Clips"
        case .useOriginalAudio:
            return "Original Audio"
        case .switchFormatVertical:
            return "Vertical"
        case .switchFormatWidescreen:
            return "Widescreen"
        }
    }

    var icon: String {
        switch self {
        case .makeShorter:
            return "minus.forwardslash.plus"
        case .makeLonger:
            return "plus.forwardslash.minus"
        case .makeMoreHype:
            return "bolt.fill"
        case .makeNBAStyle:
            return "sportscourt.fill"
        case .addMoreSlowMotion:
            return "slowmo"
        case .removeWeakClips:
            return "scissors"
        case .useOriginalAudio:
            return "waveform"
        case .switchFormatVertical:
            return "rectangle.portrait.fill"
        case .switchFormatWidescreen:
            return "rectangle.fill"
        }
    }

    var accessibilityIdentifier: String {
        switch self {
        case .makeShorter:
            return "export.aiEdit.revision.shorter"
        case .makeLonger:
            return "export.aiEdit.revision.longer"
        case .makeMoreHype:
            return "export.aiEdit.revision.moreHype"
        case .makeNBAStyle:
            return "export.aiEdit.revision.nbaStyle"
        case .addMoreSlowMotion:
            return "export.aiEdit.revision.moreSlowMo"
        case .removeWeakClips:
            return "export.aiEdit.revision.removeWeak"
        case .useOriginalAudio:
            return "export.aiEdit.revision.originalAudio"
        case .switchFormatVertical:
            return "export.aiEdit.revision.vertical"
        case .switchFormatWidescreen:
            return "export.aiEdit.revision.widescreen"
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
    let templateId: String
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
    let templateId: String?
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
    let templateId: String?
    let theme: String
    let captionStyle: String?
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
    let assetId: String?
}

struct CloudEditWatermark: Codable, Sendable {
    let enabled: Bool
    let position: String
    let assetId: String?
}

struct CloudEditRenderRequest: Codable, Sendable {
    let installId: String
    let sourceObjectKey: String
    let planTier: CloudEditPlanTier
    let editPlan: CloudEditPlanSummary
    let sourceClips: [CloudEditCandidateClip]
}

struct CloudEditRevisionRequest: Codable, Sendable {
    let installId: String
    let command: CloudEditRevisionCommand
}

struct CloudEditRevisionRenderRequest: Codable, Sendable {
    let installId: String
}

struct CloudEditPlanPatch: Codable, Sendable {
    let version: String
    let baseEditPlanId: String
    let revisionIntent: String
    let summary: String
    let operations: [CloudEditPlanPatchOperation]
    let requiresRerender: Bool
}

struct CloudEditPlanPatchOperation: Codable, Sendable {
    let op: String
    let path: String
    let reason: String?
}

struct CloudEditRevisionValidationResult: Codable, Sendable {
    let valid: Bool
    let errors: [CloudEditValidationIssue]
}

struct CloudEditRevisionResponse: Codable, Sendable {
    let revisionId: String
    let editJobId: String
    let basePlanId: String
    let newPlanId: String
    let command: CloudEditRevisionCommand
    let status: String
    let patch: CloudEditPlanPatch
    let revisedPlan: CloudEditPlanSummary
    let validationResult: CloudEditRevisionValidationResult
    let requiresRerender: Bool
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
    case downloadURLExpired
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
        case .downloadURLExpired:
            return "The download link expired. Hoopclips is requesting a fresh one."
        case .timedOut:
            return "Cloud rendering took too long. Try again with a shorter edit."
        case .backend(_, let message):
            return message
        case .network(let description):
            return description
        }
    }
}
