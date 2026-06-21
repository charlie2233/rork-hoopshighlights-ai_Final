import SwiftUI
import UIKit
import RevenueCat
import GoogleSignIn

@main
struct HoopsClipsApp: App {
    @UIApplicationDelegateAdaptor(HoopsClipsAppDelegate.self) private var appDelegate

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

final class HoopsClipsAppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        handleEventsForBackgroundURLSession identifier: String,
        completionHandler: @escaping () -> Void
    ) {
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "background_urlsession_events_received",
            metadata: [
                "identifierHash=\(stableBackgroundSessionHash(identifier))",
                "privacy=no_raw_session_ids_no_urls_no_object_keys"
            ].joined(separator: " ")
        )
        CloudUploadBackgroundSessionRegistry.shared.setCompletionHandler(completionHandler, for: identifier)
    }

    private func stableBackgroundSessionHash(_ value: String) -> String {
        var hash: UInt64 = 14_695_981_039_346_656_037
        for byte in value.utf8 {
            hash ^= UInt64(byte)
            hash = hash &* 1_099_511_628_211
        }
        return String(hash, radix: 16)
    }
}
