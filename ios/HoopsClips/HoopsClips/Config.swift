import Foundation

enum Config {
    static let environment = AppRuntimeConfig.shared.environmentName
    static let revenueCatAPIKey = AppRuntimeConfig.shared.revenueCatAPIKey
    static let googleClientID = AppRuntimeConfig.shared.googleClientID
    static let cloudAnalysisBaseURL = AppRuntimeConfig.shared.cloudAnalysisBaseURL
    static let sentryDSN = AppRuntimeConfig.shared.sentryDSN
}
