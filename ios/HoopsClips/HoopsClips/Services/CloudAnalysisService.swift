import Foundation
import UniformTypeIdentifiers

struct CloudAnalysisService {
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
        let trimmed = stage.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            return fallback
        }

        let normalized = trimmed.lowercased()
        let forbiddenMarkers = [
            "thinking",
            "eta ",
            " eta",
            "eta:",
            "http://",
            "https://",
            "presigned",
            "signature",
            "x-amz",
            "x-goog",
            "uploads/",
            "renders/",
            "render_logs/",
            "r2 ",
            "bucket",
            "secret",
            "token",
            "credential",
            "api_key",
            "apikey",
            "access_key"
        ]
        guard !forbiddenMarkers.contains(where: { normalized.contains($0) }) else {
            return fallback
        }

        return trimmed
    }

    func analyzeVideo(
        url: URL,
        duration: Double,
        installID: String,
        appVersion: String = "v1.0",
        analysisVersion: String = "v1",
        teamSelection: HighlightTeamSelection? = nil,
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async throws -> CloudAnalysisResult {
        guard let baseURL = configuredBaseURL() else {
            throw CloudAnalysisError.notConfigured
        }

        let fileInfo = try fileInfo(for: url)
        await progress(0.02, "Preparing cloud analysis")
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

        await progress(0.15, "Uploading video to cloud")
        try await uploadVideo(to: job, from: url)

        await progress(0.28, "Starting cloud clip search")
        _ = try await startJob(baseURL: baseURL, jobID: job.jobId, installID: installID, teamSelection: teamSelection)

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
        await progress(0.02, "Preparing cloud team scan")
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

        await progress(0.14, "Uploading video for team scan")
        try await uploadVideo(to: job, from: url)

        await progress(0.20, "Scanning jersey colors")
        let scan = try await scanJobTeams(baseURL: baseURL, jobID: job.jobId, installID: installID)
        await progress(0.24, scan.detectedTeams.isEmpty ? "Team scan unavailable" : "Team choices found")

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
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async throws -> CloudAnalysisResult {
        guard let baseURL = configuredBaseURL() else {
            throw CloudAnalysisError.notConfigured
        }

        await progress(0.28, "Starting cloud clip search")
        _ = try await startJob(
            baseURL: baseURL,
            jobID: preparedJob.job.jobId,
            installID: installID,
            teamSelection: teamSelection
        )

        return try await pollJob(
            baseURL: baseURL,
            jobID: preparedJob.job.jobId,
            sourceObjectKey: preparedJob.job.sourceObjectKey,
            initialPollAfterSeconds: preparedJob.job.pollAfterSeconds,
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
        let timeoutNanos: UInt64 = 180 * 1_000_000_000
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
                await progress(0.96, "Finalizing clips")
                guard let results = job.results else {
                    throw CloudAnalysisError.invalidResponse
                }
                return results.withJobMetadata(analysisJobId: job.jobId, sourceObjectKey: job.sourceObjectKey ?? sourceObjectKey)
            case .failed:
                throw CloudAnalysisError.backend(
                    code: job.errorCode ?? "analysis_failed",
                    message: job.errorMessage ?? "Analysis failed."
                )
            case .expired:
                throw CloudAnalysisError.backend(
                    code: "expired",
                    message: "Analysis took too long before completion."
                )
            case .created, .queued:
                await progress(
                    min(max(job.progress, 0.0), 0.55),
                    Self.safeProgressStage(job.stage, fallback: "Waiting for cloud analysis")
                )
            case .processing:
                await progress(
                    max(0.55, min(job.progress, 0.92)),
                    Self.safeProgressStage(job.stage, fallback: "Analyzing frames in cloud")
                )
            case .none:
                throw CloudAnalysisError.invalidResponse
            }

            pollDelay = min(pollDelay + 1, 4)
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
                message: apiError?.errorMessage ?? "Analysis request failed."
            )
        }

        do {
            return try decoder.decode(successType, from: data)
        } catch {
            throw CloudAnalysisError.invalidResponse
        }
    }
}
