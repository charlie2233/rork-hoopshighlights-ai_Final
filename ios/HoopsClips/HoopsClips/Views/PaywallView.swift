import SwiftUI
import RevenueCat

struct PaywallView: View {
    @Bindable var subscriptionManager: SubscriptionManager
    @Environment(\.dismiss) private var dismiss
    @State private var offerings: Offerings?
    @State private var isLoadingOfferings = true

    var body: some View {
        NavigationStack {
            ZStack {
                AppTheme.darkBg.ignoresSafeArea()
                AppTheme.meshBackground
                    .opacity(0.25)
                    .ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 28) {
                        Spacer().frame(height: 20)
                        headerSection
                        featuresSection
                        pricingSection
                        restoreSection
                        Spacer().frame(height: 40)
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
                }
            }
            .task {
                await loadOfferings()
            }
            .alert("Error", isPresented: .init(
                get: { subscriptionManager.errorMessage != nil },
                set: { if !$0 { subscriptionManager.errorMessage = nil } }
            )) {
                Button("OK") { subscriptionManager.errorMessage = nil }
            } message: {
                Text(subscriptionManager.errorMessage ?? "")
            }
        }
    }

    private var headerSection: some View {
        VStack(spacing: 16) {
            ZStack {
                Circle()
                    .fill(AppTheme.accentPurple.opacity(0.12))
                    .frame(width: 90, height: 90)
                Image(systemName: "crown.fill")
                    .font(.system(size: 40))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [AppTheme.neonPurple, AppTheme.electricViolet],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
            }

            Text("Go Pro")
                .font(.system(size: 32, weight: .bold))
                .foregroundStyle(.white)

            Text("Unlimited AI analysis with no restrictions.\nYou've used \(max(AppConstants.cloudAnalysisDailyQuota - subscriptionManager.freeUsesRemaining, 0)) of \(AppConstants.cloudAnalysisDailyQuota) free analyses.")
                .font(.subheadline)
                .foregroundStyle(AppTheme.subtleText)
                .multilineTextAlignment(.center)
                .lineSpacing(4)
        }
    }

    private var featuresSection: some View {
        VStack(spacing: 12) {
            featureRow(icon: "infinity", title: "Unlimited Analyses", subtitle: "No caps on video processing")
            featureRow(icon: "bolt.fill", title: "Priority Processing", subtitle: "Faster AI detection pipeline")
            featureRow(icon: "film.stack.fill", title: "Unlimited Exports", subtitle: "Export all your highlights freely")
            featureRow(icon: "sparkles", title: "Same AI Model", subtitle: "Free and Pro use the same highlight detection model")
        }
        .padding(16)
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
            if isLoadingOfferings {
                ProgressView()
                    .tint(AppTheme.neonPurple)
                    .frame(height: 60)
            } else if let package = offerings?.current?.availablePackages.first {
                Button {
                    Task {
                        let success = await subscriptionManager.purchase(package: package)
                        if success { dismiss() }
                    }
                } label: {
                    VStack(spacing: 4) {
                        HStack(spacing: 8) {
                            if subscriptionManager.isLoading {
                                ProgressView().tint(.white).controlSize(.small)
                            }
                            Text(subscriptionManager.isLoading ? "Processing..." : "Subscribe Now")
                                .font(.title3.bold())
                        }
                        Text("\(package.storeProduct.localizedPriceString)/month")
                            .font(.subheadline)
                            .opacity(0.85)
                    }
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 64)
                    .background(
                        LinearGradient(
                            colors: [AppTheme.accentPurple, AppTheme.deepPurple],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        in: .rect(cornerRadius: 16)
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 16)
                            .stroke(AppTheme.neonPurple.opacity(0.4), lineWidth: 1.5)
                    )
                    .shadow(color: AppTheme.neonPurple.opacity(0.3), radius: 12, y: 6)
                }
                .disabled(subscriptionManager.isLoading)
            } else {
                VStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.title2)
                        .foregroundStyle(AppTheme.warningYellow)
                    Text("Unable to load subscription options.")
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.subtleText)
                    Button("Retry") {
                        Task { await loadOfferings() }
                    }
                    .font(.subheadline.bold())
                    .foregroundStyle(AppTheme.neonPurple)
                }
                .frame(height: 80)
            }

            Text("Cancel anytime. Subscription auto-renews monthly.")
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .multilineTextAlignment(.center)
        }
    }

    private var restoreSection: some View {
        Button {
            Task { await subscriptionManager.restorePurchases() }
        } label: {
            Text("Restore Purchases")
                .font(.subheadline.weight(.medium))
                .foregroundStyle(AppTheme.neonPurple)
        }
    }

    private func loadOfferings() async {
        isLoadingOfferings = true
        do {
            offerings = try await Purchases.shared.offerings()
        } catch {
            offerings = nil
        }
        isLoadingOfferings = false
    }
}
