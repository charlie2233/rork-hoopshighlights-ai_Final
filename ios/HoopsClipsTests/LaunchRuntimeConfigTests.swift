import Testing
@testable import HoopsClips

struct LaunchRuntimeConfigTests {
    @Test func testProductionDisabledCloudLaunchModeDoesNotRequireCloudURL() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            cloudAnalysisBaseURL: "",
            sentryDSN: "",
            cloudLaunchMode: .disabled
        )

        #expect(config.missingRequiredKeys.isEmpty)
        #expect(config.cloudLaunchMode == .disabled)
        #expect(config.allowsCloudAnalysisRequests == false)
        #expect(config.launchAnalysisMode == .local)
    }

    @Test func testProductionEnabledCloudLaunchModeRequiresSecureURL() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
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
            cloudAnalysisBaseURL: "https://api.hoopsclips.example",
            sentryDSN: "https://dsn.ingest.sentry.io/1",
            cloudLaunchMode: .enabled
        )

        #expect(config.missingRequiredKeys.isEmpty)
        #expect(config.allowsCloudAnalysisRequests)
        #expect(config.launchAnalysisMode == .cloud)
    }
}
