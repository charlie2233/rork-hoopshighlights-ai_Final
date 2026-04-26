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
        .languageSubtitle: "Choose how Hoops Clips talks to you.",
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
        .controlRoom: "Control Room",
        .controlRoomSubtitle: "Manage your account, tune AI defaults, and jump into focused setup screens instead of one long settings list.",
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
        .resetDefaultsDescription: "Restore all AI tuning values to the original Hoops Clips defaults."
    ]

    private static let chineseText: [AppTextKey: String] = [
        .tabPlayer: "播放器",
        .tabReview: "审核",
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
        .controlRoom: "控制中心",
        .controlRoomSubtitle: "管理账号、调整 AI 默认设置，并进入专门的设置页面。",
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
        .resetDefaultsDescription: "将所有 AI 调整恢复为 Hoops Clips 默认值。"
    ]

    private static let spanishText: [AppTextKey: String] = [
        .tabPlayer: "Video",
        .tabReview: "Revisar",
        .tabExport: "Exportar",
        .tabHistory: "Historial",
        .tabSettings: "Ajustes",
        .settingsTitle: "Ajustes",
        .languageTitle: "Idioma",
        .languageSubtitle: "Elige cómo Hoops Clips te habla.",
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
        .controlRoom: "Panel de control",
        .controlRoomSubtitle: "Gestiona tu cuenta, ajusta la IA y entra a pantallas enfocadas sin una lista interminable.",
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
        .resetDefaultsDescription: "Restaurar todos los ajustes de IA a los valores de Hoops Clips."
    ]

    private static let frenchText: [AppTextKey: String] = [
        .tabPlayer: "Lecteur",
        .tabReview: "Revue",
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
        .controlRoom: "Centre de contrôle",
        .controlRoomSubtitle: "Gère ton compte, ajuste l'IA et ouvre des écrans ciblés au lieu d'une longue liste.",
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
        .resetDefaultsDescription: "Restaurer tous les réglages IA aux valeurs Hoops Clips."
    ]
}
