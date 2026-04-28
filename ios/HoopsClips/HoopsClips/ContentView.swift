import SwiftUI

struct ContentView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var viewModel = HighlightsViewModel()
    @State private var authService = AuthService()
    @State private var subscriptionManager = SubscriptionManager()
    @State private var languageStore = AppLanguageStore()
    @State private var selectedTab = 0
    @State private var showingPaywall = false

    private let firstTabIndex = 0
    private let lastTabIndex = 4
    private let tabSwipeThreshold: CGFloat = 70
    private let tabSwipeVerticalTolerance: CGFloat = 1.25

    private var needsVerification: Bool {
        guard authService.isAuthenticated else { return false }
        let hasPendingEmail = authService.pendingEmailVerification != nil
        let hasPendingPhone = authService.pendingPhoneVerification != nil
        return hasPendingEmail || hasPendingPhone
    }

    #if DEBUG
    private var isPaywallScreenshotMode: Bool {
        ProcessInfo.processInfo.arguments.contains("--hoops-paywall-screenshot")
    }
    #endif

    var body: some View {
        Group {
            #if DEBUG
            if isPaywallScreenshotMode {
                PaywallView(subscriptionManager: subscriptionManager, authService: authService)
            } else {
                authenticatedContent
            }
            #else
            authenticatedContent
            #endif
        }
        .task {
            if authService.isAuthenticated {
                await subscriptionManager.checkSubscriptionStatus()
            }
        }
        .environment(languageStore)
        .environment(\.locale, languageStore.selectedLanguage.locale)
    }

    @ViewBuilder
    private var authenticatedContent: some View {
        if !authService.isAuthenticated {
            AuthView(authService: authService)
        } else if needsVerification {
            VerificationView(authService: authService)
        } else {
            mainAppView
        }
    }

    private var mainAppView: some View {
        ZStack {
            HoopsMotionBackdrop(glowOpacity: 0.18, courtOpacity: 0.08)

            TabView(selection: $selectedTab) {
                Tab(languageStore.text(.tabPlayer), systemImage: "play.circle.fill", value: 0) {
                    VideoPlayerView(viewModel: viewModel)
                        .environment(subscriptionManager)
                        .environment(authService)
                }
                Tab(languageStore.text(.tabReview), systemImage: "film.stack.fill", value: 1) {
                    ReviewView(viewModel: viewModel)
                        .environment(subscriptionManager)
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
        .simultaneousGesture(tabSwipeGesture)
        .sheet(isPresented: $showingPaywall) {
            PaywallView(subscriptionManager: subscriptionManager, authService: authService)
        }
    }

    private var tabSwipeGesture: some Gesture {
        DragGesture(minimumDistance: 35, coordinateSpace: .local)
            .onEnded(handleTabSwipe)
    }

    private func handleTabSwipe(_ value: DragGesture.Value) {
        let horizontalDistance = value.translation.width
        let verticalDistance = value.translation.height
        let isHorizontalSwipe = abs(horizontalDistance) >= tabSwipeThreshold
            && abs(horizontalDistance) > abs(verticalDistance) * tabSwipeVerticalTolerance

        guard isHorizontalSwipe else { return }

        let nextTab = selectedTab + (horizontalDistance < 0 ? 1 : -1)
        let boundedTab = min(max(nextTab, firstTabIndex), lastTabIndex)
        guard boundedTab != selectedTab else { return }

        guard !reduceMotion else {
            selectedTab = boundedTab
            return
        }

        withAnimation(.easeOut(duration: 0.2)) {
            selectedTab = boundedTab
        }
    }
}
