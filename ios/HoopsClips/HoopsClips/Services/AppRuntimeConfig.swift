import Foundation

nonisolated enum CloudLaunchMode: String, Codable, Sendable, CaseIterable {
    case enabled
    case internalOnly = "internal_only"
    case disabled

    var allowsCloudRequests: Bool {
        self != .disabled
    }

    var supportLabel: String {
        switch self {
        case .enabled:
            return "Cloud enabled"
        case .internalOnly:
            return "Internal only"
        case .disabled:
            return "On-device only"
        }
    }
}

struct AppRuntimeConfig {
    static let shared = AppRuntimeConfig(bundle: .main)

    let environmentName: String
    let revenueCatAPIKey: String
    let googleClientID: String
    let googleReversedClientID: String
    let cloudAnalysisBaseURL: String
    let sentryDSN: String
    let cloudLaunchMode: CloudLaunchMode

    init(
        environmentName: String,
        revenueCatAPIKey: String,
        googleClientID: String,
        googleReversedClientID: String,
        cloudAnalysisBaseURL: String,
        sentryDSN: String,
        cloudLaunchMode: CloudLaunchMode
    ) {
        self.environmentName = environmentName.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        self.revenueCatAPIKey = revenueCatAPIKey.trimmingCharacters(in: .whitespacesAndNewlines)
        self.googleClientID = googleClientID.trimmingCharacters(in: .whitespacesAndNewlines)
        self.googleReversedClientID = googleReversedClientID.trimmingCharacters(in: .whitespacesAndNewlines)
        self.cloudAnalysisBaseURL = cloudAnalysisBaseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        self.sentryDSN = sentryDSN.trimmingCharacters(in: .whitespacesAndNewlines)
        self.cloudLaunchMode = cloudLaunchMode
    }

    init(bundle: Bundle) {
        self.init(
            environmentName: bundle.string(for: "HOOPSAppEnvironment") ?? "debug",
            revenueCatAPIKey: bundle.string(for: "HOOPSRevenueCatAPIKey") ?? "",
            googleClientID: bundle.string(for: "HOOPSGoogleClientID") ?? "",
            googleReversedClientID: bundle.string(for: "HOOPSGoogleReversedClientID") ?? "",
            cloudAnalysisBaseURL: bundle.string(for: "HOOPSCloudAnalysisBaseURL") ?? "",
            sentryDSN: bundle.string(for: "HOOPSSentryDSN") ?? "",
            cloudLaunchMode: CloudLaunchMode(
                rawValue: bundle.string(for: "HOOPSCloudLaunchMode") ?? CloudLaunchMode.disabled.rawValue
            ) ?? .disabled
        )
    }

    var isProduction: Bool {
        environmentName == "production"
    }

    var isDebug: Bool {
        environmentName == "debug"
    }

    var googleSignInConfigured: Bool {
        !googleClientID.isEmpty && !googleReversedClientID.isEmpty
    }

    var resolvedCloudAnalysisBaseURL: URL? {
        guard cloudLaunchMode.allowsCloudRequests, !cloudAnalysisBaseURL.isEmpty else {
            return nil
        }

        guard let url = URL(string: cloudAnalysisBaseURL),
              let scheme = url.scheme?.lowercased(),
              scheme == "https" || (isDebug && scheme == "http") else {
            return nil
        }

        return url
    }

    var allowsCloudAnalysisRequests: Bool {
        resolvedCloudAnalysisBaseURL != nil
    }

    var launchAnalysisMode: AnalysisExecutionMode {
        allowsCloudAnalysisRequests ? .cloud : .local
    }

    var missingRequiredKeys: [String] {
        guard isProduction else { return [] }

        var missing: [String] = []
        if revenueCatAPIKey.isEmpty {
            missing.append("HOOPSRevenueCatAPIKey")
        }
        if googleClientID.isEmpty {
            missing.append("HOOPSGoogleClientID")
        }
        if googleReversedClientID.isEmpty {
            missing.append("HOOPSGoogleReversedClientID")
        }
        if cloudLaunchMode.allowsCloudRequests && resolvedCloudAnalysisBaseURL == nil {
            missing.append("HOOPSCloudAnalysisBaseURL")
        }
        return missing
    }
}

private extension Bundle {
    func string(for key: String) -> String? {
        guard let rawValue = object(forInfoDictionaryKey: key) as? String else {
            return nil
        }

        let trimmed = rawValue.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}
