import SwiftUI
import Foundation
import UIKit

struct SettingsView: View {
    @Bindable var viewModel: HighlightsViewModel
    @Bindable var authService: AuthService
    @Bindable var subscriptionManager: SubscriptionManager
    @Environment(AppLanguageStore.self) private var languageStore
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @State private var showingResetConfirmation = false
    @State private var showingSignOutConfirmation = false
    @State private var showingPaywall = false
    @State private var showingAdvancedSettings = false
    @State private var feedbackType: FeedbackType = .suggestion
    @State private var contactEmail = ""
    @State private var feedbackMessage = ""
    @State private var isSubmittingFeedback = false
    @State private var feedbackBanner: FeedbackBanner?
    @State private var expandedFAQIDs: Set<String> = []
    @State private var smokeProofCopied = false
    @State private var uploadStateProofCopied = false
    @State private var isSendingSmokeProof = false
    @State private var smokeProofSendSucceeded = false
    @State private var smokeProofSendFailed = false

    private enum FeedbackType: String, CaseIterable, Identifiable {
        case suggestion = "Suggestion"
        case bug = "Bug Report"
        case question = "Question"

        var id: String { rawValue }

        var textKey: AppTextKey {
            switch self {
            case .suggestion: return .settingsFeedbackSuggestion
            case .bug: return .settingsFeedbackBug
            case .question: return .settingsFeedbackQuestion
            }
        }

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
        let stabilitySummary: String?
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

    private var commonFAQItems: [FAQItem] {
        [
            FAQItem(
                id: "no-clips",
                question: languageStore.text(.settingsFAQNoClipsQuestion),
                answer: languageStore.text(.settingsFAQNoClipsAnswer),
                icon: "film.badge.questionmark"
            ),
            FAQItem(
                id: "weights",
                question: languageStore.text(.settingsFAQWeightsQuestion),
                answer: languageStore.text(.settingsFAQWeightsAnswer),
                icon: "slider.horizontal.3"
            ),
            FAQItem(
                id: "export-format",
                question: languageStore.text(.settingsFAQExportFormatQuestion),
                answer: languageStore.text(.settingsFAQExportFormatAnswer),
                icon: "doc.badge.gearshape"
            ),
            FAQItem(
                id: "quick-share",
                question: languageStore.text(.settingsFAQQuickShareQuestion),
                answer: languageStore.text(.settingsFAQQuickShareAnswer),
                icon: "square.and.arrow.up.fill"
            )
        ]
    }

    var body: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.16, courtOpacity: 0.07)

                ScrollView {
                    VStack(spacing: 16) {
                        AnyView(accountPlanCard)
                        AnyView(membershipHubLink)
                        AnyView(languageSettingsCard)
                        AnyView(workflowHubLink)
                        AnyView(supportHubLink)
                        if shouldShowSmokeProofCard {
                            AnyView(smokeProofCard)
                        }
                        AnyView(aboutHubLink)
                        #if DEBUG
                        AnyView(runtimeStatusCard)
                        AnyView(settingsFootnote)
                        #endif
                        AnyView(signOutFooterCard)
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 6)
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
            .confirmationDialog(
                languageStore.text(.settingsResetTitle),
                isPresented: $showingResetConfirmation,
                titleVisibility: .visible
            ) {
                Button(languageStore.text(.settingsReset), role: .destructive) {
                    viewModel.settings = AnalysisSettings()
                }
                Button(languageStore.text(.settingsCancel), role: .cancel) { }
            } message: {
                Text(languageStore.text(.settingsResetMessage))
            }
            .confirmationDialog(
                languageStore.text(.settingsSignOutConfirmationTitle),
                isPresented: $showingSignOutConfirmation,
                titleVisibility: .visible
            ) {
                Button(languageStore.text(.settingsSignOut), role: .destructive) {
                    authService.signOut()
                }
                Button(languageStore.text(.settingsCancel), role: .cancel) { }
            } message: {
                Text(languageStore.text(.settingsSignOutConfirmationMessage))
            }
        }
    }

    private var accountPlanCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .center, spacing: 14) {
                ZStack {
                    Circle()
                        .fill(accountAnalysisPathTint.opacity(0.18))
                        .frame(width: 52, height: 52)
                    Image(systemName: authMethodIcon)
                        .font(.title3.weight(.semibold))
                        .foregroundStyle(accountAnalysisPathTint)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text(languageStore.text(.settingsAccountPlan))
                        .font(.headline.weight(.semibold))
                        .foregroundStyle(.white)
                    Text(accountDisplayName)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(.white.opacity(0.88))
                        .lineLimit(2)
                        .minimumScaleFactor(0.85)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(accountDetailLine)
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(2)
                        .minimumScaleFactor(0.86)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .layoutPriority(1)

                Spacer(minLength: 0)
            }

            Divider().overlay(AppTheme.softBorder)

            LazyVGrid(columns: accountPlanStatGridColumns, alignment: .leading, spacing: 10) {
                settingsInlineStat(
                    icon: subscriptionManager.isProUser ? "checkmark.seal.fill" : "sparkles",
                    value: subscriptionManager.isProUser ? "Pro" : "\(subscriptionManager.freeUsesRemaining)",
                    label: subscriptionManager.isProUser ? languageStore.text(.plan) : languageStore.text(.freeLeft),
                    tint: subscriptionManager.isProUser ? AppTheme.successGreen : AppTheme.warningYellow
                )

                settingsInlineStat(
                    icon: accountAnalysisPathIcon,
                    value: accountAnalysisPathValue,
                    label: languageStore.text(.analysis),
                    tint: accountAnalysisPathTint
                )
            }
        }
        .padding(16)
        .rorkCard(
            cornerRadius: 20,
            fill: AppTheme.accentCardFill(accountAnalysisPathTint, opacity: 0.13),
            stroke: accountAnalysisPathTint.opacity(0.18),
            glow: accountAnalysisPathTint,
            glowOpacity: 0.04
        )
    }

    private var languageSettingsCard: some View {
        VStack(alignment: .leading, spacing: 10) {
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
                        RoundedRectangle(cornerRadius: 11, style: .continuous)
                            .fill(AppTheme.rimOrange.opacity(0.16))
                            .frame(width: 38, height: 38)
                        Image(systemName: "character.bubble.fill")
                            .foregroundStyle(AppTheme.rimOrange)
                    }

                    VStack(alignment: .leading, spacing: 3) {
                        Text(languageStore.text(.languageCardTitle))
                            .font(.headline.weight(.semibold))
                            .foregroundStyle(.white)
                        Text("\(languageStore.text(.languageCurrent)): \(languageStore.selectedLanguage.nativeName)")
                            .font(.caption)
                            .foregroundStyle(AppTheme.subtleText)
                            .lineLimit(2)
                            .minimumScaleFactor(0.86)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .layoutPriority(1)

                    Spacer()

                    Image(systemName: "chevron.up.chevron.down")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(AppTheme.subtleText)
                }
            }

            Text(languageStore.text(.languageRestartNote))
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(16)
        .rorkCard(
            cornerRadius: 18,
            fill: AppTheme.accentCardFill(AppTheme.rimOrange, opacity: 0.12),
            stroke: AppTheme.rimOrange.opacity(0.18),
            glow: AppTheme.rimOrange,
            glowOpacity: 0.04
        )
    }

    private var workflowHubLink: some View {
        settingsHubLink(
            title: languageStore.text(.workflowDefaults),
            subtitle: languageStore.text(.workflowDefaultsSubtitle),
            icon: "waveform.and.magnifyingglass",
            accent: AppTheme.courtBlue,
            stats: [
                SettingsPreviewStat(
                    icon: "scope",
                    value: "\(Int(viewModel.settings.confidenceThreshold * 100))%",
                    label: languageStore.text(.settingsThreshold),
                    tint: AppTheme.courtBlue
                ),
                SettingsPreviewStat(
                    icon: "clock.badge.checkmark.fill",
                    value: formattedTargetDuration(viewModel.settings.targetHighlightDuration),
                    label: languageStore.text(.settingsTarget),
                    tint: AppTheme.warningYellow
                ),
                SettingsPreviewStat(
                    icon: "gauge.with.dots.needle.67percent",
                    value: formattedFrameRate(viewModel.settings.framesSampledPerSecond),
                    label: languageStore.text(.settingsSampling),
                    tint: AppTheme.courtBlue
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
                    icon: "person.text.rectangle.fill",
                    value: AppConstants.emailPasswordAuthConfigured ? "Ready" : "Missing",
                    label: "Email Auth",
                    tint: AppConstants.emailPasswordAuthConfigured ? AppTheme.successGreen : AppTheme.dangerRed
                )
                .settingsPreviewStatCard()
            }

            HStack(spacing: 10) {
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
            title: languageStore.text(.settingsSubscription),
            subtitle: languageStore.text(.settingsMembershipDetailSubtitle),
            icon: "person.crop.circle.badge.checkmark",
            accent: AppTheme.rimOrange,
            stats: membershipPreviewStats
        ) {
            membershipSettingsPage
        }
    }

    private var supportHubLink: some View {
        settingsHubLink(
            title: languageStore.text(.supportCenter),
            subtitle: languageStore.text(.supportCenterSubtitle),
            icon: "bubble.left.and.exclamationmark.bubble.right.fill",
            accent: AppTheme.rimOrange,
            stats: [
                SettingsPreviewStat(
                    icon: feedbackType.icon,
                    value: languageStore.text(feedbackType.textKey),
                    label: languageStore.text(.settingsDraftType),
                    tint: AppTheme.rimOrange
                ),
                SettingsPreviewStat(
                    icon: "text.alignleft",
                    value: "\(feedbackCharacterCount)",
                    label: languageStore.text(.settingsDraftChars),
                    tint: feedbackCharacterCount >= 8 ? AppTheme.successGreen : AppTheme.subtleText
                )
            ]
        ) {
            supportSettingsPage
        }
    }

    private var shouldShowSmokeProofCard: Bool {
        AppConstants.environmentName != "production" || AppConstants.cloudLaunchMode == .internalOnly
    }

    private var smokeProofCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            RorkSectionHeader(
                title: languageStore.text(.settingsSmokeProofTitle),
                icon: "doc.on.clipboard.fill",
                subtitle: languageStore.text(.settingsSmokeProofSubtitle)
            )

            HStack(spacing: 10) {
                SettingsPreviewStat(
                    icon: "number.circle.fill",
                    value: appBuildNumber,
                    label: languageStore.text(.settingsSmokeProofBuild),
                    tint: AppTheme.warningYellow
                )
                .settingsPreviewStatCard()

                SettingsPreviewStat(
                    icon: "icloud.fill",
                    value: AppConstants.cloudLaunchStatusLabel,
                    label: languageStore.text(.settingsSmokeProofCloud),
                    tint: AppConstants.cloudAnalysisEnabled ? AppTheme.successGreen : AppTheme.subtleText
                )
                .settingsPreviewStatCard()
            }

            HStack(spacing: 10) {
                SettingsPreviewStat(
                    icon: "folder.fill",
                    value: viewModel.currentProjectID == nil ? "None" : "Ready",
                    label: languageStore.text(.settingsSmokeProofProject),
                    tint: viewModel.currentProjectID == nil ? AppTheme.subtleText : AppTheme.successGreen
                )
                .settingsPreviewStatCard()

                SettingsPreviewStat(
                    icon: "scope",
                    value: viewModel.cloudAnalysisJobID == nil ? "None" : "Job",
                    label: languageStore.text(.settingsSmokeProofAnalysis),
                    tint: viewModel.cloudAnalysisJobID == nil ? AppTheme.subtleText : AppTheme.courtBlue
                )
                .settingsPreviewStatCard()
            }

            settingsBackgroundUploadStatusRow
            copyUploadStateProofButton

            Button {
                copySmokeProof()
            } label: {
                HStack(spacing: 10) {
                    Image(systemName: smokeProofCopied ? "checkmark.circle.fill" : "doc.on.doc.fill")
                    Text(languageStore.text(smokeProofCopied ? .settingsSmokeProofCopied : .settingsSmokeProofCopy))
                        .font(.subheadline.weight(.bold))
                    Spacer(minLength: 0)
                }
                .foregroundStyle(smokeProofCopied ? .black : .white)
                .padding(.horizontal, 14)
                .padding(.vertical, 13)
                .background(
                    smokeProofCopied ? AppTheme.successGreen : AppTheme.accentPurple.opacity(0.72),
                    in: .rect(cornerRadius: 15)
                )
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("settings.smokeProof.copyButton")
            .accessibilityHint(languageStore.text(.settingsSmokeProofPrivacy))

            Button {
                sendSmokeProof()
            } label: {
                HStack(spacing: 10) {
                    Image(systemName: smokeProofSendIcon)
                    Text(smokeProofSendLabel)
                        .font(.subheadline.weight(.bold))
                    Spacer(minLength: 0)
                }
                .foregroundStyle(smokeProofSendSucceeded ? .black : .white)
                .padding(.horizontal, 14)
                .padding(.vertical, 13)
                .background(
                    smokeProofSendBackground,
                    in: .rect(cornerRadius: 15)
                )
            }
            .buttonStyle(.plain)
            .disabled(isSendingSmokeProof)
            .accessibilityIdentifier("settings.smokeProof.sendButton")
            .accessibilityHint(languageStore.text(.settingsSmokeProofPrivacy))

            Text(languageStore.text(.settingsSmokeProofPrivacy))
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(16)
        .rorkCard(
            cornerRadius: 18,
            fill: AppTheme.accentCardFill(AppTheme.courtBlue, opacity: 0.12),
            stroke: AppTheme.courtBlue.opacity(0.20),
            glow: AppTheme.courtBlue,
            glowOpacity: 0.05
        )
    }

    private var settingsBackgroundUploadStatusRow: some View {
        let status = backgroundUploadStatusPreview
        return VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: status.icon)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(status.tint)
                    .frame(width: 24)

                VStack(alignment: .leading, spacing: 3) {
                    Text(status.title)
                        .font(.caption.weight(.bold))
                        .foregroundStyle(.white)
                    Text(status.detail)
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                        .minimumScaleFactor(0.84)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .layoutPriority(1)
            }

            backgroundUploadLifecycleTimeline
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(status.tint.opacity(0.10), in: .rect(cornerRadius: 14))
        .overlay {
            RoundedRectangle(cornerRadius: 14)
                .stroke(status.tint.opacity(0.20), lineWidth: 1)
        }
        .accessibilityIdentifier("settings.backgroundUpload.status")
    }

    private var backgroundUploadLifecycleTimeline: some View {
        let steps = backgroundUploadLifecycleSteps
        return VStack(alignment: .leading, spacing: 7) {
            ForEach(steps.indices, id: \.self) { index in
                let step = steps[index]
                HStack(spacing: 8) {
                    Image(systemName: step.icon)
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(step.tint)
                        .frame(width: 16)

                    VStack(alignment: .leading, spacing: 1) {
                        Text(step.title)
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(.white.opacity(0.92))
                        Text(step.detail)
                            .font(.caption2)
                            .foregroundStyle(AppTheme.subtleText)
                            .lineLimit(1)
                            .minimumScaleFactor(0.74)
                    }
                    .layoutPriority(1)
                }
            }
        }
        .padding(10)
        .background(.white.opacity(0.05), in: .rect(cornerRadius: 12))
        .overlay {
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.cyan.opacity(0.14), lineWidth: 1)
        }
        .accessibilityIdentifier("settings.backgroundUpload.timeline")
    }

    private var backgroundUploadLifecycleSteps: [(icon: String, title: String, detail: String, tint: Color)] {
        let latestProof = LaunchTelemetry.shared.latestBackgroundUploadProofSummary ?? "none"
        let proofTrail = LaunchTelemetry.shared.recentBackgroundUploadProofTrailSummary ?? "none"
        let combinedProof = "\(latestProof) \(proofTrail)".lowercased()
        let latestProgress = CloudAnalysisService.latestUploadProgressSummary()
        let hasProgress = latestProgress.trimmingCharacters(in: .whitespacesAndNewlines) != "none"
        let didWake = combinedProof.contains("background_urlsession_events_received")
        let didReattach = combinedProof.contains("reattached_session")
            || combinedProof.contains("events_received")
        let didFinish = combinedProof.contains("events_completed")
        let didRequestFinish = combinedProof.contains("events_finish_requested")

        return [
            backgroundUploadLifecycleStep(
                isDone: didWake,
                doneIcon: "iphone.radiowaves.left.and.right",
                waitingIcon: "iphone.slash",
                title: "iOS wake",
                doneDetail: "Background wake received.",
                waitingDetail: "Waiting for app-switch wake.",
                tint: Color.cyan
            ),
            backgroundUploadLifecycleStep(
                isDone: didReattach,
                doneIcon: "link.circle.fill",
                waitingIcon: "link.circle",
                title: "Session reattach",
                doneDetail: "Upload session checked.",
                waitingDetail: "Waiting to reattach session.",
                tint: AppTheme.neonPurple
            ),
            backgroundUploadLifecycleStep(
                isDone: hasProgress,
                doneIcon: "speedometer",
                waitingIcon: "hourglass",
                title: "Upload movement",
                doneDetail: backgroundUploadProgressTimelineDetail(from: latestProgress),
                waitingDetail: "No chunk progress recorded yet.",
                tint: AppTheme.warningYellow
            ),
            backgroundUploadLifecycleStep(
                isDone: didFinish,
                doneIcon: "checkmark.seal.fill",
                waitingIcon: "checkmark.seal",
                title: "Final callback",
                doneDetail: "Completion handler path recorded.",
                waitingDetail: didRequestFinish ? "Finish requested; waiting for callback." : "Waiting for final callback.",
                tint: didRequestFinish ? AppTheme.warningYellow : AppTheme.successGreen
            )
        ]
    }

    private func backgroundUploadLifecycleStep(
        isDone: Bool,
        doneIcon: String,
        waitingIcon: String,
        title: String,
        doneDetail: String,
        waitingDetail: String,
        tint: Color
    ) -> (icon: String, title: String, detail: String, tint: Color) {
        (
            icon: isDone ? doneIcon : waitingIcon,
            title: title,
            detail: isDone ? doneDetail : waitingDetail,
            tint: isDone ? tint : AppTheme.subtleText
        )
    }

    private func backgroundUploadProgressTimelineDetail(from summary: String) -> String {
        let bytes = backgroundUploadProgressField("bytes", in: summary)
        let speed = backgroundUploadProgressField("speed", in: summary)
        let eta = backgroundUploadProgressField("eta", in: summary)
        let context = backgroundUploadProgressField("context", in: summary)
        var parts = [String]()
        if let context, backgroundUploadProgressContextIsUseful(context) {
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
        return parts.isEmpty ? "Upload progress recorded." : parts.joined(separator: " | ")
    }

    private func backgroundUploadProgressField(_ field: String, in summary: String) -> String? {
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

    private func backgroundUploadProgressContextIsUseful(_ context: String) -> Bool {
        let lowercasedContext = context.lowercased()
        return lowercasedContext.contains("retry")
            || lowercasedContext.contains("failed")
            || lowercasedContext.contains("waiting")
            || lowercasedContext.contains("reconnecting")
            || lowercasedContext.contains("background upload")
    }

    private var copyUploadStateProofButton: some View {
        Button {
            copyUploadStateProof()
        } label: {
            HStack(spacing: 10) {
                Image(systemName: uploadStateProofCopied ? "checkmark.circle.fill" : "arrow.up.doc.fill")
                VStack(alignment: .leading, spacing: 2) {
                    Text(uploadStateProofCopied ? "Upload state copied" : "Copy upload state")
                        .font(.caption.weight(.bold))
                    Text("Small proof for app-switch and background upload debugging.")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(uploadStateProofCopied ? .black.opacity(0.72) : AppTheme.subtleText)
                        .lineLimit(2)
                        .minimumScaleFactor(0.84)
                }
                Spacer(minLength: 0)
            }
            .foregroundStyle(uploadStateProofCopied ? .black : .white)
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(
                uploadStateProofCopied ? AppTheme.successGreen : Color.cyan.opacity(0.16),
                in: .rect(cornerRadius: 14)
            )
            .overlay {
                RoundedRectangle(cornerRadius: 14)
                    .stroke((uploadStateProofCopied ? AppTheme.successGreen : Color.cyan).opacity(0.28), lineWidth: 1)
            }
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("settings.backgroundUpload.copyStateButton")
    }

    private var backgroundUploadStatusPreview: (icon: String, title: String, detail: String, tint: Color) {
        let pendingManifest = CloudAnalysisService.pendingBackgroundUploadManifestSummary()
        let latestProgress = CloudAnalysisService.latestUploadProgressSummary()
        let deployedCapability = CloudAnalysisService.latestDeployedUploadCapabilitySummary()
        let latestProof = LaunchTelemetry.shared.latestBackgroundUploadProofSummary ?? "none"

        if pendingManifest.contains("pending=true") {
            return (
                icon: pendingManifest.contains("source=available") ? "arrow.clockwise.icloud.fill" : "exclamationmark.icloud.fill",
                title: pendingManifest.contains("source=available") ? "Saved upload ready" : "Saved upload needs source",
                detail: compactUploadStatusDetail(pendingManifest),
                tint: pendingManifest.contains("source=available") ? Color.cyan : AppTheme.warningYellow
            )
        }

        if latestProgress != "none" {
            let isStalled = latestProgress.contains("stalled=true")
            return (
                icon: isStalled ? "wifi.exclamationmark" : "speedometer",
                title: isStalled ? "Upload waiting" : "Latest upload progress",
                detail: compactUploadStatusDetail(latestProgress),
                tint: isStalled ? AppTheme.warningYellow : Color.cyan
            )
        }

        if deployedCapability != "none" {
            return (
                icon: "checkmark.icloud.fill",
                title: "Backend limits loaded",
                detail: compactUploadStatusDetail(deployedCapability),
                tint: AppTheme.successGreen
            )
        }

        if latestProof != "none" {
            return (
                icon: "doc.text.magnifyingglass",
                title: "Upload proof available",
                detail: compactUploadStatusDetail(latestProof),
                tint: AppTheme.courtBlue
            )
        }

        return (
            icon: "icloud.and.arrow.up.fill",
            title: "Background upload ready",
            detail: "Start cloud analysis to capture upload progress, resumable status, and proof.",
            tint: AppTheme.subtleText
        )
    }

    private func compactUploadStatusDetail(_ value: String) -> String {
        let compact = proofTextValue(value)
            .replacingOccurrences(of: "_", with: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !compact.isEmpty else {
            return "No upload status yet."
        }
        return String(compact.prefix(140))
    }

    private var aboutHubLink: some View {
        settingsHubLink(
            title: languageStore.text(.aboutPrivacy),
            subtitle: languageStore.text(.aboutPrivacySubtitle),
            icon: "lock.doc.fill",
            accent: AppTheme.courtBlue,
            stats: [
                SettingsPreviewStat(
                    icon: "internaldrive.fill",
                    value: languageStore.text(.settingsOnDevice),
                    label: languageStore.text(.settingsHistory),
                    tint: AppTheme.successGreen
                ),
                SettingsPreviewStat(
                    icon: "brain.head.profile.fill",
                    value: languageStore.text(.settingsVisionAudio),
                    label: languageStore.text(.settingsEngine),
                    tint: AppTheme.courtBlue
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
                    value: languageStore.text(.settingsUnlimited),
                    label: languageStore.text(.analysis),
                    tint: AppTheme.neonPurple
                )
            ]
        }

        return [
            SettingsPreviewStat(
                icon: AppConstants.cloudAnalysisEnabled ? "sparkles" : "cpu.fill",
                value: "\(subscriptionManager.freeUsesRemaining)",
                label: AppConstants.cloudAnalysisEnabled ? languageStore.text(.freeLeft) : languageStore.text(.settingsOnDevice),
                tint: subscriptionManager.freeUsesRemaining > 0 ? AppTheme.warningYellow : AppTheme.dangerRed
            ),
            SettingsPreviewStat(
                icon: "crown.fill",
                value: "$9.99",
                label: languageStore.text(.settingsMonthly),
                tint: AppTheme.neonPurple
            )
        ]
    }

    private var appVersionString: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown"
    }

    private var appBuildNumber: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown"
    }

    private var smokeProofText: String {
        let generatedAt = ISO8601DateFormatter().string(from: Date())
        let currentProjectID = viewModel.currentProjectID?.uuidString ?? "none"
        let analysisJobID = viewModel.cloudAnalysisJobID ?? "none"
        let sourceObjectKeyState = viewModel.cloudEditSourceObjectKey == nil ? "none" : "available_redacted"
        let analysisProgressPercent = Int((min(max(viewModel.analysisService.progress, 0), 1) * 100).rounded(.down))
        let latestAIEditProof = LaunchTelemetry.shared.latestAIEditProofSummary ?? "none"
        let latestBackgroundUploadProof = LaunchTelemetry.shared.latestBackgroundUploadProofSummary ?? "none"
        let recentBackgroundUploadProofTrail = LaunchTelemetry.shared.recentBackgroundUploadProofTrailSummary ?? "none"
        let backgroundUploadWakeReceived = backgroundUploadWakeReceivedFlag(
            latestProof: latestBackgroundUploadProof,
            proofTrail: recentBackgroundUploadProofTrail
        )
        let latestUploadProgress = CloudAnalysisService.latestUploadProgressSummary()
        let latestServerUploadPlan = CloudAnalysisService.latestServerUploadPlanSummary()
        let latestServerUploadCapability = CloudAnalysisService.latestServerUploadCapabilitySummary()
        let latestDeployedUploadCapability = CloudAnalysisService.latestDeployedUploadCapabilitySummary()
        let pendingBackgroundUploadManifest = CloudAnalysisService.pendingBackgroundUploadManifestSummary()
        let backgroundUploadRuntimePolicy = CloudAnalysisService.backgroundUploadRuntimePolicySummary()
        let latestUnexpectedExit = LaunchTelemetry.shared.latestUnexpectedExitSummary ?? "none"
        let latestCrashReportDelivery = LaunchTelemetry.shared.latestCrashReportDeliverySummary ?? "none"

        return [
            "HoopClips Smoke Proof",
            "generatedAt=\(generatedAt)",
            "appVersion=\(appVersionString)",
            "build=\(appBuildNumber)",
            "environment=\(AppConstants.environmentName)",
            "cloudLaunchMode=\(AppConstants.cloudLaunchMode.rawValue)",
            "cloudAnalysisBaseURL=\(proofValue(AppConstants.cloudAnalysisBaseURL))",
            "cloudEditBaseURL=\(proofValue(AppConstants.cloudEditBaseURL))",
            "installID=\(viewModel.installID)",
            "projectID=\(currentProjectID)",
            "videoLoaded=\(viewModel.isVideoLoaded)",
            "videoDurationSeconds=\(Int(viewModel.videoDuration.rounded()))",
            "videoImportInProgress=\(viewModel.isVideoImportInProgress)",
            "videoImportStatus=\(proofTextValue(viewModel.videoImportStatusMessage))",
            "analysisMode=\(viewModel.analysisMode.rawValue)",
            "analysisIsAnalyzing=\(viewModel.analysisService.isAnalyzing)",
            "analysisProgressPercent=\(analysisProgressPercent)",
            "analysisStatus=\(proofTextValue(viewModel.analysisService.statusMessage))",
            "backgroundUploadMode=ios_background_urlsession",
            "backgroundUploadChunkedCompatible=true",
            "backgroundUploadResumePolicy=persisted_manifest_foreground_resume",
            "backgroundUploadRuntimePolicy=\(proofTextValue(backgroundUploadRuntimePolicy))",
            "backgroundUploadWakeReceived=\(backgroundUploadWakeReceived)",
            "pendingBackgroundUploadManifest=\(pendingBackgroundUploadManifest)",
            "latestBackgroundUploadProof=\(latestBackgroundUploadProof)",
            "recentBackgroundUploadProofTrail=\(proofLongTextValue(recentBackgroundUploadProofTrail))",
            "latestUploadProgress=\(proofTextValue(latestUploadProgress))",
            "serverUploadPlan=\(proofTextValue(latestServerUploadPlan))",
            "serverUploadCapability=\(proofTextValue(latestServerUploadCapability))",
            "deployedUploadCapability=\(proofTextValue(latestDeployedUploadCapability))",
            "cloudTeamScanInProgress=\(viewModel.isCloudTeamScanInProgress)",
            "cloudTeamScanStatus=\(proofTextValue(viewModel.cloudTeamScanStatusMessage))",
            "cloudQuotaRemaining=\(viewModel.cloudQuotaRemaining.map(String.init) ?? "unknown")",
            "clips=\(viewModel.clips.count)",
            "keptClips=\(viewModel.keptClips.count)",
            "discardedClips=\(viewModel.discardedClips.count)",
            "needsReviewClips=\(viewModel.needsReviewClips.count)",
            "cloudEditCandidatePool=\(viewModel.cloudEditCandidatePoolCount)",
            "analysisJobID=\(analysisJobID)",
            "sourceObjectKey=\(sourceObjectKeyState)",
            "latestAIEditProof=\(latestAIEditProof)",
            "latestUnexpectedExit=\(latestUnexpectedExit)",
            "latestCrashReportDelivery=\(latestCrashReportDelivery)",
            "note=no secrets or presigned URLs included"
        ].joined(separator: "\n")
    }

    private var uploadStateProofText: String {
        let generatedAt = ISO8601DateFormatter().string(from: Date())
        let analysisProgressPercent = Int((min(max(viewModel.analysisService.progress, 0), 1) * 100).rounded(.down))
        let pendingManifest = CloudAnalysisService.pendingBackgroundUploadManifestSummary()
        let latestProgress = CloudAnalysisService.latestUploadProgressSummary()
        let latestServerUploadPlan = CloudAnalysisService.latestServerUploadPlanSummary()
        let latestServerUploadCapability = CloudAnalysisService.latestServerUploadCapabilitySummary()
        let latestDeployedUploadCapability = CloudAnalysisService.latestDeployedUploadCapabilitySummary()
        let backgroundUploadRuntimePolicy = CloudAnalysisService.backgroundUploadRuntimePolicySummary()
        let latestBackgroundUploadProof = LaunchTelemetry.shared.latestBackgroundUploadProofSummary ?? "none"
        let recentBackgroundUploadProofTrail = LaunchTelemetry.shared.recentBackgroundUploadProofTrailSummary ?? "none"
        let backgroundUploadWakeReceived = backgroundUploadWakeReceivedFlag(
            latestProof: latestBackgroundUploadProof,
            proofTrail: recentBackgroundUploadProofTrail
        )

        return [
            "HoopClips Background Upload State",
            "generatedAt=\(generatedAt)",
            "appVersion=\(appVersionString)",
            "build=\(appBuildNumber)",
            "environment=\(AppConstants.environmentName)",
            "cloudLaunchMode=\(AppConstants.cloudLaunchMode.rawValue)",
            "videoLoaded=\(viewModel.isVideoLoaded)",
            "videoDurationSeconds=\(Int(viewModel.videoDuration.rounded()))",
            "analysisIsAnalyzing=\(viewModel.analysisService.isAnalyzing)",
            "analysisProgressPercent=\(analysisProgressPercent)",
            "analysisStatus=\(proofTextValue(viewModel.analysisService.statusMessage))",
            "backgroundUploadMode=ios_background_urlsession",
            "backgroundUploadChunkedCompatible=true",
            "backgroundUploadResumePolicy=persisted_manifest_foreground_resume",
            "backgroundUploadRuntimePolicy=\(proofTextValue(backgroundUploadRuntimePolicy))",
            "backgroundUploadWakeReceived=\(backgroundUploadWakeReceived)",
            "pendingBackgroundUploadManifest=\(proofTextValue(pendingManifest))",
            "latestUploadProgress=\(proofTextValue(latestProgress))",
            "serverUploadPlan=\(proofTextValue(latestServerUploadPlan))",
            "serverUploadCapability=\(proofTextValue(latestServerUploadCapability))",
            "deployedUploadCapability=\(proofTextValue(latestDeployedUploadCapability))",
            "latestBackgroundUploadProof=\(proofTextValue(latestBackgroundUploadProof))",
            "recentBackgroundUploadProofTrail=\(proofLongTextValue(recentBackgroundUploadProofTrail))",
            "privacy=no secrets, presigned URLs, object keys, or local file paths included"
        ].joined(separator: "\n")
    }

    private func backgroundUploadWakeReceivedFlag(latestProof: String, proofTrail: String) -> String {
        let combinedProof = "\(latestProof) \(proofTrail)".lowercased()
        return combinedProof.contains("background_urlsession_events_received") ? "true" : "false"
    }

    private func proofValue(_ value: String) -> String {
        value.isEmpty ? "none" : value
    }

    private func proofTextValue(_ value: String?) -> String {
        LaunchTelemetry.redactedAIEditFailureReason(value)
    }

    private func proofLongTextValue(_ value: String?) -> String {
        String(LaunchTelemetry.redactedAIEditFailureReason(value).prefix(720))
    }

    private func copySmokeProof() {
        UIPasteboard.general.string = smokeProofText
        smokeProofCopied = true
        LaunchTelemetry.shared.recordStabilityCheckpoint("smoke_proof.copied", metadata: "build=\(appBuildNumber)")

        DispatchQueue.main.asyncAfter(deadline: .now() + 2.2) {
            smokeProofCopied = false
        }
    }

    private func copyUploadStateProof() {
        UIPasteboard.general.string = uploadStateProofText
        uploadStateProofCopied = true
        LaunchTelemetry.shared.recordStabilityCheckpoint("background_upload_state.copied", metadata: "build=\(appBuildNumber)")

        DispatchQueue.main.asyncAfter(deadline: .now() + 2.2) {
            uploadStateProofCopied = false
        }
    }

    private var smokeProofSendLabel: String {
        if isSendingSmokeProof {
            return languageStore.text(.settingsSmokeProofSending)
        }
        if smokeProofSendSucceeded {
            return languageStore.text(.settingsSmokeProofSent)
        }
        if smokeProofSendFailed {
            return languageStore.text(.settingsSmokeProofSendFailed)
        }
        return languageStore.text(.settingsSmokeProofSend)
    }

    private var smokeProofSendIcon: String {
        if isSendingSmokeProof {
            return "paperplane.circle.fill"
        }
        if smokeProofSendSucceeded {
            return "checkmark.circle.fill"
        }
        if smokeProofSendFailed {
            return "exclamationmark.triangle.fill"
        }
        return "paperplane.fill"
    }

    private var smokeProofSendBackground: Color {
        if smokeProofSendSucceeded {
            return AppTheme.successGreen
        }
        if smokeProofSendFailed {
            return AppTheme.dangerRed.opacity(0.78)
        }
        return AppTheme.neonPurple.opacity(0.72)
    }

    private func sendSmokeProof() {
        guard !isSendingSmokeProof else { return }
        let proof = smokeProofText
        isSendingSmokeProof = true
        smokeProofSendSucceeded = false
        smokeProofSendFailed = false
        LaunchTelemetry.shared.recordStabilityCheckpoint("smoke_proof.manual_send_requested", metadata: "build=\(appBuildNumber)")

        Task { @MainActor in
            let sent = await LaunchTelemetry.shared.sendManualCrashProof(proof)
            isSendingSmokeProof = false
            smokeProofSendSucceeded = sent
            smokeProofSendFailed = !sent

            DispatchQueue.main.asyncAfter(deadline: .now() + 2.8) {
                smokeProofSendSucceeded = false
                smokeProofSendFailed = false
            }
        }
    }

    private var accountDisplayName: String {
        if let name = authService.currentUser?.displayName, !name.isEmpty {
            return name
        }
        return authMethodLabel
    }

    private var accountDetailLine: String {
        if let email = authService.currentUser?.email, !email.isEmpty {
            return email
        }
        return "\(languageStore.text(.settingsSignedInWith)) \(authMethodLabel)"
    }

    private var accountPlanStatGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize.isAccessibilitySize ? 160 : 112
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 260), spacing: 10, alignment: .top)
        ]
    }

    private var accountAnalysisPathIcon: String {
        AppConstants.cloudAnalysisEnabled ? "cloud.fill" : "cpu.fill"
    }

    private var accountAnalysisPathValue: String {
        AppConstants.cloudAnalysisEnabled ? languageStore.text(.settingsCloudAI) : languageStore.text(.settingsOnDevice)
    }

    private var accountAnalysisPathTint: Color {
        AppConstants.cloudAnalysisEnabled ? AppTheme.courtBlue : AppTheme.rimOrange
    }

    private func settingsInlineStat(icon: String, value: String, label: String, tint: Color) -> some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.caption.weight(.semibold))
                .foregroundStyle(tint)
                .frame(width: 16)

            VStack(alignment: .leading, spacing: 2) {
                Text(value)
                    .font(.caption.weight(.semibold).monospacedDigit())
                    .foregroundStyle(.white)
                    .lineLimit(2)
                    .minimumScaleFactor(0.82)
                    .fixedSize(horizontal: false, vertical: true)
                Text(label)
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
                    .lineLimit(2)
                    .minimumScaleFactor(0.86)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .layoutPriority(1)

            Spacer(minLength: 0)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 9)
        .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 60 : 48, alignment: .leading)
        .background(AppTheme.cardBg.opacity(0.44), in: .rect(cornerRadius: 13))
        .overlay(
            RoundedRectangle(cornerRadius: 13, style: .continuous)
                .stroke(AppTheme.softBorder, lineWidth: 1)
        )
    }

    private var settingsFootnote: some View {
        Text(languageStore.text(.settingsDeveloperFootnote))
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

    private var signOutFooterCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(languageStore.text(.accountQuickActions))
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.subtleText)
                .textCase(.uppercase)

            signOutButton
        }
        .padding(.top, 18)
    }

    private var workflowSettingsPage: some View {
        settingsDetailPage(
            title: languageStore.text(.workflowDefaults),
            subtitle: languageStore.text(.settingsWorkflowDetailSubtitle),
            icon: "waveform.and.magnifyingglass",
            accent: AppTheme.courtBlue
        ) {
            clipSettingsSection
            advancedSettingsSection
            dangerZone
        }
    }

    private var membershipSettingsPage: some View {
        settingsDetailPage(
            title: languageStore.text(.membershipAccount),
            subtitle: languageStore.text(.settingsMembershipDetailSubtitle),
            icon: "person.crop.circle.badge.checkmark",
            accent: AppTheme.rimOrange
        ) {
            accountSection
            subscriptionSection
        }
    }

    private var supportSettingsPage: some View {
        settingsDetailPage(
            title: languageStore.text(.supportCenter),
            subtitle: languageStore.text(.settingsSupportDetailSubtitle),
            icon: "bubble.left.and.exclamationmark.bubble.right.fill",
            accent: AppTheme.rimOrange
        ) {
            contactSuggestionsSection
            commonFAQSection
        }
    }

    private var aboutSettingsPage: some View {
        settingsDetailPage(
            title: languageStore.text(.aboutPrivacy),
            subtitle: languageStore.text(.settingsAboutDetailSubtitle),
            icon: "lock.doc.fill",
            accent: AppTheme.courtBlue
        ) {
            aboutSection
            legalLinksSection
            localLibrarySection
        }
    }

    private var legalLinksSection: some View {
        settingsCard(title: languageStore.text(.settingsLegal), icon: "doc.text.fill") {
            Text(languageStore.text(.settingsLegalSubtitle))
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
                .fixedSize(horizontal: false, vertical: true)

            legalLinkRow(
                title: languageStore.text(.legalPrivacy),
                subtitle: languageStore.text(.settingsPrivacyPolicySubtitle),
                icon: "hand.raised.fill",
                url: AppConstants.privacyPolicyURL
            )

            legalLinkRow(
                title: languageStore.text(.legalTerms),
                subtitle: languageStore.text(.settingsTermsSubtitle),
                icon: "doc.text.magnifyingglass",
                url: AppConstants.termsOfServiceURL
            )
        }
    }

    private var localLibrarySection: some View {
        settingsCard(title: languageStore.text(.settingsOnDeviceLibrary), icon: "internaldrive.fill") {
            Text(languageStore.text(.settingsOnDeviceLibraryDescription))
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
                .fixedSize(horizontal: false, vertical: true)

            HoopsFlowLayout(spacing: 8, rowSpacing: 8) {
                aiFeatureTag(languageStore.text(.settingsSourceVideoTag))
                aiFeatureTag(languageStore.text(.settingsLatestExportTag))
                aiFeatureTag(languageStore.text(.settingsEventTimelineTag))
                aiFeatureTag(languageStore.text(.settingsRestoreOnLaunchTag))
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
            HStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 11, style: .continuous)
                        .fill(accent.opacity(0.14))
                        .frame(width: 38, height: 38)
                    Image(systemName: icon)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(accent)
                }

                VStack(alignment: .leading, spacing: 3) {
                    Text(title)
                        .font(.headline.weight(.semibold))
                        .foregroundStyle(.white)
                        .lineLimit(2)
                        .minimumScaleFactor(0.86)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(2)
                        .minimumScaleFactor(0.82)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .layoutPriority(1)

                Spacer(minLength: 10)

                if let stat = stats.first {
                    Text(stat.value)
                        .font(.caption.weight(.semibold).monospacedDigit())
                        .foregroundStyle(stat.tint)
                        .lineLimit(1)
                        .minimumScaleFactor(0.75)
                        .padding(.horizontal, 9)
                        .padding(.vertical, 5)
                        .background(stat.tint.opacity(0.10), in: .capsule)
                }

                Image(systemName: "chevron.right")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(AppTheme.subtleText)
            }
            .padding(16)
            .rorkCard(
                cornerRadius: 18,
                fill: AppTheme.accentCardFill(accent, opacity: 0.12),
                stroke: accent.opacity(0.18),
                glow: accent,
                glowOpacity: 0.045
            )
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
            HoopsMotionBackdrop(glowOpacity: 0.14, courtOpacity: 0.06)

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
        settingsCard(title: languageStore.text(.settingsAIAnalysisWeights), icon: "brain.head.profile.fill") {
            weightSlider(label: languageStore.text(.settingsAudioCrowdNoise), value: $viewModel.settings.audioWeight, color: .blue)
            weightSlider(label: languageStore.text(.settingsMotionDetection), value: $viewModel.settings.motionWeight, color: .orange)
            weightSlider(label: languageStore.text(.settingsBodyPoseAnalysis), value: $viewModel.settings.poseWeight, color: .green)
            weightSlider(label: languageStore.text(.settingsSceneBrightness), value: $viewModel.settings.sceneWeight, color: .yellow)

            let total = viewModel.settings.audioWeight + viewModel.settings.motionWeight + viewModel.settings.poseWeight + viewModel.settings.sceneWeight
            HStack {
                Text(languageStore.text(.settingsTotalWeight))
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
                Text(languageStore.text(.settingsCurrentDetectionProfile))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                Spacer()
            }

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: "scope",
                    value: "\(Int(viewModel.settings.confidenceThreshold * 100))%",
                    label: languageStore.text(.settingsThreshold)
                )
                RorkMetricChip(
                    icon: "gauge.with.dots.needle.67percent",
                    value: formattedFrameRate(viewModel.settings.framesSampledPerSecond),
                    label: languageStore.text(.settingsSampling),
                    tint: AppTheme.warningYellow
                )
            }

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: normalized ? "checkmark.seal.fill" : "exclamationmark.triangle.fill",
                    value: normalized ? languageStore.text(.settingsBalanced) : languageStore.text(.settingsAdjust),
                    label: languageStore.text(.settingsWeights),
                    tint: normalized ? AppTheme.successGreen : AppTheme.warningYellow
                )
                RorkMetricChip(
                    icon: viewModel.settings.preferKeepUncertain ? "checkmark.circle.fill" : "xmark.circle.fill",
                    value: viewModel.settings.preferKeepUncertain ? languageStore.text(.settingsOn) : languageStore.text(.settingsOff),
                    label: languageStore.text(.settingsKeepUncertain),
                    tint: viewModel.settings.preferKeepUncertain ? AppTheme.successGreen : AppTheme.dangerRed
                )
            }

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: "clock.badge.checkmark.fill",
                    value: formattedTargetDuration(viewModel.settings.targetHighlightDuration),
                    label: languageStore.text(.settingsTargetReel),
                    tint: AppTheme.warningYellow
                )
                Spacer()
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder, glowOpacity: 0.06)
    }

    private var clipSettingsSection: some View {
        settingsCard(title: languageStore.text(.settingsClipReelDuration), icon: "scissors") {
            VStack(spacing: 4) {
                HStack {
                    Text(languageStore.text(.settingsMinimum))
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text(formattedSeconds(viewModel.settings.minClipDuration, fractionalDigits: 1))
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.minClipDuration, in: 1.0...5.0, step: 0.5)
                    .tint(AppTheme.accentPurple)
                    .accessibilityLabel(languageStore.text(.settingsMinimum))
                    .accessibilityValue(formattedSeconds(viewModel.settings.minClipDuration, fractionalDigits: 1))
                Text(languageStore.text(.settingsShortestClipHelp))
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }

            Divider().overlay(AppTheme.accentPurple.opacity(0.2))

            VStack(spacing: 4) {
                HStack {
                    Text(languageStore.text(.settingsMaximum))
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text(formattedSeconds(viewModel.settings.maxClipDuration, fractionalDigits: 0))
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.maxClipDuration, in: 5.0...30.0, step: 1.0)
                    .tint(AppTheme.accentPurple)
                    .accessibilityLabel(languageStore.text(.settingsMaximum))
                    .accessibilityValue(formattedSeconds(viewModel.settings.maxClipDuration, fractionalDigits: 0))
                Text(languageStore.text(.settingsLongestClipHelp))
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }

            Divider().overlay(AppTheme.accentPurple.opacity(0.2))

            VStack(spacing: 4) {
                HStack {
                    Text(languageStore.text(.settingsTargetHighlight))
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text(formattedTargetDuration(viewModel.settings.targetHighlightDuration))
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.targetHighlightDuration, in: 15.0...270.0, step: 5.0)
                    .tint(AppTheme.accentPurple)
                    .accessibilityLabel(languageStore.text(.settingsTargetHighlight))
                    .accessibilityValue(formattedTargetDuration(viewModel.settings.targetHighlightDuration))
                Text(languageStore.text(.settingsTargetHighlightHelp))
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
        let weightsStatus = abs(weightsTotal - 1.0) < 0.05 ? languageStore.text(.settingsBalanced) : languageStore.text(.settingsCustom)

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
                        title: languageStore.text(.settingsAdvancedSettings),
                        icon: "gearshape.2.fill",
                        subtitle: languageStore.text(.settingsAdvancedSubtitle)
                    )

                    if !showingAdvancedSettings {
                        HStack(spacing: 10) {
                            RorkMetricChip(
                                icon: "scope",
                                value: "\(Int(viewModel.settings.confidenceThreshold * 100))%",
                                label: languageStore.text(.settingsThreshold)
                            )
                            RorkMetricChip(
                                icon: "gauge.with.dots.needle.67percent",
                                value: formattedFrameRate(viewModel.settings.framesSampledPerSecond),
                                label: languageStore.text(.settingsSampling),
                                tint: AppTheme.warningYellow
                            )
                            RorkMetricChip(
                                icon: "brain.head.profile.fill",
                                value: weightsStatus,
                                label: languageStore.text(.settingsWeights),
                                tint: abs(weightsTotal - 1.0) < 0.05 ? AppTheme.successGreen : AppTheme.neonPurple
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
                Text(languageStore.text(.settingsConfidenceThreshold))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                Spacer()
            }

            VStack(spacing: 4) {
                HStack {
                    Text(languageStore.text(.settingsThreshold))
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text("\(Int(viewModel.settings.confidenceThreshold * 100))%")
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.confidenceThreshold, in: 0.1...0.9, step: 0.05)
                    .tint(AppTheme.accentPurple)
                    .accessibilityLabel(languageStore.text(.settingsConfidenceThreshold))
                    .accessibilityValue("\(Int(viewModel.settings.confidenceThreshold * 100)) percent")
                Text(languageStore.text(.settingsLowerConfidenceHelp))
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
                Text(languageStore.text(.settingsDetectionBehavior))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                Spacer()
            }

            VStack(spacing: 4) {
                HStack {
                    Text(languageStore.text(.settingsClipPadding))
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text(formattedSeconds(viewModel.settings.clipPadding, fractionalDigits: 1))
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.clipPadding, in: 0.5...3.0, step: 0.5)
                    .tint(AppTheme.accentPurple)
                    .accessibilityLabel(languageStore.text(.settingsClipPadding))
                    .accessibilityValue(formattedSeconds(viewModel.settings.clipPadding, fractionalDigits: 1))
                Text(languageStore.text(.settingsClipPaddingHelp))
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }

            Divider().overlay(AppTheme.accentPurple.opacity(0.2))

            Toggle(isOn: $viewModel.settings.preferKeepUncertain) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(languageStore.text(.settingsKeepUncertainClips))
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Text(languageStore.text(.settingsKeepUncertainHelp))
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
        settingsCard(title: languageStore.text(.settingsPerformance), icon: "gauge.with.dots.needle.67percent") {
            VStack(spacing: 4) {
                HStack {
                    Text(languageStore.text(.settingsFramesPerSecond))
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text(formattedFrameRate(viewModel.settings.framesSampledPerSecond))
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.framesSampledPerSecond, in: 1.0...10.0, step: 1.0)
                    .tint(AppTheme.accentPurple)
                    .accessibilityLabel(languageStore.text(.settingsFramesPerSecond))
                    .accessibilityValue(formattedFrameRate(viewModel.settings.framesSampledPerSecond))
                Text(languageStore.text(.settingsPerformanceHelp))
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }
        }
    }

    private var aboutSection: some View {
        settingsCard(title: languageStore.text(.settingsAbout), icon: "info.circle.fill") {
            VStack(spacing: 12) {
                HStack(spacing: 12) {
                    HoopsBrandMark(size: 48, showsShadow: false)

                    VStack(alignment: .leading, spacing: 2) {
                        Text("HoopClips")
                            .font(.headline)
                            .foregroundStyle(.white)
                    }

                    Spacer()

                    Text("v1.0")
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.subtleText)
                }

                Text(languageStore.text(.settingsAboutDescription))
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
                    .fixedSize(horizontal: false, vertical: true)

                HoopsFlowLayout(spacing: 5, rowSpacing: 5) {
                    Text("Created by")
                    Text("atrak.dev")
                        .fontWeight(.semibold)
                        .foregroundStyle(.white.opacity(0.9))
                    Text("with")
                    Image(systemName: "heart.fill")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(AppTheme.dangerRed)
                }
                .font(.caption.weight(.medium))
                .foregroundStyle(AppTheme.subtleText)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Created by atrak.dev with love")

                HoopsFlowLayout(spacing: 8, rowSpacing: 8) {
                    aiFeatureTag(languageStore.text(.settingsSmartClipsTag))
                    aiFeatureTag(languageStore.text(.settingsPrivateTag))
                    aiFeatureTag(languageStore.text(.settingsFastExportTag))
                    aiFeatureTag(languageStore.text(.settingsShareReadyTag))
                }
            }
        }
    }

    private var contactSuggestionsSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            RorkSectionHeader(
                title: languageStore.text(.settingsContactSuggestions),
                icon: "paperplane.fill",
                subtitle: languageStore.text(.settingsContactSubtitle)
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

            stabilityFeedbackCard

            VStack(alignment: .leading, spacing: 10) {
                Text(languageStore.text(.settingsFeedbackType))
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.subtleText)

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(FeedbackType.allCases) { type in
                            Button {
                                HoopsAccessibility.animate(reduceMotion: reduceMotion) { feedbackType = type }
                            } label: {
                                HStack(spacing: 8) {
                                    Image(systemName: type.icon)
                                        .font(.caption.weight(.semibold))
                                    Text(languageStore.text(type.textKey))
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
                Text(languageStore.text(.settingsEmailOptional))
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
                    Text(languageStore.text(.settingsMessage))
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
                        Text(languageStore.text(.settingsMessagePlaceholder))
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
                        Text(languageStore.text(.settingsClear))
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
                        Text(isSubmittingFeedback ? languageStore.text(.settingsSending) : languageStore.text(.settingsSend))
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

            Text(languageStore.text(.settingsFeedbackPrivacyNote))
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.06)
    }

    @ViewBuilder
    private var stabilityFeedbackCard: some View {
        if let stabilitySummary = LaunchTelemetry.shared.latestUnexpectedExitSummary {
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: "waveform.path.ecg.rectangle.fill")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(AppTheme.warningYellow)
                        .frame(width: 24)

                    VStack(alignment: .leading, spacing: 4) {
                        Text("App health note")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(.white)
                        Text(stabilitySummary)
                            .font(.caption2)
                            .foregroundStyle(AppTheme.subtleText)
                            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 8 : 5)
                            .minimumScaleFactor(0.84)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .layoutPriority(1)
                }

                Button {
                    prefillStabilityFeedback(stabilitySummary)
                } label: {
                    Label("Report app quit", systemImage: "paperplane.fill")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.white)
                        .lineLimit(2)
                        .minimumScaleFactor(0.86)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 48 : 38)
                        .padding(.horizontal, 10)
                        .background(AppTheme.warningYellow.opacity(0.18), in: .rect(cornerRadius: 12))
                        .overlay {
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(AppTheme.warningYellow.opacity(0.26), lineWidth: 1)
                        }
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("settings.feedback.reportAppQuit")
            }
            .padding(12)
            .rorkCard(
                cornerRadius: 12,
                fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.50)),
                stroke: AppTheme.warningYellow.opacity(0.20),
                glow: AppTheme.warningYellow,
                glowOpacity: 0.04
            )
            .accessibilityIdentifier("settings.feedback.stabilitySummary")
        }
    }

    private var commonFAQSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            RorkSectionHeader(
                title: languageStore.text(.settingsCommonFAQ),
                icon: "questionmark.circle.fill",
                subtitle: languageStore.text(.settingsFAQSubtitle)
            )

            VStack(spacing: 10) {
                ForEach(commonFAQItems) { item in
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
                title: languageStore.text(.account),
                icon: "person.crop.circle.fill",
                subtitle: languageStore.text(.settingsAccountDetailsSubtitle)
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
                    Text("\(languageStore.text(.settingsSignedInWith)) \(authMethodLabel)")
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
        case .email: return languageStore.text(.email)
        case .phone: return languageStore.text(.phoneNumber)
        case .anonymous: return languageStore.text(.settingsGuest)
        case nil: return languageStore.text(.settingsUnknown)
        }
    }

    private var membershipRequiresAccountSignIn: Bool {
        authService.currentUser?.authMethod == .anonymous
    }

    private var subscriptionSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            RorkSectionHeader(
                title: languageStore.text(.settingsSubscription),
                icon: "crown.fill",
                subtitle: subscriptionManager.isProUser ? languageStore.text(.settingsUnlimitedAccess) : (membershipRequiresAccountSignIn ? languageStore.text(.settingsSignInRequired) : languageStore.text(.settingsFreeTier))
            )

            if subscriptionManager.isProUser {
                HStack(spacing: 12) {
                    Image(systemName: "checkmark.seal.fill")
                        .font(.title2)
                        .foregroundStyle(AppTheme.successGreen)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(languageStore.text(.settingsProMember))
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.white)
                        Text(languageStore.text(.settingsUnlimitedAIExports))
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
                        label: languageStore.text(.freeLeft),
                        tint: subscriptionManager.freeUsesRemaining > 0 ? AppTheme.warningYellow : AppTheme.dangerRed
                    )
                    RorkMetricChip(
                        icon: "crown.fill",
                        value: "$9.99",
                        label: languageStore.text(.settingsPerMonth),
                        tint: AppTheme.neonPurple
                    )
                }

                Button {
                    showingPaywall = true
                } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "crown.fill")
                            .font(.subheadline)
                        Text(membershipRequiresAccountSignIn ? languageStore.text(.settingsSignInToUpgrade) : languageStore.text(.settingsUpgradeToPro))
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
            showingSignOutConfirmation = true
        } label: {
            HStack {
                Image(systemName: "rectangle.portrait.and.arrow.right")
                Text(languageStore.text(.settingsSignOut))
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
            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
            .minimumScaleFactor(0.84)
            .fixedSize(horizontal: false, vertical: true)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(AppTheme.accentPurple.opacity(0.15), in: .capsule)
    }

    private var dangerZone: some View {
        Button {
            showingResetConfirmation = true
        } label: {
            VStack(spacing: 6) {
                HStack {
                    Image(systemName: "arrow.counterclockwise")
                    Text(languageStore.text(.settingsResetToDefaults))
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
                    Text(languageStore.text(.settingsMissingReleaseURL))
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
                .accessibilityLabel(label)
                .accessibilityValue("\(Int(value.wrappedValue * 100)) percent")
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
                message: languageStore.text(.settingsFeedbackValidationMessage),
                icon: "exclamationmark.triangle.fill",
                tint: AppTheme.dangerRed
            )
            return
        }

        guard let endpoint = URL(string: "https://formspree.io/f/xlgwzrdk") else {
            feedbackBanner = FeedbackBanner(
                message: languageStore.text(.settingsFeedbackConfigError),
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
            source: "HoopClips Settings",
            appVersion: "v1.0",
            exportTheme: viewModel.selectedTheme.rawValue,
            exportQuality: viewModel.selectedQuality.rawValue,
            exportFormat: viewModel.selectedFormat.rawValue,
            stabilitySummary: LaunchTelemetry.shared.latestUnexpectedExitSummary
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
                    message: serverMessage ?? languageStore.text(.settingsFeedbackSendFailure),
                    icon: "wifi.exclamationmark",
                    tint: AppTheme.dangerRed
                )
                return
            }

            feedbackBanner = FeedbackBanner(
                message: languageStore.text(.settingsFeedbackSentThanks),
                icon: "checkmark.circle.fill",
                tint: AppTheme.successGreen
            )
            feedbackMessage = ""
        } catch {
            feedbackBanner = FeedbackBanner(
                message: languageStore.text(.settingsFeedbackNetworkError),
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

    private func prefillStabilityFeedback(_ stabilitySummary: String) {
        feedbackType = .bug
        let prefix = "The app quit unexpectedly during testing."
        let diagnosticLine = "Diagnostics: \(stabilitySummary)"
        let current = feedbackMessage.trimmingCharacters(in: .whitespacesAndNewlines)
        let separator = current.isEmpty ? "" : "\n\n"
        feedbackMessage = String((current + separator + prefix + "\n" + diagnosticLine).prefix(1200))
    }

    private func formattedTargetDuration(_ duration: Double) -> String {
        if duration < 60 {
            return formattedSeconds(duration, fractionalDigits: 0)
        }

        let minutes = Int(duration) / 60
        let seconds = Int(duration) % 60
        if languageStore.selectedLanguage == .chinese {
            if seconds == 0 {
                return "\(minutes) 分钟"
            }
            return "\(minutes)分 \(seconds)秒"
        }

        if seconds == 0 {
            return "\(minutes) min"
        }
        return "\(minutes)m \(seconds)s"
    }

    private func formattedSeconds(_ duration: Double, fractionalDigits: Int) -> String {
        let format = "%.\(fractionalDigits)f"
        let value = String(format: format, duration)
        return languageStore.selectedLanguage == .chinese ? "\(value) 秒" : "\(value) sec"
    }

    private func formattedFrameRate(_ framesPerSecond: Double) -> String {
        let value = String(format: "%.0f", framesPerSecond)
        return languageStore.selectedLanguage == .chinese ? "\(value) 帧/秒" : "\(value) fps"
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
                .lineLimit(2)
                .minimumScaleFactor(0.82)
                .fixedSize(horizontal: false, vertical: true)
            Text(label)
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .lineLimit(2)
                .minimumScaleFactor(0.86)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, minHeight: 78)
        .padding(.vertical, 12)
        .rorkCard(
            cornerRadius: 14,
            fill: AppTheme.accentCardFill(tint, opacity: 0.10),
            stroke: tint.opacity(0.18),
            glow: tint,
            glowOpacity: 0.035
        )
    }
}
