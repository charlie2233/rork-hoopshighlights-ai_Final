import Foundation
import Observation

enum AppLanguage: String, CaseIterable, Identifiable {
    case english = "en"
    case chinese = "zh-Hans"
    case spanish = "es"
    case french = "fr"

    var id: String { rawValue }

    var locale: Locale {
        Locale(identifier: rawValue)
    }

    var englishName: String {
        switch self {
        case .english:
            return "English"
        case .chinese:
            return "Chinese"
        case .spanish:
            return "Spanish"
        case .french:
            return "French"
        }
    }

    var nativeName: String {
        switch self {
        case .english:
            return "English"
        case .chinese:
            return "中文"
        case .spanish:
            return "Español"
        case .french:
            return "Français"
        }
    }

    var settingsDescription: String {
        switch self {
        case .english:
            return "Use English for app navigation and launch screens."
        case .chinese:
            return "使用中文显示主要导航和启动界面。"
        case .spanish:
            return "Usa español en la navegación principal y pantallas de inicio."
        case .french:
            return "Utilise le français pour la navigation et les écrans de départ."
        }
    }
}

enum AppTextKey {
    case tabPlayer
    case tabReview
    case tabExport
    case tabHistory
    case tabSettings
    case settingsTitle
    case languageTitle
    case languageSubtitle
    case languageCardTitle
    case languageCardSubtitle
    case languageCurrent
    case languageRestartNote
    case authTagline
    case signInError
    case continueWithGoogle
    case continueWithEmail
    case continueWithPhone
    case continueAsGuest
    case or
    case legalPrefix
    case legalTerms
    case legalAnd
    case legalPrivacy
    case legalFallback
    case email
    case password
    case passwordPlaceholder
    case signingIn
    case signIn
    case phoneNumber
    case sendCode
    case verificationCode
    case verifying
    case verifyAndSignIn
    case resendCode
    case codeSent
    case demoCodeNote
    case backToSignIn
    case region
    case willSendTo
    case playerTitle
    case importVideo
    case photoLibrary
    case files
    case noHighlightsFound
    case noHighlightsMessage
    case noHighlightsAlternateMessage
    case proRequiredTitle
    case notNow
    case goPro
    case proRequiredMessagePrefix
    case proRequiredMessageMiddle
    case turnGamesTitle
    case turnGamesSubtitle
    case selectVideo
    case smartHighlights
    case fastReels
    case autoTrim
    case sourceVideo
    case sourceVideoSubtitle
    case duration
    case format
    case aiAnalysis
    case aiAnalysisSubtitle
    case analyzeWithAI
    case analysisButtonSubtitle
    case analysisButtonUpgradePrefix
    case analysisComplete
    case clipsFound
    case kept
    case estimated
    case analysis
    case projectSnapshot
    case projectSnapshotSubtitle
    case detected
    case readyToFind
    case freeTierLimitPrefix
    case freeTierLimitSuffix
    case freeAnalysisRemainingSingular
    case freeAnalysisRemainingPlural
    case dailyAnalysesUsed
    case uploading
    case queued
    case analyzing
    case finalizing
    case refining
    case controlRoom
    case controlRoomSubtitle
    case account
    case plan
    case freeLeft
    case targetReel
    case export
    case workflowDefaults
    case workflowDefaultsSubtitle
    case membershipAccount
    case membershipAccountSubtitle
    case accountQuickActions
    case supportCenter
    case supportCenterSubtitle
    case aboutPrivacy
    case aboutPrivacySubtitle
    case resetDefaultsDescription
    case settingsThreshold
    case settingsTarget
    case settingsSampling
    case settingsDraftType
    case settingsDraftChars
    case settingsOnDevice
    case settingsHistory
    case settingsEngine
    case settingsVisionAudio
    case settingsUnlimited
    case settingsMonthly
    case settingsAccountPlan
    case settingsSignedInWith
    case settingsWorkflowDetailSubtitle
    case settingsMembershipDetailSubtitle
    case settingsSupportDetailSubtitle
    case settingsAboutDetailSubtitle
    case settingsLegal
    case settingsLegalSubtitle
    case settingsPrivacyPolicySubtitle
    case settingsTermsSubtitle
    case settingsOnDeviceLibrary
    case settingsOnDeviceLibraryDescription
    case settingsSourceVideoTag
    case settingsLatestExportTag
    case settingsEventTimelineTag
    case settingsRestoreOnLaunchTag
    case settingsAIAnalysisWeights
    case settingsAudioCrowdNoise
    case settingsMotionDetection
    case settingsBodyPoseAnalysis
    case settingsSceneBrightness
    case settingsTotalWeight
    case settingsCurrentDetectionProfile
    case settingsBalanced
    case settingsAdjust
    case settingsWeights
    case settingsKeepUncertain
    case settingsOn
    case settingsOff
    case settingsTargetReel
    case settingsClipReelDuration
    case settingsMinimum
    case settingsMaximum
    case settingsTargetHighlight
    case settingsShortestClipHelp
    case settingsLongestClipHelp
    case settingsTargetHighlightHelp
    case settingsAdvancedSettings
    case settingsAdvancedSubtitle
    case settingsCustom
    case settingsConfidenceThreshold
    case settingsLowerConfidenceHelp
    case settingsDetectionBehavior
    case settingsClipPadding
    case settingsClipPaddingHelp
    case settingsKeepUncertainClips
    case settingsKeepUncertainHelp
    case settingsPerformance
    case settingsFramesPerSecond
    case settingsPerformanceHelp
    case settingsAbout
    case settingsAboutDescription
    case settingsSmartClipsTag
    case settingsPrivateTag
    case settingsFastExportTag
    case settingsShareReadyTag
    case settingsContactSuggestions
    case settingsContactSubtitle
    case settingsFeedbackSuggestion
    case settingsFeedbackBug
    case settingsFeedbackQuestion
    case settingsFeedbackType
    case settingsEmailOptional
    case settingsMessage
    case settingsMessagePlaceholder
    case settingsClear
    case settingsSending
    case settingsSend
    case settingsFeedbackPrivacyNote
    case settingsCommonFAQ
    case settingsFAQSubtitle
    case settingsFAQNoClipsQuestion
    case settingsFAQNoClipsAnswer
    case settingsFAQWeightsQuestion
    case settingsFAQWeightsAnswer
    case settingsFAQExportFormatQuestion
    case settingsFAQExportFormatAnswer
    case settingsFAQQuickShareQuestion
    case settingsFAQQuickShareAnswer
    case settingsAccountDetailsSubtitle
    case settingsSubscription
    case settingsProMember
    case settingsUnlimitedAccess
    case settingsUnlimitedAIExports
    case settingsSignInRequired
    case settingsFreeTier
    case settingsPerMonth
    case settingsSignInToUpgrade
    case settingsUpgradeToPro
    case settingsSignOut
    case settingsGuest
    case settingsUnknown
    case settingsResetTitle
    case settingsReset
    case settingsCancel
    case settingsResetMessage
    case settingsResetToDefaults
    case settingsMissingReleaseURL
    case settingsFeedbackValidationMessage
    case settingsFeedbackConfigError
    case settingsFeedbackSendFailure
    case settingsFeedbackNetworkError
    case settingsFeedbackSentThanks
    case settingsDeveloperFootnote
}

@Observable
final class AppLanguageStore {
    private static let defaultsKey = "hoops.selectedAppLanguage"
    private let defaults: UserDefaults

    var selectedLanguage: AppLanguage {
        didSet {
            defaults.set(selectedLanguage.rawValue, forKey: Self.defaultsKey)
        }
    }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        let storedValue = defaults.string(forKey: Self.defaultsKey)
        selectedLanguage = storedValue.flatMap(AppLanguage.init(rawValue:)) ?? .english
    }

    func text(_ key: AppTextKey) -> String {
        selectedLanguage.text(key)
    }
}

extension AppLanguage {
    func text(_ key: AppTextKey) -> String {
        switch self {
        case .english:
            return Self.englishText[key] ?? ""
        case .chinese:
            return Self.chineseText[key] ?? Self.englishText[key] ?? ""
        case .spanish:
            return Self.spanishText[key] ?? Self.englishText[key] ?? ""
        case .french:
            return Self.frenchText[key] ?? Self.englishText[key] ?? ""
        }
    }

    private static let englishText: [AppTextKey: String] = [
        .tabPlayer: "Player",
        .tabReview: "Review",
        .tabExport: "Export",
        .tabHistory: "History",
        .tabSettings: "Settings",
        .settingsTitle: "Settings",
        .languageTitle: "Language",
        .languageSubtitle: "Choose the language Hoops Clips uses.",
        .languageCardTitle: "App Language",
        .languageCardSubtitle: "Pick the language for navigation, launch screens, and core controls.",
        .languageCurrent: "Current",
        .languageRestartNote: "Most text updates immediately. System dialogs may follow your iPhone language.",
        .authTagline: "Turn basketball videos into share-ready highlight reels.\nSign in to start clipping.",
        .signInError: "Sign In Error",
        .continueWithGoogle: "Continue with Google",
        .continueWithEmail: "Continue with Email",
        .continueWithPhone: "Continue with Phone",
        .continueAsGuest: "Continue as Guest",
        .or: "or",
        .legalPrefix: "By signing in, you agree to our",
        .legalTerms: "Terms of Service",
        .legalAnd: "and",
        .legalPrivacy: "Privacy Policy",
        .legalFallback: "By signing in, you agree to our Terms of Service and Privacy Policy.",
        .email: "Email",
        .password: "Password",
        .passwordPlaceholder: "Min 6 characters",
        .signingIn: "Signing in...",
        .signIn: "Sign In",
        .phoneNumber: "Phone Number",
        .sendCode: "Send Code",
        .verificationCode: "Verification Code",
        .verifying: "Verifying...",
        .verifyAndSignIn: "Verify & Sign In",
        .resendCode: "Resend Code",
        .codeSent: "Verification code sent",
        .demoCodeNote: "Demo mode — in production, codes are sent via SMS/email",
        .backToSignIn: "Back to sign in options",
        .region: "Region",
        .willSendTo: "Will send to",
        .playerTitle: "Hoops Clips",
        .importVideo: "Import Video",
        .photoLibrary: "Photo Library",
        .files: "Files",
        .noHighlightsFound: "No Highlights Found",
        .noHighlightsMessage: "Analysis finished without finding enough confident highlights in this clip.",
        .noHighlightsAlternateMessage: "AI couldn't detect enough confident highlights in this video.",
        .proRequiredTitle: "Pro Required for Longer Videos",
        .notNow: "Not Now",
        .goPro: "Go Pro",
        .proRequiredMessagePrefix: "Free tier can analyze videos up to",
        .proRequiredMessageMiddle: "This video is",
        .turnGamesTitle: "Turn Games Into Hoops Clips",
        .turnGamesSubtitle: "Find your best plays, trim the dead time,\nand build a share-ready reel in minutes.",
        .selectVideo: "Select Video",
        .smartHighlights: "Smart Highlights",
        .fastReels: "Fast Reels",
        .autoTrim: "Auto Trim",
        .sourceVideo: "Source Video",
        .sourceVideoSubtitle: "Loaded and ready for AI analysis",
        .duration: "Duration",
        .format: "Format",
        .aiAnalysis: "AI Analysis",
        .aiAnalysisSubtitle: "Find the best plays, trim the noise, and build a reel fast.",
        .analyzeWithAI: "Analyze with AI",
        .analysisButtonSubtitle: "Find highlight clips from this video",
        .analysisButtonUpgradePrefix: "Upgrade to analyze videos longer than",
        .analysisComplete: "Analysis Complete",
        .clipsFound: "Clips Found",
        .kept: "Kept",
        .estimated: "Estimated",
        .analysis: "analysis",
        .projectSnapshot: "Project Snapshot",
        .projectSnapshotSubtitle: "Quick context before review and export",
        .detected: "Detected",
        .readyToFind: "Ready to find your best clips.",
        .freeTierLimitPrefix: "Free tier supports up to",
        .freeTierLimitSuffix: "Upgrade to analyze longer games.",
        .freeAnalysisRemainingSingular: "free analysis remaining today.",
        .freeAnalysisRemainingPlural: "free analyses remaining today.",
        .dailyAnalysesUsed: "You've used today's free analyses. Upgrade for unlimited access.",
        .uploading: "Uploading...",
        .queued: "Queued...",
        .analyzing: "Analyzing...",
        .finalizing: "Finalizing...",
        .refining: "Refining...",
        .controlRoom: "App Setup",
        .controlRoomSubtitle: "Manage language, membership, defaults, and support from clean sections.",
        .account: "Account",
        .plan: "Plan",
        .freeLeft: "Free Left",
        .targetReel: "Target Reel",
        .export: "Export",
        .workflowDefaults: "Workflow Defaults",
        .workflowDefaultsSubtitle: "Clip duration, confidence, AI weighting, and reel-shaping rules.",
        .membershipAccount: "Membership & Account",
        .membershipAccountSubtitle: "Identity, subscription status, upgrade controls, and sign out.",
        .accountQuickActions: "Account Quick Actions",
        .supportCenter: "Support Center",
        .supportCenterSubtitle: "Send feedback, report bugs, and browse quick answers.",
        .aboutPrivacy: "About & Privacy",
        .aboutPrivacySubtitle: "How the app works, what is saved on device, and reset controls.",
        .resetDefaultsDescription: "Restore all AI tuning values to the original Hoops Clips defaults.",
        .settingsThreshold: "Threshold",
        .settingsTarget: "Target",
        .settingsSampling: "Sampling",
        .settingsDraftType: "Draft Type",
        .settingsDraftChars: "Draft Chars",
        .settingsOnDevice: "On Device",
        .settingsHistory: "History",
        .settingsEngine: "Engine",
        .settingsVisionAudio: "Vision + Audio",
        .settingsUnlimited: "Unlimited",
        .settingsMonthly: "Monthly",
        .settingsAccountPlan: "Account & Plan",
        .settingsSignedInWith: "Signed in with",
        .settingsWorkflowDetailSubtitle: "Tune clip selection and analysis behavior for your footage.",
        .settingsMembershipDetailSubtitle: "See how you're signed in and manage access.",
        .settingsSupportDetailSubtitle: "Feedback, bug reports, and setup help in one place.",
        .settingsAboutDetailSubtitle: "Core app details, storage behavior, and device-local history notes.",
        .settingsLegal: "Legal",
        .settingsLegalSubtitle: "Open the policies that stay reachable from the shipped app and App Store listing.",
        .settingsPrivacyPolicySubtitle: "Review how account, billing, and device-local processing are described.",
        .settingsTermsSubtitle: "Review product terms, acceptable use, and subscription language.",
        .settingsOnDeviceLibrary: "On-Device Library",
        .settingsOnDeviceLibraryDescription: "Imported videos, the latest export for each project, and the project event timeline stay in the app's local storage on this device. Nothing here is synced to a server by this feature.",
        .settingsSourceVideoTag: "Source Video",
        .settingsLatestExportTag: "Latest Export",
        .settingsEventTimelineTag: "Event Timeline",
        .settingsRestoreOnLaunchTag: "Restore on Launch",
        .settingsAIAnalysisWeights: "AI Analysis Weights",
        .settingsAudioCrowdNoise: "Audio (Crowd Noise)",
        .settingsMotionDetection: "Motion Detection",
        .settingsBodyPoseAnalysis: "Body Pose Analysis",
        .settingsSceneBrightness: "Scene Brightness",
        .settingsTotalWeight: "Total Weight",
        .settingsCurrentDetectionProfile: "Current Detection Profile",
        .settingsBalanced: "Balanced",
        .settingsAdjust: "Adjust",
        .settingsWeights: "Weights",
        .settingsKeepUncertain: "Keep Uncertain",
        .settingsOn: "On",
        .settingsOff: "Off",
        .settingsTargetReel: "Target Reel",
        .settingsClipReelDuration: "Clip & Reel Duration",
        .settingsMinimum: "Minimum",
        .settingsMaximum: "Maximum",
        .settingsTargetHighlight: "Target Highlight",
        .settingsShortestClipHelp: "Shortest clip the AI will keep",
        .settingsLongestClipHelp: "Longest clip the AI will keep",
        .settingsTargetHighlightHelp: "Caps the default auto-kept reel length after analysis. You can still keep more clips manually in Review.",
        .settingsAdvancedSettings: "Advanced Settings",
        .settingsAdvancedSubtitle: "For fine-tuning. Most users don't need to change these.",
        .settingsCustom: "Custom",
        .settingsConfidenceThreshold: "Confidence Threshold",
        .settingsLowerConfidenceHelp: "Lower = more clips found, but may include false positives.",
        .settingsDetectionBehavior: "Detection Behavior",
        .settingsClipPadding: "Clip Padding",
        .settingsClipPaddingHelp: "Adds extra lead-in and follow-through around detected moments.",
        .settingsKeepUncertainClips: "Keep Uncertain Clips",
        .settingsKeepUncertainHelp: "When unsure, keep clips for manual review.",
        .settingsPerformance: "Performance",
        .settingsFramesPerSecond: "Frames Per Second",
        .settingsPerformanceHelp: "Higher = more accurate but slower analysis.",
        .settingsAbout: "About",
        .settingsAboutDescription: "Smart basketball highlight detection that helps you find, review, export, and save your best clips directly on your iPhone.",
        .settingsSmartClipsTag: "Smart Clips",
        .settingsPrivateTag: "Private",
        .settingsFastExportTag: "Fast Export",
        .settingsShareReadyTag: "Share Ready",
        .settingsContactSuggestions: "Contact & Suggestions",
        .settingsContactSubtitle: "Send feedback directly from the app to the team.",
        .settingsFeedbackSuggestion: "Suggestion",
        .settingsFeedbackBug: "Bug Report",
        .settingsFeedbackQuestion: "Question",
        .settingsFeedbackType: "Type",
        .settingsEmailOptional: "Email (optional)",
        .settingsMessage: "Message",
        .settingsMessagePlaceholder: "Tell us what to improve, report a bug, or ask a question...",
        .settingsClear: "Clear",
        .settingsSending: "Sending...",
        .settingsSend: "Send",
        .settingsFeedbackPrivacyNote: "Submitted securely over HTTPS via Formspree. Avoid sending passwords or private account data.",
        .settingsCommonFAQ: "Common FAQ",
        .settingsFAQSubtitle: "Quick answers for setup, exports, and detection tuning.",
        .settingsFAQNoClipsQuestion: "Why did the app find few or no clips?",
        .settingsFAQNoClipsAnswer: "Lower the confidence threshold, increase the clip duration range, and check that the source video has clear motion and audible peaks. Low-light or static camera footage can reduce detection quality.",
        .settingsFAQWeightsQuestion: "When should I change AI weights?",
        .settingsFAQWeightsAnswer: "Leave weights balanced for most games. Use Advanced Settings only if your footage is unusual, like very loud gyms or silent clips with strong movement.",
        .settingsFAQExportFormatQuestion: "Should I export MP4 or MOV?",
        .settingsFAQExportFormatAnswer: "MP4 is the best default for sharing and cross-platform compatibility. MOV is a good Apple-native option if you plan to edit clips in Apple-focused workflows.",
        .settingsFAQQuickShareQuestion: "How does Review & Share work on iPhone?",
        .settingsFAQQuickShareAnswer: "After export completes, the app opens an in-app review of the latest reel first. You can replay it, save it to Photos, or open the iOS share sheet.",
        .settingsAccountDetailsSubtitle: "Your sign-in details",
        .settingsSubscription: "Subscription",
        .settingsProMember: "Pro Member",
        .settingsUnlimitedAccess: "You have unlimited access",
        .settingsUnlimitedAIExports: "Unlimited AI analyses & exports",
        .settingsSignInRequired: "Sign in required",
        .settingsFreeTier: "Free tier",
        .settingsPerMonth: "Per Month",
        .settingsSignInToUpgrade: "Sign In to Upgrade",
        .settingsUpgradeToPro: "Upgrade to Pro",
        .settingsSignOut: "Sign Out",
        .settingsGuest: "Guest",
        .settingsUnknown: "Unknown",
        .settingsResetTitle: "Reset Settings?",
        .settingsReset: "Reset",
        .settingsCancel: "Cancel",
        .settingsResetMessage: "This will restore all AI settings to their defaults.",
        .settingsResetToDefaults: "Reset to Defaults",
        .settingsMissingReleaseURL: "Missing release URL. Populate the production config before App Store submission.",
        .settingsFeedbackValidationMessage: "Please add a message (8-1200 chars) and check the email format if provided.",
        .settingsFeedbackConfigError: "Feedback form is not configured correctly.",
        .settingsFeedbackSendFailure: "Couldn't send feedback right now. Please try again.",
        .settingsFeedbackNetworkError: "Network error while sending feedback. Check connection and try again.",
        .settingsFeedbackSentThanks: "Thanks. Your feedback was sent.",
        .settingsDeveloperFootnote: "Developer-only launch diagnostics are hidden from production users."
    ]

    private static let chineseText: [AppTextKey: String] = [
        .tabPlayer: "播放器",
        .tabReview: "回看",
        .tabExport: "导出",
        .tabHistory: "历史",
        .tabSettings: "设置",
        .settingsTitle: "设置",
        .languageTitle: "语言",
        .languageSubtitle: "选择 Hoops Clips 的显示语言。",
        .languageCardTitle: "应用语言",
        .languageCardSubtitle: "选择导航、启动页和核心控件的语言。",
        .languageCurrent: "当前",
        .languageRestartNote: "大多数文字会立即更新。系统弹窗可能跟随 iPhone 语言。",
        .authTagline: "把篮球视频变成适合分享的高光集锦。\n登录后开始剪辑。",
        .signInError: "登录错误",
        .continueWithGoogle: "使用 Google 继续",
        .continueWithEmail: "使用邮箱继续",
        .continueWithPhone: "使用手机号继续",
        .continueAsGuest: "以访客身份继续",
        .or: "或",
        .legalPrefix: "登录即表示你同意我们的",
        .legalTerms: "服务条款",
        .legalAnd: "和",
        .legalPrivacy: "隐私政策",
        .legalFallback: "登录即表示你同意我们的服务条款和隐私政策。",
        .email: "邮箱",
        .password: "密码",
        .passwordPlaceholder: "至少 6 个字符",
        .signingIn: "正在登录...",
        .signIn: "登录",
        .phoneNumber: "手机号",
        .sendCode: "发送验证码",
        .verificationCode: "验证码",
        .verifying: "正在验证...",
        .verifyAndSignIn: "验证并登录",
        .resendCode: "重新发送验证码",
        .codeSent: "验证码已发送",
        .demoCodeNote: "演示模式 — 正式环境会通过短信/邮箱发送验证码",
        .backToSignIn: "返回登录选项",
        .region: "地区",
        .willSendTo: "将发送至",
        .playerTitle: "Hoops Clips",
        .importVideo: "导入视频",
        .photoLibrary: "照片图库",
        .files: "文件",
        .noHighlightsFound: "未找到高光",
        .noHighlightsMessage: "分析完成，但这个片段中没有足够确定的高光。",
        .noHighlightsAlternateMessage: "AI 没能在这个视频中检测到足够确定的高光。",
        .proRequiredTitle: "较长视频需要 Pro",
        .notNow: "暂不",
        .goPro: "升级 Pro",
        .proRequiredMessagePrefix: "免费版最多可分析",
        .proRequiredMessageMiddle: "此视频时长为",
        .turnGamesTitle: "把比赛变成 Hoops Clips",
        .turnGamesSubtitle: "找到最佳瞬间，剪掉空白时间，\n几分钟内生成可分享集锦。",
        .selectVideo: "选择视频",
        .smartHighlights: "智能高光",
        .fastReels: "快速集锦",
        .autoTrim: "自动剪辑",
        .sourceVideo: "源视频",
        .sourceVideoSubtitle: "已加载，可开始 AI 分析",
        .duration: "时长",
        .format: "格式",
        .aiAnalysis: "AI 分析",
        .aiAnalysisSubtitle: "找到最佳回合，去掉杂乱片段，快速生成集锦。",
        .analyzeWithAI: "使用 AI 分析",
        .analysisButtonSubtitle: "从这个视频中寻找高光片段",
        .analysisButtonUpgradePrefix: "升级后可分析超过此时长的视频：",
        .analysisComplete: "分析完成",
        .clipsFound: "找到片段",
        .kept: "保留",
        .estimated: "预计",
        .analysis: "分析",
        .projectSnapshot: "项目概览",
        .projectSnapshotSubtitle: "审核和导出前的快速信息",
        .detected: "已检测",
        .readyToFind: "准备寻找你的最佳片段。",
        .freeTierLimitPrefix: "免费版支持最长",
        .freeTierLimitSuffix: "升级后可分析更长比赛。",
        .freeAnalysisRemainingSingular: "次免费分析今天可用。",
        .freeAnalysisRemainingPlural: "次免费分析今天可用。",
        .dailyAnalysesUsed: "你今天的免费分析次数已用完。升级即可无限使用。",
        .uploading: "正在上传...",
        .queued: "排队中...",
        .analyzing: "正在分析...",
        .finalizing: "正在完成...",
        .refining: "正在优化...",
        .controlRoom: "应用设置",
        .controlRoomSubtitle: "在清晰分区中管理语言、会员、默认设置和支持。",
        .account: "账号",
        .plan: "方案",
        .freeLeft: "免费剩余",
        .targetReel: "目标集锦",
        .export: "导出",
        .workflowDefaults: "工作流默认值",
        .workflowDefaultsSubtitle: "片段时长、置信度、AI 权重和集锦规则。",
        .membershipAccount: "会员与账号",
        .membershipAccountSubtitle: "身份、订阅状态、升级控制和退出登录。",
        .accountQuickActions: "账号快捷操作",
        .supportCenter: "支持中心",
        .supportCenterSubtitle: "发送反馈、报告问题并查看快速答案。",
        .aboutPrivacy: "关于与隐私",
        .aboutPrivacySubtitle: "核心信息、本机保存内容和重置控制。",
        .resetDefaultsDescription: "将所有 AI 调整恢复为 Hoops Clips 默认值。",
        .settingsThreshold: "阈值",
        .settingsTarget: "目标",
        .settingsSampling: "采样",
        .settingsDraftType: "草稿类型",
        .settingsDraftChars: "草稿字数",
        .settingsOnDevice: "本机处理",
        .settingsHistory: "历史",
        .settingsEngine: "引擎",
        .settingsVisionAudio: "视觉 + 音频",
        .settingsUnlimited: "无限",
        .settingsMonthly: "月付",
        .settingsAccountPlan: "账号与方案",
        .settingsSignedInWith: "登录方式",
        .settingsWorkflowDetailSubtitle: "根据你的素材调整片段选择和分析行为。",
        .settingsMembershipDetailSubtitle: "查看登录方式并管理访问权限。",
        .settingsSupportDetailSubtitle: "集中处理反馈、问题报告和设置帮助。",
        .settingsAboutDetailSubtitle: "应用信息、存储方式和本机历史说明。",
        .settingsLegal: "法律信息",
        .settingsLegalSubtitle: "打开正式 App 和 App Store 页面需要可访问的政策链接。",
        .settingsPrivacyPolicySubtitle: "查看账号、订阅和本机处理方式的说明。",
        .settingsTermsSubtitle: "查看产品条款、可接受使用和订阅说明。",
        .settingsOnDeviceLibrary: "本机资料库",
        .settingsOnDeviceLibraryDescription: "导入的视频、每个项目的最新导出和项目时间线都会保存在此设备的应用本地存储中。此功能不会把这些内容同步到服务器。",
        .settingsSourceVideoTag: "源视频",
        .settingsLatestExportTag: "最新导出",
        .settingsEventTimelineTag: "事件时间线",
        .settingsRestoreOnLaunchTag: "启动时恢复",
        .settingsAIAnalysisWeights: "AI 分析权重",
        .settingsAudioCrowdNoise: "音频（观众声）",
        .settingsMotionDetection: "动作检测",
        .settingsBodyPoseAnalysis: "人体姿态分析",
        .settingsSceneBrightness: "画面亮度",
        .settingsTotalWeight: "总权重",
        .settingsCurrentDetectionProfile: "当前检测配置",
        .settingsBalanced: "均衡",
        .settingsAdjust: "需调整",
        .settingsWeights: "权重",
        .settingsKeepUncertain: "保留不确定",
        .settingsOn: "开启",
        .settingsOff: "关闭",
        .settingsTargetReel: "目标集锦",
        .settingsClipReelDuration: "片段与集锦时长",
        .settingsMinimum: "最短",
        .settingsMaximum: "最长",
        .settingsTargetHighlight: "目标高光",
        .settingsShortestClipHelp: "AI 会保留的最短片段",
        .settingsLongestClipHelp: "AI 会保留的最长片段",
        .settingsTargetHighlightHelp: "限制分析后默认自动保留的集锦总时长。你仍可在回看页手动保留更多片段。",
        .settingsAdvancedSettings: "高级设置",
        .settingsAdvancedSubtitle: "用于精细调整。大多数用户不需要修改。",
        .settingsCustom: "自定义",
        .settingsConfidenceThreshold: "置信度阈值",
        .settingsLowerConfidenceHelp: "越低会找到更多片段，但可能包含误检。",
        .settingsDetectionBehavior: "检测行为",
        .settingsClipPadding: "片段前后延伸",
        .settingsClipPaddingHelp: "在检测到的瞬间前后添加额外过渡时间。",
        .settingsKeepUncertainClips: "保留不确定片段",
        .settingsKeepUncertainHelp: "AI 不确定时，保留给你手动回看。",
        .settingsPerformance: "性能",
        .settingsFramesPerSecond: "每秒帧数",
        .settingsPerformanceHelp: "越高越准确，但分析会更慢。",
        .settingsAbout: "关于",
        .settingsAboutDescription: "智能篮球高光检测，帮助你直接在 iPhone 上查找、回看、导出并保存最佳片段。",
        .settingsSmartClipsTag: "智能片段",
        .settingsPrivateTag: "隐私友好",
        .settingsFastExportTag: "快速导出",
        .settingsShareReadyTag: "适合分享",
        .settingsContactSuggestions: "联系与建议",
        .settingsContactSubtitle: "直接从应用向团队发送反馈。",
        .settingsFeedbackSuggestion: "建议",
        .settingsFeedbackBug: "问题报告",
        .settingsFeedbackQuestion: "问题",
        .settingsFeedbackType: "类型",
        .settingsEmailOptional: "邮箱（可选）",
        .settingsMessage: "消息",
        .settingsMessagePlaceholder: "告诉我们哪里可以改进、报告问题或提出疑问...",
        .settingsClear: "清空",
        .settingsSending: "正在发送...",
        .settingsSend: "发送",
        .settingsFeedbackPrivacyNote: "反馈会通过 Formspree 以 HTTPS 安全提交。请不要发送密码或私人账号信息。",
        .settingsCommonFAQ: "常见问题",
        .settingsFAQSubtitle: "关于设置、导出和检测调整的快速回答。",
        .settingsFAQNoClipsQuestion: "为什么应用只找到很少或没有片段？",
        .settingsFAQNoClipsAnswer: "可以降低置信度阈值、增加片段时长范围，并确认源视频有清晰动作和可听到的声音峰值。低光或固定机位素材可能降低检测质量。",
        .settingsFAQWeightsQuestion: "什么时候需要调整 AI 权重？",
        .settingsFAQWeightsAnswer: "大多数比赛保持均衡即可。只有在素材很特殊时才使用高级设置，例如场馆很吵，或静音但动作很明显的片段。",
        .settingsFAQExportFormatQuestion: "应该导出 MP4 还是 MOV？",
        .settingsFAQExportFormatAnswer: "MP4 最适合分享和跨平台使用。若你主要在 Apple 生态内继续编辑或管理片段，MOV 也很合适。",
        .settingsFAQQuickShareQuestion: "iPhone 上的回看与分享怎么用？",
        .settingsFAQQuickShareAnswer: "导出完成后，应用会先打开最新集锦的应用内回看。你可以重播、保存到照片，或打开 iOS 分享菜单。",
        .settingsAccountDetailsSubtitle: "你的登录信息",
        .settingsSubscription: "订阅",
        .settingsProMember: "Pro 会员",
        .settingsUnlimitedAccess: "你拥有无限访问权限",
        .settingsUnlimitedAIExports: "无限 AI 分析和导出",
        .settingsSignInRequired: "需要登录",
        .settingsFreeTier: "免费版",
        .settingsPerMonth: "每月",
        .settingsSignInToUpgrade: "登录后升级",
        .settingsUpgradeToPro: "升级到 Pro",
        .settingsSignOut: "退出登录",
        .settingsGuest: "访客",
        .settingsUnknown: "未知",
        .settingsResetTitle: "重置设置？",
        .settingsReset: "重置",
        .settingsCancel: "取消",
        .settingsResetMessage: "这会将所有 AI 设置恢复为默认值。",
        .settingsResetToDefaults: "恢复默认值",
        .settingsMissingReleaseURL: "缺少发布链接。提交 App Store 前请填写生产配置。",
        .settingsFeedbackValidationMessage: "请填写 8-1200 个字符的消息，并检查邮箱格式。",
        .settingsFeedbackConfigError: "反馈表单配置不正确。",
        .settingsFeedbackSendFailure: "现在无法发送反馈，请稍后再试。",
        .settingsFeedbackNetworkError: "发送反馈时出现网络错误。请检查连接后重试。",
        .settingsFeedbackSentThanks: "谢谢，你的反馈已发送。",
        .settingsDeveloperFootnote: "开发者发布诊断信息已对正式用户隐藏。"
    ]

    private static let spanishText: [AppTextKey: String] = [
        .tabPlayer: "Video",
        .tabReview: "Revisar",
        .tabExport: "Exportar",
        .tabHistory: "Historial",
        .tabSettings: "Ajustes",
        .settingsTitle: "Ajustes",
        .languageTitle: "Idioma",
        .languageSubtitle: "Elige el idioma de Hoops Clips.",
        .languageCardTitle: "Idioma de la app",
        .languageCardSubtitle: "Elige el idioma para navegación, pantallas iniciales y controles clave.",
        .languageCurrent: "Actual",
        .languageRestartNote: "La mayoría del texto cambia al instante. Los diálogos del sistema pueden seguir el idioma del iPhone.",
        .authTagline: "Convierte videos de básquet en reels de highlights listos para compartir.\nInicia sesión para empezar.",
        .signInError: "Error de inicio de sesión",
        .continueWithGoogle: "Continuar con Google",
        .continueWithEmail: "Continuar con email",
        .continueWithPhone: "Continuar con teléfono",
        .continueAsGuest: "Continuar como invitado",
        .or: "o",
        .legalPrefix: "Al iniciar sesión, aceptas nuestros",
        .legalTerms: "Términos de servicio",
        .legalAnd: "y",
        .legalPrivacy: "Política de privacidad",
        .legalFallback: "Al iniciar sesión, aceptas nuestros Términos de servicio y Política de privacidad.",
        .email: "Email",
        .password: "Contraseña",
        .passwordPlaceholder: "Mínimo 6 caracteres",
        .signingIn: "Iniciando sesión...",
        .signIn: "Iniciar sesión",
        .phoneNumber: "Número de teléfono",
        .sendCode: "Enviar código",
        .verificationCode: "Código de verificación",
        .verifying: "Verificando...",
        .verifyAndSignIn: "Verificar e iniciar sesión",
        .resendCode: "Reenviar código",
        .codeSent: "Código enviado",
        .demoCodeNote: "Modo demo — en producción, los códigos se envían por SMS/email",
        .backToSignIn: "Volver a opciones de inicio",
        .region: "Región",
        .willSendTo: "Se enviará a",
        .playerTitle: "Hoops Clips",
        .importVideo: "Importar video",
        .photoLibrary: "Fotos",
        .files: "Archivos",
        .noHighlightsFound: "No se encontraron highlights",
        .noHighlightsMessage: "El análisis terminó sin encontrar highlights suficientemente claros en este clip.",
        .noHighlightsAlternateMessage: "La IA no detectó suficientes highlights claros en este video.",
        .proRequiredTitle: "Pro requerido para videos largos",
        .notNow: "Ahora no",
        .goPro: "Ir a Pro",
        .proRequiredMessagePrefix: "El plan gratis analiza videos de hasta",
        .proRequiredMessageMiddle: "Este video dura",
        .turnGamesTitle: "Convierte partidos en Hoops Clips",
        .turnGamesSubtitle: "Encuentra tus mejores jugadas, corta los tiempos muertos\ny crea un reel listo para compartir.",
        .selectVideo: "Seleccionar video",
        .smartHighlights: "Highlights inteligentes",
        .fastReels: "Reels rápidos",
        .autoTrim: "Auto recorte",
        .sourceVideo: "Video fuente",
        .sourceVideoSubtitle: "Cargado y listo para análisis IA",
        .duration: "Duración",
        .format: "Formato",
        .aiAnalysis: "Análisis IA",
        .aiAnalysisSubtitle: "Encuentra las mejores jugadas, limpia el ruido y arma un reel rápido.",
        .analyzeWithAI: "Analizar con IA",
        .analysisButtonSubtitle: "Encontrar clips destacados en este video",
        .analysisButtonUpgradePrefix: "Actualiza para analizar videos de más de",
        .analysisComplete: "Análisis completo",
        .clipsFound: "Clips encontrados",
        .kept: "Guardados",
        .estimated: "Estimado",
        .analysis: "análisis",
        .projectSnapshot: "Resumen del proyecto",
        .projectSnapshotSubtitle: "Contexto rápido antes de revisar y exportar",
        .detected: "Detectados",
        .readyToFind: "Listo para encontrar tus mejores clips.",
        .freeTierLimitPrefix: "El plan gratis admite hasta",
        .freeTierLimitSuffix: "Actualiza para analizar partidos más largos.",
        .freeAnalysisRemainingSingular: "análisis gratis restante hoy.",
        .freeAnalysisRemainingPlural: "análisis gratis restantes hoy.",
        .dailyAnalysesUsed: "Ya usaste los análisis gratis de hoy. Actualiza para acceso ilimitado.",
        .uploading: "Subiendo...",
        .queued: "En cola...",
        .analyzing: "Analizando...",
        .finalizing: "Finalizando...",
        .refining: "Refinando...",
        .controlRoom: "Configuración de la app",
        .controlRoomSubtitle: "Gestiona idioma, membresía, valores predeterminados y soporte en secciones claras.",
        .account: "Cuenta",
        .plan: "Plan",
        .freeLeft: "Gratis",
        .targetReel: "Reel objetivo",
        .export: "Exportar",
        .workflowDefaults: "Flujo predeterminado",
        .workflowDefaultsSubtitle: "Duración, confianza, pesos IA y reglas del reel.",
        .membershipAccount: "Membresía y cuenta",
        .membershipAccountSubtitle: "Identidad, suscripción, upgrades y cerrar sesión.",
        .accountQuickActions: "Acciones rápidas",
        .supportCenter: "Centro de soporte",
        .supportCenterSubtitle: "Envía feedback, reporta bugs y mira respuestas rápidas.",
        .aboutPrivacy: "Acerca de y privacidad",
        .aboutPrivacySubtitle: "Detalles de la app, guardado local y controles de reset.",
        .resetDefaultsDescription: "Restaurar todos los ajustes de IA a los valores de Hoops Clips.",
        .settingsThreshold: "Umbral",
        .settingsTarget: "Objetivo",
        .settingsSampling: "Muestreo",
        .settingsDraftType: "Tipo de borrador",
        .settingsDraftChars: "Caracteres",
        .settingsOnDevice: "En el dispositivo",
        .settingsHistory: "Historial",
        .settingsEngine: "Motor",
        .settingsVisionAudio: "Visión + audio",
        .settingsUnlimited: "Ilimitado",
        .settingsMonthly: "Mensual",
        .settingsAccountPlan: "Cuenta y plan",
        .settingsSignedInWith: "Sesión iniciada con",
        .settingsWorkflowDetailSubtitle: "Ajusta la selección de clips y el análisis según tu video.",
        .settingsMembershipDetailSubtitle: "Revisa cómo iniciaste sesión y gestiona el acceso.",
        .settingsSupportDetailSubtitle: "Feedback, reportes de errores y ayuda de configuración en un solo lugar.",
        .settingsAboutDetailSubtitle: "Detalles de la app, almacenamiento y notas del historial local.",
        .settingsLegal: "Legal",
        .settingsLegalSubtitle: "Abre las políticas que deben estar disponibles en la app publicada y en App Store.",
        .settingsPrivacyPolicySubtitle: "Revisa cómo se explican la cuenta, la facturación y el procesamiento local.",
        .settingsTermsSubtitle: "Revisa términos del producto, uso aceptable y lenguaje de suscripción.",
        .settingsOnDeviceLibrary: "Biblioteca local",
        .settingsOnDeviceLibraryDescription: "Los videos importados, la exportación más reciente de cada proyecto y la línea de tiempo se guardan localmente en esta app en este dispositivo. Esta función no sincroniza ese contenido con un servidor.",
        .settingsSourceVideoTag: "Video fuente",
        .settingsLatestExportTag: "Última exportación",
        .settingsEventTimelineTag: "Línea de tiempo",
        .settingsRestoreOnLaunchTag: "Restaurar al abrir",
        .settingsAIAnalysisWeights: "Pesos del análisis IA",
        .settingsAudioCrowdNoise: "Audio (ruido del público)",
        .settingsMotionDetection: "Detección de movimiento",
        .settingsBodyPoseAnalysis: "Análisis de pose corporal",
        .settingsSceneBrightness: "Brillo de escena",
        .settingsTotalWeight: "Peso total",
        .settingsCurrentDetectionProfile: "Perfil de detección actual",
        .settingsBalanced: "Equilibrado",
        .settingsAdjust: "Ajustar",
        .settingsWeights: "Pesos",
        .settingsKeepUncertain: "Mantener dudosos",
        .settingsOn: "Activado",
        .settingsOff: "Desactivado",
        .settingsTargetReel: "Reel objetivo",
        .settingsClipReelDuration: "Duración de clips y reel",
        .settingsMinimum: "Mínimo",
        .settingsMaximum: "Máximo",
        .settingsTargetHighlight: "Highlight objetivo",
        .settingsShortestClipHelp: "Clip más corto que la IA conservará",
        .settingsLongestClipHelp: "Clip más largo que la IA conservará",
        .settingsTargetHighlightHelp: "Limita la duración total del reel auto-conservado después del análisis. Aún puedes guardar más clips manualmente en Revisar.",
        .settingsAdvancedSettings: "Ajustes avanzados",
        .settingsAdvancedSubtitle: "Para ajuste fino. La mayoría de usuarios no necesita cambiarlos.",
        .settingsCustom: "Personalizado",
        .settingsConfidenceThreshold: "Umbral de confianza",
        .settingsLowerConfidenceHelp: "Más bajo = más clips encontrados, pero puede incluir falsos positivos.",
        .settingsDetectionBehavior: "Comportamiento de detección",
        .settingsClipPadding: "Margen del clip",
        .settingsClipPaddingHelp: "Añade entrada y seguimiento extra alrededor de los momentos detectados.",
        .settingsKeepUncertainClips: "Mantener clips dudosos",
        .settingsKeepUncertainHelp: "Si la IA duda, conserva el clip para revisión manual.",
        .settingsPerformance: "Rendimiento",
        .settingsFramesPerSecond: "Fotogramas por segundo",
        .settingsPerformanceHelp: "Más alto = más precisión, pero análisis más lento.",
        .settingsAbout: "Acerca de",
        .settingsAboutDescription: "Detección inteligente de highlights de básquet para encontrar, revisar, exportar y guardar tus mejores clips directamente en tu iPhone.",
        .settingsSmartClipsTag: "Clips inteligentes",
        .settingsPrivateTag: "Privado",
        .settingsFastExportTag: "Exportación rápida",
        .settingsShareReadyTag: "Listo para compartir",
        .settingsContactSuggestions: "Contacto y sugerencias",
        .settingsContactSubtitle: "Envía feedback directamente al equipo desde la app.",
        .settingsFeedbackSuggestion: "Sugerencia",
        .settingsFeedbackBug: "Reporte de error",
        .settingsFeedbackQuestion: "Pregunta",
        .settingsFeedbackType: "Tipo",
        .settingsEmailOptional: "Email (opcional)",
        .settingsMessage: "Mensaje",
        .settingsMessagePlaceholder: "Cuéntanos qué mejorar, reporta un error o haz una pregunta...",
        .settingsClear: "Borrar",
        .settingsSending: "Enviando...",
        .settingsSend: "Enviar",
        .settingsFeedbackPrivacyNote: "Se envía de forma segura por HTTPS vía Formspree. Evita enviar contraseñas o datos privados de cuenta.",
        .settingsCommonFAQ: "Preguntas frecuentes",
        .settingsFAQSubtitle: "Respuestas rápidas sobre configuración, exportación y ajuste de detección.",
        .settingsFAQNoClipsQuestion: "¿Por qué la app encontró pocos clips o ninguno?",
        .settingsFAQNoClipsAnswer: "Baja el umbral de confianza, aumenta el rango de duración de clips y comprueba que el video tenga movimiento claro y picos de audio. La poca luz o una cámara fija pueden reducir la calidad.",
        .settingsFAQWeightsQuestion: "¿Cuándo debería cambiar los pesos de IA?",
        .settingsFAQWeightsAnswer: "Déjalos equilibrados para la mayoría de partidos. Usa Ajustes avanzados solo si el video es inusual, como gimnasios muy ruidosos o clips silenciosos con mucho movimiento.",
        .settingsFAQExportFormatQuestion: "¿Debería exportar MP4 o MOV?",
        .settingsFAQExportFormatAnswer: "MP4 es el mejor valor predeterminado para compartir y compatibilidad. MOV es buena opción si planeas editar en flujos de Apple.",
        .settingsFAQQuickShareQuestion: "¿Cómo funciona Revisar y compartir en iPhone?",
        .settingsFAQQuickShareAnswer: "Cuando termina la exportación, la app abre primero una revisión interna del reel más reciente. Puedes reproducirlo, guardarlo en Fotos o abrir la hoja de compartir de iOS.",
        .settingsAccountDetailsSubtitle: "Tus datos de inicio de sesión",
        .settingsSubscription: "Suscripción",
        .settingsProMember: "Miembro Pro",
        .settingsUnlimitedAccess: "Tienes acceso ilimitado",
        .settingsUnlimitedAIExports: "Análisis IA y exportaciones ilimitadas",
        .settingsSignInRequired: "Inicio de sesión requerido",
        .settingsFreeTier: "Plan gratis",
        .settingsPerMonth: "Por mes",
        .settingsSignInToUpgrade: "Inicia sesión para mejorar",
        .settingsUpgradeToPro: "Mejorar a Pro",
        .settingsSignOut: "Cerrar sesión",
        .settingsGuest: "Invitado",
        .settingsUnknown: "Desconocido",
        .settingsResetTitle: "¿Restablecer ajustes?",
        .settingsReset: "Restablecer",
        .settingsCancel: "Cancelar",
        .settingsResetMessage: "Esto restaurará todos los ajustes de IA a sus valores predeterminados.",
        .settingsResetToDefaults: "Restablecer valores",
        .settingsMissingReleaseURL: "Falta la URL de lanzamiento. Completa la configuración de producción antes de enviar a App Store.",
        .settingsFeedbackValidationMessage: "Añade un mensaje de 8 a 1200 caracteres y revisa el formato del email si lo incluyes.",
        .settingsFeedbackConfigError: "El formulario de feedback no está configurado correctamente.",
        .settingsFeedbackSendFailure: "No se pudo enviar el feedback ahora. Inténtalo de nuevo.",
        .settingsFeedbackNetworkError: "Error de red al enviar feedback. Revisa la conexión e inténtalo de nuevo.",
        .settingsFeedbackSentThanks: "Gracias. Tu feedback fue enviado.",
        .settingsDeveloperFootnote: "Los diagnósticos de lanzamiento para desarrolladores están ocultos para usuarios de producción."
    ]

    private static let frenchText: [AppTextKey: String] = [
        .tabPlayer: "Lecteur",
        .tabReview: "Revoir",
        .tabExport: "Exporter",
        .tabHistory: "Historique",
        .tabSettings: "Réglages",
        .settingsTitle: "Réglages",
        .languageTitle: "Langue",
        .languageSubtitle: "Choisis la langue de Hoops Clips.",
        .languageCardTitle: "Langue de l'app",
        .languageCardSubtitle: "Choisis la langue de la navigation, des écrans de départ et des contrôles clés.",
        .languageCurrent: "Actuelle",
        .languageRestartNote: "La plupart du texte change tout de suite. Les dialogues système suivent parfois la langue de l'iPhone.",
        .authTagline: "Transforme tes vidéos de basket en reels de highlights prêts à partager.\nConnecte-toi pour commencer.",
        .signInError: "Erreur de connexion",
        .continueWithGoogle: "Continuer avec Google",
        .continueWithEmail: "Continuer avec l'email",
        .continueWithPhone: "Continuer avec le téléphone",
        .continueAsGuest: "Continuer comme invité",
        .or: "ou",
        .legalPrefix: "En te connectant, tu acceptes nos",
        .legalTerms: "Conditions d'utilisation",
        .legalAnd: "et",
        .legalPrivacy: "Politique de confidentialité",
        .legalFallback: "En te connectant, tu acceptes nos Conditions d'utilisation et notre Politique de confidentialité.",
        .email: "Email",
        .password: "Mot de passe",
        .passwordPlaceholder: "6 caractères minimum",
        .signingIn: "Connexion...",
        .signIn: "Se connecter",
        .phoneNumber: "Numéro de téléphone",
        .sendCode: "Envoyer le code",
        .verificationCode: "Code de vérification",
        .verifying: "Vérification...",
        .verifyAndSignIn: "Vérifier et se connecter",
        .resendCode: "Renvoyer le code",
        .codeSent: "Code envoyé",
        .demoCodeNote: "Mode démo — en production, les codes sont envoyés par SMS/email",
        .backToSignIn: "Retour aux options",
        .region: "Région",
        .willSendTo: "Envoi à",
        .playerTitle: "Hoops Clips",
        .importVideo: "Importer une vidéo",
        .photoLibrary: "Photos",
        .files: "Fichiers",
        .noHighlightsFound: "Aucun highlight trouvé",
        .noHighlightsMessage: "L'analyse n'a pas trouvé assez de highlights fiables dans ce clip.",
        .noHighlightsAlternateMessage: "L'IA n'a pas détecté assez de highlights fiables dans cette vidéo.",
        .proRequiredTitle: "Pro requis pour les longues vidéos",
        .notNow: "Pas maintenant",
        .goPro: "Passer Pro",
        .proRequiredMessagePrefix: "L'offre gratuite analyse les vidéos jusqu'à",
        .proRequiredMessageMiddle: "Cette vidéo dure",
        .turnGamesTitle: "Transforme les matchs en Hoops Clips",
        .turnGamesSubtitle: "Trouve tes meilleures actions, coupe les temps morts\net crée un reel prêt à partager.",
        .selectVideo: "Choisir une vidéo",
        .smartHighlights: "Highlights intelligents",
        .fastReels: "Reels rapides",
        .autoTrim: "Auto découpe",
        .sourceVideo: "Vidéo source",
        .sourceVideoSubtitle: "Chargée et prête pour l'analyse IA",
        .duration: "Durée",
        .format: "Format",
        .aiAnalysis: "Analyse IA",
        .aiAnalysisSubtitle: "Trouve les meilleures actions, enlève le bruit et crée vite un reel.",
        .analyzeWithAI: "Analyser avec l'IA",
        .analysisButtonSubtitle: "Trouver les clips forts dans cette vidéo",
        .analysisButtonUpgradePrefix: "Passe Pro pour analyser des vidéos de plus de",
        .analysisComplete: "Analyse terminée",
        .clipsFound: "Clips trouvés",
        .kept: "Gardés",
        .estimated: "Estimé",
        .analysis: "analyse",
        .projectSnapshot: "Aperçu du projet",
        .projectSnapshotSubtitle: "Contexte rapide avant revue et export",
        .detected: "Détectés",
        .readyToFind: "Prêt à trouver tes meilleurs clips.",
        .freeTierLimitPrefix: "L'offre gratuite prend en charge jusqu'à",
        .freeTierLimitSuffix: "Passe Pro pour analyser des matchs plus longs.",
        .freeAnalysisRemainingSingular: "analyse gratuite restante aujourd'hui.",
        .freeAnalysisRemainingPlural: "analyses gratuites restantes aujourd'hui.",
        .dailyAnalysesUsed: "Tu as utilisé les analyses gratuites du jour. Passe Pro pour un accès illimité.",
        .uploading: "Envoi...",
        .queued: "En attente...",
        .analyzing: "Analyse...",
        .finalizing: "Finalisation...",
        .refining: "Optimisation...",
        .controlRoom: "Configuration de l'app",
        .controlRoomSubtitle: "Gère la langue, l'abonnement, les réglages par défaut et l'aide dans des sections claires.",
        .account: "Compte",
        .plan: "Formule",
        .freeLeft: "Restant",
        .targetReel: "Reel cible",
        .export: "Export",
        .workflowDefaults: "Réglages du workflow",
        .workflowDefaultsSubtitle: "Durée, confiance, pondération IA et règles du reel.",
        .membershipAccount: "Abonnement et compte",
        .membershipAccountSubtitle: "Identité, abonnement, upgrade et déconnexion.",
        .accountQuickActions: "Actions rapides",
        .supportCenter: "Centre d'aide",
        .supportCenterSubtitle: "Envoie un avis, signale un bug et consulte les réponses rapides.",
        .aboutPrivacy: "À propos et confidentialité",
        .aboutPrivacySubtitle: "Détails de l'app, stockage local et options de reset.",
        .resetDefaultsDescription: "Restaurer tous les réglages IA aux valeurs Hoops Clips.",
        .settingsThreshold: "Seuil",
        .settingsTarget: "Objectif",
        .settingsSampling: "Échantillonnage",
        .settingsDraftType: "Type de brouillon",
        .settingsDraftChars: "Caractères",
        .settingsOnDevice: "Sur l'appareil",
        .settingsHistory: "Historique",
        .settingsEngine: "Moteur",
        .settingsVisionAudio: "Vision + audio",
        .settingsUnlimited: "Illimité",
        .settingsMonthly: "Mensuel",
        .settingsAccountPlan: "Compte et formule",
        .settingsSignedInWith: "Connecté avec",
        .settingsWorkflowDetailSubtitle: "Ajuste la sélection des clips et l'analyse selon ta vidéo.",
        .settingsMembershipDetailSubtitle: "Vois comment tu es connecté et gère l'accès.",
        .settingsSupportDetailSubtitle: "Retours, signalements de bugs et aide de configuration au même endroit.",
        .settingsAboutDetailSubtitle: "Détails de l'app, stockage et notes d'historique local.",
        .settingsLegal: "Mentions légales",
        .settingsLegalSubtitle: "Ouvre les politiques qui doivent rester accessibles dans l'app publiée et sur l'App Store.",
        .settingsPrivacyPolicySubtitle: "Consulte la façon dont le compte, la facturation et le traitement local sont expliqués.",
        .settingsTermsSubtitle: "Consulte les conditions du produit, l'utilisation acceptable et les informations d'abonnement.",
        .settingsOnDeviceLibrary: "Bibliothèque locale",
        .settingsOnDeviceLibraryDescription: "Les vidéos importées, le dernier export de chaque projet et la chronologie restent dans le stockage local de l'app sur cet appareil. Cette fonction ne synchronise rien avec un serveur.",
        .settingsSourceVideoTag: "Vidéo source",
        .settingsLatestExportTag: "Dernier export",
        .settingsEventTimelineTag: "Chronologie",
        .settingsRestoreOnLaunchTag: "Restaurer au lancement",
        .settingsAIAnalysisWeights: "Pondération de l'analyse IA",
        .settingsAudioCrowdNoise: "Audio (bruit du public)",
        .settingsMotionDetection: "Détection du mouvement",
        .settingsBodyPoseAnalysis: "Analyse de la posture",
        .settingsSceneBrightness: "Luminosité de la scène",
        .settingsTotalWeight: "Poids total",
        .settingsCurrentDetectionProfile: "Profil de détection actuel",
        .settingsBalanced: "Équilibré",
        .settingsAdjust: "Ajuster",
        .settingsWeights: "Poids",
        .settingsKeepUncertain: "Garder incertain",
        .settingsOn: "Activé",
        .settingsOff: "Désactivé",
        .settingsTargetReel: "Reel cible",
        .settingsClipReelDuration: "Durée des clips et du reel",
        .settingsMinimum: "Minimum",
        .settingsMaximum: "Maximum",
        .settingsTargetHighlight: "Highlight cible",
        .settingsShortestClipHelp: "Clip le plus court que l'IA gardera",
        .settingsLongestClipHelp: "Clip le plus long que l'IA gardera",
        .settingsTargetHighlightHelp: "Limite la durée totale du reel gardé automatiquement après analyse. Tu peux toujours garder plus de clips manuellement dans Revoir.",
        .settingsAdvancedSettings: "Réglages avancés",
        .settingsAdvancedSubtitle: "Pour un réglage fin. La plupart des utilisateurs n'ont pas besoin de les modifier.",
        .settingsCustom: "Personnalisé",
        .settingsConfidenceThreshold: "Seuil de confiance",
        .settingsLowerConfidenceHelp: "Plus bas = plus de clips trouvés, mais avec plus de faux positifs possibles.",
        .settingsDetectionBehavior: "Comportement de détection",
        .settingsClipPadding: "Marge du clip",
        .settingsClipPaddingHelp: "Ajoute une entrée et une sortie autour des moments détectés.",
        .settingsKeepUncertainClips: "Garder les clips incertains",
        .settingsKeepUncertainHelp: "Si l'IA hésite, garde le clip pour une revue manuelle.",
        .settingsPerformance: "Performance",
        .settingsFramesPerSecond: "Images par seconde",
        .settingsPerformanceHelp: "Plus haut = plus précis, mais l'analyse est plus lente.",
        .settingsAbout: "À propos",
        .settingsAboutDescription: "Détection intelligente de highlights de basket pour trouver, revoir, exporter et enregistrer tes meilleurs clips directement sur ton iPhone.",
        .settingsSmartClipsTag: "Clips intelligents",
        .settingsPrivateTag: "Privé",
        .settingsFastExportTag: "Export rapide",
        .settingsShareReadyTag: "Prêt à partager",
        .settingsContactSuggestions: "Contact et suggestions",
        .settingsContactSubtitle: "Envoie un retour directement à l'équipe depuis l'app.",
        .settingsFeedbackSuggestion: "Suggestion",
        .settingsFeedbackBug: "Signalement de bug",
        .settingsFeedbackQuestion: "Question",
        .settingsFeedbackType: "Type",
        .settingsEmailOptional: "Email (facultatif)",
        .settingsMessage: "Message",
        .settingsMessagePlaceholder: "Dis-nous quoi améliorer, signale un bug ou pose une question...",
        .settingsClear: "Effacer",
        .settingsSending: "Envoi...",
        .settingsSend: "Envoyer",
        .settingsFeedbackPrivacyNote: "Envoyé de façon sécurisée via HTTPS avec Formspree. Évite d'envoyer des mots de passe ou des données de compte privées.",
        .settingsCommonFAQ: "FAQ",
        .settingsFAQSubtitle: "Réponses rapides sur la configuration, les exports et les réglages de détection.",
        .settingsFAQNoClipsQuestion: "Pourquoi l'app a trouvé peu ou aucun clip ?",
        .settingsFAQNoClipsAnswer: "Baisse le seuil de confiance, augmente la plage de durée des clips et vérifie que la vidéo a un mouvement clair et des pics audio audibles. Une faible lumière ou une caméra fixe peut réduire la qualité.",
        .settingsFAQWeightsQuestion: "Quand modifier les poids de l'IA ?",
        .settingsFAQWeightsAnswer: "Garde-les équilibrés pour la plupart des matchs. Utilise les réglages avancés seulement si la vidéo est inhabituelle, par exemple un gymnase très bruyant ou des clips muets avec beaucoup de mouvement.",
        .settingsFAQExportFormatQuestion: "Exporter en MP4 ou en MOV ?",
        .settingsFAQExportFormatAnswer: "MP4 est le meilleur choix par défaut pour partager et rester compatible. MOV convient bien si tu comptes éditer dans des workflows Apple.",
        .settingsFAQQuickShareQuestion: "Comment fonctionne Revoir et partager sur iPhone ?",
        .settingsFAQQuickShareAnswer: "Quand l'export est terminé, l'app ouvre d'abord une revue interne du dernier reel. Tu peux le relire, l'enregistrer dans Photos ou ouvrir la feuille de partage iOS.",
        .settingsAccountDetailsSubtitle: "Tes informations de connexion",
        .settingsSubscription: "Abonnement",
        .settingsProMember: "Membre Pro",
        .settingsUnlimitedAccess: "Tu as un accès illimité",
        .settingsUnlimitedAIExports: "Analyses IA et exports illimités",
        .settingsSignInRequired: "Connexion requise",
        .settingsFreeTier: "Offre gratuite",
        .settingsPerMonth: "Par mois",
        .settingsSignInToUpgrade: "Connecte-toi pour passer Pro",
        .settingsUpgradeToPro: "Passer Pro",
        .settingsSignOut: "Se déconnecter",
        .settingsGuest: "Invité",
        .settingsUnknown: "Inconnu",
        .settingsResetTitle: "Réinitialiser les réglages ?",
        .settingsReset: "Réinitialiser",
        .settingsCancel: "Annuler",
        .settingsResetMessage: "Cela restaurera tous les réglages IA à leurs valeurs par défaut.",
        .settingsResetToDefaults: "Restaurer les valeurs",
        .settingsMissingReleaseURL: "URL de publication manquante. Renseigne la configuration de production avant l'envoi à l'App Store.",
        .settingsFeedbackValidationMessage: "Ajoute un message de 8 à 1200 caractères et vérifie le format de l'email si tu l'indiques.",
        .settingsFeedbackConfigError: "Le formulaire de retour n'est pas configuré correctement.",
        .settingsFeedbackSendFailure: "Impossible d'envoyer le retour maintenant. Réessaie.",
        .settingsFeedbackNetworkError: "Erreur réseau pendant l'envoi du retour. Vérifie la connexion et réessaie.",
        .settingsFeedbackSentThanks: "Merci. Ton retour a été envoyé.",
        .settingsDeveloperFootnote: "Les diagnostics de lancement réservés aux développeurs sont masqués pour les utilisateurs en production."
    ]
}
