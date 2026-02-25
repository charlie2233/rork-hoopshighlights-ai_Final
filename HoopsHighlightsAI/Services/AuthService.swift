import Foundation
import AuthenticationServices
import GoogleSignIn
import SwiftUI

nonisolated enum AuthMethod: String, Codable, Sendable {
    case apple
    case google
    case email
    case phone
}

nonisolated struct AuthUser: Codable, Sendable {
    let id: String
    let displayName: String?
    let email: String?
    let authMethod: AuthMethod
}

@Observable
@MainActor
final class AuthService {
    var currentUser: AuthUser?
    var isAuthenticated: Bool { currentUser != nil }
    var isLoading = false
    var errorMessage: String?

    private let userDefaultsKey = "hoops_auth_user"

    init() {
        loadPersistedUser()
    }

    func signInWithApple(result: Result<ASAuthorization, Error>) {
        switch result {
        case .success(let auth):
            guard let credential = auth.credential as? ASAuthorizationAppleIDCredential else { return }
            let userId = credential.user
            let fullName = [credential.fullName?.givenName, credential.fullName?.familyName]
                .compactMap { $0 }
                .joined(separator: " ")
            let email = credential.email

            let existing = loadPersistedUser()
            let name = fullName.isEmpty ? existing?.displayName : fullName
            let mail = email ?? existing?.email

            let user = AuthUser(id: userId, displayName: name, email: mail, authMethod: .apple)
            setUser(user)

        case .failure(let error):
            if (error as NSError).code == ASAuthorizationError.canceled.rawValue { return }
            errorMessage = error.localizedDescription
        }
    }

    func signInWithGoogle(presenting viewController: UIViewController) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        let clientID = AppConstants.googleClientID
        guard !clientID.isEmpty else {
            errorMessage = "Google Sign-In is not configured yet."
            return
        }

        do {
            let config = GIDConfiguration(clientID: clientID)
            GIDSignIn.sharedInstance.configuration = config
            let result = try await GIDSignIn.sharedInstance.signIn(withPresenting: viewController)
            let profile = result.user.profile
            let user = AuthUser(
                id: result.user.userID ?? UUID().uuidString,
                displayName: profile?.name,
                email: profile?.email,
                authMethod: .google
            )
            setUser(user)
        } catch {
            if (error as NSError).code == GIDSignInError.canceled.rawValue { return }
            errorMessage = error.localizedDescription
        }
    }

    func signInWithEmail(email: String, password: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        guard !email.isEmpty, !password.isEmpty else {
            errorMessage = "Please enter both email and password."
            return
        }
        guard password.count >= 6 else {
            errorMessage = "Password must be at least 6 characters."
            return
        }

        try? await Task.sleep(for: .milliseconds(800))

        let userId = email.lowercased().data(using: .utf8)?.base64EncodedString() ?? UUID().uuidString
        let user = AuthUser(id: userId, displayName: nil, email: email, authMethod: .email)
        setUser(user)
    }

    func signInWithPhone(phoneNumber: String, code: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        guard !phoneNumber.isEmpty else {
            errorMessage = "Please enter your phone number."
            return
        }
        guard code.count == 6 else {
            errorMessage = "Please enter the 6-digit verification code."
            return
        }

        try? await Task.sleep(for: .milliseconds(800))

        let userId = phoneNumber.data(using: .utf8)?.base64EncodedString() ?? UUID().uuidString
        let user = AuthUser(id: userId, displayName: nil, email: nil, authMethod: .phone)
        setUser(user)
    }

    func signOut() {
        currentUser = nil
        UserDefaults.standard.removeObject(forKey: userDefaultsKey)
        GIDSignIn.sharedInstance.signOut()
    }

    private func setUser(_ user: AuthUser) {
        currentUser = user
        if let data = try? JSONEncoder().encode(user) {
            UserDefaults.standard.set(data, forKey: userDefaultsKey)
        }
    }

    @discardableResult
    private func loadPersistedUser() -> AuthUser? {
        guard let data = UserDefaults.standard.data(forKey: userDefaultsKey),
              let user = try? JSONDecoder().decode(AuthUser.self, from: data) else { return nil }
        currentUser = user
        return user
    }
}
