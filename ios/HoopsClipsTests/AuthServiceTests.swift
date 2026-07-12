import Foundation
import Testing
@testable import HoopsClips

@MainActor
struct AuthServiceTests {
    @Test
    func demoPhoneVerificationStaysDisabledOutsideDevelopmentBuilds() async {
        UserDefaults.standard.removeObject(forKey: "hoops_auth_user")
        let service = AuthService(
            emailAuthClient: FirebaseEmailAuthClient(apiKey: ""),
            isDemoVerificationEnabled: false
        )

        service.sendPhoneVerificationCode(to: "+15555550123")

        #expect(service.phoneVerificationCode == nil)
        #expect(service.pendingPhoneVerification == nil)
        #expect(service.errorMessage == "Phone sign-in is not available in this build.")

        await service.signInWithPhone(phoneNumber: "+15555550123", code: "123456")

        #expect(service.currentUser == nil)
        #expect(service.errorMessage == "Phone sign-in is not available in this build.")
    }

    @Test
    func demoGuestLinkingStaysDisabledOutsideDevelopmentBuilds() {
        UserDefaults.standard.removeObject(forKey: "hoops_auth_user")
        let service = AuthService(
            emailAuthClient: FirebaseEmailAuthClient(apiKey: ""),
            isDemoVerificationEnabled: false
        )
        service.signInAnonymously()

        service.linkEmail("player@example.com")

        #expect(service.currentUser?.email == nil)
        #expect(service.pendingEmailVerification == nil)
        #expect(service.emailVerificationCode == nil)
        #expect(service.errorMessage == "Account linking is not available in this build.")

        service.signOut()
    }
}
