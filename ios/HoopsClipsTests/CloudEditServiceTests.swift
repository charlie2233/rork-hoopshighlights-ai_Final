import Foundation
import Testing
@testable import HoopsClips

@MainActor
@Suite(.serialized)
struct CloudEditServiceTests {
    @Test func testFetchRenderHistoryUsesCloudLockerEndpoint() async throws {
        try await withCloudEditBaseURL {
            let service = CloudEditService(session: makeSession { request in
                #expect(request.httpMethod == "GET")
                let url = try #require(request.url)
                #expect(url.path == "/v1/render-jobs")
                #expect(queryValue("installId", in: url) == "install-locker-001")
                #expect(queryValue("limit", in: url) == "12")
                #expect(request.value(forHTTPHeaderField: "User-Agent") == "Hoopclips-iOS/1.0")
                #expect(request.value(forHTTPHeaderField: "x-trace-id")?.isEmpty == false)

                let response = try #require(
                    HTTPURLResponse(
                        url: url,
                        statusCode: 200,
                        httpVersion: nil,
                        headerFields: ["Content-Type": "application/json"]
                    )
                )
                return (response, Data(renderHistoryJSON.utf8))
            })

            let history = try await service.fetchRenderHistory(installID: "install-locker-001", limit: 12)

            #expect(history.installId == "install-locker-001")
            #expect(history.generatedAt == "2026-05-23T18:00:00Z")
            #expect(history.renders.count == 1)
            #expect(history.renders[0].editJobId == "edit_locker_001")
            #expect(history.renders[0].renderJobId == "render_locker_001")
            #expect(history.renders[0].status == .rendered)
            #expect(history.renders[0].retentionMetadata?.deleteEligible == false)
        }
    }

    @Test func testFetchDownloadURLByRenderJobUsesRenderScopedEndpoint() async throws {
        try await withCloudEditBaseURL {
            let service = CloudEditService(session: makeSession { request in
                #expect(request.httpMethod == "GET")
                let url = try #require(request.url)
                #expect(url.path == "/v1/render-jobs/render_locker_001/download-url")
                #expect(queryValue("installId", in: url) == "install-locker-001")

                let response = try #require(
                    HTTPURLResponse(
                        url: url,
                        statusCode: 200,
                        httpVersion: nil,
                        headerFields: ["Content-Type": "application/json"]
                    )
                )
                return (response, Data(downloadURLJSON.utf8))
            })

            let download = try await service.fetchDownloadURL(
                renderJobID: "render_locker_001",
                installID: "install-locker-001"
            )

            #expect(download.editJobId == "edit_locker_001")
            #expect(download.renderJobId == "render_locker_001")
            #expect(download.outputObjectKey == nil)
            #expect(download.contentType == "video/mp4")
            #expect(download.downloadUrl.hasPrefix("https://cdn.hoopsclips.test/locker-render.mp4"))
        }
    }

    @Test func testRequestStoredRenderUsesForceNewAndLockerIdempotencyKey() async throws {
        try await withCloudEditBaseURL {
            let service = CloudEditService(session: makeSession { request in
                #expect(request.httpMethod == "POST")
                let url = try #require(request.url)
                #expect(url.path == "/v1/edit-jobs/edit_locker_001/render")
                #expect(request.value(forHTTPHeaderField: "Content-Type") == "application/json")

                let body = try #require(bodyData(from: request))
                let payload = try #require(
                    JSONSerialization.jsonObject(with: body) as? [String: Any]
                )
                #expect(payload["installId"] as? String == "install-locker-001")
                #expect(payload["forceNew"] as? Bool == true)
                let idempotencyKey = try #require(payload["idempotencyKey"] as? String)
                #expect(idempotencyKey.hasPrefix("ios-locker-rerender-"))

                let response = try #require(
                    HTTPURLResponse(
                        url: url,
                        statusCode: 200,
                        httpVersion: nil,
                        headerFields: ["Content-Type": "application/json"]
                    )
                )
                return (response, Data(renderStatusJSON.utf8))
            })

            let render = try await service.requestStoredRender(
                editJobID: "edit_locker_001",
                installID: "install-locker-001"
            )

            #expect(render.editJobId == "edit_locker_001")
            #expect(render.renderJobId == "render_locker_001")
            #expect(render.status == .rendered)
        }
    }

    @Test func testDownloadRenderedVideoMapsExpiredStatusesToDownloadURLExpired() async throws {
        for statusCode in [401, 403, 404, 410] {
            let service = CloudEditService(session: makeSession { request in
                let response = try #require(
                    HTTPURLResponse(
                        url: request.url ?? URL(string: "https://cdn.hoopsclips.test")!,
                        statusCode: statusCode,
                        httpVersion: nil,
                        headerFields: ["Content-Type": "video/mp4"]
                    )
                )
                return (response, Data())
            })
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

    private func makeSession(handler: @escaping (URLRequest) throws -> (HTTPURLResponse, Data)) -> URLSession {
        CloudEditMockURLProtocol.requestHandler = handler
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [CloudEditMockURLProtocol.self]
        return URLSession(configuration: configuration)
    }

    private func withCloudEditBaseURL<T>(_ operation: () async throws -> T) async throws -> T {
        let key = "hoops.cloudEditBaseURL"
        let previous = UserDefaults.standard.string(forKey: key)
        UserDefaults.standard.set("https://worker.hoopsclips.test", forKey: key)
        defer {
            if let previous {
                UserDefaults.standard.set(previous, forKey: key)
            } else {
                UserDefaults.standard.removeObject(forKey: key)
            }
        }
        return try await operation()
    }

    private func queryValue(_ name: String, in url: URL) -> String? {
        URLComponents(url: url, resolvingAgainstBaseURL: false)?
            .queryItems?
            .first(where: { $0.name == name })?
            .value
    }

    private func bodyData(from request: URLRequest) -> Data? {
        if let body = request.httpBody {
            return body
        }
        guard let stream = request.httpBodyStream else {
            return nil
        }
        stream.open()
        defer { stream.close() }

        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 1024)
        while stream.hasBytesAvailable {
            let count = stream.read(&buffer, maxLength: buffer.count)
            if count < 0 {
                return nil
            }
            if count == 0 {
                break
            }
            data.append(buffer, count: count)
        }
        return data
    }
}

private let renderStatusJSON = """
{
  "editJobId": "edit_locker_001",
  "revisionId": null,
  "renderJobId": "render_locker_001",
  "renderer": "ffmpeg",
  "rendererVersion": "ffmpeg-renderer-v1",
  "planVersion": "edit-plan-v1",
  "templateId": "personal_highlight_v1",
  "status": "rendered",
  "outputObjectKey": null,
  "renderLogObjectKey": null,
  "durationSeconds": 28.5,
  "aspectRatio": "9:16",
  "traceId": "trace-locker-001",
  "failureReason": null,
  "validationErrors": [],
  "planTier": "free",
  "policy": null,
  "retryCount": 0,
  "outputBytes": 1234567,
  "retentionMetadata": {
    "expiresAt": "2026-06-22T18:00:00Z",
    "retentionClass": "free_30d",
    "deleteEligible": false,
    "planTier": "free",
    "editJobId": "edit_locker_001",
    "renderJobId": "render_locker_001",
    "templateId": "personal_highlight_v1",
    "outputBytes": 1234567,
    "durationSeconds": 28.5
  },
  "workTimeline": null,
  "workReceipt": null
}
"""

private let renderHistoryJSON = """
{
  "installId": "install-locker-001",
  "generatedAt": "2026-05-23T18:00:00Z",
  "renders": [
    \(renderStatusJSON)
  ]
}
"""

private let downloadURLJSON = """
{
  "editJobId": "edit_locker_001",
  "renderJobId": "render_locker_001",
  "downloadUrl": "https://cdn.hoopsclips.test/locker-render.mp4?token=redacted",
  "outputObjectKey": null,
  "contentType": "video/mp4",
  "expiresAt": "2026-05-23T18:15:00Z"
}
"""

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
