import SwiftUI
import RevenueCat

@main
struct HoopsClipsApp: App {
    init() {
        let apiKey: String
        #if DEBUG
        apiKey = AppConstants.revenueCatTestAPIKey
        Purchases.logLevel = .debug
        #else
        apiKey = AppConstants.revenueCatProdAPIKey
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
        }
    }
}
