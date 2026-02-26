import SwiftUI

struct ContentView: View {
    @State private var viewModel = HighlightsViewModel()
    @State private var authService = AuthService()
    @State private var subscriptionManager = SubscriptionManager()
    @State private var selectedTab = 0
    @State private var showingPaywall = false

    private var needsVerification: Bool {
        guard authService.isAuthenticated else { return false }
        let hasPendingEmail = authService.pendingEmailVerification != nil
        let hasPendingPhone = authService.pendingPhoneVerification != nil
        return hasPendingEmail || hasPendingPhone
    }

    var body: some View {
        Group {
            if !authService.isAuthenticated {
                AuthView(authService: authService)
            } else if needsVerification {
                VerificationView(authService: authService)
            } else {
                mainAppView
            }
        }
        .task {
            if authService.isAuthenticated {
                await subscriptionManager.checkSubscriptionStatus()
            }
        }
    }

    private var mainAppView: some View {
        ZStack {
            AppTheme.darkBg.ignoresSafeArea()
            AppTheme.meshBackground
                .opacity(0.22)
                .ignoresSafeArea()

            TabView(selection: $selectedTab) {
                Tab("Player", systemImage: "play.circle.fill", value: 0) {
                    VideoPlayerView(viewModel: viewModel)
                        .environment(subscriptionManager)
                }
                Tab("Review", systemImage: "film.stack.fill", value: 1) {
                    ReviewView(viewModel: viewModel)
                }
                Tab("Export", systemImage: "square.and.arrow.up.fill", value: 2) {
                    ExportView(viewModel: viewModel)
                        .environment(subscriptionManager)
                }
                Tab("Settings", systemImage: "gearshape.fill", value: 3) {
                    SettingsView(viewModel: viewModel, authService: authService, subscriptionManager: subscriptionManager)
                }
            }
            .tint(AppTheme.neonPurple)
            .toolbarBackground(AppTheme.cardBg.opacity(0.95), for: .tabBar)
            .toolbarBackground(.visible, for: .tabBar)
            .toolbarColorScheme(.dark, for: .tabBar)
        }
        .preferredColorScheme(.dark)
        .sheet(isPresented: $showingPaywall) {
            PaywallView(subscriptionManager: subscriptionManager)
        }
    }
}
