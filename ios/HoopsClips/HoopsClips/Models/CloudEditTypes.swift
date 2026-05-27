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

enum CloudEditProTemplate: String, CaseIterable, Identifiable, Sendable {
    case recruitingReelPro = "recruiting_reel_pro_v1"
    case cinematicMixtapePro = "cinematic_mixtape_pro_v1"
    case nbaRecapPro = "nba_recap_pro_v1"
    case teamHighlightPro = "team_highlight_pro_v1"

    var id: String { rawValue }
    var templateID: String { rawValue }

    var preset: CloudEditPreset {
        switch self {
        case .recruitingReelPro, .cinematicMixtapePro:
            return .personalHighlight
        case .nbaRecapPro, .teamHighlightPro:
            return .fullGameHighlight
        }
    }

    var title: String {
        switch self {
        case .recruitingReelPro:
            return "Recruiting Reel Pro"
        case .cinematicMixtapePro:
            return "Cinematic Mixtape Pro"
        case .nbaRecapPro:
            return "NBA Recap Pro"
        case .teamHighlightPro:
            return "Team Highlight Pro"
        }
    }

    var icon: String {
        switch self {
        case .recruitingReelPro:
            return "person.crop.rectangle.stack.fill"
        case .cinematicMixtapePro:
            return "camera.filters"
        case .nbaRecapPro:
            return "sportscourt.fill"
        case .teamHighlightPro:
            return "person.3.sequence.fill"
        }
    }

    var subtitle: String {
        switch self {
        case .recruitingReelPro:
            return "Recruiting-ready player story"
        case .cinematicMixtapePro:
            return "Premium social mixtape"
        case .nbaRecapPro:
            return "Broadcast-style game recap"
        case .teamHighlightPro:
            return "Team-first highlight package"
        }
    }

    var bestFor: String {
        switch self {
        case .recruitingReelPro:
            return "Best for coaches, scouts, and player profiles"
        case .cinematicMixtapePro:
            return "Best for polished Instagram and TikTok edits"
        case .nbaRecapPro:
            return "Best for clean YouTube or team recap videos"
        case .teamHighlightPro:
            return "Best for parents, teams, and season moments"
        }
    }

    var styleSummary: String {
        switch self {
        case .recruitingReelPro:
            return "Skill clarity, strong individual plays, cleaner recruiting captions."
        case .cinematicMixtapePro:
            return "Top social plays, dramatic captions, aggressive slow motion."
        case .nbaRecapPro:
            return "Chronological game story, clean lower thirds, game-audio priority."
        case .teamHighlightPro:
            return "Balanced players, offense-defense variety, team-style captions."
        }
    }

    var accessibilityIdentifier: String {
        switch self {
        case .recruitingReelPro:
            return "export.aiEdit.proTemplate.recruitingReel"
        case .cinematicMixtapePro:
            return "export.aiEdit.proTemplate.cinematicMixtape"
        case .nbaRecapPro:
            return "export.aiEdit.proTemplate.nbaRecap"
        case .teamHighlightPro:
            return "export.aiEdit.proTemplate.teamHighlight"
        }
    }

    var aspectRatio: CloudEditAspectRatio {
        switch self {
        case .recruitingReelPro, .cinematicMixtapePro:
            return .vertical
        case .nbaRecapPro, .teamHighlightPro:
            return .widescreen
        }
    }

    var durationOptions: [Int] {
        switch self {
        case .recruitingReelPro:
            return [45, 60, 90, 120]
        case .cinematicMixtapePro:
            return [30, 45, 60, 90]
        case .nbaRecapPro, .teamHighlightPro:
            return [90, 120, 180]
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
    case internalTier = "internal"
    case dev

    var isFree: Bool {
        self == .free
    }

    var usesPriorityQueue: Bool {
        self != .free
    }
}

struct CloudEditPolicySummary: Codable, Sendable {
    let planTier: CloudEditPlanTier
    let displayName: String
    let maxRenderSeconds: Int
    let maxDailyRenders: Int
    let maxActiveRenders: Int
    let maxRevisionsPerEdit: Int
    let maxOutputResolution: String
    let watermarkRequired: Bool
    let outroRequired: Bool
    let premiumTemplatesAllowed: Bool
    let renderRetentionDays: Int

    static let freeDefault = CloudEditPolicySummary(
        planTier: .free,
        displayName: "Free",
        maxRenderSeconds: 45,
        maxDailyRenders: 3,
        maxActiveRenders: 1,
        maxRevisionsPerEdit: 3,
        maxOutputResolution: "720p",
        watermarkRequired: true,
        outroRequired: true,
        premiumTemplatesAllowed: false,
        renderRetentionDays: 14
    )

    static let proDefault = CloudEditPolicySummary(
        planTier: .pro,
        displayName: "Pro",
        maxRenderSeconds: 180,
        maxDailyRenders: 25,
        maxActiveRenders: 2,
        maxRevisionsPerEdit: 10,
        maxOutputResolution: "1080p",
        watermarkRequired: false,
        outroRequired: false,
        premiumTemplatesAllowed: true,
        renderRetentionDays: 60
    )

    var queueTitle: String {
        planTier.usesPriorityQueue ? "Priority render" : "Standard render queue"
    }

    var queueDetail: String {
        planTier.usesPriorityQueue
            ? "Faster cloud editing when priority capacity is available."
            : "HoopClips keeps editing in the cloud. Pro gets priority rendering."
    }

    var brandingSummary: String {
        watermarkRequired || outroRequired
            ? "HoopClips watermark/outro included"
            : "Clean export: no required watermark or outro"
    }

    var retentionSummary: String {
        "Videos stored for \(renderRetentionDays) days"
    }

    var planLimitRows: [String] {
        [
            queueTitle,
            "\(maxOutputResolution) max export",
            brandingSummary,
            "\(maxDailyRenders) AI edits/day",
            "\(maxRevisionsPerEdit) revisions/edit",
            retentionSummary
        ]
    }

    static let proValueRows = [
        "Priority rendering",
        "1080p clean exports",
        "No required watermark",
        "No required HoopClips outro",
        "Longer videos",
        "More revisions",
        "Longer cloud storage",
        "Pro template packs"
    ]
}

struct CloudEditProUXFlags: Sendable {
    let proUpsellEnabled: Bool
    let proTemplatesEnabled: Bool
    let priorityQueueEnabled: Bool
    let cloudLockerEnabled: Bool

    static let safeDefault = CloudEditProUXFlags(
        proUpsellEnabled: true,
        proTemplatesEnabled: true,
        priorityQueueEnabled: true,
        cloudLockerEnabled: true
    )
}

struct CloudEditVersionResponse: Codable, Sendable {
    let service: String?
    let backendModelVersion: String?
    let gitSha: String?
    let featureFlags: CloudEditFeatureFlags?
}

struct CloudEditFeatureFlags: Codable, Sendable {
    let aiEditEnabled: Bool?
    let aiEditLiveRenderEnabled: Bool?
    let aiEditRevisionEnabled: Bool?
    let aiEditTemplatePackEnabled: Bool?
    let aiEditMaxDailyRenders: Int?
    let aiEditFreeWatermarkRequired: Bool?
    let aiEditProExportsEnabled: Bool?
    let gptHighlightRerankerEnabled: Bool?

    var allowsEditPlanning: Bool {
        aiEditEnabled ?? true
    }

    var allowsLiveRendering: Bool {
        aiEditLiveRenderEnabled ?? true
    }

    var allowsRevisions: Bool {
        aiEditRevisionEnabled ?? true
    }

    var allowsTemplatePacks: Bool {
        aiEditTemplatePackEnabled ?? true
    }
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
    case failedTimeout = "failed_timeout"
    case cancelled

    var displayLabel: String {
        switch self {
        case .renderRequested:
            return "HoopClips is starting your edit"
        case .planning:
            return "Building your AI edit"
        case .planReady:
            return "Applying your style"
        case .created:
            return "Preparing cloud edit"
        case .queued:
            return "Waiting for cloud editing"
        case .rendering:
            return "Rendering your highlight reel"
        case .rendered:
            return "Your reel is ready"
        case .failed:
            return "Render failed"
        case .failedTimeout:
            return "Render timed out"
        case .cancelled:
            return "Cancelled"
        }
    }
}

enum CloudEditWorkStepStatus: String, Codable, Sendable {
    case pending
    case running
    case complete
    case failed
}

struct CloudEditWorkStep: Codable, Identifiable, Sendable {
    let stepId: String
    let title: String
    let detail: String?
    let status: CloudEditWorkStepStatus
    let startedAt: String?
    let completedAt: String?

    var id: String { stepId }
}

struct CloudEditWorkTimeline: Codable, Sendable {
    let editJobId: String
    let revisionId: String?
    let renderJobId: String?
    let status: CloudEditRenderState
    let generatedAt: String?
    let steps: [CloudEditWorkStep]
}

struct CloudEditWorkReceipt: Codable, Sendable {
    let editJobId: String
    let revisionId: String?
    let renderJobId: String?
    let selectedClipCount: Int?
    let candidateClipCount: Int?
    let templateId: String?
    let templateName: String?
    let slowMotionMomentCount: Int
    let outputDurationSeconds: Double?
    let outputResolution: String?
    let aspectRatio: CloudEditAspectRatio?
    let watermarkIncluded: Bool?
    let outroIncluded: Bool?
    let storageExpiresAt: String?
    let planTier: CloudEditPlanTier?
    let priorityQueue: Bool
    let gptRerankApplied: Bool?
    let gptRerankModel: String?
    let gptRerankSampledClipCount: Int?
    let gptRerankSampledFrameCount: Int?
    let gptRerankKeptClipCount: Int?
    let gptRerankRejectedClipCount: Int?
    let gptRerankFallbackReason: String?
    let teamUncertainCandidateCount: Int?
    let teamUncertainSelectedClipCount: Int?
    let defensiveSelectedClipCount: Int?
    let summaryRows: [String]
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
    var nativeShotSignals: NativeShotSignals? = nil
    var teamAttribution: ClipTeamAttribution? = nil
    var teamAttributionStatus: String? = nil
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
    let revenueCatAppUserID: String?
    let userPrompt: String?
    var teamSelection: HighlightTeamSelection? = nil
    let clips: [CloudEditCandidateClip]
}

struct CloudEditJobResponse: Codable, Sendable {
    let editJobId: String
    let videoId: String
    let analysisJobId: String
    let status: String
    let preset: String
    let templateId: String?
    let planTier: CloudEditPlanTier?
    let policy: CloudEditPolicySummary?
    let targetDurationSeconds: Int
    let aspectRatio: CloudEditAspectRatio
    let clipCount: Int
    let validationErrors: [CloudEditValidationIssue]?
}

struct CloudEditPlanResponse: Codable, Sendable {
    let editJobId: String
    let status: String
    let plan: CloudEditPlanSummary
    let planTier: CloudEditPlanTier?
    let policy: CloudEditPolicySummary?
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
    let revenueCatAppUserID: String?
    let editPlan: CloudEditPlanSummary
    let sourceClips: [CloudEditCandidateClip]
    let idempotencyKey: String?
}

struct CloudEditStoredRenderRequest: Codable, Sendable {
    let installId: String
    let idempotencyKey: String?
    let forceNew: Bool
}

struct CloudEditRevisionRequest: Codable, Sendable {
    let installId: String
    let command: CloudEditRevisionCommand
}

struct CloudEditRevisionRenderRequest: Codable, Sendable {
    let installId: String
    let idempotencyKey: String?
}

struct CloudEditRetentionMetadata: Codable, Sendable {
    let expiresAt: String
    let retentionClass: String
    let deleteEligible: Bool
    let planTier: CloudEditPlanTier?
    let editJobId: String
    let renderJobId: String
    let templateId: String?
    let outputBytes: Int?
    let durationSeconds: Double?
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
    let revisionId: String?
    let renderJobId: String
    let renderer: String
    let rendererVersion: String
    let planVersion: String?
    let templateId: String?
    let status: CloudEditRenderState
    let outputObjectKey: String?
    let renderLogObjectKey: String?
    let durationSeconds: Double?
    let aspectRatio: CloudEditAspectRatio
    let traceId: String
    let failureReason: String?
    let validationErrors: [CloudEditValidationIssue]?
    let planTier: CloudEditPlanTier?
    let policy: CloudEditPolicySummary?
    let retryCount: Int?
    let outputBytes: Int?
    let retentionMetadata: CloudEditRetentionMetadata?
    let workTimeline: CloudEditWorkTimeline?
    let workReceipt: CloudEditWorkReceipt?
}

struct CloudEditRenderHistoryResponse: Codable, Sendable {
    let installId: String
    let generatedAt: String?
    let renders: [CloudEditRenderStatusResponse]
}

struct CloudEditDownloadResponse: Codable, Sendable {
    let editJobId: String
    let renderJobId: String
    let downloadUrl: String
    let outputObjectKey: String?
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
            return "This project needs a cloud-uploaded source video before HoopClips can render an AI edit."
        case .downloadURLExpired:
            return "The download link expired. HoopClips is requesting a fresh one."
        case .timedOut:
            return "Cloud rendering took too long. Try again with a shorter edit."
        case .backend(_, let message):
            return message
        case .network(let description):
            return description
        }
    }

    static func friendlyBackendMessage(code: String, fallback: String) -> String {
        switch code {
        case "video_too_long", "source_video_too_long":
            return "That video is too long for this plan. Try a shorter source clip set."
        case "render_cost_limit", "render_cost_too_high", "render_duration_limit":
            return "That edit is over this plan’s render limit. Choose a shorter length or upgrade later."
        case "daily_render_limit":
            return "You’ve used today’s AI edit renders. Try again tomorrow."
        case "active_render_limit":
            return "Another AI edit is still rendering. Let that finish before starting another."
        case "revision_limit":
            return "This edit has reached the revision limit for your plan."
        case "premium_template_required", "pro_entitlement_required":
            return "That template requires HoopClips Pro. Upgrade or choose a Free template."
        case "pro_entitlement_unverified", "revenuecat_verifier_unavailable":
            return "HoopClips could not verify your Pro access. Try again in a moment."
        case "revenuecat_verifier_unconfigured", "pro_exports_unavailable":
            return "Pro AI exports are not enabled in this environment yet."
        case "render_retry_limit":
            return "This render has already been retried. Start a new edit if you want to try again."
        case "storage_unavailable", "source_missing":
            return "Cloud storage is not ready for this edit. Try again after the upload finishes."
        case "download_url_expired":
            return "The download link expired. HoopClips is requesting a fresh one."
        case "failed_timeout":
            return "Rendering timed out. Try a shorter edit."
        case "render_failed":
            return "Cloud rendering failed. Try again in a moment."
        case "render_not_ready":
            return "Your video is still rendering. Try again when it is ready."
        case "render_expired":
            return "That cloud render expired. Request a fresh cloud render from My AI Edits."
        case "render_lease_active":
            return "That AI edit is already rendering. HoopClips will keep checking the existing job."
        case "render_lease_lost":
            return "The render worker lost its lock. Try again in a moment."
        case "download_url_refresh_failed":
            return "HoopClips could not refresh the download link. Try again in a moment."
        case "ai_edit_disabled":
            return "Cloud AI editing is temporarily paused. Try again after HoopClips re-enables editing."
        case "ai_edit_live_render_disabled":
            return "Cloud rendering is temporarily paused. HoopClips will keep AI edits in the cloud and retry when rendering is re-enabled."
        case "ai_edit_revision_disabled":
            return "AI edit revisions are temporarily paused. Your current render is still safe to preview and share."
        case "ai_edit_template_pack_disabled":
            return "Template packs are temporarily paused. Try again after HoopClips re-enables cloud templates."
        case "invalid_edit_plan":
            return "HoopClips could not validate that edit plan. Try a different template or shorter length."
        case "template_asset_missing":
            return "This template is missing a required asset. Try another template while we fix it."
        default:
            return fallback
        }
    }
}
