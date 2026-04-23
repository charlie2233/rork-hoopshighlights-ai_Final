import Testing
@testable import HoopsClips

struct LaunchRuntimeConfigTests {
    @Test func testProductionDisabledCloudLaunchModeDoesNotRequireCloudURL() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "com.googleusercontent.apps.example",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "",
            sentryDSN: "",
            cloudLaunchMode: .disabled
        )

        #expect(config.missingRequiredKeys.isEmpty)
        #expect(config.cloudLaunchMode == .disabled)
        #expect(config.allowsCloudAnalysisRequests == false)
        #expect(config.googleSignInConfigured)
        #expect(config.launchAnalysisMode == .local)
    }

    @Test func testProductionEnabledCloudLaunchModeRequiresSecureURL() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "com.googleusercontent.apps.example",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "http://example.com",
            sentryDSN: "",
            cloudLaunchMode: .enabled
        )

        #expect(config.missingRequiredKeys.contains("HOOPSCloudAnalysisBaseURL"))
        #expect(config.allowsCloudAnalysisRequests == false)
        #expect(config.launchAnalysisMode == .local)
    }

    @Test func testProductionEnabledCloudLaunchModeUsesCloudWhenSecureURLExists() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "com.googleusercontent.apps.example",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "https://api.hoopsclips.example",
            sentryDSN: "https://dsn.ingest.sentry.io/1",
            cloudLaunchMode: .enabled
        )

        #expect(config.missingRequiredKeys.isEmpty)
        #expect(config.allowsCloudAnalysisRequests)
        #expect(config.launchAnalysisMode == .cloud)
    }

    @Test func testProductionRequiresGoogleReversedClientIDForGoogleReadiness() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "",
            sentryDSN: "",
            cloudLaunchMode: .disabled
        )

        #expect(config.googleSignInConfigured == false)
        #expect(config.missingRequiredKeys.contains("HOOPSGoogleReversedClientID"))
    }

    @Test func testProductionRequiresReachableLegalLinksForPublishReadiness() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "com.googleusercontent.apps.example",
            privacyPolicyURL: "not-a-url",
            termsOfServiceURL: "",
            cloudAnalysisBaseURL: "",
            sentryDSN: "",
            cloudLaunchMode: .disabled
        )

        #expect(config.legalLinksConfigured == false)
        #expect(config.missingRequiredKeys.contains("HOOPSPrivacyPolicyURL"))
        #expect(config.missingRequiredKeys.contains("HOOPSTermsOfServiceURL"))
    }
}
