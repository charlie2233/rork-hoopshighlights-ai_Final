import Foundation

enum AppConstants {
    static let cloudAnalysisVersion = "v1"
    static let cloudAnalysisDailyQuota = 5
    static let nonProMaxAnalysisDuration: Double = 15 * 60
    static let cloudAnalysisMaxDuration: Double = 30 * 60

    static var cloudAnalysisBaseURL: String {
        let defaultsOverride = UserDefaults.standard.string(forKey: "hoops.cloudAnalysisBaseURL")?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if !defaultsOverride.isEmpty {
            return defaultsOverride
        }
        return AppRuntimeConfig.shared.cloudAnalysisBaseURL
    }
}
