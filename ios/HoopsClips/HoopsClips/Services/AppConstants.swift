import Foundation

enum AppConstants {
    static let cloudAnalysisVersion = "v1"
    static let cloudAnalysisDailyQuota = 5
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

    static var cloudAnalysisEnabled: Bool {
        runtimeConfig.allowsCloudAnalysisRequests
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
}
