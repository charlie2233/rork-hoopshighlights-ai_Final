import SwiftUI

struct UploadsWorkflowView: View {
    @Bindable var viewModel: HighlightsViewModel
    var onOpenHistory: () -> Void
    var onOpenSettings: () -> Void
    var onOpenReview: () -> Void

    var body: some View {
        VideoPlayerView(
            viewModel: viewModel,
            onOpenHistory: onOpenHistory,
            onOpenSettings: onOpenSettings,
            onOpenReview: onOpenReview
        )
    }
}

struct AIEditWorkflowView: View {
    @Bindable var viewModel: HighlightsViewModel
    var onRequestProUpgrade: () -> Void

    @Environment(SubscriptionManager.self) private var subscriptionManager
    @Environment(AuthService.self) private var authService

    var body: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.18)

                ScrollView {
                    VStack(spacing: 18) {
                        workflowHeader
                        AIEditView(
                            viewModel: viewModel,
                            isProUser: subscriptionManager.isProUser,
                            revenueCatAppUserID: subscriptionManager.revenueCatAppUserID,
                            presentation: .exportSection,
                            onRequestProUpgrade: onRequestProUpgrade
                        )
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                    .padding(.bottom, 100)
                }
            }
            .navigationTitle("AI Edit")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
        .environment(subscriptionManager)
        .environment(authService)
    }

    private var workflowHeader: some View {
        VStack(alignment: .leading, spacing: 12) {
            RorkSectionHeader(
                title: "AI Edit job",
                icon: "wand.and.stars.inverse",
                subtitle: viewModel.canRequestCloudEdit
                    ? "Choose style, duration, aspect ratio, then let the cloud build the edit plan and render job."
                    : (viewModel.cloudEditUnavailableReason ?? "Review or analyze clips before rendering.")
            )

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: "film.stack.fill",
                    value: "\(viewModel.cloudEditCandidatePoolCount)",
                    label: "Candidates",
                    tint: AppTheme.neonPurple
                )
                RorkMetricChip(
                    icon: viewModel.cloudEditSourceObjectKey == nil ? "icloud.slash.fill" : "icloud.fill",
                    value: viewModel.cloudEditSourceObjectKey == nil ? "Pending" : "Ready",
                    label: "Source",
                    tint: viewModel.cloudEditSourceObjectKey == nil ? AppTheme.warningYellow : AppTheme.successGreen
                )
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.neonPurple.opacity(0.18), glow: AppTheme.neonPurple, glowOpacity: 0.05)
        .accessibilityIdentifier("aiEdit.workflow.header")
    }
}
