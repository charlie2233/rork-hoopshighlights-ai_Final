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
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
