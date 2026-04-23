import Foundation
import os

final class LaunchTelemetry {
    static let shared = LaunchTelemetry(runtimeConfig: .shared)

    private let logger = Logger(subsystem: "app.rork.hoopshighlights-ai", category: "launch")
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
}
