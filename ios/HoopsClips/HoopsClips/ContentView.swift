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
        let englishTitle: String
        let chineseTitle: String
        let spanishTitle: String
        let englishBody: String
        let chineseBody: String
        let spanishBody: String
        let englishTip: String
        let chineseTip: String
        let spanishTip: String

        func title(for language: AppLanguage) -> String {
            switch language {
            case .english:
                return englishTitle
            case .chinese:
                return chineseTitle
            case .spanish:
                return spanishTitle
            }
        }

        func body(for language: AppLanguage) -> String {
            switch language {
            case .english:
                return englishBody
            case .chinese:
                return chineseBody
            case .spanish:
                return spanishBody
            }
        }

        func tip(for language: AppLanguage) -> String {
            switch language {
            case .english:
                return englishTip
            case .chinese:
                return chineseTip
            case .spanish:
                return spanishTip
            }
        }
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

            TabView(selection: $selectedTab) {
                VideoPlayerView(
                    viewModel: viewModel,
                    onOpenHistory: {
                        selectTab(.history)
                    }
                )
                    .id("player-\(revenueCatSyncKey)")
                    .environment(subscriptionManager)
                    .environment(authService)
                    .tag(AppTab.player.rawValue)

                ReviewView(viewModel: viewModel, selectedTab: $selectedTab)
                    .tag(AppTab.review.rawValue)

                ExportView(viewModel: viewModel)
                    .environment(subscriptionManager)
                    .environment(authService)
                    .tag(AppTab.export.rawValue)

                HistoryView(viewModel: viewModel)
                    .tag(AppTab.history.rawValue)

                SettingsView(viewModel: viewModel, authService: authService, subscriptionManager: subscriptionManager)
                    .tag(AppTab.settings.rawValue)
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            .indexViewStyle(.page(backgroundDisplayMode: .never))
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
                englishTitle: "Import a game",
                chineseTitle: "导入比赛视频",
                spanishTitle: "Importa un partido",
                englishBody: "Pick a video, choose your team, then start cloud analysis.",
                chineseBody: "选择视频，选好球队，然后开始云端分析。",
                spanishBody: "Elige un video, selecciona tu equipo y empieza el análisis en la nube.",
                englishTip: "Analysis can take a little while.",
                chineseTip: "分析可能需要一点时间。",
                spanishTip: "El análisis puede tardar un poco."
            ),
            RookieGuideStep(
                id: 2,
                tab: .review,
                icon: "film.stack.fill",
                englishTitle: "Review clips",
                chineseTitle: "审核片段",
                spanishTitle: "Revisa clips",
                englishBody: "Watch one clip. Keep strong plays, skip weak ones, and tag issues.",
                chineseBody: "一次看一个片段。好的保留，不好的跳过，也可以标记问题。",
                spanishBody: "Mira un clip. Guarda las buenas jugadas, descarta las débiles y marca problemas.",
                englishTip: "Swipe left or right to decide faster.",
                chineseTip: "左右滑动可以更快选择。",
                spanishTip: "Desliza a la izquierda o derecha para decidir más rápido."
            ),
            RookieGuideStep(
                id: 3,
                tab: .export,
                icon: "square.and.arrow.up.fill",
                englishTitle: "Make the reel",
                chineseTitle: "生成集锦",
                spanishTitle: "Crea el reel",
                englishBody: "Choose style, length, and format. HoopClips renders the MP4 in the cloud.",
                chineseBody: "选择风格、时长和比例。HoopClips 会在云端生成 MP4。",
                spanishBody: "Elige estilo, duración y formato. HoopClips renderiza el MP4 en la nube.",
                englishTip: "You can wait here or come back later.",
                chineseTip: "可以等一下，也可以之后回来查看。",
                spanishTip: "Puedes esperar aquí o volver después."
            ),
            RookieGuideStep(
                id: 4,
                tab: .history,
                icon: "clock.arrow.circlepath",
                englishTitle: "Find past work",
                chineseTitle: "找回项目",
                spanishTitle: "Encuentra trabajos",
                englishBody: "Open recent games and finished cloud renders from History.",
                chineseBody: "在历史记录里打开最近的视频和已生成的云端作品。",
                spanishBody: "Abre partidos recientes y renders terminados desde Historial.",
                englishTip: "Free cloud videos can expire.",
                chineseTip: "免费云端视频可能会过期。",
                spanishTip: "Los videos gratuitos en la nube pueden caducar."
            ),
            RookieGuideStep(
                id: 5,
                tab: .settings,
                icon: "gearshape.fill",
                englishTitle: "Tune settings",
                chineseTitle: "调整设置",
                spanishTitle: "Ajusta opciones",
                englishBody: "Manage language, account, Pro status, and workflow defaults.",
                chineseBody: "管理语言、账号、Pro 状态和流程默认设置。",
                spanishBody: "Administra idioma, cuenta, estado Pro y preferencias de flujo.",
                englishTip: "First run the basic flow once.",
                chineseTip: "新手先跑完一次基础流程就好。",
                spanishTip: "Primero completa el flujo básico una vez."
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
                        Label(rookieGuideTitle, systemImage: "sparkles")
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
                            Text(step.title(for: languageStore.selectedLanguage))
                                .font(.title3.weight(.bold))
                                .foregroundStyle(.white)
                                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                                .minimumScaleFactor(0.84)
                                .fixedSize(horizontal: false, vertical: true)

                            Text(step.body(for: languageStore.selectedLanguage))
                                .font(.callout.weight(.medium))
                                .foregroundStyle(AppTheme.subtleText)
                                .lineSpacing(2)
                                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 8 : 4)
                                .minimumScaleFactor(0.84)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }

                    Label(step.tip(for: languageStore.selectedLanguage), systemImage: "lightbulb.fill")
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
                            Text(rookieGuideSkipTitle)
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
                                Text(rookieGuideBackTitle)
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
                            Text(isLastStep ? rookieGuideDoneTitle : rookieGuideNextTitle)
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
            Label(rookieGuideReplayTitle, systemImage: "questionmark.circle.fill")
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
        .accessibilityLabel("Replay rookie guide")
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

    private var rookieGuideTitle: String {
        rookieGuideCopy(
            english: "Quick guide",
            chinese: "新手教程",
            spanish: "Guía rápida"
        )
    }

    private var rookieGuideSkipTitle: String {
        rookieGuideCopy(
            english: "Skip",
            chinese: "跳过",
            spanish: "Omitir"
        )
    }

    private var rookieGuideBackTitle: String {
        rookieGuideCopy(
            english: "Back",
            chinese: "上一步",
            spanish: "Atrás"
        )
    }

    private var rookieGuideNextTitle: String {
        rookieGuideCopy(
            english: "Next",
            chinese: "下一步",
            spanish: "Siguiente"
        )
    }

    private var rookieGuideDoneTitle: String {
        rookieGuideCopy(
            english: "Done",
            chinese: "完成",
            spanish: "Listo"
        )
    }

    private var rookieGuideReplayTitle: String {
        rookieGuideCopy(
            english: "Replay guide",
            chinese: "重看新手教程",
            spanish: "Ver guía"
        )
    }

    private func rookieGuideCopy(english: String, chinese: String, spanish: String) -> String {
        switch languageStore.selectedLanguage {
        case .english:
            return english
        case .chinese:
            return chinese
        case .spanish:
            return spanish
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
        LaunchTelemetry.shared.recordStabilityCheckpoint("tab.selected", metadata: "tab=\(tab.telemetryName)")
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
