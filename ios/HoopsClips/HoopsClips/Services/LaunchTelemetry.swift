import Foundation
import os

final class LaunchTelemetry {
    static let shared = LaunchTelemetry(runtimeConfig: .shared)

    private let logger = Logger(subsystem: "atrak.charlie.hoopsclips", category: "launch")
    private let runtimeConfig: AppRuntimeConfig
    private let stabilitySessionID = UUID().uuidString
    private let stabilityDefaultsKey = "hoopsclips.stability.currentSession.v1"
    private let stabilityLastUnexpectedExitKey = "hoopsclips.stability.lastUnexpectedExit.v1"

    init(runtimeConfig: AppRuntimeConfig) {
        self.runtimeConfig = runtimeConfig
    }

    var supportStatusLabel: String {
        runtimeConfig.sentryDSN.isEmpty ? "Logger only" : "DSN staged"
    }

    var latestUnexpectedExitSummary: String? {
        UserDefaults.standard.string(forKey: stabilityLastUnexpectedExitKey)
    }

    func configure() {
        recordPreviousSessionIfNeeded()
        updateStabilitySnapshot(
            lifecycleState: "launching",
            screen: nil,
            checkpoint: "app.launch",
            metadata: "build=\(Self.bundleBuildVersion)"
        )

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

    func recordLifecycleState(_ state: String, screen: String?) {
        let safeState = Self.redactedAIEditFailureReason(state)
        let safeScreen = Self.redactedAIEditFailureReason(screen)
        updateStabilitySnapshot(
            lifecycleState: safeState,
            screen: safeScreen == "none" ? nil : safeScreen,
            checkpoint: "lifecycle.\(safeState)",
            metadata: nil
        )
        logger.notice(
            "Lifecycle state=\(safeState, privacy: .public) screen=\(safeScreen, privacy: .public)"
        )
    }

    func recordMemoryWarning(screen: String?) {
        let safeScreen = Self.redactedAIEditFailureReason(screen)
        var snapshot = currentStabilitySnapshot()
        snapshot.memoryWarningCount += 1
        snapshot.lastMemoryWarningAt = Date()
        snapshot.lastUpdatedAt = Date()
        snapshot.lastCheckpoint = "memory.warning"
        snapshot.screen = safeScreen == "none" ? snapshot.screen : safeScreen
        saveStabilitySnapshot(snapshot)
        let checkpoint = snapshot.lastCheckpoint ?? "none"
        logger.error(
            "Memory warning count=\(snapshot.memoryWarningCount, privacy: .public) screen=\(safeScreen, privacy: .public) checkpoint=\(checkpoint, privacy: .public)"
        )
    }

    func recordStabilityCheckpoint(_ name: String, metadata: String? = nil) {
        let safeName = Self.redactedAIEditFailureReason(name)
        let safeMetadata = Self.redactedAIEditFailureReason(metadata)
        updateStabilitySnapshot(
            lifecycleState: nil,
            screen: nil,
            checkpoint: safeName,
            metadata: safeMetadata == "none" ? nil : safeMetadata
        )
        logger.notice(
            "Stability checkpoint=\(safeName, privacy: .public) metadata=\(safeMetadata, privacy: .public)"
        )
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

    private func recordPreviousSessionIfNeeded() {
        guard let snapshot = loadStabilitySnapshot(),
              snapshot.appVersion == Self.bundleShortVersion,
              snapshot.buildVersion == Self.bundleBuildVersion else {
            return
        }

        let normalTerminalStates = ["background", "terminated"]
        guard !normalTerminalStates.contains(snapshot.lifecycleState) else { return }

        let checkpoint = snapshot.lastCheckpoint ?? "none"
        let screen = snapshot.screen ?? "none"
        let supportSummary = Self.stabilitySupportSummary(
            lifecycleState: snapshot.lifecycleState,
            screen: snapshot.screen,
            checkpoint: snapshot.lastCheckpoint,
            memoryWarningCount: snapshot.memoryWarningCount
        )
        UserDefaults.standard.set(supportSummary, forKey: stabilityLastUnexpectedExitKey)
        logger.error(
            "Previous HoopClips session may have ended unexpectedly; state=\(snapshot.lifecycleState, privacy: .public) screen=\(screen, privacy: .public) checkpoint=\(checkpoint, privacy: .public) memoryWarnings=\(snapshot.memoryWarningCount, privacy: .public)"
        )
    }

    static func stabilitySupportSummary(
        lifecycleState: String,
        screen: String?,
        checkpoint: String?,
        memoryWarningCount: Int
    ) -> String {
        let safeState = redactedAIEditFailureReason(lifecycleState)
        let safeScreen = redactedAIEditFailureReason(screen)
        let safeCheckpoint = redactedAIEditFailureReason(checkpoint)
        return "Previous session may have ended unexpectedly. State: \(safeState). Screen: \(safeScreen). Last step: \(safeCheckpoint). Memory warnings: \(max(0, memoryWarningCount))."
    }

    private func currentStabilitySnapshot() -> StabilitySnapshot {
        loadStabilitySnapshot() ?? StabilitySnapshot(
            sessionID: stabilitySessionID,
            appVersion: Self.bundleShortVersion,
            buildVersion: Self.bundleBuildVersion,
            launchedAt: Date(),
            lastUpdatedAt: Date(),
            lifecycleState: "launching",
            screen: nil,
            lastCheckpoint: nil,
            lastMetadata: nil,
            memoryWarningCount: 0,
            lastMemoryWarningAt: nil
        )
    }

    private func updateStabilitySnapshot(
        lifecycleState: String?,
        screen: String?,
        checkpoint: String?,
        metadata: String?
    ) {
        var snapshot = currentStabilitySnapshot()
        snapshot.sessionID = stabilitySessionID
        snapshot.appVersion = Self.bundleShortVersion
        snapshot.buildVersion = Self.bundleBuildVersion
        snapshot.lastUpdatedAt = Date()
        if let lifecycleState {
            snapshot.lifecycleState = lifecycleState
        }
        if let screen {
            snapshot.screen = screen
        }
        if let checkpoint {
            snapshot.lastCheckpoint = checkpoint
        }
        if let metadata {
            snapshot.lastMetadata = metadata
        }
        saveStabilitySnapshot(snapshot)
    }

    private func loadStabilitySnapshot() -> StabilitySnapshot? {
        guard let data = UserDefaults.standard.data(forKey: stabilityDefaultsKey) else { return nil }
        return try? JSONDecoder().decode(StabilitySnapshot.self, from: data)
    }

    private func saveStabilitySnapshot(_ snapshot: StabilitySnapshot) {
        guard let data = try? JSONEncoder().encode(snapshot) else { return }
        UserDefaults.standard.set(data, forKey: stabilityDefaultsKey)
    }

    private static var bundleShortVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown"
    }

    private static var bundleBuildVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown"
    }
}

private struct StabilitySnapshot: Codable {
    var sessionID: String
    var appVersion: String
    var buildVersion: String
    var launchedAt: Date
    var lastUpdatedAt: Date
    var lifecycleState: String
    var screen: String?
    var lastCheckpoint: String?
    var lastMetadata: String?
    var memoryWarningCount: Int
    var lastMemoryWarningAt: Date?
}
