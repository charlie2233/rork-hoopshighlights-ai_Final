import Foundation
import os

final class LaunchTelemetry {
    static let shared = LaunchTelemetry(runtimeConfig: .shared)

    private let logger = Logger(subsystem: "atrak.charlie.hoopsclips", category: "launch")
    private let runtimeConfig: AppRuntimeConfig

    init(runtimeConfig: AppRuntimeConfig) {
        self.runtimeConfig = runtimeConfig
    }

    var supportStatusLabel: String {
        runtimeConfig.sentryDSN.isEmpty ? "Logger only" : "DSN staged"
    }

    func configure() {
        logger.notice(
            "Launch telemetry ready; cloudLaunchMode=\(self.runtimeConfig.cloudLaunchMode.rawValue, privacy: .public), environment=\(self.runtimeConfig.environmentName, privacy: .public)"
        )

        if !runtimeConfig.sentryDSN.isEmpty {
            logger.notice("External crash reporter DSN configured but not linked in this build; using unified logging only.")
        }
    }

    func recordConfigurationIssue(_ message: String) {
        logger.error("\(message, privacy: .public)")
    }

    func recordSupportTrace(requestID: String?, traceID: String?, source: String) {
        let requestValue = requestID?.isEmpty == false ? requestID! : "none"
        let traceValue = traceID?.isEmpty == false ? traceID! : "none"
        logger.notice(
            "Support trace source=\(source, privacy: .public) requestId=\(requestValue, privacy: .public) traceId=\(traceValue, privacy: .public)"
        )
    }

    func recordAIEditEvent(
        _ name: String,
        editJobID: String? = nil,
        renderJobID: String? = nil,
        revisionID: String? = nil,
        templateID: String? = nil,
        planTier: String? = nil,
        failureReason: String? = nil
    ) {
        let safeFailureReason = Self.redactedAIEditFailureReason(failureReason)
        logger.notice(
            "AIEdit event=\(name, privacy: .public) editJobId=\(editJobID ?? "none", privacy: .public) renderJobId=\(renderJobID ?? "none", privacy: .public) revisionId=\(revisionID ?? "none", privacy: .public) templateId=\(templateID ?? "none", privacy: .public) planTier=\(planTier ?? "none", privacy: .public) failureReason=\(safeFailureReason, privacy: .public)"
        )
    }

    static func redactedAIEditFailureReason(_ rawValue: String?) -> String {
        guard var value = rawValue?.trimmingCharacters(in: .whitespacesAndNewlines), !value.isEmpty else {
            return "none"
        }

        value = value.replacingOccurrences(
            of: #"https?://[^\s]+"#,
            with: "[redacted_url]",
            options: .regularExpression
        )
        value = value.replacingOccurrences(
            of: #"\b(?:uploads|edits)/[A-Za-z0-9._/\-]+"#,
            with: "[redacted_object_key]",
            options: .regularExpression
        )
        value = value.replacingOccurrences(
            of: #"(?i)\b(?:X-Amz-[A-Za-z0-9_-]+|AWSAccessKeyId|Signature|Credential|Policy|Expires)=\S+"#,
            with: "[redacted_query]",
            options: .regularExpression
        )

        if value.count > 280 {
            value = String(value.prefix(280)) + "..."
        }
        return value
    }
}
