import SwiftUI
import UIKit
import RevenueCat
import GoogleSignIn

@main
struct HoopsClipsApp: App {
    init() {
        Self.configureNavigationTitlePlacement()

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

    private static func configureNavigationTitlePlacement() {
        let titleOffset = UIOffset(horizontal: 8, vertical: -4)
        let titleParagraph = NSMutableParagraphStyle()
        titleParagraph.firstLineHeadIndent = titleOffset.horizontal
        titleParagraph.headIndent = titleOffset.horizontal

        let titleAttributes: [NSAttributedString.Key: Any] = [
            .foregroundColor: UIColor.white,
            .baselineOffset: 2,
            .paragraphStyle: titleParagraph
        ]

        let navigationAppearance = UINavigationBarAppearance()
        navigationAppearance.configureWithOpaqueBackground()
        navigationAppearance.backgroundColor = UIColor(AppTheme.darkBg)
        navigationAppearance.shadowColor = .clear
        navigationAppearance.titleTextAttributes = titleAttributes
        navigationAppearance.largeTitleTextAttributes = titleAttributes
        navigationAppearance.titlePositionAdjustment = titleOffset

        let navigationBar = UINavigationBar.appearance()
        navigationBar.tintColor = UIColor(AppTheme.neonPurple)
        navigationBar.standardAppearance = navigationAppearance
        navigationBar.scrollEdgeAppearance = navigationAppearance
        navigationBar.compactAppearance = navigationAppearance
        if #available(iOS 15.0, *) {
            navigationBar.compactScrollEdgeAppearance = navigationAppearance
        }
    }
}
