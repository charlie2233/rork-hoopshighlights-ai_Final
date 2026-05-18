import SwiftUI
import RevenueCat

struct PaywallView: View {
    @Bindable var subscriptionManager: SubscriptionManager
    @Bindable var authService: AuthService
    @Environment(\.dismiss) private var dismiss
    @State private var offerings: Offerings?
    @State private var isLoadingOfferings = false
    @State private var offeringsLoadMessage: String?

    #if DEBUG
    private var isScreenshotMode: Bool {
        ProcessInfo.processInfo.arguments.contains("--hoops-paywall-screenshot")
    }
    #else
    private var isScreenshotMode: Bool { false }
    #endif

    private var requiresSignedInAccount: Bool {
        if isScreenshotMode { return false }
        return authService.currentUser?.authMethod == .anonymous
    }

    var body: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.26)

                ScrollView {
                    VStack(spacing: isScreenshotMode ? 16 : 28) {
                        Spacer().frame(height: isScreenshotMode ? 0 : 20)
                        headerSection
                        featuresSection
                        pricingSection
                        restoreSection
                        Spacer().frame(height: isScreenshotMode ? 12 : 40)
                    }
                    .padding(.horizontal, 24)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.title3)
                            .foregroundStyle(AppTheme.subtleText)
                    }
                    .accessibilityLabel("Close Premium")
                    .accessibilityHint("Dismisses the membership screen.")
                }
            }
            .task {
                if isScreenshotMode {
                    offerings = nil
                    offeringsLoadMessage = nil
                    isLoadingOfferings = false
                } else if requiresSignedInAccount {
                    offerings = nil
                    offeringsLoadMessage = nil
                    isLoadingOfferings = false
                } else if subscriptionManager.billingConfigured {
                    await subscriptionManager.syncAuthenticatedUser(authService.currentUser)
                    await loadOfferings()
                } else {
                    isLoadingOfferings = false
                }
            }
            .alert("Error", isPresented: .init(
                get: { subscriptionManager.errorMessage != nil },
                set: { if !$0 { subscriptionManager.errorMessage = nil } }
            )) {
                Button("OK") { subscriptionManager.errorMessage = nil }
            } message: {
                Text(subscriptionManager.errorMessage ?? "")
            }
            .onChange(of: isLoadingOfferings) { _, isLoading in
                if isLoading {
                    HoopsAccessibility.announce("Loading subscription options.")
                }
            }
            .onChange(of: subscriptionManager.isLoading) { _, isLoading in
                if isLoading {
                    HoopsAccessibility.announce("Processing subscription.")
                }
            }
        }
    }

    private var headerSection: some View {
        VStack(spacing: isScreenshotMode ? 10 : 16) {
            HoopsMotionHero(
                icon: "crown.fill",
                size: isScreenshotMode ? 118 : 188,
                accent: AppTheme.neonPurple,
                secondary: AppTheme.warningYellow
            )

            Text("HoopClips Pro")
                .font(.system(size: isScreenshotMode ? 28 : 32, weight: .bold))
                .foregroundStyle(.white)

            Text("Unlock priority cloud AI editing, cleaner exports, longer videos, more revisions, and Pro template access as it rolls out.")
                .font(.subheadline)
                .foregroundStyle(AppTheme.subtleText)
                .multilineTextAlignment(.center)
                .lineSpacing(4)
        }
    }

    private var featuresSection: some View {
        VStack(spacing: isScreenshotMode ? 10 : 12) {
            featureRow(icon: "bolt.fill", title: "Priority cloud AI Edit", subtitle: "Move through the Pro render queue when capacity is available")
            featureRow(icon: "sparkles.tv.fill", title: "1080p clean exports", subtitle: "Remove required HoopClips watermark and outro when policy allows")
            featureRow(icon: "film.stack.fill", title: "More revisions and storage", subtitle: "Create longer edits, revise more, and keep cloud renders longer")
            featureRow(icon: "rectangle.stack.badge.play.fill", title: "Pro template packs", subtitle: "Unlock premium styles like Recruiting Reel and Cinematic Mixtape as they launch")
        }
        .padding(isScreenshotMode ? 14 : 16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder, glowOpacity: 0.06)
    }

    private func featureRow(icon: String, title: String, subtitle: String) -> some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(AppTheme.accentPurple.opacity(0.15))
                    .frame(width: 38, height: 38)
                Image(systemName: icon)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(AppTheme.neonPurple)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
            }

            Spacer()

            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(AppTheme.successGreen)
                .font(.body)
        }
    }

    private var pricingSection: some View {
        VStack(spacing: 14) {
            if requiresSignedInAccount {
                accountRequiredSection
            } else if isLoadingOfferings {
                ProgressView()
                    .tint(AppTheme.neonPurple)
                    .frame(height: 60)
                    .accessibilityLabel("Loading subscription options")
            } else if isScreenshotMode {
                premiumPlanCard(
                    priceText: "$9.99/month",
                    buttonTitle: "Start Pro",
                    isProcessing: false
                ) { }
            } else if !subscriptionManager.billingConfigured {
                VStack(spacing: 8) {
                    Image(systemName: "creditcard.trianglebadge.exclamationmark")
                        .font(.title2)
                        .foregroundStyle(AppTheme.warningYellow)
                    Text(subscriptionManager.billingUnavailableMessage)
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.subtleText)
                    Text("Please try again later.")
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .multilineTextAlignment(.center)
                }
                .frame(height: 96)
            } else if let package = offerings?.current?.availablePackages.first {
                Button {
                    Task {
                        let success = await subscriptionManager.purchase(package: package)
                        if success { dismiss() }
                    }
                } label: {
                    premiumPlanCardContent(
                        priceText: "\(package.storeProduct.localizedPriceString)/month",
                        buttonTitle: subscriptionManager.isLoading ? "Processing..." : "Start Pro",
                        isProcessing: subscriptionManager.isLoading
                    )
                }
                .disabled(subscriptionManager.isLoading)
                .accessibilityIdentifier("paywall.premium.startButton")
            } else {
                VStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.title2)
                        .foregroundStyle(AppTheme.warningYellow)
                    Text("Unable to load subscription options.")
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.subtleText)
                    if let offeringsLoadMessage {
                        Text(offeringsLoadMessage)
                            .font(.caption2)
                            .foregroundStyle(AppTheme.subtleText)
                            .multilineTextAlignment(.center)
                    }
                    Button("Retry") {
                        Task { await loadOfferings() }
                    }
                    .font(.subheadline.bold())
                    .foregroundStyle(AppTheme.neonPurple)
                    .accessibilityIdentifier("paywall.offerings.retryButton")
                }
                .frame(minHeight: 104)
            }

            Text(requiresSignedInAccount ? "Memberships stay attached to your signed-in account." : "Cancel anytime. Subscription auto-renews monthly.")
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .multilineTextAlignment(.center)
        }
    }

    private func premiumPlanCard(
        priceText: String,
        buttonTitle: String,
        isProcessing: Bool,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            premiumPlanCardContent(
                priceText: priceText,
                buttonTitle: buttonTitle,
                isProcessing: isProcessing
            )
        }
        .disabled(isProcessing)
        .accessibilityIdentifier("paywall.premium.startButton")
    }

    private func premiumPlanCardContent(
        priceText: String,
        buttonTitle: String,
        isProcessing: Bool
    ) -> some View {
        VStack(spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Pro Monthly")
                        .font(.headline.weight(.semibold))
                    Text(priceText)
                        .font(.title3.weight(.bold))
                }

                Spacer()

                Text("Best value")
                    .font(.caption.weight(.bold))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(AppTheme.warningYellow.opacity(0.16), in: .capsule)
                    .foregroundStyle(AppTheme.warningYellow)
            }

            HStack(spacing: 8) {
                if isProcessing {
                    ProgressView().tint(.white).controlSize(.small)
                        .accessibilityLabel("Processing subscription")
                }
                Text(buttonTitle)
                    .font(.title3.bold())
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
            }
            .frame(maxWidth: .infinity)
            .frame(minHeight: isScreenshotMode ? 50 : 56)
            .padding(.vertical, 2)
            .background(
                LinearGradient(
                    colors: [AppTheme.accentPurple, AppTheme.deepPurple],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ),
                in: .rect(cornerRadius: 16)
            )
        }
        .foregroundStyle(.white)
        .padding(isScreenshotMode ? 14 : 16)
        .background(AppTheme.cardBg.opacity(0.86), in: RoundedRectangle(cornerRadius: 20))
        .overlay(
            RoundedRectangle(cornerRadius: 20)
                .stroke(AppTheme.neonPurple.opacity(0.38), lineWidth: 1.5)
        )
        .shadow(color: AppTheme.neonPurple.opacity(0.25), radius: 14, y: 7)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Pro Monthly")
        .accessibilityValue("\(priceText). \(buttonTitle)")
    }

    private var accountRequiredSection: some View {
        VStack(spacing: 12) {
            Image(systemName: "person.crop.circle.badge.exclamationmark")
                .font(.title2)
                .foregroundStyle(AppTheme.warningYellow)

            Text("Sign in to get a membership.")
                .font(.headline)
                .foregroundStyle(.white)

            Text("Memberships are tied to your Hoopclips account. Sign in with Google, Apple, email, or phone before upgrading.")
                .font(.subheadline)
                .foregroundStyle(AppTheme.subtleText)
                .multilineTextAlignment(.center)
                .lineSpacing(3)

            Button {
                authService.signOut()
                dismiss()
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "person.crop.circle.fill.badge.plus")
                    Text("Sign In to Upgrade")
                        .font(.subheadline.bold())
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(minHeight: 48)
                .padding(.vertical, 2)
                .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 14))
                .overlay(
                    RoundedRectangle(cornerRadius: 14)
                        .stroke(AppTheme.neonPurple.opacity(0.35), lineWidth: 1)
                )
            }
            .accessibilityHint("Returns to the sign-in screen so membership can attach to your account.")
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder, glowOpacity: 0.05)
    }

    private var restoreSection: some View {
        Group {
            if requiresSignedInAccount {
                Text("Already Pro? Sign in first, then restore purchases.")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(AppTheme.subtleText)
                    .multilineTextAlignment(.center)
            } else {
                Button {
                    Task { await subscriptionManager.restorePurchases() }
                } label: {
                    Text("Restore Purchases")
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(AppTheme.neonPurple)
                }
                .accessibilityIdentifier("paywall.restorePurchases")
            }
        }
    }

    private func loadOfferings() async {
        guard !requiresSignedInAccount else {
            offerings = nil
            offeringsLoadMessage = nil
            isLoadingOfferings = false
            return
        }

        guard subscriptionManager.billingConfigured else {
            offerings = nil
            isLoadingOfferings = false
            return
        }

        isLoadingOfferings = true
        offeringsLoadMessage = nil
        do {
            let loadedOfferings = try await Purchases.shared.offerings()
            offerings = loadedOfferings

            if loadedOfferings.current == nil {
                offeringsLoadMessage = "Subscription options are temporarily unavailable. Please try again later."
                LaunchTelemetry.shared.recordConfigurationIssue("RevenueCat offerings loaded without a current offering.")
            } else if loadedOfferings.current?.availablePackages.isEmpty == true {
                offeringsLoadMessage = "Subscription options are temporarily unavailable. Please try again later."
                LaunchTelemetry.shared.recordConfigurationIssue("RevenueCat current offering loaded with no available packages.")
            }
        } catch {
            offerings = nil
            offeringsLoadMessage = "Subscription options are temporarily unavailable. Please try again later."
            LaunchTelemetry.shared.recordConfigurationIssue("RevenueCat offerings failed: \(error.localizedDescription)")
        }
        isLoadingOfferings = false
    }
}
