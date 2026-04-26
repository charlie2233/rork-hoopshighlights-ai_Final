import SwiftUI

struct VerificationView: View {
    @Bindable var authService: AuthService
    @State private var emailCode = ""
    @State private var phoneCode = ""
    @State private var linkEmail = ""
    @State private var linkPhoneRegion: PhoneRegion = .unitedStates
    @State private var linkPhone = ""
    @State private var showLinkEmail = false
    @State private var showLinkPhone = false
    @State private var showSuccess = false

    private var needsEmailVerification: Bool {
        guard let user = authService.currentUser else { return false }
        return user.email != nil && !user.isEmailVerified
    }

    private var needsPhoneVerification: Bool {
        guard let user = authService.currentUser else { return false }
        return user.phone != nil && !user.isPhoneVerified
    }

    private var isAnonymous: Bool {
        authService.currentUser?.authMethod == .anonymous
    }

    var body: some View {
        ZStack {
            HoopsMotionBackdrop(glowOpacity: 0.24)

            ScrollView {
                VStack(spacing: 24) {
                    Spacer().frame(height: 40)
                    headerSection
                    verificationCards
                    if isAnonymous {
                        guestLinkSection
                    }
                    skipButton
                    Spacer().frame(height: 40)
                }
                .padding(.horizontal, 24)
            }
        }
        .overlay {
            if showSuccess {
                successOverlay
            }
        }
    }

    private var headerSection: some View {
        VStack(spacing: 12) {
            HoopsMotionHero(icon: "checkmark.shield.fill", size: 172, accent: AppTheme.successGreen, secondary: AppTheme.neonPurple)

            Text(isAnonymous ? "Secure Your Account" : "Verify Your Identity")
                .font(.title2.bold())
                .foregroundStyle(.white)

            Text(isAnonymous
                 ? "Link an email or phone number to keep your data safe and unlock full features."
                 : "Complete verification to secure your account.")
                .font(.subheadline)
                .foregroundStyle(AppTheme.subtleText)
                .multilineTextAlignment(.center)
        }
    }

    @ViewBuilder
    private var verificationCards: some View {
        if needsEmailVerification {
            emailVerificationCard
        }
        if needsPhoneVerification {
            phoneVerificationCard
        }
    }

    private var emailVerificationCard: some View {
        VStack(spacing: 14) {
            HStack(spacing: 10) {
                Image(systemName: "envelope.badge.fill")
                    .foregroundStyle(AppTheme.neonPurple)
                Text("Verify Email")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
            }

            if let code = authService.emailVerificationCode {
                HStack(spacing: 8) {
                    Image(systemName: "info.circle.fill")
                        .foregroundStyle(AppTheme.neonPurple)
                        .font(.caption)
                    Text("Demo code: \(code)")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(10)
                .background(AppTheme.accentPurple.opacity(0.1), in: .rect(cornerRadius: 8))
            }

            TextField("Enter 6-digit code", text: $emailCode)
                .keyboardType(.numberPad)
                .foregroundStyle(.white)
                .padding(14)
                .background(AppTheme.surfaceBg.opacity(0.55), in: .rect(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(AppTheme.softBorder, lineWidth: 1))

            HStack(spacing: 12) {
                Button {
                    if let email = authService.currentUser?.email {
                        authService.sendEmailVerificationCode(to: email)
                    }
                } label: {
                    Text("Resend")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(AppTheme.neonPurple)
                }

                Spacer()

                Button {
                    if authService.verifyEmail(code: emailCode) {
                        withAnimation(.spring(duration: 0.4)) { showSuccess = true }
                        Task {
                            try? await Task.sleep(for: .seconds(1.5))
                            withAnimation { showSuccess = false }
                        }
                    }
                } label: {
                    Text("Verify")
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 24)
                        .padding(.vertical, 10)
                        .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 10))
                }
                .disabled(emailCode.count != 6)
                .opacity(emailCode.count == 6 ? 1 : 0.5)
            }
        }
        .padding(16)
        .rorkCard()
    }

    private var phoneVerificationCard: some View {
        VStack(spacing: 14) {
            HStack(spacing: 10) {
                Image(systemName: "phone.badge.checkmark.fill")
                    .foregroundStyle(AppTheme.neonPurple)
                Text("Verify Phone")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
            }

            if let code = authService.phoneVerificationCode {
                HStack(spacing: 8) {
                    Image(systemName: "info.circle.fill")
                        .foregroundStyle(AppTheme.neonPurple)
                        .font(.caption)
                    Text("Demo code: \(code)")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(10)
                .background(AppTheme.accentPurple.opacity(0.1), in: .rect(cornerRadius: 8))
            }

            TextField("Enter 6-digit code", text: $phoneCode)
                .keyboardType(.numberPad)
                .foregroundStyle(.white)
                .padding(14)
                .background(AppTheme.surfaceBg.opacity(0.55), in: .rect(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(AppTheme.softBorder, lineWidth: 1))

            HStack(spacing: 12) {
                Button {
                    if let phone = authService.currentUser?.phone {
                        authService.sendPhoneVerificationCode(to: phone)
                    }
                } label: {
                    Text("Resend")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(AppTheme.neonPurple)
                }

                Spacer()

                Button {
                    if authService.verifyPhone(code: phoneCode) {
                        withAnimation(.spring(duration: 0.4)) { showSuccess = true }
                        Task {
                            try? await Task.sleep(for: .seconds(1.5))
                            withAnimation { showSuccess = false }
                        }
                    }
                } label: {
                    Text("Verify")
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 24)
                        .padding(.vertical, 10)
                        .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 10))
                }
                .disabled(phoneCode.count != 6)
                .opacity(phoneCode.count == 6 ? 1 : 0.5)
            }
        }
        .padding(16)
        .rorkCard()
    }

    private var guestLinkSection: some View {
        VStack(spacing: 14) {
            if !showLinkEmail {
                Button {
                    withAnimation(.snappy) { showLinkEmail = true }
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: "envelope.fill")
                            .font(.title3)
                        Text("Link Email Address")
                            .font(.body.weight(.semibold))
                    }
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 52)
                    .background(AppTheme.surfaceBg, in: .rect(cornerRadius: 14))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppTheme.cardBorder, lineWidth: 1))
                }
            } else {
                VStack(spacing: 12) {
                    TextField("you@example.com", text: $linkEmail)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.emailAddress)
                        .autocorrectionDisabled()
                        .foregroundStyle(.white)
                        .padding(14)
                        .background(AppTheme.surfaceBg.opacity(0.55), in: .rect(cornerRadius: 12))
                        .overlay(RoundedRectangle(cornerRadius: 12).stroke(AppTheme.softBorder, lineWidth: 1))

                    Button {
                        guard !linkEmail.isEmpty else { return }
                        authService.linkEmail(linkEmail)
                    } label: {
                        Text("Send Verification Code")
                            .font(.subheadline.weight(.bold))
                            .foregroundStyle(.white)
                            .frame(maxWidth: .infinity)
                            .frame(height: 44)
                            .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 12))
                    }
                    .disabled(linkEmail.isEmpty)
                    .opacity(linkEmail.isEmpty ? 0.5 : 1)
                }
            }

            if !showLinkPhone {
                Button {
                    withAnimation(.snappy) { showLinkPhone = true }
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: "phone.fill")
                            .font(.title3)
                        Text("Link Phone Number")
                            .font(.body.weight(.semibold))
                    }
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 52)
                    .background(AppTheme.surfaceBg, in: .rect(cornerRadius: 14))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppTheme.cardBorder, lineWidth: 1))
                }
            } else {
                VStack(spacing: 12) {
                    PhoneNumberInputView(
                        title: "Phone Number",
                        selectedRegion: $linkPhoneRegion,
                        nationalNumber: $linkPhone
                    )

                    Button {
                        guard linkPhoneIsReady else { return }
                        authService.linkPhone(normalizedLinkPhone)
                    } label: {
                        Text("Send Verification Code")
                            .font(.subheadline.weight(.bold))
                            .foregroundStyle(.white)
                            .frame(maxWidth: .infinity)
                            .frame(height: 44)
                            .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 12))
                    }
                    .disabled(!linkPhoneIsReady)
                    .opacity(linkPhoneIsReady ? 1 : 0.5)
                }
            }
        }
    }

    private var normalizedLinkPhone: String {
        PhoneNumberFormatter.normalizedNumber(from: linkPhone, region: linkPhoneRegion)
    }

    private var linkPhoneIsReady: Bool {
        PhoneNumberFormatter.hasEnoughDigits(linkPhone, region: linkPhoneRegion)
    }

    private var skipButton: some View {
        Button {
            authService.pendingEmailVerification = nil
            authService.pendingPhoneVerification = nil
            authService.emailVerificationCode = nil
            authService.phoneVerificationCode = nil
        } label: {
            Text(isAnonymous ? "Continue as Guest" : "Skip for Now")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(AppTheme.subtleText)
        }
        .padding(.top, 8)
    }

    private var successOverlay: some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 56))
                .foregroundStyle(AppTheme.successGreen)
            Text("Verified!")
                .font(.title3.bold())
                .foregroundStyle(.white)
        }
        .padding(40)
        .background(.ultraThinMaterial, in: .rect(cornerRadius: 24))
        .transition(.scale.combined(with: .opacity))
    }
}
