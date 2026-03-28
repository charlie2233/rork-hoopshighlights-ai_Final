import SwiftUI
import RevenueCat

@main
struct HoopsClipsApp: App {
    init() {
        let runtimeConfig = AppRuntimeConfig.shared
        if !runtimeConfig.missingRequiredKeys.isEmpty {
            print("Missing HoopsClips runtime config keys: \(runtimeConfig.missingRequiredKeys.joined(separator: ", "))")
        }
        let apiKey = runtimeConfig.revenueCatAPIKey
        if runtimeConfig.environmentName != "production" {
            Purchases.logLevel = .debug
        }
        if !apiKey.isEmpty {
            Purchases.configure(withAPIKey: apiKey)
        }
        if !LaunchAutomation.isEnabled {
            Task { @MainActor in
                AnalysisNotificationService.shared.configure()
            }
        }
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
