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
        let titleLeadingInset: CGFloat = 24
        let titleOffset = UIOffset(horizontal: 0, vertical: -2)
        let titleParagraph = NSMutableParagraphStyle()
        titleParagraph.firstLineHeadIndent = titleLeadingInset
        titleParagraph.headIndent = titleLeadingInset

        let titleAttributes: [NSAttributedString.Key: Any] = [
            .foregroundColor: UIColor.white,
            .baselineOffset: 1,
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
        navigationBar.layoutMargins.left = titleLeadingInset
        navigationBar.layoutMargins.right = 16
        navigationBar.standardAppearance = navigationAppearance
        navigationBar.scrollEdgeAppearance = navigationAppearance
        navigationBar.compactAppearance = navigationAppearance
        if #available(iOS 15.0, *) {
            navigationBar.compactScrollEdgeAppearance = navigationAppearance
        }
    }
}
