import Foundation
import UIKit
import UserNotifications

@MainActor
final class AnalysisNotificationService: NSObject {
    enum CompletionContext: String {
        case analysis
        case backgroundUploadResume
    }

    static let shared = AnalysisNotificationService()

    private override init() {
        super.init()
    }

    func configure() {
        UNUserNotificationCenter.current().delegate = self
    }

    func prepareForAnalysis() async {
        let center = UNUserNotificationCenter.current()
        let settings = await center.notificationSettings()

        guard settings.authorizationStatus == .notDetermined else { return }
        _ = try? await center.requestAuthorization(options: [.alert, .sound, .badge])
    }

    func notifyAnalysisCompleted(
        clipsCount: Int,
        usedFallback: Bool,
        context: CompletionContext = .analysis
    ) {
        Task {
            let center = UNUserNotificationCenter.current()
            let settings = await center.notificationSettings()
            let status = settings.authorizationStatus
            guard status == .authorized || status == .provisional || status == .ephemeral else { return }

            let content = UNMutableNotificationContent()
            content.title = clipsCount > 0 ? "Review ready" : "Analysis finished"
            if clipsCount > 0 {
                let clipLabel = "clip\(clipsCount == 1 ? "" : "s")"
                switch context {
                case .analysis:
                    content.body = "HoopClips found \(clipsCount) \(clipLabel). Open Review to keep or nah."
                case .backgroundUploadResume:
                    content.body = "Background upload finished. HoopClips found \(clipsCount) \(clipLabel). Open Review to keep or nah."
                }
            } else {
                switch context {
                case .analysis:
                    content.body = "Your highlight scan finished, but no strong clips were detected."
                case .backgroundUploadResume:
                    content.body = "Background upload finished, but no strong clips were detected."
                }
            }
            content.sound = .default
            content.threadIdentifier = "hoopclips-analysis"
            content.categoryIdentifier = "analysis-complete"
            content.userInfo = [
                "source": "HoopClips",
                "event": "analysis_completed",
                "clipsCount": clipsCount,
                "usedFallback": usedFallback,
                "completionContext": context.rawValue
            ]

            let request = UNNotificationRequest(
                identifier: "analysis-complete-\(UUID().uuidString)",
                content: content,
                trigger: nil
            )
            try? await center.add(request)
        }
    }
}

extension AnalysisNotificationService: UNUserNotificationCenterDelegate {
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound]
    }
}
