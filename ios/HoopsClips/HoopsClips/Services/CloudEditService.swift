import Foundation

struct CloudEditService {
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init(session: URLSession = .shared) {
        self.session = session
        decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
    }

    func createEditJob(_ requestBody: CreateCloudEditJobRequest) async throws -> CloudEditJobResponse {
        let baseURL = try configuredBaseURL()
        var request = URLRequest(url: baseURL.appending(path: "v1/edit-jobs"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Hoopclips-iOS/1.0", forHTTPHeaderField: "User-Agent")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "x-trace-id")
        request.httpBody = try encoder.encode(requestBody)

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(data: data, response: response, successType: CloudEditJobResponse.self)
    }

    func fetchEditPlan(editJobID: String, installID: String) async throws -> CloudEditPlanResponse {
        let baseURL = try configuredBaseURL()
        var components = URLComponents(url: baseURL.appending(path: "v1/edit-jobs/\(editJobID)/plan"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "installId", value: installID)]
        guard let url = components?.url else {
            throw CloudEditError.invalidResponse
        }

        let (data, response) = try await session.data(for: signedClientRequest(url: url))
        return try decodeResponse(data: data, response: response, successType: CloudEditPlanResponse.self)
    }

    func requestRender(
        editJobID: String,
        installID: String,
        sourceObjectKey: String,
        planTier: CloudEditPlanTier,
        editPlan: CloudEditPlanSummary,
        sourceClips: [CloudEditCandidateClip]
    ) async throws -> CloudEditRenderStatusResponse {
        let baseURL = try configuredBaseURL()
        var request = URLRequest(url: baseURL.appending(path: "v1/edit-jobs/\(editJobID)/render"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Hoopclips-iOS/1.0", forHTTPHeaderField: "User-Agent")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "x-trace-id")
        request.httpBody = try encoder.encode(
            CloudEditRenderRequest(
                installId: installID,
                sourceObjectKey: sourceObjectKey,
                planTier: planTier,
                editPlan: editPlan,
                sourceClips: sourceClips
            )
        )

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(data: data, response: response, successType: CloudEditRenderStatusResponse.self)
    }

    func pollRenderStatus(editJobID: String, installID: String) async throws -> CloudEditRenderStatusResponse {
        let timeoutNanos: UInt64 = 240 * 1_000_000_000
        let start = DispatchTime.now().uptimeNanoseconds
        var pollDelaySeconds: UInt64 = 2
        var attempts = 0

        while DispatchTime.now().uptimeNanoseconds - start < timeoutNanos {
            try await Task.sleep(nanoseconds: pollDelaySeconds * 1_000_000_000)
            let status = try await fetchRenderStatus(editJobID: editJobID, installID: installID)
            switch status.status {
            case .rendered, .failed, .cancelled:
                return status
            case .planning, .planReady, .created, .queued, .rendering:
                attempts += 1
                if attempts >= 15 {
                    pollDelaySeconds = 5
                }
            }
        }

        throw CloudEditError.timedOut
    }

    func fetchDownloadURL(editJobID: String, installID: String) async throws -> CloudEditDownloadResponse {
        let baseURL = try configuredBaseURL()
        var components = URLComponents(url: baseURL.appending(path: "v1/edit-jobs/\(editJobID)/download-url"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "installId", value: installID)]
        guard let url = components?.url else {
            throw CloudEditError.invalidResponse
        }

        let (data, response) = try await session.data(for: signedClientRequest(url: url))
        return try decodeResponse(data: data, response: response, successType: CloudEditDownloadResponse.self)
    }

    func downloadRenderedVideo(from response: CloudEditDownloadResponse) async throws -> URL {
        guard let url = URL(string: response.downloadUrl) else {
            throw CloudEditError.invalidResponse
        }

        let (temporaryURL, urlResponse) = try await session.download(from: url)
        guard let http = urlResponse as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw CloudEditError.network("The rendered video download failed.")
        }

        let destination = URL.temporaryDirectory
            .appendingPathComponent("Hoopclips-AI-Edit-\(response.renderJobId)")
            .appendingPathExtension("mp4")
        try? FileManager.default.removeItem(at: destination)
        try FileManager.default.moveItem(at: temporaryURL, to: destination)
        return destination
    }

    private func fetchRenderStatus(editJobID: String, installID: String) async throws -> CloudEditRenderStatusResponse {
        let baseURL = try configuredBaseURL()
        var components = URLComponents(url: baseURL.appending(path: "v1/edit-jobs/\(editJobID)/render-status"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "installId", value: installID)]
        guard let url = components?.url else {
            throw CloudEditError.invalidResponse
        }

        let (data, response) = try await session.data(for: signedClientRequest(url: url))
        return try decodeResponse(data: data, response: response, successType: CloudEditRenderStatusResponse.self)
    }

    private func configuredBaseURL() throws -> URL {
        guard AppConstants.cloudEditEnabled, !AppConstants.cloudEditBaseURL.isEmpty else {
            throw CloudEditError.notConfigured
        }
        guard let url = URL(string: AppConstants.cloudEditBaseURL) else {
            throw CloudEditError.notConfigured
        }
        return url
    }

    private func signedClientRequest(url: URL) -> URLRequest {
        var request = URLRequest(url: url)
        request.setValue("Hoopclips-iOS/1.0", forHTTPHeaderField: "User-Agent")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "x-trace-id")
        return request
    }

    private func decodeResponse<T: Decodable>(
        data: Data,
        response: URLResponse,
        successType: T.Type
    ) throws -> T {
        guard let http = response as? HTTPURLResponse else {
            throw CloudEditError.invalidResponse
        }

        guard (200..<300).contains(http.statusCode) else {
            let apiError = try? decoder.decode(CloudEditAPIError.self, from: data)
            throw CloudEditError.backend(
                code: apiError?.errorCode ?? "http_\(http.statusCode)",
                message: apiError?.failureReason ?? apiError?.errorMessage ?? "Cloud editing request failed."
            )
        }

        do {
            return try decoder.decode(successType, from: data)
        } catch {
            throw CloudEditError.invalidResponse
        }
    }
}
