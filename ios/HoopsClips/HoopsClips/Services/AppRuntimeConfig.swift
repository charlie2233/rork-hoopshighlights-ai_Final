import Foundation

struct AppRuntimeConfig {
    static let shared = AppRuntimeConfig(bundle: .main)

    let environmentName: String
    let revenueCatAPIKey: String
    let googleClientID: String
    let cloudAnalysisBaseURL: String
    let sentryDSN: String

    init(bundle: Bundle) {
        environmentName = bundle.string(for: "HOOPSAppEnvironment") ?? "unknown"
        revenueCatAPIKey = bundle.string(for: "HOOPSRevenueCatAPIKey") ?? ""
        googleClientID = bundle.string(for: "HOOPSGoogleClientID") ?? ""
        cloudAnalysisBaseURL = bundle.string(for: "HOOPSCloudAnalysisBaseURL") ?? ""
        sentryDSN = bundle.string(for: "HOOPSSentryDSN") ?? ""
    }

    var missingRequiredKeys: [String] {
        let normalizedEnvironment = environmentName.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard normalizedEnvironment == "staging" || normalizedEnvironment == "production" else {
            return []
        }

        var missing: [String] = []
        if normalizedEnvironment == "production", revenueCatAPIKey.isEmpty {
            missing.append("HOOPSRevenueCatAPIKey")
        }
        if normalizedEnvironment == "production", googleClientID.isEmpty {
            missing.append("HOOPSGoogleClientID")
        }
        if cloudAnalysisBaseURL.isEmpty {
            missing.append("HOOPSCloudAnalysisBaseURL")
        }
        return missing
    }
}

private extension Bundle {
    func string(for key: String) -> String? {
        guard let value = object(forInfoDictionaryKey: key) as? String else { return nil }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}
