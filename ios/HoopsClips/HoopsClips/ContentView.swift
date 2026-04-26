import SwiftUI

struct ContentView: View {
    @State private var viewModel = HighlightsViewModel()
    @State private var authService = AuthService()
    @State private var subscriptionManager = SubscriptionManager()
    @State private var languageStore = AppLanguageStore()
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
        .environment(languageStore)
        .environment(\.locale, languageStore.selectedLanguage.locale)
    }

    private var mainAppView: some View {
        ZStack {
            AppTheme.darkBg.ignoresSafeArea()
            AppTheme.meshBackground
                .opacity(0.22)
                .ignoresSafeArea()

            TabView(selection: $selectedTab) {
                Tab(languageStore.text(.tabPlayer), systemImage: "play.circle.fill", value: 0) {
                    VideoPlayerView(viewModel: viewModel)
                        .environment(subscriptionManager)
                        .environment(authService)
                }
                Tab(languageStore.text(.tabReview), systemImage: "film.stack.fill", value: 1) {
                    ReviewView(viewModel: viewModel)
                }
                Tab(languageStore.text(.tabExport), systemImage: "square.and.arrow.up.fill", value: 2) {
                    ExportView(viewModel: viewModel)
                        .environment(subscriptionManager)
                        .environment(authService)
                }
                Tab(languageStore.text(.tabHistory), systemImage: "clock.arrow.circlepath", value: 3) {
                    HistoryView(viewModel: viewModel)
                }
                Tab(languageStore.text(.tabSettings), systemImage: "gearshape.fill", value: 4) {
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
            PaywallView(subscriptionManager: subscriptionManager, authService: authService)
        }
    }
}
