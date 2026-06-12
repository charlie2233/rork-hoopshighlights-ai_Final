import SwiftUI
import UIKit

struct ContentView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @Environment(\.scenePhase) private var scenePhase
    @State private var viewModel = HighlightsViewModel()
    @State private var authService = AuthService()
    @State private var subscriptionManager = SubscriptionManager()
    @State private var languageStore = AppLanguageStore()
    @State private var selectedTab = 0
    @State private var showingPaywall = false
    @State private var didShowSignInScreen = false
    @State private var isShowingPostSignInTransition = false
    @State private var isRookieGuideVisible = false
    @State private var rookieGuideStepIndex = 0
    @AppStorage("hoopsclips.visibleProjectAuthScopeKey.v1") private var visibleProjectAuthScopeKey = "signed-out"
    @AppStorage("hoopsclips.rookieGuide.completed.v1") private var rookieGuideCompleted = false
    @GestureState private var tabBarDragTranslation: CGFloat = 0
    @Namespace private var tabSelectionNamespace

    private let tabSwipeAnimation = Animation.interactiveSpring(
        response: 0.34,
        dampingFraction: 0.92,
        blendDuration: 0.08
    )

    private let tabSelectionAnimation = Animation.interactiveSpring(
        response: 0.28,
        dampingFraction: 0.88,
        blendDuration: 0.08
    )

    private enum AppTab: Int, CaseIterable, Identifiable {
        case player
        case review
        case export
        case history
        case settings

        var id: Int { rawValue }

        var iconName: String {
            switch self {
            case .player: return "play.circle.fill"
            case .review: return "film.stack.fill"
            case .export: return "square.and.arrow.up.fill"
            case .history: return "clock.arrow.circlepath"
            case .settings: return "gearshape.fill"
            }
        }

        var accessibilityIdentifier: String {
            switch self {
            case .player: return "app.tab.player"
            case .review: return "app.tab.review"
            case .export: return "app.tab.export"
            case .history: return "app.tab.history"
            case .settings: return "app.tab.settings"
            }
        }

        var telemetryName: String {
            switch self {
            case .player: return "player"
            case .review: return "review"
            case .export: return "export"
            case .history: return "history"
            case .settings: return "settings"
            }
        }

        func title(using languageStore: AppLanguageStore) -> String {
            switch self {
            case .player: return languageStore.text(.tabPlayer)
            case .review: return languageStore.text(.tabReview)
            case .export: return languageStore.text(.tabExport)
            case .history: return languageStore.text(.tabHistory)
            case .settings: return languageStore.text(.tabSettings)
            }
        }
    }

    private enum AppTabBarLayout {
        case fixed
        case scrollable
    }

    private struct RookieGuideStep: Identifiable {
        let id: Int
        let tab: AppTab
        let icon: String
        let titleKey: AppTextKey
        let bodyKey: AppTextKey
        let tipKey: AppTextKey
    }

    private var needsVerification: Bool {
        guard authService.isAuthenticated else { return false }
        let hasPendingEmail = authService.pendingEmailVerification != nil
        let hasPendingPhone = authService.pendingPhoneVerification != nil
        return hasPendingEmail || hasPendingPhone
    }

    private var revenueCatSyncKey: String {
        guard let user = authService.currentUser else { return "signed-out" }
        return "\(user.authMethod.rawValue):\(user.id)"
    }

    private var visibleProjectScopeKey: String {
        HighlightsViewModel.installIDDefaultsKey(forAuthScope: revenueCatSyncKey)
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
            reconcileInitialAuthenticatedUserScope(revenueCatSyncKey, visibleScopeKey: visibleProjectScopeKey)
            await subscriptionManager.syncAuthenticatedUser(authService.currentUser)
        }
        .onChange(of: revenueCatSyncKey) { oldScope, newScope in
            handleAuthenticatedUserScopeChange(from: oldScope, to: newScope)
            Task {
                await subscriptionManager.syncAuthenticatedUser(authService.currentUser)
            }
        }
        .onChange(of: authService.isAuthenticated) { _, isAuthenticated in
            handleAuthenticationChange(isAuthenticated)
        }
        .onAppear {
            LaunchTelemetry.shared.recordLifecycleState("active", screen: selectedTabTelemetryName)
        }
        .onChange(of: scenePhase) { _, phase in
            LaunchTelemetry.shared.recordLifecycleState(phase.hoopsTelemetryName, screen: selectedTabTelemetryName)
        }
        .onChange(of: selectedTab) { oldValue, newValue in
            recordTabSwitchBreadcrumb(fromRawValue: oldValue, toRawValue: newValue, phase: "active", trigger: "state")
        }
        .onChange(of: reviewSafetySignature) { _, _ in
            resetReviewTabIfNeeded(reason: "review_state_changed")
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didReceiveMemoryWarningNotification)) { _ in
            LaunchTelemetry.shared.recordMemoryWarning(screen: selectedTabTelemetryName)
        }
        .environment(languageStore)
        .environment(\.locale, languageStore.selectedLanguage.locale)
    }

    @ViewBuilder
    private var authenticatedContent: some View {
        if !authService.isAuthenticated {
            AuthView(authService: authService)
                .onAppear {
                    didShowSignInScreen = true
                    isShowingPostSignInTransition = false
                }
        } else if isShowingPostSignInTransition {
            postSignInTransitionView
        } else if needsVerification {
            VerificationView(authService: authService)
        } else {
            mainAppView
        }
    }

    private var postSignInTransitionView: some View {
        ZStack {
            HoopsMotionBackdrop(glowOpacity: 0.22, courtOpacity: 0.10)

            VStack(spacing: 18) {
                HoopsBrandMark(size: 118)

                VStack(spacing: 6) {
                    Text("You're in")
                        .font(.title.bold())
                        .foregroundStyle(.white)
                    Text("Opening HoopClips")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(AppTheme.warningYellow)
                }

                ProgressView()
                    .tint(AppTheme.neonPurple)
                    .accessibilityLabel("Opening HoopClips")
            }
            .padding(24)
        }
        .preferredColorScheme(.dark)
    }

    private var mainAppView: some View {
        ZStack {
            HoopsMotionBackdrop(glowOpacity: 0.18, courtOpacity: 0.08)

            activeTabContent
                .transition(reduceMotion ? .identity : .opacity.combined(with: .scale(scale: 0.995)))
                .animation(reduceMotion ? nil : tabSelectionAnimation, value: activeTab.id)
            .safeAreaInset(edge: .bottom, spacing: 0) {
                appTabBar
            }

            if selectedTab == AppTab.settings.rawValue, !isRookieGuideVisible {
                VStack {
                    Spacer(minLength: 0)
                    HStack {
                        Spacer(minLength: 0)
                        rookieGuideReplayButton
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, tabButtonHeight + 20)
                }
                .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .preferredColorScheme(.dark)
        .overlay {
            if isRookieGuideVisible {
                rookieGuideOverlay
                    .transition(.opacity.combined(with: .move(edge: .bottom)))
            }
        }
        .onAppear {
            activateRookieGuideIfNeeded()
        }
        .task(id: viewModel.currentProjectID) {
            await viewModel.resumeInFlightCloudAnalysisIfNeeded()
        }
        .sheet(isPresented: $showingPaywall) {
            PaywallView(subscriptionManager: subscriptionManager, authService: authService)
        }
    }

    private var rookieGuideSteps: [RookieGuideStep] {
        [
            RookieGuideStep(
                id: 1,
                tab: .player,
                icon: "play.circle.fill",
                titleKey: .rookieGuideImportTitle,
                bodyKey: .rookieGuideImportBody,
                tipKey: .rookieGuideImportTip
            ),
            RookieGuideStep(
                id: 2,
                tab: .review,
                icon: "checkmark.seal.fill",
                titleKey: .rookieGuideReviewTitle,
                bodyKey: .rookieGuideReviewBody,
                tipKey: .rookieGuideReviewTip
            ),
            RookieGuideStep(
                id: 3,
                tab: .export,
                icon: "wand.and.stars.inverse",
                titleKey: .rookieGuideExportTitle,
                bodyKey: .rookieGuideExportBody,
                tipKey: .rookieGuideExportTip
            ),
            RookieGuideStep(
                id: 4,
                tab: .history,
                icon: "clock.badge.checkmark.fill",
                titleKey: .rookieGuideHistoryTitle,
                bodyKey: .rookieGuideHistoryBody,
                tipKey: .rookieGuideHistoryTip
            ),
            RookieGuideStep(
                id: 5,
                tab: .settings,
                icon: "slider.horizontal.3",
                titleKey: .rookieGuideSettingsTitle,
                bodyKey: .rookieGuideSettingsBody,
                tipKey: .rookieGuideSettingsTip
            )
        ]
    }

    private var activeRookieGuideStep: RookieGuideStep {
        let clampedIndex = min(max(rookieGuideStepIndex, 0), rookieGuideSteps.count - 1)
        return rookieGuideSteps[clampedIndex]
    }

    private var rookieGuideOverlay: some View {
        let step = activeRookieGuideStep
        let isLastStep = rookieGuideStepIndex >= rookieGuideSteps.count - 1

        return ZStack {
            Color.black.opacity(0.46)
                .ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer(minLength: 0)
                rookieGuideTabCoachMark(step: step)
                    .padding(.horizontal, 16)
                    .padding(.bottom, tabButtonHeight + 8)
            }

            VStack(spacing: 0) {
                Spacer(minLength: 0)

                VStack(alignment: .leading, spacing: 14) {
                    HStack(spacing: 10) {
                        Label(languageStore.text(.rookieGuideTitle), systemImage: "sparkles")
                            .font(.subheadline.bold())
                            .foregroundStyle(.white)

                        Spacer(minLength: 0)

                        Text("\(rookieGuideStepIndex + 1)/\(rookieGuideSteps.count)")
                            .font(.caption.bold())
                            .foregroundStyle(AppTheme.warningYellow)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(AppTheme.warningYellow.opacity(0.12), in: .capsule)
                    }

                    HStack(alignment: .top, spacing: 12) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 14, style: .continuous)
                                .fill(.white.opacity(0.08))
                                .frame(width: 46, height: 46)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                                        .stroke(AppTheme.neonPurple.opacity(0.18), lineWidth: 1)
                                )
                            Image(systemName: step.icon)
                                .font(.headline.bold())
                                .foregroundStyle(AppTheme.warningYellow)
                        }
                        .accessibilityHidden(true)

                        VStack(alignment: .leading, spacing: 6) {
                            Text(languageStore.text(step.titleKey))
                                .font(.title3.weight(.bold))
                                .foregroundStyle(.white)
                                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                                .minimumScaleFactor(0.84)
                                .fixedSize(horizontal: false, vertical: true)

                            Text(languageStore.text(step.bodyKey))
                                .font(.callout.weight(.medium))
                                .foregroundStyle(AppTheme.subtleText)
                                .lineSpacing(2)
                                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 8 : 4)
                                .minimumScaleFactor(0.84)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }

                    Label(languageStore.text(step.tipKey), systemImage: "lightbulb.fill")
                        .font(.caption.bold())
                        .foregroundStyle(.white.opacity(0.86))
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                        .minimumScaleFactor(0.82)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 9)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(.white.opacity(0.07), in: .rect(cornerRadius: 13))

                    rookieGuideProgressDots

                    HStack(spacing: 10) {
                        Button {
                            skipRookieGuide()
                        } label: {
                            Text(languageStore.text(.rookieGuideSkip))
                                .font(.subheadline.bold())
                                .foregroundStyle(AppTheme.subtleText)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 13)
                                .background(AppTheme.cardBg.opacity(0.65), in: .rect(cornerRadius: 14))
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("rookieGuide.skipButton")

                        if rookieGuideStepIndex > 0 {
                            Button {
                                showPreviousRookieGuideStep()
                            } label: {
                                Text(languageStore.text(.rookieGuideBack))
                                    .font(.subheadline.bold())
                                    .foregroundStyle(.white)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 13)
                                    .background(AppTheme.accentPurple.opacity(0.26), in: .rect(cornerRadius: 14))
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("rookieGuide.backButton")
                        }

                        Button {
                            showNextRookieGuideStep()
                        } label: {
                            Text(languageStore.text(isLastStep ? .rookieGuideDone : .rookieGuideNext))
                                .font(.subheadline.bold())
                                .foregroundStyle(.black)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 13)
                                .background(AppTheme.warningYellow, in: .rect(cornerRadius: 14))
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("rookieGuide.nextButton")
                    }
                }
                .padding(16)
                .rorkCard(cornerRadius: 22, stroke: AppTheme.neonPurple.opacity(0.20), glow: AppTheme.neonPurple, glowOpacity: 0.12)
                .padding(.horizontal, 16)
                .padding(.bottom, tabButtonHeight + 28)
            }
        }
        .accessibilityIdentifier("rookieGuide.overlay")
    }

    private var rookieGuideReplayButton: some View {
        Button {
            restartRookieGuide()
        } label: {
            Label(languageStore.text(.rookieGuideReplay), systemImage: "questionmark.circle.fill")
                .font(.caption.bold())
                .foregroundStyle(.white)
                .padding(.horizontal, 13)
                .padding(.vertical, 10)
                .background(AppTheme.accentPurple.opacity(0.86), in: .capsule)
                .overlay(
                    Capsule()
                        .stroke(AppTheme.neonPurple.opacity(0.32), lineWidth: 1)
                )
                .shadow(color: AppTheme.neonPurple.opacity(0.24), radius: 14, x: 0, y: 8)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("settings.rookieGuide.replayButton")
        .accessibilityLabel(languageStore.text(.rookieGuideReplay))
        .accessibilityHint("Shows the step by step beginner tutorial again.")
    }

    private func rookieGuideTabCoachMark(step: RookieGuideStep) -> some View {
        GeometryReader { proxy in
            let centerX = rookieGuideTabCenterX(for: step.tab, width: proxy.size.width)

            ZStack(alignment: .bottomLeading) {
                VStack(spacing: 5) {
                    Text(step.tab.title(using: languageStore))
                        .font(.caption.bold())
                            .foregroundStyle(.black)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(AppTheme.warningYellow.opacity(0.94), in: .capsule)

                    Image(systemName: "arrowtriangle.down.fill")
                        .font(.caption.bold())
                        .foregroundStyle(AppTheme.warningYellow)
                        .shadow(color: AppTheme.warningYellow.opacity(0.32), radius: 8, x: 0, y: 0)
                }
                .position(x: centerX, y: proxy.size.height / 2)
            }
        }
        .frame(height: 44)
        .accessibilityHidden(true)
    }

    private func rookieGuideTabCenterX(for tab: AppTab, width: CGFloat) -> CGFloat {
        let tabCount = CGFloat(AppTab.allCases.count)
        let availableWidth = max(width - 20, 1)
        let tabWidth = availableWidth / max(tabCount, 1)
        return 10 + tabWidth * (CGFloat(tab.rawValue) + 0.5)
    }

    private var rookieGuideProgressDots: some View {
        HStack(spacing: 7) {
            ForEach(0..<rookieGuideSteps.count, id: \.self) { index in
                Capsule()
                    .fill(index == rookieGuideStepIndex ? AppTheme.warningYellow : AppTheme.subtleText.opacity(0.35))
                    .frame(width: index == rookieGuideStepIndex ? 24 : 8, height: 8)
                    .animation(reduceMotion ? nil : .snappy(duration: 0.18), value: rookieGuideStepIndex)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityHidden(true)
    }

    private var selectedTabTelemetryName: String {
        AppTab(rawValue: selectedTab)?.telemetryName ?? "unknown"
    }

    private var activeTab: AppTab {
        let tab = AppTab(rawValue: selectedTab) ?? .player
        if tab == .review, !hasCurrentReviewableClips {
            return .player
        }
        return tab
    }

    private var hasCurrentReviewableClips: Bool {
        guard viewModel.isVideoLoaded, !viewModel.clips.isEmpty else { return false }
        return viewModel.clips.contains(where: isReviewableClip)
    }

    private var currentReviewableClipCount: Int {
        viewModel.clips.filter(isReviewableClip).count
    }

    private var reviewSafetySignature: String {
        [
            "selected=\(selectedTab)",
            "videoLoaded=\(viewModel.isVideoLoaded)",
            "duration=\(viewModel.videoDuration)",
            "clips=\(viewModel.clips.count)",
            "reviewable=\(currentReviewableClipCount)",
            "project=\(viewModel.currentProjectID?.uuidString ?? "none")"
        ].joined(separator: "|")
    }

    @ViewBuilder
    private var activeTabContent: some View {
        switch activeTab {
        case .player:
            VideoPlayerView(
                viewModel: viewModel,
                onOpenHistory: {
                    selectTab(.history)
                }
            )
            .id("player-\(revenueCatSyncKey)")
            .environment(subscriptionManager)
            .environment(authService)

        case .review:
            ReviewView(viewModel: viewModel, selectedTab: $selectedTab)

        case .export:
            ExportView(viewModel: viewModel)
                .environment(subscriptionManager)
                .environment(authService)

        case .history:
            HistoryView(viewModel: viewModel)

        case .settings:
            SettingsView(viewModel: viewModel, authService: authService, subscriptionManager: subscriptionManager)
        }
    }

    private func activateRookieGuideIfNeeded() {
        guard !rookieGuideCompleted, !isRookieGuideVisible else { return }
        rookieGuideStepIndex = 0
        selectedTab = AppTab.player.rawValue
        isRookieGuideVisible = true
        LaunchTelemetry.shared.recordStabilityCheckpoint("rookie_guide.started")
    }

    private func restartRookieGuide() {
        rookieGuideCompleted = false
        rookieGuideStepIndex = 0
        selectedTab = AppTab.player.rawValue
        isRookieGuideVisible = true
        LaunchTelemetry.shared.recordStabilityCheckpoint("rookie_guide.replayed")
    }

    private func showNextRookieGuideStep() {
        guard rookieGuideStepIndex < rookieGuideSteps.count - 1 else {
            completeRookieGuide()
            return
        }

        showRookieGuideStep(rookieGuideStepIndex + 1)
    }

    private func showPreviousRookieGuideStep() {
        showRookieGuideStep(max(rookieGuideStepIndex - 1, 0))
    }

    private func showRookieGuideStep(_ index: Int) {
        let clampedIndex = min(max(index, 0), rookieGuideSteps.count - 1)
        let targetTab = rookieGuideSteps[clampedIndex].tab

        guard reduceMotion == false else {
            rookieGuideStepIndex = clampedIndex
            selectedTab = targetTab.rawValue
            return
        }

        withAnimation(tabSwipeAnimation) {
            rookieGuideStepIndex = clampedIndex
            selectedTab = targetTab.rawValue
        }
    }

    private func skipRookieGuide() {
        rookieGuideCompleted = true
        isRookieGuideVisible = false
        LaunchTelemetry.shared.recordStabilityCheckpoint("rookie_guide.skipped")
    }

    private func completeRookieGuide() {
        rookieGuideCompleted = true
        isRookieGuideVisible = false
        LaunchTelemetry.shared.recordStabilityCheckpoint("rookie_guide.completed")
    }

    private var appTabBar: some View {
        ViewThatFits(in: .horizontal) {
            fixedAppTabBarRow
            scrollableAppTabBarRow
        }
        .padding(.top, 8)
        .padding(.bottom, 8)
        .background(AppTheme.cardBg.opacity(0.96))
        .overlay(alignment: .top) {
            Rectangle()
                .fill(AppTheme.softBorder.opacity(0.8))
                .frame(height: 1)
        }
        .contentShape(.rect)
        .offset(x: reduceMotion ? 0 : tabBarVisualOffset)
        .simultaneousGesture(tabBarDragGesture)
        .animation(reduceMotion ? nil : tabSelectionAnimation, value: selectedTab)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("app.tabBar")
    }

    private var fixedAppTabBarRow: some View {
        HStack(spacing: 6) {
            ForEach(AppTab.allCases) { tab in
                appTabButton(tab, layout: .fixed)
            }
        }
        .padding(.horizontal, 10)
    }

    private var scrollableAppTabBarRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(AppTab.allCases) { tab in
                    appTabButton(tab, layout: .scrollable)
                }
            }
            .padding(.horizontal, 10)
        }
        .accessibilityHint("Swipe the tab row horizontally to reveal every tab.")
    }

    private var tabBarVisualOffset: CGFloat {
        min(18, max(-18, tabBarDragTranslation * 0.12))
    }

    private var tabBarDragGesture: some Gesture {
        DragGesture(minimumDistance: 18, coordinateSpace: .local)
            .updating($tabBarDragTranslation) { value, state, _ in
                guard abs(value.translation.width) > abs(value.translation.height) * 1.2 else { return }
                state = value.translation.width
            }
            .onEnded(handleTabBarDrag)
    }

    private func handleAuthenticationChange(_ isAuthenticated: Bool) {
        guard isAuthenticated else {
            resetVisibleProjectForAuthenticationBoundary(reason: "signed_out")
            visibleProjectAuthScopeKey = HighlightsViewModel.installIDDefaultsKey(forAuthScope: "signed-out")
            didShowSignInScreen = true
            isShowingPostSignInTransition = false
            return
        }

        guard didShowSignInScreen else {
            isShowingPostSignInTransition = false
            return
        }

        isShowingPostSignInTransition = true
        let signedInUserID = authService.currentUser?.id

        Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(700))
            guard authService.currentUser?.id == signedInUserID else { return }
            selectedTab = AppTab.player.rawValue
            didShowSignInScreen = false
            isShowingPostSignInTransition = false
            HoopsAccessibility.announce("Signed in. Opening HoopClips.")
        }
    }

    private func handleAuthenticatedUserScopeChange(from oldScope: String, to newScope: String) {
        guard oldScope != newScope else { return }

        viewModel.applyAuthenticatedCloudScope(newScope)
        let reason = newScope == "signed-out" ? "signed_out" : "account_switched"
        resetVisibleProjectForAuthenticationBoundary(reason: reason)
        visibleProjectAuthScopeKey = HighlightsViewModel.installIDDefaultsKey(forAuthScope: newScope)
    }

    private func reconcileInitialAuthenticatedUserScope(_ currentScope: String, visibleScopeKey: String) {
        viewModel.applyAuthenticatedCloudScope(currentScope)
        guard visibleProjectAuthScopeKey != visibleScopeKey else { return }

        let reason: String
        let signedOutScopeKey = HighlightsViewModel.installIDDefaultsKey(forAuthScope: "signed-out")
        if currentScope == "signed-out" {
            reason = "signed_out"
        } else if visibleProjectAuthScopeKey == "signed-out" || visibleProjectAuthScopeKey == signedOutScopeKey {
            reason = "signed_in"
        } else {
            reason = "account_switched"
        }

        resetVisibleProjectForAuthenticationBoundary(reason: reason)
        visibleProjectAuthScopeKey = visibleScopeKey
    }

    private func resetVisibleProjectForAuthenticationBoundary(reason: String) {
        let hasVisibleProject = viewModel.isVideoLoaded
            || viewModel.currentProjectID != nil
            || !viewModel.clips.isEmpty

        if hasVisibleProject {
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "auth.project_reset",
                metadata: "reason=\(reason)"
            )
        }
        viewModel.clearVisibleProjectForAuthenticationBoundary()
        selectedTab = AppTab.player.rawValue
        showingPaywall = false
    }

    private func appTabButton(_ tab: AppTab, layout: AppTabBarLayout) -> some View {
        let isSelected = selectedTab == tab.rawValue
        let title = tab.title(using: languageStore)

        return Button {
            selectTab(tab)
        } label: {
            VStack(spacing: 4) {
                Image(systemName: tab.iconName)
                    .font(.system(size: 17, weight: isSelected ? .semibold : .medium))
                Text(title)
                    .font(.caption2.weight(isSelected ? .semibold : .medium))
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                    .minimumScaleFactor(0.82)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .foregroundStyle(isSelected ? .white : AppTheme.subtleText)
            .frame(
                minWidth: layout == .fixed ? 66 : nil,
                maxWidth: layout == .fixed ? .infinity : nil
            )
            .frame(
                width: layout == .scrollable ? tabButtonScrollableWidth : nil,
                height: tabButtonHeight
            )
            .background {
                if isSelected {
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .fill(AppTheme.accentPurple.opacity(0.18))
                        .overlay {
                            RoundedRectangle(cornerRadius: 16, style: .continuous)
                                .stroke(AppTheme.neonPurple.opacity(0.28), lineWidth: 1)
                        }
                        .matchedGeometryEffect(id: "app.tab.selection", in: tabSelectionNamespace)
                }
            }
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(tab.accessibilityIdentifier)
        .accessibilityLabel(title)
        .accessibilityHint("Opens \(title).")
        .hoopsSelectedState(isSelected)
    }

    private var tabButtonScrollableWidth: CGFloat {
        dynamicTypeSize.isAccessibilitySize ? 106 : 88
    }

    private var tabButtonHeight: CGFloat {
        dynamicTypeSize.isAccessibilitySize ? 84 : 60
    }

    private func selectTab(_ tab: AppTab) {
        guard selectedTab != tab.rawValue else { return }
        recordTabSwitchBreadcrumb(fromRawValue: selectedTab, toRawValue: tab.rawValue, phase: "requested", trigger: "tab_bar")
        if tab == .review, !hasCurrentReviewableClips {
            resetToDefaultTabAfterReviewBlock(reason: "no_reviewable_clips")
            return
        }
        guard !reduceMotion else {
            selectedTab = tab.rawValue
            return
        }

        withAnimation(tabSwipeAnimation) {
            selectedTab = tab.rawValue
        }
    }

    private func handleTabBarDrag(_ value: DragGesture.Value) {
        let horizontal = value.translation.width
        let vertical = abs(value.translation.height)
        let projected: CGFloat
        if abs(value.predictedEndTranslation.width) > abs(horizontal) {
            projected = value.predictedEndTranslation.width
        } else {
            projected = horizontal
        }

        guard abs(projected) >= 32 || abs(horizontal) >= 32 else { return }
        guard abs(horizontal) > vertical * 1.2 || abs(projected) > vertical * 1.6 else { return }

        let delta = projected < 0 ? 1 : -1
        let firstTab = AppTab.allCases.first?.rawValue ?? selectedTab
        let lastTab = AppTab.allCases.last?.rawValue ?? selectedTab
        let targetRawValue = min(max(selectedTab + delta, firstTab), lastTab)
        guard let targetTab = AppTab(rawValue: targetRawValue) else { return }
        selectTab(targetTab)
    }

    private func resetReviewTabIfNeeded(reason: String) {
        guard selectedTab == AppTab.review.rawValue, !hasCurrentReviewableClips else { return }
        resetToDefaultTabAfterReviewBlock(reason: reason)
    }

    private func resetToDefaultTabAfterReviewBlock(reason: String) {
        LaunchTelemetry.shared.recordStabilityCheckpoint(
            "tab.switch.blocked",
            metadata: reviewBlockMetadata(reason: reason)
        )
        guard selectedTab != AppTab.player.rawValue else { return }

        if reduceMotion {
            selectedTab = AppTab.player.rawValue
        } else {
            withAnimation(tabSwipeAnimation) {
                selectedTab = AppTab.player.rawValue
            }
        }
        HoopsAccessibility.announce("No reviewable clips yet. Opening Player.")
    }

    private func reviewBlockMetadata(reason: String) -> String {
        [
            "reason=\(reason)",
            "videoLoaded=\(viewModel.isVideoLoaded)",
            "clips=\(viewModel.clips.count)",
            "reviewable=\(currentReviewableClipCount)",
            "videoDuration=\(viewModel.videoDuration)",
            "project=\(viewModel.currentProjectID?.uuidString ?? "none")"
        ].joined(separator: " ")
    }

    private func isReviewableClip(_ clip: Clip) -> Bool {
        guard clip.startTime.isFinite, clip.endTime.isFinite else { return false }
        let sourceDuration = viewModel.videoDuration
        let hasFiniteSourceDuration = sourceDuration.isFinite && sourceDuration > 0
        let upperBound = hasFiniteSourceDuration ? sourceDuration : max(clip.startTime, clip.endTime)
        let start = max(0, min(clip.startTime, upperBound))
        let end = max(0, min(clip.endTime, upperBound))
        return end > start
    }

    private func recordTabSwitchBreadcrumb(
        fromRawValue: Int,
        toRawValue: Int,
        phase: String,
        trigger: String
    ) {
        let fromTab = AppTab(rawValue: fromRawValue)?.telemetryName ?? "invalid_\(fromRawValue)"
        let toTab = AppTab(rawValue: toRawValue)?.telemetryName ?? "invalid_\(toRawValue)"
        let metadata = [
            "from=\(fromTab)",
            "to=\(toTab)",
            "trigger=\(trigger)",
            "videoLoaded=\(viewModel.isVideoLoaded)",
            "clips=\(viewModel.clips.count)",
            "project=\(viewModel.currentProjectID?.uuidString ?? "none")"
        ].joined(separator: " ")
        LaunchTelemetry.shared.recordStabilityCheckpoint("tab.switch.\(phase)", metadata: metadata)
    }
}

private extension ScenePhase {
    var hoopsTelemetryName: String {
        switch self {
        case .active: return "active"
        case .inactive: return "inactive"
        case .background: return "background"
        @unknown default: return "unknown"
        }
    }
}
