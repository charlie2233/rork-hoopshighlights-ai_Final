import Foundation
import UniformTypeIdentifiers

struct CloudAnalysisService {
    typealias HandoffHandler = @MainActor @Sendable (_ jobID: String, _ sourceObjectKey: String?) -> Void

    private static let analysisPollTimeoutSeconds: UInt64 = 8 * 60
    private static let maxPollDelaySeconds = 5
    private static let maxVisibleProgressStageCharacters = 72
    private static let maxVisibleBackendMessageCharacters = 96
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

    static func safeProgressStage(_ stage: String, fallback: String) -> String {
        safeVisibleMessage(stage, fallback: fallback, maxCharacters: maxVisibleProgressStageCharacters)
    }

    static func safeBackendMessage(_ message: String, fallback: String) -> String {
        safeVisibleMessage(message, fallback: fallback, maxCharacters: maxVisibleBackendMessageCharacters)
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

        progress(0.15, "Uploading video to cloud")
        try await uploadVideo(to: job, from: url)

        progress(0.28, "Starting cloud clip search")
        _ = try await startJob(baseURL: baseURL, jobID: job.jobId, installID: installID, teamSelection: teamSelection)
        await onCloudHandoff?(job.jobId, job.sourceObjectKey)

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

        progress(0.14, "Uploading video for team scan")
        try await uploadVideo(to: job, from: url)

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
        await onCloudHandoff?(preparedJob.job.jobId, preparedJob.job.sourceObjectKey)

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

    private func uploadVideo(to job: CreateCloudAnalysisJobResponse, from url: URL) async throws {
        guard let uploadURL = URL(string: job.uploadUrl) else {
            throw CloudAnalysisError.invalidResponse
        }

        var request = URLRequest(url: uploadURL)
        request.httpMethod = job.uploadMethod
        for (header, value) in job.uploadHeaders {
            request.setValue(value, forHTTPHeaderField: header)
        }

        let (_, response) = try await session.upload(for: request, fromFile: url)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw CloudAnalysisError.uploadFailed
        }
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
