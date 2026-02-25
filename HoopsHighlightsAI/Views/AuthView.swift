import SwiftUI
import AuthenticationServices
import GoogleSignIn

struct AuthView: View {
    @Bindable var authService: AuthService
    @State private var authMode: AuthMode = .welcome
    @State private var email = ""
    @State private var password = ""
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
            AppTheme.darkBg.ignoresSafeArea()
            AppTheme.meshBackground
                .opacity(0.3)
                .ignoresSafeArea()

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
        .alert("Sign In Error", isPresented: $showError) {
            Button("OK") { }
        } message: {
            Text(authService.errorMessage ?? "Something went wrong.")
        }
        .onChange(of: authService.errorMessage) { _, newValue in
            if newValue != nil { showError = true }
        }
    }

    private var heroSection: some View {
        VStack(spacing: 16) {
            ZStack {
                Circle()
                    .fill(AppTheme.accentPurple.opacity(0.15))
                    .frame(width: 100, height: 100)
                Circle()
                    .fill(AppTheme.accentPurple.opacity(0.08))
                    .frame(width: 130, height: 130)
                Image(systemName: "basketball.fill")
                    .font(.system(size: 44))
                    .foregroundStyle(AppTheme.neonPurple)
            }

            VStack(spacing: 8) {
                Text("Hoops Highlights")
                    .font(.system(size: 28, weight: .bold))
                    .foregroundStyle(.white)
                Text("AI")
                    .font(.system(size: 28, weight: .bold))
                    .foregroundStyle(AppTheme.neonPurple)
            }

            Text("AI-powered basketball highlight detection.\nSign in to get started.")
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
            .frame(height: 52)
            .clipShape(.rect(cornerRadius: 14))

            Button {
                signInWithGoogle()
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "g.circle.fill")
                        .font(.title2)
                    Text("Continue with Google")
                        .font(.body.weight(.semibold))
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
                .background(Color(red: 0.26, green: 0.52, blue: 0.96), in: .rect(cornerRadius: 14))
            }

            HStack(spacing: 12) {
                Rectangle()
                    .fill(AppTheme.softBorder)
                    .frame(height: 1)
                Text("or")
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
                Rectangle()
                    .fill(AppTheme.softBorder)
                    .frame(height: 1)
            }
            .padding(.vertical, 4)

            Button {
                withAnimation(.snappy) { authMode = .email }
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "envelope.fill")
                        .font(.title3)
                    Text("Continue with Email")
                        .font(.body.weight(.semibold))
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
                .background(AppTheme.surfaceBg, in: .rect(cornerRadius: 14))
                .overlay(
                    RoundedRectangle(cornerRadius: 14)
                        .stroke(AppTheme.cardBorder, lineWidth: 1)
                )
            }

            Button {
                withAnimation(.snappy) { authMode = .phone }
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "phone.fill")
                        .font(.title3)
                    Text("Continue with Phone")
                        .font(.body.weight(.semibold))
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
                .background(AppTheme.surfaceBg, in: .rect(cornerRadius: 14))
                .overlay(
                    RoundedRectangle(cornerRadius: 14)
                        .stroke(AppTheme.cardBorder, lineWidth: 1)
                )
            }

            Text("By signing in, you agree to our Terms of Service and Privacy Policy.")
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .multilineTextAlignment(.center)
                .padding(.top, 8)
        }
    }

    private var emailForm: some View {
        VStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Email")
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
                Text("Password")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.subtleText)
                SecureField("Min 6 characters", text: $password)
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
                    }
                    Text(authService.isLoading ? "Signing in..." : "Sign In")
                        .font(.body.weight(.bold))
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
                .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 14))
            }
            .disabled(authService.isLoading)

            backButton
        }
    }

    private var phoneForm: some View {
        VStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Phone Number")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.subtleText)
                TextField("+1 (555) 123-4567", text: $phoneNumber)
                    .keyboardType(.phonePad)
                    .foregroundStyle(.white)
                    .padding(14)
                    .background(AppTheme.surfaceBg.opacity(0.55), in: .rect(cornerRadius: 12))
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(AppTheme.softBorder, lineWidth: 1))
            }

            if !codeSent {
                Button {
                    withAnimation(.snappy) { codeSent = true }
                } label: {
                    Text("Send Code")
                        .font(.body.weight(.bold))
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 52)
                        .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 14))
                }
                .disabled(phoneNumber.isEmpty)
                .opacity(phoneNumber.isEmpty ? 0.5 : 1)
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Verification Code")
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
                    Task { await authService.signInWithPhone(phoneNumber: phoneNumber, code: verificationCode) }
                } label: {
                    HStack(spacing: 8) {
                        if authService.isLoading {
                            ProgressView().tint(.white).controlSize(.small)
                        }
                        Text(authService.isLoading ? "Verifying..." : "Verify & Sign In")
                            .font(.body.weight(.bold))
                    }
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 52)
                    .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 14))
                }
                .disabled(authService.isLoading)
            }

            backButton
        }
    }

    private var backButton: some View {
        Button {
            withAnimation(.snappy) {
                authMode = .welcome
                codeSent = false
                verificationCode = ""
            }
        } label: {
            HStack(spacing: 6) {
                Image(systemName: "chevron.left")
                    .font(.caption.bold())
                Text("Back to sign in options")
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
