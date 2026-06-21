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
    private let latestBackgroundUploadProofKey = "hoopsclips.launchProof.latestBackgroundUpload.v1"
    private let recentBackgroundUploadProofTrailKey = "hoopsclips.launchProof.backgroundUploadTrail.v1"
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

    var latestBackgroundUploadProofSummary: String? {
        UserDefaults.standard.string(forKey: latestBackgroundUploadProofKey)
    }

    var recentBackgroundUploadProofTrailSummary: String? {
        UserDefaults.standard.string(forKey: recentBackgroundUploadProofTrailKey)
    }

    func resetBackgroundUploadProofTrail(reason: String) {
        let safeReason = Self.redactedAIEditFailureReason(reason)
        UserDefaults.standard.removeObject(forKey: recentBackgroundUploadProofTrailKey)
        logger.notice("Background upload proof trail reset reason=\(safeReason, privacy: .public)")
    }

    var latestCrashReportDeliverySummary: String? {
        UserDefaults.standard.string(forKey: latestCrashReportDeliveryKey)
    }

    var pendingCrashReportRetryCount: Int {
        Self.loadPendingCrashReports(from: pendingCrashReportsKey).count
    }

    var pendingCrashReportRetrySummary: String {
        let count = pendingCrashReportRetryCount
        guard count > 0 else { return "none" }
        return "pending_retry_count=\(count) endpoint=formspree"
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
            metadata: "build=\(Self.bundleBuildVersion)"
        )
        logger.notice(
            "Lifecycle state=\(safeState, privacy: .public) screen=\(safeScreen, privacy: .public)"
        )
    }

    func recordRuntimeState(screen: String?, metadata: String) {
        let safeScreen = Self.redactedAIEditFailureReason(screen)
        let safeMetadata = Self.redactedAIEditFailureReason(metadata)
        updateStabilitySnapshot(
            lifecycleState: nil,
            screen: safeScreen == "none" ? nil : safeScreen,
            checkpoint: "runtime.state",
            metadata: safeMetadata == "none" ? "build=\(Self.bundleBuildVersion)" : safeMetadata
        )
        logger.notice(
            "Runtime state screen=\(safeScreen, privacy: .public) metadata=\(safeMetadata, privacy: .public)"
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

    func recordBackgroundUploadProof(_ event: String, metadata: String? = nil) {
        let safeEvent = Self.redactedAIEditFailureReason(event)
        let safeMetadata = Self.redactedAIEditFailureReason(metadata)
        let generatedAt = Self.isoString(Date())
        let summary = [
            "event=\(safeEvent)",
            "at=\(generatedAt)",
            "mode=ios_background_urlsession",
            safeMetadata == "none" ? nil : "metadata=\(safeMetadata)"
        ]
            .compactMap { $0 }
            .joined(separator: " ")
        UserDefaults.standard.set(summary, forKey: latestBackgroundUploadProofKey)
        let existingTrail = UserDefaults.standard
            .string(forKey: recentBackgroundUploadProofTrailKey)?
            .components(separatedBy: " || ")
            .filter { !$0.isEmpty } ?? []
        let recentTrail = Array((existingTrail + [summary]).suffix(6))
        UserDefaults.standard.set(recentTrail.joined(separator: " || "), forKey: recentBackgroundUploadProofTrailKey)
        recordStabilityCheckpoint("upload.background.\(safeEvent)", metadata: safeMetadata == "none" ? nil : safeMetadata)
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
        let diagnosis = Self.crashDiagnosis(for: snapshot)
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
            diagnosisTitle: diagnosis.title,
            likelyCause: diagnosis.likelyCause,
            suggestedFix: diagnosis.suggestedFix,
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

    @discardableResult
    func sendAutomaticUploadStallProof(_ proofText: String) async -> Bool {
        let snapshot = currentStabilitySnapshot()
        let queuedAt = Date()
        let diagnosis = CrashDiagnosis(
            title: "Cloud upload appears stuck",
            likelyCause: "The upload monitor saw no meaningful byte progress for several minutes while video upload or import was active.",
            suggestedFix: "Use the upload proof fields to compare uploaded bytes, speed, elapsed time, and seconds since progress. If bytes stopped moving, show retry/cancel and preserve the current project so the user can try again."
        )
        let payload = CrashBreadcrumbReport(
            subject: "HoopClips stuck upload proof",
            recipientEmail: Self.crashReportRecipientEmail,
            replyToEmail: Self.crashReportRecipientEmail,
            source: "HoopClips iOS Upload Monitor",
            message: "Automatic upload-stall proof sent after upload progress stopped moving.",
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
            diagnosisTitle: diagnosis.title,
            likelyCause: diagnosis.likelyCause,
            suggestedFix: diagnosis.suggestedFix,
            memoryWarningCount: max(0, snapshot.memoryWarningCount),
            launchedAt: Self.isoString(snapshot.launchedAt),
            lastUpdatedAt: Self.isoString(snapshot.lastUpdatedAt),
            queuedAt: Self.isoString(queuedAt),
            privacyNote: "No secrets, presigned URLs, object keys, or local file URLs are included."
        )

        UserDefaults.standard.set(
            "upload-stall queued at \(Self.isoString(queuedAt)) endpoint=formspree",
            forKey: latestCrashReportDeliveryKey
        )
        logger.notice("Automatic Formspree upload-stall proof requested.")

        do {
            try await Self.postCrashBreadcrumbReport(payload)
            UserDefaults.standard.set(
                "upload-stall sent at \(Self.isoString(Date())) endpoint=formspree",
                forKey: latestCrashReportDeliveryKey
            )
            logger.notice("Automatic Formspree upload-stall proof sent.")
            return true
        } catch {
            let safeError = Self.redactedAIEditFailureReason(error.localizedDescription)
            UserDefaults.standard.set(
                "upload-stall failed at \(Self.isoString(Date())) endpoint=formspree error=\(safeError)",
                forKey: latestCrashReportDeliveryKey
            )
            logger.error("Automatic Formspree upload-stall proof failed: \(safeError, privacy: .public)")
            queueCrashReportForRetry(payload, reason: safeError)
            return false
        }
    }

    @discardableResult
    func sendManualUploadProof(_ proofText: String) async -> Bool {
        let snapshot = currentStabilitySnapshot()
        let queuedAt = Date()
        let diagnosis = CrashDiagnosis(
            title: "Manual background upload smoke proof",
            likelyCause: "A tester manually sent background upload proof from the Player upload card.",
            suggestedFix: "Review upload progress, latest background upload proof, resume manifest summary, and cloud routing flags to confirm whether the upload survived app switching or needs retry/resume work."
        )
        let payload = CrashBreadcrumbReport(
            subject: "HoopClips upload smoke proof",
            recipientEmail: Self.crashReportRecipientEmail,
            replyToEmail: Self.crashReportRecipientEmail,
            source: "HoopClips iOS Player upload card",
            message: "Manual background upload proof sent from Player.",
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
            diagnosisTitle: diagnosis.title,
            likelyCause: diagnosis.likelyCause,
            suggestedFix: diagnosis.suggestedFix,
            memoryWarningCount: max(0, snapshot.memoryWarningCount),
            launchedAt: Self.isoString(snapshot.launchedAt),
            lastUpdatedAt: Self.isoString(snapshot.lastUpdatedAt),
            queuedAt: Self.isoString(queuedAt),
            privacyNote: "No secrets, presigned URLs, object keys, or local file URLs are included."
        )

        UserDefaults.standard.set(
            "upload-proof queued at \(Self.isoString(queuedAt)) endpoint=formspree",
            forKey: latestCrashReportDeliveryKey
        )
        logger.notice("Manual Formspree upload proof requested from Player.")

        do {
            try await Self.postCrashBreadcrumbReport(payload)
            UserDefaults.standard.set(
                "upload-proof sent at \(Self.isoString(Date())) endpoint=formspree",
                forKey: latestCrashReportDeliveryKey
            )
            logger.notice("Manual Formspree upload proof sent.")
            return true
        } catch {
            let safeError = Self.redactedAIEditFailureReason(error.localizedDescription)
            UserDefaults.standard.set(
                "upload-proof failed at \(Self.isoString(Date())) endpoint=formspree error=\(safeError)",
                forKey: latestCrashReportDeliveryKey
            )
            logger.error("Manual Formspree upload proof failed: \(safeError, privacy: .public)")
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
        if Self.isBenignPreviousSessionEnd(snapshot) {
            UserDefaults.standard.removeObject(forKey: stabilityLastUnexpectedExitKey)
            logger.notice(
                "Previous HoopClips session ended after a benign guard checkpoint; state=\(snapshot.lifecycleState, privacy: .public) screen=\(screen, privacy: .public) checkpoint=\(checkpoint, privacy: .public)"
            )
            return
        }

        let supportSummary = Self.stabilitySupportSummary(
            lifecycleState: snapshot.lifecycleState,
            screen: snapshot.screen,
            checkpoint: snapshot.lastCheckpoint,
            memoryWarningCount: snapshot.memoryWarningCount
        )
        let diagnosis = Self.crashDiagnosis(for: snapshot)
        let diagnosedSummary = [
            supportSummary,
            "Likely cause: \(diagnosis.likelyCause)",
            "Suggested fix: \(diagnosis.suggestedFix)"
        ].joined(separator: " ")
        UserDefaults.standard.set(diagnosedSummary, forKey: stabilityLastUnexpectedExitKey)
        logger.error(
            "Previous HoopClips session may have ended unexpectedly; state=\(snapshot.lifecycleState, privacy: .public) screen=\(screen, privacy: .public) checkpoint=\(checkpoint, privacy: .public) memoryWarnings=\(snapshot.memoryWarningCount, privacy: .public)"
        )
        enqueueUnexpectedExitReport(snapshot: snapshot, supportSummary: diagnosedSummary, diagnosis: diagnosis)
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

    private func enqueueUnexpectedExitReport(
        snapshot: StabilitySnapshot,
        supportSummary: String,
        diagnosis: CrashDiagnosis
    ) {
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
            diagnosisTitle: diagnosis.title,
            likelyCause: diagnosis.likelyCause,
            suggestedFix: diagnosis.suggestedFix,
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

        Task(priority: .utility) {
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

        Task(priority: .utility) {
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

    private static func isBenignPreviousSessionEnd(_ snapshot: StabilitySnapshot) -> Bool {
        let checkpoint = snapshot.lastCheckpoint ?? "none"
        let metadata = (snapshot.lastMetadata ?? "").lowercased()
        if checkpoint == "tab.switch.blocked",
           metadata.contains("to=review") || metadata.contains("reason=") {
            return true
        }
        return false
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

    private static func crashDiagnosis(for snapshot: StabilitySnapshot) -> CrashDiagnosis {
        let checkpoint = snapshot.lastCheckpoint ?? "none"
        let metadata = snapshot.lastMetadata ?? ""
        let normalizedMetadata = metadata.lowercased()

        if checkpoint == "tab.switch.requested", metadata.contains("to=review") {
            return CrashDiagnosis(
                title: "Review tab crash during tab switch",
                likelyCause: "The restored project reached Review after the tab request, but Review did not become active. This usually means saved clips or source video metadata looked present but were unsafe for Review rendering.",
                suggestedFix: "Block Review unless the current project has a source URL, positive finite source duration, and at least one clip with finite timing and scores. If blocked, return to Player and show repair/reset options."
            )
        }

        if checkpoint == "tab.switch.blocked", metadata.contains("to=review") || metadata.contains("reason=") {
            return CrashDiagnosis(
                title: "Review tab prevented unsafe project",
                likelyCause: "HoopClips detected that the current project did not have review-safe clips before opening Review.",
                suggestedFix: "Keep the user on Player, rerun analysis, or repair the saved project before opening Review."
            )
        }

        if checkpoint == "runtime.state",
           normalizedMetadata.contains("importing=true") || normalizedMetadata.contains("upload") {
            return CrashDiagnosis(
                title: "Unexpected exit during cloud upload/import",
                likelyCause: "The app was importing or uploading video when the previous session ended. The most useful proof is the runtime metadata: upload percent, uploaded size, speed, ETA, and whether analysis had started.",
                suggestedFix: "Use the runtime metadata to decide whether the upload stalled, the app was killed while active, or the cloud analysis handoff failed. Keep upload progress resumable and show retry/cancel if transfer stops moving."
            )
        }

        if checkpoint == "runtime.state",
           normalizedMetadata.contains("analyzing=true") {
            return CrashDiagnosis(
                title: "Unexpected exit during cloud analysis",
                likelyCause: "Cloud analysis was active when the previous session ended. The app should keep Review in a waiting state instead of showing rerun while analysis is still in progress.",
                suggestedFix: "Restore the in-progress analysis state, keep Review on the analyzing/wait screen, and use the recorded progress/status metadata to identify the last completed analysis stage."
            )
        }

        if checkpoint == "review.preview.bad_window" {
            return CrashDiagnosis(
                title: "Review preview bad clip window",
                likelyCause: "A clip had non-finite, empty, or out-of-bounds playback timing.",
                suggestedFix: "Clamp or discard the clip before Review playback and ask the user to rerun analysis if all clips are invalid."
            )
        }

        return CrashDiagnosis(
            title: "Unexpected app exit",
            likelyCause: "The previous session stopped before a normal background or termination lifecycle event.",
            suggestedFix: "Use the last checkpoint and metadata to identify the screen/action, then add a guard or recovery path around that transition."
        )
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

private struct CrashDiagnosis: Sendable {
    var title: String
    var likelyCause: String
    var suggestedFix: String
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
    var diagnosisTitle: String
    var likelyCause: String
    var suggestedFix: String
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
        case diagnosisTitle
        case likelyCause
        case suggestedFix
        case memoryWarningCount
        case launchedAt
        case lastUpdatedAt
        case queuedAt
        case privacyNote
    }
}
