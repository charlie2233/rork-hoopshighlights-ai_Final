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

    func analyzeVideo(
        url: URL,
        duration: Double,
        installID: String,
        appVersion: String = "v1.0",
        analysisVersion: String = AppConstants.cloudAnalysisVersion,
        progress: @escaping @MainActor @Sendable (Double, String) -> Void
    ) async throws -> CloudAnalysisResult {
        guard let baseURL = configuredBaseURL() else {
            throw CloudAnalysisError.notConfigured
        }

        let fileInfo = try fileInfo(for: url)
        let requestId = makeRequestID()

        await progress(0.02, "Preparing upload")
        if usesHappyPathFlow {
            let presign = try await requestPresignedUpload(
                baseURL: baseURL,
                request: CloudUploadPresignRequest(
                    filename: url.lastPathComponent,
                    contentType: fileInfo.contentType,
                    fileSizeBytes: fileInfo.fileSizeBytes,
                    durationSeconds: duration,
                    installId: installID,
                    appVersion: appVersion,
                    analysisVersion: analysisVersion
                ),
                requestId: requestId
            )

            await progress(0.15, "Uploading video")
            try await uploadVideo(to: presign, from: url)

            await progress(0.28, "Creating job")
            let job = try await createHappyPathJob(
                baseURL: baseURL,
                request: CloudCreateJobRequest(
                    filename: url.lastPathComponent,
                    contentType: fileInfo.contentType,
                    fileSizeBytes: fileInfo.fileSizeBytes,
                    durationSeconds: duration,
                    installId: installID,
                    appVersion: appVersion,
                    analysisVersion: analysisVersion,
                    uploadObjectKey: presign.uploadObjectKey,
                    resultObjectKey: presign.resultObjectKey
                ),
                requestId: requestId
            )

            return try await pollJob(
                baseURL: baseURL,
                jobID: job.jobId,
                initialPollAfterSeconds: job.pollAfterSeconds ?? 2,
                progress: progress,
                requestId: requestId
            )
        }

        let job = try await createLegacyJob(
            baseURL: baseURL,
            request: CreateCloudAnalysisJobRequest(
                filename: url.lastPathComponent,
                contentType: fileInfo.contentType,
                fileSizeBytes: fileInfo.fileSizeBytes,
                durationSeconds: duration,
                installId: installID,
                appVersion: appVersion,
                analysisVersion: analysisVersion
            ),
            requestId: requestId
        )

        await progress(0.15, "Uploading video")
        try await uploadLegacyVideo(to: job, from: url)

        await progress(0.28, "Queued on server")
        _ = try await startLegacyJob(baseURL: baseURL, jobID: job.jobId, installID: installID, requestId: requestId)

        return try await pollJob(
            baseURL: baseURL,
            jobID: job.jobId,
            initialPollAfterSeconds: job.pollAfterSeconds,
            progress: progress,
            requestId: requestId
        )
    }

    private func configuredBaseURL() -> URL? {
        guard !AppConstants.cloudAnalysisBaseURL.isEmpty,
              let url = URL(string: AppConstants.cloudAnalysisBaseURL) else {
            return nil
        }

        if usesHappyPathFlow, isLoopback(url) {
            return nil
        }

        return url
    }

    private var usesHappyPathFlow: Bool {
        let normalizedEnvironment = AppRuntimeConfig.shared.environmentName
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
        return normalizedEnvironment == "staging" || normalizedEnvironment == "production"
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

    private func requestPresignedUpload(
        baseURL: URL,
        request body: CloudUploadPresignRequest,
        requestId: String
    ) async throws -> CloudUploadPresignResponse {
        var request = URLRequest(url: baseURL.appending(path: "uploads/presign"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(requestId, forHTTPHeaderField: "X-Request-ID")
        request.httpBody = try encoder.encode(body)

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(
            data: data,
            response: response,
            successType: CloudUploadPresignResponse.self
        )
    }

    private func createHappyPathJob(
        baseURL: URL,
        request body: CloudCreateJobRequest,
        requestId: String
    ) async throws -> CloudCreateJobResponse {
        var request = URLRequest(url: baseURL.appending(path: "jobs"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(requestId, forHTTPHeaderField: "X-Request-ID")
        request.httpBody = try encoder.encode(body)

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(
            data: data,
            response: response,
            successType: CloudCreateJobResponse.self
        )
    }

    private func uploadVideo(to presign: CloudUploadPresignResponse, from url: URL) async throws {
        guard let uploadURL = URL(string: presign.uploadUrl) else {
            throw CloudAnalysisError.invalidResponse
        }

        var request = URLRequest(url: uploadURL)
        request.httpMethod = presign.uploadMethod
        for (header, value) in presign.uploadHeaders {
            request.setValue(value, forHTTPHeaderField: header)
        }

        let (_, response) = try await session.upload(for: request, fromFile: url)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw CloudAnalysisError.uploadFailed
        }
    }

    private func createLegacyJob(
        baseURL: URL,
        request body: CreateCloudAnalysisJobRequest,
        requestId: String
    ) async throws -> CreateCloudAnalysisJobResponse {
        var request = URLRequest(url: baseURL.appending(path: "v1/analysis/jobs"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(requestId, forHTTPHeaderField: "X-Request-ID")
        request.httpBody = try encoder.encode(body)

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(
            data: data,
            response: response,
            successType: CreateCloudAnalysisJobResponse.self
        )
    }

    private func uploadLegacyVideo(to job: CreateCloudAnalysisJobResponse, from url: URL) async throws {
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

    private func startLegacyJob(
        baseURL: URL,
        jobID: String,
        installID: String,
        requestId: String
    ) async throws -> StartCloudAnalysisJobResponse {
        var request = URLRequest(url: baseURL.appending(path: "v1/analysis/jobs/\(jobID)/start"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(requestId, forHTTPHeaderField: "X-Request-ID")
        request.httpBody = try encoder.encode(StartCloudAnalysisJobRequest(installId: installID))

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(
            data: data,
            response: response,
            successType: StartCloudAnalysisJobResponse.self
        )
    }

    private func pollJob(
        baseURL: URL,
        jobID: String,
        initialPollAfterSeconds: Int,
        progress: @escaping @MainActor @Sendable (Double, String) -> Void,
        requestId: String
    ) async throws -> CloudAnalysisResult {
        let timeoutNanos: UInt64 = 180 * 1_000_000_000
        let deadline = DispatchTime.now().uptimeNanoseconds + timeoutNanos
        var pollDelay = max(1, initialPollAfterSeconds)

        while DispatchTime.now().uptimeNanoseconds < deadline {
            try await Task.sleep(nanoseconds: UInt64(pollDelay) * 1_000_000_000)

            let path = usesHappyPathFlow ? "jobs/\(jobID)" : "v1/analysis/jobs/\(jobID)"
            var request = URLRequest(url: baseURL.appending(path: path))
            request.setValue(requestId, forHTTPHeaderField: "X-Request-ID")

            let (data, response) = try await session.data(for: request)
            let job: CloudAnalysisJobResponse = try decodeResponse(
                data: data,
                response: response,
                successType: CloudAnalysisJobResponse.self
            )

            switch CloudAnalysisJobState(rawValue: job.status) {
            case .created, .uploadPending, .uploaded:
                await progress(min(max(job.progress, 0.0), 0.35), job.stage.isEmpty ? "Uploading video" : job.stage)
            case .queued:
                await progress(min(max(job.progress, 0.0), 0.55), job.stage.isEmpty ? "Queued on server" : job.stage)
            case .processing:
                await progress(max(0.55, min(job.progress, 0.92)), job.stage.isEmpty ? "Analyzing in cloud" : job.stage)
            case .completed, .succeeded:
                await progress(0.96, "Finalizing clips")
                guard let results = job.results else {
                    throw CloudAnalysisError.invalidResponse
                }
                return results
            case .failed:
                throw CloudAnalysisError.backend(
                    code: job.failureReason ?? job.errorCode ?? "analysis_failed",
                    message: job.errorMessage ?? "Cloud analysis failed."
                )
            case .expired:
                throw CloudAnalysisError.backend(
                    code: "expired",
                    message: "Cloud analysis job expired before completion."
                )
            case .cancelled:
                throw CloudAnalysisError.backend(
                    code: job.failureReason ?? "cancelled",
                    message: job.errorMessage ?? "Cloud analysis job was cancelled."
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
                code: apiError?.failureReason ?? apiError?.errorCode ?? "http_\(http.statusCode)",
                message: apiError?.errorMessage ?? apiError?.failureReason ?? "Cloud analysis request failed."
            )
        }

        do {
            return try decoder.decode(successType, from: data)
        } catch {
            throw CloudAnalysisError.invalidResponse
        }
    }

    private func makeRequestID() -> String {
        UUID().uuidString.replacingOccurrences(of: "-", with: "")
    }

    private func isLoopback(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        return host == "localhost" || host == "127.0.0.1" || host == "::1"
    }
}
