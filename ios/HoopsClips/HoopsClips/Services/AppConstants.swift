import Foundation

enum AppConstants {
    static let cloudAnalysisVersion = "v1"
    static let cloudAnalysisDailyQuota = 3
    static let nonProMaxAnalysisDuration: Double = 15 * 60
    static let cloudAnalysisMaxDuration: Double = 30 * 60

    static var runtimeConfig: AppRuntimeConfig {
        AppRuntimeConfig.shared
    }

    static var revenueCatAPIKey: String {
        runtimeConfig.revenueCatAPIKey
    }

    static var googleClientID: String {
        runtimeConfig.googleClientID
    }

    static var googleReversedClientID: String {
        runtimeConfig.googleReversedClientID
    }

    static var firebaseAuthAPIKey: String {
        runtimeConfig.firebaseAuthAPIKey
    }

    static var emailPasswordAuthConfigured: Bool {
        runtimeConfig.emailPasswordAuthConfigured
    }

    static var privacyPolicyURL: URL? {
        runtimeConfig.resolvedPrivacyPolicyURL
    }

    static var termsOfServiceURL: URL? {
        runtimeConfig.resolvedTermsOfServiceURL
    }

    static var legalLinksConfigured: Bool {
        runtimeConfig.legalLinksConfigured
    }

    static var googleSignInConfigured: Bool {
        runtimeConfig.googleSignInConfigured
    }

    static var sentryDSN: String {
        runtimeConfig.sentryDSN
    }

    static var environmentName: String {
        runtimeConfig.environmentName
    }

    static var cloudLaunchMode: CloudLaunchMode {
        runtimeConfig.cloudLaunchMode
    }

    static var requiresCloudVideoPipeline: Bool {
        runtimeConfig.requiresCloudVideoPipeline
    }

    static var localVideoExportUnavailableMessage: String {
        "Cloud rendering is required for this build. Use AI Edit to render, preview, download, or share."
    }

    static var cloudAnalysisEnabled: Bool {
        runtimeConfig.requiresCloudVideoPipeline || runtimeConfig.allowsCloudAnalysisRequests || (runtimeConfig.isDebug && !cloudAnalysisBaseURL.isEmpty)
    }

    static var cloudEditEnabled: Bool {
        runtimeConfig.allowsCloudEditRequests || (runtimeConfig.isDebug && !cloudEditBaseURL.isEmpty)
    }

    static var cloudLaunchStatusLabel: String {
        runtimeConfig.cloudLaunchMode.supportLabel
    }

    static var cloudAnalysisBaseURL: String {
        if runtimeConfig.isDebug {
            let defaultsOverride = UserDefaults.standard.string(forKey: "hoops.cloudAnalysisBaseURL")?
                .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            if !defaultsOverride.isEmpty {
                return defaultsOverride
            }
        }
        return runtimeConfig.resolvedCloudAnalysisBaseURL?.absoluteString ?? ""
    }

    static var cloudEditBaseURL: String {
        if runtimeConfig.isDebug {
            let defaultsOverride = UserDefaults.standard.string(forKey: "hoops.cloudEditBaseURL")?
                .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            if !defaultsOverride.isEmpty {
                return defaultsOverride
            }
        }
        return runtimeConfig.resolvedCloudEditBaseURL?.absoluteString ?? ""
    }
}
