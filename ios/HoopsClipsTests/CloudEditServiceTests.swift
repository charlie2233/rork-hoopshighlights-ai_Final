import Foundation
import Testing
@testable import HoopsClips

@Suite(.serialized)
struct CloudEditServiceTests {
    @Test func testLockerRerenderUsesRevisionEndpointForRevisionRows() async throws {
        let captured = RequestCapture()
        let service = try makeConfiguredService(captured: captured)
        defer { resetTestState() }

        let response = try await service.requestLockerRerender(
            render: makeRenderStatus(editJobID: "edit_123", renderJobID: "render_old", revisionID: "rev_more_hype"),
            installID: "install-local-001"
        )

        let request = try #require(captured.requests.first)
        let payload = try #require(captured.jsonBodies.first)
        #expect(response.renderJobId == "render_revision_new")
        #expect(request.httpMethod == "POST")
        #expect(request.url?.path == "/v1/edit-jobs/edit_123/revisions/rev_more_hype/render")
        #expect(payload["installId"] as? String == "install-local-001")
        let idempotencyKey = try #require(payload["idempotencyKey"] as? String)
        #expect(idempotencyKey.hasPrefix("ios-revision-rerender-rev_more_hype-"))
    }

    @Test func testLockerRerenderUsesStoredEditEndpointForBaseRows() async throws {
        let captured = RequestCapture()
        let service = try makeConfiguredService(captured: captured)
        defer { resetTestState() }

        let response = try await service.requestLockerRerender(
            render: makeRenderStatus(editJobID: "edit_123", renderJobID: "render_old", revisionID: nil),
            installID: "install-local-001"
        )

        let request = try #require(captured.requests.first)
        let payload = try #require(captured.jsonBodies.first)
        #expect(response.renderJobId == "render_base_new")
        #expect(request.httpMethod == "POST")
        #expect(request.url?.path == "/v1/edit-jobs/edit_123/render")
        #expect(payload["installId"] as? String == "install-local-001")
        #expect(payload["forceNew"] as? Bool == true)
        let idempotencyKey = try #require(payload["idempotencyKey"] as? String)
        #expect(idempotencyKey.hasPrefix("ios-locker-rerender-"))
    }

    @Test func testDownloadRenderedVideoMapsExpiredStatusesToDownloadURLExpired() async throws {
        for statusCode in [401, 403, 404, 410] {
            let service = CloudEditService(session: makeSession(statusCode: statusCode))
            defer { CloudEditMockURLProtocol.requestHandler = nil }
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

    private func makeConfiguredService(captured: RequestCapture) throws -> CloudEditService {
        UserDefaults.standard.set("https://editing.hoopsclips.test", forKey: "hoops.cloudEditBaseURL")
        CloudEditMockURLProtocol.requestHandler = { request in
            captured.requests.append(request)
            captured.jsonBodies.append(try decodeJSONBody(from: request))
            let isRevisionRender = request.url?.path.contains("/revisions/") == true
            let payload = """
            {
              "editJobId": "edit_123",
              "revisionId": \(isRevisionRender ? "\"rev_more_hype\"" : "null"),
              "renderJobId": "\(isRevisionRender ? "render_revision_new" : "render_base_new")",
              "renderer": "cloud_ffmpeg",
              "rendererVersion": "ffmpeg-renderer-v1",
              "status": "queued",
              "aspectRatio": "9:16",
              "traceId": "trace_rerender"
            }
            """
            let response = try #require(
                HTTPURLResponse(
                    url: request.url ?? URL(string: "https://editing.hoopsclips.test")!,
                    statusCode: 200,
                    httpVersion: nil,
                    headerFields: ["Content-Type": "application/json"]
                )
            )
            return (response, Data(payload.utf8))
        }
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [CloudEditMockURLProtocol.self]
        return CloudEditService(session: URLSession(configuration: configuration))
    }

    private func decodeJSONBody(from request: URLRequest) throws -> [String: Any] {
        let body: Data
        if let requestBody = request.httpBody {
            body = requestBody
        } else if let stream = request.httpBodyStream {
            stream.open()
            defer { stream.close() }

            var data = Data()
            var buffer = [UInt8](repeating: 0, count: 1_024)
            while stream.hasBytesAvailable {
                let count = stream.read(&buffer, maxLength: buffer.count)
                if count < 0 {
                    throw stream.streamError ?? CocoaError(.fileReadUnknown)
                }
                if count == 0 {
                    break
                }
                data.append(buffer, count: count)
            }
            body = data
        } else {
            body = Data()
        }

        guard !body.isEmpty else { return [:] }
        let object = try JSONSerialization.jsonObject(with: body)
        return (object as? [String: Any]) ?? [:]
    }

    private func resetTestState() {
        UserDefaults.standard.removeObject(forKey: "hoops.cloudEditBaseURL")
        CloudEditMockURLProtocol.requestHandler = nil
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

    private func makeRenderStatus(editJobID: String, renderJobID: String, revisionID: String?) -> CloudEditRenderStatusResponse {
        CloudEditRenderStatusResponse(
            editJobId: editJobID,
            revisionId: revisionID,
            renderJobId: renderJobID,
            renderer: "cloud_ffmpeg",
            rendererVersion: "ffmpeg-renderer-v1",
            planVersion: "edit-plan-v1",
            templateId: "personal_highlight_v1",
            status: .rendered,
            outputObjectKey: nil,
            renderLogObjectKey: nil,
            durationSeconds: 15,
            aspectRatio: .vertical,
            traceId: "trace_old",
            failureReason: nil,
            validationErrors: nil,
            planTier: .free,
            policy: nil,
            retryCount: nil,
            outputBytes: 1234,
            retentionMetadata: nil,
            workTimeline: nil,
            workReceipt: nil
        )
    }
}

private final class RequestCapture: @unchecked Sendable {
    var requests: [URLRequest] = []
    var jsonBodies: [[String: Any]] = []
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
