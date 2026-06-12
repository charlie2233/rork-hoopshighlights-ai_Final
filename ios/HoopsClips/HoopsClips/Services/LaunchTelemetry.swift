import Foundation
import os

final class LaunchTelemetry {
    static let shared = LaunchTelemetry(runtimeConfig: .shared)

    private let logger = Logger(subsystem: "atrak.charlie.hoopsclips", category: "launch")
    private let runtimeConfig: AppRuntimeConfig
    private let stabilitySessionID = UUID().uuidString
    private let stabilityDefaultsKey = "hoopsclips.stability.currentSession.v1"
    private let stabilityLastUnexpectedExitKey = "hoopsclips.stability.lastUnexpectedExit.v1"
    private let latestAIEditProofKey = "hoopsclips.launchProof.latestAIEdit.v1"
    private let latestCrashReportDeliveryKey = "hoopsclips.stability.latestCrashReportDelivery.v1"
    private let pendingCrashReportsKey = "hoopsclips.stability.pendingCrashReports.v1"
    private let crashReportSentFingerprintKey = "hoopsclips.stability.crashReportSentFingerprint.v1"
    private static let crashReportEndpoint = "https://formspree.io/f/mbdzrwbo"
    private static let crashReportRecipientEmail = "charliehan112@gmail.com"
    private static let maxPendingCrashReports = 8

    init(runtimeConfig: AppRuntimeConfig) {
        self.runtimeConfig = runtimeConfig
    }

    var supportStatusLabel: String {
        runtimeConfig.sentryDSN.isEmpty ? "Logger only" : "DSN staged"
    }

    var latestUnexpectedExitSummary: String? {
        UserDefaults.standard.string(forKey: stabilityLastUnexpectedExitKey)
    }

    var latestAIEditProofSummary: String? {
        UserDefaults.standard.string(forKey: latestAIEditProofKey)
    }

    var latestCrashReportDeliverySummary: String? {
        UserDefaults.standard.string(forKey: latestCrashReportDeliveryKey)
    }

    func configure() {
        recordPreviousSessionIfNeeded()
        retryPendingCrashReportsIfNeeded()
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
        let safeName = Self.redactedAIEditFailureReason(name)
        let safeFailureReason = Self.redactedAIEditFailureReason(failureReason)
        recordLatestAIEditProof(
            eventName: safeName,
            editJobID: editJobID,
            renderJobID: renderJobID,
            revisionID: revisionID,
            templateID: templateID
        )
        logger.notice(
            "AIEdit event=\(safeName, privacy: .public) editJobId=\(editJobID ?? "none", privacy: .public) renderJobId=\(renderJobID ?? "none", privacy: .public) revisionId=\(revisionID ?? "none", privacy: .public) templateId=\(templateID ?? "none", privacy: .public) planTier=\(planTier ?? "none", privacy: .public) failureReason=\(safeFailureReason, privacy: .public)"
        )
    }

    @discardableResult
    func sendManualCrashProof(_ proofText: String) async -> Bool {
        let snapshot = currentStabilitySnapshot()
        let queuedAt = Date()
        let payload = CrashBreadcrumbReport(
            subject: "HoopClips manual crash proof",
            recipientEmail: Self.crashReportRecipientEmail,
            replyToEmail: Self.crashReportRecipientEmail,
            source: "HoopClips iOS Settings manual proof",
            message: "Manual smoke/crash proof sent from Settings.",
            proofText: proofText,
            appVersion: Self.bundleShortVersion,
            buildVersion: Self.bundleBuildVersion,
            previousAppVersion: snapshot.appVersion,
            previousBuildVersion: snapshot.buildVersion,
            environmentName: runtimeConfig.environmentName,
            cloudLaunchMode: runtimeConfig.cloudLaunchMode.rawValue,
            sessionID: snapshot.sessionID,
            lifecycleState: Self.redactedAIEditFailureReason(snapshot.lifecycleState),
            screen: Self.redactedAIEditFailureReason(snapshot.screen),
            lastCheckpoint: Self.redactedAIEditFailureReason(snapshot.lastCheckpoint),
            lastMetadata: Self.redactedAIEditFailureReason(snapshot.lastMetadata),
            latestAIEditProof: latestAIEditProofSummary,
            latestUnexpectedExit: latestUnexpectedExitSummary,
            memoryWarningCount: max(0, snapshot.memoryWarningCount),
            launchedAt: Self.isoString(snapshot.launchedAt),
            lastUpdatedAt: Self.isoString(snapshot.lastUpdatedAt),
            queuedAt: Self.isoString(queuedAt),
            privacyNote: "No secrets, presigned URLs, object keys, or local file URLs are included."
        )

        UserDefaults.standard.set(
            "manual queued at \(Self.isoString(queuedAt)) endpoint=formspree",
            forKey: latestCrashReportDeliveryKey
        )
        logger.notice("Manual Formspree crash proof send requested from Settings.")

        do {
            try await Self.postCrashBreadcrumbReport(payload)
            UserDefaults.standard.set(
                "manual sent at \(Self.isoString(Date())) endpoint=formspree",
                forKey: latestCrashReportDeliveryKey
            )
            logger.notice("Manual Formspree crash proof sent.")
            return true
        } catch {
            let safeError = Self.redactedAIEditFailureReason(error.localizedDescription)
            UserDefaults.standard.set(
                "manual failed at \(Self.isoString(Date())) endpoint=formspree error=\(safeError)",
                forKey: latestCrashReportDeliveryKey
            )
            logger.error("Manual Formspree crash proof failed: \(safeError, privacy: .public)")
            queueCrashReportForRetry(payload, reason: safeError)
            return false
        }
    }

    private func recordLatestAIEditProof(
        eventName: String,
        editJobID: String?,
        renderJobID: String?,
        revisionID: String?,
        templateID: String?
    ) {
        guard editJobID?.isEmpty == false
            || renderJobID?.isEmpty == false
            || revisionID?.isEmpty == false
            || templateID?.isEmpty == false else {
            return
        }

        let proof = [
            "event=\(eventName)",
            "editJobId=\(editJobID ?? "none")",
            "renderJobId=\(renderJobID ?? "none")",
            "revisionId=\(revisionID ?? "none")",
            "templateId=\(templateID ?? "none")"
        ].joined(separator: " ")
        UserDefaults.standard.set(proof, forKey: latestAIEditProofKey)
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
            of: #"file://[^\s]+"#,
            with: "[redacted_file_url]",
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
        guard let snapshot = loadStabilitySnapshot() else {
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
        enqueueUnexpectedExitReport(snapshot: snapshot, supportSummary: supportSummary)
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

    private func enqueueUnexpectedExitReport(snapshot: StabilitySnapshot, supportSummary: String) {
        let fingerprint = Self.crashReportFingerprint(for: snapshot)
        guard UserDefaults.standard.string(forKey: crashReportSentFingerprintKey) != fingerprint else {
            return
        }

        let queuedAt = Date()
        let payload = CrashBreadcrumbReport(
            subject: "HoopClips crash breadcrumb",
            recipientEmail: Self.crashReportRecipientEmail,
            replyToEmail: Self.crashReportRecipientEmail,
            source: "HoopClips iOS LaunchTelemetry",
            message: supportSummary,
            proofText: nil,
            appVersion: Self.bundleShortVersion,
            buildVersion: Self.bundleBuildVersion,
            previousAppVersion: snapshot.appVersion,
            previousBuildVersion: snapshot.buildVersion,
            environmentName: runtimeConfig.environmentName,
            cloudLaunchMode: runtimeConfig.cloudLaunchMode.rawValue,
            sessionID: snapshot.sessionID,
            lifecycleState: Self.redactedAIEditFailureReason(snapshot.lifecycleState),
            screen: Self.redactedAIEditFailureReason(snapshot.screen),
            lastCheckpoint: Self.redactedAIEditFailureReason(snapshot.lastCheckpoint),
            lastMetadata: Self.redactedAIEditFailureReason(snapshot.lastMetadata),
            latestAIEditProof: latestAIEditProofSummary,
            latestUnexpectedExit: supportSummary,
            memoryWarningCount: max(0, snapshot.memoryWarningCount),
            launchedAt: Self.isoString(snapshot.launchedAt),
            lastUpdatedAt: Self.isoString(snapshot.lastUpdatedAt),
            queuedAt: Self.isoString(queuedAt),
            privacyNote: "No secrets, presigned URLs, object keys, or local file URLs are included."
        )

        UserDefaults.standard.set(fingerprint, forKey: crashReportSentFingerprintKey)
        UserDefaults.standard.set(
            "queued at \(Self.isoString(queuedAt)) endpoint=formspree",
            forKey: latestCrashReportDeliveryKey
        )
        logger.notice("Queued Formspree crash breadcrumb report for previous unexpected exit.")

        Task.detached(priority: .utility) {
            do {
                try await Self.postCrashBreadcrumbReport(payload)
                UserDefaults.standard.set(
                    "sent at \(Self.isoString(Date())) endpoint=formspree",
                    forKey: "hoopsclips.stability.latestCrashReportDelivery.v1"
                )
            } catch {
                let safeError = Self.redactedAIEditFailureReason(error.localizedDescription)
                Self.queueCrashReportForRetry(
                    payload,
                    reason: safeError,
                    pendingKey: "hoopsclips.stability.pendingCrashReports.v1",
                    deliveryKey: "hoopsclips.stability.latestCrashReportDelivery.v1"
                )
                UserDefaults.standard.set(
                    "failed and queued retry at \(Self.isoString(Date())) endpoint=formspree error=\(safeError)",
                    forKey: "hoopsclips.stability.latestCrashReportDelivery.v1"
                )
            }
        }
    }

    private static func postCrashBreadcrumbReport(_ payload: CrashBreadcrumbReport) async throws {
        guard let url = URL(string: crashReportEndpoint) else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = try JSONEncoder().encode(payload)

        let (_, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              (200..<300).contains(httpResponse.statusCode) else {
            let statusCode = (response as? HTTPURLResponse)?.statusCode ?? -1
            throw NSError(
                domain: "HoopClipsCrashReport",
                code: statusCode,
                userInfo: [NSLocalizedDescriptionKey: "Formspree crash report failed with HTTP \(statusCode)."]
            )
        }
    }

    private func retryPendingCrashReportsIfNeeded() {
        let pendingReports = Self.loadPendingCrashReports(from: pendingCrashReportsKey)
        guard !pendingReports.isEmpty else { return }

        let pendingKey = pendingCrashReportsKey
        let deliveryKey = latestCrashReportDeliveryKey
        UserDefaults.standard.set(
            "retrying \(pendingReports.count) report(s) at \(Self.isoString(Date())) endpoint=formspree",
            forKey: deliveryKey
        )

        Task.detached(priority: .utility) {
            var remainingReports: [CrashBreadcrumbReport] = []
            var sentCount = 0
            var lastError = "none"

            for payload in pendingReports {
                do {
                    try await Self.postCrashBreadcrumbReport(payload)
                    sentCount += 1
                } catch {
                    lastError = Self.redactedAIEditFailureReason(error.localizedDescription)
                    remainingReports.append(payload)
                }
            }

            Self.savePendingCrashReports(remainingReports, to: pendingKey)
            let status: String
            if remainingReports.isEmpty {
                status = "retry sent \(sentCount) report(s) at \(Self.isoString(Date())) endpoint=formspree"
            } else {
                status = "retry partial at \(Self.isoString(Date())) endpoint=formspree sent=\(sentCount) remaining=\(remainingReports.count) error=\(lastError)"
            }
            UserDefaults.standard.set(status, forKey: deliveryKey)
        }
    }

    private func queueCrashReportForRetry(_ payload: CrashBreadcrumbReport, reason: String) {
        Self.queueCrashReportForRetry(
            payload,
            reason: reason,
            pendingKey: pendingCrashReportsKey,
            deliveryKey: latestCrashReportDeliveryKey
        )
    }

    private static func queueCrashReportForRetry(
        _ payload: CrashBreadcrumbReport,
        reason: String,
        pendingKey: String,
        deliveryKey: String
    ) {
        let safeReason = redactedAIEditFailureReason(reason)
        var pendingReports = loadPendingCrashReports(from: pendingKey)
        if !pendingReports.contains(where: { $0.retryFingerprint == payload.retryFingerprint }) {
            pendingReports.append(payload)
        }
        savePendingCrashReports(pendingReports, to: pendingKey)
        UserDefaults.standard.set(
            "queued retry at \(isoString(Date())) endpoint=formspree count=\(min(pendingReports.count, maxPendingCrashReports)) error=\(safeReason)",
            forKey: deliveryKey
        )
    }

    private static func loadPendingCrashReports(from key: String) -> [CrashBreadcrumbReport] {
        guard let data = UserDefaults.standard.data(forKey: key),
              let reports = try? JSONDecoder().decode([CrashBreadcrumbReport].self, from: data) else {
            return []
        }
        return reports
    }

    private static func savePendingCrashReports(_ reports: [CrashBreadcrumbReport], to key: String) {
        let cappedReports = Array(reports.suffix(maxPendingCrashReports))
        guard !cappedReports.isEmpty else {
            UserDefaults.standard.removeObject(forKey: key)
            return
        }
        guard let data = try? JSONEncoder().encode(cappedReports) else { return }
        UserDefaults.standard.set(data, forKey: key)
    }

    private static func crashReportFingerprint(for snapshot: StabilitySnapshot) -> String {
        [
            snapshot.sessionID,
            snapshot.appVersion,
            snapshot.buildVersion,
            isoString(snapshot.lastUpdatedAt),
            snapshot.lifecycleState,
            snapshot.screen ?? "none",
            snapshot.lastCheckpoint ?? "none"
        ].joined(separator: "|")
    }

    private static func isoString(_ date: Date) -> String {
        ISO8601DateFormatter().string(from: date)
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

private struct CrashBreadcrumbReport: Codable, Sendable {
    var subject: String
    var recipientEmail: String
    var replyToEmail: String
    var source: String
    var message: String
    var proofText: String?
    var appVersion: String
    var buildVersion: String
    var previousAppVersion: String
    var previousBuildVersion: String
    var environmentName: String
    var cloudLaunchMode: String
    var sessionID: String
    var lifecycleState: String
    var screen: String
    var lastCheckpoint: String
    var lastMetadata: String
    var latestAIEditProof: String?
    var latestUnexpectedExit: String?
    var memoryWarningCount: Int
    var launchedAt: String
    var lastUpdatedAt: String
    var queuedAt: String
    var privacyNote: String

    var retryFingerprint: String {
        [
            subject,
            source,
            sessionID,
            appVersion,
            buildVersion,
            previousBuildVersion,
            lastUpdatedAt,
            lastCheckpoint,
            proofText.map { String($0.prefix(160)) } ?? "none"
        ].joined(separator: "|")
    }

    enum CodingKeys: String, CodingKey {
        case subject = "_subject"
        case recipientEmail = "email"
        case replyToEmail = "_replyto"
        case source
        case message
        case proofText
        case appVersion
        case buildVersion
        case previousAppVersion
        case previousBuildVersion
        case environmentName
        case cloudLaunchMode
        case sessionID
        case lifecycleState
        case screen
        case lastCheckpoint
        case lastMetadata
        case latestAIEditProof
        case latestUnexpectedExit
        case memoryWarningCount
        case launchedAt
        case lastUpdatedAt
        case queuedAt
        case privacyNote
    }
}
