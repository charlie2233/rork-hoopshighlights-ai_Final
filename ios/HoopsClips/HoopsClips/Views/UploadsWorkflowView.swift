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
    var isActive = true
    var onRequestProUpgrade: () -> Void

    @Environment(SubscriptionManager.self) private var subscriptionManager
    @Environment(AuthService.self) private var authService

    var body: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.18)

                ScrollView {
                    AIEditView(
                        viewModel: viewModel,
                        isProUser: subscriptionManager.isProUser,
                        revenueCatAppUserID: subscriptionManager.revenueCatAppUserID,
                        presentation: .exportSection,
                        isActive: isActive,
                        onRequestProUpgrade: onRequestProUpgrade
                    )
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
        .accessibilityIdentifier("aiEdit.workflow.screen")
        .environment(subscriptionManager)
        .environment(authService)
    }
}
