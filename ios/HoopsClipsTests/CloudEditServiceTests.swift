import Foundation
import Testing
@testable import HoopsClips

struct CloudEditServiceTests {
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
