import AVFoundation
import Foundation
import Network
import UniformTypeIdentifiers

private let cloudUploadSingleSourcePrefix = "single-source-"
private let cloudUploadServerPlanDefaultsKey = "hoopsclips.cloudUpload.serverPlan.v1"
private let cloudUploadProgressSummaryDefaultsKey = "hoopsclips.cloudUpload.progressSummary.v1"
private let cloudUploadCapabilitySummaryDefaultsKey = "hoopsclips.cloudUpload.capabilitySummary.v1"
private let cloudUploadDeployedCapabilitySummaryDefaultsKey = "hoopsclips.cloudUpload.deployedCapabilitySummary.v1"
private let cloudUploadSourceOptimizationSummaryDefaultsKey = "hoopsclips.cloudUpload.sourceOptimizationSummary.v1"
private let optimizedUploadSourceMaximumAge: TimeInterval = 24 * 60 * 60
private let compactOptimizedUploadDurationSeconds: Double = 45 * 60
private let compactOptimizedUploadFileSizeBytes: Int64 = 1_400 * 1_024 * 1_024
private let optimizedUploadSourceTimeoutSeconds: UInt64 = 4 * 60
private let cloudUploadForegroundRequestTimeoutSeconds: TimeInterval = 2 * 60
private let cloudUploadForegroundResourceTimeoutSeconds: TimeInterval = 2 * 60 * 60
private let cloudUploadBackgroundRequestTimeoutSeconds: TimeInterval = 10 * 60
private let cloudUploadBackgroundResourceTimeoutSeconds: TimeInterval = 24 * 60 * 60
private let cloudUploadStallProofThresholdSeconds: TimeInterval = 90
private let cloudUploadFileProtectionName = "completeUntilFirstUserAuthentication"
private let cloudUploadChunkRetryBackoffSeconds: [UInt64] = [2, 5, 12, 30]

nonisolated enum CloudUploadResumeOutcome: Sendable {
    case pendingUpload
    case analysis(CloudAnalysisResult)
    case teamScan(PreparedCloudAnalysisJob)
}

nonisolated private enum CloudUploadResumePurpose: String, Codable, Sendable {
    case analysis
    case teamScan
}

nonisolated private struct CloudUploadPartTarget: Sendable {
    let jobId: String
    let partNumber: Int
    let uploadUrl: String
    let uploadMethod: String
    let uploadHeaders: [String: String]

    init(_ response: CloudMultipartPartResponse) {
        self.jobId = response.jobId
        self.partNumber = response.partNumber
        self.uploadUrl = response.uploadUrl
        self.uploadMethod = response.uploadMethod
        self.uploadHeaders = response.uploadHeaders
    }

    init(assetID: String, target: CloudAssetUploadTarget) throws {
        guard let partNumber = target.partNumber else {
            throw CloudAnalysisError.invalidResponse
        }
        self.jobId = assetID
        self.partNumber = partNumber
        self.uploadUrl = target.uploadUrl
        self.uploadMethod = target.uploadMethod
        self.uploadHeaders = target.uploadHeaders
    }
}

nonisolated private struct CloudReadyAsset: Sendable {
    let assetID: String
    let storageKey: String
    let analysisStorageKey: String
    let pollAfterSeconds: Int
}

struct CloudAnalysisService {
    typealias HandoffHandler = @MainActor @Sendable (_ jobID: String, _ sourceObjectKey: String?) -> Void

    private static let analysisPollTimeoutSeconds: UInt64 = 8 * 60
    private static let assetPollTimeoutSeconds: UInt64 = 4 * 60
    private static let maxPollDelaySeconds = 5
    private static let maxVisibleProgressStageCharacters = 72
    private static let maxVisibleBackendMessageCharacters = 96
    private static let fallbackBackgroundSessionPrefix = "atrak.charlie.hoopsclips.cloud-upload"
    private static let maxConcurrentMultipartUploads = 3
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
                configuration: Self.uploadSessionConfiguration(backgroundIdentifier: identifier)
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
        let completedParts = manifest.completedParts.count
        let partCount = max(manifest.partCount, 0)
        let completedBytes = completedUploadBytes(
            completedParts: manifest.completedParts,
            chunkSizeBytes: manifest.chunkSizeBytes,
            totalFileSizeBytes: manifest.totalFileSizeBytes
        )
        let totalBytes = max(manifest.totalFileSizeBytes, 0)
        let progressPercent = totalBytes > 0
            ? min(100, max(0, Int((Double(completedBytes) / Double(totalBytes) * 100).rounded())))
            : 0
        let uploadComplete = partCount > 0 && completedParts >= partCount
        let activeSessions = manifest.activeSessionIdentifiers.count
        let ageSeconds = max(0, Int(Date().timeIntervalSince(manifest.updatedAt).rounded(.down)))
        let staleWithoutActiveSession = !uploadComplete && activeSessions == 0 && ageSeconds >= 300
        let uploadExpired = manifest.uploadExpiresAt.map { $0 <= Date().addingTimeInterval(60) } ?? false
        let resumeSafe = (sourceAvailability == "available" || uploadComplete) && !uploadExpired && !staleWithoutActiveSession
        let expiresAt = manifest.uploadExpiresAt.map { ISO8601DateFormatter().string(from: $0) } ?? "none"
        let nextAction: String
        if uploadExpired {
            nextAction = "fresh_upload_required"
        } else if activeSessions > 0 {
            nextAction = "wait_for_background_session"
        } else if uploadComplete, manifest.assetID != nil {
            nextAction = "complete_asset_upload"
        } else if uploadComplete {
            nextAction = manifest.purpose == .teamScan ? "run_team_scan" : "start_cloud_analysis"
        } else {
            nextAction = "resume_upload"
        }
        return [
            "pending=true",
            "assetUpload=\(manifest.assetID != nil)",
            "purpose=\(manifest.purpose.rawValue)",
            "completed=\(completedParts)/\(partCount)",
            "completedBytes=\(completedBytes)",
            "totalBytes=\(totalBytes)",
            "progressPercent=\(progressPercent)",
            "uploadComplete=\(uploadComplete)",
            "sessions=\(activeSessions)",
            "activeUploadSessions=\(activeSessions > 0)",
            "nextAction=\(nextAction)",
            "ageSeconds=\(ageSeconds)",
            "staleWithoutActiveSession=\(staleWithoutActiveSession)",
            "uploadExpired=\(uploadExpired)",
            "resumeSafe=\(resumeSafe)",
            "expiresAt=\(expiresAt)",
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

    static func latestUploadSourceOptimizationSummary() -> String {
        UserDefaults.standard.string(forKey: cloudUploadSourceOptimizationSummaryDefaultsKey) ?? "none"
    }

    static func multipartUploadPolicySummary() -> String {
        let networkPolicy = CloudUploadNetworkPolicy.shared.currentPolicy(
            defaultMaximum: maxConcurrentMultipartUploads
        )
        return [
            "maxConcurrentMultipartUploads=\(networkPolicy.laneLimit)",
            "configuredMaxConcurrentMultipartUploads=\(maxConcurrentMultipartUploads)",
            "multipartLaneReason=\(networkPolicy.reason)",
            "networkExpensive=\(networkPolicy.isExpensive)",
            "networkConstrained=\(networkPolicy.isConstrained)",
            "chunkRetryAttempts=\(cloudUploadChunkRetryBackoffSeconds.count + 1)",
            "chunkRetryBackoffSeconds=\(cloudUploadChunkRetryBackoffSeconds.map { String($0) }.joined(separator: ","))",
            "progressAggregation=total_bytes_across_active_chunks",
            "memoryPolicy=bounded_chunk_data_per_lane",
            "resumePolicy=persist_completed_parts"
        ].joined(separator: " ")
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

    static func backgroundUploadRuntimePolicySummary() -> String {
        [
            "mode=ios_background_urlsession",
            "backgroundRequestTimeoutSeconds=\(Int(cloudUploadBackgroundRequestTimeoutSeconds))",
            "backgroundResourceTimeoutSeconds=\(Int(cloudUploadBackgroundResourceTimeoutSeconds))",
            "foregroundRequestTimeoutSeconds=\(Int(cloudUploadForegroundRequestTimeoutSeconds))",
            "fileProtection=\(cloudUploadFileProtectionName)",
            "stallProofThresholdSeconds=\(Int(cloudUploadStallProofThresholdSeconds))",
            "waitsForConnectivity=true",
            "allowsCellularAccess=true",
            "allowsExpensiveNetworkAccess=true",
            "allowsConstrainedNetworkAccess=true",
            "sessionSendsLaunchEvents=true",
            "multipartCompleteIdempotent=true",
            "cancellationPolicy=background_sessions_finish_after_task_cancel",
            "chunkFileCleanup=terminal_response_or_manifest_clear",
            "isDiscretionary=false",
            "privacy=no_urls_no_object_keys_no_local_file_paths"
        ].joined(separator: " ")
    }

    static func backgroundUploadCompletionProofSummary() -> String {
        let latestProof = LaunchTelemetry.shared.latestBackgroundUploadProofSummary ?? ""
        let recentTrail = LaunchTelemetry.shared.recentBackgroundUploadProofTrailSummary ?? ""
        let combinedProof = "\(latestProof) \(recentTrail)".lowercased()
        let wakeReceived = combinedProof.contains("background_urlsession_events_received")
            || combinedProof.contains("events_received")
        let relaunchCompletion = combinedProof.contains("resume_manifest_relaunch_upload_completed")
        let inferredSourceCompletion = combinedProof.contains("resume_manifest_source_completion_inferred")
        let completedWhileAway = wakeReceived && (relaunchCompletion || inferredSourceCompletion)

        return [
            "completedWhileAway=\(completedWhileAway)",
            "wakeReceived=\(wakeReceived)",
            "relaunchCompletion=\(relaunchCompletion)",
            "inferredSourceCompletion=\(inferredSourceCompletion)",
            "privacy=no_urls_no_object_keys_no_local_file_paths"
        ].joined(separator: " ")
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

    private nonisolated static func formatUploadElapsedTime(_ elapsedSeconds: TimeInterval) -> String {
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

    private nonisolated static func formatUploadByteProgress(uploadedBytes: Int64, totalBytes: Int64) -> String {
        let uploadedMB = Double(max(uploadedBytes, 0)) / 1_048_576.0
        let totalMB = Double(max(totalBytes, 1)) / 1_048_576.0
        if totalMB >= 100 {
            return "\(Int(uploadedMB.rounded()))/\(Int(totalMB.rounded())) MB"
        }
        return String(format: "%.1f/%.1f MB", uploadedMB, totalMB)
    }

    private nonisolated static func formatUploadSpeed(bytesPerSecond: Double) -> String {
        let mbPerSecond = max(bytesPerSecond, 0) / 1_048_576.0
        if mbPerSecond >= 1 {
            return String(format: "%.1f MB/s", mbPerSecond)
        }

        let kbPerSecond = max(bytesPerSecond, 0) / 1_024.0
        return "\(Int(kbPerSecond.rounded())) KB/s"
    }

    private nonisolated static func formatUploadRemainingTime(uploadedBytes: Int64, totalBytes: Int64, bytesPerSecond: Double) -> String {
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

    private nonisolated static func recordLatestUploadProgressSummary(
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

    private static func recordServerAssetUploadPlan(_ asset: CloudAssetUploadInitResponse) {
        let multipart = asset.multipart
        let partCount = max(multipart?.partCount ?? 1, 1)
        let chunkSizeBytes = max(multipart?.partSizeBytes ?? 0, 0)
        let chunkSizeMB = chunkSizeBytes > 0
            ? String(format: "%.1f", Double(chunkSizeBytes) / 1_048_576.0)
            : "none"
        let expiresAt = ISO8601DateFormatter().string(from: asset.expiresAt)
        let summary = [
            "assetUpload=true",
            "serverChunked=\(partCount > 1)",
            "partCount=\(partCount)",
            "chunkSizeMB=\(chunkSizeMB)",
            "uploadMode=\(safeUploadPlanComponent(asset.uploadMode))",
            "uploadMethod=\(safeUploadPlanComponent(asset.uploadMethod))",
            "uploadState=\(safeUploadPlanComponent(asset.uploadState))",
            "expiresAt=\(expiresAt)",
            "privacy=no_urls_no_object_keys_no_upload_ids"
        ].joined(separator: " ")

        UserDefaults.standard.set(summary, forKey: cloudUploadServerPlanDefaultsKey)
        let capabilitySummary = [
            "assetUploadAdvertised=true",
            "chunkedUploadAdvertised=\(partCount > 1)",
            "partCount=\(partCount)",
            "chunkSizeMB=\(chunkSizeMB)",
            "singleUploadURLPresent=\(!(asset.uploadUrl ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)",
            "uploadMode=\(safeUploadPlanComponent(asset.uploadMode))",
            "privacy=no_urls_no_object_keys_no_upload_ids"
        ].joined(separator: " ")
        UserDefaults.standard.set(capabilitySummary, forKey: cloudUploadCapabilitySummaryDefaultsKey)
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "server_asset_upload_plan_received",
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

    private nonisolated static func safeUploadPlanComponent(_ value: String) -> String {
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

        progress(0.02, "Preparing cloud analysis")
        let originalFileInfo = try fileInfo(for: url)
        let uploadSource = await preparedUploadSource(
            originalURL: url,
            duration: duration,
            originalFileSizeBytes: originalFileInfo.fileSizeBytes,
            progressStage: "Preparing smaller cloud upload",
            progressValue: 0.04,
            progress: progress
        )
        let uploadURL = uploadSource.url
        let fileInfo = try fileInfo(for: uploadURL)
        let assetUpload = try await createAssetUploadIfSupported(
            baseURL: baseURL,
            request: CloudAssetUploadInitRequest(
                filename: uploadSource.filename,
                contentType: fileInfo.contentType,
                fileSizeBytes: fileInfo.fileSizeBytes,
                durationSeconds: duration,
                installId: installID,
                appVersion: appVersion,
                analysisVersion: analysisVersion
            )
        )
        if let assetUpload {
            let uploadStage = Self.uploadProgressStage(fileSizeBytes: fileInfo.fileSizeBytes)
            progress(0.15, uploadStage)
            let readyAsset = try await uploadAsset(
                assetUpload,
                from: uploadURL,
                baseURL: baseURL,
                installID: installID,
                purpose: .analysis,
                stage: uploadStage,
                progressStart: 0.15,
                progressEnd: 0.27,
                progress: progress
            )

            progress(0.35, "Starting cloud clip search")
            let job = try await createAssetAnalysisJob(
                baseURL: baseURL,
                assetID: readyAsset.assetID,
                installID: installID,
                appVersion: appVersion,
                analysisVersion: analysisVersion,
                teamSelection: teamSelection
            )
            onCloudHandoff?(job.jobId, job.storageKey)
            await CloudUploadResumeStore.shared.clearJob(jobID: readyAsset.assetID, reason: "asset_analysis_started")
            Self.cleanupOptimizedUploadSourceIfNeeded(uploadSource)

            return try await pollJob(
                baseURL: baseURL,
                jobID: job.jobId,
                sourceObjectKey: job.storageKey,
                initialPollAfterSeconds: job.pollAfterSeconds,
                progress: progress
            )
        }

        let job = try await createJob(
            baseURL: baseURL,
            request: CreateCloudAnalysisJobRequest(
                filename: uploadSource.filename,
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
            from: uploadURL,
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
        Self.cleanupOptimizedUploadSourceIfNeeded(uploadSource)

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

        progress(0.02, "Preparing cloud team scan")
        let originalFileInfo = try fileInfo(for: url)
        let uploadSource = await preparedUploadSource(
            originalURL: url,
            duration: duration,
            originalFileSizeBytes: originalFileInfo.fileSizeBytes,
            progressStage: "Preparing smaller team-scan upload",
            progressValue: 0.04,
            progress: progress
        )
        let uploadURL = uploadSource.url
        let fileInfo = try fileInfo(for: uploadURL)
        let assetUpload = try await createAssetUploadIfSupported(
            baseURL: baseURL,
            request: CloudAssetUploadInitRequest(
                filename: uploadSource.filename,
                contentType: fileInfo.contentType,
                fileSizeBytes: fileInfo.fileSizeBytes,
                durationSeconds: duration,
                installId: installID,
                appVersion: appVersion,
                analysisVersion: analysisVersion
            )
        )
        if let assetUpload {
            let uploadStage = Self.uploadProgressStage(fileSizeBytes: fileInfo.fileSizeBytes, teamScan: true)
            progress(0.14, uploadStage)
            let readyAsset = try await uploadAsset(
                assetUpload,
                from: uploadURL,
                baseURL: baseURL,
                installID: installID,
                purpose: .teamScan,
                stage: uploadStage,
                progressStart: 0.14,
                progressEnd: 0.19,
                progress: progress
            )

            progress(0.20, "Scanning jersey colors")
            let scan = try await scanAssetTeams(
                baseURL: baseURL,
                assetID: readyAsset.assetID,
                installID: installID
            )
            await CloudUploadResumeStore.shared.clearJob(jobID: readyAsset.assetID, reason: "asset_team_scan_started")
            Self.cleanupOptimizedUploadSourceIfNeeded(uploadSource)
            progress(0.24, scan.detectedTeams.isEmpty ? "Team scan unavailable" : "Team choices found")

            let job = CreateCloudAnalysisJobResponse(
                jobId: readyAsset.assetID,
                assetId: readyAsset.assetID,
                storageKey: readyAsset.analysisStorageKey,
                uploadUrl: "",
                uploadMethod: "PUT",
                uploadHeaders: [:],
                expiresAt: Date(),
                pollAfterSeconds: readyAsset.pollAfterSeconds,
                quotaRemainingToday: 0,
                analysisMode: "cloud",
                sourceObjectKey: readyAsset.analysisStorageKey,
                resultObjectKey: nil
            )
            return PreparedCloudAnalysisJob(
                sourceURL: url.standardizedFileURL,
                job: job,
                detectedTeams: scan.detectedTeams
            )
        }

        let job = try await createJob(
            baseURL: baseURL,
            request: CreateCloudAnalysisJobRequest(
                filename: uploadSource.filename,
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
            from: uploadURL,
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
        Self.cleanupOptimizedUploadSourceIfNeeded(uploadSource)
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

        if let assetID = preparedJob.job.assetId {
            progress(0.28, "Starting cloud clip search")
            let job = try await createAssetAnalysisJob(
                baseURL: baseURL,
                assetID: assetID,
                installID: installID,
                appVersion: nil,
                analysisVersion: nil,
                teamSelection: teamSelection
            )
            onCloudHandoff?(job.jobId, job.storageKey)

            return try await pollJob(
                baseURL: baseURL,
                jobID: job.jobId,
                sourceObjectKey: job.storageKey,
                initialPollAfterSeconds: job.pollAfterSeconds,
                progress: progress
            )
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
        if let uploadExpiresAt = manifest.uploadExpiresAt,
           uploadExpiresAt <= Date().addingTimeInterval(60) {
            await CloudUploadResumeStore.shared.clearAnyManifest(reason: "upload_expired")
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "resume_manifest_upload_expired",
                metadata: "purpose=\(manifest.purpose.rawValue) completed=\(manifest.completedParts.count)/\(manifest.partCount)"
            )
            return nil
        }
        guard let baseURL = configuredBaseURL() else {
            throw CloudAnalysisError.notConfigured
        }

        let sourceURL = URL(fileURLWithPath: manifest.sourceFilePath)
        let sourceFileExists = FileManager.default.fileExists(atPath: sourceURL.path)
        let isSingleSourceUpload = manifest.uploadID.hasPrefix(cloudUploadSingleSourcePrefix)
        let isAssetUpload = manifest.assetID != nil
        let uploadPartsCompleted = manifest.completedParts.count >= manifest.partCount
        var assetCompletedParts = manifest.completedParts.sorted { $0.partNumber < $1.partNumber }
        guard sourceFileExists || uploadPartsCompleted else {
            await CloudUploadResumeStore.shared.clear(jobID: manifest.jobID, uploadID: manifest.uploadID)
            LaunchTelemetry.shared.recordBackgroundUploadProof("resume_manifest_source_missing")
            return nil
        }
        if !sourceFileExists {
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "resume_manifest_source_missing_but_upload_complete",
                metadata: "purpose=\(manifest.purpose.rawValue) partCount=\(manifest.partCount) singleSource=\(isSingleSourceUpload)"
            )
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
        var didInferCompletedSingleSourceUpload = false
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
            if manifest.uploadID.hasPrefix(cloudUploadSingleSourcePrefix),
               manifest.completedParts.isEmpty,
               sessionInspection.checkedCount > 0 {
                manifest.completedParts = await CloudUploadResumeStore.shared.recordCompletedPart(
                    jobID: manifest.jobID,
                    uploadID: manifest.uploadID,
                    partNumber: 1,
                    etag: "source-upload-session-finished"
                )
                didInferCompletedSingleSourceUpload = true
                LaunchTelemetry.shared.recordBackgroundUploadProof(
                    "resume_manifest_source_completion_inferred",
                    metadata: "reason=stale_empty_background_session"
                )
            }
        }
        assetCompletedParts = manifest.completedParts.sorted { $0.partNumber < $1.partNumber }
        if isSingleSourceUpload {
            guard !manifest.completedParts.isEmpty else {
                LaunchTelemetry.shared.recordBackgroundUploadProof("resume_manifest_source_still_uploading")
                return .pendingUpload
            }
            await tracker.update(uploadedBytes: manifest.totalFileSizeBytes, totalBytes: manifest.totalFileSizeBytes)
            let snapshot = await tracker.snapshot()
            reportUploadProgress(
                snapshot,
                false,
                didInferCompletedSingleSourceUpload
                    ? "source upload session finished; checking cloud"
                    : "source upload saved"
            )
        } else if !sourceFileExists, uploadPartsCompleted {
            let uploadedParts = manifest.completedParts.sorted { $0.partNumber < $1.partNumber }
            assetCompletedParts = uploadedParts
            if !isAssetUpload {
                try await completeMultipartUpload(
                    baseURL: baseURL,
                    jobID: manifest.jobID,
                    installID: manifest.installID,
                    uploadID: manifest.uploadID,
                    parts: uploadedParts
                )
            }
            await tracker.update(uploadedBytes: manifest.totalFileSizeBytes, totalBytes: manifest.totalFileSizeBytes)
            let snapshot = await tracker.snapshot()
            reportUploadProgress(snapshot, false, "saved chunks assembled; checking cloud")
            Self.recordLatestUploadProgressSummary(
                stage: stage,
                snapshot: snapshot,
                transferContext: "saved chunks assembled",
                stalled: false
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "resume_manifest_completed_chunks_assembled_without_source",
                metadata: "partCount=\(manifest.partCount)"
            )
        } else {
            if isAssetUpload {
                assetCompletedParts = try await resumeAssetUploadManifest(
                    manifest,
                    sourceURL: sourceURL,
                    tracker: tracker,
                    reportUploadProgress: reportUploadProgress
                )
            } else {
                try await resumeUploadManifest(
                    manifest,
                    sourceURL: sourceURL,
                    baseURL: baseURL,
                    tracker: tracker,
                    reportUploadProgress: reportUploadProgress
                )
            }
        }

        if let assetID = manifest.assetID {
            progress(min(progressEnd + 0.01, 0.35), "Preparing uploaded video")
            let completion = try await completeAssetUpload(
                baseURL: baseURL,
                assetID: assetID,
                installID: installID,
                uploadID: isSingleSourceUpload ? nil : manifest.uploadID,
                parts: isSingleSourceUpload ? [] : assetCompletedParts
            )
            let readyAsset = try await waitForAssetProxyReady(
                baseURL: baseURL,
                assetID: assetID,
                installID: installID,
                completion: completion,
                initialPollAfterSeconds: completion.pollAfterSeconds,
                progressStart: min(progressEnd + 0.01, 0.35),
                progressEnd: manifest.purpose == .teamScan ? 0.20 : 0.34,
                progress: progress
            )

            switch manifest.purpose {
            case .analysis:
                progress(0.35, "Starting cloud clip search")
                let job = try await createAssetAnalysisJob(
                    baseURL: baseURL,
                    assetID: readyAsset.assetID,
                    installID: installID,
                    appVersion: nil,
                    analysisVersion: nil,
                    teamSelection: teamSelection
                )
                onCloudHandoff?(job.jobId, job.storageKey)
                await CloudUploadResumeStore.shared.clearJob(jobID: assetID, reason: "resumed_asset_analysis_started")
                let result = try await pollJob(
                    baseURL: baseURL,
                    jobID: job.jobId,
                    sourceObjectKey: job.storageKey,
                    initialPollAfterSeconds: job.pollAfterSeconds,
                    progress: progress
                )
                return .analysis(result)
            case .teamScan:
                progress(0.20, "Scanning jersey colors")
                let scan = try await scanAssetTeams(baseURL: baseURL, assetID: readyAsset.assetID, installID: installID)
                await CloudUploadResumeStore.shared.clearJob(jobID: assetID, reason: "resumed_asset_team_scan_started")
                progress(0.24, scan.detectedTeams.isEmpty ? "Team scan unavailable" : "Team choices found")
                let job = CreateCloudAnalysisJobResponse(
                    jobId: readyAsset.assetID,
                    assetId: readyAsset.assetID,
                    storageKey: readyAsset.analysisStorageKey,
                    uploadUrl: "",
                    uploadMethod: "PUT",
                    uploadHeaders: [:],
                    expiresAt: Date(),
                    pollAfterSeconds: readyAsset.pollAfterSeconds,
                    quotaRemainingToday: 0,
                    analysisMode: "cloud",
                    sourceObjectKey: readyAsset.analysisStorageKey,
                    resultObjectKey: nil
                )
                return .teamScan(PreparedCloudAnalysisJob(sourceURL: sourceURL.standardizedFileURL, job: job, detectedTeams: scan.detectedTeams))
            }
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

    private func preparedUploadSource(
        originalURL: URL,
        duration: Double,
        originalFileSizeBytes: Int64,
        progressStage: String,
        progressValue: Double,
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async -> PreparedUploadSource {
        Self.cleanupStaleOptimizedUploadSources()

        let policy = CloudAnalysisProgressCopy.uploadSourceOptimization(
            durationSeconds: duration,
            fileSizeBytes: originalFileSizeBytes,
            statusMessage: "Preparing upload",
            latestUploadProgress: Self.latestUploadProgressSummary()
        )
        guard policy.shouldPreferOptimizedSource else {
            Self.recordUploadSourceOptimizationSummary(
                result: "original",
                reason: "policy_not_recommended",
                originalBytes: originalFileSizeBytes,
                optimizedBytes: nil
            )
            return PreparedUploadSource(
                url: originalURL.standardizedFileURL,
                originalURL: originalURL.standardizedFileURL,
                originalFileSizeBytes: originalFileSizeBytes,
                optimizedFileSizeBytes: nil,
                shouldCleanup: false
            )
        }

        progress(progressValue, progressStage)
        do {
            let optimizedExport = try await Self.exportOptimizedUploadSourceWithTimeout(
                from: originalURL,
                duration: duration,
                fileSizeBytes: originalFileSizeBytes
            )
            let optimizedURL = optimizedExport.url
            let optimizedBytes = try Self.fileSizeBytes(for: optimizedURL)
            let savedBytes = max(originalFileSizeBytes - optimizedBytes, 0)
            let savedFraction = originalFileSizeBytes > 0 ? Double(savedBytes) / Double(originalFileSizeBytes) : 0
            guard optimizedBytes > 0,
                  optimizedBytes < originalFileSizeBytes,
                  savedFraction >= 0.18 else {
                try? FileManager.default.removeItem(at: optimizedURL)
                Self.recordUploadSourceOptimizationSummary(
                    result: "fallback_original",
                    reason: "insufficient_savings",
                    originalBytes: originalFileSizeBytes,
                    optimizedBytes: optimizedBytes,
                    profile: optimizedExport.profile
                )
                return PreparedUploadSource(
                    url: originalURL.standardizedFileURL,
                    originalURL: originalURL.standardizedFileURL,
                    originalFileSizeBytes: originalFileSizeBytes,
                    optimizedFileSizeBytes: optimizedBytes,
                    shouldCleanup: false
                )
            }

            Self.prepareFileForBackgroundUpload(optimizedURL, context: "optimized_upload_source")
            Self.recordUploadSourceOptimizationSummary(
                result: "optimized",
                reason: optimizedExport.profile == "compact_540p" ? "compact_source_created" : "smaller_source_created",
                originalBytes: originalFileSizeBytes,
                optimizedBytes: optimizedBytes,
                profile: optimizedExport.profile
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "optimized_upload_source_created",
                metadata: "originalMB=\(Self.megabytes(originalFileSizeBytes)) optimizedMB=\(Self.megabytes(optimizedBytes)) profile=\(optimizedExport.profile) preset=\(Self.safeUploadPlanComponent(optimizedExport.presetName))"
            )
            return PreparedUploadSource(
                url: optimizedURL.standardizedFileURL,
                originalURL: originalURL.standardizedFileURL,
                originalFileSizeBytes: originalFileSizeBytes,
                optimizedFileSizeBytes: optimizedBytes,
                shouldCleanup: true
            )
        } catch OptimizedUploadSourceError.timedOut {
            Self.recordUploadSourceOptimizationSummary(
                result: "fallback_original",
                reason: "preparation_timed_out",
                originalBytes: originalFileSizeBytes,
                optimizedBytes: nil,
                profile: "timeout"
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "optimized_upload_source_timeout",
                metadata: "timeoutSeconds=\(optimizedUploadSourceTimeoutSeconds)"
            )
            return PreparedUploadSource(
                url: originalURL.standardizedFileURL,
                originalURL: originalURL.standardizedFileURL,
                originalFileSizeBytes: originalFileSizeBytes,
                optimizedFileSizeBytes: nil,
                shouldCleanup: false
            )
        } catch {
            Self.recordUploadSourceOptimizationSummary(
                result: "fallback_original",
                reason: "export_failed",
                originalBytes: originalFileSizeBytes,
                optimizedBytes: nil
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "optimized_upload_source_failed",
                metadata: "reason=export_failed"
            )
            return PreparedUploadSource(
                url: originalURL.standardizedFileURL,
                originalURL: originalURL.standardizedFileURL,
                originalFileSizeBytes: originalFileSizeBytes,
                optimizedFileSizeBytes: nil,
                shouldCleanup: false
            )
        }
    }

    private final class OptimizedUploadExportSessionBox: @unchecked Sendable {
        let exporter: AVAssetExportSession

        init(_ exporter: AVAssetExportSession) {
            self.exporter = exporter
        }
    }

    private static func exportOptimizedUploadSourceWithTimeout(
        from sourceURL: URL,
        duration: Double,
        fileSizeBytes: Int64
    ) async throws -> (url: URL, presetName: String, profile: String) {
        try await withThrowingTaskGroup(of: (url: URL, presetName: String, profile: String).self) { group in
            group.addTask {
                try await exportOptimizedUploadSource(
                    from: sourceURL,
                    duration: duration,
                    fileSizeBytes: fileSizeBytes
                )
            }
            group.addTask {
                try await Task.sleep(nanoseconds: optimizedUploadSourceTimeoutSeconds * 1_000_000_000)
                throw OptimizedUploadSourceError.timedOut
            }

            guard let result = try await group.next() else {
                throw CloudAnalysisError.uploadFailed
            }
            group.cancelAll()
            return result
        }
    }

    private static func exportOptimizedUploadSource(
        from sourceURL: URL,
        duration: Double,
        fileSizeBytes: Int64
    ) async throws -> (url: URL, presetName: String, profile: String) {
        let asset = AVURLAsset(url: sourceURL)
        let compatiblePresets = AVAssetExportSession.exportPresets(compatibleWith: asset)
        let preferCompactSource = duration >= compactOptimizedUploadDurationSeconds
            || fileSizeBytes >= compactOptimizedUploadFileSizeBytes
        let preferredPresets = preferCompactSource
            ? [AVAssetExportPreset960x540, AVAssetExportPreset1280x720, AVAssetExportPresetMediumQuality]
            : [AVAssetExportPreset1280x720, AVAssetExportPreset960x540, AVAssetExportPresetMediumQuality]
        let preset = preferredPresets.first { compatiblePresets.contains($0) }
        guard let preset,
              let exporter = AVAssetExportSession(asset: asset, presetName: preset) else {
            throw CloudAnalysisError.invalidVideo
        }
        let profile = optimizedUploadProfileName(for: preset)

        let directory = try optimizedUploadSourceDirectory()
        let outputURL = directory.appending(path: "optimized-upload-\(UUID().uuidString).mp4")
        try? FileManager.default.removeItem(at: outputURL)
        exporter.outputURL = outputURL
        exporter.outputFileType = .mp4
        exporter.shouldOptimizeForNetworkUse = true
        let exportBox = OptimizedUploadExportSessionBox(exporter)

        try await withTaskCancellationHandler(operation: {
            try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
                exportBox.exporter.exportAsynchronously {
                    switch exportBox.exporter.status {
                    case .completed:
                        continuation.resume(returning: ())
                    case .cancelled:
                        continuation.resume(throwing: CancellationError())
                    case .failed:
                        continuation.resume(throwing: exportBox.exporter.error ?? CloudAnalysisError.uploadFailed)
                    default:
                        continuation.resume(throwing: CloudAnalysisError.uploadFailed)
                    }
                }
            }
        }, onCancel: {
            exportBox.exporter.cancelExport()
        })

        return (url: outputURL, presetName: preset, profile: profile)
    }

    private static func optimizedUploadProfileName(for preset: String) -> String {
        switch preset {
        case AVAssetExportPreset960x540:
            return "compact_540p"
        case AVAssetExportPreset1280x720:
            return "balanced_720p"
        default:
            return "medium_quality"
        }
    }

    private static func optimizedUploadSourceDirectory() throws -> URL {
        let caches = try FileManager.default.url(
            for: .cachesDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )
        let directory = caches.appending(path: "HoopClipsOptimizedUploads", directoryHint: .isDirectory)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        return directory
    }

    private static func cleanupOptimizedUploadSourceIfNeeded(_ source: PreparedUploadSource) {
        guard source.shouldCleanup, source.url != source.originalURL else { return }
        try? FileManager.default.removeItem(at: source.url)
    }

    private static func cleanupStaleOptimizedUploadSources(
        now: Date = Date(),
        maximumAge: TimeInterval = optimizedUploadSourceMaximumAge
    ) {
        guard let directory = try? optimizedUploadSourceDirectory(),
              let files = try? FileManager.default.contentsOfDirectory(
                at: directory,
                includingPropertiesForKeys: [.contentModificationDateKey, .isRegularFileKey],
                options: [.skipsHiddenFiles]
              ) else {
            return
        }

        for file in files where file.pathExtension.lowercased() == "mp4" {
            guard let values = try? file.resourceValues(forKeys: [.contentModificationDateKey, .isRegularFileKey]),
                  values.isRegularFile == true else {
                continue
            }

            let modifiedAt = values.contentModificationDate ?? .distantPast
            guard now.timeIntervalSince(modifiedAt) > maximumAge else { continue }
            try? FileManager.default.removeItem(at: file)
        }
    }

    private static func fileSizeBytes(for url: URL) throws -> Int64 {
        let values = try url.resourceValues(forKeys: [.fileSizeKey])
        if let fileSize = values.fileSize, fileSize > 0 {
            return Int64(fileSize)
        }
        let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
        guard let fileSize = attributes[.size] as? NSNumber else {
            throw CloudAnalysisError.invalidVideo
        }
        return fileSize.int64Value
    }

    private nonisolated static func recordUploadSourceOptimizationSummary(
        result: String,
        reason: String,
        originalBytes: Int64,
        optimizedBytes: Int64?,
        profile: String = "none"
    ) {
        let originalMB = megabytes(originalBytes)
        let optimizedMB = optimizedBytes.map(megabytes) ?? -1
        let savedMB = optimizedBytes.map { max(megabytes(originalBytes - $0), 0) } ?? 0
        let summary = [
            "result=\(safeUploadPlanComponent(result))",
            "reason=\(safeUploadPlanComponent(reason))",
            "profile=\(safeUploadPlanComponent(profile))",
            "originalMB=\(originalMB)",
            optimizedBytes == nil ? "optimizedMB=none" : "optimizedMB=\(optimizedMB)",
            "savedMB=\(savedMB)",
            "pathPrivacy=no_local_paths"
        ].joined(separator: " ")
        UserDefaults.standard.set(summary, forKey: cloudUploadSourceOptimizationSummaryDefaultsKey)
    }

    private nonisolated static func megabytes(_ bytes: Int64) -> Int {
        max(0, Int((Double(max(bytes, 0)) / 1_048_576.0).rounded()))
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

    private func createAssetUploadIfSupported(
        baseURL: URL,
        request body: CloudAssetUploadInitRequest
    ) async throws -> CloudAssetUploadInitResponse? {
        do {
            return try await createAssetUpload(baseURL: baseURL, request: body)
        } catch {
            guard Self.shouldFallbackToLegacyUpload(after: error) else {
                throw error
            }
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "asset_upload_api_unavailable",
                metadata: "fallback=legacy_job_upload reason=\(Self.uploadRetryReason(for: error))"
            )
            return nil
        }
    }

    private func createAssetUpload(
        baseURL: URL,
        request body: CloudAssetUploadInitRequest
    ) async throws -> CloudAssetUploadInitResponse {
        var request = URLRequest(url: baseURL.appending(path: "v1/uploads/init"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(
            data: data,
            response: response,
            successType: CloudAssetUploadInitResponse.self
        )
    }

    private func uploadAsset(
        _ asset: CloudAssetUploadInitResponse,
        from url: URL,
        baseURL: URL,
        installID: String,
        purpose: CloudUploadResumePurpose,
        stage: String,
        progressStart: Double,
        progressEnd: Double,
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async throws -> CloudReadyAsset {
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
                    await MainActor.run {
                        LaunchTelemetry.shared.recordBackgroundUploadProof(
                            "upload_waiting_for_connectivity",
                            metadata: "kind=asset_source"
                        )
                    }
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
                if snapshot.secondsSinceProgress >= cloudUploadStallProofThresholdSeconds,
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
        let uploadPartCount = asset.multipart?.partCount ?? 1
        LaunchTelemetry.shared.resetBackgroundUploadProofTrail(reason: "fresh_asset_upload_started")
        Self.recordServerAssetUploadPlan(asset)
        defer {
            uploadMonitorTask.cancel()
        }
        Self.prepareFileForBackgroundUpload(url, context: "asset_source_file")

        if let multipart = asset.multipart, multipart.partCount > 1 {
            let initialSnapshot = await tracker.snapshot()
            Self.recordLatestUploadProgressSummary(
                stage: stage,
                snapshot: initialSnapshot,
                transferContext: "asset chunked upload starting",
                stalled: false
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "asset_chunked_upload_selected",
                metadata: "partCount=\(multipart.partCount) chunkSizeBytes=\(multipart.partSizeBytes)"
            )
            let parts = try await uploadAssetInChunks(
                asset: asset,
                multipart: multipart,
                from: url,
                installID: installID,
                purpose: purpose,
                totalFileSizeBytes: FileManager.default.fileExists(atPath: url.path) ? (try fileInfo(for: url).fileSizeBytes) : 0,
                tracker: tracker,
                reportUploadProgress: reportUploadProgress
            )
            progress(min(progressEnd + 0.01, 0.35), "Preparing uploaded video")
            let completion = try await completeAssetUpload(
                baseURL: baseURL,
                assetID: asset.assetId,
                installID: installID,
                uploadID: multipart.uploadId,
                parts: parts
            )
            return try await waitForAssetProxyReady(
                baseURL: baseURL,
                assetID: asset.assetId,
                installID: installID,
                completion: completion,
                initialPollAfterSeconds: completion.pollAfterSeconds,
                progressStart: min(progressEnd + 0.01, 0.35),
                progressEnd: purpose == .teamScan ? 0.20 : 0.34,
                progress: progress
            )
        }

        let sourceUploadID = Self.singleSourceUploadID(jobID: asset.assetId)
        let sourceSessionIdentifier = Self.backgroundUploadSessionIdentifier(jobID: asset.assetId)
        let fileSizeBytes = (try? fileInfo(for: url).fileSizeBytes) ?? 1
        _ = await CloudUploadResumeStore.shared.begin(
            jobID: asset.assetId,
            installID: installID,
            sourceURL: url.standardizedFileURL,
            uploadID: sourceUploadID,
            sourceObjectKey: asset.storageKey,
            resultObjectKey: nil,
            pollAfterSeconds: asset.pollAfterSeconds,
            purpose: purpose,
            chunkSizeBytes: Int(max(fileSizeBytes, 1)),
            partCount: 1,
            totalFileSizeBytes: max(fileSizeBytes, 1),
            assetID: asset.assetId,
            storageKey: asset.storageKey,
            assetMultipartParts: nil
        )
        await CloudUploadResumeStore.shared.recordSession(
            jobID: asset.assetId,
            uploadID: sourceUploadID,
            sessionIdentifier: sourceSessionIdentifier
        )
        let initialSnapshot = await tracker.snapshot()
        Self.recordLatestUploadProgressSummary(
            stage: stage,
            snapshot: initialSnapshot,
            transferContext: "asset source upload starting",
            stalled: false
        )
        let uploadSession = URLSession(
            configuration: Self.uploadSessionConfiguration(
                backgroundIdentifier: sourceSessionIdentifier
            ),
            delegate: delegate,
            delegateQueue: nil
        )
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "asset_source_session_started",
            metadata: "kind=asset_source chunked=false partCount=\(uploadPartCount)"
        )
        defer {
            uploadSession.finishTasksAndInvalidate()
        }

        do {
            guard let uploadUrlString = asset.uploadUrl,
                  let uploadURL = URL(string: uploadUrlString),
                  uploadURL.scheme?.isEmpty == false else {
                throw CloudAnalysisError.invalidResponse
            }
            var request = URLRequest(url: uploadURL)
            request.httpMethod = asset.uploadMethod
            for (header, value) in asset.uploadHeaders {
                request.setValue(value, forHTTPHeaderField: header)
            }

            let response = try await delegate.upload(request: request, fromFile: url, using: uploadSession)
            let finalSnapshot = await tracker.snapshot()
            Self.recordLatestUploadProgressSummary(
                stage: stage,
                snapshot: finalSnapshot,
                transferContext: "asset source upload complete",
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
                jobID: asset.assetId,
                uploadID: sourceUploadID,
                partNumber: 1,
                etag: "source-upload-complete"
            )
            await CloudUploadResumeStore.shared.clearActiveSession(
                jobID: asset.assetId,
                uploadID: sourceUploadID,
                sessionIdentifier: sourceSessionIdentifier
            )
        } catch {
            await CloudUploadResumeStore.shared.clearActiveSession(
                jobID: asset.assetId,
                uploadID: sourceUploadID,
                sessionIdentifier: sourceSessionIdentifier
            )
            let failedSnapshot = await tracker.snapshot()
            Self.recordLatestUploadProgressSummary(
                stage: stage,
                snapshot: failedSnapshot,
                transferContext: "asset source upload failed",
                stalled: true
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "asset_source_upload_failed",
                metadata: "reason=\(Self.uploadRetryReason(for: error))"
            )
            throw error
        }

        progress(min(progressEnd + 0.01, 0.35), "Preparing uploaded video")
        let completion = try await completeAssetUpload(
            baseURL: baseURL,
            assetID: asset.assetId,
            installID: installID,
            uploadID: nil,
            parts: []
        )
        return try await waitForAssetProxyReady(
            baseURL: baseURL,
            assetID: asset.assetId,
            installID: installID,
            completion: completion,
            initialPollAfterSeconds: completion.pollAfterSeconds,
            progressStart: min(progressEnd + 0.01, 0.35),
            progressEnd: purpose == .teamScan ? 0.20 : 0.34,
            progress: progress
        )
    }

    private func uploadAssetInChunks(
        asset: CloudAssetUploadInitResponse,
        multipart: CloudAssetMultipartUpload,
        from url: URL,
        installID: String,
        purpose: CloudUploadResumePurpose,
        totalFileSizeBytes: Int64,
        tracker: CloudUploadProgressTracker,
        reportUploadProgress: @escaping @Sendable (_ snapshot: CloudUploadProgressSnapshot, _ stalled: Bool, _ transferContext: String?) -> Void
    ) async throws -> [CloudMultipartCompletedPart] {
        let fileHandle = try FileHandle(forReadingFrom: url)
        defer {
            try? fileHandle.close()
        }

        let safeChunkSize = max(multipart.partSizeBytes, 1)
        let totalBytes = max(totalFileSizeBytes, 0)
        var uploadedParts = await CloudUploadResumeStore.shared.begin(
            jobID: asset.assetId,
            installID: installID,
            sourceURL: url.standardizedFileURL,
            uploadID: multipart.uploadId,
            sourceObjectKey: asset.storageKey,
            resultObjectKey: nil,
            pollAfterSeconds: asset.pollAfterSeconds,
            purpose: purpose,
            chunkSizeBytes: safeChunkSize,
            partCount: multipart.partCount,
            totalFileSizeBytes: totalBytes,
            assetID: asset.assetId,
            storageKey: asset.storageKey,
            assetMultipartParts: multipart.parts
        )
        var completedPartNumbers = Set(uploadedParts.map(\.partNumber))
        let initialCompletedBytes = Self.completedUploadBytes(
            completedParts: uploadedParts,
            chunkSizeBytes: safeChunkSize,
            totalFileSizeBytes: totalBytes
        )
        await tracker.update(uploadedBytes: initialCompletedBytes, totalBytes: totalBytes)
        let networkUploadPolicy = CloudUploadNetworkPolicy.shared.currentPolicy(
            defaultMaximum: Self.maxConcurrentMultipartUploads
        )
        let maxConcurrentUploads = min(max(multipart.partCount, 1), networkUploadPolicy.laneLimit)
        let progressAggregator = CloudMultipartUploadProgressAggregator(
            completedBytes: initialCompletedBytes,
            totalBytes: totalBytes,
            tracker: tracker
        )
        let targetsByPart = Dictionary(uniqueKeysWithValues: multipart.parts.compactMap { target -> (Int, CloudAssetUploadTarget)? in
            guard let partNumber = target.partNumber else { return nil }
            return (partNumber, target)
        })
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "asset_multipart_parallel_upload_selected",
            metadata: "lanes=\(maxConcurrentUploads) partCount=\(multipart.partCount) reason=\(networkUploadPolicy.reason) networkExpensive=\(networkUploadPolicy.isExpensive) networkConstrained=\(networkUploadPolicy.isConstrained)"
        )

        try await withThrowingTaskGroup(of: CloudMultipartCompletedPart.self) { group in
            var nextPartNumber = 1
            var inFlightUploads = 0

            while nextPartNumber <= multipart.partCount || inFlightUploads > 0 {
                while inFlightUploads < maxConcurrentUploads && nextPartNumber <= multipart.partCount {
                    try Task.checkCancellation()
                    let partNumber = nextPartNumber
                    nextPartNumber += 1
                    let offset = UInt64(partNumber - 1) * UInt64(safeChunkSize)
                    if completedPartNumbers.contains(partNumber) {
                        let snapshot = await tracker.snapshot()
                        reportUploadProgress(snapshot, false, "chunk \(partNumber)/\(multipart.partCount) saved")
                        continue
                    }
                    try fileHandle.seek(toOffset: offset)
                    guard let chunk = try fileHandle.read(upToCount: safeChunkSize), !chunk.isEmpty else {
                        nextPartNumber = multipart.partCount + 1
                        break
                    }
                    guard let uploadTarget = targetsByPart[partNumber] else {
                        throw CloudAnalysisError.invalidResponse
                    }

                    let partTarget = try CloudUploadPartTarget(assetID: asset.assetId, target: uploadTarget)
                    group.addTask {
                        let etag = try await Self.uploadMultipartChunk(
                            partTarget,
                            chunk: chunk,
                            alreadyUploadedBytes: min(Int64(offset), totalBytes),
                            totalBytes: totalBytes,
                            uploadID: multipart.uploadId,
                            partCount: multipart.partCount,
                            tracker: tracker,
                            progressAggregator: progressAggregator,
                            reportUploadProgress: reportUploadProgress
                        )
                        return CloudMultipartCompletedPart(partNumber: partNumber, etag: etag)
                    }
                    inFlightUploads += 1
                }

                guard inFlightUploads > 0 else {
                    break
                }

                if let completedPart = try await group.next() {
                    uploadedParts = await CloudUploadResumeStore.shared.recordCompletedPart(
                        jobID: asset.assetId,
                        uploadID: multipart.uploadId,
                        partNumber: completedPart.partNumber,
                        etag: completedPart.etag
                    )
                    completedPartNumbers.insert(completedPart.partNumber)
                    inFlightUploads -= 1
                }
            }
        }

        guard uploadedParts.count == multipart.partCount else {
            throw CloudAnalysisError.uploadFailed
        }

        await tracker.update(uploadedBytes: totalBytes, totalBytes: totalBytes)
        let finalSnapshot = await tracker.snapshot()
        reportUploadProgress(finalSnapshot, false, "asset chunks complete")
        Self.recordLatestUploadProgressSummary(
            stage: "Uploading video chunks",
            snapshot: finalSnapshot,
            transferContext: "asset chunks complete",
            stalled: false
        )
        return uploadedParts
    }

    private func completeAssetUpload(
        baseURL: URL,
        assetID: String,
        installID: String,
        uploadID: String?,
        parts: [CloudMultipartCompletedPart]
    ) async throws -> CloudAssetUploadCompleteResponse {
        var request = URLRequest(url: baseURL.appending(path: "v1/uploads/\(assetID)/complete"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(
            CloudAssetUploadCompleteRequest(
                installId: installID,
                uploadId: uploadID,
                parts: parts
            )
        )

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(
            data: data,
            response: response,
            successType: CloudAssetUploadCompleteResponse.self
        )
    }

    private func waitForAssetProxyReady(
        baseURL: URL,
        assetID: String,
        installID: String,
        completion: CloudAssetUploadCompleteResponse,
        initialPollAfterSeconds: Int,
        progressStart: Double,
        progressEnd: Double,
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async throws -> CloudReadyAsset {
        if Self.isAssetProxyReady(completion.status) {
            progress(progressEnd, "Uploaded video ready")
            return Self.readyAsset(
                assetID: completion.assetId,
                storageKey: completion.storageKey,
                artifacts: completion.artifacts,
                pollAfterSeconds: completion.pollAfterSeconds
            )
        }
        if Self.isAssetFailed(completion.status) {
            throw CloudAnalysisError.backend(
                code: "asset_processing_failed",
                message: "The uploaded video could not be prepared for cloud analysis."
            )
        }

        let timeoutNanos: UInt64 = Self.assetPollTimeoutSeconds * 1_000_000_000
        let deadline = DispatchTime.now().uptimeNanoseconds + timeoutNanos
        var pollDelay = max(1, initialPollAfterSeconds)

        while DispatchTime.now().uptimeNanoseconds < deadline {
            progress(progressStart, "Preparing first preview")
            try await Task.sleep(nanoseconds: UInt64(pollDelay) * 1_000_000_000)

            var components = URLComponents(url: baseURL.appending(path: "v1/assets/\(assetID)"), resolvingAgainstBaseURL: false)
            components?.queryItems = [URLQueryItem(name: "installId", value: installID)]
            guard let url = components?.url else {
                throw CloudAnalysisError.invalidResponse
            }
            let request = URLRequest(url: url)
            let (data, response) = try await session.data(for: request)
            let asset: CloudAssetStatusResponse = try decodeResponse(
                data: data,
                response: response,
                successType: CloudAssetStatusResponse.self
            )

            if Self.isAssetProxyReady(asset.status) {
                progress(progressEnd, "Uploaded video ready")
                return Self.readyAsset(
                    assetID: asset.assetId,
                    storageKey: asset.storageKey,
                    artifacts: asset.artifacts,
                    pollAfterSeconds: initialPollAfterSeconds
                )
            }
            if Self.isAssetFailed(asset.status) {
                throw CloudAnalysisError.backend(
                    code: "asset_processing_failed",
                    message: Self.safeBackendMessage(
                        asset.failureReason ?? "",
                        fallback: "The uploaded video could not be prepared for cloud analysis."
                    )
                )
            }

            let boundedProgress = progressStart + min(0.8, max(0.0, Double(asset.uploadedBytes) / Double(max(asset.fileSizeBytes, 1)))) * (progressEnd - progressStart)
            progress(boundedProgress, "Preparing first preview")
            pollDelay = min(pollDelay + 1, Self.maxPollDelaySeconds)
        }

        throw CloudAnalysisError.timedOut
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
                    await MainActor.run {
                        LaunchTelemetry.shared.recordBackgroundUploadProof(
                            "upload_waiting_for_connectivity",
                            metadata: "kind=source"
                        )
                    }
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
                if snapshot.secondsSinceProgress >= cloudUploadStallProofThresholdSeconds,
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
            totalFileSizeBytes: max(fileSizeBytes, 1),
            uploadExpiresAt: job.expiresAt
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
            configuration: Self.uploadSessionConfiguration(
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
            totalFileSizeBytes: totalBytes,
            uploadExpiresAt: resumableUpload.expiresAt
        )
        var completedPartNumbers = Set(uploadedParts.map(\.partNumber))
        let initialCompletedBytes = Self.completedUploadBytes(
            completedParts: uploadedParts,
            chunkSizeBytes: safeChunkSize,
            totalFileSizeBytes: totalBytes
        )
        await tracker.update(uploadedBytes: initialCompletedBytes, totalBytes: totalBytes)
        let networkUploadPolicy = CloudUploadNetworkPolicy.shared.currentPolicy(
            defaultMaximum: Self.maxConcurrentMultipartUploads
        )
        let maxConcurrentUploads = min(max(resumableUpload.partCount, 1), networkUploadPolicy.laneLimit)
        let progressAggregator = CloudMultipartUploadProgressAggregator(
            completedBytes: initialCompletedBytes,
            totalBytes: totalBytes,
            tracker: tracker
        )
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "multipart_parallel_upload_selected",
            metadata: "lanes=\(maxConcurrentUploads) partCount=\(resumableUpload.partCount) reason=\(networkUploadPolicy.reason) networkExpensive=\(networkUploadPolicy.isExpensive) networkConstrained=\(networkUploadPolicy.isConstrained)"
        )

        try await withThrowingTaskGroup(of: CloudMultipartCompletedPart.self) { group in
            var nextPartNumber = 1
            var inFlightUploads = 0

            while nextPartNumber <= resumableUpload.partCount || inFlightUploads > 0 {
                while inFlightUploads < maxConcurrentUploads && nextPartNumber <= resumableUpload.partCount {
                    try Task.checkCancellation()
                    let partNumber = nextPartNumber
                    nextPartNumber += 1
                    let offset = UInt64(partNumber - 1) * UInt64(safeChunkSize)
                    if completedPartNumbers.contains(partNumber) {
                        let snapshot = await tracker.snapshot()
                        reportUploadProgress(snapshot, false, "chunk \(partNumber)/\(resumableUpload.partCount) saved")
                        continue
                    }
                    try fileHandle.seek(toOffset: offset)
                    guard let chunk = try fileHandle.read(upToCount: safeChunkSize), !chunk.isEmpty else {
                        nextPartNumber = resumableUpload.partCount + 1
                        break
                    }

                    let partTarget = try await createMultipartPart(
                        baseURL: baseURL,
                        jobID: job.jobId,
                        installID: installID,
                        uploadID: resumableUpload.uploadId,
                        partNumber: partNumber
                    )
                    group.addTask {
                        let etag = try await Self.uploadMultipartChunk(
                            CloudUploadPartTarget(partTarget),
                            chunk: chunk,
                            alreadyUploadedBytes: min(Int64(offset), totalBytes),
                            totalBytes: totalBytes,
                            uploadID: resumableUpload.uploadId,
                            partCount: resumableUpload.partCount,
                            tracker: tracker,
                            progressAggregator: progressAggregator,
                            reportUploadProgress: reportUploadProgress
                        )
                        return CloudMultipartCompletedPart(partNumber: partNumber, etag: etag)
                    }
                    inFlightUploads += 1
                }

                guard inFlightUploads > 0 else {
                    break
                }

                if let completedPart = try await group.next() {
                    uploadedParts = await CloudUploadResumeStore.shared.recordCompletedPart(
                        jobID: job.jobId,
                        uploadID: resumableUpload.uploadId,
                        partNumber: completedPart.partNumber,
                        etag: completedPart.etag
                    )
                    completedPartNumbers.insert(completedPart.partNumber)
                    inFlightUploads -= 1
                }
            }
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

        let safeChunkSize = max(manifest.chunkSizeBytes, 5 * 1024 * 1024)
        let totalBytes = max(manifest.totalFileSizeBytes, 0)
        let jobID = manifest.jobID
        let installID = manifest.installID
        let uploadID = manifest.uploadID
        let partCount = manifest.partCount
        var uploadedParts = manifest.completedParts.sorted { $0.partNumber < $1.partNumber }
        var completedPartNumbers = Set(uploadedParts.map(\.partNumber))
        let initialCompletedBytes = Self.completedUploadBytes(
            completedParts: uploadedParts,
            chunkSizeBytes: safeChunkSize,
            totalFileSizeBytes: totalBytes
        )
        await tracker.update(uploadedBytes: initialCompletedBytes, totalBytes: totalBytes)

        let networkUploadPolicy = CloudUploadNetworkPolicy.shared.currentPolicy(
            defaultMaximum: Self.maxConcurrentMultipartUploads
        )
        let maxConcurrentUploads = min(max(partCount, 1), networkUploadPolicy.laneLimit)
        let progressAggregator = CloudMultipartUploadProgressAggregator(
            completedBytes: initialCompletedBytes,
            totalBytes: totalBytes,
            tracker: tracker
        )
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_parallel_upload_selected",
            metadata: "lanes=\(maxConcurrentUploads) completed=\(uploadedParts.count) partCount=\(partCount) reason=\(networkUploadPolicy.reason) networkExpensive=\(networkUploadPolicy.isExpensive) networkConstrained=\(networkUploadPolicy.isConstrained)"
        )

        try await withThrowingTaskGroup(of: CloudMultipartCompletedPart.self) { group in
            var nextPartNumber = 1
            var inFlightUploads = 0

            while nextPartNumber <= partCount || inFlightUploads > 0 {
                while inFlightUploads < maxConcurrentUploads && nextPartNumber <= partCount {
                    try Task.checkCancellation()
                    let partNumber = nextPartNumber
                    nextPartNumber += 1
                    let offset = UInt64(partNumber - 1) * UInt64(safeChunkSize)

                    if completedPartNumbers.contains(partNumber) {
                        let snapshot = await tracker.snapshot()
                        reportUploadProgress(snapshot, false, "chunk \(partNumber)/\(partCount) saved")
                        Self.recordLatestUploadProgressSummary(
                            stage: "Resuming cloud upload",
                            snapshot: snapshot,
                            transferContext: "chunk \(partNumber)/\(partCount) saved",
                            stalled: false
                        )
                        continue
                    }

                    try fileHandle.seek(toOffset: offset)
                    guard let chunk = try fileHandle.read(upToCount: safeChunkSize), !chunk.isEmpty else {
                        nextPartNumber = partCount + 1
                        break
                    }

                    let partTarget = try await createMultipartPart(
                        baseURL: baseURL,
                        jobID: jobID,
                        installID: installID,
                        uploadID: uploadID,
                        partNumber: partNumber
                    )
                    group.addTask {
                        let etag = try await Self.uploadMultipartChunk(
                            CloudUploadPartTarget(partTarget),
                            chunk: chunk,
                            alreadyUploadedBytes: min(Int64(offset), totalBytes),
                            totalBytes: totalBytes,
                            uploadID: uploadID,
                            partCount: partCount,
                            tracker: tracker,
                            progressAggregator: progressAggregator,
                            reportUploadProgress: reportUploadProgress
                        )
                        return CloudMultipartCompletedPart(partNumber: partNumber, etag: etag)
                    }
                    inFlightUploads += 1
                }

                guard inFlightUploads > 0 else {
                    break
                }

                if let completedPart = try await group.next() {
                    uploadedParts = await CloudUploadResumeStore.shared.recordCompletedPart(
                        jobID: jobID,
                        uploadID: uploadID,
                        partNumber: completedPart.partNumber,
                        etag: completedPart.etag
                    )
                    completedPartNumbers.insert(completedPart.partNumber)
                    inFlightUploads -= 1
                }
            }
        }

        guard uploadedParts.count == partCount else {
            throw CloudAnalysisError.uploadFailed
        }

        try await completeMultipartUpload(
            baseURL: baseURL,
            jobID: jobID,
            installID: installID,
            uploadID: uploadID,
            parts: uploadedParts
        )
        await tracker.update(uploadedBytes: totalBytes, totalBytes: totalBytes)
        let finalSnapshot = await tracker.snapshot()
        reportUploadProgress(finalSnapshot, false, "resumed chunks complete")
        Self.recordLatestUploadProgressSummary(
            stage: "Resuming cloud upload",
            snapshot: finalSnapshot,
            transferContext: "resumed chunks complete",
            stalled: false
        )
    }

    private func resumeAssetUploadManifest(
        _ manifest: CloudUploadResumeManifest,
        sourceURL: URL,
        tracker: CloudUploadProgressTracker,
        reportUploadProgress: @escaping @Sendable (_ snapshot: CloudUploadProgressSnapshot, _ stalled: Bool, _ transferContext: String?) -> Void
    ) async throws -> [CloudMultipartCompletedPart] {
        guard let assetID = manifest.assetID,
              let assetMultipartParts = manifest.assetMultipartParts,
              !assetMultipartParts.isEmpty else {
            throw CloudAnalysisError.invalidResponse
        }

        let fileHandle = try FileHandle(forReadingFrom: sourceURL)
        defer {
            try? fileHandle.close()
        }

        let safeChunkSize = max(manifest.chunkSizeBytes, 1)
        let totalBytes = max(manifest.totalFileSizeBytes, 0)
        let uploadID = manifest.uploadID
        let partCount = manifest.partCount
        var uploadedParts = manifest.completedParts.sorted { $0.partNumber < $1.partNumber }
        var completedPartNumbers = Set(uploadedParts.map(\.partNumber))
        let initialCompletedBytes = Self.completedUploadBytes(
            completedParts: uploadedParts,
            chunkSizeBytes: safeChunkSize,
            totalFileSizeBytes: totalBytes
        )
        await tracker.update(uploadedBytes: initialCompletedBytes, totalBytes: totalBytes)

        let networkUploadPolicy = CloudUploadNetworkPolicy.shared.currentPolicy(
            defaultMaximum: Self.maxConcurrentMultipartUploads
        )
        let maxConcurrentUploads = min(max(partCount, 1), networkUploadPolicy.laneLimit)
        let progressAggregator = CloudMultipartUploadProgressAggregator(
            completedBytes: initialCompletedBytes,
            totalBytes: totalBytes,
            tracker: tracker
        )
        let targetsByPart = Dictionary(uniqueKeysWithValues: assetMultipartParts.compactMap { target -> (Int, CloudAssetUploadTarget)? in
            guard let partNumber = target.partNumber else { return nil }
            return (partNumber, target)
        })
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_asset_manifest_parallel_upload_selected",
            metadata: "lanes=\(maxConcurrentUploads) completed=\(uploadedParts.count) partCount=\(partCount) reason=\(networkUploadPolicy.reason) networkExpensive=\(networkUploadPolicy.isExpensive) networkConstrained=\(networkUploadPolicy.isConstrained)"
        )

        try await withThrowingTaskGroup(of: CloudMultipartCompletedPart.self) { group in
            var nextPartNumber = 1
            var inFlightUploads = 0

            while nextPartNumber <= partCount || inFlightUploads > 0 {
                while inFlightUploads < maxConcurrentUploads && nextPartNumber <= partCount {
                    try Task.checkCancellation()
                    let partNumber = nextPartNumber
                    nextPartNumber += 1
                    let offset = UInt64(partNumber - 1) * UInt64(safeChunkSize)

                    if completedPartNumbers.contains(partNumber) {
                        let snapshot = await tracker.snapshot()
                        reportUploadProgress(snapshot, false, "chunk \(partNumber)/\(partCount) saved")
                        Self.recordLatestUploadProgressSummary(
                            stage: "Resuming cloud upload",
                            snapshot: snapshot,
                            transferContext: "chunk \(partNumber)/\(partCount) saved",
                            stalled: false
                        )
                        continue
                    }

                    try fileHandle.seek(toOffset: offset)
                    guard let chunk = try fileHandle.read(upToCount: safeChunkSize), !chunk.isEmpty else {
                        nextPartNumber = partCount + 1
                        break
                    }
                    guard let uploadTarget = targetsByPart[partNumber] else {
                        throw CloudAnalysisError.invalidResponse
                    }

                    let partTarget = try CloudUploadPartTarget(assetID: assetID, target: uploadTarget)
                    group.addTask {
                        let etag = try await Self.uploadMultipartChunk(
                            partTarget,
                            chunk: chunk,
                            alreadyUploadedBytes: min(Int64(offset), totalBytes),
                            totalBytes: totalBytes,
                            uploadID: uploadID,
                            partCount: partCount,
                            tracker: tracker,
                            progressAggregator: progressAggregator,
                            reportUploadProgress: reportUploadProgress
                        )
                        return CloudMultipartCompletedPart(partNumber: partNumber, etag: etag)
                    }
                    inFlightUploads += 1
                }

                guard inFlightUploads > 0 else {
                    break
                }

                if let completedPart = try await group.next() {
                    uploadedParts = await CloudUploadResumeStore.shared.recordCompletedPart(
                        jobID: assetID,
                        uploadID: uploadID,
                        partNumber: completedPart.partNumber,
                        etag: completedPart.etag
                    )
                    completedPartNumbers.insert(completedPart.partNumber)
                    inFlightUploads -= 1
                }
            }
        }

        guard uploadedParts.count == partCount else {
            throw CloudAnalysisError.uploadFailed
        }

        await tracker.update(uploadedBytes: totalBytes, totalBytes: totalBytes)
        let finalSnapshot = await tracker.snapshot()
        reportUploadProgress(finalSnapshot, false, "resumed asset chunks complete")
        Self.recordLatestUploadProgressSummary(
            stage: "Resuming cloud upload",
            snapshot: finalSnapshot,
            transferContext: "resumed asset chunks complete",
            stalled: false
        )
        return uploadedParts
    }

    private static func uploadMultipartChunk(
        _ partTarget: CloudUploadPartTarget,
        chunk: Data,
        alreadyUploadedBytes: Int64,
        totalBytes: Int64,
        uploadID: String,
        partCount: Int,
        tracker: CloudUploadProgressTracker,
        progressAggregator: CloudMultipartUploadProgressAggregator? = nil,
        reportUploadProgress: @escaping @Sendable (_ snapshot: CloudUploadProgressSnapshot, _ stalled: Bool, _ transferContext: String?) -> Void
    ) async throws -> String {
        guard let uploadURL = URL(string: partTarget.uploadUrl) else {
            throw CloudAnalysisError.invalidResponse
        }

        var lastError: Error?
        let maxAttempts = cloudUploadChunkRetryBackoffSeconds.count + 1
        for attempt in 0..<maxAttempts {
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
                            let snapshot: CloudUploadProgressSnapshot
                            if let progressAggregator {
                                snapshot = await progressAggregator.recordPartProgress(
                                    partNumber: partTarget.partNumber,
                                    sentBytes: sentBytes
                                )
                            } else {
                                await tracker.update(uploadedBytes: alreadyUploadedBytes + sentBytes, totalBytes: totalBytes)
                                snapshot = await tracker.snapshot()
                            }
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
                            await MainActor.run {
                                LaunchTelemetry.shared.recordBackgroundUploadProof(
                                    "upload_waiting_for_connectivity",
                                    metadata: "kind=chunk partNumber=\(partTarget.partNumber) partCount=\(partCount) attempt=\(attempt + 1)"
                                )
                            }
                        }
                    }
                )
                let chunkFileURL = try CloudUploadChunkFileStore.writeChunk(chunk, jobID: partTarget.jobId, partNumber: partTarget.partNumber)
                Self.prepareFileForBackgroundUpload(chunkFileURL, context: "chunk_\(partTarget.partNumber)")

                await CloudUploadResumeStore.shared.recordSession(
                    jobID: partTarget.jobId,
                    uploadID: uploadID,
                    sessionIdentifier: backgroundIdentifier
                )

                let uploadSession = URLSession(
                    configuration: Self.uploadSessionConfiguration(
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
                try? FileManager.default.removeItem(at: chunkFileURL)
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                    throw CloudAnalysisError.uploadFailed
                }
                guard let etag = Self.headerValue("ETag", from: http), !etag.isEmpty else {
                    throw CloudAnalysisError.invalidResponse
                }
                let snapshot: CloudUploadProgressSnapshot
                if let progressAggregator {
                    snapshot = await progressAggregator.recordPartCompleted(
                        partNumber: partTarget.partNumber,
                        partBytes: Int64(chunk.count)
                    )
                } else {
                    await tracker.update(uploadedBytes: alreadyUploadedBytes + Int64(chunk.count), totalBytes: totalBytes)
                    snapshot = await tracker.snapshot()
                }
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
                let retrying = attemptNumber < maxAttempts
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
                let retryDelaySeconds = retrying ? Self.chunkRetryBackoffSeconds(afterAttempt: attemptNumber) : 0
                let retryContext = retryDelaySeconds > 0
                    ? "chunk \(partTarget.partNumber)/\(partCount) retrying in \(retryDelaySeconds)s after try \(attemptNumber)"
                    : "chunk \(partTarget.partNumber)/\(partCount) retrying after try \(attemptNumber)"
                let failedContext = "chunk \(partTarget.partNumber)/\(partCount) failed after try \(attemptNumber)"
                reportUploadProgress(
                    snapshot,
                    true,
                    retrying ? retryContext : failedContext
                )
                Self.recordLatestUploadProgressSummary(
                    stage: "Uploading video chunk",
                    snapshot: snapshot,
                    transferContext: retrying ? retryContext : failedContext,
                    stalled: true
                )
                if retryDelaySeconds > 0 {
                    LaunchTelemetry.shared.recordBackgroundUploadProof(
                        "chunk_retry_backoff",
                        metadata: "kind=chunk partNumber=\(partTarget.partNumber) attempt=\(attemptNumber) delaySeconds=\(retryDelaySeconds)"
                    )
                    try await Task.sleep(nanoseconds: retryDelaySeconds * 1_000_000_000)
                }
            }
        }

        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "chunk_upload_failed",
            metadata: "kind=chunk partNumber=\(partTarget.partNumber) partCount=\(partCount) attempts=\(maxAttempts) reason=\(Self.uploadRetryReason(for: lastError))"
        )
        throw lastError ?? CloudAnalysisError.uploadFailed
    }

    private static func chunkRetryBackoffSeconds(afterAttempt attemptNumber: Int) -> UInt64 {
        guard !cloudUploadChunkRetryBackoffSeconds.isEmpty else { return 0 }
        let index = min(max(attemptNumber - 1, 0), cloudUploadChunkRetryBackoffSeconds.count - 1)
        return cloudUploadChunkRetryBackoffSeconds[index]
    }

    private static func multipartUploadConcurrency(partCount: Int) -> Int {
        let networkPolicy = CloudUploadNetworkPolicy.shared.currentPolicy(
            defaultMaximum: maxConcurrentMultipartUploads
        )
        return min(max(partCount, 1), networkPolicy.laneLimit)
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

    private static func shouldFallbackToLegacyUpload(after error: Error) -> Bool {
        guard case CloudAnalysisError.backend(let code, _) = error else {
            return false
        }
        switch code.lowercased() {
        case "http_404", "not_found", "route_not_found", "endpoint_not_found":
            return true
        default:
            return false
        }
    }

    private static func isAssetProxyReady(_ status: String) -> Bool {
        let normalized = status.lowercased()
        return normalized == "proxy_ready" || normalized == "ready"
    }

    private static func isAssetFailed(_ status: String) -> Bool {
        let normalized = status.lowercased()
        return normalized == "failed" || normalized == "error"
    }

    private static func readyAsset(
        assetID: String,
        storageKey: String,
        artifacts: CloudAssetArtifacts,
        pollAfterSeconds: Int
    ) -> CloudReadyAsset {
        CloudReadyAsset(
            assetID: assetID,
            storageKey: storageKey,
            analysisStorageKey: artifacts.proxyStorageKey ?? storageKey,
            pollAfterSeconds: pollAfterSeconds
        )
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

    private static func uploadSessionConfiguration(backgroundIdentifier: String? = nil) -> URLSessionConfiguration {
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

    private func createAssetAnalysisJob(
        baseURL: URL,
        assetID: String,
        installID: String,
        appVersion: String?,
        analysisVersion: String?,
        teamSelection: HighlightTeamSelection? = nil
    ) async throws -> CloudAssetAnalysisJobResponse {
        var request = URLRequest(url: baseURL.appending(path: "v1/assets/\(assetID)/analysis-jobs"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(
            CloudAssetAnalysisJobRequest(
                installId: installID,
                appVersion: appVersion,
                analysisVersion: analysisVersion,
                teamSelection: teamSelection
            )
        )

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(
            data: data,
            response: response,
            successType: CloudAssetAnalysisJobResponse.self
        )
    }

    private func scanAssetTeams(
        baseURL: URL,
        assetID: String,
        installID: String
    ) async throws -> ScanCloudAnalysisTeamsResponse {
        var request = URLRequest(url: baseURL.appending(path: "v1/assets/\(assetID)/team-scan"))
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
            if http.statusCode == 410,
               apiError?.errorCode == "upload_expired" {
                throw CloudAnalysisError.backend(
                    code: "upload_expired",
                    message: "Upload expired. Tap AI Analysis again to start a fresh cloud upload."
                )
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

private struct CloudUploadNetworkLanePolicy {
    let laneLimit: Int
    let reason: String
    let isExpensive: Bool
    let isConstrained: Bool
}

private final class CloudUploadNetworkPolicy: @unchecked Sendable {
    static let shared = CloudUploadNetworkPolicy()

    private let monitor = NWPathMonitor()
    private let monitorQueue = DispatchQueue(label: "hoopsclips.cloud-upload.network-policy")
    private let lock = NSLock()
    private var latestPath: NWPath?

    private init() {
        monitor.pathUpdateHandler = { [weak self] path in
            self?.lock.lock()
            self?.latestPath = path
            self?.lock.unlock()
        }
        monitor.start(queue: monitorQueue)
    }

    func currentPolicy(defaultMaximum: Int) -> CloudUploadNetworkLanePolicy {
        let safeMaximum = max(defaultMaximum, 1)

        lock.lock()
        let path = latestPath
        lock.unlock()

        guard let path else {
            return CloudUploadNetworkLanePolicy(
                laneLimit: safeMaximum,
                reason: "network_pending",
                isExpensive: false,
                isConstrained: false
            )
        }

        if path.isConstrained {
            return CloudUploadNetworkLanePolicy(
                laneLimit: 1,
                reason: "low_data_mode",
                isExpensive: path.isExpensive,
                isConstrained: true
            )
        }

        if path.isExpensive {
            return CloudUploadNetworkLanePolicy(
                laneLimit: min(safeMaximum, 2),
                reason: "expensive_network",
                isExpensive: true,
                isConstrained: false
            )
        }

        return CloudUploadNetworkLanePolicy(
            laneLimit: safeMaximum,
            reason: "normal_network",
            isExpensive: false,
            isConstrained: false
        )
    }
}

nonisolated private enum CloudUploadChunkFileStore {
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
            recordBackgroundUploadProof("background_upload_chunk_directory_ready")
        } catch {
            recordBackgroundUploadProof("background_upload_chunk_directory_protection_unavailable")
        }
    }

    private static func recordBackgroundUploadProof(_ event: String) {
        Task { @MainActor in
            LaunchTelemetry.shared.recordBackgroundUploadProof(event)
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
        Self.recordBackgroundUploadProof("events_received", metadata: "source=app_delegate reattached=true")

        session.getAllTasks { tasks in
            Self.recordBackgroundUploadProof(
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
        let session = sessionForInspection(identifier: identifier)
        let tasks = await Self.allTasks(in: session)
        Self.recordBackgroundUploadProof(
            "reattached_session_foreground_checked",
            metadata: "source=foreground_resume taskCount=\(tasks.count)"
        )
        if tasks.isEmpty {
            finishEvents(for: identifier)
        }
        return tasks.count
    }

    private func sessionForInspection(identifier: String) -> URLSession {
        lock.lock()
        defer { lock.unlock() }

        if let existingSession = relaunchSessions[identifier] {
            return existingSession
        }

        let delegate = CloudUploadBackgroundRelaunchDelegate(identifier: identifier)
        let configuration = URLSessionConfiguration.background(withIdentifier: identifier)
        configuration.applyHoopsCloudUploadPolicy(isBackgroundTransfer: true)
        let session = URLSession(configuration: configuration, delegate: delegate, delegateQueue: nil)
        relaunchDelegates[identifier] = delegate
        relaunchSessions[identifier] = session
        return session
    }

    private static func allTasks(in session: URLSession) async -> [URLSessionTask] {
        await withCheckedContinuation { continuation in
            session.getAllTasks { tasks in
                continuation.resume(returning: tasks)
            }
        }
    }

    private func recheckEmptySessionBeforeFinishing(identifier: String, session: URLSession) {
        Self.recordBackgroundUploadProof(
            "reattached_session_empty_recheck_scheduled",
            metadata: "source=app_delegate delayMs=750"
        )
        DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + 0.75) {
            session.getAllTasks { tasks in
                Self.recordBackgroundUploadProof(
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

        Self.recordBackgroundUploadProof(
            "events_finish_requested",
            metadata: [
                "source=urlsession_delegate",
                "hadCompletionHandler=\(completionHandler != nil)",
                "hadRelaunchSession=\(session != nil)",
                "privacy=no_raw_session_ids_no_urls_no_object_keys"
            ].joined(separator: " ")
        )

        session?.finishTasksAndInvalidate()

        guard let completionHandler else {
            Self.recordBackgroundUploadProof(
                "events_finished_without_completion_handler",
                metadata: "source=urlsession_delegate privacy=no_raw_session_ids_no_urls_no_object_keys"
            )
            return
        }
        DispatchQueue.main.async {
            completionHandler()
            Self.recordBackgroundUploadProof("events_completed", metadata: "source=urlsession_delegate")
        }
    }

    private static func recordBackgroundUploadProof(_ event: String, metadata: String? = nil) {
        Task { @MainActor in
            LaunchTelemetry.shared.recordBackgroundUploadProof(event, metadata: metadata)
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
            timeoutIntervalForRequest = cloudUploadBackgroundRequestTimeoutSeconds
            timeoutIntervalForResource = cloudUploadBackgroundResourceTimeoutSeconds
        } else {
            timeoutIntervalForRequest = cloudUploadForegroundRequestTimeoutSeconds
            timeoutIntervalForResource = cloudUploadForegroundResourceTimeoutSeconds
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
            Self.recordBackgroundUploadProof(
                "relaunch_task_failed",
                metadata: "source=urlsession_delegate reason=\(reason)"
            )
        } else {
            guard let http = task.response as? HTTPURLResponse else {
                CloudAnalysisService.recordRelaunchedUploadProgressSummary(
                    event: "relaunch_task_no_http_response",
                    reason: "no_http_response"
                )
                Self.recordBackgroundUploadProof(
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
                Self.recordBackgroundUploadProof(
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
                    Self.recordBackgroundUploadProof(
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
            Self.recordBackgroundUploadProof(
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
            Self.recordBackgroundUploadProof(
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
            Self.recordBackgroundUploadProof(
                "manifest_persistence_finished",
                metadata: "source=urlsession_delegate"
            )
            CloudUploadBackgroundSessionRegistry.shared.finishEvents(for: identifier)
        }
    }

    private static func recordBackgroundUploadProof(_ event: String, metadata: String? = nil) {
        Task { @MainActor in
            LaunchTelemetry.shared.recordBackgroundUploadProof(event, metadata: metadata)
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

nonisolated private struct CloudUploadResumeManifest: Codable, Sendable {
    var jobID: String
    var installID: String
    var sourceFilePath: String
    var uploadID: String
    var sourceObjectKey: String?
    var resultObjectKey: String?
    var assetID: String?
    var storageKey: String?
    var assetMultipartParts: [CloudAssetUploadTarget]?
    var pollAfterSeconds: Int
    var purpose: CloudUploadResumePurpose
    var chunkSizeBytes: Int
    var partCount: Int
    var totalFileSizeBytes: Int64
    var completedParts: [CloudMultipartCompletedPart]
    var activeSessionIdentifiers: [String]
    var uploadExpiresAt: Date?
    var createdAt: Date
    var updatedAt: Date
}

private actor CloudUploadResumeStore {
    static let shared = CloudUploadResumeStore()

    private nonisolated static let manifestDefaultsKey = "hoopsclips.cloudUpload.resumeManifest.v1"
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
        totalFileSizeBytes: Int64,
        assetID: String? = nil,
        storageKey: String? = nil,
        assetMultipartParts: [CloudAssetUploadTarget]? = nil,
        uploadExpiresAt: Date? = nil
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
                assetID: assetID,
                storageKey: storageKey,
                assetMultipartParts: assetMultipartParts,
                pollAfterSeconds: pollAfterSeconds,
                purpose: purpose,
                chunkSizeBytes: chunkSizeBytes,
                partCount: partCount,
                totalFileSizeBytes: totalFileSizeBytes,
                completedParts: [],
                activeSessionIdentifiers: [],
                uploadExpiresAt: uploadExpiresAt,
                createdAt: Date(),
                updatedAt: Date()
            )
        }

        if let assetID {
            manifest?.assetID = assetID
        }
        if let storageKey {
            manifest?.storageKey = storageKey
        }
        if let assetMultipartParts {
            manifest?.assetMultipartParts = assetMultipartParts
        }
        if let uploadExpiresAt {
            manifest?.uploadExpiresAt = uploadExpiresAt
        }
        manifest?.updatedAt = Date()
        saveManifest(manifest)
        Self.recordBackgroundUploadProof(
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
        Self.recordBackgroundUploadProof(
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
        Self.recordBackgroundUploadProof(
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
        Self.recordBackgroundUploadProof(
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
        Self.recordBackgroundUploadProof(
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
            Self.recordBackgroundUploadProof("resume_manifest_relaunch_part_ignored")
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
        Self.recordBackgroundUploadProof(
            "resume_manifest_relaunch_part_completed",
            metadata: "completed=\(manifest.completedParts.count) partCount=\(manifest.partCount) activeSessions=\(manifest.activeSessionIdentifiers.count)"
        )
        if uploadCompleted {
            Self.recordBackgroundUploadProof(
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
            Self.recordBackgroundUploadProof("resume_manifest_relaunch_source_ignored")
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
        Self.recordBackgroundUploadProof(
            "resume_manifest_relaunch_source_completed",
            metadata: "completed=\(manifest.completedParts.count) partCount=\(manifest.partCount) activeSessions=\(manifest.activeSessionIdentifiers.count)"
        )
        if uploadCompleted {
            Self.recordBackgroundUploadProof(
                "resume_manifest_relaunch_upload_completed",
                metadata: "purpose=\(manifest.purpose.rawValue) partCount=\(manifest.partCount)"
            )
        }
        return uploadCompleted
    }

    func clear(jobID: String, uploadID: String) {
        guard let manifest = loadMatchingManifest(jobID: jobID, uploadID: uploadID) else { return }
        UserDefaults.standard.removeObject(forKey: Self.manifestDefaultsKey)
        CloudUploadChunkFileStore.clearChunks(jobID: manifest.jobID)
        Self.recordBackgroundUploadProof(
            "resume_manifest_cleared",
            metadata: "completed=\(manifest.completedParts.count) partCount=\(manifest.partCount)"
        )
    }

    func clearAnyManifest(reason: String) {
        guard let manifest = loadManifest() else { return }
        UserDefaults.standard.removeObject(forKey: Self.manifestDefaultsKey)
        CloudUploadChunkFileStore.clearChunks(jobID: manifest.jobID)
        Self.recordBackgroundUploadProof(
            "resume_manifest_cleared",
            metadata: "reason=\(reason) completed=\(manifest.completedParts.count) partCount=\(manifest.partCount)"
        )
    }

    func clearJob(jobID: String, reason: String) {
        guard let manifest = loadManifest(),
              manifest.jobID == jobID else {
            return
        }
        UserDefaults.standard.removeObject(forKey: Self.manifestDefaultsKey)
        CloudUploadChunkFileStore.clearChunks(jobID: manifest.jobID)
        Self.recordBackgroundUploadProof(
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
        guard let data = UserDefaults.standard.data(forKey: Self.manifestDefaultsKey) else { return nil }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try? decoder.decode(CloudUploadResumeManifest.self, from: data)
    }

    private func saveManifest(_ manifest: CloudUploadResumeManifest?) {
        guard let manifest,
              let data = try? encoder.encode(manifest) else {
            UserDefaults.standard.removeObject(forKey: Self.manifestDefaultsKey)
            return
        }
        UserDefaults.standard.set(data, forKey: Self.manifestDefaultsKey)
    }

    private nonisolated static func recordBackgroundUploadProof(_ event: String, metadata: String? = nil) {
        Task { @MainActor in
            LaunchTelemetry.shared.recordBackgroundUploadProof(event, metadata: metadata)
        }
    }
}

private enum OptimizedUploadSourceError: Error {
    case timedOut
}

private struct PreparedUploadSource: Sendable {
    let url: URL
    let originalURL: URL
    let originalFileSizeBytes: Int64
    let optimizedFileSizeBytes: Int64?
    let shouldCleanup: Bool

    var filename: String {
        optimizedFileSizeBytes == nil ? originalURL.lastPathComponent : url.lastPathComponent
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

private actor CloudMultipartUploadProgressAggregator {
    private let totalBytes: Int64
    private let tracker: CloudUploadProgressTracker
    private var completedBytes: Int64
    private var activePartBytes: [Int: Int64] = [:]

    init(completedBytes: Int64, totalBytes: Int64, tracker: CloudUploadProgressTracker) {
        self.completedBytes = max(completedBytes, 0)
        self.totalBytes = max(totalBytes, 0)
        self.tracker = tracker
    }

    func recordPartProgress(partNumber: Int, sentBytes: Int64) async -> CloudUploadProgressSnapshot {
        let currentPartBytes = activePartBytes[partNumber] ?? 0
        activePartBytes[partNumber] = max(currentPartBytes, sentBytes, 0)
        return await pushProgress()
    }

    func recordPartCompleted(partNumber: Int, partBytes: Int64) async -> CloudUploadProgressSnapshot {
        activePartBytes[partNumber] = nil
        completedBytes = min(totalBytes, completedBytes + max(partBytes, 0))
        return await pushProgress()
    }

    private func pushProgress() async -> CloudUploadProgressSnapshot {
        let activeBytes = activePartBytes.values.reduce(Int64(0)) { partial, sentBytes in
            partial + max(sentBytes, 0)
        }
        let uploadedBytes = min(totalBytes, completedBytes + activeBytes)
        await tracker.update(uploadedBytes: uploadedBytes, totalBytes: totalBytes)
        return await tracker.snapshot()
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
            Self.handleUploadTaskCancellation(for: session)
        })
    }

    private static func handleUploadTaskCancellation(for session: URLSession) {
        if session.configuration.identifier != nil {
            CloudAnalysisService.recordRelaunchedUploadProgressSummary(
                event: "background_task_cancel_detached",
                reason: "background_session_kept_alive"
            )
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "background_upload_task_cancel_detached",
                metadata: "session=background action=finish_tasks privacy=no_urls_no_object_keys_no_local_file_paths"
            )
            session.finishTasksAndInvalidate()
        } else {
            session.invalidateAndCancel()
        }
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
