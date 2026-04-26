import SwiftUI
import Foundation

struct SettingsView: View {
    @Bindable var viewModel: HighlightsViewModel
    @Bindable var authService: AuthService
    @Bindable var subscriptionManager: SubscriptionManager
    @Environment(AppLanguageStore.self) private var languageStore
    @State private var showingResetAlert = false
    @State private var showingPaywall = false
    @State private var showingAdvancedSettings = false
    @State private var feedbackType: FeedbackType = .suggestion
    @State private var contactEmail = ""
    @State private var feedbackMessage = ""
    @State private var isSubmittingFeedback = false
    @State private var feedbackBanner: FeedbackBanner?
    @State private var expandedFAQIDs: Set<String> = []

    private enum FeedbackType: String, CaseIterable, Identifiable {
        case suggestion = "Suggestion"
        case bug = "Bug Report"
        case question = "Question"

        var id: String { rawValue }

        var icon: String {
            switch self {
            case .suggestion: return "sparkles"
            case .bug: return "ladybug.fill"
            case .question: return "questionmark.bubble.fill"
            }
        }
    }

    private struct FeedbackBanner: Identifiable {
        let id = UUID()
        let message: String
        let icon: String
        let tint: Color
    }

    private struct FormspreePayload: Encodable {
        let category: String
        let email: String?
        let message: String
        let source: String
        let appVersion: String
        let exportTheme: String
        let exportQuality: String
        let exportFormat: String
    }

    private struct FormspreeErrorEnvelope: Decodable {
        struct FormspreeErrorItem: Decodable {
            let message: String?
        }

        let errors: [FormspreeErrorItem]?
    }

    private struct FAQItem: Identifiable {
        let id: String
        let question: String
        let answer: String
        let icon: String
    }

    fileprivate struct SettingsPreviewStat: Identifiable {
        let id = UUID()
        let icon: String
        let value: String
        let label: String
        let tint: Color
    }

    private static let commonFAQItems: [FAQItem] = [
        FAQItem(
            id: "no-clips",
            question: "Why did the app find few or no clips?",
            answer: "Lower the confidence threshold, increase clip duration range, and check the source video has clear motion and audible peaks. Low-light or static camera footage can reduce detection quality.",
            icon: "film.badge.questionmark"
        ),
        FAQItem(
            id: "weights",
            question: "When should I change AI weights?",
            answer: "Leave weights balanced for most games. Use Advanced Settings only if your footage is unusual, like very loud gyms (audio bias) or silent clips with strong movement (motion/pose bias).",
            icon: "slider.horizontal.3"
        ),
        FAQItem(
            id: "export-format",
            question: "Should I export MP4 or MOV?",
            answer: "MP4 is the best default for sharing and cross-platform compatibility. MOV is a good Apple-native option if you plan to edit or manage clips in Apple-focused workflows.",
            icon: "doc.badge.gearshape"
        ),
        FAQItem(
            id: "quick-share",
            question: "How does Review & Share work on iPhone?",
            answer: "After export completes, the app opens an in-app review of the latest reel first. From the Review & Share section, you can replay it, save it to Photos, or open the iOS share sheet for Messages, AirDrop, Files, or social apps.",
            icon: "square.and.arrow.up.fill"
        )
    ]

    var body: some View {
        NavigationStack {
            ZStack {
                AppTheme.darkBg.ignoresSafeArea()
                AppTheme.meshBackground
                    .opacity(0.14)
                    .ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 24) {
                        AnyView(settingsHeroCard)
                        AnyView(languageSettingsCard)
                        #if DEBUG
                        AnyView(runtimeStatusCard)
                        #endif
                        AnyView(workflowHubLink)
                        AnyView(membershipHubLink)
                        AnyView(accountQuickActionCard)
                        AnyView(supportHubLink)
                        AnyView(aboutHubLink)
                        #if DEBUG
                        AnyView(settingsFootnote)
                        #endif
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                    .padding(.bottom, 100)
                }
            }
            .navigationTitle(languageStore.text(.settingsTitle))
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .sheet(isPresented: $showingPaywall) {
                PaywallView(subscriptionManager: subscriptionManager, authService: authService)
            }
            .alert("Reset Settings?", isPresented: $showingResetAlert) {
                Button("Reset", role: .destructive) {
                    viewModel.settings = AnalysisSettings()
                }
                Button("Cancel", role: .cancel) { }
            } message: {
                Text("This will restore all AI settings to their defaults.")
            }
        }
    }

    private var settingsHeroCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top, spacing: 14) {
                ZStack {
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .fill(AppTheme.accentPurple.opacity(0.18))
                        .frame(width: 62, height: 62)
                    Image(systemName: "slider.horizontal.3")
                        .font(.title2.weight(.bold))
                        .foregroundStyle(AppTheme.neonPurple)
                }

                VStack(alignment: .leading, spacing: 6) {
                    Text(languageStore.text(.controlRoom))
                        .font(.title3.weight(.bold))
                        .foregroundStyle(.white)

                    Text(languageStore.text(.controlRoomSubtitle))
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 0)
            }

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: "person.crop.circle.fill",
                    value: authService.currentUser?.displayName ?? authMethodLabel,
                    label: languageStore.text(.account),
                    tint: AppTheme.neonPurple
                )
                RorkMetricChip(
                    icon: subscriptionManager.isProUser ? "checkmark.seal.fill" : "sparkles",
                    value: subscriptionManager.isProUser ? "Pro" : "\(subscriptionManager.freeUsesRemaining)",
                    label: subscriptionManager.isProUser ? languageStore.text(.plan) : languageStore.text(.freeLeft),
                    tint: subscriptionManager.isProUser ? AppTheme.successGreen : AppTheme.warningYellow
                )
            }

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: "clock.badge.checkmark.fill",
                    value: formattedTargetDuration(viewModel.settings.targetHighlightDuration),
                    label: languageStore.text(.targetReel),
                    tint: AppTheme.warningYellow
                )
                RorkMetricChip(
                    icon: "square.stack.3d.up.fill",
                    value: viewModel.selectedFormat.rawValue,
                    label: languageStore.text(.export),
                    tint: AppTheme.neonPurple
                )
            }
        }
        .padding(18)
        .rorkCard(cornerRadius: 22, stroke: AppTheme.softBorder, glowOpacity: 0.08)
    }

    private var languageSettingsCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            RorkSectionHeader(
                title: languageStore.text(.languageCardTitle),
                icon: "globe",
                subtitle: languageStore.text(.languageCardSubtitle)
            )

            Menu {
                ForEach(AppLanguage.allCases) { language in
                    Button {
                        languageStore.selectedLanguage = language
                    } label: {
                        if languageStore.selectedLanguage == language {
                            Label(language.nativeName, systemImage: "checkmark")
                        } else {
                            Text(language.nativeName)
                        }
                    }
                }
            } label: {
                HStack(spacing: 12) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(AppTheme.accentPurple.opacity(0.14))
                            .frame(width: 42, height: 42)
                        Image(systemName: "character.bubble.fill")
                            .foregroundStyle(AppTheme.neonPurple)
                    }

                    VStack(alignment: .leading, spacing: 3) {
                        Text(languageStore.text(.languageTitle))
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.white)
                        Text("\(languageStore.text(.languageCurrent)): \(languageStore.selectedLanguage.nativeName)")
                            .font(.caption)
                            .foregroundStyle(AppTheme.subtleText)
                    }

                    Spacer()

                    Image(systemName: "chevron.up.chevron.down")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(AppTheme.neonPurple)
                }
                .padding(14)
                .background(AppTheme.surfaceBg.opacity(0.55), in: .rect(cornerRadius: 16))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(AppTheme.softBorder, lineWidth: 1)
                )
            }

            Text(languageStore.text(.languageRestartNote))
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder, glowOpacity: 0.05)
    }

    private var workflowHubLink: some View {
        settingsHubLink(
            title: languageStore.text(.workflowDefaults),
            subtitle: languageStore.text(.workflowDefaultsSubtitle),
            icon: "waveform.and.magnifyingglass",
            accent: AppTheme.neonPurple,
            stats: [
                SettingsPreviewStat(
                    icon: "scope",
                    value: "\(Int(viewModel.settings.confidenceThreshold * 100))%",
                    label: "Threshold",
                    tint: AppTheme.neonPurple
                ),
                SettingsPreviewStat(
                    icon: "clock.badge.checkmark.fill",
                    value: formattedTargetDuration(viewModel.settings.targetHighlightDuration),
                    label: "Target",
                    tint: AppTheme.warningYellow
                ),
                SettingsPreviewStat(
                    icon: "gauge.with.dots.needle.67percent",
                    value: "\(Int(viewModel.settings.framesSampledPerSecond)) fps",
                    label: "Sampling",
                    tint: AppTheme.successGreen
                )
            ]
        ) {
            workflowSettingsPage
        }
    }

    private var runtimeStatusCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            RorkSectionHeader(
                title: "Launch Status",
                icon: "antenna.radiowaves.left.and.right",
                subtitle: "What this build can use in production right now."
            )

            HStack(spacing: 10) {
                SettingsPreviewStat(
                    icon: "cpu.fill",
                    value: AppConstants.cloudLaunchStatusLabel,
                    label: "Analysis Path",
                    tint: AppConstants.cloudAnalysisEnabled ? AppTheme.warningYellow : AppTheme.successGreen
                )
                .settingsPreviewStatCard()

                SettingsPreviewStat(
                    icon: "person.crop.circle.badge.checkmark",
                    value: AppConstants.googleSignInConfigured ? "Ready" : "Missing",
                    label: "Google Sign-In",
                    tint: AppConstants.googleSignInConfigured ? AppTheme.successGreen : AppTheme.dangerRed
                )
                .settingsPreviewStatCard()
            }

            HStack(spacing: 10) {
                SettingsPreviewStat(
                    icon: "creditcard.fill",
                    value: AppConstants.revenueCatAPIKey.isEmpty ? "Missing" : "Ready",
                    label: "RevenueCat",
                    tint: AppConstants.revenueCatAPIKey.isEmpty ? AppTheme.dangerRed : AppTheme.successGreen
                )
                .settingsPreviewStatCard()

                SettingsPreviewStat(
                    icon: "exclamationmark.bubble.fill",
                    value: LaunchTelemetry.shared.supportStatusLabel,
                    label: "Telemetry",
                    tint: AppConstants.sentryDSN.isEmpty ? AppTheme.subtleText : AppTheme.successGreen
                )
                .settingsPreviewStatCard()
            }

            HStack(spacing: 10) {
                SettingsPreviewStat(
                    icon: "doc.text.fill",
                    value: AppConstants.legalLinksConfigured ? "Ready" : "Missing",
                    label: "Legal Links",
                    tint: AppConstants.legalLinksConfigured ? AppTheme.successGreen : AppTheme.dangerRed
                )
                .settingsPreviewStatCard()

                Spacer(minLength: 0)
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder, glowOpacity: 0.05)
    }

    private var membershipHubLink: some View {
        settingsHubLink(
            title: languageStore.text(.membershipAccount),
            subtitle: languageStore.text(.membershipAccountSubtitle),
            icon: "person.crop.circle.badge.checkmark",
            accent: AppTheme.successGreen,
            stats: membershipPreviewStats
        ) {
            membershipSettingsPage
        }
    }

    private var accountQuickActionCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            RorkSectionHeader(
                title: languageStore.text(.accountQuickActions),
                icon: "person.crop.circle.fill",
                subtitle: "Signed in with \(authMethodLabel)"
            )

            signOutButton
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder, glowOpacity: 0.05)
    }

    private var supportHubLink: some View {
        settingsHubLink(
            title: languageStore.text(.supportCenter),
            subtitle: languageStore.text(.supportCenterSubtitle),
            icon: "bubble.left.and.exclamationmark.bubble.right.fill",
            accent: AppTheme.warningYellow,
            stats: [
                SettingsPreviewStat(
                    icon: feedbackType.icon,
                    value: feedbackType.rawValue,
                    label: "Draft Type",
                    tint: AppTheme.warningYellow
                ),
                SettingsPreviewStat(
                    icon: "text.alignleft",
                    value: "\(feedbackCharacterCount)",
                    label: "Draft Chars",
                    tint: feedbackCharacterCount >= 8 ? AppTheme.successGreen : AppTheme.subtleText
                )
            ]
        ) {
            supportSettingsPage
        }
    }

    private var aboutHubLink: some View {
        settingsHubLink(
            title: languageStore.text(.aboutPrivacy),
            subtitle: languageStore.text(.aboutPrivacySubtitle),
            icon: "lock.doc.fill",
            accent: AppTheme.neonPurple,
            stats: [
                SettingsPreviewStat(
                    icon: "internaldrive.fill",
                    value: "On Device",
                    label: "History",
                    tint: AppTheme.successGreen
                ),
                SettingsPreviewStat(
                    icon: "brain.head.profile.fill",
                    value: "Vision + Audio",
                    label: "Engine",
                    tint: AppTheme.neonPurple
                )
            ]
        ) {
            aboutSettingsPage
        }
    }

    private var membershipPreviewStats: [SettingsPreviewStat] {
        if subscriptionManager.isProUser {
            return [
                SettingsPreviewStat(
                    icon: "checkmark.seal.fill",
                    value: "Pro",
                    label: languageStore.text(.plan),
                    tint: AppTheme.successGreen
                ),
                SettingsPreviewStat(
                    icon: "infinity",
                    value: "Unlimited",
                    label: languageStore.text(.analysis),
                    tint: AppTheme.neonPurple
                )
            ]
        }

        return [
            SettingsPreviewStat(
                icon: AppConstants.cloudAnalysisEnabled ? "sparkles" : "cpu.fill",
                value: "\(subscriptionManager.freeUsesRemaining)",
                label: AppConstants.cloudAnalysisEnabled ? languageStore.text(.freeLeft) : "On Device",
                tint: subscriptionManager.freeUsesRemaining > 0 ? AppTheme.warningYellow : AppTheme.dangerRed
            ),
            SettingsPreviewStat(
                icon: "crown.fill",
                value: "$9.99",
                label: "Monthly",
                tint: AppTheme.neonPurple
            )
        ]
    }

    private var settingsFootnote: some View {
        Text("Developer-only launch diagnostics are hidden from production users.")
            .font(.caption2)
            .foregroundStyle(AppTheme.subtleText)
            .multilineTextAlignment(.center)
            .padding(.horizontal, 18)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity)
            .background(AppTheme.surfaceBg.opacity(0.30), in: RoundedRectangle(cornerRadius: 14))
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(AppTheme.softBorder, lineWidth: 1)
            )
    }

    private var workflowSettingsPage: some View {
        settingsDetailPage(
            title: languageStore.text(.workflowDefaults),
            subtitle: "Tune clip selection and analysis behavior for your footage.",
            icon: "waveform.and.magnifyingglass",
            accent: AppTheme.neonPurple
        ) {
            clipSettingsSection
            advancedSettingsSection
            dangerZone
        }
    }

    private var membershipSettingsPage: some View {
        settingsDetailPage(
            title: languageStore.text(.membershipAccount),
            subtitle: "See how you’re signed in and manage access.",
            icon: "person.crop.circle.badge.checkmark",
            accent: AppTheme.successGreen
        ) {
            accountSection
            subscriptionSection
            signOutButton
        }
    }

    private var supportSettingsPage: some View {
        settingsDetailPage(
            title: languageStore.text(.supportCenter),
            subtitle: "Feedback, bug reports, and setup help in one place.",
            icon: "bubble.left.and.exclamationmark.bubble.right.fill",
            accent: AppTheme.warningYellow
        ) {
            contactSuggestionsSection
            commonFAQSection
        }
    }

    private var aboutSettingsPage: some View {
        settingsDetailPage(
            title: languageStore.text(.aboutPrivacy),
            subtitle: "Core app details, storage behavior, and device-local history notes.",
            icon: "lock.doc.fill",
            accent: AppTheme.neonPurple
        ) {
            aboutSection
            legalLinksSection
            localLibrarySection
        }
    }

    private var legalLinksSection: some View {
        settingsCard(title: "Legal", icon: "doc.text.fill") {
            Text("Open the policies that should stay reachable from the shipped app and App Store listing.")
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
                .fixedSize(horizontal: false, vertical: true)

            legalLinkRow(
                title: "Privacy Policy",
                subtitle: "Review how account, billing, and device-local processing are described.",
                icon: "hand.raised.fill",
                url: AppConstants.privacyPolicyURL
            )

            legalLinkRow(
                title: "Terms of Service",
                subtitle: "Review product terms, acceptable use, and subscription language.",
                icon: "doc.text.magnifyingglass",
                url: AppConstants.termsOfServiceURL
            )
        }
    }

    private var localLibrarySection: some View {
        settingsCard(title: "On-Device Library", icon: "internaldrive.fill") {
            Text("Imported videos, the latest export for each project, and the project event timeline stay in the app’s local storage on this device. Nothing here is synced to a server by this feature.")
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 10) {
                aiFeatureTag("Source Video")
                aiFeatureTag("Latest Export")
                aiFeatureTag("Event Timeline")
                aiFeatureTag("Restore on Launch")
            }
        }
    }

    private func settingsHubLink<Destination: View>(
        title: String,
        subtitle: String,
        icon: String,
        accent: Color,
        stats: [SettingsPreviewStat],
        @ViewBuilder destination: @escaping () -> Destination
    ) -> some View {
        NavigationLink(destination: destination()) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 12) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 14, style: .continuous)
                            .fill(accent.opacity(0.14))
                            .frame(width: 42, height: 42)
                        Image(systemName: icon)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(accent)
                    }

                    VStack(alignment: .leading, spacing: 3) {
                        Text(title)
                            .font(.headline)
                            .foregroundStyle(.white)
                        Text(subtitle)
                            .font(.caption)
                            .foregroundStyle(AppTheme.subtleText)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    Spacer(minLength: 0)

                    Image(systemName: "chevron.right")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(AppTheme.subtleText)
                }

                if !stats.isEmpty {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 10) {
                            ForEach(stats) { stat in
                                RorkMetricChip(
                                    icon: stat.icon,
                                    value: stat.value,
                                    label: stat.label,
                                    tint: stat.tint
                                )
                                .frame(minWidth: 120)
                            }
                        }
                    }
                    .contentMargins(.horizontal, 0)
                }
            }
            .padding(16)
            .rorkCard(cornerRadius: 18, stroke: accent.opacity(0.18), glow: accent, glowOpacity: 0.05)
        }
        .buttonStyle(.plain)
    }

    private func settingsDetailPage<Content: View>(
        title: String,
        subtitle: String,
        icon: String,
        accent: Color,
        @ViewBuilder content: () -> Content
    ) -> some View {
        ZStack {
            AppTheme.darkBg.ignoresSafeArea()

            ScrollView {
                VStack(spacing: 20) {
                    settingsDetailHero(
                        title: title,
                        subtitle: subtitle,
                        icon: icon,
                        accent: accent
                    )

                    content()
                }
                .padding(.horizontal, 16)
                .padding(.top, 8)
                .padding(.bottom, 100)
            }
        }
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
    }

    private func settingsDetailHero(
        title: String,
        subtitle: String,
        icon: String,
        accent: Color
    ) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 14) {
                ZStack {
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .fill(accent.opacity(0.16))
                        .frame(width: 54, height: 54)
                    Image(systemName: icon)
                        .font(.title3.weight(.bold))
                        .foregroundStyle(accent)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.title3.weight(.bold))
                        .foregroundStyle(.white)
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 0)
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: accent.opacity(0.16), glow: accent, glowOpacity: 0.04)
    }

    private var aiWeightsSection: some View {
        settingsCard(title: "AI Analysis Weights", icon: "brain.head.profile.fill") {
            weightSlider(label: "Audio (Crowd Noise)", value: $viewModel.settings.audioWeight, color: .blue)
            weightSlider(label: "Motion Detection", value: $viewModel.settings.motionWeight, color: .orange)
            weightSlider(label: "Body Pose Analysis", value: $viewModel.settings.poseWeight, color: .green)
            weightSlider(label: "Scene Brightness", value: $viewModel.settings.sceneWeight, color: .yellow)

            let total = viewModel.settings.audioWeight + viewModel.settings.motionWeight + viewModel.settings.poseWeight + viewModel.settings.sceneWeight
            HStack {
                Text("Total Weight")
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
                Spacer()
                Text(String(format: "%.0f%%", total * 100))
                    .font(.caption.bold().monospacedDigit())
                    .foregroundStyle(abs(total - 1.0) < 0.05 ? AppTheme.successGreen : AppTheme.warningYellow)
            }
            .padding(.top, 4)
        }
    }

    private var settingsSummaryCard: some View {
        let weightsTotal = viewModel.settings.audioWeight
            + viewModel.settings.motionWeight
            + viewModel.settings.poseWeight
            + viewModel.settings.sceneWeight
        let normalized = abs(weightsTotal - 1.0) < 0.05

        return VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "sparkles")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.neonPurple)
                Text("Current Detection Profile")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                Spacer()
            }

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: "scope",
                    value: "\(Int(viewModel.settings.confidenceThreshold * 100))%",
                    label: "Threshold"
                )
                RorkMetricChip(
                    icon: "gauge.with.dots.needle.67percent",
                    value: "\(Int(viewModel.settings.framesSampledPerSecond)) fps",
                    label: "Sampling",
                    tint: AppTheme.warningYellow
                )
            }

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: normalized ? "checkmark.seal.fill" : "exclamationmark.triangle.fill",
                    value: normalized ? "Balanced" : "Adjust",
                    label: "Weights",
                    tint: normalized ? AppTheme.successGreen : AppTheme.warningYellow
                )
                RorkMetricChip(
                    icon: viewModel.settings.preferKeepUncertain ? "checkmark.circle.fill" : "xmark.circle.fill",
                    value: viewModel.settings.preferKeepUncertain ? "On" : "Off",
                    label: "Keep Uncertain",
                    tint: viewModel.settings.preferKeepUncertain ? AppTheme.successGreen : AppTheme.dangerRed
                )
            }

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: "clock.badge.checkmark.fill",
                    value: formattedTargetDuration(viewModel.settings.targetHighlightDuration),
                    label: "Target Reel",
                    tint: AppTheme.warningYellow
                )
                Spacer()
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder, glowOpacity: 0.06)
    }

    private var clipSettingsSection: some View {
        settingsCard(title: "Clip & Reel Duration", icon: "scissors") {
            VStack(spacing: 4) {
                HStack {
                    Text("Minimum")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text(String(format: "%.1f sec", viewModel.settings.minClipDuration))
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.minClipDuration, in: 1.0...5.0, step: 0.5)
                    .tint(AppTheme.accentPurple)
                Text("Shortest clip the AI will keep")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }

            Divider().overlay(AppTheme.accentPurple.opacity(0.2))

            VStack(spacing: 4) {
                HStack {
                    Text("Maximum")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text(String(format: "%.0f sec", viewModel.settings.maxClipDuration))
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.maxClipDuration, in: 5.0...30.0, step: 1.0)
                    .tint(AppTheme.accentPurple)
                Text("Longest clip the AI will keep")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }

            Divider().overlay(AppTheme.accentPurple.opacity(0.2))

            VStack(spacing: 4) {
                HStack {
                    Text("Target Highlight")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text(formattedTargetDuration(viewModel.settings.targetHighlightDuration))
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.targetHighlightDuration, in: 15.0...180.0, step: 5.0)
                    .tint(AppTheme.accentPurple)
                Text("Caps the default auto-kept reel length after analysis. You can still keep more clips manually in Review.")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }
        }
    }

    private var advancedSettingsSection: some View {
        let weightsTotal = viewModel.settings.audioWeight
            + viewModel.settings.motionWeight
            + viewModel.settings.poseWeight
            + viewModel.settings.sceneWeight
        let weightsStatus = abs(weightsTotal - 1.0) < 0.05 ? "Balanced" : "Custom"

        return VStack(alignment: .leading, spacing: 12) {
            DisclosureGroup(isExpanded: $showingAdvancedSettings) {
                VStack(spacing: 16) {
                    advancedConfidenceSection
                    advancedDetectionBehavior
                    performanceSection
                    aiWeightsSection
                    settingsSummaryCard
                }
                .padding(.top, 8)
            } label: {
                VStack(alignment: .leading, spacing: 10) {
                    RorkSectionHeader(
                        title: "Advanced Settings",
                        icon: "gearshape.2.fill",
                        subtitle: "For fine-tuning — most users won't need to change these"
                    )

                    if !showingAdvancedSettings {
                        HStack(spacing: 10) {
                            RorkMetricChip(
                                icon: "scope",
                                value: "\(Int(viewModel.settings.confidenceThreshold * 100))%",
                                label: "Threshold"
                            )
                            RorkMetricChip(
                                icon: "gauge.with.dots.needle.67percent",
                                value: "\(Int(viewModel.settings.framesSampledPerSecond)) fps",
                                label: "Sampling",
                                tint: AppTheme.warningYellow
                            )
                            RorkMetricChip(
                                icon: "brain.head.profile.fill",
                                value: weightsStatus,
                                label: "Weights",
                                tint: weightsStatus == "Balanced" ? AppTheme.successGreen : AppTheme.neonPurple
                            )
                        }
                    }
                }
            }
        }
        .tint(AppTheme.neonPurple)
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder, glowOpacity: 0.06)
    }

    private var advancedConfidenceSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "scope")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.neonPurple)
                Text("Confidence Threshold")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                Spacer()
            }

            VStack(spacing: 4) {
                HStack {
                    Text("Threshold")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text("\(Int(viewModel.settings.confidenceThreshold * 100))%")
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.confidenceThreshold, in: 0.1...0.9, step: 0.05)
                    .tint(AppTheme.accentPurple)
                Text("Lower = more clips found (may include false positives)")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }
        }
        .padding(14)
        .rorkCard(
            cornerRadius: 14,
            fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.55)),
            stroke: AppTheme.softBorder,
            glowOpacity: 0.03
        )
    }

    private var advancedDetectionBehavior: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "slider.horizontal.3")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.neonPurple)
                Text("Detection Behavior")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                Spacer()
            }

            VStack(spacing: 4) {
                HStack {
                    Text("Clip Padding")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text(String(format: "%.1fs", viewModel.settings.clipPadding))
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.clipPadding, in: 0.5...3.0, step: 0.5)
                    .tint(AppTheme.accentPurple)
                Text("Adds extra lead-in / follow-through around detected moments")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }

            Divider().overlay(AppTheme.accentPurple.opacity(0.2))

            Toggle(isOn: $viewModel.settings.preferKeepUncertain) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Keep Uncertain Clips")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Text("When unsure, keep clips for manual review")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                }
            }
            .tint(AppTheme.accentPurple)
        }
        .padding(14)
        .rorkCard(
            cornerRadius: 14,
            fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.55)),
            stroke: AppTheme.softBorder,
            glowOpacity: 0.03
        )
    }

    private var performanceSection: some View {
        settingsCard(title: "Performance", icon: "gauge.with.dots.needle.67percent") {
            VStack(spacing: 4) {
                HStack {
                    Text("Frames Per Second")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text(String(format: "%.0f fps", viewModel.settings.framesSampledPerSecond))
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.framesSampledPerSecond, in: 1.0...10.0, step: 1.0)
                    .tint(AppTheme.accentPurple)
                Text("Higher = more accurate but slower analysis")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }
        }
    }

    private var aboutSection: some View {
        settingsCard(title: "About", icon: "info.circle.fill") {
            VStack(spacing: 12) {
                HStack {
                    Text("Hoops Clips")
                        .font(.headline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text("v1.0")
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.subtleText)
                }

                Text("Smart basketball highlight detection that helps you find, review, export, and save your best clips directly on your iPhone.")
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
                    .fixedSize(horizontal: false, vertical: true)

                HStack(spacing: 16) {
                    aiFeatureTag("Smart Clips")
                    aiFeatureTag("Private")
                    aiFeatureTag("Fast Export")
                    aiFeatureTag("Share Ready")
                }
            }
        }
    }

    private var contactSuggestionsSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            RorkSectionHeader(
                title: "Contact & Suggestions",
                icon: "paperplane.fill",
                subtitle: "Send feedback directly from the app to the team"
            )

            if let feedbackBanner {
                HStack(spacing: 10) {
                    Image(systemName: feedbackBanner.icon)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(feedbackBanner.tint)
                    Text(feedbackBanner.message)
                        .font(.caption)
                        .foregroundStyle(.white)
                    Spacer()
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .rorkCard(
                    cornerRadius: 12,
                    fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.55)),
                    stroke: feedbackBanner.tint.opacity(0.22),
                    glow: feedbackBanner.tint,
                    glowOpacity: 0.05
                )
            }

            VStack(alignment: .leading, spacing: 10) {
                Text("Type")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.subtleText)

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(FeedbackType.allCases) { type in
                            Button {
                                withAnimation(.snappy) { feedbackType = type }
                            } label: {
                                HStack(spacing: 8) {
                                    Image(systemName: type.icon)
                                        .font(.caption.weight(.semibold))
                                    Text(type.rawValue)
                                        .font(.caption.weight(.medium))
                                }
                                .foregroundStyle(feedbackType == type ? .white : AppTheme.subtleText)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 8)
                                .background(
                                    feedbackType == type ? AppTheme.accentPurple : AppTheme.cardBg,
                                    in: .capsule
                                )
                                .overlay(
                                    Capsule()
                                        .stroke(
                                            feedbackType == type ? AppTheme.neonPurple : Color.clear,
                                            lineWidth: 1.5
                                        )
                                )
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
                .contentMargins(.horizontal, 0)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Email (optional)")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.subtleText)

                TextField("you@example.com", text: $contactEmail)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.emailAddress)
                    .autocorrectionDisabled(true)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 12)
                    .background(AppTheme.surfaceBg.opacity(0.55), in: .rect(cornerRadius: 12))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(AppTheme.softBorder, lineWidth: 1)
                    )
            }

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Message")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(AppTheme.subtleText)
                    Spacer()
                    Text("\(feedbackCharacterCount)/1200")
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(feedbackCharacterCount > 1200 ? AppTheme.dangerRed : AppTheme.subtleText)
                }

                ZStack(alignment: .topLeading) {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(AppTheme.surfaceBg.opacity(0.55))
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(AppTheme.softBorder, lineWidth: 1)
                        )

                    if feedbackMessage.isEmpty {
                        Text("Tell us what to improve, report a bug, or ask a question...")
                            .font(.subheadline)
                            .foregroundStyle(AppTheme.subtleText)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 14)
                            .allowsHitTesting(false)
                    }

                    TextEditor(text: $feedbackMessage)
                        .scrollContentBackground(.hidden)
                        .foregroundStyle(.white)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 8)
                        .frame(minHeight: 120)
                        .background(Color.clear)
                }
                .frame(minHeight: 120)
            }

            HStack(spacing: 10) {
                Button {
                    feedbackMessage = ""
                    feedbackBanner = nil
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "eraser.fill")
                        Text("Clear")
                    }
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.subtleText)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 10)
                    .background(AppTheme.surfaceBg.opacity(0.35), in: .capsule)
                }
                .buttonStyle(.plain)

                Spacer()

                Button {
                    Task { await submitFeedback() }
                } label: {
                    HStack(spacing: 8) {
                        if isSubmittingFeedback {
                            ProgressView()
                                .tint(.white)
                                .controlSize(.small)
                        } else {
                            Image(systemName: "paperplane.fill")
                        }
                        Text(isSubmittingFeedback ? "Sending..." : "Send")
                            .font(.subheadline.bold())
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 11)
                    .background(AppTheme.purpleGradient, in: .capsule)
                    .overlay(
                        Capsule()
                            .stroke(AppTheme.neonPurple.opacity(0.28), lineWidth: 1)
                    )
                }
                .buttonStyle(.plain)
                .disabled(isSubmittingFeedback || !canSubmitFeedback)
                .opacity((isSubmittingFeedback || !canSubmitFeedback) ? 0.55 : 1.0)
            }

            Text("Submitted securely over HTTPS via Formspree. Avoid sending passwords or private account data.")
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.06)
    }

    private var commonFAQSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            RorkSectionHeader(
                title: "Common FAQ",
                icon: "questionmark.circle.fill",
                subtitle: "Quick answers for setup, exports, and detection tuning"
            )

            VStack(spacing: 10) {
                ForEach(Self.commonFAQItems) { item in
                    DisclosureGroup(isExpanded: faqBinding(for: item.id)) {
                        Text(item.answer)
                            .font(.caption)
                            .foregroundStyle(AppTheme.subtleText)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.top, 4)
                    } label: {
                        HStack(spacing: 10) {
                            ZStack {
                                RoundedRectangle(cornerRadius: 9, style: .continuous)
                                    .fill(AppTheme.accentPurple.opacity(0.14))
                                    .frame(width: 28, height: 28)
                                Image(systemName: item.icon)
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(AppTheme.neonPurple)
                            }
                            Text(item.question)
                                .font(.subheadline.weight(.medium))
                                .foregroundStyle(.white)
                            Spacer()
                        }
                    }
                    .tint(AppTheme.neonPurple)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 10)
                    .rorkCard(
                        cornerRadius: 12,
                        fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.50)),
                        stroke: AppTheme.softBorder,
                        glowOpacity: 0.03
                    )
                }
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.05)
    }

    private var accountSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            RorkSectionHeader(
                title: "Account",
                icon: "person.crop.circle.fill",
                subtitle: "Your sign-in details"
            )

            HStack(spacing: 14) {
                ZStack {
                    Circle()
                        .fill(AppTheme.accentPurple.opacity(0.2))
                        .frame(width: 48, height: 48)
                    Image(systemName: authMethodIcon)
                        .font(.title3.weight(.semibold))
                        .foregroundStyle(AppTheme.neonPurple)
                }

                VStack(alignment: .leading, spacing: 4) {
                    if let name = authService.currentUser?.displayName, !name.isEmpty {
                        Text(name)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.white)
                    }
                    if let email = authService.currentUser?.email {
                        Text(email)
                            .font(.caption)
                            .foregroundStyle(AppTheme.subtleText)
                    }
                    Text("Signed in with \(authMethodLabel)")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                }

                Spacer()
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder, glowOpacity: 0.06)
    }

    private var authMethodIcon: String {
        switch authService.currentUser?.authMethod {
        case .apple: return "apple.logo"
        case .google: return "g.circle.fill"
        case .email: return "envelope.fill"
        case .phone: return "phone.fill"
        case .anonymous: return "person.fill.questionmark"
        case nil: return "person.fill"
        }
    }

    private var authMethodLabel: String {
        switch authService.currentUser?.authMethod {
        case .apple: return "Apple"
        case .google: return "Google"
        case .email: return "Email"
        case .phone: return "Phone"
        case .anonymous: return "Guest"
        case nil: return "Unknown"
        }
    }

    private var membershipRequiresAccountSignIn: Bool {
        authService.currentUser?.authMethod == .anonymous
    }

    private var subscriptionSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            RorkSectionHeader(
                title: "Subscription",
                icon: "crown.fill",
                subtitle: subscriptionManager.isProUser ? "You have unlimited access" : (membershipRequiresAccountSignIn ? "Sign in required" : "Free tier")
            )

            if subscriptionManager.isProUser {
                HStack(spacing: 12) {
                    Image(systemName: "checkmark.seal.fill")
                        .font(.title2)
                        .foregroundStyle(AppTheme.successGreen)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Pro Member")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.white)
                        Text("Unlimited AI analyses & exports")
                            .font(.caption)
                            .foregroundStyle(AppTheme.subtleText)
                    }
                    Spacer()
                }
            } else {
                HStack(spacing: 10) {
                    RorkMetricChip(
                        icon: "sparkles",
                        value: "\(subscriptionManager.freeUsesRemaining)",
                        label: "Free Left",
                        tint: subscriptionManager.freeUsesRemaining > 0 ? AppTheme.warningYellow : AppTheme.dangerRed
                    )
                    RorkMetricChip(
                        icon: "crown.fill",
                        value: "$9.99",
                        label: "Per Month",
                        tint: AppTheme.neonPurple
                    )
                }

                Button {
                    showingPaywall = true
                } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "crown.fill")
                            .font(.subheadline)
                        Text(membershipRequiresAccountSignIn ? "Sign In to Upgrade" : "Upgrade to Pro")
                            .font(.subheadline.bold())
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.caption.bold())
                    }
                    .foregroundStyle(.white)
                    .padding(14)
                    .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 14))
                    .overlay(
                        RoundedRectangle(cornerRadius: 14)
                            .stroke(AppTheme.neonPurple.opacity(0.3), lineWidth: 1)
                    )
                }
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder, glowOpacity: 0.06)
    }

    private var signOutButton: some View {
        Button {
            authService.signOut()
        } label: {
            HStack {
                Image(systemName: "rectangle.portrait.and.arrow.right")
                Text("Sign Out")
                    .fontWeight(.semibold)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption.bold())
            }
            .font(.subheadline)
            .foregroundStyle(AppTheme.dangerRed)
            .frame(maxWidth: .infinity)
            .padding(14)
            .background(AppTheme.dangerRed.opacity(0.10), in: .rect(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(AppTheme.dangerRed.opacity(0.28), lineWidth: 1)
            )
        }
    }

    private func aiFeatureTag(_ text: String) -> some View {
        Text(text)
            .font(.caption2)
            .foregroundStyle(AppTheme.neonPurple)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(AppTheme.accentPurple.opacity(0.15), in: .capsule)
    }

    private var dangerZone: some View {
        Button {
            showingResetAlert = true
        } label: {
            VStack(spacing: 6) {
                HStack {
                    Image(systemName: "arrow.counterclockwise")
                    Text("Reset to Defaults")
                        .fontWeight(.semibold)
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption.bold())
                }
                .font(.subheadline)
                .foregroundStyle(AppTheme.dangerRed)

                HStack {
                    Text(languageStore.text(.resetDefaultsDescription))
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                    Spacer()
                }
            }
            .frame(maxWidth: .infinity)
            .padding(14)
            .background(AppTheme.dangerRed.opacity(0.08), in: .rect(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(AppTheme.dangerRed.opacity(0.18), lineWidth: 1)
            )
        }
    }

    private func settingsCard(title: String, icon: String, @ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            RorkSectionHeader(title: title, icon: icon)

            VStack(spacing: 12) {
                content()
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.accentPurple.opacity(0.15), glowOpacity: 0.05)
    }

    @ViewBuilder
    private func legalLinkRow(title: String, subtitle: String, icon: String, url: URL?) -> some View {
        if let url {
            Link(destination: url) {
                HStack(spacing: 12) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .fill(AppTheme.accentPurple.opacity(0.14))
                            .frame(width: 40, height: 40)
                        Image(systemName: icon)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(AppTheme.neonPurple)
                    }

                    VStack(alignment: .leading, spacing: 3) {
                        Text(title)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.white)
                        Text(subtitle)
                            .font(.caption2)
                            .foregroundStyle(AppTheme.subtleText)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    Spacer(minLength: 0)

                    Image(systemName: "arrow.up.right.square")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(AppTheme.neonPurple)
                }
                .padding(12)
                .background(AppTheme.surfaceBg.opacity(0.42), in: .rect(cornerRadius: 14))
                .overlay(
                    RoundedRectangle(cornerRadius: 14)
                        .stroke(AppTheme.softBorder, lineWidth: 1)
                )
            }
        } else {
            HStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .fill(AppTheme.dangerRed.opacity(0.12))
                        .frame(width: 40, height: 40)
                    Image(systemName: icon)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(AppTheme.dangerRed)
                }

                VStack(alignment: .leading, spacing: 3) {
                    Text(title)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                    Text("Missing release URL. Populate the production config before App Store submission.")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 0)
            }
            .padding(12)
            .background(AppTheme.surfaceBg.opacity(0.42), in: .rect(cornerRadius: 14))
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(AppTheme.dangerRed.opacity(0.2), lineWidth: 1)
            )
        }
    }

    private func weightSlider(label: String, value: Binding<Double>, color: Color) -> some View {
        VStack(spacing: 4) {
            HStack {
                Circle()
                    .fill(color)
                    .frame(width: 8, height: 8)
                Text(label)
                    .font(.subheadline)
                    .foregroundStyle(.white)
                Spacer()
                Text("\(Int(value.wrappedValue * 100))%")
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(color)
            }
            Slider(value: value, in: 0...1.0, step: 0.05)
                .tint(color)
        }
    }

    private var feedbackCharacterCount: Int {
        feedbackMessage.trimmingCharacters(in: .whitespacesAndNewlines).count
    }

    private var canSubmitFeedback: Bool {
        let trimmed = feedbackMessage.trimmingCharacters(in: .whitespacesAndNewlines)
        guard (8...1200).contains(trimmed.count) else { return false }
        return isEmailValidOrEmpty(contactEmail)
    }

    private func faqBinding(for id: String) -> Binding<Bool> {
        Binding {
            expandedFAQIDs.contains(id)
        } set: { isExpanded in
            if isExpanded {
                expandedFAQIDs.insert(id)
            } else {
                expandedFAQIDs.remove(id)
            }
        }
    }

    @MainActor
    private func submitFeedback() async {
        guard canSubmitFeedback else {
            feedbackBanner = FeedbackBanner(
                message: "Please add a message (8-1200 chars) and check the email format if provided.",
                icon: "exclamationmark.triangle.fill",
                tint: AppTheme.dangerRed
            )
            return
        }

        guard let endpoint = URL(string: "https://formspree.io/f/xlgwzrdk") else {
            feedbackBanner = FeedbackBanner(
                message: "Feedback form is not configured correctly.",
                icon: "xmark.octagon.fill",
                tint: AppTheme.dangerRed
            )
            return
        }

        isSubmittingFeedback = true
        feedbackBanner = nil
        defer { isSubmittingFeedback = false }

        let trimmedMessage = String(
            feedbackMessage
                .trimmingCharacters(in: .whitespacesAndNewlines)
                .prefix(1200)
        )
        let trimmedEmail = contactEmail.trimmingCharacters(in: .whitespacesAndNewlines)
        let optionalEmail = trimmedEmail.isEmpty ? nil : trimmedEmail

        let payload = FormspreePayload(
            category: feedbackType.rawValue,
            email: optionalEmail,
            message: trimmedMessage,
            source: "Hoops Clips Settings",
            appVersion: "v1.0",
            exportTheme: viewModel.selectedTheme.rawValue,
            exportQuality: viewModel.selectedQuality.rawValue,
            exportFormat: viewModel.selectedFormat.rawValue
        )

        do {
            var request = URLRequest(url: endpoint)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("application/json", forHTTPHeaderField: "Accept")
            request.httpBody = try JSONEncoder().encode(payload)

            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw URLError(.badServerResponse)
            }

            guard (200..<300).contains(http.statusCode) else {
                let envelope = try? JSONDecoder().decode(FormspreeErrorEnvelope.self, from: data)
                let serverMessage = envelope?.errors?.compactMap(\.message).first
                feedbackBanner = FeedbackBanner(
                    message: serverMessage ?? "Couldn’t send feedback right now. Please try again.",
                    icon: "wifi.exclamationmark",
                    tint: AppTheme.dangerRed
                )
                return
            }

            feedbackBanner = FeedbackBanner(
                message: "Thanks. Your \(feedbackType.rawValue.lowercased()) was sent.",
                icon: "checkmark.circle.fill",
                tint: AppTheme.successGreen
            )
            feedbackMessage = ""
        } catch {
            feedbackBanner = FeedbackBanner(
                message: "Network error while sending feedback. Check connection and try again.",
                icon: "wifi.exclamationmark",
                tint: AppTheme.dangerRed
            )
        }
    }

    private func isEmailValidOrEmpty(_ value: String) -> Bool {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return true }
        guard trimmed.count <= 254 else { return false }
        let parts = trimmed.split(separator: "@")
        guard parts.count == 2 else { return false }
        let domain = parts[1]
        return !parts[0].isEmpty && domain.contains(".") && !domain.hasPrefix(".") && !domain.hasSuffix(".")
    }

    private func formattedTargetDuration(_ duration: Double) -> String {
        if duration < 60 {
            return String(format: "%.0f sec", duration)
        }

        let minutes = Int(duration) / 60
        let seconds = Int(duration) % 60
        if seconds == 0 {
            return "\(minutes) min"
        }
        return "\(minutes)m \(seconds)s"
    }
}

private extension SettingsView.SettingsPreviewStat {
    @ViewBuilder
    func settingsPreviewStatCard() -> some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(tint)
            Text(value)
                .font(.subheadline.weight(.bold))
                .foregroundStyle(.white)
            Text(label)
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .rorkCard(cornerRadius: 14, fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.72)), stroke: AppTheme.softBorder, glowOpacity: 0.04)
    }
}
