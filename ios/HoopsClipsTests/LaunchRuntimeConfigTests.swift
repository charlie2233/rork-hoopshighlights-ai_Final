import Foundation
import Testing
@testable import HoopsClips

struct LaunchRuntimeConfigTests {
    @Test func testProductionDisabledCloudLaunchModeFailsCloudReadiness() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "com.googleusercontent.apps.example",
            firebaseAuthAPIKey: "firebase_key",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "",
            sentryDSN: "",
            cloudLaunchMode: .disabled
        )

        #expect(config.missingRequiredKeys.contains("HOOPSCloudLaunchMode"))
        #expect(config.missingRequiredKeys.contains("HOOPSCloudAnalysisBaseURL"))
        #expect(config.missingRequiredKeys.contains("HOOPSCloudEditBaseURL"))
        #expect(config.cloudLaunchMode == .disabled)
        #expect(config.allowsCloudAnalysisRequests == false)
        #expect(config.googleSignInConfigured)
        #expect(config.emailPasswordAuthConfigured)
        #expect(config.requiresCloudVideoPipeline)
        #expect(config.launchAnalysisMode == .cloud)
    }

    @Test func testProductionEnabledCloudLaunchModeRequiresSecureURL() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "com.googleusercontent.apps.example",
            firebaseAuthAPIKey: "firebase_key",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "http://example.com",
            cloudEditBaseURL: "https://edit.hoopsclips.example",
            sentryDSN: "",
            cloudLaunchMode: .enabled
        )

        #expect(config.missingRequiredKeys.contains("HOOPSCloudAnalysisBaseURL"))
        #expect(config.allowsCloudAnalysisRequests == false)
        #expect(config.requiresCloudVideoPipeline)
        #expect(config.launchAnalysisMode == .cloud)
    }

    @Test func testProductionEnabledCloudLaunchModeUsesCloudWhenSecureURLExists() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "com.googleusercontent.apps.example",
            firebaseAuthAPIKey: "firebase_key",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "https://api.hoopsclips.example",
            cloudEditBaseURL: "https://edit.hoopsclips.example",
            sentryDSN: "https://dsn.ingest.sentry.io/1",
            cloudLaunchMode: .enabled
        )

        #expect(config.missingRequiredKeys.isEmpty)
        #expect(config.allowsCloudAnalysisRequests)
        #expect(config.allowsCloudEditRequests)
        #expect(config.requiresCloudVideoPipeline)
        #expect(config.launchAnalysisMode == .cloud)
    }

    @Test func testInternalStagingCloudLaunchModeDoesNotDowngradeToLocalWhenURLIsMissing() {
        let missingURLConfig = AppRuntimeConfig(
            environmentName: "internal_staging",
            revenueCatAPIKey: "",
            googleClientID: "",
            googleReversedClientID: "",
            firebaseAuthAPIKey: "",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "",
            sentryDSN: "",
            cloudLaunchMode: .internalOnly
        )
        #expect(missingURLConfig.allowsCloudAnalysisRequests == false)
        #expect(missingURLConfig.requiresCloudVideoPipeline)
        #expect(missingURLConfig.launchAnalysisMode == .cloud)

        let invalidURLConfig = AppRuntimeConfig(
            environmentName: "internal_staging",
            revenueCatAPIKey: "",
            googleClientID: "",
            googleReversedClientID: "",
            firebaseAuthAPIKey: "",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "http://127.0.0.1:8080",
            sentryDSN: "",
            cloudLaunchMode: .internalOnly
        )
        #expect(invalidURLConfig.allowsCloudAnalysisRequests == false)
        #expect(invalidURLConfig.requiresCloudVideoPipeline)
        #expect(invalidURLConfig.launchAnalysisMode == .cloud)
    }

    @Test @MainActor func testVideoExportServiceUnavailableStateClearsLocalExport() {
        let service = VideoExportService()
        service.isExporting = true
        service.exportProgress = 0.5
        service.exportedURL = URL(fileURLWithPath: "/tmp/local-export.mp4")

        service.markUnavailable("Cloud rendering is required for this build.")

        #expect(service.isExporting == false)
        #expect(service.exportProgress == 0.0)
        #expect(service.exportedURL == nil)
        #expect(service.statusMessage == "Cloud rendering is required for this build.")
    }

    @Test func testCloudEditEndpointIsRequiredAndRequiresSecureURLInProduction() {
        let disabledConfig = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "com.googleusercontent.apps.example",
            firebaseAuthAPIKey: "firebase_key",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "",
            cloudEditBaseURL: "",
            sentryDSN: "",
            cloudLaunchMode: .disabled
        )
        #expect(disabledConfig.allowsCloudEditRequests == false)
        #expect(disabledConfig.missingRequiredKeys.contains("HOOPSCloudLaunchMode"))
        #expect(disabledConfig.missingRequiredKeys.contains("HOOPSCloudEditBaseURL"))

        let disabledWithEditURLConfig = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "com.googleusercontent.apps.example",
            firebaseAuthAPIKey: "firebase_key",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "",
            cloudEditBaseURL: "https://hoopsclips-control-plane-staging.example",
            sentryDSN: "",
            cloudLaunchMode: .disabled
        )
        #expect(disabledWithEditURLConfig.allowsCloudAnalysisRequests == false)
        #expect(disabledWithEditURLConfig.allowsCloudEditRequests == false)
        #expect(disabledWithEditURLConfig.missingRequiredKeys.contains("HOOPSCloudLaunchMode"))

        let enabledConfig = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "com.googleusercontent.apps.example",
            firebaseAuthAPIKey: "firebase_key",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "https://api.hoopsclips.example",
            cloudEditBaseURL: "https://hoopsclips-control-plane-staging.example",
            sentryDSN: "",
            cloudLaunchMode: .enabled
        )
        #expect(enabledConfig.allowsCloudAnalysisRequests)
        #expect(enabledConfig.allowsCloudEditRequests)
    }

    @Test func testProductionRequiresGoogleReversedClientIDForGoogleReadiness() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "",
            firebaseAuthAPIKey: "firebase_key",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "https://api.hoopsclips.example",
            cloudEditBaseURL: "https://edit.hoopsclips.example",
            sentryDSN: "",
            cloudLaunchMode: .enabled
        )

        #expect(config.googleSignInConfigured == false)
        #expect(config.missingRequiredKeys.contains("HOOPSGoogleReversedClientID"))
    }

    @Test func testProductionRequiresFirebaseAuthForEmailReadiness() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "com.googleusercontent.apps.example",
            firebaseAuthAPIKey: "",
            privacyPolicyURL: "https://example.com/privacy",
            termsOfServiceURL: "https://example.com/terms",
            cloudAnalysisBaseURL: "https://api.hoopsclips.example",
            cloudEditBaseURL: "https://edit.hoopsclips.example",
            sentryDSN: "",
            cloudLaunchMode: .enabled
        )

        #expect(config.emailPasswordAuthConfigured == false)
        #expect(config.missingRequiredKeys.contains("HOOPSFirebaseAuthAPIKey"))
    }

    @Test func testProductionRequiresReachableLegalLinksForPublishReadiness() {
        let config = AppRuntimeConfig(
            environmentName: "production",
            revenueCatAPIKey: "prod_key",
            googleClientID: "google_client",
            googleReversedClientID: "com.googleusercontent.apps.example",
            firebaseAuthAPIKey: "firebase_key",
            privacyPolicyURL: "not-a-url",
            termsOfServiceURL: "",
            cloudAnalysisBaseURL: "https://api.hoopsclips.example",
            cloudEditBaseURL: "https://edit.hoopsclips.example",
            sentryDSN: "",
            cloudLaunchMode: .enabled
        )

        #expect(config.legalLinksConfigured == false)
        #expect(config.missingRequiredKeys.contains("HOOPSPrivacyPolicyURL"))
        #expect(config.missingRequiredKeys.contains("HOOPSTermsOfServiceURL"))
    }
}
