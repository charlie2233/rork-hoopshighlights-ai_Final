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
    let firebaseAuthAPIKey: String
    let privacyPolicyURL: String
    let termsOfServiceURL: String
    let cloudAnalysisBaseURL: String
    let cloudEditBaseURL: String
    let sentryDSN: String
    let cloudLaunchMode: CloudLaunchMode

    init(
        environmentName: String,
        revenueCatAPIKey: String,
        googleClientID: String,
        googleReversedClientID: String,
        firebaseAuthAPIKey: String,
        privacyPolicyURL: String,
        termsOfServiceURL: String,
        cloudAnalysisBaseURL: String,
        cloudEditBaseURL: String = "",
        sentryDSN: String,
        cloudLaunchMode: CloudLaunchMode
    ) {
        self.environmentName = environmentName.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        self.revenueCatAPIKey = revenueCatAPIKey.trimmingCharacters(in: .whitespacesAndNewlines)
        self.googleClientID = googleClientID.trimmingCharacters(in: .whitespacesAndNewlines)
        self.googleReversedClientID = googleReversedClientID.trimmingCharacters(in: .whitespacesAndNewlines)
        self.firebaseAuthAPIKey = firebaseAuthAPIKey.trimmingCharacters(in: .whitespacesAndNewlines)
        self.privacyPolicyURL = privacyPolicyURL.trimmingCharacters(in: .whitespacesAndNewlines)
        self.termsOfServiceURL = termsOfServiceURL.trimmingCharacters(in: .whitespacesAndNewlines)
        self.cloudAnalysisBaseURL = cloudAnalysisBaseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        self.cloudEditBaseURL = cloudEditBaseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        self.sentryDSN = sentryDSN.trimmingCharacters(in: .whitespacesAndNewlines)
        self.cloudLaunchMode = cloudLaunchMode
    }

    init(bundle: Bundle) {
        self.init(
            environmentName: bundle.string(for: "HOOPSAppEnvironment") ?? "debug",
            revenueCatAPIKey: bundle.string(for: "HOOPSRevenueCatAPIKey") ?? "",
            googleClientID: bundle.string(for: "HOOPSGoogleClientID") ?? "",
            googleReversedClientID: bundle.string(for: "HOOPSGoogleReversedClientID") ?? "",
            firebaseAuthAPIKey: bundle.string(for: "HOOPSFirebaseAuthAPIKey") ?? "",
            privacyPolicyURL: bundle.string(for: "HOOPSPrivacyPolicyURL") ?? "",
            termsOfServiceURL: bundle.string(for: "HOOPSTermsOfServiceURL") ?? "",
            cloudAnalysisBaseURL: bundle.string(for: "HOOPSCloudAnalysisBaseURL") ?? "",
            cloudEditBaseURL: bundle.string(for: "HOOPSCloudEditBaseURL") ?? "",
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

    var emailPasswordAuthConfigured: Bool {
        !firebaseAuthAPIKey.isEmpty
    }

    var resolvedPrivacyPolicyURL: URL? {
        resolvedURL(from: privacyPolicyURL)
    }

    var resolvedTermsOfServiceURL: URL? {
        resolvedURL(from: termsOfServiceURL)
    }

    var legalLinksConfigured: Bool {
        resolvedPrivacyPolicyURL != nil && resolvedTermsOfServiceURL != nil
    }

    var resolvedCloudAnalysisBaseURL: URL? {
        guard cloudLaunchMode.allowsCloudRequests, !cloudAnalysisBaseURL.isEmpty else {
            return nil
        }

        return resolvedURL(from: cloudAnalysisBaseURL)
    }

    var resolvedCloudEditBaseURL: URL? {
        guard cloudLaunchMode.allowsCloudRequests, !cloudEditBaseURL.isEmpty else {
            return nil
        }

        return resolvedURL(from: cloudEditBaseURL)
    }

    private func resolvedURL(from rawValue: String) -> URL? {
        guard !rawValue.isEmpty else {
            return nil
        }

        guard let url = URL(string: rawValue),
              let scheme = url.scheme?.lowercased(),
              scheme == "https" || (isDebug && scheme == "http") else {
            return nil
        }

        return url
    }

    var allowsCloudAnalysisRequests: Bool {
        resolvedCloudAnalysisBaseURL != nil
    }

    var allowsCloudEditRequests: Bool {
        resolvedCloudEditBaseURL != nil
    }

    var allowsLocalVideoPipeline: Bool {
        isDebug
    }

    var requiresCloudVideoPipeline: Bool {
        !allowsLocalVideoPipeline
    }

    var launchAnalysisMode: AnalysisExecutionMode {
        requiresCloudVideoPipeline || allowsCloudAnalysisRequests ? .cloud : .local
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
        if firebaseAuthAPIKey.isEmpty {
            missing.append("HOOPSFirebaseAuthAPIKey")
        }
        if resolvedPrivacyPolicyURL == nil {
            missing.append("HOOPSPrivacyPolicyURL")
        }
        if resolvedTermsOfServiceURL == nil {
            missing.append("HOOPSTermsOfServiceURL")
        }
        if !cloudLaunchMode.allowsCloudRequests {
            missing.append("HOOPSCloudLaunchMode")
        }
        if resolvedCloudAnalysisBaseURL == nil {
            missing.append("HOOPSCloudAnalysisBaseURL")
        }
        if resolvedCloudEditBaseURL == nil {
            missing.append("HOOPSCloudEditBaseURL")
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
