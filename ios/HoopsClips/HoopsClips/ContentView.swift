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
    @State private var reviewRecoveryNotice: ReviewRecoveryNotice?
    @State private var uploadResumeNotice: UploadResumeNotice?
    @State private var showingPipelineCancelConfirmation = false
    @State private var didCopyPipelineUploadProof = false
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

    fileprivate struct ReviewRecoveryNotice: Identifiable, Equatable {
        let id = UUID()
        let reason: String
        let clipCount: Int
        let reviewableClipCount: Int

        static func == (lhs: ReviewRecoveryNotice, rhs: ReviewRecoveryNotice) -> Bool {
            lhs.reason == rhs.reason
                && lhs.clipCount == rhs.clipCount
                && lhs.reviewableClipCount == rhs.reviewableClipCount
        }
    }

    private struct UploadResumeNotice: Identifiable, Equatable {
        let id = UUID()
        let message: String
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
            recordRuntimeStateBreadcrumb(reason: "appear")
            resumeCloudAnalysisAfterForegroundIfNeeded()
        }
        .onChange(of: scenePhase) { _, phase in
            LaunchTelemetry.shared.recordLifecycleState(phase.hoopsTelemetryName, screen: selectedTabTelemetryName)
            recordRuntimeStateBreadcrumb(reason: "lifecycle_\(phase.hoopsTelemetryName)")
            if phase == .active {
                resumeCloudAnalysisAfterForegroundIfNeeded()
            }
        }
        .onChange(of: selectedTab) { oldValue, newValue in
            recordTabSwitchBreadcrumb(fromRawValue: oldValue, toRawValue: newValue, phase: "active", trigger: "state")
        }
        .onChange(of: reviewSafetySignature) { _, _ in
            resetReviewTabIfNeeded(reason: "review_state_changed")
        }
        .onChange(of: runtimeStateSignature) { _, _ in
            recordRuntimeStateBreadcrumb(reason: "state_changed")
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didReceiveMemoryWarningNotification)) { _ in
            LaunchTelemetry.shared.recordMemoryWarning(screen: selectedTabTelemetryName)
        }
        .onReceive(NotificationCenter.default.publisher(for: .hoopClipsAnalysisNotificationTapped)) { notification in
            handleAnalysisNotificationTap(notification)
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

            if let reviewRecoveryNotice, !isRookieGuideVisible, !isReviewWaitingForAnalysis {
                VStack {
                    Spacer(minLength: 0)
                    ReviewUnavailableRecoveryCard(
                        notice: reviewRecoveryNotice,
                        onRerunAnalysis: openPlayerFromReviewRecovery,
                        onDismiss: dismissReviewRecoveryNotice
                    )
                    .padding(.horizontal, 16)
                    .padding(.bottom, tabButtonHeight + 24)
                }
                .transition(.move(edge: .bottom).combined(with: .opacity))
                .zIndex(3)
            }

            if shouldShowGlobalPipelineBanner {
                VStack {
                    GlobalImportProgressBanner(
                        message: pipelineStatusMessage,
                        detailMessage: pipelineDetailMessage,
                        stage: pipelineStage,
                        canResumeUpload: canResumePipelineUpload,
                        didCopyProof: didCopyPipelineUploadProof,
                        onResumeUpload: resumePipelineUpload,
                        onCopyProof: copyPipelineUploadProof,
                        onCancel: requestPipelineCancelConfirmation
                    )
                        .padding(.horizontal, 16)
                        .padding(.top, 12)
                    Spacer(minLength: 0)
                }
                .transition(.move(edge: .top).combined(with: .opacity))
                .zIndex(4)
            }

            if viewModel.canRetryUploadAfterCancel, !isRookieGuideVisible {
                VStack {
                    UploadRetryCard(onRetry: viewModel.retryUploadAfterCancel)
                        .padding(.horizontal, 16)
                        .padding(.top, 12)
                    Spacer(minLength: 0)
                }
                .transition(.move(edge: .top).combined(with: .opacity))
                .zIndex(5)
            }

            if let uploadResumeNotice, !isRookieGuideVisible {
                VStack {
                    UploadResumeNoticeToast(message: uploadResumeNotice.message)
                        .padding(.horizontal, 16)
                        .padding(.top, shouldShowGlobalPipelineBanner ? 86 : 12)
                    Spacer(minLength: 0)
                }
                .transition(.move(edge: .top).combined(with: .opacity))
                .zIndex(6)
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
        .confirmationDialog(
            pipelineStage.cancelTitle + "?",
            isPresented: $showingPipelineCancelConfirmation,
            titleVisibility: .visible
        ) {
            Button(pipelineStage.cancelTitle, role: .destructive) {
                viewModel.cancelActiveUploadOrAnalysis()
            }
            Button("Keep going", role: .cancel) { }
        } message: {
            Text("Large videos can take a while. Cancel stops the current upload or analysis; you can retry from HoopClips.")
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

    private var shouldShowGlobalPipelineBanner: Bool {
        (viewModel.isVideoImportInProgress || viewModel.analysisService.isAnalyzing)
            && activeTab != .review
            && !isRookieGuideVisible
    }

    private var isReviewWaitingForAnalysis: Bool {
        viewModel.isVideoLoaded && viewModel.analysisService.isAnalyzing
    }

    private var pipelineStatusMessage: String {
        if let videoImportStatusMessage = viewModel.videoImportStatusMessage,
           !videoImportStatusMessage.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return videoImportStatusMessage
        }

        if isBackgroundUploadStillRunning {
            return "Still uploading in background. Safe to switch apps."
        }

        let status = viewModel.analysisService.statusMessage.trimmingCharacters(in: .whitespacesAndNewlines)
        return status.isEmpty ? "Preparing upload..." : status
    }

    private var pipelineDetailMessage: String? {
        guard pipelineStage == .uploading else { return nil }
        return uploadProgressPipelineDetail(from: CloudAnalysisService.latestUploadProgressSummary())
            ?? CloudAnalysisProgressCopy.compactUploadProgressSummary(statusMessage: pipelineStatusMessage)
    }

    private var canResumePipelineUpload: Bool {
        guard pipelineStage == .uploading else { return false }
        let manifest = CloudAnalysisService.pendingBackgroundUploadManifestSummary()
        return manifest.contains("pending=true")
            && manifest.contains("nextAction=resume_upload")
    }

    private func uploadProgressPipelineDetail(from summary: String) -> String? {
        let trimmedSummary = summary.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedSummary.isEmpty, trimmedSummary != "none" else { return nil }

        let bytes = uploadProgressField("bytes", in: trimmedSummary)
        let speed = uploadProgressField("speed", in: trimmedSummary)
        let eta = uploadProgressField("eta", in: trimmedSummary)
        let context = uploadProgressField("context", in: trimmedSummary)
        let stalled = uploadProgressField("stalled", in: trimmedSummary) == "true"

        var parts: [String] = []
        if let context = context, uploadProgressContextIsUseful(context) {
            parts.append(context)
        }
        if let bytes {
            parts.append(bytes)
        }
        if let speed {
            parts.append(speed)
        }
        if let eta {
            parts.append("about \(eta) left")
        }
        if stalled, parts.isEmpty {
            parts.append("waiting for connection")
        }

        guard !parts.isEmpty else { return nil }
        return parts.joined(separator: " -> ")
    }

    private func uploadProgressField(_ field: String, in summary: String) -> String? {
        let prefix = "\(field)="
        guard let rawValue = summary
            .split(separator: " ")
            .first(where: { $0.hasPrefix(prefix) })?
            .dropFirst(prefix.count) else {
            return nil
        }
        let value = String(rawValue).replacingOccurrences(of: "_", with: " ")
        return value.isEmpty ? nil : String(value.prefix(40))
    }

    private func uploadProgressContextIsUseful(_ context: String) -> Bool {
        let lowercasedContext = context.lowercased()
        return lowercasedContext.contains("retry")
            || lowercasedContext.contains("failed")
            || lowercasedContext.contains("waiting")
            || lowercasedContext.contains("reconnecting")
            || lowercasedContext.contains("background upload")
            || lowercasedContext.contains("chunk")
            || lowercasedContext.contains("source upload")
            || lowercasedContext.contains("saved chunks")
    }

    private var pipelineStage: AnalysisPipelineStage {
        let status = pipelineStatusMessage.lowercased()
        if hasCurrentReviewableClips, !viewModel.analysisService.isAnalyzing, !viewModel.isVideoImportInProgress {
            return .reviewReady
        }
        if viewModel.isVideoImportInProgress || status.contains("upload") {
            return .uploading
        }
        return .analyzing
    }

    private var isBackgroundUploadStillRunning: Bool {
        let status = viewModel.analysisService.statusMessage.lowercased()
        let latestProof = (LaunchTelemetry.shared.latestBackgroundUploadProofSummary ?? "").lowercased()
        let recentProof = (LaunchTelemetry.shared.recentBackgroundUploadProofTrailSummary ?? "").lowercased()
        let combined = [status, latestProof, recentProof].joined(separator: " ")

        return combined.contains("background upload still running")
            || combined.contains("source_still_uploading")
            || combined.contains("active_sessions_pending")
    }

    private var activeTab: AppTab {
        let tab = AppTab(rawValue: selectedTab) ?? .player
        if tab == .review, !hasCurrentReviewableClips, !isReviewWaitingForAnalysis {
            return .player
        }
        return tab
    }

    private var hasCurrentReviewableClips: Bool {
        guard viewModel.isVideoLoaded, viewModel.videoURL != nil, !viewModel.clips.isEmpty else { return false }
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
            "guard=\(reviewGuardReasonSummary)",
            "project=\(viewModel.currentProjectID?.uuidString ?? "none")"
        ].joined(separator: "|")
    }

    private var runtimeStateSignature: String {
        [
            "tab=\(selectedTabTelemetryName)",
            "videoLoaded=\(viewModel.isVideoLoaded)",
            "importing=\(viewModel.isVideoImportInProgress)",
            "importStatus=\(telemetryValue(viewModel.videoImportStatusMessage))",
            "analyzing=\(viewModel.analysisService.isAnalyzing)",
            "progress=\(analysisProgressPercent)",
            "analysisStatus=\(telemetryValue(viewModel.analysisService.statusMessage))",
            "clips=\(viewModel.clips.count)",
            "reviewable=\(currentReviewableClipCount)",
            "guard=\(reviewGuardReasonSummary)",
            "project=\(viewModel.currentProjectID?.uuidString ?? "none")"
        ].joined(separator: "|")
    }

    @ViewBuilder
    private var activeTabContent: some View {
        ZStack {
            persistentTabLayer(.player) {
                VideoPlayerView(
                    viewModel: viewModel,
                    onOpenHistory: {
                        selectTab(.history)
                    },
                    onOpenReview: {
                        selectTab(.review)
                    }
                )
                .id("player-\(revenueCatSyncKey)")
                .environment(subscriptionManager)
                .environment(authService)
            }

            transientActiveTabLayer
        }
    }

    private func persistentTabLayer<Content: View>(
        _ tab: AppTab,
        @ViewBuilder content: () -> Content
    ) -> some View {
        let isActive = activeTab == tab

        return content()
            .opacity(isActive ? 1 : 0)
            .allowsHitTesting(isActive)
            .accessibilityHidden(!isActive)
            .zIndex(isActive ? 1 : 0)
    }

    @ViewBuilder
    private var transientActiveTabLayer: some View {
        switch activeTab {
        case .player:
            EmptyView()

        case .review:
            if hasCurrentReviewableClips {
                ReviewView(viewModel: viewModel, selectedTab: $selectedTab)
            } else if isReviewWaitingForAnalysis {
                ReviewAnalysisWaitingView(
                    title: languageStore.text(.tabReview),
                    progress: viewModel.analysisService.progress,
                    statusMessage: pipelineStatusMessage,
                    detailText: reviewAnalysisDetailText,
                    approximateRemainingText: reviewAnalysisApproximateRemainingText,
                    pipelineStage: pipelineStage,
                    onCancel: requestPipelineCancelConfirmation
                )
            }

        case .export:
            ExportView(viewModel: viewModel)
                .environment(subscriptionManager)
                .environment(authService)

        case .history:
            HistoryView(viewModel: viewModel, onReturnToPlayer: { selectTab(.player) })

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
        fixedAppTabBarRow
        .padding(.top, 7)
        .padding(.bottom, 7)
        .padding(.horizontal, 6)
        .padding(.bottom, 6)
        .background(AppTheme.cardBg.opacity(0.58), in: .rect(cornerRadius: 28))
        .hoopsLiquidGlassSurface(cornerRadius: 28, tint: AppTheme.courtBlue.opacity(0.14), interactive: true)
        .overlay(alignment: .top) {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(.white.opacity(0.18), lineWidth: 1)
        }
        .contentShape(.rect)
        .offset(x: reduceMotion ? 0 : tabBarVisualOffset)
        .simultaneousGesture(tabBarDragGesture)
        .animation(reduceMotion ? nil : tabSelectionAnimation, value: selectedTab)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("app.tabBar")
    }

    private var fixedAppTabBarRow: some View {
        HStack(spacing: 2) {
            ForEach(AppTab.allCases) { tab in
                appTabButton(tab, layout: .fixed)
            }
        }
        .padding(.horizontal, 2)
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
        let displayTitle = compactTabTitle(for: tab, fullTitle: title)

        return Button {
            selectTab(tab)
        } label: {
            VStack(spacing: 4) {
                Image(systemName: tab.iconName)
                    .font(.system(size: 17, weight: isSelected ? .semibold : .medium))
                Text(displayTitle)
                    .font(.system(size: dynamicTypeSize.isAccessibilitySize ? 11 : 10, weight: isSelected ? .semibold : .medium, design: .rounded))
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 2 : 1)
                    .minimumScaleFactor(0.52)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .foregroundStyle(isSelected ? .white : Color.white.opacity(0.78))
            .frame(
                minWidth: layout == .fixed ? 0 : nil,
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

      private func compactTabTitle(for tab: AppTab, fullTitle: String) -> String {
          guard !dynamicTypeSize.isAccessibilitySize else { return fullTitle }
          switch tab {
          case .player:
              return fullTitle.count > 5 ? "Play" : fullTitle
          case .review:
              return fullTitle.count > 6 ? "Clips" : fullTitle
          case .export:
              return fullTitle.count > 6 ? "Share" : fullTitle
          case .history:
              return fullTitle.count > 6 ? "Past" : fullTitle
          case .settings:
              return fullTitle.count > 6 ? "Set" : fullTitle
          }
      }

    private var tabButtonScrollableWidth: CGFloat {
        dynamicTypeSize.isAccessibilitySize ? 106 : 88
    }

    private var tabButtonHeight: CGFloat {
        dynamicTypeSize.isAccessibilitySize ? 84 : 60
    }

    private func requestPipelineCancelConfirmation() {
        showingPipelineCancelConfirmation = true
    }

    private func resumePipelineUpload() {
        viewModel.resumePendingBackgroundUploadFromPlayer()
        LaunchTelemetry.shared.recordStabilityCheckpoint(
            "pipeline_upload_resume.requested",
            metadata: "progress=\(analysisProgressPercent)"
        )
    }

    private func copyPipelineUploadProof() {
        UIPasteboard.general.string = pipelineUploadProofText
        didCopyPipelineUploadProof = true
        LaunchTelemetry.shared.recordStabilityCheckpoint(
            "pipeline_upload_proof.copied",
            metadata: "stage=\(pipelineStage.title) progress=\(analysisProgressPercent)"
        )
        Task {
            try? await Task.sleep(nanoseconds: 1_600_000_000)
            await MainActor.run {
                didCopyPipelineUploadProof = false
            }
        }
    }

    private var pipelineUploadProofText: String {
        [
            "HoopClips Upload Proof",
            "pipelineStage=\(safePipelineProofValue(pipelineStage.title))",
            "analysisProgress=\(analysisProgressPercent)%",
            "analysisStatus=\(safePipelineProofValue(pipelineStatusMessage))",
            "uploadDetail=\(safePipelineProofValue(pipelineDetailMessage ?? "none"))",
            "latestUploadProgress=\(safePipelineProofValue(CloudAnalysisService.latestUploadProgressSummary()))",
            "pendingBackgroundUploadManifest=\(safePipelineProofValue(CloudAnalysisService.pendingBackgroundUploadManifestSummary()))",
            "backgroundUploadRuntimePolicy=\(safePipelineProofValue(CloudAnalysisService.backgroundUploadRuntimePolicySummary()))",
            "backgroundUploadCompletionProof=\(safePipelineProofValue(CloudAnalysisService.backgroundUploadCompletionProofSummary()))",
            "latestBackgroundUploadProof=\(safePipelineProofValue(LaunchTelemetry.shared.latestBackgroundUploadProofSummary ?? "none"))",
            "privacy=no_urls_no_object_keys_no_local_file_paths"
        ].joined(separator: "\n")
    }

    private func safePipelineProofValue(_ value: String) -> String {
        value
            .replacingOccurrences(of: "\n", with: " ")
            .replacingOccurrences(of: "\r", with: " ")
            .replacingOccurrences(of: "file://", with: "file-redacted://")
            .replacingOccurrences(of: "/var/", with: "/redacted/")
            .replacingOccurrences(of: "/Users/", with: "/redacted/")
            .prefix(260)
            .description
    }

    private func selectTab(_ tab: AppTab) {
        guard selectedTab != tab.rawValue else { return }
        recordTabSwitchBreadcrumb(fromRawValue: selectedTab, toRawValue: tab.rawValue, phase: "requested", trigger: "tab_bar")
          if tab == .review, !hasCurrentReviewableClips {
              if isReviewWaitingForAnalysis {
                  dismissReviewRecoveryNotice()
              } else {
                  resetToDefaultTabAfterReviewBlock(reason: "no_reviewable_clips")
                  return
              }
          }
        dismissReviewRecoveryNotice()
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
        if hasCurrentReviewableClips || isReviewWaitingForAnalysis {
            dismissReviewRecoveryNotice()
            return
        }

        guard selectedTab == AppTab.review.rawValue else { return }
        resetToDefaultTabAfterReviewBlock(reason: reason)
    }

    private func resetToDefaultTabAfterReviewBlock(reason: String) {
        LaunchTelemetry.shared.recordStabilityCheckpoint(
            "tab.switch.blocked",
            metadata: reviewBlockMetadata(reason: reason)
        )
        showReviewRecoveryNotice()
        guard selectedTab != AppTab.player.rawValue else { return }

        if reduceMotion {
            selectedTab = AppTab.player.rawValue
        } else {
            withAnimation(tabSwipeAnimation) {
                selectedTab = AppTab.player.rawValue
            }
        }
        HoopsAccessibility.announce("Review needs clips first. Back to Player.")
    }

    private func showReviewRecoveryNotice() {
        let notice = ReviewRecoveryNotice(
            reason: reviewGuardReasonSummary,
            clipCount: viewModel.clips.count,
            reviewableClipCount: currentReviewableClipCount
        )
        guard reviewRecoveryNotice != notice else { return }

        if reduceMotion {
            reviewRecoveryNotice = notice
        } else {
            withAnimation(tabSelectionAnimation) {
                reviewRecoveryNotice = notice
            }
        }
    }

    private func dismissReviewRecoveryNotice() {
        guard reviewRecoveryNotice != nil else { return }

        if reduceMotion {
            reviewRecoveryNotice = nil
        } else {
            withAnimation(tabSelectionAnimation) {
                reviewRecoveryNotice = nil
            }
        }
    }

    private func showUploadResumeNotice(_ message: String) {
        let notice = UploadResumeNotice(message: message)
        if reduceMotion {
            uploadResumeNotice = notice
        } else {
            withAnimation(tabSelectionAnimation) {
                uploadResumeNotice = notice
            }
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 2.8) {
            guard uploadResumeNotice == notice else { return }
            if reduceMotion {
                uploadResumeNotice = nil
            } else {
                withAnimation(tabSelectionAnimation) {
                    uploadResumeNotice = nil
                }
            }
        }
    }

    private func openPlayerFromReviewRecovery() {
        dismissReviewRecoveryNotice()
        selectTab(.player)
    }

    private func handleAnalysisNotificationTap(_ notification: Notification) {
        let event = notification.userInfo?["event"] as? String ?? "unknown"
        let context = notification.userInfo?["completionContext"] as? String ?? "unknown"
        LaunchTelemetry.shared.recordStabilityCheckpoint(
            "notification.opened",
            metadata: "event=\(telemetryValue(event)) context=\(telemetryValue(context))"
        )

        dismissReviewRecoveryNotice()
        if event == "background_upload_completed" || context == AnalysisNotificationService.CompletionContext.backgroundUploadResume.rawValue {
            selectTab(.player)
            showUploadResumeNotice("Upload finished. Continuing from Player.")
            resumeCloudAnalysisAfterForegroundIfNeeded()
            HoopsAccessibility.announce("Upload finished. Continuing from Player.")
            return
        }

        if event == "analysis_completed", hasCurrentReviewableClips {
            selectTab(.review)
            HoopsAccessibility.announce("Review is ready.")
            return
        }

        selectTab(.player)
        resumeCloudAnalysisAfterForegroundIfNeeded()
    }

    private func resumeCloudAnalysisAfterForegroundIfNeeded() {
        let pendingManifest = CloudAnalysisService.pendingBackgroundUploadManifestSummary()
        if pendingManifest.contains("pending=true") {
            let message = pendingManifest.contains("source=available")
                ? "Resuming saved upload..."
                : "Saved upload source missing. Check Player."
            showUploadResumeNotice(message)
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "upload.resume.notice",
                metadata: "sourceAvailable=\(pendingManifest.contains("source=available"))"
            )
        }
        Task { @MainActor in
            await viewModel.resumeInFlightCloudAnalysisIfNeeded()
        }
    }

    private func reviewBlockMetadata(reason: String) -> String {
          [
              "to=review",
              "reason=\(reason)",
              "videoLoaded=\(viewModel.isVideoLoaded)",
              "analyzing=\(viewModel.analysisService.isAnalyzing)",
            "progress=\(viewModel.analysisService.progress)",
            "clips=\(viewModel.clips.count)",
            "reviewable=\(currentReviewableClipCount)",
            "videoDuration=\(viewModel.videoDuration)",
            "guard=\(reviewGuardReasonSummary)",
            "project=\(viewModel.currentProjectID?.uuidString ?? "none")"
        ].joined(separator: " ")
    }

    private func recordRuntimeStateBreadcrumb(reason: String) {
        LaunchTelemetry.shared.recordRuntimeState(
            screen: selectedTabTelemetryName,
            metadata: runtimeStateMetadata(reason: reason)
        )
    }

    private func runtimeStateMetadata(reason: String) -> String {
        [
            "reason=\(reason)",
            "build=\(appBuildNumberForTelemetry)",
            "screen=\(selectedTabTelemetryName)",
            "videoLoaded=\(viewModel.isVideoLoaded)",
            "importing=\(viewModel.isVideoImportInProgress)",
            "importStatus=\(telemetryValue(viewModel.videoImportStatusMessage))",
            "analyzing=\(viewModel.analysisService.isAnalyzing)",
            "progress=\(analysisProgressPercent)",
            "analysisMode=\(telemetryValue(viewModel.analysisModeDisplayName))",
            "analysisStatus=\(telemetryValue(viewModel.analysisService.statusMessage))",
            "clips=\(viewModel.clips.count)",
            "reviewable=\(currentReviewableClipCount)",
            "guard=\(reviewGuardReasonSummary)",
            "project=\(viewModel.currentProjectID?.uuidString ?? "none")"
        ].joined(separator: " ")
    }

    private var analysisProgressPercent: Int {
        Int((min(max(viewModel.analysisService.progress, 0), 1) * 100).rounded(.down))
    }

    private var appBuildNumberForTelemetry: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown"
    }

    private func telemetryValue(_ rawValue: String?) -> String {
        LaunchTelemetry.redactedAIEditFailureReason(rawValue)
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: "_")
    }

    private func isReviewableClip(_ clip: Clip) -> Bool {
        reviewClipInvalidReason(clip) == nil
    }

    private var reviewGuardReasonSummary: String {
        if !viewModel.isVideoLoaded { return "video_not_loaded" }
        if viewModel.videoURL == nil { return "missing_source_url" }
        if viewModel.clips.isEmpty { return "no_clips" }
        let reasons = viewModel.clips.compactMap(reviewClipInvalidReason)
        if reasons.isEmpty { return "ok" }
        let uniqueReasons = Array(Set(reasons)).sorted()
        return uniqueReasons.prefix(4).joined(separator: ",")
    }

    private func reviewClipInvalidReason(_ clip: Clip) -> String? {
        guard clip.startTime.isFinite, clip.endTime.isFinite else { return "non_finite_window" }
        let sourceDuration = viewModel.videoDuration
        guard sourceDuration.isFinite, sourceDuration > 0 else { return "invalid_source_duration" }
        let upperBound = sourceDuration
        let start = max(0, min(clip.startTime, upperBound))
        let end = max(0, min(clip.endTime, upperBound))
        guard end > start else { return "empty_window" }
        guard clip.confidence.isFinite,
              clip.audioScore.isFinite,
              clip.visualScore.isFinite,
              clip.motionScore.isFinite,
              clip.combinedScore.isFinite,
              clip.playbackSpeed.isFinite,
              clip.playbackSpeed > 0 else {
            return "non_finite_score"
        }
        if let eventCenter = clip.eventCenter, !eventCenter.isFinite {
            return "non_finite_event_center"
        }
        if let audioCueConfidence = clip.audioCueConfidence, !audioCueConfidence.isFinite {
            return "non_finite_audio_confidence"
        }
        if let audioCueTime = clip.audioCueTime, !audioCueTime.isFinite {
            return "non_finite_audio_time"
        }
        return nil
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
            "importing=\(viewModel.isVideoImportInProgress)",
            "analyzing=\(viewModel.analysisService.isAnalyzing)",
            "progress=\(analysisProgressPercent)",
            "analysisStatus=\(telemetryValue(viewModel.analysisService.statusMessage))",
            "clips=\(viewModel.clips.count)",
            "reviewable=\(currentReviewableClipCount)",
            "guard=\(reviewGuardReasonSummary)",
            "project=\(viewModel.currentProjectID?.uuidString ?? "none")"
        ].joined(separator: " ")
        LaunchTelemetry.shared.recordStabilityCheckpoint("tab.switch.\(phase)", metadata: metadata)
    }

    private var reviewAnalysisDetailText: String {
        CloudAnalysisProgressCopy.detail(
            statusMessage: viewModel.analysisService.statusMessage,
            analysisMode: viewModel.analysisMode,
            teamSelection: viewModel.settings.highlightTeamSelection
        )
    }

    private var reviewAnalysisApproximateRemainingText: String? {
        CloudAnalysisProgressCopy.approximateRemainingTime(
            statusMessage: viewModel.analysisService.statusMessage,
            analysisMode: viewModel.analysisMode,
            progress: viewModel.analysisService.progress,
            durationSeconds: viewModel.videoDuration
        )
    }
}

private struct ReviewAnalysisWaitingView: View {
    let title: String
    let progress: Double
    let statusMessage: String
    let detailText: String
    let approximateRemainingText: String?
    let pipelineStage: AnalysisPipelineStage
    let onCancel: () -> Void

    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    private var safeProgress: Double {
        guard progress.isFinite else { return 0 }
        return min(max(progress, 0), 1)
    }

    private var progressPercentText: String {
        "\(Int(safeProgress * 100))%"
    }

    private var visibleStatusMessage: String {
        let trimmed = statusMessage.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? "Analysis is starting..." : trimmed
    }

    var body: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.18, courtOpacity: 0.08)

                VStack(spacing: 18) {
                    Spacer(minLength: 20)

                    VStack(alignment: .leading, spacing: 16) {
                        HStack(alignment: .center, spacing: 12) {
                            ZStack {
                                Circle()
                                    .fill(AppTheme.neonPurple.opacity(0.18))
                                    .frame(width: 46, height: 46)
                                ProgressView()
                                    .tint(AppTheme.neonPurple)
                            }

                            VStack(alignment: .leading, spacing: 4) {
                                Text("Analyzing, please wait")
                                    .font(.headline.weight(.bold))
                                    .foregroundStyle(.white)
                                Text("Review will open automatically when clips are ready.")
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(AppTheme.subtleText)
                                    .fixedSize(horizontal: false, vertical: true)
                            }

                            Spacer(minLength: 0)

                            Text(progressPercentText)
                                .font(.subheadline.weight(.bold).monospacedDigit())
                                .foregroundStyle(AppTheme.neonPurple)
                        }

                        analysisProgressBar
                        reviewPipelineGlass

                        Text(visibleStatusMessage)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.white.opacity(0.92))
                            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                            .minimumScaleFactor(0.84)
                            .fixedSize(horizontal: false, vertical: true)

                        Text(detailText)
                            .font(.caption)
                            .foregroundStyle(AppTheme.subtleText)
                            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                            .minimumScaleFactor(0.84)
                            .fixedSize(horizontal: false, vertical: true)

                        if let approximateRemainingText {
                            Label(approximateRemainingText, systemImage: "clock.badge.checkmark")
                                .font(.caption2.weight(.semibold))
                                .foregroundStyle(.white.opacity(0.9))
                                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                                .minimumScaleFactor(0.84)
                                .fixedSize(horizontal: false, vertical: true)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 8)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(.white.opacity(0.07), in: .rect(cornerRadius: 12))
                                .accessibilityIdentifier("review.analysisWaiting.approximateRemainingTime")
                        }

                        cancelButton
                    }
                    .padding(18)
                    .background(
                        LinearGradient(
                            colors: [
                                pipelineStage.tint.opacity(0.20),
                                AppTheme.cardBg.opacity(0.82),
                                AppTheme.surfaceBg.opacity(0.72)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        in: .rect(cornerRadius: 24)
                    )
                    .hoopsLiquidGlassSurface(cornerRadius: 24, tint: pipelineStage.tint.opacity(0.16))
                    .overlay {
                        RoundedRectangle(cornerRadius: 24)
                            .stroke(pipelineStage.tint.opacity(0.32), lineWidth: 1)
                    }
                    .shadow(color: pipelineStage.tint.opacity(0.16), radius: 22, y: 12)
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("Analyzing, please wait")
                    .accessibilityValue("\(progressPercentText). \(visibleStatusMessage). \(detailText)")
                    .accessibilityIdentifier("review.analysisWaiting.card")

                    Spacer(minLength: 80)
                }
                .padding(.horizontal, 16)
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
    }

    private var analysisProgressBar: some View {
        ProgressView(value: safeProgress)
            .tint(pipelineStage.tint)
            .scaleEffect(y: 2)
            .accessibilityLabel("Analysis progress")
            .accessibilityValue(progressPercentText)
    }

    private var reviewPipelineGlass: some View {
        VStack(alignment: .leading, spacing: 10) {
            TinyAnalysisPipelineTracker(currentStage: pipelineStage)

            HStack(spacing: 8) {
                Label("Upload first", systemImage: "icloud.and.arrow.up.fill")
                    .foregroundStyle(pipelineStage == .uploading ? AnalysisPipelineStage.uploading.tint : AppTheme.subtleText)
                Label("Cloud scan", systemImage: "brain.head.profile.fill")
                    .foregroundStyle(pipelineStage == .analyzing ? AnalysisPipelineStage.analyzing.tint : AppTheme.subtleText)
                Label("Review opens", systemImage: "checkmark.seal.fill")
                    .foregroundStyle(pipelineStage == .reviewReady ? AnalysisPipelineStage.reviewReady.tint : AppTheme.subtleText)
            }
            .font(.caption2.weight(.bold))
            .lineLimit(1)
            .minimumScaleFactor(0.72)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(12)
        .background(.white.opacity(0.06), in: .rect(cornerRadius: 16))
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .stroke(pipelineStage.tint.opacity(0.20), lineWidth: 1)
        }
        .accessibilityIdentifier("review.analysisWaiting.pipeline")
    }

    private var cancelButton: some View {
        Button(role: .cancel, action: onCancel) {
            Label(pipelineStage.cancelTitle, systemImage: "xmark.circle.fill")
                .font(.caption.weight(.bold))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 11)
        }
        .buttonStyle(.plain)
        .foregroundStyle(.white)
        .background(AppTheme.dangerRed.opacity(0.18), in: .rect(cornerRadius: 14))
        .overlay {
            RoundedRectangle(cornerRadius: 14)
                .stroke(AppTheme.dangerRed.opacity(0.32), lineWidth: 1)
        }
        .accessibilityIdentifier("review.analysisWaiting.cancelUpload")
    }
}

private struct ReviewUnavailableRecoveryCard: View {
    let notice: ContentView.ReviewRecoveryNotice
    let onRerunAnalysis: () -> Void
    let onDismiss: () -> Void

    private var reasonCopy: String {
        switch notice.reason {
        case "video_not_loaded":
            return "No source video is loaded."
        case "missing_source_url":
            return "The source video file is missing."
        case "no_clips":
            return "This video has no review clips yet."
        case "invalid_source_duration":
            return "The source video duration could not be verified."
        case "empty_window":
            return "The clip windows are empty or outside the video."
        case "non_finite_window", "non_finite_score", "non_finite_event_center", "non_finite_audio_confidence", "non_finite_audio_time":
            return "Some clip data is not safe to preview."
        default:
            return "Clip data needs a fresh analysis pass."
        }
    }

    private var titleCopy: String {
        switch notice.reason {
        case "video_not_loaded", "missing_source_url":
            return "Review needs a video"
        case "no_clips":
            return "Review needs clips first"
        default:
            return "Review needs safe clips"
        }
    }

    private var messageCopy: String {
        switch notice.reason {
        case "video_not_loaded", "missing_source_url":
            return "Go back to Player and import a video first."
        case "no_clips":
            return "Start AI Analysis on Player. Review opens when clips are ready."
        default:
            return "Some clips are not safe to preview yet. Back to Player and run AI Analysis again."
        }
    }

    private var actionTitle: String {
        "Back to Player"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 12) {
                ZStack {
                    Circle()
                        .fill(AppTheme.warningYellow.opacity(0.16))
                        .frame(width: 42, height: 42)
                    Image(systemName: notice.reason == "no_clips" ? "film.badge.plus" : "exclamationmark.triangle.fill")
                        .font(.system(size: 18, weight: .bold))
                        .foregroundStyle(AppTheme.warningYellow)
                }

                VStack(alignment: .leading, spacing: 5) {
                    Text(titleCopy)
                        .font(.headline.weight(.bold))
                        .foregroundStyle(.white)
                    Text(messageCopy)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(AppTheme.subtleText)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 8)

                Button(action: onDismiss) {
                    Image(systemName: "xmark")
                        .font(.system(size: 13, weight: .bold))
                        .foregroundStyle(AppTheme.subtleText)
                        .frame(width: 32, height: 32)
                        .background(AppTheme.cardBg.opacity(0.82), in: Circle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Dismiss Review unavailable message")
            }

            Text("\(notice.reviewableClipCount)/\(notice.clipCount) clips reviewable. \(reasonCopy)")
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.warningYellow)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)

            Button(action: onRerunAnalysis) {
                Label(actionTitle, systemImage: "play.circle.fill")
                    .font(.subheadline.weight(.bold))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 13)
                    .foregroundStyle(.white)
                    .background(
                        LinearGradient(
                            colors: [AppTheme.neonPurple, AppTheme.accentPurple],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        in: RoundedRectangle(cornerRadius: 18, style: .continuous)
                    )
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("review.unavailable.rerunAnalysis")
            .accessibilityHint("Opens Player so you can import, wait for, or rerun analysis.")
        }
        .padding(18)
        .background(
            RoundedRectangle(cornerRadius: 26, style: .continuous)
                .fill(AppTheme.cardBg.opacity(0.98))
                .overlay {
                    RoundedRectangle(cornerRadius: 26, style: .continuous)
                        .stroke(AppTheme.warningYellow.opacity(0.34), lineWidth: 1)
                }
                .shadow(color: .black.opacity(0.35), radius: 22, x: 0, y: 14)
        )
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("review.unavailable.card")
    }
}

private struct GlobalImportProgressBanner: View {
    let message: String
    let detailMessage: String?
    let stage: AnalysisPipelineStage
    let canResumeUpload: Bool
    let didCopyProof: Bool
    let onResumeUpload: () -> Void
    let onCopyProof: () -> Void
    let onCancel: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                ZStack {
                    Circle()
                        .fill(stage.tint.opacity(0.18))
                        .frame(width: 28, height: 28)
                    Image(systemName: stage.iconName)
                        .font(.caption.weight(.bold))
                        .foregroundStyle(stage.tint)
                }
                .accessibilityHidden(true)

                Text(shortMessage)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.white)
                    .lineLimit(1)
                    .minimumScaleFactor(0.82)

                Spacer(minLength: 0)

                if canResumeUpload {
                    resumeButton
                }
                copyProofButton
                cancelButton
            }

            TinyAnalysisPipelineTracker(currentStage: stage)

            if let detailMessage {
                Text(detailMessage)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(AppTheme.subtleText)
                    .lineLimit(1)
                    .minimumScaleFactor(0.76)
                    .accessibilityIdentifier("analysis.pipeline.uploadDetail")
            }
        }
        .padding(.horizontal, 13)
        .padding(.vertical, 10)
        .background(
            LinearGradient(
                colors: [
                    stage.tint.opacity(0.22),
                    AppTheme.cardBg.opacity(0.76),
                    AppTheme.surfaceBg.opacity(0.64)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: .rect(cornerRadius: 18)
        )
        .hoopsLiquidGlassSurface(cornerRadius: 18, tint: stage.tint.opacity(0.15))
        .overlay(
            RoundedRectangle(cornerRadius: 18)
                .stroke(stage.tint.opacity(0.34), lineWidth: 1)
        )
        .shadow(color: stage.tint.opacity(0.16), radius: 18, x: 0, y: 9)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Import in progress")
        .accessibilityValue(shortMessage)
        .accessibilityIdentifier("global.importProgress.banner")
    }

    private var shortMessage: String {
        let trimmed = message.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? "Importing video..." : trimmed
    }

    private var resumeButton: some View {
        Button(action: onResumeUpload) {
            Label("Resume", systemImage: "arrow.clockwise.icloud.fill")
                .font(.caption2.weight(.bold))
                .foregroundStyle(.white)
                .labelStyle(.titleAndIcon)
                .padding(.horizontal, 9)
                .padding(.vertical, 6)
                .background(stage.tint.opacity(0.26), in: Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Resume upload")
        .accessibilityIdentifier("analysis.pipeline.resumeUploadButton")
    }

    private var copyProofButton: some View {
        Button(action: onCopyProof) {
            Image(systemName: didCopyProof ? "checkmark.circle.fill" : "doc.on.doc.fill")
                .font(.caption.weight(.bold))
                .foregroundStyle(didCopyProof ? AppTheme.successGreen : stage.tint)
                .frame(width: 30, height: 30)
                .background(Color.white.opacity(didCopyProof ? 0.16 : 0.08), in: Circle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(didCopyProof ? "Upload proof copied" : "Copy upload proof")
        .accessibilityIdentifier("analysis.pipeline.copyProofButton")
    }

    private var cancelButton: some View {
        Button(role: .cancel, action: onCancel) {
            Text("Cancel")
                .font(.caption2.weight(.bold))
                .foregroundStyle(.white)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(AppTheme.dangerRed.opacity(0.20), in: Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(stage.cancelTitle)
    }
}

private struct UploadResumeNoticeToast: View {
    let message: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "arrow.clockwise.icloud.fill")
                .font(.caption.weight(.heavy))
                .foregroundStyle(Color.cyan)
                .accessibilityHidden(true)

            Text(message)
                .font(.caption.weight(.bold))
                .foregroundStyle(.white)
                .lineLimit(1)
                .minimumScaleFactor(0.82)

            Spacer(minLength: 0)
        }
        .padding(.horizontal, 13)
        .padding(.vertical, 10)
        .background(AppTheme.cardBg.opacity(0.96), in: .rect(cornerRadius: 16))
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.cyan.opacity(0.30), lineWidth: 1)
        }
        .shadow(color: Color.cyan.opacity(0.14), radius: 18, x: 0, y: 9)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("upload.resume.noticeToast")
    }
}

private struct UploadRetryCard: View {
    let onRetry: () -> Void

    var body: some View {
        HStack(spacing: 11) {
            Image(systemName: "arrow.clockwise.circle.fill")
                .font(.system(size: 18, weight: .bold))
                .foregroundStyle(AppTheme.neonPurple)
                .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: 2) {
                Text("Upload canceled")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.white)
                Text("Safe to retry when you are ready.")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(AppTheme.subtleText)
                    .lineLimit(1)
                    .minimumScaleFactor(0.82)
            }

            Spacer(minLength: 0)

            Button(action: onRetry) {
                Text("Retry upload")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(AppTheme.neonPurple.opacity(0.26), in: Capsule())
                    .overlay {
                        Capsule().stroke(AppTheme.neonPurple.opacity(0.42), lineWidth: 1)
                    }
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("upload.retryAfterCancel.button")
        }
        .padding(.horizontal, 13)
        .padding(.vertical, 11)
        .background(AppTheme.cardBg.opacity(0.97), in: .rect(cornerRadius: 16))
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .stroke(AppTheme.neonPurple.opacity(0.24), lineWidth: 1)
        }
        .shadow(color: .black.opacity(0.20), radius: 14, x: 0, y: 8)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("upload.retryAfterCancel.card")
    }
}

private enum AnalysisPipelineStage: Int, CaseIterable {
    case uploading
    case analyzing
    case reviewReady

    var title: String {
        switch self {
        case .uploading:
            return "Uploading"
        case .analyzing:
            return "Analyzing"
        case .reviewReady:
            return "Review ready"
        }
    }

    var cancelTitle: String {
        switch self {
        case .uploading:
            return "Cancel upload"
        case .analyzing, .reviewReady:
            return "Cancel analysis"
        }
    }

    var tint: Color {
        switch self {
        case .uploading:
            return Color(red: 0.26, green: 0.69, blue: 1.0)
        case .analyzing:
            return AppTheme.warningYellow
        case .reviewReady:
            return AppTheme.successGreen
        }
    }

    var iconName: String {
        switch self {
        case .uploading:
            return "icloud.and.arrow.up.fill"
        case .analyzing:
            return "brain.head.profile.fill"
        case .reviewReady:
            return "checkmark.seal.fill"
        }
    }
}

private struct TinyAnalysisPipelineTracker: View {
    let currentStage: AnalysisPipelineStage

    var body: some View {
        HStack(spacing: 6) {
            ForEach(AnalysisPipelineStage.allCases, id: \.self) { stage in
                pipelineChip(stage)

                if stage != AnalysisPipelineStage.allCases.last {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 8, weight: .bold))
                        .foregroundStyle(AppTheme.subtleText.opacity(0.58))
                        .accessibilityHidden(true)
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Progress pipeline")
        .accessibilityValue(AnalysisPipelineStage.allCases.map(\.title).joined(separator: " to "))
        .accessibilityIdentifier("analysis.pipeline.tracker")
    }

    private func pipelineChip(_ stage: AnalysisPipelineStage) -> some View {
        let isCurrent = stage == currentStage
        let isComplete = stage.rawValue < currentStage.rawValue
        let foreground = isCurrent || isComplete ? Color.white : AppTheme.subtleText
        let fill = isCurrent
            ? stage.tint.opacity(0.30)
            : (isComplete ? stage.tint.opacity(0.18) : Color.white.opacity(0.06))
        let stroke = isCurrent
            ? stage.tint.opacity(0.58)
            : (isComplete ? stage.tint.opacity(0.34) : Color.white.opacity(0.08))

        return Label(stage.title, systemImage: stage.iconName)
            .font(.caption2.weight(.bold))
            .foregroundStyle(foreground)
            .lineLimit(1)
            .minimumScaleFactor(0.68)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(fill, in: Capsule())
            .overlay {
                Capsule().stroke(stroke, lineWidth: 1)
            }
            .labelStyle(.titleAndIcon)
    }
}

extension View {
    @ViewBuilder
    func hoopsLiquidGlassSurface(cornerRadius: CGFloat, tint: Color = .white.opacity(0.08), interactive: Bool = false) -> some View {
        if #available(iOS 26.0, *) {
            if interactive {
                self.glassEffect(.regular.tint(tint).interactive(), in: .rect(cornerRadius: cornerRadius))
            } else {
                self.glassEffect(.regular.tint(tint), in: .rect(cornerRadius: cornerRadius))
            }
        } else {
            self.background(.ultraThinMaterial, in: .rect(cornerRadius: cornerRadius))
        }
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
