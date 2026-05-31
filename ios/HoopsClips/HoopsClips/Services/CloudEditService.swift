import Foundation

protocol CloudEditServicing {
    func fetchVersion() async throws -> CloudEditVersionResponse
    func createEditJob(_ requestBody: CreateCloudEditJobRequest) async throws -> CloudEditJobResponse
    func fetchEditPlan(editJobID: String, installID: String) async throws -> CloudEditPlanResponse
    func pollRenderStatus(editJobID: String, installID: String) async throws -> CloudEditRenderStatusResponse
    func fetchRenderHistory(installID: String, limit: Int) async throws -> CloudEditRenderHistoryResponse
    func requestStoredRender(
        editJobID: String,
        installID: String,
        idempotencyKey: String?,
        forceNew: Bool
    ) async throws -> CloudEditRenderStatusResponse
    func requestLockerRerender(render: CloudEditRenderStatusResponse, installID: String) async throws -> CloudEditRenderStatusResponse
    func fetchDownloadURL(editJobID: String, installID: String) async throws -> CloudEditDownloadResponse
    func fetchDownloadURL(renderJobID: String, installID: String) async throws -> CloudEditDownloadResponse
    func requestRevision(
        editJobID: String,
        installID: String,
        command: CloudEditRevisionCommand
    ) async throws -> CloudEditRevisionResponse
    func requestRevisionRender(
        editJobID: String,
        revisionID: String,
        installID: String,
        forceNew: Bool
    ) async throws -> CloudEditRenderStatusResponse
    func downloadRenderedVideo(from response: CloudEditDownloadResponse) async throws -> URL
}

struct CloudEditService: CloudEditServicing {
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

    func fetchVersion() async throws -> CloudEditVersionResponse {
        let baseURL = try configuredBaseURL()
        let url = baseURL.appending(path: "v1/editing/version")

        let (data, response) = try await session.data(for: signedClientRequest(url: url))
        return try decodeResponse(data: data, response: response, successType: CloudEditVersionResponse.self)
    }

    func createEditJob(_ requestBody: CreateCloudEditJobRequest) async throws -> CloudEditJobResponse {
        let baseURL = try configuredBaseURL()
        var request = URLRequest(url: baseURL.appending(path: "v1/edit-jobs"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("HoopClips-iOS/1.0", forHTTPHeaderField: "User-Agent")
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

    func pollRenderStatus(editJobID: String, installID: String) async throws -> CloudEditRenderStatusResponse {
        let timeoutNanos: UInt64 = 240 * 1_000_000_000
        let start = DispatchTime.now().uptimeNanoseconds
        var pollDelaySeconds: UInt64 = 2
        var attempts = 0

        while DispatchTime.now().uptimeNanoseconds - start < timeoutNanos {
            try await Task.sleep(nanoseconds: pollDelaySeconds * 1_000_000_000)
            let status: CloudEditRenderStatusResponse
            do {
                status = try await fetchRenderStatus(editJobID: editJobID, installID: installID)
            } catch CloudEditError.backend(let code, _) where code == "render_job_not_found" && attempts < 5 {
                attempts += 1
                continue
            }
            switch status.status {
            case .rendered, .failed, .failedTimeout, .cancelled:
                return status
            case .renderRequested, .planning, .planReady, .created, .queued, .rendering:
                attempts += 1
                if attempts >= 15 {
                    pollDelaySeconds = 5
                }
            }
        }

        throw CloudEditError.timedOut
    }

    func fetchRenderHistory(installID: String, limit: Int = 20) async throws -> CloudEditRenderHistoryResponse {
        let baseURL = try configuredBaseURL()
        var components = URLComponents(url: baseURL.appending(path: "v1/render-jobs"), resolvingAgainstBaseURL: false)
        components?.queryItems = [
            URLQueryItem(name: "installId", value: installID),
            URLQueryItem(name: "limit", value: String(limit))
        ]
        guard let url = components?.url else {
            throw CloudEditError.invalidResponse
        }

        let (data, response) = try await session.data(for: signedClientRequest(url: url))
        return try decodeResponse(data: data, response: response, successType: CloudEditRenderHistoryResponse.self)
    }

    func requestStoredRender(
        editJobID: String,
        installID: String,
        idempotencyKey: String? = nil,
        forceNew: Bool = true
    ) async throws -> CloudEditRenderStatusResponse {
        let baseURL = try configuredBaseURL()
        var request = URLRequest(url: baseURL.appending(path: "v1/edit-jobs/\(editJobID)/render"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("HoopClips-iOS/1.0", forHTTPHeaderField: "User-Agent")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "x-trace-id")
        request.httpBody = try encoder.encode(
            CloudEditStoredRenderRequest(
                installId: installID,
                idempotencyKey: idempotencyKey ?? "ios-locker-rerender-\(UUID().uuidString)",
                forceNew: forceNew
            )
        )

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(data: data, response: response, successType: CloudEditRenderStatusResponse.self)
    }

    func requestLockerRerender(render: CloudEditRenderStatusResponse, installID: String) async throws -> CloudEditRenderStatusResponse {
        if let revisionID = render.revisionId, !revisionID.isEmpty {
            return try await requestRevisionRender(
                editJobID: render.editJobId,
                revisionID: revisionID,
                installID: installID,
                forceNew: true
            )
        }

        return try await requestStoredRender(editJobID: render.editJobId, installID: installID)
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

    func fetchDownloadURL(renderJobID: String, installID: String) async throws -> CloudEditDownloadResponse {
        let baseURL = try configuredBaseURL()
        var components = URLComponents(url: baseURL.appending(path: "v1/render-jobs/\(renderJobID)/download-url"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "installId", value: installID)]
        guard let url = components?.url else {
            throw CloudEditError.invalidResponse
        }

        let (data, response) = try await session.data(for: signedClientRequest(url: url))
        return try decodeResponse(data: data, response: response, successType: CloudEditDownloadResponse.self)
    }

    func requestRevision(
        editJobID: String,
        installID: String,
        command: CloudEditRevisionCommand
    ) async throws -> CloudEditRevisionResponse {
        let baseURL = try configuredBaseURL()
        var request = URLRequest(url: baseURL.appending(path: "v1/edit-jobs/\(editJobID)/revise"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("HoopClips-iOS/1.0", forHTTPHeaderField: "User-Agent")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "x-trace-id")
        request.httpBody = try encoder.encode(
            CloudEditRevisionRequest(
                installId: installID,
                command: command
            )
        )

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(data: data, response: response, successType: CloudEditRevisionResponse.self)
    }

    func requestRevisionRender(
        editJobID: String,
        revisionID: String,
        installID: String,
        forceNew: Bool = false
    ) async throws -> CloudEditRenderStatusResponse {
        let baseURL = try configuredBaseURL()
        var request = URLRequest(url: baseURL.appending(path: "v1/edit-jobs/\(editJobID)/revisions/\(revisionID)/render"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("HoopClips-iOS/1.0", forHTTPHeaderField: "User-Agent")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "x-trace-id")
        let idempotencyKey: String
        if forceNew {
            idempotencyKey = "ios-revision-rerender-\(revisionID)-\(UUID().uuidString)"
        } else {
            idempotencyKey = "ios-revision-render-\(revisionID)"
        }
        request.httpBody = try encoder.encode(
            CloudEditRevisionRenderRequest(
                installId: installID,
                idempotencyKey: idempotencyKey
            )
        )

        let (data, response) = try await session.data(for: request)
        return try decodeResponse(data: data, response: response, successType: CloudEditRenderStatusResponse.self)
    }

    func downloadRenderedVideo(from response: CloudEditDownloadResponse) async throws -> URL {
        guard let url = URL(string: response.downloadUrl) else {
            throw CloudEditError.invalidResponse
        }

        let (temporaryURL, urlResponse) = try await session.download(from: url)
        guard let http = urlResponse as? HTTPURLResponse else {
            throw CloudEditError.network("The rendered video download failed.")
        }
        guard (200..<300).contains(http.statusCode) else {
            if [401, 403, 404, 410].contains(http.statusCode) {
                throw CloudEditError.downloadURLExpired
            }
            throw CloudEditError.network("The rendered video download failed.")
        }

        let destination = URL.temporaryDirectory
            .appendingPathComponent("HoopClips-AI-Edit-\(response.renderJobId)")
            .appendingPathExtension("mp4")
        try? FileManager.default.removeItem(at: destination)
        try FileManager.default.moveItem(at: temporaryURL, to: destination)
        let attributes = try FileManager.default.attributesOfItem(atPath: destination.path)
        let fileSize = attributes[.size] as? NSNumber
        guard (fileSize?.int64Value ?? 0) > 0 else {
            try? FileManager.default.removeItem(at: destination)
            throw CloudEditError.invalidResponse
        }
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
        request.setValue("HoopClips-iOS/1.0", forHTTPHeaderField: "User-Agent")
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
                message: CloudEditError.friendlyBackendMessage(
                    code: apiError?.errorCode ?? "http_\(http.statusCode)",
                    fallback: apiError?.failureReason ?? apiError?.errorMessage ?? "Cloud editing request failed."
                )
            )
        }

        do {
            return try decoder.decode(successType, from: data)
        } catch {
            throw CloudEditError.invalidResponse
        }
    }
}
