import Testing
@testable import HoopsClips

struct LaunchRuntimeConfigTests {
    @Test func testProductionDisabledCloudLaunchModeDoesNotRequireCloudURL() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "com.googleusercontent.apps.example",
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
            cloudAnalysisBaseURL: "",
            sentryDSN: "",
            cloudLaunchMode: .disabled
        )

        #expect(config.googleSignInConfigured == false)
        #expect(config.missingRequiredKeys.contains("HOOPSGoogleReversedClientID"))
    }
}
