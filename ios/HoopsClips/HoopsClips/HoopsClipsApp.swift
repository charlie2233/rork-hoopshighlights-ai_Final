import SwiftUI
import RevenueCat
import GoogleSignIn

@main
struct HoopsClipsApp: App {
    init() {
        let runtimeConfig = AppRuntimeConfig.shared
        let telemetry = LaunchTelemetry.shared

        telemetry.configure()

        if !runtimeConfig.missingRequiredKeys.isEmpty {
            let message = "Missing HoopClips runtime config keys: \(runtimeConfig.missingRequiredKeys.joined(separator: ", "))"
            telemetry.recordConfigurationIssue(message)
        }

        let apiKey = AppConstants.revenueCatAPIKey
        #if DEBUG
        if !apiKey.isEmpty {
            Purchases.logLevel = .debug
        }
        #endif
        if !apiKey.isEmpty {
            Purchases.configure(withAPIKey: apiKey)
        }
        Task { @MainActor in
            AnalysisNotificationService.shared.configure()
        }
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .onOpenURL { url in
                    _ = GIDSignIn.sharedInstance.handle(url)
                }
        }
    }
}
