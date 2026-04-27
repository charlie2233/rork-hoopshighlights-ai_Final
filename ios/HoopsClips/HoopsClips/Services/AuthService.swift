import Foundation
import AuthenticationServices
import GoogleSignIn
import SwiftUI

nonisolated enum AuthMethod: String, Codable, Sendable {
    case apple
    case google
    case email
    case phone
    case anonymous
}

nonisolated struct AuthUser: Codable, Sendable {
    let id: String
    let displayName: String?
    let email: String?
    let phone: String?
    let authMethod: AuthMethod
    let isEmailVerified: Bool
    let isPhoneVerified: Bool

    init(id: String, displayName: String? = nil, email: String? = nil, phone: String? = nil, authMethod: AuthMethod, isEmailVerified: Bool = false, isPhoneVerified: Bool = false) {
        self.id = id
        self.displayName = displayName
        self.email = email
        self.phone = phone
        self.authMethod = authMethod
        self.isEmailVerified = isEmailVerified
        self.isPhoneVerified = isPhoneVerified
    }
}

@Observable
@MainActor
final class AuthService {
    var currentUser: AuthUser?
    var isAuthenticated: Bool { currentUser != nil }
    var isLoading = false
    var errorMessage: String?
    var emailVerificationCode: String?
    var phoneVerificationCode: String?
    var pendingEmailVerification: String?
    var pendingPhoneVerification: String?

    private let userDefaultsKey = "hoops_auth_user"
    private let emailAuthClient: FirebaseEmailAuthClient

    init(emailAuthClient: FirebaseEmailAuthClient? = nil) {
        self.emailAuthClient = emailAuthClient ?? FirebaseEmailAuthClient(apiKey: AppConstants.firebaseAuthAPIKey)
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

            let user = AuthUser(id: userId, displayName: name, email: mail, authMethod: .apple, isEmailVerified: mail != nil)
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
        guard AppConstants.googleSignInConfigured else {
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
                authMethod: .google,
                isEmailVerified: profile?.email != nil
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

        if emailAuthClient.isConfigured {
            do {
                let session = try await emailAuthClient.signInOrCreateAccount(email: email, password: password)
                let user = AuthUser(
                    id: session.userID,
                    displayName: nil,
                    email: session.email,
                    authMethod: .email,
                    isEmailVerified: true
                )
                setUser(user)
            } catch let authError as FirebaseEmailAuthError {
                errorMessage = authError.localizedDescription
            } catch {
                errorMessage = "Email sign-in failed. Please try again."
            }
            return
        }

        guard AppConstants.runtimeConfig.isDebug else {
            errorMessage = "Email sign-in is not configured for this build."
            return
        }

        try? await Task.sleep(for: .milliseconds(800))
        let userId = email.lowercased().data(using: .utf8)?.base64EncodedString() ?? UUID().uuidString
        let user = AuthUser(id: userId, displayName: nil, email: email, authMethod: .email, isEmailVerified: false)
        setUser(user)
        pendingEmailVerification = email
        sendEmailVerificationCode(to: email)
    }

    func sendEmailVerificationCode(to email: String) {
        let code = generateCode()
        emailVerificationCode = code
        pendingEmailVerification = email
    }

    func verifyEmail(code: String) -> Bool {
        guard let expected = emailVerificationCode, code == expected else {
            errorMessage = "Invalid verification code. Please try again."
            return false
        }
        guard var user = currentUser else { return false }
        user = AuthUser(
            id: user.id,
            displayName: user.displayName,
            email: user.email,
            phone: user.phone,
            authMethod: user.authMethod,
            isEmailVerified: true,
            isPhoneVerified: user.isPhoneVerified
        )
        setUser(user)
        emailVerificationCode = nil
        pendingEmailVerification = nil
        return true
    }

    func sendPhoneVerificationCode(to phone: String) {
        let code = generateCode()
        phoneVerificationCode = code
        pendingPhoneVerification = phone
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

        guard let expected = phoneVerificationCode, code == expected else {
            errorMessage = "Invalid verification code."
            return
        }

        let userId = phoneNumber.data(using: .utf8)?.base64EncodedString() ?? UUID().uuidString
        let user = AuthUser(id: userId, displayName: nil, phone: phoneNumber, authMethod: .phone, isPhoneVerified: true)
        setUser(user)
        phoneVerificationCode = nil
        pendingPhoneVerification = nil
    }

    func signInAnonymously() {
        let userId = UUID().uuidString
        let user = AuthUser(id: userId, displayName: "Guest", authMethod: .anonymous)
        setUser(user)
    }

    func linkEmail(_ email: String) {
        guard var user = currentUser else { return }
        user = AuthUser(
            id: user.id,
            displayName: user.displayName,
            email: email,
            phone: user.phone,
            authMethod: user.authMethod,
            isEmailVerified: false,
            isPhoneVerified: user.isPhoneVerified
        )
        setUser(user)
        sendEmailVerificationCode(to: email)
    }

    func linkPhone(_ phone: String) {
        guard var user = currentUser else { return }
        user = AuthUser(
            id: user.id,
            displayName: user.displayName,
            email: user.email,
            phone: phone,
            authMethod: user.authMethod,
            isEmailVerified: user.isEmailVerified,
            isPhoneVerified: false
        )
        setUser(user)
        sendPhoneVerificationCode(to: phone)
    }

    func verifyPhone(code: String) -> Bool {
        guard let expected = phoneVerificationCode, code == expected else {
            errorMessage = "Invalid verification code."
            return false
        }
        guard var user = currentUser else { return false }
        user = AuthUser(
            id: user.id,
            displayName: user.displayName,
            email: user.email,
            phone: user.phone,
            authMethod: user.authMethod,
            isEmailVerified: user.isEmailVerified,
            isPhoneVerified: true
        )
        setUser(user)
        phoneVerificationCode = nil
        pendingPhoneVerification = nil
        return true
    }

    private func generateCode() -> String {
        let code = (100000...999999).randomElement() ?? 123456
        return String(code)
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
