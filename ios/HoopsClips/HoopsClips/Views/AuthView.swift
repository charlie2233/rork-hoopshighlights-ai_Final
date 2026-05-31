import SwiftUI
import AuthenticationServices
import GoogleSignIn

struct AuthView: View {
    @Bindable var authService: AuthService
    @Environment(AppLanguageStore.self) private var languageStore
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var authMode: AuthMode = .welcome
    @State private var email = ""
    @State private var password = ""
    @State private var selectedPhoneRegion: PhoneRegion = .unitedStates
    @State private var phoneNumber = ""
    @State private var verificationCode = ""
    @State private var codeSent = false
    @State private var showError = false

    private enum AuthMode: Equatable {
        case welcome
        case email
        case phone
    }

    var body: some View {
        ZStack {
            HoopsMotionBackdrop(glowOpacity: 0.28)

            ScrollView {
                VStack(spacing: 0) {
                    Spacer().frame(height: 60)
                    heroSection
                    Spacer().frame(height: 40)
                    authButtons
                    Spacer().frame(height: 20)
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 40)
            }
        }
        .alert(languageStore.text(.signInError), isPresented: $showError) {
            Button("OK") { }
        } message: {
            Text(authService.errorMessage ?? "Something went wrong.")
        }
        .onChange(of: authService.errorMessage) { _, newValue in
            if let newValue {
                showError = true
                HoopsAccessibility.announce(newValue)
            }
        }
        .onChange(of: authService.isLoading) { _, isLoading in
            if isLoading {
                HoopsAccessibility.announce(languageStore.text(.signingIn))
            }
        }
    }

    private var heroSection: some View {
        VStack(spacing: 16) {
            HoopsBrandMark(size: 142)

            VStack(spacing: 8) {
                Text("HoopClips")
                    .font(.system(size: 32, weight: .bold))
                    .foregroundStyle(.white)
            }

            Text(languageStore.text(.authTagline))
                .font(.subheadline)
                .foregroundStyle(AppTheme.subtleText)
                .multilineTextAlignment(.center)
                .lineSpacing(4)
        }
    }

    @ViewBuilder
    private var authButtons: some View {
        switch authMode {
        case .welcome:
            welcomeButtons
        case .email:
            emailForm
        case .phone:
            phoneForm
        }
    }

    private var welcomeButtons: some View {
        VStack(spacing: 14) {
            SignInWithAppleButton(.signIn) { request in
                request.requestedScopes = [.fullName, .email]
            } onCompletion: { result in
                authService.signInWithApple(result: result)
            }
            .signInWithAppleButtonStyle(.white)
            .frame(minHeight: 52)
            .clipShape(.rect(cornerRadius: 14))
            .accessibilityHint("Signs in with your Apple ID.")

            Button {
                signInWithGoogle()
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "g.circle.fill")
                        .font(.title2)
                    Text(languageStore.text(.continueWithGoogle))
                        .font(.body.weight(.semibold))
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(minHeight: 52)
                .padding(.vertical, 2)
                .background(Color(red: 0.26, green: 0.52, blue: 0.96), in: .rect(cornerRadius: 14))
            }
            .accessibilityHint("Opens Google Sign-In.")

            HStack(spacing: 12) {
                Rectangle()
                    .fill(AppTheme.softBorder)
                    .frame(height: 1)
                Text(languageStore.text(.or))
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
                Rectangle()
                    .fill(AppTheme.softBorder)
                    .frame(height: 1)
            }
            .padding(.vertical, 4)

            Button {
                HoopsAccessibility.animate(reduceMotion: reduceMotion) { authMode = .email }
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "envelope.fill")
                        .font(.title3)
                    Text(languageStore.text(.continueWithEmail))
                        .font(.body.weight(.semibold))
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(minHeight: 52)
                .padding(.vertical, 2)
                .background(AppTheme.surfaceBg, in: .rect(cornerRadius: 14))
                .overlay(
                    RoundedRectangle(cornerRadius: 14)
                        .stroke(AppTheme.cardBorder, lineWidth: 1)
                )
            }

            Button {
                HoopsAccessibility.animate(reduceMotion: reduceMotion) { authMode = .phone }
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "phone.fill")
                        .font(.title3)
                    Text(languageStore.text(.continueWithPhone))
                        .font(.body.weight(.semibold))
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(minHeight: 52)
                .padding(.vertical, 2)
                .background(AppTheme.surfaceBg, in: .rect(cornerRadius: 14))
                .overlay(
                    RoundedRectangle(cornerRadius: 14)
                        .stroke(AppTheme.cardBorder, lineWidth: 1)
                )
            }

            Button {
                authService.signInAnonymously()
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "person.fill.questionmark")
                        .font(.title3)
                    Text(languageStore.text(.continueAsGuest))
                        .font(.body.weight(.semibold))
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                }
                .foregroundStyle(AppTheme.subtleText)
                .frame(maxWidth: .infinity)
                .frame(minHeight: 52)
                .padding(.vertical, 2)
                .background(AppTheme.surfaceBg.opacity(0.4), in: .rect(cornerRadius: 14))
                .overlay(
                    RoundedRectangle(cornerRadius: 14)
                        .stroke(AppTheme.softBorder, lineWidth: 1)
                )
            }

            legalAcknowledgement
                .padding(.top, 8)
        }
    }

    @ViewBuilder
    private var legalAcknowledgement: some View {
        if let termsURL = AppConstants.termsOfServiceURL,
           let privacyURL = AppConstants.privacyPolicyURL {
            VStack(spacing: 4) {
                Text(languageStore.text(.legalPrefix))
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)

                ViewThatFits(in: .vertical) {
                    HStack(spacing: 4) {
                        legalLink(title: languageStore.text(.legalTerms), url: termsURL)
                        Text(languageStore.text(.legalAnd))
                            .font(.caption2)
                            .foregroundStyle(AppTheme.subtleText)
                        legalLink(title: languageStore.text(.legalPrivacy), url: privacyURL)
                    }

                    VStack(spacing: 4) {
                        legalLink(title: languageStore.text(.legalTerms), url: termsURL)
                        legalLink(title: languageStore.text(.legalPrivacy), url: privacyURL)
                    }
                }
                .multilineTextAlignment(.center)
            }
        } else {
            Text(languageStore.text(.legalFallback))
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .multilineTextAlignment(.center)
        }
    }

    private func legalLink(title: String, url: URL) -> some View {
        Link(destination: url) {
            Text(title)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(AppTheme.neonPurple)
                .underline()
        }
    }

    private var emailForm: some View {
        VStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                Text(languageStore.text(.email))
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.subtleText)
                TextField("you@example.com", text: $email)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.emailAddress)
                    .autocorrectionDisabled()
                    .foregroundStyle(.white)
                    .padding(14)
                    .background(AppTheme.surfaceBg.opacity(0.55), in: .rect(cornerRadius: 12))
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(AppTheme.softBorder, lineWidth: 1))
            }

            VStack(alignment: .leading, spacing: 8) {
                Text(languageStore.text(.password))
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.subtleText)
                SecureField(languageStore.text(.passwordPlaceholder), text: $password)
                    .foregroundStyle(.white)
                    .padding(14)
                    .background(AppTheme.surfaceBg.opacity(0.55), in: .rect(cornerRadius: 12))
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(AppTheme.softBorder, lineWidth: 1))
            }

            Button {
                Task { await authService.signInWithEmail(email: email, password: password) }
            } label: {
                HStack(spacing: 8) {
                    if authService.isLoading {
                        ProgressView().tint(.white).controlSize(.small)
                            .accessibilityLabel(languageStore.text(.signingIn))
                    }
                    Text(authService.isLoading ? languageStore.text(.signingIn) : languageStore.text(.signIn))
                        .font(.body.weight(.bold))
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(minHeight: 52)
                .padding(.vertical, 2)
                .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 14))
            }
            .disabled(authService.isLoading)
            .accessibilityLabel(authService.isLoading ? languageStore.text(.signingIn) : languageStore.text(.signIn))
            .accessibilityValue(authService.isLoading ? "In progress" : "Ready")

            backButton
        }
    }

    private var phoneForm: some View {
        VStack(spacing: 16) {
            PhoneNumberInputView(
                title: languageStore.text(.phoneNumber),
                selectedRegion: $selectedPhoneRegion,
                nationalNumber: $phoneNumber
            )

            if !codeSent {
                Button {
                    authService.sendPhoneVerificationCode(to: normalizedPhoneNumber)
                    HoopsAccessibility.animate(reduceMotion: reduceMotion) { codeSent = true }
                } label: {
                    Text(languageStore.text(.sendCode))
                        .font(.body.weight(.bold))
                        .foregroundStyle(.white)
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                        .frame(maxWidth: .infinity)
                        .frame(minHeight: 52)
                        .padding(.vertical, 2)
                        .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 14))
                }
                .disabled(!isPhoneNumberReady)
                .opacity(isPhoneNumberReady ? 1 : 0.5)
                .accessibilityValue(isPhoneNumberReady ? "Ready" : "Enter a valid phone number")
            } else {
                codeInfoBanner(destination: normalizedPhoneNumber)

                VStack(alignment: .leading, spacing: 8) {
                    Text(languageStore.text(.verificationCode))
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(AppTheme.subtleText)
                    TextField("123456", text: $verificationCode)
                        .keyboardType(.numberPad)
                        .foregroundStyle(.white)
                        .padding(14)
                        .background(AppTheme.surfaceBg.opacity(0.55), in: .rect(cornerRadius: 12))
                        .overlay(RoundedRectangle(cornerRadius: 12).stroke(AppTheme.softBorder, lineWidth: 1))
                }

                Button {
                    Task { await authService.signInWithPhone(phoneNumber: normalizedPhoneNumber, code: verificationCode) }
                } label: {
                    HStack(spacing: 8) {
                        if authService.isLoading {
                            ProgressView().tint(.white).controlSize(.small)
                                .accessibilityLabel(languageStore.text(.verifying))
                        }
                        Text(authService.isLoading ? languageStore.text(.verifying) : languageStore.text(.verifyAndSignIn))
                            .font(.body.weight(.bold))
                            .multilineTextAlignment(.center)
                            .lineLimit(2)
                    }
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .frame(minHeight: 52)
                    .padding(.vertical, 2)
                    .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 14))
                }
                .disabled(authService.isLoading)
                .accessibilityLabel(authService.isLoading ? languageStore.text(.verifying) : languageStore.text(.verifyAndSignIn))
                .accessibilityValue(authService.isLoading ? "In progress" : "Ready")

                Button {
                    authService.sendPhoneVerificationCode(to: normalizedPhoneNumber)
                } label: {
                    Text(languageStore.text(.resendCode))
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(AppTheme.neonPurple)
                }
            }

            backButton
        }
    }

    private var normalizedPhoneNumber: String {
        PhoneNumberFormatter.normalizedNumber(from: phoneNumber, region: selectedPhoneRegion)
    }

    private var isPhoneNumberReady: Bool {
        PhoneNumberFormatter.hasEnoughDigits(phoneNumber, region: selectedPhoneRegion)
    }

    private func codeInfoBanner(destination: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "info.circle.fill")
                .foregroundStyle(AppTheme.neonPurple)
            VStack(alignment: .leading, spacing: 2) {
                Text(languageStore.text(.codeSent))
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.white)
                Text("Code: \(authService.phoneVerificationCode ?? "------")")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(AppTheme.neonPurple)
                Text(languageStore.text(.demoCodeNote))
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.accentPurple.opacity(0.1), in: .rect(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(AppTheme.accentPurple.opacity(0.25), lineWidth: 1))
    }

    private var backButton: some View {
        Button {
            HoopsAccessibility.animate(reduceMotion: reduceMotion) {
                authMode = .welcome
                codeSent = false
                verificationCode = ""
            }
        } label: {
            HStack(spacing: 6) {
                Image(systemName: "chevron.left")
                    .font(.caption.bold())
                Text(languageStore.text(.backToSignIn))
                    .font(.subheadline)
            }
            .foregroundStyle(AppTheme.neonPurple)
        }
        .padding(.top, 4)
    }

    private func signInWithGoogle() {
        guard let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
              let rootVC = windowScene.windows.first?.rootViewController else { return }
        Task { await authService.signInWithGoogle(presenting: rootVC) }
    }
}
