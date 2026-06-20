import Foundation
import UniformTypeIdentifiers

private let cloudUploadResumeManifestDefaultsKey = "hoopsclips.cloudUpload.resumeManifest.v1"

nonisolated enum CloudUploadResumeOutcome: Sendable {
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
        stalled: Bool = false
    ) -> String {
        let boundedFraction = min(max(fraction, 0), 1)
        let percent = Int((boundedFraction * 100).rounded(.down))
        var parts = ["\(stage) \(percent)%"]

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
            parts.append("connection may be slow")
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
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async throws -> CloudUploadResumeOutcome? {
        guard let manifest = await CloudUploadResumeStore.shared.pendingManifest() else {
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
        let reportUploadProgress: @Sendable (_ snapshot: CloudUploadProgressSnapshot, _ stalled: Bool) -> Void = { snapshot, stalled in
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
                        stalled: stalled
                    )
                )
            }
        }

        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_foreground_resume_started",
            metadata: "purpose=\(manifest.purpose.rawValue) completed=\(manifest.completedParts.count) partCount=\(manifest.partCount)"
        )
        try await resumeUploadManifest(
            manifest,
            sourceURL: sourceURL,
            baseURL: baseURL,
            tracker: tracker,
            reportUploadProgress: reportUploadProgress
        )

        switch manifest.purpose {
        case .analysis:
            progress(0.28, "Starting cloud clip search")
            _ = try await startJob(baseURL: baseURL, jobID: manifest.jobID, installID: installID, teamSelection: teamSelection)
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
        guard let uploadURL = URL(string: job.uploadUrl) else {
            throw CloudAnalysisError.invalidResponse
        }

        var request = URLRequest(url: uploadURL)
        request.httpMethod = job.uploadMethod
        for (header, value) in job.uploadHeaders {
            request.setValue(value, forHTTPHeaderField: header)
        }

        let tracker = CloudUploadProgressTracker()
        let reportUploadProgress: @Sendable (_ snapshot: CloudUploadProgressSnapshot, _ stalled: Bool) -> Void = { snapshot, stalled in
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
                    stalled: stalled
                )
                progress(progressValue, message)
            }
        }
        let delegate = CloudUploadProgressDelegate { uploadedBytes, totalBytes in
            Task {
                await tracker.update(uploadedBytes: uploadedBytes, totalBytes: totalBytes)
                let snapshot = await tracker.snapshot()
                reportUploadProgress(snapshot, false)
            }
        }
        let uploadMonitorTask = Task {
            while !Task.isCancelled {
                do {
                    try await Task.sleep(nanoseconds: 10 * 1_000_000_000)
                } catch {
                    return
                }

                let snapshot = await tracker.snapshot()
                let stalled = snapshot.secondsSinceProgress >= 60 && snapshot.fraction < 0.99
                reportUploadProgress(snapshot, stalled)
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
        let uploadSession = URLSession(
            configuration: uploadSessionConfiguration(
                backgroundIdentifier: Self.backgroundUploadSessionIdentifier(jobID: job.jobId)
            ),
            delegate: delegate,
            delegateQueue: nil
        )
        let uploadPartCount = job.resumableUpload?.partCount ?? 1
        let usesChunkedUpload = uploadPartCount > 1
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "source_session_started",
            metadata: "kind=source chunked=\(usesChunkedUpload) partCount=\(uploadPartCount)"
        )
        defer {
            uploadMonitorTask.cancel()
            uploadSession.finishTasksAndInvalidate()
        }

        if let resumableUpload = job.resumableUpload, resumableUpload.partCount > 1 {
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

        let response = try await delegate.upload(request: request, fromFile: url, using: uploadSession)
        let finalSnapshot = await tracker.snapshot()
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
        reportUploadProgress: @escaping @Sendable (_ snapshot: CloudUploadProgressSnapshot, _ stalled: Bool) -> Void
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
                reportUploadProgress(snapshot, false)
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
        await CloudUploadResumeStore.shared.clear(jobID: job.jobId, uploadID: resumableUpload.uploadId)
        await tracker.update(uploadedBytes: totalBytes, totalBytes: totalBytes)
        let finalSnapshot = await tracker.snapshot()
        reportUploadProgress(finalSnapshot, false)
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
        reportUploadProgress: @escaping @Sendable (_ snapshot: CloudUploadProgressSnapshot, _ stalled: Bool) -> Void
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
                reportUploadProgress(snapshot, false)
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
        await CloudUploadResumeStore.shared.clear(jobID: manifest.jobID, uploadID: manifest.uploadID)
    }

    private func uploadMultipartChunk(
        _ partTarget: CloudMultipartPartResponse,
        chunk: Data,
        alreadyUploadedBytes: Int64,
        totalBytes: Int64,
        uploadID: String,
        tracker: CloudUploadProgressTracker,
        reportUploadProgress: @escaping @Sendable (_ snapshot: CloudUploadProgressSnapshot, _ stalled: Bool) -> Void
    ) async throws -> String {
        guard let uploadURL = URL(string: partTarget.uploadUrl) else {
            throw CloudAnalysisError.invalidResponse
        }

        var lastError: Error?
        for attempt in 0..<3 {
            do {
                var request = URLRequest(url: uploadURL)
                request.httpMethod = partTarget.uploadMethod
                for (header, value) in partTarget.uploadHeaders {
                    request.setValue(value, forHTTPHeaderField: header)
                }

                let delegate = CloudUploadProgressDelegate { sentBytes, _ in
                    Task {
                        await tracker.update(uploadedBytes: alreadyUploadedBytes + sentBytes, totalBytes: totalBytes)
                        let snapshot = await tracker.snapshot()
                        reportUploadProgress(snapshot, false)
                    }
                }
                let chunkFileURL = try CloudUploadChunkFileStore.writeChunk(chunk, jobID: partTarget.jobId, partNumber: partTarget.partNumber)
                defer {
                    try? FileManager.default.removeItem(at: chunkFileURL)
                }

                let backgroundIdentifier = Self.backgroundUploadSessionIdentifier(
                    jobID: partTarget.jobId,
                    partNumber: partTarget.partNumber,
                    attempt: attempt + 1
                )
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
                    metadata: "kind=chunk partNumber=\(partTarget.partNumber) attempt=\(attempt + 1)"
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
                reportUploadProgress(snapshot, false)
                return etag
            } catch {
                lastError = error
                try await Task.sleep(nanoseconds: 700_000_000)
            }
        }

        throw lastError ?? CloudAnalysisError.uploadFailed
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
            configuration.sessionSendsLaunchEvents = true
            configuration.isDiscretionary = false
        } else {
            configuration = URLSessionConfiguration.default
        }
        configuration.waitsForConnectivity = true
        configuration.allowsCellularAccess = true
        configuration.allowsExpensiveNetworkAccess = true
        configuration.allowsConstrainedNetworkAccess = true
        configuration.timeoutIntervalForRequest = 60
        configuration.timeoutIntervalForResource = 2 * 60 * 60
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
        return directory
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
        configuration.sessionSendsLaunchEvents = true
        configuration.isDiscretionary = false
        configuration.waitsForConnectivity = true
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
                CloudUploadBackgroundSessionRegistry.shared.finishEvents(for: identifier)
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

private final class CloudUploadBackgroundRelaunchDelegate: NSObject, URLSessionTaskDelegate, URLSessionDataDelegate, @unchecked Sendable {
    private let identifier: String

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
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "relaunch_task_failed",
                metadata: "source=urlsession_delegate error=\(error.localizedDescription)"
            )
        } else {
            if identifier.contains(".part-"),
               let http = task.response as? HTTPURLResponse,
               let etag = Self.headerValue("ETag", from: http) {
                Task {
                    await CloudUploadResumeStore.shared.recordRelaunchedCompletedPart(
                        sessionIdentifier: identifier,
                        etag: etag
                    )
                }
            }
            LaunchTelemetry.shared.recordBackgroundUploadProof(
                "relaunch_task_completed",
                metadata: "source=urlsession_delegate"
            )
        }
    }

    func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
        CloudUploadBackgroundSessionRegistry.shared.finishEvents(for: identifier)
    }

    private static func headerValue(_ name: String, from response: HTTPURLResponse) -> String? {
        for (key, value) in response.allHeaderFields {
            if String(describing: key).caseInsensitiveCompare(name) == .orderedSame {
                return String(describing: value)
            }
        }
        return nil
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

    func recordRelaunchedCompletedPart(sessionIdentifier: String, etag: String) {
        guard let sessionPart = Self.parseMultipartSessionIdentifier(sessionIdentifier),
              var manifest = loadManifest(),
              manifest.jobID == sessionPart.jobID else {
            LaunchTelemetry.shared.recordBackgroundUploadProof("resume_manifest_relaunch_part_ignored")
            return
        }

        var parts = manifest.completedParts.filter { $0.partNumber != sessionPart.partNumber }
        parts.append(CloudMultipartCompletedPart(partNumber: sessionPart.partNumber, etag: etag))
        manifest.completedParts = parts.sorted { $0.partNumber < $1.partNumber }
        manifest.updatedAt = Date()
        saveManifest(manifest)
        LaunchTelemetry.shared.recordBackgroundUploadProof(
            "resume_manifest_relaunch_part_completed",
            metadata: "completed=\(manifest.completedParts.count) partCount=\(manifest.partCount)"
        )
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
    private let lock = NSLock()
    private var continuation: CheckedContinuation<URLResponse, Error>?

    init(onProgress: @escaping @Sendable (_ uploadedBytes: Int64, _ totalBytes: Int64) -> Void) {
        self.onProgress = onProgress
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
