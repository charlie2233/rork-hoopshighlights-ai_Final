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
        let granted = (try? await center.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
        if !granted {
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "analysis_notification_permission_denied",
                metadata: "source=prepare_for_analysis"
            )
        }
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
            guard status == .authorized || status == .provisional || status == .ephemeral else {
                LaunchTelemetry.shared.recordBackgroundUploadProof(
                    "analysis_notification_blocked",
                    metadata: "context=\(context.rawValue) status=\(Self.authorizationProofStatus(status))"
                )
                return
            }

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
            do {
                try await center.add(request)
                LaunchTelemetry.shared.recordBackgroundUploadProof(
                    "analysis_notification_scheduled",
                    metadata: "context=\(context.rawValue) clips=\(clipsCount)"
                )
            } catch {
                LaunchTelemetry.shared.recordBackgroundUploadProof(
                    "analysis_notification_schedule_failed",
                    metadata: "context=\(context.rawValue) reason=schedule_error"
                )
            }
        }
    }

    func notifyBackgroundUploadCompleted() {
        Task {
            let center = UNUserNotificationCenter.current()
            let settings = await center.notificationSettings()
            let status = settings.authorizationStatus
            guard status == .authorized || status == .provisional || status == .ephemeral else {
                LaunchTelemetry.shared.recordBackgroundUploadProof(
                    "background_upload_notification_blocked",
                    metadata: "status=\(Self.authorizationProofStatus(status))"
                )
                return
            }

            let content = UNMutableNotificationContent()
            content.title = "Upload finished"
            content.body = "Open HoopClips to continue analysis and get Review ready."
            content.sound = .default
            content.threadIdentifier = "hoopclips-analysis"
            content.categoryIdentifier = "background-upload-complete"
            content.userInfo = [
                "source": "HoopClips",
                "event": "background_upload_completed",
                "completionContext": CompletionContext.backgroundUploadResume.rawValue
            ]

            let request = UNNotificationRequest(
                identifier: "background-upload-complete-\(UUID().uuidString)",
                content: content,
                trigger: nil
            )
            do {
                try await center.add(request)
                LaunchTelemetry.shared.recordBackgroundUploadProof("background_upload_notification_scheduled")
            } catch {
                LaunchTelemetry.shared.recordBackgroundUploadProof(
                    "background_upload_notification_schedule_failed",
                    metadata: "reason=schedule_error"
                )
            }
        }
    }

    private static func authorizationProofStatus(_ status: UNAuthorizationStatus) -> String {
        switch status {
        case .notDetermined:
            return "not_determined"
        case .denied:
            return "denied"
        case .authorized:
            return "authorized"
        case .provisional:
            return "provisional"
        case .ephemeral:
            return "ephemeral"
        @unknown default:
            return "unknown"
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
