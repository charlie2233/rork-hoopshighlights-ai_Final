import Foundation
import Testing
@testable import HoopsClips

@Suite(.serialized)
@MainActor
struct CloudEditServiceTests {
    @Test func testCloudEditServiceConformsToAIEditViewServiceContract() {
        let service: any CloudEditServicing = CloudEditService()

        #expect(String(describing: type(of: service)) == "CloudEditService")
    }

    @Test func testAIEditViewAcceptsInjectedCloudEditService() {
        let viewModel = HighlightsViewModel()
        let service = InjectedCloudEditService()
        let view = AIEditView(
            viewModel: viewModel,
            isProUser: false,
            cloudEditService: service
        )

        #expect(Mirror(reflecting: view).displayStyle == .struct)
    }

    @Test func testFetchVersionUsesEditingVersionEndpointAndDecodesGptFlags() async throws {
        try await withCloudEditBaseURL {
            let service = CloudEditService(session: makeSession { request in
                #expect(request.httpMethod == "GET")
                #expect(request.value(forHTTPHeaderField: "User-Agent") == "HoopClips-iOS/1.0")
                #expect(request.value(forHTTPHeaderField: "x-trace-id")?.isEmpty == false)
                #expect(request.timeoutInterval == 30)
                let url = try #require(request.url)
                #expect(url.path == "/v1/editing/version")
                #expect(request.httpBody == nil)

                return try jsonResponse(for: request, body: """
                {
                  "service": "hoopclips-editing",
                  "backendModelVersion": "editing-cloud-v1",
                  "gitSha": "test-sha",
                  "featureFlags": {
                    "aiEditEnabled": true,
                    "aiEditLiveRenderEnabled": true,
                    "aiEditRevisionEnabled": true,
                    "aiEditTemplatePackEnabled": true,
                    "aiClipGptEditorEnabled": true,
                    "aiClipGptPlanEditEnabled": true,
                    "aiClipGptRevisionEnabled": true,
                    "gptHighlightRerankerEnabled": true
                  }
                }
                """)
            })

            let version = try await service.fetchVersion()

            #expect(version.service == "hoopclips-editing")
            #expect(version.gitSha == "test-sha")
            #expect(version.featureFlags?.hasRequiredLaunchReadinessFlags == true)
            #expect(version.featureFlags?.allowsGptClipEditing == true)
            #expect(version.featureFlags?.allowsGptPlanEditing == true)
            #expect(version.featureFlags?.allowsGptRevisionEditing == true)
        }
    }

    @Test func testDownloadRenderedVideoMapsExpiredStatusesToDownloadURLExpired() async throws {
        for statusCode in [401, 403, 404, 410] {
            let service = CloudEditService(session: makeSession(statusCode: statusCode))
            let download = CloudEditDownloadResponse(
                editJobId: "edit_123",
                renderJobId: "render_\(statusCode)",
                downloadUrl: "https://cdn.hoopsclips.test/render-\(statusCode).mp4",
                outputObjectKey: nil,
                contentType: "video/mp4",
                expiresAt: Date().addingTimeInterval(900)
            )

            do {
                _ = try await service.downloadRenderedVideo(from: download)
                Issue.record("Expected expired download URL for HTTP \(statusCode).")
            } catch CloudEditError.downloadURLExpired {
                continue
            } catch {
                Issue.record("Expected expired download URL for HTTP \(statusCode), got \(error).")
            }
        }
    }

    @Test func testFetchRenderHistoryUsesRenderJobsEndpointAndLimit() async throws {
        try await withCloudEditBaseURL {
            let service = CloudEditService(session: makeSession { request in
                #expect(request.httpMethod == "GET")
                #expect(request.value(forHTTPHeaderField: "User-Agent") == "HoopClips-iOS/1.0")
                #expect(request.value(forHTTPHeaderField: "x-trace-id")?.isEmpty == false)
                #expect(request.timeoutInterval == 12)
                let url = try #require(request.url)
                #expect(url.path == "/v1/render-jobs")
                let query = try #require(URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems)
                #expect(query.value(named: "installId") == "install_test")
                #expect(query.value(named: "limit") == "7")
                #expect(request.httpBody == nil)

                return try jsonResponse(for: request, body: """
                {
                  "installId": "install_test",
                  "generatedAt": "2026-05-23T21:00:00Z",
                  "renders": [
                    \(renderStatusJSON(editJobId: "edit_history", renderJobId: "render_history"))
                  ]
                }
                """)
            })

            let history = try await service.fetchRenderHistory(installID: "install_test", limit: 7)
            #expect(history.installId == "install_test")
            #expect(history.renders.count == 1)
            #expect(history.renders[0].renderJobId == "render_history")
        }
    }

    @Test func testFetchDownloadURLByRenderJobUsesRenderScopedEndpoint() async throws {
        try await withCloudEditBaseURL {
            let service = CloudEditService(session: makeSession { request in
                #expect(request.httpMethod == "GET")
                let url = try #require(request.url)
                #expect(url.path == "/v1/render-jobs/render_123/download-url")
                let query = try #require(URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems)
                #expect(query.value(named: "installId") == "install_test")
                #expect(request.httpBody == nil)

                return try jsonResponse(for: request, body: """
                {
                  "editJobId": "edit_123",
                  "renderJobId": "render_123",
                  "downloadUrl": "https://cdn.hoopsclips.test/render-123.mp4",
                  "outputObjectKey": null,
                  "contentType": "video/mp4",
                  "expiresAt": "2026-05-23T22:00:00Z"
                }
                """)
            })

            let download = try await service.fetchDownloadURL(renderJobID: "render_123", installID: "install_test")
            #expect(download.editJobId == "edit_123")
            #expect(download.renderJobId == "render_123")
            #expect(download.outputObjectKey == nil)
        }
    }

    @Test func testRequestStoredRenderForcesNewCloudRenderWithoutSourceOrPlanPayload() async throws {
        try await withCloudEditBaseURL {
            let service = CloudEditService(session: makeSession { request in
                #expect(request.httpMethod == "POST")
                #expect(request.url?.path == "/v1/edit-jobs/edit_123/render")
                #expect(request.value(forHTTPHeaderField: "Content-Type") == "application/json")
                let payload = try jsonObject(from: try requestBodyData(from: request))
                #expect(payload["installId"] as? String == "install_test")
                #expect(payload["forceNew"] as? Bool == true)
                #expect((payload["idempotencyKey"] as? String)?.hasPrefix("ios-locker-rerender-") == true)
                #expect(payload["sourceObjectKey"] == nil)
                #expect(payload["editPlan"] == nil)
                #expect(payload["sourceClips"] == nil)

                return try jsonResponse(for: request, body: renderStatusJSON(editJobId: "edit_123", renderJobId: "render_forced"))
            })

            let status = try await service.requestStoredRender(editJobID: "edit_123", installID: "install_test")
            #expect(status.editJobId == "edit_123")
            #expect(status.renderJobId == "render_forced")
        }
    }

    @Test func testRequestStoredRenderCanUseStableInitialRenderKeyWithoutSourceOrPlanPayload() async throws {
        try await withCloudEditBaseURL {
            let service = CloudEditService(session: makeSession { request in
                #expect(request.httpMethod == "POST")
                #expect(request.url?.path == "/v1/edit-jobs/edit_123/render")
                let payload = try jsonObject(from: try requestBodyData(from: request))
                #expect(payload["installId"] as? String == "install_test")
                #expect(payload["forceNew"] as? Bool == false)
                #expect(payload["idempotencyKey"] as? String == "ios-render-edit_123")
                #expect(payload["sourceObjectKey"] == nil)
                #expect(payload["planTier"] == nil)
                #expect(payload["editPlan"] == nil)
                #expect(payload["sourceClips"] == nil)

                return try jsonResponse(for: request, body: renderStatusJSON(editJobId: "edit_123", renderJobId: "render_initial"))
            })

            let status = try await service.requestStoredRender(
                editJobID: "edit_123",
                installID: "install_test",
                idempotencyKey: "ios-render-edit_123",
                forceNew: false
            )
            #expect(status.editJobId == "edit_123")
            #expect(status.renderJobId == "render_initial")
        }
    }

    @Test func testLockerRerenderUsesRevisionEndpointForRevisionRows() async throws {
        try await withCloudEditBaseURL {
            let service = CloudEditService(session: makeSession { request in
                #expect(request.httpMethod == "POST")
                #expect(request.url?.path == "/v1/edit-jobs/edit_123/revisions/rev_more_hype/render")
                let payload = try jsonObject(from: try requestBodyData(from: request))
                #expect(payload["installId"] as? String == "install_test")
                #expect((payload["idempotencyKey"] as? String)?.hasPrefix("ios-revision-rerender-rev_more_hype-") == true)
                #expect(payload["sourceObjectKey"] == nil)
                #expect(payload["editPlan"] == nil)
                #expect(payload["sourceClips"] == nil)

                return try jsonResponse(
                    for: request,
                    body: renderStatusJSON(editJobId: "edit_123", revisionId: "rev_more_hype", renderJobId: "render_revision_fresh")
                )
            })

            let status = try await service.requestLockerRerender(
                render: makeRenderStatus(editJobID: "edit_123", revisionID: "rev_more_hype", renderJobID: "render_revision_old"),
                installID: "install_test"
            )
            #expect(status.revisionId == "rev_more_hype")
            #expect(status.renderJobId == "render_revision_fresh")
        }
    }

    @Test func testLockerRerenderUsesBaseEndpointForBaseRows() async throws {
        try await withCloudEditBaseURL {
            let service = CloudEditService(session: makeSession { request in
                #expect(request.httpMethod == "POST")
                #expect(request.url?.path == "/v1/edit-jobs/edit_123/render")
                let payload = try jsonObject(from: try requestBodyData(from: request))
                #expect(payload["installId"] as? String == "install_test")
                #expect(payload["forceNew"] as? Bool == true)
                #expect((payload["idempotencyKey"] as? String)?.hasPrefix("ios-locker-rerender-") == true)
                #expect(payload["sourceObjectKey"] == nil)
                #expect(payload["editPlan"] == nil)
                #expect(payload["sourceClips"] == nil)

                return try jsonResponse(for: request, body: renderStatusJSON(editJobId: "edit_123", renderJobId: "render_base_fresh"))
            })

            let status = try await service.requestLockerRerender(
                render: makeRenderStatus(editJobID: "edit_123", revisionID: nil, renderJobID: "render_base_old"),
                installID: "install_test"
            )
            #expect(status.revisionId == nil)
            #expect(status.renderJobId == "render_base_fresh")
        }
    }

    @Test func testRequestRevisionRenderUsesRevisionEndpointAndIdempotencyKey() async throws {
        try await withCloudEditBaseURL {
            let service = CloudEditService(session: makeSession { request in
                #expect(request.httpMethod == "POST")
                #expect(request.url?.path == "/v1/edit-jobs/edit_123/revisions/rev_456/render")
                let payload = try jsonObject(from: try requestBodyData(from: request))
                #expect(payload["installId"] as? String == "install_test")
                #expect(payload["idempotencyKey"] as? String == "ios-revision-render-rev_456")
                #expect(payload["sourceObjectKey"] == nil)
                #expect(payload["editPlan"] == nil)
                #expect(payload["sourceClips"] == nil)

                return try jsonResponse(
                    for: request,
                    body: renderStatusJSON(editJobId: "edit_123", revisionId: "rev_456", renderJobId: "render_revision")
                )
            })

            let status = try await service.requestRevisionRender(
                editJobID: "edit_123",
                revisionID: "rev_456",
                installID: "install_test"
            )
            #expect(status.revisionId == "rev_456")
            #expect(status.renderJobId == "render_revision")
        }
    }

    private func makeSession(statusCode: Int) -> URLSession {
        CloudEditMockURLProtocol.requestHandler = { request in
            let response = try #require(
                HTTPURLResponse(
                    url: request.url ?? URL(string: "https://cdn.hoopsclips.test")!,
                    statusCode: statusCode,
                    httpVersion: nil,
                    headerFields: ["Content-Type": "video/mp4"]
                )
            )
            return (response, Data())
        }
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [CloudEditMockURLProtocol.self]
        return URLSession(configuration: configuration)
    }

    private func makeSession(
        handler: @escaping (URLRequest) throws -> (HTTPURLResponse, Data)
    ) -> URLSession {
        CloudEditMockURLProtocol.requestHandler = handler
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [CloudEditMockURLProtocol.self]
        return URLSession(configuration: configuration)
    }

    private func withCloudEditBaseURL(_ body: () async throws -> Void) async throws {
        UserDefaults.standard.set("https://control.hoopsclips.test", forKey: "hoops.cloudEditBaseURL")
        defer {
            UserDefaults.standard.removeObject(forKey: "hoops.cloudEditBaseURL")
            CloudEditMockURLProtocol.requestHandler = nil
        }
        try await body()
    }

    private func jsonResponse(for request: URLRequest, body: String) throws -> (HTTPURLResponse, Data) {
        let url = try #require(request.url)
        let response = try #require(
            HTTPURLResponse(
                url: url,
                statusCode: 200,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            )
        )
        return (response, Data(body.utf8))
    }

    private func jsonObject(from data: Data) throws -> [String: Any] {
        let value = try JSONSerialization.jsonObject(with: data)
        return try #require(value as? [String: Any])
    }

    private func requestBodyData(from request: URLRequest) throws -> Data {
        if let body = request.httpBody {
            return body
        }
        guard let stream = request.httpBodyStream else {
            throw CloudEditError.invalidResponse
        }
        stream.open()
        defer { stream.close() }

        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 1024)
        while stream.hasBytesAvailable {
            let count = stream.read(&buffer, maxLength: buffer.count)
            if count < 0 {
                throw stream.streamError ?? CloudEditError.invalidResponse
            }
            if count == 0 {
                break
            }
            data.append(buffer, count: count)
        }
        return data
    }

    private func renderStatusJSON(
        editJobId: String,
        revisionId: String? = nil,
        renderJobId: String
    ) -> String {
        """
        {
          "editJobId": "\(editJobId)",
          "revisionId": \(revisionId.map { "\"\($0)\"" } ?? "null"),
          "renderJobId": "\(renderJobId)",
          "renderer": "cloud-renderer",
          "rendererVersion": "test",
          "planVersion": null,
          "templateId": "personal_highlight_v1",
          "status": "rendered",
          "outputObjectKey": null,
          "renderLogObjectKey": null,
          "durationSeconds": 30.0,
          "aspectRatio": "9:16",
          "traceId": "trace_test",
          "failureReason": null,
          "validationErrors": null,
          "planTier": "free",
          "policy": null,
          "retryCount": 0,
          "outputBytes": 123456,
          "retentionMetadata": null,
          "workTimeline": null,
          "workReceipt": null
        }
        """
    }

    private func makeRenderStatus(
        editJobID: String,
        revisionID: String?,
        renderJobID: String
    ) -> CloudEditRenderStatusResponse {
        CloudEditRenderStatusResponse(
            editJobId: editJobID,
            revisionId: revisionID,
            renderJobId: renderJobID,
            renderer: "cloud-renderer",
            rendererVersion: "test",
            planVersion: nil,
            templateId: "personal_highlight_v1",
            status: .rendered,
            outputObjectKey: nil,
            renderLogObjectKey: nil,
            durationSeconds: 30.0,
            aspectRatio: .vertical,
            traceId: "trace_test",
            failureReason: nil,
            validationErrors: nil,
            planTier: .free,
            policy: nil,
            retryCount: 0,
            outputBytes: 123456,
            retentionMetadata: nil,
            workTimeline: nil,
            workReceipt: nil
        )
    }
}

private extension [URLQueryItem] {
    func value(named name: String) -> String? {
        first { $0.name == name }?.value
    }
}

private final class InjectedCloudEditService: CloudEditServicing {
    func fetchVersion() async throws -> CloudEditVersionResponse {
        try unexpectedCall()
    }

    func createEditJob(_ requestBody: CreateCloudEditJobRequest) async throws -> CloudEditJobResponse {
        try unexpectedCall()
    }

    func fetchEditPlan(editJobID: String, installID: String) async throws -> CloudEditPlanResponse {
        try unexpectedCall()
    }

    func pollRenderStatus(editJobID: String, installID: String) async throws -> CloudEditRenderStatusResponse {
        try unexpectedCall()
    }

    func fetchRenderHistory(installID: String, limit: Int) async throws -> CloudEditRenderHistoryResponse {
        try unexpectedCall()
    }

    func requestStoredRender(
        editJobID: String,
        installID: String,
        idempotencyKey: String?,
        forceNew: Bool
    ) async throws -> CloudEditRenderStatusResponse {
        try unexpectedCall()
    }

    func requestLockerRerender(render: CloudEditRenderStatusResponse, installID: String) async throws -> CloudEditRenderStatusResponse {
        try unexpectedCall()
    }

    func fetchDownloadURL(editJobID: String, installID: String) async throws -> CloudEditDownloadResponse {
        try unexpectedCall()
    }

    func fetchDownloadURL(renderJobID: String, installID: String) async throws -> CloudEditDownloadResponse {
        try unexpectedCall()
    }

    func requestRevision(
        editJobID: String,
        installID: String,
        command: CloudEditRevisionCommand
    ) async throws -> CloudEditRevisionResponse {
        try unexpectedCall()
    }

    func requestRevisionRender(
        editJobID: String,
        revisionID: String,
        installID: String,
        forceNew: Bool
    ) async throws -> CloudEditRenderStatusResponse {
        try unexpectedCall()
    }

    func downloadRenderedVideo(from response: CloudEditDownloadResponse) async throws -> URL {
        try unexpectedCall()
    }

    private func unexpectedCall<T>(function: StaticString = #function) throws -> T {
        throw CloudEditError.network("Unexpected cloud edit service call in injection test: \(function)")
    }
}

private final class CloudEditMockURLProtocol: URLProtocol {
    static var requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        guard let handler = Self.requestHandler else {
            client?.urlProtocol(self, didFailWithError: CloudEditError.network("missing test handler"))
            return
        }

        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}
