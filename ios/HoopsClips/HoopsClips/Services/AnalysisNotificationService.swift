import Foundation
import UIKit
import UserNotifications

@MainActor
final class AnalysisNotificationService: NSObject {
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

    func notifyAnalysisCompleted(clipsCount: Int, usedFallback: Bool) {
        guard UIApplication.shared.applicationState != .active else { return }

        Task {
            let center = UNUserNotificationCenter.current()
            let settings = await center.notificationSettings()
            let status = settings.authorizationStatus
            guard status == .authorized || status == .provisional || status == .ephemeral else { return }

            let content = UNMutableNotificationContent()
            content.title = "Analysis Complete"
            if clipsCount > 0 {
                content.body = "Your highlight scan finished and found \(clipsCount) clip\(clipsCount == 1 ? "" : "s")."
            } else {
                content.body = "Your highlight scan finished, but no strong clips were detected."
            }
            content.sound = .default

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
