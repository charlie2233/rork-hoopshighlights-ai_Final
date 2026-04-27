import Foundation

nonisolated struct BackendEmailAuthSession: Sendable, Equatable {
    let userID: String
    let email: String
    let idToken: String
    let refreshToken: String
}

nonisolated enum FirebaseEmailAuthError: LocalizedError, Equatable {
    case notConfigured
    case invalidEmail
    case weakPassword
    case invalidCredentials
    case emailAlreadyExists
    case disabled
    case tooManyAttempts
    case malformedResponse
    case transport(String)
    case server(String)

    var errorDescription: String? {
        switch self {
        case .notConfigured:
            return "Email sign-in is not configured for this build."
        case .invalidEmail:
            return "Please enter a valid email address."
        case .weakPassword:
            return "Please use a stronger password."
        case .invalidCredentials:
            return "The email or password is incorrect."
        case .emailAlreadyExists:
            return "That email is already registered. Please sign in with the original password."
        case .disabled:
            return "Email/password sign-in is not enabled for this app."
        case .tooManyAttempts:
            return "Too many attempts. Please wait a moment and try again."
        case .malformedResponse:
            return "The auth server returned an unreadable response."
        case .transport:
            return "We could not reach the auth server. Check your connection and try again."
        case .server(let message):
            return "Auth failed: \(message)"
        }
    }

    var shouldCreateAccountAfterSignInFailure: Bool {
        self == .invalidCredentials
    }
}

nonisolated struct FirebaseEmailAuthClient {
    private enum Endpoint: String {
        case signIn = "accounts:signInWithPassword"
        case signUp = "accounts:signUp"
    }

    private struct AuthRequest: Encodable {
        let email: String
        let password: String
        let returnSecureToken: Bool
    }

    private struct AuthResponse: Decodable {
        let idToken: String?
        let email: String?
        let refreshToken: String?
        let localId: String?
    }

    private struct ErrorResponse: Decodable {
        struct Body: Decodable {
            let message: String?
        }

        let error: Body?
    }

    private let apiKey: String
    private let session: URLSession

    init(apiKey: String, session: URLSession = .shared) {
        self.apiKey = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        self.session = session
    }

    var isConfigured: Bool {
        !apiKey.isEmpty
    }

    func signInOrCreateAccount(email: String, password: String) async throws -> BackendEmailAuthSession {
        do {
            return try await authenticate(endpoint: .signIn, email: email, password: password)
        } catch let signInError as FirebaseEmailAuthError where signInError.shouldCreateAccountAfterSignInFailure {
            do {
                return try await authenticate(endpoint: .signUp, email: email, password: password)
            } catch FirebaseEmailAuthError.emailAlreadyExists {
                throw FirebaseEmailAuthError.invalidCredentials
            }
        }
    }

    private func authenticate(endpoint: Endpoint, email: String, password: String) async throws -> BackendEmailAuthSession {
        guard isConfigured else {
            throw FirebaseEmailAuthError.notConfigured
        }

        guard var components = URLComponents(string: "https://identitytoolkit.googleapis.com/v1/\(endpoint.rawValue)") else {
            throw FirebaseEmailAuthError.notConfigured
        }
        components.queryItems = [URLQueryItem(name: "key", value: apiKey)]

        guard let url = components.url else {
            throw FirebaseEmailAuthError.notConfigured
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 20
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(
            AuthRequest(email: email, password: password, returnSecureToken: true)
        )

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw FirebaseEmailAuthError.transport(error.localizedDescription)
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw FirebaseEmailAuthError.malformedResponse
        }

        guard (200..<300).contains(httpResponse.statusCode) else {
            throw mapFirebaseError(from: data)
        }

        let decoded = try JSONDecoder().decode(AuthResponse.self, from: data)
        guard let userID = decoded.localId, !userID.isEmpty,
              let email = decoded.email, !email.isEmpty,
              let idToken = decoded.idToken, !idToken.isEmpty,
              let refreshToken = decoded.refreshToken, !refreshToken.isEmpty else {
            throw FirebaseEmailAuthError.malformedResponse
        }

        return BackendEmailAuthSession(
            userID: userID,
            email: email,
            idToken: idToken,
            refreshToken: refreshToken
        )
    }

    private func mapFirebaseError(from data: Data) -> FirebaseEmailAuthError {
        let decodedError = try? JSONDecoder().decode(ErrorResponse.self, from: data)
        let rawMessage = decodedError?.error?.message ?? "UNKNOWN"
        let code = rawMessage
            .components(separatedBy: " : ")
            .first?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? rawMessage

        switch code {
        case "EMAIL_EXISTS":
            return .emailAlreadyExists
        case "INVALID_EMAIL", "MISSING_EMAIL":
            return .invalidEmail
        case "WEAK_PASSWORD", "MISSING_PASSWORD":
            return .weakPassword
        case "EMAIL_NOT_FOUND", "INVALID_PASSWORD", "INVALID_LOGIN_CREDENTIALS":
            return .invalidCredentials
        case "OPERATION_NOT_ALLOWED":
            return .disabled
        case "TOO_MANY_ATTEMPTS_TRY_LATER":
            return .tooManyAttempts
        case "API_KEY_INVALID", "INVALID_API_KEY":
            return .notConfigured
        default:
            return .server(code)
        }
    }
}
