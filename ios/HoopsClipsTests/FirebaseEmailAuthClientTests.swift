import Foundation
import Testing
@testable import HoopsClips

struct FirebaseEmailAuthClientTests {
    @Test func signInUsesFirebasePasswordEndpoint() async throws {
        var capturedMethod: String?
        var capturedURL: String?
        let session = makeSession { request in
            capturedMethod = request.httpMethod
            capturedURL = request.url?.absoluteString

            return try jsonResponse(
                statusCode: 200,
                body: [
                    "localId": "firebase-user-id",
                    "email": "appreview@hoopsclips.app",
                    "idToken": "id-token",
                    "refreshToken": "refresh-token"
                ]
            )
        }

        let client = FirebaseEmailAuthClient(apiKey: "test_key", session: session)
        let authSession = try await client.signInOrCreateAccount(
            email: "appreview@hoopsclips.app",
            password: "review-password"
        )

        #expect(authSession.userID == "firebase-user-id")
        #expect(authSession.email == "appreview@hoopsclips.app")
        #expect(capturedMethod == "POST")
        #expect(capturedURL?.contains("accounts:signInWithPassword") == true)
        #expect(capturedURL?.contains("key=test_key") == true)
    }

    @Test func createsBackendAccountWhenSignInCredentialsDoNotExistYet() async throws {
        var calls: [String] = []
        let session = makeSession { request in
            guard let url = request.url?.absoluteString else {
                throw FirebaseEmailAuthError.malformedResponse
            }
            calls.append(url)

            if url.contains("accounts:signInWithPassword") {
                return try jsonResponse(
                    statusCode: 400,
                    body: ["error": ["message": "EMAIL_NOT_FOUND"]]
                )
            }

            return try jsonResponse(
                statusCode: 200,
                body: [
                    "localId": "created-user-id",
                    "email": "new-reviewer@hoopsclips.app",
                    "idToken": "new-id-token",
                    "refreshToken": "new-refresh-token"
                ]
            )
        }

        let client = FirebaseEmailAuthClient(apiKey: "test_key", session: session)
        let authSession = try await client.signInOrCreateAccount(
            email: "new-reviewer@hoopsclips.app",
            password: "review-password"
        )

        #expect(authSession.userID == "created-user-id")
        #expect(calls.count == 2)
        #expect(calls[0].contains("accounts:signInWithPassword"))
        #expect(calls[1].contains("accounts:signUp"))
    }

    @Test func existingAccountWithWrongPasswordStaysInvalidCredentials() async throws {
        var callCount = 0
        let session = makeSession { request in
            callCount += 1
            guard let url = request.url?.absoluteString else {
                throw FirebaseEmailAuthError.malformedResponse
            }

            if url.contains("accounts:signInWithPassword") {
                return try jsonResponse(
                    statusCode: 400,
                    body: ["error": ["message": "INVALID_LOGIN_CREDENTIALS"]]
                )
            }

            return try jsonResponse(
                statusCode: 400,
                body: ["error": ["message": "EMAIL_EXISTS"]]
            )
        }

        let client = FirebaseEmailAuthClient(apiKey: "test_key", session: session)

        do {
            _ = try await client.signInOrCreateAccount(
                email: "existing@hoopsclips.app",
                password: "wrong-password"
            )
            Issue.record("Expected invalid credentials")
        } catch let error as FirebaseEmailAuthError {
            #expect(error == .invalidCredentials)
        }

        #expect(callCount == 2)
    }

    private func makeSession(
        handler: @escaping (URLRequest) throws -> (HTTPURLResponse, Data)
    ) -> URLSession {
        MockURLProtocol.requestHandler = handler
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MockURLProtocol.self]
        return URLSession(configuration: configuration)
    }

    private func jsonResponse(statusCode: Int, body: [String: Any]) throws -> (HTTPURLResponse, Data) {
        let data = try JSONSerialization.data(withJSONObject: body)
        let response = try #require(
            HTTPURLResponse(
                url: URL(string: "https://identitytoolkit.googleapis.com")!,
                statusCode: statusCode,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            )
        )
        return (response, data)
    }
}

private final class MockURLProtocol: URLProtocol {
    static var requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        guard let handler = Self.requestHandler else {
            client?.urlProtocol(self, didFailWithError: FirebaseEmailAuthError.server("missing test handler"))
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
