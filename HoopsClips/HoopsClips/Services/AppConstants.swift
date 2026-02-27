import Foundation

enum AppConstants {
    static let revenueCatTestAPIKey = "test_bJcnJkVgFGDpzQgnknxyemoNcXP"
    static let revenueCatProdAPIKey = ""
    static let googleClientID = ""
    static let cloudAnalysisVersion = "v1"
    static let cloudAnalysisDailyQuota = 3
#if DEBUG
    static let defaultCloudAnalysisBaseURL = "http://127.0.0.1:8080"
#else
    static let defaultCloudAnalysisBaseURL = ""
#endif

    static var cloudAnalysisBaseURL: String {
        let defaultsOverride = UserDefaults.standard.string(forKey: "hoops.cloudAnalysisBaseURL")?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if !defaultsOverride.isEmpty {
            return defaultsOverride
        }
        return defaultCloudAnalysisBaseURL
    }
}
