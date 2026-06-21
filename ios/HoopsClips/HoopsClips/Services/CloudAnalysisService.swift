import Foundation
import UniformTypeIdentifiers

private let cloudUploadResumeManifestDefaultsKey = "hoopsclips.cloudUpload.resumeManifest.v1"
private let cloudUploadSingleSourcePrefix = "single-source-"
private let cloudUploadServerPlanDefaultsKey = "hoopsclips.cloudUpload.serverPlan.v1"
private let cloudUploadProgressSummaryDefaultsKey = "hoopsclips.cloudUpload.progressSummary.v1"
private let cloudUploadCapabilitySummaryDefaultsKey = "hoopsclips.cloudUpload.capabilitySummary.v1"
private let cloudUploadDeployedCapabilitySummaryDefaultsKey = "hoopsclips.cloudUpload.deployedCapabilitySummary.v1"

nonisolated enum CloudUploadResumeOutcome: Sendable {
    case pendingUpload
    case analysis(CloudAnalysisResult)
    case teamScan(PreparedCloudAnalysisJob)
}

private enum CloudUploadResumePurpose: String, Codable, Sendable {
    case analysis
    case teamScan
}

struct CloudAnalysisService {
    typealias HandoffHandler = @MainActor @Sendable (_ jobID: String, _ sourceObjectKey: String?) -> Void

    private static let analysisPollTimeoutSeconds: UInt64 = 8 * 60
    private static let maxPollDelaySeconds = 5
    private static let maxVisibleProgressStageCharacters = 72
    private static let maxVisibleBackendMessageCharacters = 96
    private static let fallbackBackgroundSessionPrefix = "atrak.charlie.hoopsclips.cloud-upload"
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init(session: URLSession = .shared) {
        self.session = session
        self.decoder = JSONDecoder()
        self.decoder.dateDecodingStrategy = .iso8601
        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
    }

    func hasPendingBackgroundUpload() async -> Bool {
        await CloudUploadResumeStore.shared.pendingManifest() != nil
    }

    func fetchAnalysisCapabilities() async throws -> CloudAnalysisCapabilitiesResponse {
        guard let baseURL = configuredBaseURL() else {
            throw CloudAnalysisError.notConfigured
        }

        let request = URLRequest(url: baseURL.appending(path: "v1/analysis/capabilities"))
        let (data, response) = try await session.data(for: request)
        let capabilities = try decodeResponse(
            data: data,
            response: response,
            successType: CloudAnalysisCapabilitiesResponse.self
        )
        Self.recordDeployedUploadCapabilities(capabilities)
        return capabilities
    }

    func cancelPendingBackgroundUpload(reason: String) async {
        guard let manifest = await CloudUploadResumeStore.shared.pendingManifest() else {
            Self.recordCancelledUploadProofState(
                reason: reason,
                sessions: 0,
                completedParts: 0,
                partCount: 0,
                hadManifest: false
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "background_upload_cancel_cleanup",
                metadata: "reason=\(reason) sessions=0 hadManifest=false"
            )
            return
        }

        let sessionIdentifiers = manifest.activeSessionIdentifiers
        for identifier in sessionIdentifiers {
            let session = URLSession(
                configuration: uploadSessionConfiguration(backgroundIdentifier: identifier)
            )
            session.getAllTasks { tasks in
                tasks.forEach { $0.cancel() }
                session.invalidateAndCancel()
                LaunchTelemetry.shared.recordBackgroundUploadProof(
                    "background_upload_session_cancelled",
                    metadata: "taskCount=\(tasks.count)"
                )
            }
        }

        await CloudUploadResumeStore.shared.clearAnyManifest(reason: reason)
        Self.recordCancelledUploadProofState(
            reason: reason,
            sessions: sessionIdentifiers.count,
            completedParts: manifest.completedParts.count,
            partCount: manifest.partCount,
            hadManifest: true
        )
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "background_upload_cancel_cleanup",
            metadata: "reason=\(reason) sessions=\(sessionIdentifiers.count) hadManifest=true"
        )
    }

    static func pendingBackgroundUploadManifestSummary() -> String {
        guard let manifest = CloudUploadResumeStore.loadPersistedManifestSnapshot() else {
            return "none"
        }

        let sourceAvailability = FileManager.default.fileExists(atPath: manifest.sourceFilePath) ? "available" : "missing"
        return [
            "pending=true",
            "purpose=\(manifest.purpose.rawValue)",
            "completed=\(manifest.completedParts.count)/\(manifest.partCount)",
            "sessions=\(manifest.activeSessionIdentifiers.count)",
            "source=\(sourceAvailability)",
            "updatedAt=\(ISO8601DateFormatter().string(from: manifest.updatedAt))"
        ].joined(separator: " ")
    }

    static func latestServerUploadPlanSummary() -> String {
        UserDefaults.standard.string(forKey: cloudUploadServerPlanDefaultsKey) ?? "none"
    }

    static func latestUploadProgressSummary() -> String {
        UserDefaults.standard.string(forKey: cloudUploadProgressSummaryDefaultsKey) ?? "none"
    }

    static func recordRelaunchedUploadProgressSummary(
        event: String,
        statusCode: Int? = nil,
        reason: String? = nil
    ) {
        var fields = [
            "at=\(ISO8601DateFormatter().string(from: Date()))",
            "stage=relaunched_upload",
            "event=\(safeUploadPlanComponent(event))"
        ]
        if let statusCode {
            fields.append("status=\(statusCode)")
        }
        if let reason {
            fields.append("reason=\(safeUploadPlanComponent(reason))")
        }
        fields.append("privacy=no_urls_no_object_keys_no_local_file_paths")
        UserDefaults.standard.set(fields.joined(separator: " "), forKey: cloudUploadProgressSummaryDefaultsKey)
    }

    static func latestServerUploadCapabilitySummary() -> String {
        UserDefaults.standard.string(forKey: cloudUploadCapabilitySummaryDefaultsKey) ?? "none"
    }

    static func latestDeployedUploadCapabilitySummary() -> String {
        UserDefaults.standard.string(forKey: cloudUploadDeployedCapabilitySummaryDefaultsKey) ?? "none"
    }

    static func safeProgressStage(_ stage: String, fallback: String) -> String {
        safeVisibleMessage(stage, fallback: fallback, maxCharacters: maxVisibleProgressStageCharacters)
    }

    static func safeBackendMessage(_ message: String, fallback: String) -> String {
        safeVisibleMessage(message, fallback: fallback, maxCharacters: maxVisibleBackendMessageCharacters)
    }

    private static func uploadProgressStage(fileSizeBytes: Int64, teamScan: Bool = false) -> String {
        let megabytes = Double(max(fileSizeBytes, 0)) / 1_048_576.0
        if megabytes >= 350 {
            return teamScan ? "Uploading large video for team scan" : "Uploading large video to cloud"
        }
        return teamScan ? "Uploading video for team scan" : "Uploading video to cloud"
    }

    private static func uploadProgressMessage(
        stage: String,
        fraction: Double,
        elapsedSeconds: TimeInterval,
        uploadedBytes: Int64? = nil,
        totalBytes: Int64? = nil,
        transferContext: String? = nil,
        stalled: Bool = false
    ) -> String {
        let boundedFraction = min(max(fraction, 0), 1)
        let percent = Int((boundedFraction * 100).rounded(.down))
        var parts = ["\(stage) \(percent)%"]

        if let transferContext, !transferContext.isEmpty {
            parts.append(transferContext)
        }

        if let uploadedBytes, let totalBytes, totalBytes > 0 {
            parts.append(formatUploadByteProgress(uploadedBytes: uploadedBytes, totalBytes: totalBytes))

            let speed = elapsedSeconds > 0 ? Double(max(uploadedBytes, 0)) / elapsedSeconds : 0
            if speed > 0 {
                parts.append(formatUploadSpeed(bytesPerSecond: speed))
                if boundedFraction < 0.995 {
                    parts.append("about \(formatUploadRemainingTime(uploadedBytes: uploadedBytes, totalBytes: totalBytes, bytesPerSecond: speed)) left")
                }
            }
        }

        parts.append(formatUploadElapsedTime(elapsedSeconds))

        if stalled {
            parts.append("paused or slow connection, will resume")
        }

        return parts.joined(separator: " · ")
    }

    private static func formatUploadElapsedTime(_ elapsedSeconds: TimeInterval) -> String {
        let totalSeconds = max(0, Int(elapsedSeconds.rounded(.down)))
        let hours = totalSeconds / 3600
        let minutes = (totalSeconds % 3600) / 60
        let seconds = totalSeconds % 60

        if hours > 0 {
            return "\(hours)h \(minutes)m"
        }
        if minutes > 0 {
            return "\(minutes)m \(seconds)s"
        }
        return "\(seconds)s"
    }

    private static func formatUploadByteProgress(uploadedBytes: Int64, totalBytes: Int64) -> String {
        let uploadedMB = Double(max(uploadedBytes, 0)) / 1_048_576.0
        let totalMB = Double(max(totalBytes, 1)) / 1_048_576.0
        if totalMB >= 100 {
            return "\(Int(uploadedMB.rounded()))/\(Int(totalMB.rounded())) MB"
        }
        return String(format: "%.1f/%.1f MB", uploadedMB, totalMB)
    }

    private static func formatUploadSpeed(bytesPerSecond: Double) -> String {
        let mbPerSecond = max(bytesPerSecond, 0) / 1_048_576.0
        if mbPerSecond >= 1 {
            return String(format: "%.1f MB/s", mbPerSecond)
        }

        let kbPerSecond = max(bytesPerSecond, 0) / 1_024.0
        return "\(Int(kbPerSecond.rounded())) KB/s"
    }

    private static func formatUploadRemainingTime(uploadedBytes: Int64, totalBytes: Int64, bytesPerSecond: Double) -> String {
        guard bytesPerSecond > 0 else {
            return "calculating"
        }

        let remainingBytes = max(totalBytes - uploadedBytes, 0)
        let remainingSeconds = Double(remainingBytes) / bytesPerSecond
        return formatUploadElapsedTime(remainingSeconds)
    }

    private static func uploadStallProofText(stage: String, snapshot: CloudUploadProgressSnapshot) -> String {
        var fields = [
            "source=CloudAnalysisService.uploadMonitor",
            "stage=\(stage.split(whereSeparator: \.isWhitespace).joined(separator: "_"))",
            "percent=\(Int((min(max(snapshot.fraction, 0), 1) * 100).rounded(.down)))",
            "elapsed=\(formatUploadElapsedTime(snapshot.elapsedSeconds))",
            "secondsSinceProgress=\(Int(snapshot.secondsSinceProgress.rounded(.down)))"
        ]

        if let uploadedBytes = snapshot.uploadedBytes, let totalBytes = snapshot.totalBytes, totalBytes > 0 {
            fields.append("bytes=\(formatUploadByteProgress(uploadedBytes: uploadedBytes, totalBytes: totalBytes).replacingOccurrences(of: " ", with: "_"))")
            let speed = snapshot.elapsedSeconds > 0 ? Double(max(uploadedBytes, 0)) / snapshot.elapsedSeconds : 0
            if speed > 0 {
                fields.append("speed=\(formatUploadSpeed(bytesPerSecond: speed).replacingOccurrences(of: " ", with: "_"))")
                fields.append("eta=\(formatUploadRemainingTime(uploadedBytes: uploadedBytes, totalBytes: totalBytes, bytesPerSecond: speed).replacingOccurrences(of: " ", with: "_"))")
            }
        }

        fields.append("privacy=no_urls_no_object_keys_no_local_file_paths")
        return fields.joined(separator: " ")
    }

    private static func recordLatestUploadProgressSummary(
        stage: String,
        snapshot: CloudUploadProgressSnapshot,
        transferContext: String?,
        stalled: Bool
    ) {
        var fields = [
            "at=\(ISO8601DateFormatter().string(from: Date()))",
            "stage=\(safeUploadPlanComponent(stage))",
            "percent=\(Int((min(max(snapshot.fraction, 0), 1) * 100).rounded(.down)))",
            "elapsed=\(formatUploadElapsedTime(snapshot.elapsedSeconds).replacingOccurrences(of: " ", with: "_"))",
            "secondsSinceProgress=\(Int(snapshot.secondsSinceProgress.rounded(.down)))",
            "stalled=\(stalled)"
        ]

        if let transferContext, !transferContext.isEmpty {
            fields.append("context=\(safeUploadPlanComponent(transferContext))")
        }

        if let uploadedBytes = snapshot.uploadedBytes, let totalBytes = snapshot.totalBytes, totalBytes > 0 {
            fields.append("bytes=\(formatUploadByteProgress(uploadedBytes: uploadedBytes, totalBytes: totalBytes).replacingOccurrences(of: " ", with: "_"))")
            let speed = snapshot.elapsedSeconds > 0 ? Double(max(uploadedBytes, 0)) / snapshot.elapsedSeconds : 0
            if speed > 0 {
                fields.append("speed=\(formatUploadSpeed(bytesPerSecond: speed).replacingOccurrences(of: " ", with: "_"))")
                fields.append("eta=\(formatUploadRemainingTime(uploadedBytes: uploadedBytes, totalBytes: totalBytes, bytesPerSecond: speed).replacingOccurrences(of: " ", with: "_"))")
            }
        }

        fields.append("privacy=no_urls_no_object_keys_no_local_file_paths")
        UserDefaults.standard.set(fields.joined(separator: " "), forKey: cloudUploadProgressSummaryDefaultsKey)
    }

    private static func recordCancelledUploadProofState(
        reason: String,
        sessions: Int,
        completedParts: Int,
        partCount: Int,
        hadManifest: Bool
    ) {
        let generatedAt = ISO8601DateFormatter().string(from: Date())
        let safeReason = safeUploadPlanComponent(reason)
        let progressSummary = [
            "at=\(generatedAt)",
            "stage=cancelled",
            "reason=\(safeReason)",
            "hadManifest=\(hadManifest)",
            "sessions=\(max(sessions, 0))",
            "completed=\(max(completedParts, 0))/\(max(partCount, 0))",
            "privacy=no_urls_no_object_keys_no_local_file_paths"
        ].joined(separator: " ")
        let serverPlanSummary = [
            "cleared=true",
            "at=\(generatedAt)",
            "reason=\(safeReason)",
            "hadManifest=\(hadManifest)",
            "privacy=no_urls_no_object_keys_no_upload_ids"
        ].joined(separator: " ")
        let capabilitySummary = [
            "cleared=true",
            "at=\(generatedAt)",
            "reason=\(safeReason)",
            "hadManifest=\(hadManifest)",
            "privacy=no_urls_no_object_keys_no_upload_ids"
        ].joined(separator: " ")

        UserDefaults.standard.set(progressSummary, forKey: cloudUploadProgressSummaryDefaultsKey)
        UserDefaults.standard.set(serverPlanSummary, forKey: cloudUploadServerPlanDefaultsKey)
        UserDefaults.standard.set(capabilitySummary, forKey: cloudUploadCapabilitySummaryDefaultsKey)
    }

    private static func recordServerUploadPlan(_ job: CreateCloudAnalysisJobResponse) {
        let resumableUpload = job.resumableUpload
        let partCount = max(resumableUpload?.partCount ?? 1, 1)
        let chunkSizeBytes = max(resumableUpload?.chunkSizeBytes ?? 0, 0)
        let chunkSizeMB = chunkSizeBytes > 0
            ? String(format: "%.1f", Double(chunkSizeBytes) / 1_048_576.0)
            : "none"
        let expiresAt = resumableUpload.map { ISO8601DateFormatter().string(from: $0.expiresAt) } ?? "none"
        let summary = [
            "serverChunked=\(partCount > 1)",
            "partCount=\(partCount)",
            "chunkSizeMB=\(chunkSizeMB)",
            "analysisMode=\(safeUploadPlanComponent(job.analysisMode))",
            "uploadMethod=\(safeUploadPlanComponent(job.uploadMethod))",
            "expiresAt=\(expiresAt)",
            "privacy=no_urls_no_object_keys_no_upload_ids"
        ].joined(separator: " ")

        UserDefaults.standard.set(summary, forKey: cloudUploadServerPlanDefaultsKey)
        let capabilitySummary = [
            "resumableAdvertised=\(resumableUpload != nil)",
            "chunkedUploadAdvertised=\(partCount > 1)",
            "partCount=\(partCount)",
            "chunkSizeMB=\(chunkSizeMB)",
            "singleUploadURLPresent=\(!job.uploadUrl.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)",
            "quotaRemainingToday=\(max(job.quotaRemainingToday, 0))",
            "analysisMode=\(safeUploadPlanComponent(job.analysisMode))",
            "privacy=no_urls_no_object_keys_no_upload_ids"
        ].joined(separator: " ")
        UserDefaults.standard.set(capabilitySummary, forKey: cloudUploadCapabilitySummaryDefaultsKey)
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "server_upload_plan_received",
            metadata: "serverChunked=\(partCount > 1) partCount=\(partCount) chunkSizeMB=\(chunkSizeMB)"
        )
    }

    private static func recordDeployedUploadCapabilities(_ capabilities: CloudAnalysisCapabilitiesResponse) {
        let maxFileSizeMB = String(format: "%.0f", Double(max(capabilities.maxFileSizeBytes, 0)) / 1_048_576.0)
        let thresholdMB = String(format: "%.0f", Double(max(capabilities.resumableUploadThresholdBytes, 0)) / 1_048_576.0)
        let summary = [
            "source=worker_capabilities",
            "maxFileSizeMB=\(maxFileSizeMB)",
            "maxDurationSeconds=\(Int(max(capabilities.maxDurationSeconds, 0).rounded(.down)))",
            "supportsResumableUpload=\(capabilities.supportsResumableUpload)",
            "recommendedUploadPreference=\(safeUploadPlanComponent(capabilities.recommendedUploadPreference ?? "unknown"))",
            "resumableThresholdMB=\(thresholdMB)",
            "signedUploadTtlSeconds=\(max(capabilities.signedUploadTtlSeconds, 0))",
            "defaultPollAfterSeconds=\(max(capabilities.defaultPollAfterSeconds, 0))",
            "analysisMode=\(safeUploadPlanComponent(capabilities.analysisMode))",
            "privacy=no_urls_no_object_keys"
        ].joined(separator: " ")
        UserDefaults.standard.set(summary, forKey: cloudUploadDeployedCapabilitySummaryDefaultsKey)
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "server_upload_capabilities_received",
            metadata: "maxFileSizeMB=\(maxFileSizeMB) maxDurationSeconds=\(Int(max(capabilities.maxDurationSeconds, 0).rounded(.down))) resumable=\(capabilities.supportsResumableUpload) recommended=\(safeUploadPlanComponent(capabilities.recommendedUploadPreference ?? "unknown")) thresholdMB=\(thresholdMB)"
        )
    }

    private static func safeUploadPlanComponent(_ value: String) -> String {
        let compact = value
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: "_")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !compact.isEmpty else {
            return "none"
        }
        return String(compact.prefix(48))
    }

    private static func safeVisibleMessage(_ message: String, fallback: String, maxCharacters: Int) -> String {
        let compact = message
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !compact.isEmpty else {
            return fallback
        }

        let normalized = compact.lowercased()
        if normalized.contains("retry") && normalized.contains("timed out") {
            return "Cloud analysis is retrying."
        }
        if normalized.contains("timed out") || normalized.contains("timeout") || normalized.contains("request time") {
            return "Cloud request timed out. Try again."
        }

        let forbiddenMarkers = [
            "thinking",
            "almost there",
            "hang tight",
            "just a moment",
            "please wait",
            "soon",
            "estimate",
            "eta ",
            " eta",
            "eta:",
            "minute",
            "minutes",
            "second",
            "seconds",
            "hour",
            "hours",
            " day",
            "day ",
            " days",
            " week",
            "week ",
            " weeks",
            "tomorrow",
            "http://",
            "https://",
            "presigned",
            "signature",
            "x-amz",
            "x-goog",
            "uploads/",
            "renders/",
            "render_logs/",
            "source object key",
            "sourceobjectkey",
            "object_key",
            "s3://",
            ".r2.cloudflarestorage.com",
            "amazonaws.com",
            "authorization",
            "r2 ",
            "bucket",
            "secret",
            "token",
            "credential",
            "password",
            "private_key",
            "private key",
            "client_secret",
            "client secret",
            "jwt",
            "session_id",
            "session id",
            "cookie",
            "set-cookie",
            "refresh_token",
            "refresh token",
            "id_token",
            "id token",
            "assertion",
            "issuer id",
            "key id",
            "kid=",
            "oauth",
            "grant_type",
            "client_id",
            "client id",
            "csrf",
            "xsrf",
            "nonce",
            "stack trace",
            "traceback",
            "exception",
            "worker ",
            "worker.",
            "upstream",
            "cloudflare",
            "wrangler",
            "durable object",
            "api_key",
            "apikey",
            "access_key",
            "trace_id",
            "trace id",
            "request_id",
            "request id",
            "correlation_id",
            "correlation id"
        ]
        guard !forbiddenMarkers.contains(where: { normalized.contains($0) }) else {
            return fallback
        }

        let genericStage = normalized
            .replacingOccurrences(of: "_", with: " ")
            .replacingOccurrences(of: "-", with: " ")
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: " ")
            .trimmingCharacters(in: .punctuationCharacters)
        let genericStageMarkers = [
            "created",
            "queued",
            "queueing",
            "pending",
            "processing",
            "running",
            "started",
            "submitted",
            "working",
            "in progress",
            "loading"
        ]
        guard !genericStageMarkers.contains(genericStage) else {
            return fallback
        }

        return clippedVisibleMessage(compact, maxCharacters: maxCharacters)
    }

    private static func clippedVisibleMessage(_ message: String, maxCharacters: Int) -> String {
        guard maxCharacters > 3, message.count > maxCharacters else {
            return message
        }

        let rawPrefixEnd = message.index(message.startIndex, offsetBy: maxCharacters - 3)
        let rawPrefix = String(message[..<rawPrefixEnd])
        let clippedPrefix = rawPrefix
            .split(separator: " ")
            .dropLast()
            .joined(separator: " ")
        let prefix = clippedPrefix.isEmpty ? rawPrefix.trimmingCharacters(in: .whitespacesAndNewlines) : clippedPrefix
        return "\(prefix)..."
    }

    func analyzeVideo(
        url: URL,
        duration: Double,
        installID: String,
        appVersion: String = "v1.0",
        analysisVersion: String = "v1",
        teamSelection: HighlightTeamSelection? = nil,
        onCloudHandoff: HandoffHandler? = nil,
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async throws -> CloudAnalysisResult {
        guard let baseURL = configuredBaseURL() else {
            throw CloudAnalysisError.notConfigured
        }

        let fileInfo = try fileInfo(for: url)
        progress(0.02, "Preparing cloud analysis")
        let job = try await createJob(
            baseURL: baseURL,
            request: CreateCloudAnalysisJobRequest(
                filename: url.lastPathComponent,
                contentType: fileInfo.contentType,
                fileSizeBytes: fileInfo.fileSizeBytes,
                durationSeconds: duration,
                installId: installID,
                appVersion: appVersion,
                analysisVersion: analysisVersion,
                teamSelection: teamSelection
            )
        )

        let uploadStage = Self.uploadProgressStage(fileSizeBytes: fileInfo.fileSizeBytes)
        progress(0.15, uploadStage)
        try await uploadVideo(
            to: job,
            from: url,
            baseURL: baseURL,
            installID: installID,
            purpose: .analysis,
            stage: uploadStage,
            progressStart: 0.15,
            progressEnd: 0.27,
            progress: progress
        )

        progress(0.28, "Starting cloud clip search")
        _ = try await startJob(baseURL: baseURL, jobID: job.jobId, installID: installID, teamSelection: teamSelection)
        onCloudHandoff?(job.jobId, job.sourceObjectKey)
        await CloudUploadResumeStore.shared.clearJob(jobID: job.jobId, reason: "analysis_started")

        return try await pollJob(
            baseURL: baseURL,
            jobID: job.jobId,
            sourceObjectKey: job.sourceObjectKey,
            initialPollAfterSeconds: job.pollAfterSeconds,
            progress: progress
        )
    }

    func prepareTeamScan(
        url: URL,
        duration: Double,
        installID: String,
        appVersion: String = "v1.0",
        analysisVersion: String = "v1",
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async throws -> PreparedCloudAnalysisJob {
        guard let baseURL = configuredBaseURL() else {
            throw CloudAnalysisError.notConfigured
        }

        let fileInfo = try fileInfo(for: url)
        progress(0.02, "Preparing cloud team scan")
        let job = try await createJob(
            baseURL: baseURL,
            request: CreateCloudAnalysisJobRequest(
                filename: url.lastPathComponent,
                contentType: fileInfo.contentType,
                fileSizeBytes: fileInfo.fileSizeBytes,
                durationSeconds: duration,
                installId: installID,
                appVersion: appVersion,
                analysisVersion: analysisVersion
            )
        )

        let uploadStage = Self.uploadProgressStage(fileSizeBytes: fileInfo.fileSizeBytes, teamScan: true)
        progress(0.14, uploadStage)
        try await uploadVideo(
            to: job,
            from: url,
            baseURL: baseURL,
            installID: installID,
            purpose: .teamScan,
            stage: uploadStage,
            progressStart: 0.14,
            progressEnd: 0.19,
            progress: progress
        )

        progress(0.20, "Scanning jersey colors")
        let scan = try await scanJobTeams(baseURL: baseURL, jobID: job.jobId, installID: installID)
        await CloudUploadResumeStore.shared.clearJob(jobID: job.jobId, reason: "team_scan_started")
        progress(0.24, scan.detectedTeams.isEmpty ? "Team scan unavailable" : "Team choices found")

        return PreparedCloudAnalysisJob(
            sourceURL: url.standardizedFileURL,
            job: job,
            detectedTeams: scan.detectedTeams
        )
    }

    func analyzePreparedVideo(
        _ preparedJob: PreparedCloudAnalysisJob,
        teamSelection: HighlightTeamSelection? = nil,
        installID: String,
        onCloudHandoff: HandoffHandler? = nil,
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async throws -> CloudAnalysisResult {
        guard let baseURL = configuredBaseURL() else {
            throw CloudAnalysisError.notConfigured
        }

        progress(0.28, "Starting cloud clip search")
        _ = try await startJob(
            baseURL: baseURL,
            jobID: preparedJob.job.jobId,
            installID: installID,
            teamSelection: teamSelection
        )
        onCloudHandoff?(preparedJob.job.jobId, preparedJob.job.sourceObjectKey)

        return try await pollJob(
            baseURL: baseURL,
            jobID: preparedJob.job.jobId,
            sourceObjectKey: preparedJob.job.sourceObjectKey,
            initialPollAfterSeconds: preparedJob.job.pollAfterSeconds,
            progress: progress
        )
    }

    func resumeAnalysisJob(
        jobID: String,
        sourceObjectKey: String?,
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async throws -> CloudAnalysisResult {
        guard let baseURL = configuredBaseURL() else {
            throw CloudAnalysisError.notConfigured
        }

        progress(0.45, "Reconnecting to cloud analysis")
        return try await pollJob(
            baseURL: baseURL,
            jobID: jobID,
            sourceObjectKey: sourceObjectKey,
            initialPollAfterSeconds: 1,
            progress: progress
        )
    }

    func resumePendingBackgroundUploadIfNeeded(
        installID: String,
        teamSelection: HighlightTeamSelection? = nil,
        onCloudHandoff: HandoffHandler? = nil,
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async throws -> CloudUploadResumeOutcome? {
        guard var manifest = await CloudUploadResumeStore.shared.pendingManifest() else {
            return nil
        }
        guard manifest.installID == installID else {
            await CloudUploadResumeStore.shared.clearAnyManifest(reason: "install_mismatch")
            LaunchTelemetry.shared.recordBackgroundUploadProof("resume_manifest_install_mismatch")
            return nil
        }
        guard manifest.partCount > 0,
              manifest.chunkSizeBytes > 0,
              manifest.totalFileSizeBytes > 0 else {
            await CloudUploadResumeStore.shared.clearAnyManifest(reason: "invalid_manifest")
            LaunchTelemetry.shared.recordBackgroundUploadProof("resume_manifest_invalid")
            return nil
        }
        guard let baseURL = configuredBaseURL() else {
            throw CloudAnalysisError.notConfigured
        }

        let sourceURL = URL(fileURLWithPath: manifest.sourceFilePath)
        guard FileManager.default.fileExists(atPath: sourceURL.path) else {
            await CloudUploadResumeStore.shared.clear(jobID: manifest.jobID, uploadID: manifest.uploadID)
            LaunchTelemetry.shared.recordBackgroundUploadProof("resume_manifest_source_missing")
            return nil
        }

        let stage = manifest.purpose == .teamScan ? "Resuming team scan upload" : "Resuming cloud upload"
        let progressStart = manifest.purpose == .teamScan ? 0.14 : 0.15
        let progressEnd = manifest.purpose == .teamScan ? 0.20 : 0.28
        let tracker = CloudUploadProgressTracker()
        let reportUploadProgress: @Sendable (_ snapshot: CloudUploadProgressSnapshot, _ stalled: Bool, _ transferContext: String?) -> Void = { snapshot, stalled, transferContext in
            let boundedFraction = min(max(snapshot.fraction, 0), 1)
            let progressValue = progressStart + ((progressEnd - progressStart) * boundedFraction)
            Task { @MainActor in
                progress(
                    progressValue,
                    Self.uploadProgressMessage(
                        stage: stage,
                        fraction: boundedFraction,
                        elapsedSeconds: snapshot.elapsedSeconds,
                        uploadedBytes: snapshot.uploadedBytes,
                        totalBytes: snapshot.totalBytes,
                        transferContext: transferContext,
                        stalled: stalled
                    )
                )
            }
        }

        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_foreground_resume_started",
            metadata: "purpose=\(manifest.purpose.rawValue) completed=\(manifest.completedParts.count) partCount=\(manifest.partCount)"
        )
        if !manifest.activeSessionIdentifiers.isEmpty,
           manifest.completedParts.count < manifest.partCount {
            let sessionInspection = await inspectBackgroundUploadSessions(manifest.activeSessionIdentifiers)
            let completedBytes = Self.completedUploadBytes(
                completedParts: manifest.completedParts,
                chunkSizeBytes: manifest.chunkSizeBytes,
                totalFileSizeBytes: manifest.totalFileSizeBytes
            )
            await tracker.update(uploadedBytes: completedBytes, totalBytes: manifest.totalFileSizeBytes)
            let snapshot = await tracker.snapshot()
            if sessionInspection.taskCount > 0 {
                reportUploadProgress(snapshot, true, "background upload still running")
                Self.recordLatestUploadProgressSummary(
                    stage: stage,
                    snapshot: snapshot,
                    transferContext: "background upload still running",
                    stalled: true
                )
                LaunchTelemetry.shared.recordBackgroundUploadProof(
                    "resume_manifest_active_sessions_pending",
                    metadata: "activeSessions=\(manifest.activeSessionIdentifiers.count) taskCount=\(sessionInspection.taskCount) checked=\(sessionInspection.checkedCount) completed=\(manifest.completedParts.count) partCount=\(manifest.partCount)"
                )
                return .pendingUpload
            }

            await CloudUploadResumeStore.shared.clearActiveSessions(
                jobID: manifest.jobID,
                uploadID: manifest.uploadID,
                sessionIdentifiers: sessionInspection.checkedIdentifiers,
                reason: "stale_no_tasks"
            )
            manifest.activeSessionIdentifiers.removeAll { sessionInspection.checkedIdentifiers.contains($0) }
            reportUploadProgress(snapshot, true, "reconnecting saved upload")
            Self.recordLatestUploadProgressSummary(
                stage: stage,
                snapshot: snapshot,
                transferContext: "reconnecting saved upload",
                stalled: true
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "resume_manifest_active_sessions_stale",
                metadata: "cleared=\(sessionInspection.checkedIdentifiers.count) completed=\(manifest.completedParts.count) partCount=\(manifest.partCount)"
            )
        }
        if manifest.uploadID.hasPrefix(cloudUploadSingleSourcePrefix) {
            guard !manifest.completedParts.isEmpty else {
                LaunchTelemetry.shared.recordBackgroundUploadProof("resume_manifest_source_still_uploading")
                return .pendingUpload
            }
            await tracker.update(uploadedBytes: manifest.totalFileSizeBytes, totalBytes: manifest.totalFileSizeBytes)
            let snapshot = await tracker.snapshot()
            reportUploadProgress(snapshot, false, "source upload saved")
        } else {
            try await resumeUploadManifest(
                manifest,
                sourceURL: sourceURL,
                baseURL: baseURL,
                tracker: tracker,
                reportUploadProgress: reportUploadProgress
            )
        }

        switch manifest.purpose {
        case .analysis:
            progress(0.28, "Starting cloud clip search")
            _ = try await startJob(baseURL: baseURL, jobID: manifest.jobID, installID: installID, teamSelection: teamSelection)
            onCloudHandoff?(manifest.jobID, manifest.sourceObjectKey)
            await CloudUploadResumeStore.shared.clearJob(jobID: manifest.jobID, reason: "resumed_analysis_started")
            let result = try await pollJob(
                baseURL: baseURL,
                jobID: manifest.jobID,
                sourceObjectKey: manifest.sourceObjectKey,
                initialPollAfterSeconds: manifest.pollAfterSeconds,
                progress: progress
            )
            return .analysis(result)
        case .teamScan:
            progress(0.20, "Scanning jersey colors")
            let scan = try await scanJobTeams(baseURL: baseURL, jobID: manifest.jobID, installID: installID)
            await CloudUploadResumeStore.shared.clearJob(jobID: manifest.jobID, reason: "resumed_team_scan_started")
            progress(0.24, scan.detectedTeams.isEmpty ? "Team scan unavailable" : "Team choices found")
            let job = CreateCloudAnalysisJobResponse(
                jobId: manifest.jobID,
                uploadUrl: "",
                uploadMethod: "PUT",
                uploadHeaders: [:],
                expiresAt: Date(),
                pollAfterSeconds: manifest.pollAfterSeconds,
                quotaRemainingToday: 0,
                analysisMode: "cloud",
                sourceObjectKey: manifest.sourceObjectKey,
                resultObjectKey: manifest.resultObjectKey
            )
            return .teamScan(PreparedCloudAnalysisJob(sourceURL: sourceURL.standardizedFileURL, job: job, detectedTeams: scan.detectedTeams))
        }
    }

    private func configuredBaseURL() -> URL? {
        guard AppConstants.cloudAnalysisEnabled else { return nil }
        guard !AppConstants.cloudAnalysisBaseURL.isEmpty else { return nil }
        return URL(string: AppConstants.cloudAnalysisBaseURL)
    }

    private func fileInfo(for url: URL) throws -> (fileSizeBytes: Int64, contentType: String) {
        let values = try url.resourceValues(forKeys: [.fileSizeKey, .contentTypeKey])
        guard let fileSize = values.fileSize else {
            throw CloudAnalysisError.invalidVideo
        }
        let contentType = values.contentType?.preferredMIMEType
            ?? inferredContentType(for: url)
        return (Int64(fileSize), contentType)
    }

    private func inferredContentType(for url: URL) -> String {
        switch url.pathExtension.lowercased() {
        case "mov":
            return "video/quicktime"
        case "mp4":
            return "video/mp4"
        case "m4v":
            return "video/x-m4v"
        default:
            return "application/octet-stream"
        }
    }

    private func createJob(
        baseURL: URL,
        request body: CreateCloudAnalysisJobRequest
    ) async throws -> CreateCloudAnalysisJobResponse {
        var request = URLRequest(url: baseURL.appending(path: "v1/analysis/jobs"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(
            data: data,
            response: response,
            successType: CreateCloudAnalysisJobResponse.self
        )
    }

    private func uploadVideo(
        to job: CreateCloudAnalysisJobResponse,
        from url: URL,
        baseURL: URL,
        installID: String,
        purpose: CloudUploadResumePurpose,
        stage: String,
        progressStart: Double,
        progressEnd: Double,
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async throws {
        let tracker = CloudUploadProgressTracker()
        let reportUploadProgress: @Sendable (_ snapshot: CloudUploadProgressSnapshot, _ stalled: Bool, _ transferContext: String?) -> Void = { snapshot, stalled, transferContext in
            let fraction = snapshot.fraction
            let boundedFraction = min(max(fraction, 0), 1)
            let progressValue = progressStart + ((progressEnd - progressStart) * boundedFraction)
            Task { @MainActor in
                let message = Self.uploadProgressMessage(
                    stage: stage,
                    fraction: boundedFraction,
                    elapsedSeconds: snapshot.elapsedSeconds,
                    uploadedBytes: snapshot.uploadedBytes,
                    totalBytes: snapshot.totalBytes,
                    transferContext: transferContext,
                    stalled: stalled
                )
                progress(progressValue, message)
            }
        }
        let delegate = CloudUploadProgressDelegate(
            onProgress: { uploadedBytes, totalBytes in
                Task {
                    await tracker.update(uploadedBytes: uploadedBytes, totalBytes: totalBytes)
                    let snapshot = await tracker.snapshot()
                    reportUploadProgress(snapshot, false, nil)
                }
            },
            onWaitingForConnectivity: {
                Task {
                    let snapshot = await tracker.snapshot()
                    reportUploadProgress(snapshot, true, nil)
                    Self.recordLatestUploadProgressSummary(
                        stage: stage,
                        snapshot: snapshot,
                        transferContext: nil,
                        stalled: true
                    )
                    LaunchTelemetry.shared.recordBackgroundUploadProof(
                        "upload_waiting_for_connectivity",
                        metadata: "kind=source"
                    )
                }
            }
        )
        let uploadMonitorTask = Task {
            while !Task.isCancelled {
                do {
                    try await Task.sleep(nanoseconds: 10 * 1_000_000_000)
                } catch {
                    return
                }

                let snapshot = await tracker.snapshot()
                let stalled = snapshot.secondsSinceProgress >= 60 && snapshot.fraction < 0.99
                reportUploadProgress(snapshot, stalled, nil)
                Self.recordLatestUploadProgressSummary(
                    stage: stage,
                    snapshot: snapshot,
                    transferContext: nil,
                    stalled: stalled
                )
                if snapshot.secondsSinceProgress >= 180,
                   snapshot.fraction < 0.99,
                   await tracker.markStallProofSentIfNeeded() {
                    let proofText = await MainActor.run {
                        Self.uploadStallProofText(stage: stage, snapshot: snapshot)
                    }
                    Task(priority: .utility) {
                        await LaunchTelemetry.shared.sendAutomaticUploadStallProof(proofText)
                    }
                }
            }
        }
        let uploadPartCount = job.resumableUpload?.partCount ?? 1
        LaunchTelemetry.shared.resetBackgroundUploadProofTrail(reason: "fresh_upload_started")
        Self.recordServerUploadPlan(job)
        defer {
            uploadMonitorTask.cancel()
        }
        Self.prepareFileForBackgroundUpload(url, context: "source_file")

        if let resumableUpload = job.resumableUpload, resumableUpload.partCount > 1 {
            let initialSnapshot = await tracker.snapshot()
            Self.recordLatestUploadProgressSummary(
                stage: stage,
                snapshot: initialSnapshot,
                transferContext: "chunked upload starting",
                stalled: false
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "chunked_upload_selected",
                metadata: "partCount=\(resumableUpload.partCount) chunkSizeBytes=\(resumableUpload.chunkSizeBytes)"
            )
            try await uploadVideoInChunks(
                job: job,
                resumableUpload: resumableUpload,
                from: url,
                baseURL: baseURL,
                installID: installID,
                purpose: purpose,
                totalFileSizeBytes: FileManager.default.fileExists(atPath: url.path) ? (try fileInfo(for: url).fileSizeBytes) : 0,
                tracker: tracker,
                reportUploadProgress: reportUploadProgress
            )
            return
        }

        let sourceUploadID = Self.singleSourceUploadID(jobID: job.jobId)
        let sourceSessionIdentifier = Self.backgroundUploadSessionIdentifier(jobID: job.jobId)
        let fileSizeBytes = (try? fileInfo(for: url).fileSizeBytes) ?? 1
        _ = await CloudUploadResumeStore.shared.begin(
            jobID: job.jobId,
            installID: installID,
            sourceURL: url.standardizedFileURL,
            uploadID: sourceUploadID,
            sourceObjectKey: job.sourceObjectKey,
            resultObjectKey: job.resultObjectKey,
            pollAfterSeconds: job.pollAfterSeconds,
            purpose: purpose,
            chunkSizeBytes: Int(max(fileSizeBytes, 1)),
            partCount: 1,
            totalFileSizeBytes: max(fileSizeBytes, 1)
        )
        await CloudUploadResumeStore.shared.recordSession(
            jobID: job.jobId,
            uploadID: sourceUploadID,
            sessionIdentifier: sourceSessionIdentifier
        )
        let initialSnapshot = await tracker.snapshot()
        Self.recordLatestUploadProgressSummary(
            stage: stage,
            snapshot: initialSnapshot,
            transferContext: "source upload starting",
            stalled: false
        )
        let uploadSession = URLSession(
            configuration: uploadSessionConfiguration(
                backgroundIdentifier: sourceSessionIdentifier
            ),
            delegate: delegate,
            delegateQueue: nil
        )
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "source_session_started",
            metadata: "kind=source chunked=false partCount=\(uploadPartCount)"
        )
        defer {
            uploadSession.finishTasksAndInvalidate()
        }

        do {
        guard let uploadURL = URL(string: job.uploadUrl),
              uploadURL.scheme?.isEmpty == false else {
            throw CloudAnalysisError.invalidResponse
        }
        var request = URLRequest(url: uploadURL)
        request.httpMethod = job.uploadMethod
        for (header, value) in job.uploadHeaders {
            request.setValue(value, forHTTPHeaderField: header)
        }

        let response = try await delegate.upload(request: request, fromFile: url, using: uploadSession)
        let finalSnapshot = await tracker.snapshot()
        Self.recordLatestUploadProgressSummary(
            stage: stage,
            snapshot: finalSnapshot,
            transferContext: "source upload complete",
            stalled: false
        )
        await MainActor.run {
            progress(
                progressEnd,
                Self.uploadProgressMessage(
                    stage: stage,
                    fraction: 1,
                    elapsedSeconds: finalSnapshot.elapsedSeconds,
                    uploadedBytes: finalSnapshot.uploadedBytes,
                    totalBytes: finalSnapshot.totalBytes
                )
            )
        }

        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw CloudAnalysisError.uploadFailed
        }
        _ = await CloudUploadResumeStore.shared.recordCompletedPart(
            jobID: job.jobId,
            uploadID: sourceUploadID,
            partNumber: 1,
            etag: "source-upload-complete"
        )
        await CloudUploadResumeStore.shared.clearActiveSession(
            jobID: job.jobId,
            uploadID: sourceUploadID,
            sessionIdentifier: sourceSessionIdentifier
        )
        } catch {
            await CloudUploadResumeStore.shared.clearActiveSession(
                jobID: job.jobId,
                uploadID: sourceUploadID,
                sessionIdentifier: sourceSessionIdentifier
            )
            let failedSnapshot = await tracker.snapshot()
            Self.recordLatestUploadProgressSummary(
                stage: stage,
                snapshot: failedSnapshot,
                transferContext: "source upload failed",
                stalled: true
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "source_upload_failed",
                metadata: "reason=\(Self.uploadRetryReason(for: error))"
            )
            throw error
        }
    }

    private static func completedUploadBytes(
        completedParts: [CloudMultipartCompletedPart],
        chunkSizeBytes: Int,
        totalFileSizeBytes: Int64
    ) -> Int64 {
        let safeChunkSize = max(Int64(chunkSizeBytes), 1)
        let safeTotal = max(totalFileSizeBytes, 0)
        let completedBytes = completedParts.reduce(Int64(0)) { partial, part in
            let partStart = max(Int64(part.partNumber - 1), 0) * safeChunkSize
            let partEnd = min(Int64(max(part.partNumber, 0)) * safeChunkSize, safeTotal)
            return partial + max(partEnd - partStart, 0)
        }
        return min(completedBytes, safeTotal)
    }

    private struct BackgroundUploadSessionInspection {
        let checkedIdentifiers: [String]
        let taskCount: Int

        var checkedCount: Int {
            checkedIdentifiers.count
        }
    }

    private func inspectBackgroundUploadSessions(_ identifiers: [String]) async -> BackgroundUploadSessionInspection {
        var checkedIdentifiers: [String] = []
        var taskCount = 0

        for identifier in identifiers {
            let tasks = await CloudUploadBackgroundSessionRegistry.shared.inspectTaskCount(for: identifier)
            checkedIdentifiers.append(identifier)
            taskCount += tasks
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "resume_manifest_active_session_checked",
                metadata: "taskCount=\(tasks)"
            )
        }

        return BackgroundUploadSessionInspection(
            checkedIdentifiers: checkedIdentifiers,
            taskCount: taskCount
        )
    }

    private func uploadVideoInChunks(
        job: CreateCloudAnalysisJobResponse,
        resumableUpload: CloudResumableUpload,
        from url: URL,
        baseURL: URL,
        installID: String,
        purpose: CloudUploadResumePurpose,
        totalFileSizeBytes: Int64,
        tracker: CloudUploadProgressTracker,
        reportUploadProgress: @escaping @Sendable (_ snapshot: CloudUploadProgressSnapshot, _ stalled: Bool, _ transferContext: String?) -> Void
    ) async throws {
        let fileHandle = try FileHandle(forReadingFrom: url)
        defer {
            try? fileHandle.close()
        }

        let safeChunkSize = max(resumableUpload.chunkSizeBytes, 5 * 1024 * 1024)
        let totalBytes = max(totalFileSizeBytes, 0)
        var uploadedParts = await CloudUploadResumeStore.shared.begin(
            jobID: job.jobId,
            installID: installID,
            sourceURL: url.standardizedFileURL,
            uploadID: resumableUpload.uploadId,
            sourceObjectKey: job.sourceObjectKey,
            resultObjectKey: job.resultObjectKey,
            pollAfterSeconds: job.pollAfterSeconds,
            purpose: purpose,
            chunkSizeBytes: safeChunkSize,
            partCount: resumableUpload.partCount,
            totalFileSizeBytes: totalBytes
        )
        var completedPartNumbers = Set(uploadedParts.map(\.partNumber))

        for partNumber in 1...resumableUpload.partCount {
            try Task.checkCancellation()
            let offset = UInt64(partNumber - 1) * UInt64(safeChunkSize)
            if completedPartNumbers.contains(partNumber) {
                await tracker.update(uploadedBytes: min(Int64(offset) + Int64(safeChunkSize), totalBytes), totalBytes: totalBytes)
                let snapshot = await tracker.snapshot()
                reportUploadProgress(snapshot, false, "chunk \(partNumber)/\(resumableUpload.partCount) saved")
                continue
            }
            try fileHandle.seek(toOffset: offset)
            guard let chunk = try fileHandle.read(upToCount: safeChunkSize), !chunk.isEmpty else {
                break
            }

            let partTarget = try await createMultipartPart(
                baseURL: baseURL,
                jobID: job.jobId,
                installID: installID,
                uploadID: resumableUpload.uploadId,
                partNumber: partNumber
            )
            let etag = try await uploadMultipartChunk(
                partTarget,
                chunk: chunk,
                alreadyUploadedBytes: min(Int64(offset), totalBytes),
                totalBytes: totalBytes,
                uploadID: resumableUpload.uploadId,
                partCount: resumableUpload.partCount,
                tracker: tracker,
                reportUploadProgress: reportUploadProgress
            )
            uploadedParts = await CloudUploadResumeStore.shared.recordCompletedPart(
                jobID: job.jobId,
                uploadID: resumableUpload.uploadId,
                partNumber: partNumber,
                etag: etag
            )
            completedPartNumbers.insert(partNumber)
        }

        guard uploadedParts.count == resumableUpload.partCount else {
            throw CloudAnalysisError.uploadFailed
        }

        try await completeMultipartUpload(
            baseURL: baseURL,
            jobID: job.jobId,
            installID: installID,
            uploadID: resumableUpload.uploadId,
            parts: uploadedParts
        )
        await tracker.update(uploadedBytes: totalBytes, totalBytes: totalBytes)
        let finalSnapshot = await tracker.snapshot()
        reportUploadProgress(finalSnapshot, false, "chunks complete")
        Self.recordLatestUploadProgressSummary(
            stage: "Uploading video chunks",
            snapshot: finalSnapshot,
            transferContext: "chunks complete",
            stalled: false
        )
    }

    private func createMultipartPart(
        baseURL: URL,
        jobID: String,
        installID: String,
        uploadID: String,
        partNumber: Int
    ) async throws -> CloudMultipartPartResponse {
        var request = URLRequest(url: baseURL.appending(path: "v1/analysis/uploads/multipart/part"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(
            CloudMultipartPartRequest(
                jobId: jobID,
                installId: installID,
                uploadId: uploadID,
                partNumber: partNumber
            )
        )

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(
            data: data,
            response: response,
            successType: CloudMultipartPartResponse.self
        )
    }

    private func resumeUploadManifest(
        _ manifest: CloudUploadResumeManifest,
        sourceURL: URL,
        baseURL: URL,
        tracker: CloudUploadProgressTracker,
        reportUploadProgress: @escaping @Sendable (_ snapshot: CloudUploadProgressSnapshot, _ stalled: Bool, _ transferContext: String?) -> Void
    ) async throws {
        let fileHandle = try FileHandle(forReadingFrom: sourceURL)
        defer {
            try? fileHandle.close()
        }

        var uploadedParts = manifest.completedParts.sorted { $0.partNumber < $1.partNumber }
        var completedPartNumbers = Set(uploadedParts.map(\.partNumber))

        for partNumber in 1...manifest.partCount {
            try Task.checkCancellation()
            let offset = UInt64(partNumber - 1) * UInt64(manifest.chunkSizeBytes)
            if completedPartNumbers.contains(partNumber) {
                await tracker.update(
                    uploadedBytes: min(Int64(offset) + Int64(manifest.chunkSizeBytes), manifest.totalFileSizeBytes),
                    totalBytes: manifest.totalFileSizeBytes
                )
                let snapshot = await tracker.snapshot()
                reportUploadProgress(snapshot, false, "chunk \(partNumber)/\(manifest.partCount) saved")
                Self.recordLatestUploadProgressSummary(
                    stage: "Resuming cloud upload",
                    snapshot: snapshot,
                    transferContext: "chunk \(partNumber)/\(manifest.partCount) saved",
                    stalled: false
                )
                continue
            }

            try fileHandle.seek(toOffset: offset)
            guard let chunk = try fileHandle.read(upToCount: manifest.chunkSizeBytes), !chunk.isEmpty else {
                break
            }

            let partTarget = try await createMultipartPart(
                baseURL: baseURL,
                jobID: manifest.jobID,
                installID: manifest.installID,
                uploadID: manifest.uploadID,
                partNumber: partNumber
            )
            let etag = try await uploadMultipartChunk(
                partTarget,
                chunk: chunk,
                alreadyUploadedBytes: min(Int64(offset), manifest.totalFileSizeBytes),
                totalBytes: manifest.totalFileSizeBytes,
                uploadID: manifest.uploadID,
                partCount: manifest.partCount,
                tracker: tracker,
                reportUploadProgress: reportUploadProgress
            )
            uploadedParts = await CloudUploadResumeStore.shared.recordCompletedPart(
                jobID: manifest.jobID,
                uploadID: manifest.uploadID,
                partNumber: partNumber,
                etag: etag
            )
            completedPartNumbers.insert(partNumber)
        }

        guard uploadedParts.count == manifest.partCount else {
            throw CloudAnalysisError.uploadFailed
        }

        try await completeMultipartUpload(
            baseURL: baseURL,
            jobID: manifest.jobID,
            installID: manifest.installID,
            uploadID: manifest.uploadID,
            parts: uploadedParts
        )
        await tracker.update(uploadedBytes: manifest.totalFileSizeBytes, totalBytes: manifest.totalFileSizeBytes)
        let finalSnapshot = await tracker.snapshot()
        reportUploadProgress(finalSnapshot, false, "resumed chunks complete")
        Self.recordLatestUploadProgressSummary(
            stage: "Resuming cloud upload",
            snapshot: finalSnapshot,
            transferContext: "resumed chunks complete",
            stalled: false
        )
    }

    private func uploadMultipartChunk(
        _ partTarget: CloudMultipartPartResponse,
        chunk: Data,
        alreadyUploadedBytes: Int64,
        totalBytes: Int64,
        uploadID: String,
        partCount: Int,
        tracker: CloudUploadProgressTracker,
        reportUploadProgress: @escaping @Sendable (_ snapshot: CloudUploadProgressSnapshot, _ stalled: Bool, _ transferContext: String?) -> Void
    ) async throws -> String {
        guard let uploadURL = URL(string: partTarget.uploadUrl) else {
            throw CloudAnalysisError.invalidResponse
        }

        var lastError: Error?
        for attempt in 0..<3 {
            let attemptNumber = attempt + 1
            let transferContext = "chunk \(partTarget.partNumber)/\(partCount) try \(attemptNumber)"
            let backgroundIdentifier = Self.backgroundUploadSessionIdentifier(
                jobID: partTarget.jobId,
                partNumber: partTarget.partNumber,
                attempt: attemptNumber
            )
            do {
                var request = URLRequest(url: uploadURL)
                request.httpMethod = partTarget.uploadMethod
                for (header, value) in partTarget.uploadHeaders {
                    request.setValue(value, forHTTPHeaderField: header)
                }

                let delegate = CloudUploadProgressDelegate(
                    onProgress: { sentBytes, _ in
                        Task {
                            await tracker.update(uploadedBytes: alreadyUploadedBytes + sentBytes, totalBytes: totalBytes)
                            let snapshot = await tracker.snapshot()
                            reportUploadProgress(snapshot, false, transferContext)
                        }
                    },
                    onWaitingForConnectivity: {
                        Task {
                            let snapshot = await tracker.snapshot()
                            reportUploadProgress(snapshot, true, transferContext)
                            Self.recordLatestUploadProgressSummary(
                                stage: "Uploading video chunk",
                                snapshot: snapshot,
                                transferContext: transferContext,
                                stalled: true
                            )
                            LaunchTelemetry.shared.recordBackgroundUploadProof(
                                "upload_waiting_for_connectivity",
                                metadata: "kind=chunk partNumber=\(partTarget.partNumber) partCount=\(partCount) attempt=\(attempt + 1)"
                            )
                        }
                    }
                )
                let chunkFileURL = try CloudUploadChunkFileStore.writeChunk(chunk, jobID: partTarget.jobId, partNumber: partTarget.partNumber)
                Self.prepareFileForBackgroundUpload(chunkFileURL, context: "chunk_\(partTarget.partNumber)")
                defer {
                    try? FileManager.default.removeItem(at: chunkFileURL)
                }

                await CloudUploadResumeStore.shared.recordSession(
                    jobID: partTarget.jobId,
                    uploadID: uploadID,
                    sessionIdentifier: backgroundIdentifier
                )

                let uploadSession = URLSession(
                    configuration: uploadSessionConfiguration(
                        backgroundIdentifier: backgroundIdentifier
                    ),
                    delegate: delegate,
                    delegateQueue: nil
                )
                LaunchTelemetry.shared.recordBackgroundUploadProof(
                    "chunk_session_started",
                    metadata: "kind=chunk partNumber=\(partTarget.partNumber) partCount=\(partCount) attempt=\(attemptNumber)"
                )
                defer {
                    uploadSession.finishTasksAndInvalidate()
                }

                let response = try await delegate.upload(request: request, fromFile: chunkFileURL, using: uploadSession)
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                    throw CloudAnalysisError.uploadFailed
                }
                guard let etag = Self.headerValue("ETag", from: http), !etag.isEmpty else {
                    throw CloudAnalysisError.invalidResponse
                }
                await tracker.update(uploadedBytes: alreadyUploadedBytes + Int64(chunk.count), totalBytes: totalBytes)
                let snapshot = await tracker.snapshot()
                reportUploadProgress(snapshot, false, transferContext)
                Self.recordLatestUploadProgressSummary(
                    stage: "Uploading video chunk",
                    snapshot: snapshot,
                    transferContext: transferContext,
                    stalled: false
                )
                await CloudUploadResumeStore.shared.clearActiveSession(
                    jobID: partTarget.jobId,
                    uploadID: uploadID,
                    sessionIdentifier: backgroundIdentifier
                )
                return etag
            } catch {
                lastError = error
                let retrying = attempt < 2
                let retryReason = Self.uploadRetryReason(for: error)
                LaunchTelemetry.shared.recordBackgroundUploadProof(
                    "chunk_upload_attempt_failed",
                    metadata: "kind=chunk partNumber=\(partTarget.partNumber) partCount=\(partCount) attempt=\(attemptNumber) retrying=\(retrying) reason=\(retryReason)"
                )
                await CloudUploadResumeStore.shared.clearActiveSession(
                    jobID: partTarget.jobId,
                    uploadID: uploadID,
                    sessionIdentifier: backgroundIdentifier
                )
                let snapshot = await tracker.snapshot()
                reportUploadProgress(
                    snapshot,
                    true,
                    retrying
                        ? "chunk \(partTarget.partNumber)/\(partCount) retrying after try \(attemptNumber)"
                        : "chunk \(partTarget.partNumber)/\(partCount) failed after try \(attemptNumber)"
                )
                Self.recordLatestUploadProgressSummary(
                    stage: "Uploading video chunk",
                    snapshot: snapshot,
                    transferContext: retrying
                        ? "chunk \(partTarget.partNumber)/\(partCount) retrying after try \(attemptNumber)"
                        : "chunk \(partTarget.partNumber)/\(partCount) failed after try \(attemptNumber)",
                    stalled: true
                )
                try await Task.sleep(nanoseconds: 700_000_000)
            }
        }

        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "chunk_upload_failed",
            metadata: "kind=chunk partNumber=\(partTarget.partNumber) partCount=\(partCount) attempts=3 reason=\(Self.uploadRetryReason(for: lastError))"
        )
        throw lastError ?? CloudAnalysisError.uploadFailed
    }

    private static func prepareFileForBackgroundUpload(_ url: URL, context: String) {
        do {
            try FileManager.default.setAttributes(
                [FileAttributeKey.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication],
                ofItemAtPath: url.path
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "background_upload_file_protection_ready",
                metadata: "context=\(safeUploadPlanComponent(context))"
            )
        } catch {
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "background_upload_file_protection_unavailable",
                metadata: "context=\(safeUploadPlanComponent(context)) reason=\(uploadRetryReason(for: error))"
            )
        }
    }

    private static func uploadRetryReason(for error: Error?) -> String {
        guard let error else {
            return "unknown"
        }
        if error.isTaskCancellation {
            return "cancelled"
        }
        if let urlError = error as? URLError {
            return "url_error_\(urlError.code.rawValue)"
        }
        if error is CloudAnalysisError {
            return "cloud_analysis_error"
        }
        return String(describing: type(of: error))
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: "_")
    }

    private func completeMultipartUpload(
        baseURL: URL,
        jobID: String,
        installID: String,
        uploadID: String,
        parts: [CloudMultipartCompletedPart]
    ) async throws {
        var request = URLRequest(url: baseURL.appending(path: "v1/analysis/uploads/multipart/complete"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(
            CloudMultipartCompleteRequest(
                jobId: jobID,
                installId: installID,
                uploadId: uploadID,
                parts: parts
            )
        )

        let (data, response) = try await session.data(for: request)
        _ = try decodeResponse(
            data: data,
            response: response,
            successType: CloudAnalysisJobResponse.self
        )
    }

    private static func headerValue(_ name: String, from response: HTTPURLResponse) -> String? {
        for (key, value) in response.allHeaderFields {
            if String(describing: key).caseInsensitiveCompare(name) == .orderedSame {
                return String(describing: value)
            }
        }
        return nil
    }

    private static func backgroundUploadSessionIdentifier(jobID: String, partNumber: Int? = nil, attempt: Int? = nil) -> String {
        let baseIdentifier = Bundle.main.bundleIdentifier ?? fallbackBackgroundSessionPrefix
        var components = [baseIdentifier, "cloud-upload", sanitizedSessionComponent(jobID)]
        if let partNumber {
            components.append("part-\(partNumber)")
        } else {
            components.append("source")
        }
        if let attempt {
            components.append("try-\(attempt)")
        }
        return components.joined(separator: ".")
    }

    private static func singleSourceUploadID(jobID: String) -> String {
        "\(cloudUploadSingleSourcePrefix)\(sanitizedSessionComponent(jobID))"
    }

    private static func sanitizedSessionComponent(_ value: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_"))
        let filtered = value.map { character -> Character in
            character.unicodeScalars.allSatisfy { allowed.contains($0) } ? character : "-"
        }
        let result = String(filtered).trimmingCharacters(in: CharacterSet(charactersIn: "-_"))
        return result.isEmpty ? UUID().uuidString : result
    }

    private func uploadSessionConfiguration(backgroundIdentifier: String? = nil) -> URLSessionConfiguration {
        let configuration: URLSessionConfiguration
        if let backgroundIdentifier {
            configuration = URLSessionConfiguration.background(withIdentifier: backgroundIdentifier)
            configuration.applyHoopsCloudUploadPolicy(isBackgroundTransfer: true)
        } else {
            configuration = URLSessionConfiguration.default
            configuration.applyHoopsCloudUploadPolicy(isBackgroundTransfer: false)
        }
        return configuration
    }

    private func startJob(
        baseURL: URL,
        jobID: String,
        installID: String,
        teamSelection: HighlightTeamSelection? = nil
    ) async throws -> StartCloudAnalysisJobResponse {
        var request = URLRequest(url: baseURL.appending(path: "v1/analysis/jobs/\(jobID)/start"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(StartCloudAnalysisJobRequest(installId: installID, teamSelection: teamSelection))

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(
            data: data,
            response: response,
            successType: StartCloudAnalysisJobResponse.self
        )
    }

    private func scanJobTeams(
        baseURL: URL,
        jobID: String,
        installID: String
    ) async throws -> ScanCloudAnalysisTeamsResponse {
        var request = URLRequest(url: baseURL.appending(path: "v1/analysis/jobs/\(jobID)/team-scan"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(ScanCloudAnalysisTeamsRequest(installId: installID))

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(
            data: data,
            response: response,
            successType: ScanCloudAnalysisTeamsResponse.self
        )
    }

    private func pollJob(
        baseURL: URL,
        jobID: String,
        sourceObjectKey: String?,
        initialPollAfterSeconds: Int,
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async throws -> CloudAnalysisResult {
        let timeoutNanos: UInt64 = Self.analysisPollTimeoutSeconds * 1_000_000_000
        let deadline = DispatchTime.now().uptimeNanoseconds + timeoutNanos
        var pollDelay = max(1, initialPollAfterSeconds)

        while DispatchTime.now().uptimeNanoseconds < deadline {
            try await Task.sleep(nanoseconds: UInt64(pollDelay) * 1_000_000_000)

            let request = URLRequest(url: baseURL.appending(path: "v1/analysis/jobs/\(jobID)"))
            let (data, response) = try await session.data(for: request)
            let job: CloudAnalysisJobResponse = try decodeResponse(
                data: data,
                response: response,
                successType: CloudAnalysisJobResponse.self
            )

            switch CloudAnalysisJobState(rawValue: job.status) {
            case .succeeded:
                progress(0.96, "Finalizing clips")
                guard let results = job.results else {
                    throw CloudAnalysisError.invalidResponse
                }
                return results.withJobMetadata(analysisJobId: job.jobId, sourceObjectKey: job.sourceObjectKey ?? sourceObjectKey)
            case .failed:
                throw CloudAnalysisError.backend(
                    code: job.errorCode ?? "analysis_failed",
                    message: Self.safeBackendMessage(job.errorMessage ?? "", fallback: "Cloud analysis failed. Try again.")
                )
            case .expired:
                throw CloudAnalysisError.backend(
                    code: "expired",
                    message: "Analysis took too long before completion."
                )
            case .created, .queued:
                progress(
                    min(max(job.progress, 0.0), 0.55),
                    Self.safeProgressStage(job.stage, fallback: "Waiting for cloud analysis")
                )
            case .processing:
                progress(
                    max(0.55, min(job.progress, 0.92)),
                    Self.safeProgressStage(job.stage, fallback: "Analyzing frames in cloud")
                )
            case .none:
                throw CloudAnalysisError.invalidResponse
            }

            pollDelay = min(pollDelay + 1, Self.maxPollDelaySeconds)
        }

        throw CloudAnalysisError.timedOut
    }

    private func decodeResponse<T: Decodable>(
        data: Data,
        response: URLResponse,
        successType: T.Type
    ) throws -> T {
        guard let http = response as? HTTPURLResponse else {
            throw CloudAnalysisError.invalidResponse
        }

        guard (200..<300).contains(http.statusCode) else {
            let apiError = try? decoder.decode(CloudAnalysisAPIError.self, from: data)
            if http.statusCode == 429 {
                throw CloudAnalysisError.quotaExceeded(apiError?.quotaRemainingToday)
            }
            throw CloudAnalysisError.backend(
                code: apiError?.errorCode ?? "http_\(http.statusCode)",
                message: Self.safeBackendMessage(apiError?.errorMessage ?? "", fallback: "Analysis request failed.")
            )
        }

        do {
            return try decoder.decode(successType, from: data)
        } catch {
            throw CloudAnalysisError.invalidResponse
        }
    }
}

private enum CloudUploadChunkFileStore {
    static func writeChunk(_ data: Data, jobID: String, partNumber: Int) throws -> URL {
        let directory = try chunkDirectory()
        let filename = "hoops-upload-\(sanitizedComponent(jobID))-part-\(partNumber)-\(UUID().uuidString).tmp"
        let url = directory.appendingPathComponent(filename)
        try data.write(to: url, options: .atomic)
        return url
    }

    static func clearChunks(jobID: String) {
        guard let directory = try? chunkDirectory() else { return }
        let prefix = "hoops-upload-\(sanitizedComponent(jobID))-part-"
        guard let urls = try? FileManager.default.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: nil
        ) else {
            return
        }

        for url in urls where url.lastPathComponent.hasPrefix(prefix) {
            try? FileManager.default.removeItem(at: url)
        }
    }

    private static func chunkDirectory() throws -> URL {
        let base = try FileManager.default.url(
            for: .applicationSupportDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )
        let directory = base.appendingPathComponent("CloudUploadChunks", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        prepareChunkDirectoryForBackgroundUpload(directory)
        return directory
    }

    private static func prepareChunkDirectoryForBackgroundUpload(_ directory: URL) {
        do {
            try FileManager.default.setAttributes(
                [FileAttributeKey.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication],
                ofItemAtPath: directory.path
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof("background_upload_chunk_directory_ready")
        } catch {
            LaunchTelemetry.shared.recordBackgroundUploadProof("background_upload_chunk_directory_protection_unavailable")
        }
    }

    private static func sanitizedComponent(_ value: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_"))
        let filtered = value.map { character -> Character in
            character.unicodeScalars.allSatisfy { allowed.contains($0) } ? character : "-"
        }
        let result = String(filtered).trimmingCharacters(in: CharacterSet(charactersIn: "-_"))
        return result.isEmpty ? UUID().uuidString : result
    }
}

final class CloudUploadBackgroundSessionRegistry: @unchecked Sendable {
    static let shared = CloudUploadBackgroundSessionRegistry()

    private let lock = NSLock()
    private var completionHandlers: [String: () -> Void] = [:]
    private var relaunchSessions: [String: URLSession] = [:]
    private var relaunchDelegates: [String: CloudUploadBackgroundRelaunchDelegate] = [:]

    private init() {}

    func setCompletionHandler(_ completionHandler: @escaping () -> Void, for identifier: String) {
        let delegate = CloudUploadBackgroundRelaunchDelegate(identifier: identifier)
        let configuration = URLSessionConfiguration.background(withIdentifier: identifier)
        configuration.applyHoopsCloudUploadPolicy(isBackgroundTransfer: true)
        let session = URLSession(configuration: configuration, delegate: delegate, delegateQueue: nil)

        lock.lock()
        completionHandlers[identifier] = completionHandler
        relaunchDelegates[identifier] = delegate
        relaunchSessions[identifier] = session
        lock.unlock()
        LaunchTelemetry.shared.recordBackgroundUploadProof("events_received", metadata: "source=app_delegate reattached=true")

        session.getAllTasks { tasks in
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "reattached_session_checked",
                metadata: "source=app_delegate taskCount=\(tasks.count)"
            )
            if tasks.isEmpty {
                CloudUploadBackgroundSessionRegistry.shared.recheckEmptySessionBeforeFinishing(
                    identifier: identifier,
                    session: session
                )
            }
        }
    }

    func inspectTaskCount(for identifier: String) async -> Int {
        let session: URLSession

        lock.lock()
        if let existingSession = relaunchSessions[identifier] {
            session = existingSession
        } else {
            let delegate = CloudUploadBackgroundRelaunchDelegate(identifier: identifier)
            let configuration = URLSessionConfiguration.background(withIdentifier: identifier)
            configuration.applyHoopsCloudUploadPolicy(isBackgroundTransfer: true)
            session = URLSession(configuration: configuration, delegate: delegate, delegateQueue: nil)
            relaunchDelegates[identifier] = delegate
            relaunchSessions[identifier] = session
        }
        lock.unlock()

        let tasks = await Self.allTasks(in: session)
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "reattached_session_foreground_checked",
            metadata: "source=foreground_resume taskCount=\(tasks.count)"
        )
        if tasks.isEmpty {
            finishEvents(for: identifier)
        }
        return tasks.count
    }

    private static func allTasks(in session: URLSession) async -> [URLSessionTask] {
        await withCheckedContinuation { continuation in
            session.getAllTasks { tasks in
                continuation.resume(returning: tasks)
            }
        }
    }

    private func recheckEmptySessionBeforeFinishing(identifier: String, session: URLSession) {
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "reattached_session_empty_recheck_scheduled",
            metadata: "source=app_delegate delayMs=750"
        )
        DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + 0.75) {
            session.getAllTasks { tasks in
                LaunchTelemetry.shared.recordBackgroundUploadProof(
                    "reattached_session_empty_rechecked",
                    metadata: "source=app_delegate taskCount=\(tasks.count)"
                )
                if tasks.isEmpty {
                    CloudUploadBackgroundSessionRegistry.shared.finishEvents(for: identifier)
                }
            }
        }
    }

    func finishEvents(for identifier: String) {
        lock.lock()
        let completionHandler = completionHandlers.removeValue(forKey: identifier)
        let session = relaunchSessions.removeValue(forKey: identifier)
        relaunchDelegates.removeValue(forKey: identifier)
        lock.unlock()

        session?.finishTasksAndInvalidate()

        guard let completionHandler else { return }
        DispatchQueue.main.async {
            completionHandler()
            LaunchTelemetry.shared.recordBackgroundUploadProof("events_completed", metadata: "source=urlsession_delegate")
        }
    }
}

private extension URLSessionConfiguration {
    func applyHoopsCloudUploadPolicy(isBackgroundTransfer: Bool) {
        waitsForConnectivity = true
        allowsCellularAccess = true
        allowsExpensiveNetworkAccess = true
        allowsConstrainedNetworkAccess = true

        if isBackgroundTransfer {
            sessionSendsLaunchEvents = true
            isDiscretionary = false
            timeoutIntervalForRequest = 10 * 60
            timeoutIntervalForResource = 24 * 60 * 60
        } else {
            timeoutIntervalForRequest = 2 * 60
            timeoutIntervalForResource = 2 * 60 * 60
        }
    }
}

private final class CloudUploadBackgroundRelaunchDelegate: NSObject, URLSessionTaskDelegate, URLSessionDataDelegate, @unchecked Sendable {
    private let identifier: String
    private let lock = NSLock()
    private var pendingPersistenceCount = 0
    private var didReceiveFinishEvents = false

    init(identifier: String) {
        self.identifier = identifier
        super.init()
    }

    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        didCompleteWithError error: Error?
    ) {
        if let error {
            let reason = Self.safeRelaunchErrorReason(error)
            CloudAnalysisService.recordRelaunchedUploadProgressSummary(
                event: "relaunch_task_failed",
                reason: reason
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "relaunch_task_failed",
                metadata: "source=urlsession_delegate reason=\(reason)"
            )
        } else {
            guard let http = task.response as? HTTPURLResponse else {
                CloudAnalysisService.recordRelaunchedUploadProgressSummary(
                    event: "relaunch_task_no_http_response",
                    reason: "no_http_response"
                )
                LaunchTelemetry.shared.recordBackgroundUploadProof(
                    "relaunch_task_no_http_response",
                    metadata: "source=urlsession_delegate"
                )
                return
            }

            guard (200..<300).contains(http.statusCode) else {
                CloudAnalysisService.recordRelaunchedUploadProgressSummary(
                    event: "relaunch_task_http_failed",
                    statusCode: http.statusCode,
                    reason: "http_failed"
                )
                LaunchTelemetry.shared.recordBackgroundUploadProof(
                    "relaunch_task_http_failed",
                    metadata: "source=urlsession_delegate status=\(http.statusCode)"
                )
                return
            }

            if identifier.contains(".part-") {
                guard let etag = Self.headerValue("ETag", from: http), !etag.isEmpty else {
                    CloudAnalysisService.recordRelaunchedUploadProgressSummary(
                        event: "relaunch_task_missing_etag",
                        statusCode: http.statusCode,
                        reason: "missing_etag"
                    )
                    LaunchTelemetry.shared.recordBackgroundUploadProof(
                        "relaunch_task_missing_etag",
                        metadata: "source=urlsession_delegate status=\(http.statusCode)"
                    )
                    return
                }
                beginPersistence()
                Task {
                    let uploadCompleted = await CloudUploadResumeStore.shared.recordRelaunchedCompletedPart(
                        sessionIdentifier: identifier,
                        etag: etag
                    )
                    if uploadCompleted {
                        await MainActor.run {
                            AnalysisNotificationService.shared.notifyBackgroundUploadCompleted()
                        }
                    }
                    self.endPersistenceIfNeeded()
                }
            } else if identifier.hasSuffix(".source") {
                beginPersistence()
                Task {
                    let uploadCompleted = await CloudUploadResumeStore.shared.recordRelaunchedSourceUploadCompleted(
                        sessionIdentifier: identifier
                    )
                    if uploadCompleted {
                        await MainActor.run {
                            AnalysisNotificationService.shared.notifyBackgroundUploadCompleted()
                        }
                    }
                    self.endPersistenceIfNeeded()
                }
            }
            CloudAnalysisService.recordRelaunchedUploadProgressSummary(
                event: "relaunch_task_completed",
                statusCode: http.statusCode
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "relaunch_task_completed",
                metadata: "source=urlsession_delegate status=\(http.statusCode)"
            )
        }
    }

    func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
        lock.lock()
        didReceiveFinishEvents = true
        let shouldFinish = pendingPersistenceCount == 0
        let pendingCount = pendingPersistenceCount
        lock.unlock()

        if shouldFinish {
            CloudUploadBackgroundSessionRegistry.shared.finishEvents(for: identifier)
        } else {
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "events_waiting_for_manifest_persistence",
                metadata: "source=urlsession_delegate pending=\(pendingCount)"
            )
        }
    }

    private func beginPersistence() {
        lock.lock()
        pendingPersistenceCount += 1
        lock.unlock()
    }

    private func endPersistenceIfNeeded() {
        lock.lock()
        pendingPersistenceCount = max(0, pendingPersistenceCount - 1)
        let shouldFinish = didReceiveFinishEvents && pendingPersistenceCount == 0
        lock.unlock()

        if shouldFinish {
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "manifest_persistence_finished",
                metadata: "source=urlsession_delegate"
            )
            CloudUploadBackgroundSessionRegistry.shared.finishEvents(for: identifier)
        }
    }

    private static func headerValue(_ name: String, from response: HTTPURLResponse) -> String? {
        for (key, value) in response.allHeaderFields {
            if String(describing: key).caseInsensitiveCompare(name) == .orderedSame {
                return String(describing: value)
            }
        }
        return nil
    }

    private static func safeRelaunchErrorReason(_ error: Error) -> String {
        if error.isTaskCancellation {
            return "cancelled"
        }
        if let urlError = error as? URLError {
            return "url_error_\(urlError.code.rawValue)"
        }
        return String(describing: type(of: error))
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: "_")
    }
}

private struct CloudUploadResumeManifest: Codable, Sendable {
    var jobID: String
    var installID: String
    var sourceFilePath: String
    var uploadID: String
    var sourceObjectKey: String?
    var resultObjectKey: String?
    var pollAfterSeconds: Int
    var purpose: CloudUploadResumePurpose
    var chunkSizeBytes: Int
    var partCount: Int
    var totalFileSizeBytes: Int64
    var completedParts: [CloudMultipartCompletedPart]
    var activeSessionIdentifiers: [String]
    var createdAt: Date
    var updatedAt: Date
}

private actor CloudUploadResumeStore {
    static let shared = CloudUploadResumeStore()

    private let maxStoredSessionIdentifiers = 24
    private let encoder = JSONEncoder()

    private init() {
        encoder.dateEncodingStrategy = .iso8601
    }

    func begin(
        jobID: String,
        installID: String,
        sourceURL: URL,
        uploadID: String,
        sourceObjectKey: String?,
        resultObjectKey: String?,
        pollAfterSeconds: Int,
        purpose: CloudUploadResumePurpose,
        chunkSizeBytes: Int,
        partCount: Int,
        totalFileSizeBytes: Int64
    ) -> [CloudMultipartCompletedPart] {
        var manifest = loadManifest()
        if manifest?.jobID != jobID || manifest?.uploadID != uploadID {
            manifest = CloudUploadResumeManifest(
                jobID: jobID,
                installID: installID,
                sourceFilePath: sourceURL.path,
                uploadID: uploadID,
                sourceObjectKey: sourceObjectKey,
                resultObjectKey: resultObjectKey,
                pollAfterSeconds: pollAfterSeconds,
                purpose: purpose,
                chunkSizeBytes: chunkSizeBytes,
                partCount: partCount,
                totalFileSizeBytes: totalFileSizeBytes,
                completedParts: [],
                activeSessionIdentifiers: [],
                createdAt: Date(),
                updatedAt: Date()
            )
        }

        manifest?.updatedAt = Date()
        saveManifest(manifest)
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_started",
            metadata: "partCount=\(partCount) completed=\(manifest?.completedParts.count ?? 0)"
        )
        return manifest?.completedParts.sorted { $0.partNumber < $1.partNumber } ?? []
    }

    func pendingManifest() -> CloudUploadResumeManifest? {
        loadManifest()
    }

    func recordSession(jobID: String, uploadID: String, sessionIdentifier: String) {
        guard var manifest = loadMatchingManifest(jobID: jobID, uploadID: uploadID) else { return }
        var identifiers = manifest.activeSessionIdentifiers.filter { $0 != sessionIdentifier }
        identifiers.append(sessionIdentifier)
        manifest.activeSessionIdentifiers = Array(identifiers.suffix(maxStoredSessionIdentifiers))
        manifest.updatedAt = Date()
        saveManifest(manifest)
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_session_recorded",
            metadata: "sessionCount=\(manifest.activeSessionIdentifiers.count)"
        )
    }

    func clearActiveSession(jobID: String, uploadID: String, sessionIdentifier: String) {
        guard var manifest = loadMatchingManifest(jobID: jobID, uploadID: uploadID),
              manifest.activeSessionIdentifiers.contains(sessionIdentifier) else { return }
        manifest.activeSessionIdentifiers.removeAll { $0 == sessionIdentifier }
        manifest.updatedAt = Date()
        saveManifest(manifest)
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_session_completed",
            metadata: "sessionCount=\(manifest.activeSessionIdentifiers.count)"
        )
    }

    func clearActiveSessions(jobID: String, uploadID: String, sessionIdentifiers: [String], reason: String) {
        guard var manifest = loadMatchingManifest(jobID: jobID, uploadID: uploadID),
              !sessionIdentifiers.isEmpty else { return }
        let staleIdentifiers = Set(sessionIdentifiers)
        let beforeCount = manifest.activeSessionIdentifiers.count
        manifest.activeSessionIdentifiers.removeAll { staleIdentifiers.contains($0) }
        manifest.updatedAt = Date()
        saveManifest(manifest)
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_sessions_cleared",
            metadata: "reason=\(reason) before=\(beforeCount) after=\(manifest.activeSessionIdentifiers.count)"
        )
    }

    func recordCompletedPart(jobID: String, uploadID: String, partNumber: Int, etag: String) -> [CloudMultipartCompletedPart] {
        guard var manifest = loadMatchingManifest(jobID: jobID, uploadID: uploadID) else {
            return [CloudMultipartCompletedPart(partNumber: partNumber, etag: etag)]
        }

        var parts = manifest.completedParts.filter { $0.partNumber != partNumber }
        parts.append(CloudMultipartCompletedPart(partNumber: partNumber, etag: etag))
        manifest.completedParts = parts.sorted { $0.partNumber < $1.partNumber }
        manifest.updatedAt = Date()
        saveManifest(manifest)
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_part_completed",
            metadata: "completed=\(manifest.completedParts.count) partCount=\(manifest.partCount)"
        )
        return manifest.completedParts
    }

    private static func manifestJobMatchesSession(_ manifestJobID: String, sessionJobID: String) -> Bool {
        manifestJobID == sessionJobID || sanitizedSessionComponent(manifestJobID) == sessionJobID
    }

    private static func sanitizedSessionComponent(_ value: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_"))
        let filtered = value.map { character -> Character in
            character.unicodeScalars.allSatisfy { allowed.contains($0) } ? character : "-"
        }
        let result = String(filtered).trimmingCharacters(in: CharacterSet(charactersIn: "-_"))
        return result.isEmpty ? UUID().uuidString : result
    }

    func recordRelaunchedCompletedPart(sessionIdentifier: String, etag: String) -> Bool {
        guard let sessionPart = Self.parseMultipartSessionIdentifier(sessionIdentifier),
              var manifest = loadManifest(),
              Self.manifestJobMatchesSession(manifest.jobID, sessionJobID: sessionPart.jobID) else {
            LaunchTelemetry.shared.recordBackgroundUploadProof("resume_manifest_relaunch_part_ignored")
            return false
        }

        var parts = manifest.completedParts.filter { $0.partNumber != sessionPart.partNumber }
        parts.append(CloudMultipartCompletedPart(partNumber: sessionPart.partNumber, etag: etag))
        manifest.completedParts = parts.sorted { $0.partNumber < $1.partNumber }
        manifest.activeSessionIdentifiers.removeAll { $0 == sessionIdentifier }
        manifest.updatedAt = Date()
        saveManifest(manifest)
        let uploadCompleted = manifest.completedParts.count == manifest.partCount
            && manifest.activeSessionIdentifiers.isEmpty
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_relaunch_part_completed",
            metadata: "completed=\(manifest.completedParts.count) partCount=\(manifest.partCount) activeSessions=\(manifest.activeSessionIdentifiers.count)"
        )
        if uploadCompleted {
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "resume_manifest_relaunch_upload_completed",
                metadata: "purpose=\(manifest.purpose.rawValue) partCount=\(manifest.partCount)"
            )
        }
        return uploadCompleted
    }

    func recordRelaunchedSourceUploadCompleted(sessionIdentifier: String) -> Bool {
        guard let jobID = Self.parseSourceSessionIdentifier(sessionIdentifier),
              var manifest = loadManifest(),
              Self.manifestJobMatchesSession(manifest.jobID, sessionJobID: jobID) else {
            LaunchTelemetry.shared.recordBackgroundUploadProof("resume_manifest_relaunch_source_ignored")
            return false
        }

        var parts = manifest.completedParts.filter { $0.partNumber != 1 }
        parts.append(CloudMultipartCompletedPart(partNumber: 1, etag: "source-upload-complete"))
        manifest.completedParts = parts.sorted { $0.partNumber < $1.partNumber }
        manifest.activeSessionIdentifiers.removeAll { $0 == sessionIdentifier }
        manifest.updatedAt = Date()
        saveManifest(manifest)
        let uploadCompleted = manifest.completedParts.count == manifest.partCount
            && manifest.activeSessionIdentifiers.isEmpty
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_relaunch_source_completed",
            metadata: "completed=\(manifest.completedParts.count) partCount=\(manifest.partCount) activeSessions=\(manifest.activeSessionIdentifiers.count)"
        )
        if uploadCompleted {
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "resume_manifest_relaunch_upload_completed",
                metadata: "purpose=\(manifest.purpose.rawValue) partCount=\(manifest.partCount)"
            )
        }
        return uploadCompleted
    }

    func clear(jobID: String, uploadID: String) {
        guard let manifest = loadMatchingManifest(jobID: jobID, uploadID: uploadID) else { return }
        UserDefaults.standard.removeObject(forKey: cloudUploadResumeManifestDefaultsKey)
        CloudUploadChunkFileStore.clearChunks(jobID: manifest.jobID)
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_cleared",
            metadata: "completed=\(manifest.completedParts.count) partCount=\(manifest.partCount)"
        )
    }

    func clearAnyManifest(reason: String) {
        guard let manifest = loadManifest() else { return }
        UserDefaults.standard.removeObject(forKey: cloudUploadResumeManifestDefaultsKey)
        CloudUploadChunkFileStore.clearChunks(jobID: manifest.jobID)
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_cleared",
            metadata: "reason=\(reason) completed=\(manifest.completedParts.count) partCount=\(manifest.partCount)"
        )
    }

    func clearJob(jobID: String, reason: String) {
        guard let manifest = loadManifest(),
              manifest.jobID == jobID else {
            return
        }
        UserDefaults.standard.removeObject(forKey: cloudUploadResumeManifestDefaultsKey)
        CloudUploadChunkFileStore.clearChunks(jobID: manifest.jobID)
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_cleared",
            metadata: "reason=\(reason) completed=\(manifest.completedParts.count) partCount=\(manifest.partCount)"
        )
    }

    private func loadMatchingManifest(jobID: String, uploadID: String) -> CloudUploadResumeManifest? {
        guard let manifest = loadManifest(),
              manifest.jobID == jobID,
              manifest.uploadID == uploadID else {
            return nil
        }
        return manifest
    }

    private static func parseMultipartSessionIdentifier(_ identifier: String) -> (jobID: String, partNumber: Int)? {
        let components = identifier.split(separator: ".").map(String.init)
        guard let markerIndex = components.firstIndex(of: "cloud-upload"),
              components.indices.contains(markerIndex + 2) else {
            return nil
        }

        let jobID = components[markerIndex + 1]
        let partComponent = components[markerIndex + 2]
        guard partComponent.hasPrefix("part-"),
              let partNumber = Int(partComponent.dropFirst("part-".count)),
              partNumber > 0 else {
            return nil
        }

        return (jobID, partNumber)
    }

    private static func parseSourceSessionIdentifier(_ identifier: String) -> String? {
        let components = identifier.split(separator: ".").map(String.init)
        guard let markerIndex = components.firstIndex(of: "cloud-upload"),
              components.indices.contains(markerIndex + 2),
              components[markerIndex + 2] == "source" else {
            return nil
        }
        return components[markerIndex + 1]
    }

    private func loadManifest() -> CloudUploadResumeManifest? {
        Self.loadPersistedManifestSnapshot()
    }

    static func loadPersistedManifestSnapshot() -> CloudUploadResumeManifest? {
        guard let data = UserDefaults.standard.data(forKey: cloudUploadResumeManifestDefaultsKey) else { return nil }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try? decoder.decode(CloudUploadResumeManifest.self, from: data)
    }

    private func saveManifest(_ manifest: CloudUploadResumeManifest?) {
        guard let manifest,
              let data = try? encoder.encode(manifest) else {
            UserDefaults.standard.removeObject(forKey: cloudUploadResumeManifestDefaultsKey)
            return
        }
        UserDefaults.standard.set(data, forKey: cloudUploadResumeManifestDefaultsKey)
    }
}

private struct CloudUploadProgressSnapshot: Sendable {
    let fraction: Double
    let elapsedSeconds: TimeInterval
    let secondsSinceProgress: TimeInterval
    let uploadedBytes: Int64?
    let totalBytes: Int64?
}

private actor CloudUploadProgressTracker {
    private let startedAt = Date()
    private var lastProgressAt = Date()
    private var latestFraction = 0.0
    private var latestUploadedBytes: Int64?
    private var latestTotalBytes: Int64?
    private var didSendStallProof = false

    func update(uploadedBytes: Int64, totalBytes: Int64) {
        let safeUploadedBytes = max(uploadedBytes, 0)
        let safeTotalBytes = max(totalBytes, 0)
        let boundedFraction: Double
        if safeTotalBytes > 0 {
            boundedFraction = min(max(Double(safeUploadedBytes) / Double(safeTotalBytes), 0), 1)
        } else {
            boundedFraction = latestFraction
        }

        if boundedFraction > latestFraction + 0.001 {
            latestFraction = boundedFraction
            lastProgressAt = Date()
        } else {
            latestFraction = max(latestFraction, boundedFraction)
        }
        latestUploadedBytes = safeUploadedBytes
        if safeTotalBytes > 0 {
            latestTotalBytes = safeTotalBytes
        }
    }

    func snapshot() -> CloudUploadProgressSnapshot {
        let now = Date()
        let fraction = latestFraction
        let lastProgressAt = lastProgressAt
        let uploadedBytes = latestUploadedBytes
        let totalBytes = latestTotalBytes
        return CloudUploadProgressSnapshot(
            fraction: fraction,
            elapsedSeconds: now.timeIntervalSince(startedAt),
            secondsSinceProgress: now.timeIntervalSince(lastProgressAt),
            uploadedBytes: uploadedBytes,
            totalBytes: totalBytes
        )
    }

    func markStallProofSentIfNeeded() -> Bool {
        guard !didSendStallProof else { return false }
        didSendStallProof = true
        return true
    }
}

private final class CloudUploadProgressDelegate: NSObject, URLSessionTaskDelegate, URLSessionDataDelegate, @unchecked Sendable {
    private let onProgress: @Sendable (_ uploadedBytes: Int64, _ totalBytes: Int64) -> Void
    private let onWaitingForConnectivity: @Sendable () -> Void
    private let lock = NSLock()
    private var continuation: CheckedContinuation<URLResponse, Error>?

    init(
        onProgress: @escaping @Sendable (_ uploadedBytes: Int64, _ totalBytes: Int64) -> Void,
        onWaitingForConnectivity: @escaping @Sendable () -> Void
    ) {
        self.onProgress = onProgress
        self.onWaitingForConnectivity = onWaitingForConnectivity
        super.init()
    }

    func upload(request: URLRequest, fromFile fileURL: URL, using session: URLSession) async throws -> URLResponse {
        try await withTaskCancellationHandler(operation: {
            try await withCheckedThrowingContinuation { continuation in
                let task = session.uploadTask(with: request, fromFile: fileURL)
                lock.lock()
                self.continuation = continuation
                lock.unlock()
                task.resume()
            }
        }, onCancel: {
            session.invalidateAndCancel()
        })
    }

    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        didSendBodyData bytesSent: Int64,
        totalBytesSent: Int64,
        totalBytesExpectedToSend: Int64
    ) {
        guard totalBytesExpectedToSend > 0 else { return }
        onProgress(totalBytesSent, totalBytesExpectedToSend)
    }

    func urlSession(_ session: URLSession, taskIsWaitingForConnectivity task: URLSessionTask) {
        onWaitingForConnectivity()
    }

    func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
        guard let identifier = session.configuration.identifier else { return }
        CloudUploadBackgroundSessionRegistry.shared.finishEvents(for: identifier)
    }

    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        didCompleteWithError error: Error?
    ) {
        lock.lock()
        let continuation = continuation
        self.continuation = nil
        lock.unlock()

        guard let continuation else { return }
        if let error {
            continuation.resume(throwing: error)
            return
        }
        guard let response = task.response else {
            continuation.resume(throwing: CloudAnalysisError.invalidResponse)
            return
        }
        continuation.resume(returning: response)
    }
}
