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
    let isDemoVerificationEnabled: Bool

    private let userDefaultsKey = "hoops_auth_user"
    private let emailAuthClient: FirebaseEmailAuthClient

    init(
        emailAuthClient: FirebaseEmailAuthClient? = nil,
        isDemoVerificationEnabled: Bool? = nil
    ) {
        self.emailAuthClient = emailAuthClient ?? FirebaseEmailAuthClient(apiKey: AppConstants.firebaseAuthAPIKey)
        self.isDemoVerificationEnabled = isDemoVerificationEnabled ?? AppConstants.runtimeConfig.isDebug
        #if DEBUG
        if AIEditUISmokeConfig.isEnabled || ImportProgressUISmokeConfig.isEnabled {
            setUser(Self.aiEditLiveSmokeUser)
            return
        }
        #endif
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
        guard isDemoVerificationEnabled else {
            errorMessage = "Email verification is not available in this build."
            return
        }
        let code = generateCode()
        emailVerificationCode = code
        pendingEmailVerification = email
    }

    func verifyEmail(code: String) -> Bool {
        guard isDemoVerificationEnabled else {
            errorMessage = "Email verification is not available in this build."
            return false
        }
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
        guard isDemoVerificationEnabled else {
            errorMessage = "Phone sign-in is not available in this build."
            return
        }
        let code = generateCode()
        phoneVerificationCode = code
        pendingPhoneVerification = phone
    }

    func signInWithPhone(phoneNumber: String, code: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        guard isDemoVerificationEnabled else {
            errorMessage = "Phone sign-in is not available in this build."
            return
        }

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
        guard isDemoVerificationEnabled else {
            errorMessage = "Account linking is not available in this build."
            return
        }
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
        guard isDemoVerificationEnabled else {
            errorMessage = "Account linking is not available in this build."
            return
        }
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
        guard isDemoVerificationEnabled else {
            errorMessage = "Phone verification is not available in this build."
            return false
        }
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
        clearTransientAuthState()
        currentUser = nil
        UserDefaults.standard.removeObject(forKey: userDefaultsKey)
        GIDSignIn.sharedInstance.signOut()
    }

    private func setUser(_ user: AuthUser) {
        errorMessage = nil
        isLoading = false
        currentUser = user
        if let data = try? JSONEncoder().encode(user) {
            UserDefaults.standard.set(data, forKey: userDefaultsKey)
        }
    }

    private func clearTransientAuthState() {
        isLoading = false
        errorMessage = nil
        emailVerificationCode = nil
        phoneVerificationCode = nil
        pendingEmailVerification = nil
        pendingPhoneVerification = nil
    }

    @discardableResult
    private func loadPersistedUser() -> AuthUser? {
        guard let data = UserDefaults.standard.data(forKey: userDefaultsKey),
              let user = try? JSONDecoder().decode(AuthUser.self, from: data) else { return nil }
        currentUser = user
        return user
    }

    #if DEBUG
    private static var aiEditLiveSmokeUser: AuthUser {
        AuthUser(id: "phase-edit3c-ui-smoke", displayName: "Smoke Guest", authMethod: .anonymous)
    }
    #endif
}

#if DEBUG
enum ImportProgressUISmokeConfig {
    static var isEnabled: Bool {
        ProcessInfo.processInfo.arguments.contains("--hoops-import-progress-smoke")
    }
}

enum AIEditUITestFixture: String {
    case stagingRenderReady = "staging_render_ready"
    case failingRender = "failing_render"
    case teamChoice = "team_choice"
    case reviewCrash = "review_crash"
}

enum AIEditUISmokeConfig {
    static var isEnabled: Bool {
        ProcessInfo.processInfo.arguments.contains("--hoops-ai-edit-live-smoke")
            || ProcessInfo.processInfo.arguments.contains("--hoops-team-choice-ui-smoke")
            || ProcessInfo.processInfo.arguments.contains("--hoops-review-crash-smoke")
            || truthy(environment["HOOPS_UI_SMOKE_MODE"])
            || smokeMode == AIEditUITestFixture.teamChoice.rawValue
            || smokeMode == AIEditUITestFixture.reviewCrash.rawValue
    }

    static var fixture: AIEditUITestFixture {
        if ProcessInfo.processInfo.arguments.contains("--hoops-team-choice-ui-smoke") {
            return .teamChoice
        }
        if ProcessInfo.processInfo.arguments.contains("--hoops-review-crash-smoke") {
            return .reviewCrash
        }
        if smokeMode == AIEditUITestFixture.teamChoice.rawValue {
            return .teamChoice
        }
        if smokeMode == AIEditUITestFixture.reviewCrash.rawValue {
            return .reviewCrash
        }
        let rawFixture = trimmed(environment["HOOPS_AI_EDIT_TEST_FIXTURE"]) ?? ""
        return AIEditUITestFixture(rawValue: rawFixture) ?? .stagingRenderReady
    }

    static var sourceObjectKey: String? {
        trimmed(environment["HOOPS_SMOKE_SOURCE_OBJECT_KEY"])
            ?? sourceObjectKey(for: fixture)
    }

    static var cloudAnalysisBaseURL: String? {
        trimmed(environment["HOOPS_CLOUD_ANALYSIS_BASE_URL"])
            ?? trimmed(environment["HOOPS_SMOKE_WORKER_URL"])
    }

    static var cloudEditBaseURL: String? {
        trimmed(environment["HOOPS_CLOUD_EDIT_BASE_URL"])
            ?? trimmed(environment["HOOPS_SMOKE_WORKER_URL"])
            ?? trimmed(environment["HOOPS_CLOUD_ANALYSIS_BASE_URL"])
    }

    static var installID: String? {
        trimmed(environment["HOOPS_SMOKE_INSTALL_ID"])
    }

    private static var environment: [String: String] {
        ProcessInfo.processInfo.environment
    }

    private static var smokeMode: String? {
        trimmed(environment["HOOPS_UI_SMOKE_MODE"])?.lowercased()
    }

    private static func sourceObjectKey(for fixture: AIEditUITestFixture) -> String? {
        switch fixture {
        case .stagingRenderReady, .failingRender:
            return "uploads/25a101ba8d234fd98094bd112276161f/source.mp4"
        case .teamChoice, .reviewCrash:
            return nil
        }
    }

    private static func truthy(_ rawValue: String?) -> Bool {
        guard let value = trimmed(rawValue)?.lowercased() else { return false }
        return ["1", "true", "yes", "ai_edit", "ai_edit_live"].contains(value)
    }

    private static func trimmed(_ rawValue: String?) -> String? {
        let value = rawValue?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return value.isEmpty ? nil : value
    }
}
#endif
