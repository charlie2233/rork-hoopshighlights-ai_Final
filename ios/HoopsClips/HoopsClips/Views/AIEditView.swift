import AVKit
import Foundation
import SwiftUI

enum AIEditPresentation {
    case sheet
    case exportSection
}

private enum AIEditProInfoSheet: Identifiable {
    case benefits
    case template(CloudEditProTemplate)

    var id: String {
        switch self {
        case .benefits:
            return "benefits"
        case .template(let template):
            return template.id
        }
    }
}

struct AIEditView: View {
    @Bindable var viewModel: HighlightsViewModel
    let isProUser: Bool
    var revenueCatAppUserID: String? = nil
    var presentation: AIEditPresentation = .sheet
    var onRequestProUpgrade: (() -> Void)?

    @Environment(\.dismiss) private var dismiss
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    @State private var selectedPreset: CloudEditPreset = .personalHighlight
    @State private var selectedProTemplate: CloudEditProTemplate?
    @State private var selectedAspectRatio: CloudEditAspectRatio = CloudEditPreset.personalHighlight.aspectRatio
    @State private var selectedDuration = CloudEditPreset.personalHighlight.durationOptions[1]
    @State private var phase: CloudEditRenderState = .planning
    @State private var editJob: CloudEditJobResponse?
    @State private var editPlan: CloudEditPlanSummary?
    @State private var policySummary: CloudEditPolicySummary?
    @State private var renderStatus: CloudEditRenderStatusResponse?
    @State private var downloadResponse: CloudEditDownloadResponse?
    @State private var revisionResponse: CloudEditRevisionResponse?
    @State private var pendingRevisionCommand: CloudEditRevisionCommand?
    @State private var serviceVersion: CloudEditVersionResponse?
    @State private var serviceStatusErrorMessage: String?
    @State private var serviceStatusBlocksRendering = false
    @State private var serviceStatusIsChecking = false
    @State private var renderHistory: [CloudEditRenderStatusResponse] = []
    @AppStorage("hoops.previewAudioMuted.v1") private var previewAudioMuted = false
    @State private var previewPlayer: AVPlayer?
    @State private var localShareURL: URL?
    @State private var errorMessage: String?
    @State private var lockerErrorMessage: String?
    @State private var userEditPrompt = ""
    @State private var isWorking = false
    @State private var isPreparingShare = false
    @State private var isLoadingRenderHistory = false
    @State private var lockerBusyRenderJobID: String?
    @State private var showingShareSheet = false
    @State private var proInfoSheet: AIEditProInfoSheet?
    @State private var showPlanDetails = false
    @State private var showSetupControls = false
    @State private var showTimelineDetails = false
    @State private var showAdvancedAIEditDetails = false
    @State private var showAllDurationOptions = false
    @State private var activeInstallID: String?
    @State private var foregroundRefreshTask: Task<Void, Never>?

    private let cloudEditService: any CloudEditServicing
    private let proUXFlags = CloudEditProUXFlags.safeDefault
    private static let maxUserPromptCharacters = CloudEditUserPromptBuilder.maxPromptCharacters
    private static let quickPrompts = AIEditQuickPromptLibrary.options

    init(
        viewModel: HighlightsViewModel,
        isProUser: Bool,
        revenueCatAppUserID: String? = nil,
        presentation: AIEditPresentation = .sheet,
        cloudEditService: any CloudEditServicing = CloudEditService(),
        onRequestProUpgrade: (() -> Void)? = nil
    ) {
        self.viewModel = viewModel
        self.isProUser = isProUser
        self.revenueCatAppUserID = revenueCatAppUserID
        self.presentation = presentation
        self.cloudEditService = cloudEditService
        self.onRequestProUpgrade = onRequestProUpgrade
    }

    var body: some View {
        Group {
            switch presentation {
            case .sheet:
                sheetBody
            case .exportSection:
                workflowContent
            }
        }
        .sheet(isPresented: $showingShareSheet) {
            if let localShareURL {
                SystemShareSheet(
                    items: SystemShareSheet.videoItems(
                        for: localShareURL,
                        title: "HoopClips AI Edit"
                    ),
                    subject: "HoopClips AI Edit"
                )
            }
        }
        .sheet(item: $proInfoSheet) { sheet in
            switch sheet {
            case .benefits:
                proBenefitsSheet
            case .template(let template):
                proTemplateInfoSheet(for: template)
            }
        }
        .alert("Saved to Photos", isPresented: $viewModel.showingSaveSuccess) {
            Button("OK", role: .cancel) { }
        } message: {
            Text("Your HoopClips video is in your photo library.")
        }
        .task(id: viewModel.installID) {
            resetCloudEditSessionIfIdentityChanged(to: viewModel.installID)
            await refreshCloudEditVersion()
            await refreshRenderHistory()
        }
        .onChange(of: scenePhase) { _, phase in
            guard phase == .active else { return }
            refreshCloudEditAfterForegroundIfNeeded()
        }
    }

    private func resetCloudEditSessionIfIdentityChanged(to installID: String) {
        let previousInstallID = activeInstallID
        activeInstallID = installID
        guard let previousInstallID, previousInstallID != installID else { return }

        foregroundRefreshTask?.cancel()
        foregroundRefreshTask = nil
        previewPlayer?.pause()
        selectedPreset = .personalHighlight
        selectedProTemplate = nil
        selectedAspectRatio = CloudEditPreset.personalHighlight.aspectRatio
        selectedDuration = CloudEditPreset.personalHighlight.durationOptions[1]
        phase = .planning
        editJob = nil
        editPlan = nil
        policySummary = nil
        renderStatus = nil
        downloadResponse = nil
        revisionResponse = nil
        pendingRevisionCommand = nil
        renderHistory = []
        previewPlayer = nil
        localShareURL = nil
        errorMessage = nil
        lockerErrorMessage = nil
        isWorking = false
        isPreparingShare = false
        isLoadingRenderHistory = false
        lockerBusyRenderJobID = nil
        showingShareSheet = false
        showPlanDetails = false
        showTimelineDetails = false
        showAdvancedAIEditDetails = false
        showAllDurationOptions = false
    }

    private func refreshCloudEditAfterForegroundIfNeeded() {
        guard foregroundRefreshTask == nil else { return }

        foregroundRefreshTask = Task { @MainActor in
            await refreshCloudEditVersion()
            await refreshRenderHistory()
            foregroundRefreshTask = nil
        }
    }

    private var sheetBody: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.18)

                ScrollView {
                    workflowContent
                    .padding(16)
                    .padding(.bottom, 32)
                }
            }
            .navigationTitle("AI Edit")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                        .foregroundStyle(AppTheme.neonPurple)
                }
            }
        }
    }

    private var workflowContent: some View {
        VStack(spacing: 18) {
            heroCard
            promptCard
            smartSetupCard
            if showSetupControls {
                stylePicker
                formatPicker
                durationPicker
            }
            actionCard
            statusCard
            if let previewPlayer {
                previewCard(player: previewPlayer)
            }
            if editPlan != nil, downloadResponse != nil || revisionResponse != nil {
                revisionCard
            }
            aiEditDetailsToggle
            if showAdvancedAIEditDetails {
                if shouldShowAIWorkTimeline {
                    aiWorkTimelineCard
                }
                if shouldShowCloudLocker {
                    cloudLockerCard
                }

                if let receipt = activeWorkReceipt {
                    aiWorkReceiptCard(receipt)
                }

                planTierCard
                if activePolicy.planTier.isFree, proUXFlags.proUpsellEnabled {
                    proValueCard
                }
            }
        }
    }

    private var aiEditDetailsToggle: some View {
        Button {
            HoopsAccessibility.animate(reduceMotion: reduceMotion, .snappy(duration: 0.18)) {
                showAdvancedAIEditDetails.toggle()
            }
        } label: {
            HStack(alignment: .center, spacing: 10) {
                Image(systemName: showAdvancedAIEditDetails ? "chevron.up.circle.fill" : "chevron.down.circle.fill")
                    .font(.headline)
                    .foregroundStyle(AppTheme.warningYellow)
                    .frame(width: 24)

                VStack(alignment: .leading, spacing: 3) {
                    Text(showAdvancedAIEditDetails ? "Hide edit details" : "Edit details")
                        .font(.subheadline.bold())
                        .foregroundStyle(.white)
                        .lineLimit(2)
                        .minimumScaleFactor(0.84)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(aiEditDetailsSummary)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                        .minimumScaleFactor(0.84)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(AppTheme.cardBg.opacity(0.74), in: .rect(cornerRadius: 14))
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(AppTheme.neonPurple.opacity(0.14), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("export.aiEdit.detailsToggle")
        .accessibilityLabel(showAdvancedAIEditDetails ? "Hide edit details" : "Show edit details")
        .accessibilityValue(aiEditDetailsSummary)
    }

    private var heroCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Make My Reel", systemImage: "wand.and.stars")
                .font(.title2.bold())
                .foregroundStyle(.white)
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                .minimumScaleFactor(0.84)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("export.aiEdit.section")

            Text(AIEditPromptCopy.heroSubtitle)
                .font(.subheadline)
                .foregroundStyle(AppTheme.subtleText)
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 3)
                .minimumScaleFactor(0.84)
                .fixedSize(horizontal: false, vertical: true)

            LazyVGrid(columns: heroChipGridColumns, alignment: .leading, spacing: 8) {
                aiChip(icon: "film.stack.fill", text: clipPoolChipText)
                aiChip(icon: viewModel.settings.highlightTeamSelection.mode == .team ? "person.2.fill" : "person.3.fill", text: teamTargetChipText)
                aiChip(icon: selectedAspectRatio.icon, text: selectedAspectRatio.rawValue)
                aiChip(icon: "timer", text: formattedDuration(selectedDuration))
            }

        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.accentPurple.opacity(0.22), glow: AppTheme.neonPurple, glowOpacity: 0.10)
    }

    private var planTierCard: some View {
        let policy = activePolicy
        return VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(policy.planTier.isFree ? AppTheme.cardBg.opacity(0.9) : AppTheme.successGreen.opacity(0.24))
                        .frame(width: 44, height: 44)
                    Image(systemName: policy.planTier.isFree ? "person.crop.circle.badge.clock" : "bolt.badge.checkmark.fill")
                        .font(.headline)
                        .foregroundStyle(policy.planTier.isFree ? AppTheme.warningYellow : AppTheme.successGreen)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text("Current plan: \(policy.displayName)")
                        .font(.headline)
                        .foregroundStyle(.white)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("export.aiEdit.plan.current")
                    Text("\(policy.maxDailyRenders) AI edits/day - \(policy.maxOutputResolution) max")
                        .font(.caption.bold())
                        .foregroundStyle(AppTheme.warningYellow)
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                        .minimumScaleFactor(0.84)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("export.aiEdit.queue.label")
                }
                Spacer(minLength: 0)
            }

            DisclosureGroup(isExpanded: $showPlanDetails) {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(policy.planLimitRows, id: \.self) { row in
                        Label(row, systemImage: "checkmark.circle.fill")
                            .font(.caption2.weight(.semibold))
                            .foregroundStyle(.white.opacity(0.88))
                            .lineLimit(2)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    if policy.planTier.isFree {
                        Label("Failed HoopClips jobs do not use a free edit.", systemImage: "arrow.counterclockwise.circle.fill")
                            .font(.caption2.weight(.semibold))
                            .foregroundStyle(AppTheme.warningYellow)
                            .lineLimit(3)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(.top, 4)
            } label: {
                Label("Plan limits", systemImage: "list.bullet.clipboard.fill")
                    .font(.caption.bold())
                    .foregroundStyle(AppTheme.subtleText)
            }
            .tint(AppTheme.warningYellow)
            .accessibilityIdentifier("export.aiEdit.planDetails")
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.warningYellow.opacity(0.18), glow: AppTheme.warningYellow, glowOpacity: 0.04)
        .accessibilityIdentifier("export.aiEdit.planCard.\(policy.planTier.isFree ? "free" : "pro")")
    }

    private var proValueCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(AppTheme.neonPurple.opacity(0.2))
                        .frame(width: 44, height: 44)
                    Image(systemName: "crown.fill")
                        .font(.headline)
                        .foregroundStyle(AppTheme.warningYellow)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("Upgrade to Pro")
                        .font(.headline)
                        .foregroundStyle(.white)
                    Text("Priority rendering, 1080p exports, Pro templates, and 10 revisions/edit.")
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer()
            }

            VStack(spacing: 8) {
                if onRequestProUpgrade != nil {
                    Button {
                        requestProUpgrade()
                    } label: {
                        Label("Upgrade with App Store", systemImage: "crown.fill")
                            .font(.caption.bold())
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 10)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(AppTheme.warningYellow)
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("Upgrade with App Store")
                    .accessibilityIdentifier("export.aiEdit.pro.upgradeButton")
                }

                Button {
                    proInfoSheet = .benefits
                } label: {
                    Label("See Pro benefits", systemImage: "info.circle.fill")
                        .font(.caption.bold())
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                }
                .buttonStyle(.bordered)
                .tint(AppTheme.warningYellow)
                .accessibilityIdentifier("export.aiEdit.pro.infoButton")
            }

            LazyVGrid(columns: [GridItem(.adaptive(minimum: 138), spacing: 8)], spacing: 8) {
                ForEach(Array(CloudEditPolicySummary.proValueRows.prefix(4)), id: \.self) { row in
                    Label(row, systemImage: "sparkles")
                        .font(.caption2.bold())
                        .foregroundStyle(.white.opacity(0.9))
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 8)
                        .background(AppTheme.accentPurple.opacity(0.22), in: .rect(cornerRadius: 12))
                }
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.neonPurple.opacity(0.2), glow: AppTheme.neonPurple, glowOpacity: 0.06)
        .accessibilityIdentifier("export.aiEdit.proValueCard")
    }

    private var smartSetupCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(AppTheme.accentPurple.opacity(0.24))
                        .frame(width: 44, height: 44)
                    Image(systemName: "slider.horizontal.below.rectangle")
                        .font(.headline)
                        .foregroundStyle(AppTheme.warningYellow)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text("Edit options")
                        .font(.headline)
                        .foregroundStyle(.white)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)

                    Text(selectedSetupSummary)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                        .minimumScaleFactor(0.84)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("export.aiEdit.smartSetup.summary")
                }

                Spacer(minLength: 0)
            }

            Button {
                HoopsAccessibility.animate(reduceMotion: reduceMotion, .snappy(duration: 0.18)) {
                    showSetupControls.toggle()
                }
            } label: {
                Label(showSetupControls ? "Hide options" : "Change options", systemImage: showSetupControls ? "chevron.up.circle.fill" : "slider.horizontal.3")
                    .font(.caption.bold())
                    .multilineTextAlignment(.center)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                    .minimumScaleFactor(0.84)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 52 : 42)
                    .padding(.horizontal, 8)
            }
            .buttonStyle(.bordered)
            .tint(AppTheme.neonPurple)
            .accessibilityIdentifier("export.aiEdit.smartSetup.changeButton")
            .accessibilityValue(showSetupControls ? "Setup choices shown" : "Setup choices hidden")
            .accessibilityHint("Shows or hides optional AI edit style, video shape, and reel length choices.")
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.neonPurple.opacity(0.18), glow: AppTheme.neonPurple, glowOpacity: 0.05)
        .accessibilityIdentifier("export.aiEdit.smartSetupCard")
    }

    private var stylePicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Edit Style")
                .font(.headline)
                .foregroundStyle(.white)

            ForEach(CloudEditPreset.allCases) { preset in
                Button {
                    selectFreePreset(preset)
                } label: {
                    HStack(alignment: .top, spacing: 12) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 12)
                                .fill(selectedProTemplate == nil && selectedPreset == preset ? AppTheme.accentPurple.opacity(0.32) : AppTheme.cardBg.opacity(0.86))
                                .frame(width: 44, height: 44)
                            Image(systemName: preset.icon)
                                .font(.headline)
                                .foregroundStyle(selectedProTemplate == nil && selectedPreset == preset ? AppTheme.warningYellow : AppTheme.neonPurple)
                        }
                        VStack(alignment: .leading, spacing: 3) {
                            Text(preset.title)
                                .font(.subheadline.bold())
                                .foregroundStyle(.white)
                                .lineLimit(2)
                                .fixedSize(horizontal: false, vertical: true)
                            HStack(spacing: 6) {
                                Text("Free")
                                    .font(.caption2.bold())
                                    .foregroundStyle(AppTheme.successGreen)
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 3)
                                    .background(AppTheme.successGreen.opacity(0.16), in: .capsule)
                                if selectedProTemplate == nil && selectedPreset == preset {
                                    Image(systemName: "checkmark.seal.fill")
                                        .font(.caption)
                                        .foregroundStyle(AppTheme.successGreen)
                                }
                            }
                            Text(preset.subtitle)
                                .font(.caption.bold())
                                .foregroundStyle(AppTheme.warningYellow)
                                .lineLimit(2)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        Spacer(minLength: 0)
                    }
                    .padding(14)
                    .background(selectedProTemplate == nil && selectedPreset == preset ? AppTheme.accentPurple.opacity(0.18) : AppTheme.cardBg.opacity(0.72), in: .rect(cornerRadius: 14))
                    .overlay {
                        RoundedRectangle(cornerRadius: 14)
                            .stroke(selectedProTemplate == nil && selectedPreset == preset ? AppTheme.neonPurple.opacity(0.35) : AppTheme.softBorder, lineWidth: 1)
                    }
                }
                .buttonStyle(.plain)
                .accessibilityLabel(preset.title)
                .accessibilityIdentifier(styleAccessibilityIdentifier(for: preset))
                .accessibilityValue(selectedProTemplate == nil && selectedPreset == preset ? "Selected" : "Not selected")
                .accessibilityHint("Selects the AI edit style.")
            }

            if proUXFlags.proTemplatesEnabled {
                ForEach(CloudEditProTemplate.allCases) { template in
                    Button {
                        if isProUser {
                            selectProTemplate(template)
                        } else {
                            proInfoSheet = .template(template)
                        }
                    } label: {
                        HStack(alignment: .top, spacing: 12) {
                            ZStack {
                                RoundedRectangle(cornerRadius: 12)
                                    .fill(selectedProTemplate == template ? AppTheme.warningYellow.opacity(0.24) : AppTheme.cardBg.opacity(0.62))
                                    .frame(width: 44, height: 44)
                                Image(systemName: template.icon)
                                    .font(.headline)
                                    .foregroundStyle(selectedProTemplate == template ? AppTheme.warningYellow : AppTheme.subtleText)
                            }
                            VStack(alignment: .leading, spacing: 3) {
                                Text(template.title)
                                    .font(.subheadline.bold())
                                    .foregroundStyle(.white)
                                    .lineLimit(2)
                                    .fixedSize(horizontal: false, vertical: true)
                                HStack(spacing: 6) {
                                    Text("Pro")
                                        .font(.caption2.bold())
                                        .foregroundStyle(.white)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 3)
                                        .background(AppTheme.warningYellow.opacity(0.5), in: .capsule)
                                    Image(systemName: isProUser ? "checkmark.seal.fill" : "lock.fill")
                                        .font(.caption2.bold())
                                        .foregroundStyle(AppTheme.warningYellow)
                                }
                                Text(template.subtitle)
                                    .font(.caption.bold())
                                    .foregroundStyle(AppTheme.warningYellow)
                                    .lineLimit(2)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            Spacer(minLength: 0)
                        }
                        .padding(14)
                        .background(selectedProTemplate == template ? AppTheme.warningYellow.opacity(0.12) : AppTheme.cardBg.opacity(0.45), in: .rect(cornerRadius: 14))
                        .overlay {
                            RoundedRectangle(cornerRadius: 14)
                                .stroke(selectedProTemplate == template ? AppTheme.warningYellow.opacity(0.36) : AppTheme.warningYellow.opacity(0.18), lineWidth: 1)
                        }
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(isProUser ? template.title : "\(template.title), locked Pro template")
                    .accessibilityIdentifier(template.accessibilityIdentifier)
                    .accessibilityValue(selectedProTemplate == template ? "Selected" : (isProUser ? "Not selected" : "Locked"))
                    .accessibilityHint(isProUser ? "Selects this Pro AI edit template." : "Shows Pro information without changing the current render template.")
                }
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.04)
    }

    private var durationPicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            optionHeader(title: "Reel Length", value: formattedDuration(selectedDuration))

            LazyVGrid(columns: durationGridColumns, spacing: 8) {
                ForEach(displayedDurationOptions, id: \.self) { duration in
                    Button {
                        if duration <= activePolicy.maxRenderSeconds {
                            selectedDuration = duration
                        }
                    } label: {
                        Text(formattedDuration(duration))
                            .font(.subheadline.bold())
                            .lineLimit(1)
                            .minimumScaleFactor(0.82)
                            .foregroundStyle(duration > activePolicy.maxRenderSeconds ? AppTheme.subtleText.opacity(0.45) : (selectedDuration == duration ? .white : AppTheme.subtleText))
                            .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 54 : 44)
                            .padding(.horizontal, 8)
                            .background(selectedDuration == duration ? AppTheme.accentPurple : AppTheme.cardBg.opacity(duration > activePolicy.maxRenderSeconds ? 0.45 : 1), in: .rect(cornerRadius: 12))
                    }
                    .buttonStyle(.plain)
                    .disabled(duration > activePolicy.maxRenderSeconds)
                    .accessibilityLabel("Set reel length to \(formattedDuration(duration))")
                    .accessibilityIdentifier(durationAccessibilityIdentifier(for: duration))
                    .accessibilityValue(duration > activePolicy.maxRenderSeconds ? "Unavailable on \(activePolicy.displayName)" : (selectedDuration == duration ? "Selected" : "Not selected"))
                }
            }

            if shouldShowDurationOptionsToggle {
                Button {
                    HoopsAccessibility.animate(reduceMotion: reduceMotion, .snappy(duration: 0.18)) {
                        showAllDurationOptions.toggle()
                    }
                } label: {
                    Label(showAllDurationOptions ? "Show fewer lengths" : "More lengths", systemImage: showAllDurationOptions ? "chevron.up.circle.fill" : "ellipsis.circle.fill")
                        .font(.caption.bold())
                        .multilineTextAlignment(.center)
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                        .minimumScaleFactor(0.84)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 52 : 42)
                        .padding(.horizontal, 8)
                }
                .buttonStyle(.bordered)
                .tint(AppTheme.neonPurple)
                .accessibilityIdentifier("export.aiEdit.length.moreButton")
                .accessibilityValue(showAllDurationOptions ? "All length choices shown" : "Only common length choices shown")
                .accessibilityHint("Shows or hides longer AI edit length choices.")
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.04)
    }

    private var formatPicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            optionHeader(title: "Video Shape", value: selectedAspectRatio.rawValue)

            LazyVGrid(columns: formatGridColumns, alignment: .leading, spacing: 8) {
                ForEach(displayedAspectRatios, id: \.rawValue) { aspectRatio in
                    Button {
                        selectedAspectRatio = aspectRatio
                    } label: {
                        VStack(spacing: dynamicTypeSize.isAccessibilitySize ? 8 : 6) {
                            Image(systemName: aspectRatio.icon)
                                .font(.headline)
                                .frame(height: dynamicTypeSize.isAccessibilitySize ? 24 : 20)
                            Text(aspectRatio.title)
                                .font(.caption.bold())
                                .multilineTextAlignment(.center)
                                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                                .minimumScaleFactor(0.82)
                                .fixedSize(horizontal: false, vertical: true)
                            Text(aspectRatio.subtitle)
                                .font(.caption2)
                                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                                .minimumScaleFactor(0.84)
                                .multilineTextAlignment(.center)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .foregroundStyle(selectedAspectRatio == aspectRatio ? .white : AppTheme.subtleText)
                        .frame(maxWidth: .infinity, minHeight: formatButtonMinHeight)
                        .padding(.vertical, 10)
                        .padding(.horizontal, 6)
                        .background(selectedAspectRatio == aspectRatio ? AppTheme.accentPurple : AppTheme.cardBg, in: .rect(cornerRadius: 12))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(aspectRatio.title)
                    .accessibilityIdentifier(formatAccessibilityIdentifier(for: aspectRatio))
                    .accessibilityValue(selectedAspectRatio == aspectRatio ? "Selected" : "Not selected")
                    .accessibilityHint("Sets the AI edit output format.")
                }
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.04)
    }

    private var promptCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            promptHeader

            Label(defaultCloudEditFocusSummary, systemImage: "scope")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.white.opacity(0.9))
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                .minimumScaleFactor(0.84)
                .fixedSize(horizontal: false, vertical: true)
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(AppTheme.cardBg.opacity(0.58), in: .rect(cornerRadius: 12))
                .overlay {
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(AppTheme.softBorder, lineWidth: 1)
                }
                .accessibilityIdentifier("export.aiEdit.targetFocusSummary")

            ZStack(alignment: .topLeading) {
                TextEditor(text: $userEditPrompt)
                    .font(.subheadline)
                    .foregroundStyle(.white)
                    .scrollContentBackground(.hidden)
                    .frame(minHeight: dynamicTypeSize.isAccessibilitySize ? 132 : 96)
                    .padding(10)
                    .background(AppTheme.cardBg.opacity(0.72), in: .rect(cornerRadius: 12))
                    .overlay {
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(AppTheme.softBorder, lineWidth: 1)
                    }
                    .accessibilityIdentifier("export.aiEdit.userPrompt")
                    .accessibilityLabel(AIEditPromptCopy.accessibilityLabel)
                    .accessibilityHint(AIEditPromptCopy.accessibilityHint)
                    .onChange(of: userEditPrompt) { _, newValue in
                        if newValue.count > Self.maxUserPromptCharacters {
                            userEditPrompt = String(newValue.prefix(Self.maxUserPromptCharacters))
                        }
                }

                if userEditPrompt.isEmpty {
                    Text(AIEditPromptCopy.placeholder)
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.subtleText)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 18)
                        .allowsHitTesting(false)
                        .lineLimit(3)
                        .minimumScaleFactor(0.86)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            if let smartSetupSummary {
                Label(smartSetupSummary, systemImage: "slider.horizontal.3")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.white.opacity(0.9))
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                    .minimumScaleFactor(0.84)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AppTheme.accentPurple.opacity(0.16), in: .rect(cornerRadius: 12))
                    .overlay {
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(AppTheme.neonPurple.opacity(0.22), lineWidth: 1)
                    }
                    .accessibilityIdentifier("export.aiEdit.smartSetupSummary")
            }

            quickPromptPicker

            if let proIntentWarningText {
                Label(proIntentWarningText, systemImage: "lock.fill")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.warningYellow)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("export.aiEdit.userPrompt.proIntentWarning")
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.04)
    }

    private var quickPromptPicker: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(AIEditPromptCopy.quickFocusTitle, systemImage: "lightbulb.fill")
                .font(.caption.bold())
                .foregroundStyle(AppTheme.warningYellow)
                .lineLimit(2)
                .minimumScaleFactor(0.84)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("export.aiEdit.quickFocus.title")

            LazyVGrid(columns: quickPromptGridColumns, alignment: .leading, spacing: 8) {
                ForEach(Self.quickPrompts) { quickPrompt in
                    Button {
                        applyQuickPrompt(quickPrompt)
                    } label: {
                        Label(quickPrompt.title, systemImage: quickPrompt.icon)
                            .font(.caption.weight(.semibold))
                            .multilineTextAlignment(.center)
                            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                            .minimumScaleFactor(0.86)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 58 : 42)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .foregroundStyle(.white)
                            .background(AppTheme.accentPurple.opacity(0.20), in: .rect(cornerRadius: 12))
                            .overlay {
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(AppTheme.neonPurple.opacity(0.22), lineWidth: 1)
                            }
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("export.aiEdit.quickPrompt.\(quickPrompt.id)")
                    .accessibilityLabel("Add edit note: \(quickPrompt.title)")
                    .accessibilityHint("Adds this editing direction to the cloud AI edit note.")
                }
            }
        }
        .accessibilityElement(children: .contain)
    }

    private var promptHeader: some View {
        Group {
            if dynamicTypeSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 6) {
                    promptHeaderTitle
                    HStack(alignment: .center, spacing: 10) {
                        promptCharacterCount
                        if !userEditPrompt.isEmpty {
                            clearNoteButton
                        }
                    }
                }
            } else {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    promptHeaderTitle
                    Spacer(minLength: 8)
                    if !userEditPrompt.isEmpty {
                        clearNoteButton
                    }
                    promptCharacterCount
                }
            }
        }
    }

    private var promptHeaderTitle: some View {
        Label(AIEditPromptCopy.title, systemImage: "text.bubble.fill")
            .font(.headline)
            .foregroundStyle(.white)
            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
            .minimumScaleFactor(0.86)
            .fixedSize(horizontal: false, vertical: true)
    }

    private var promptCharacterCount: some View {
        Text("\(userEditPrompt.count)/\(Self.maxUserPromptCharacters)")
            .font(.caption2.monospacedDigit().bold())
            .foregroundStyle(userEditPrompt.count >= Self.maxUserPromptCharacters ? AppTheme.warningYellow : AppTheme.subtleText)
            .lineLimit(1)
            .minimumScaleFactor(0.76)
            .accessibilityLabel("\(userEditPrompt.count) of \(Self.maxUserPromptCharacters) characters used")
    }

    private var clearNoteButton: some View {
        Button {
            userEditPrompt = ""
        } label: {
            Label(AIEditPromptCopy.clearNoteTitle, systemImage: "xmark.circle.fill")
                .font(.caption.weight(.semibold))
                .lineLimit(1)
                .minimumScaleFactor(0.82)
        }
        .buttonStyle(.plain)
        .foregroundStyle(AppTheme.warningYellow)
        .accessibilityIdentifier("export.aiEdit.userPrompt.clear")
        .accessibilityHint(AIEditPromptCopy.clearNoteAccessibilityHint)
    }

    private func optionHeader(title: String, value: String) -> some View {
        Group {
            if dynamicTypeSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.headline)
                        .foregroundStyle(.white)
                        .lineLimit(3)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(value)
                        .font(.subheadline.monospacedDigit().bold())
                        .foregroundStyle(AppTheme.warningYellow)
                        .lineLimit(2)
                        .minimumScaleFactor(0.84)
                        .fixedSize(horizontal: false, vertical: true)
                }
            } else {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Text(title)
                        .font(.headline)
                        .foregroundStyle(.white)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 8)
                    Text(value)
                        .font(.subheadline.monospacedDigit().bold())
                        .foregroundStyle(AppTheme.warningYellow)
                        .lineLimit(1)
                        .minimumScaleFactor(0.78)
                }
            }
        }
    }

    private var quickPromptGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize.isAccessibilitySize ? 168 : 132
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 240), spacing: 8, alignment: .top)
        ]
    }

    private var heroChipGridColumns: [GridItem] {
        [
            GridItem(.adaptive(minimum: dynamicTypeSize.isAccessibilitySize ? 150 : 112), spacing: 8, alignment: .top)
        ]
    }

    private var durationGridColumns: [GridItem] {
        [
            GridItem(.adaptive(minimum: dynamicTypeSize.isAccessibilitySize ? 92 : 72, maximum: 124), spacing: 8, alignment: .top)
        ]
    }

    private var formatGridColumns: [GridItem] {
        [
            GridItem(.adaptive(minimum: dynamicTypeSize.isAccessibilitySize ? 184 : 126, maximum: 240), spacing: 8, alignment: .top)
        ]
    }

    private var formatButtonMinHeight: CGFloat {
        dynamicTypeSize.isAccessibilitySize ? 112 : 76
    }

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: statusIcon)
                    .font(.headline)
                    .foregroundStyle(statusColor)
                Text(phase.displayLabel)
                    .font(.headline)
                    .foregroundStyle(statusColor)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                    .minimumScaleFactor(0.84)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("export.aiEdit.statusLabel")
                Spacer()
                if isWorking {
                    ProgressView()
                        .tint(AppTheme.neonPurple)
                }
            }

            if let editPlan {
                Text("\(editPlan.clips.count) clips planned for \(editPlan.targetDurationSeconds)s, \(editPlan.aspectRatio.rawValue).")
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                    .minimumScaleFactor(0.84)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                Text(viewModel.cloudEditUnavailableReason ?? renderStateGuidance)
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                    .minimumScaleFactor(0.84)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let activeAIWorkPhrase {
                Label(activeAIWorkPhrase, systemImage: "sparkles")
                    .font(.caption.bold())
                    .foregroundStyle(AppTheme.warningYellow)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 3)
                    .minimumScaleFactor(0.84)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("export.aiEdit.activeWorkPhrase")
            }

            if let backgroundJobReminderText {
                Label(backgroundJobReminderText, systemImage: "rectangle.on.rectangle")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.white.opacity(0.86))
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                    .minimumScaleFactor(0.84)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("export.aiEdit.backgroundReminder")
            }

            if let renderStatus, let duration = renderStatus.durationSeconds {
                Text("Rendered duration: \(Clip.formatTime(duration))")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(AppTheme.subtleText)
            }

            if let serviceStatusMessage {
                serviceStatusBanner(message: serviceStatusMessage)
            }

            if let errorMessage {
                Text(errorMessage)
                    .font(.caption)
                    .foregroundStyle(AppTheme.dangerRed)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: statusColor.opacity(0.24), glow: statusColor, glowOpacity: 0.05)
        .accessibilityLabel("AI edit status")
        .accessibilityValue(phase.displayLabel)
    }

    private func serviceStatusBanner(message: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label {
                Text(message)
                    .font(.caption)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                    .minimumScaleFactor(0.84)
                    .fixedSize(horizontal: false, vertical: true)
            } icon: {
                Image(systemName: serviceStatusIcon)
                    .accessibilityHidden(true)
            }
            .foregroundStyle(serviceStatusColor)
            .accessibilityIdentifier("export.aiEdit.serviceStatus")

            if shouldShowCloudStatusRetry {
                Button {
                    Task { await refreshCloudEditVersion() }
                } label: {
                    Label("Retry status check", systemImage: "arrow.clockwise")
                        .font(.caption.weight(.semibold))
                        .lineLimit(2)
                        .minimumScaleFactor(0.84)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, alignment: .center)
                }
                .buttonStyle(.bordered)
                .tint(serviceStatusColor)
                .accessibilityIdentifier("export.aiEdit.retryStatus")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var aiWorkTimelineCard: some View {
        let timeline = activeWorkTimeline
        let summaryStep = timelineSummaryStep(in: timeline)
        return VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Cloud Job", systemImage: "sparkles.rectangle.stack.fill")
                    .font(.headline)
                    .foregroundStyle(.white)
                    .lineLimit(2)
                    .minimumScaleFactor(0.84)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer()
                if activePolicy.planTier != .free {
                    Text("Priority")
                        .font(.caption2.bold())
                        .foregroundStyle(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(AppTheme.successGreen.opacity(0.7), in: .capsule)
                }
            }

            timelineStepRow(summaryStep, isDetailed: false)
                .padding(10)
                .background(AppTheme.cardBg.opacity(0.58), in: .rect(cornerRadius: 12))
                .accessibilityIdentifier("export.aiEdit.timeline.current")

            if hasServerWorkTimeline {
                DisclosureGroup(isExpanded: $showTimelineDetails) {
                    VStack(alignment: .leading, spacing: 9) {
                        ForEach(timeline.steps) { step in
                            timelineStepRow(step, isDetailed: true)
                                .accessibilityIdentifier("export.aiEdit.timeline.\(step.stepId)")
                        }
                    }
                    .padding(.top, 6)
                } label: {
                    Label(showTimelineDetails ? "Hide cloud details" : "Show cloud details", systemImage: "list.bullet.clipboard.fill")
                        .font(.caption.bold())
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(2)
                        .minimumScaleFactor(0.84)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .tint(AppTheme.warningYellow)
                .accessibilityIdentifier("export.aiEdit.timeline.detailsToggle")
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.neonPurple.opacity(0.16), glow: AppTheme.neonPurple, glowOpacity: 0.05)
        .accessibilityIdentifier("export.aiEdit.timeline")
    }

    private func timelineStepRow(_ step: CloudEditWorkStep, isDetailed: Bool) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: workStepIcon(for: step.status))
                .font(.caption.bold())
                .foregroundStyle(workStepColor(for: step.status))
                .frame(width: 18)
                .padding(.top, 2)

            VStack(alignment: .leading, spacing: 2) {
                Text(step.title)
                    .font(.caption.bold())
                    .foregroundStyle(.white)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                    .minimumScaleFactor(0.84)
                    .fixedSize(horizontal: false, vertical: true)
                if let detail = step.detail, !detail.isEmpty {
                    Text(detail)
                        .font(.caption2)
                        .foregroundStyle(isDetailed ? AppTheme.subtleText : .white.opacity(0.74))
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                        .minimumScaleFactor(0.84)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 0)
        }
        .accessibilityElement(children: .combine)
    }

    private var cloudLockerCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("My AI Edits", systemImage: "externaldrive.fill")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
                Button {
                    Task { await refreshRenderHistory(showError: true) }
                } label: {
                    Image(systemName: "arrow.clockwise")
                        .font(.caption.bold())
                        .frame(width: 30, height: 30)
                }
                .buttonStyle(.bordered)
                .tint(AppTheme.neonPurple)
                .disabled(isLoadingRenderHistory)
                .accessibilityIdentifier("export.aiEdit.cloudLocker.refreshButton")
                .accessibilityLabel("Refresh My AI Edits")
            }

            if isLoadingRenderHistory && renderHistory.isEmpty {
                HStack(spacing: 10) {
                    ProgressView()
                        .tint(AppTheme.neonPurple)
                    Text("Loading latest renders")
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(12)
                .background(AppTheme.cardBg.opacity(0.62), in: .rect(cornerRadius: 12))
            } else if renderHistory.isEmpty {
                Label("Finished cloud renders will appear here after the first AI edit.", systemImage: "tray")
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .background(AppTheme.cardBg.opacity(0.62), in: .rect(cornerRadius: 12))
                    .accessibilityIdentifier("export.aiEdit.cloudLocker.empty")
            } else {
                VStack(spacing: 10) {
                    ForEach(Array(renderHistory.prefix(8)), id: \.renderJobId) { render in
                        cloudLockerRenderRow(render)
                    }
                }
            }

            Text("Cloud copies expire on your plan. Videos saved to Photos or kept in local History stay on this iPhone.")
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("export.aiEdit.cloudLocker.retentionCopy")

            if let lockerErrorMessage {
                Text(lockerErrorMessage)
                    .font(.caption)
                    .foregroundStyle(AppTheme.dangerRed)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("export.aiEdit.cloudLocker.error")
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.neonPurple.opacity(0.16), glow: AppTheme.neonPurple, glowOpacity: 0.04)
        .accessibilityIdentifier("export.aiEdit.cloudLocker")
    }

    private func cloudLockerRenderRow(_ render: CloudEditRenderStatusResponse) -> some View {
        let isBusy = lockerBusyRenderJobID == render.renderJobId
        let isExpired = isLockerRenderExpired(render)
        return VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 10) {
                VStack(alignment: .leading, spacing: 3) {
                    Text(templateDisplayName(for: render.templateId))
                        .font(.subheadline.bold())
                        .foregroundStyle(.white)
                        .lineLimit(2)
                    Text(lockerRenderSubtitle(for: render))
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 8)
                Text(isExpired ? "Expired" : lockerStatusTitle(for: render.status))
                    .font(.caption2.bold())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background((isExpired ? AppTheme.dangerRed : lockerStatusColor(for: render.status)).opacity(0.72), in: .capsule)
            }

            LazyVGrid(columns: lockerActionGridColumns, alignment: .leading, spacing: 8) {
                if render.status == .rendered {
                    Button {
                        Task { await saveLockerRenderToPhotos(render) }
                    } label: {
                        Label(
                            isExpired ? "Expired" : (isBusy && isPreparingShare ? "Saving" : "Save"),
                            systemImage: isExpired ? "exclamationmark.triangle.fill" : "photo.badge.arrow.down.fill"
                        )
                            .font(.caption.bold())
                            .multilineTextAlignment(.center)
                            .lineLimit(2)
                            .minimumScaleFactor(0.82)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 52 : 42)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(AppTheme.successGreen)
                    .disabled(isExpired || isWorking || isPreparingShare || lockerBusyRenderJobID != nil)
                    .accessibilityIdentifier("export.aiEdit.cloudLocker.save.\(render.renderJobId)")

                    Button {
                        Task { await redownloadLockerRender(render) }
                    } label: {
                        Label(
                            isExpired ? "Expired" : (isBusy && isPreparingShare ? "Preparing" : "Share"),
                            systemImage: isExpired ? "exclamationmark.triangle.fill" : "square.and.arrow.up.fill"
                        )
                            .font(.caption.bold())
                            .multilineTextAlignment(.center)
                            .lineLimit(2)
                            .minimumScaleFactor(0.82)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 52 : 42)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(AppTheme.accentPurple)
                    .disabled(isExpired || isWorking || isPreparingShare || lockerBusyRenderJobID != nil)
                    .accessibilityIdentifier("export.aiEdit.cloudLocker.download.\(render.renderJobId)")
                }

                Button {
                    Task { await rerenderLockerEdit(render) }
                } label: {
                    Label(isBusy && isWorking ? "Rendering" : "Re-render", systemImage: "arrow.triangle.2.circlepath")
                        .font(.caption.bold())
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                        .minimumScaleFactor(0.82)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 52 : 42)
                }
                .buttonStyle(.bordered)
                .tint(AppTheme.warningYellow)
                .disabled(isPreparingShare || isWorking || lockerBusyRenderJobID != nil || !canRerenderLockerRender(render))
                .accessibilityIdentifier("export.aiEdit.cloudLocker.rerender.\(render.renderJobId)")
            }
        }
        .padding(12)
        .background(AppTheme.cardBg.opacity(0.68), in: .rect(cornerRadius: 12))
        .overlay {
            RoundedRectangle(cornerRadius: 12)
                .stroke(AppTheme.softBorder, lineWidth: 1)
        }
    }

    private var lockerActionGridColumns: [GridItem] {
        [
            GridItem(.adaptive(minimum: dynamicTypeSize.isAccessibilitySize ? 156 : 104, maximum: 220), spacing: 8, alignment: .top)
        ]
    }

    private var revisionCommandGridColumns: [GridItem] {
        [
            GridItem(.adaptive(minimum: dynamicTypeSize.isAccessibilitySize ? 168 : 136, maximum: 220), spacing: 8, alignment: .top)
        ]
    }

    private func aiWorkReceiptCard(_ receipt: CloudEditWorkReceipt) -> some View {
        let receiptPlanTier = receipt.planTier ?? activePolicy.planTier
        let includesBranding = (receipt.watermarkIncluded ?? activePolicy.watermarkRequired) || (receipt.outroIncluded ?? activePolicy.outroRequired)
        return VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label(receiptPlanTier.isFree ? "AI Work Receipt" : "Pro Edit Breakdown", systemImage: "checklist.checked")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
                Text(receiptPlanTier.isFree ? "Free" : "Pro/Internal")
                    .font(.caption2.bold())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background((receiptPlanTier.isFree ? AppTheme.cardBg : AppTheme.successGreen.opacity(0.7)), in: .capsule)
            }

            Text(receiptPlanSummary(for: receipt))
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
                .fixedSize(horizontal: false, vertical: true)

            VStack(alignment: .leading, spacing: 7) {
                ForEach(receiptRows(for: receipt), id: \.self) { row in
                    Label(row, systemImage: "checkmark.circle.fill")
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            if receiptPlanTier.isFree, includesBranding, proUXFlags.proUpsellEnabled {
                Button {
                    if onRequestProUpgrade != nil {
                        requestProUpgrade()
                    } else {
                        proInfoSheet = .benefits
                    }
                } label: {
                    Label("Free export includes HoopClips branding. Upgrade to remove watermark/outro.", systemImage: "crown.fill")
                        .font(.caption2.bold())
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(10)
                        .background(AppTheme.accentPurple.opacity(0.25), in: .rect(cornerRadius: 12))
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("export.aiEdit.watermarkUpsell")
            }

            if !receiptPlanTier.isFree {
                Label("Clean export: no required watermark/outro when policy allows.", systemImage: "sparkles")
                    .font(.caption.bold())
                    .foregroundStyle(AppTheme.successGreen)
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.successGreen.opacity(0.2), glow: AppTheme.successGreen, glowOpacity: 0.05)
        .accessibilityIdentifier("export.aiEdit.workReceipt")
    }

    private func previewCard(player: AVPlayer) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 12) {
                Text("Preview")
                    .font(.headline)
                    .foregroundStyle(.white)

                Spacer()

                Button {
                    previewAudioMuted.toggle()
                    applyPreviewAudioMute()
                } label: {
                    Label(previewAudioMuted ? "Unmute" : "Mute", systemImage: previewAudioMuted ? "speaker.slash.fill" : "speaker.wave.2.fill")
                        .font(.caption.weight(.semibold))
                }
                .buttonStyle(.plain)
                .foregroundStyle(.white)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(.white.opacity(0.12), in: Capsule())
                .accessibilityIdentifier("export.aiEdit.preview.muteToggle")
                .accessibilityLabel(previewAudioMuted ? "Unmute preview" : "Mute preview")
            }

            VideoPlayer(player: player)
                .frame(height: 320)
                .clipShape(.rect(cornerRadius: 18))
                .overlay {
                    RoundedRectangle(cornerRadius: 18)
                        .stroke(AppTheme.accentPurple.opacity(0.28), lineWidth: 1)
                }
                .accessibilityIdentifier("export.aiEdit.preview")
                .accessibilityLabel("Rendered AI edit preview")
                .accessibilityHint("Plays the cloud-rendered video.")
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.04)
    }

    private func applyPreviewAudioMute() {
        previewPlayer?.isMuted = previewAudioMuted
        previewPlayer?.volume = previewAudioMuted ? 0 : 1
    }

    private var proBenefitsSheet: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.12)
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        Label("HoopClips Pro", systemImage: "crown.fill")
                            .font(.title2.bold())
                            .foregroundStyle(.white)
                            .accessibilityIdentifier("export.aiEdit.proInfoSheet")

                        Text("Pro unlocks the faster, cleaner cloud editing tier with App Store in-app purchase.")
                            .font(.subheadline)
                            .foregroundStyle(AppTheme.subtleText)
                            .fixedSize(horizontal: false, vertical: true)

                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(CloudEditPolicySummary.proValueRows, id: \.self) { row in
                                Label(row, systemImage: "checkmark.seal.fill")
                                    .font(.subheadline.bold())
                                    .foregroundStyle(.white)
                            }
                        }
                        .padding(14)
                        .background(AppTheme.cardBg.opacity(0.72), in: .rect(cornerRadius: 16))

                        Text("Free still works: it uses the standard queue, includes HoopClips branding, and stores rendered videos temporarily.")
                            .font(.caption)
                            .foregroundStyle(AppTheme.warningYellow)
                            .fixedSize(horizontal: false, vertical: true)

                        if onRequestProUpgrade != nil {
                            Button {
                                requestProUpgrade()
                            } label: {
                                Label("Upgrade with App Store", systemImage: "crown.fill")
                                    .font(.headline)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 12)
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(AppTheme.warningYellow)
                            .accessibilityIdentifier("export.aiEdit.proInfoSheet.upgradeButton")
                        }
                    }
                    .padding(18)
                }
            }
            .navigationTitle("Pro Benefits")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Close") { proInfoSheet = nil }
                }
            }
        }
        .accessibilityIdentifier("export.aiEdit.proInfoSheet")
    }

    private func proTemplateInfoSheet(for template: CloudEditProTemplate) -> some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.12)
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        Label(template.title, systemImage: template.icon)
                            .font(.title2.bold())
                            .foregroundStyle(.white)
                            .accessibilityIdentifier("export.aiEdit.proInfoSheet")

                        Text(template.subtitle)
                            .font(.headline)
                            .foregroundStyle(AppTheme.warningYellow)

                        Text(template.bestFor)
                            .font(.subheadline)
                            .foregroundStyle(AppTheme.subtleText)
                            .fixedSize(horizontal: false, vertical: true)

                        Text(template.styleSummary)
                            .font(.subheadline)
                            .foregroundStyle(AppTheme.subtleText)
                            .fixedSize(horizontal: false, vertical: true)

                        VStack(alignment: .leading, spacing: 8) {
                            Text("Available with Pro")
                                .font(.headline)
                                .foregroundStyle(.white)
                            Text("This template unlocks with Pro and uses HoopClips cloud to make the finished video.")
                                .font(.caption)
                                .foregroundStyle(AppTheme.subtleText)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .padding(14)
                        .background(AppTheme.cardBg.opacity(0.72), in: .rect(cornerRadius: 16))

                        if onRequestProUpgrade != nil {
                            Button {
                                requestProUpgrade()
                            } label: {
                                Label("Upgrade with App Store", systemImage: "crown.fill")
                                    .font(.headline)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 12)
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(AppTheme.warningYellow)
                            .accessibilityIdentifier("export.aiEdit.proInfoSheet.upgradeButton")
                        }
                    }
                    .padding(18)
                }
            }
            .navigationTitle("Pro Template")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Close") { proInfoSheet = nil }
                }
            }
        }
        .accessibilityIdentifier("export.aiEdit.proInfoSheet")
    }

    private func requestProUpgrade() {
        proInfoSheet = nil
        Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(180))
            onRequestProUpgrade?()
        }
    }

    private var actionCard: some View {
        VStack(spacing: 10) {
            if let errorMessage {
                Text(errorMessage)
                    .font(.caption)
                    .foregroundStyle(AppTheme.dangerRed)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("export.aiEdit.failure.reasonLabel")
            }

            Button(action: startEdit) {
                fullWidthActionLabel(primaryActionTitle, systemImage: primaryActionIcon)
            }
            .buttonStyle(.borderedProminent)
            .tint(AppTheme.accentPurple)
            .disabled(primaryActionDisabled)
            .accessibilityIdentifier(revisionResponse != nil && downloadResponse == nil ? "export.aiEdit.renderRevisionButton" : "export.aiEdit.generateButton")
            .accessibilityHint(primaryActionHint)

            if phase == .failed {
                Button(action: startEdit) {
                    fullWidthActionLabel(
                        "Try Again",
                        systemImage: "arrow.clockwise",
                        font: .caption.bold(),
                        minimumHeight: 40,
                        verticalPadding: 10
                    )
                }
                .buttonStyle(.bordered)
                .tint(AppTheme.warningYellow)
                .disabled(primaryActionDisabled)
                .accessibilityIdentifier("export.aiEdit.retryButton")
                .accessibilityHint("Retries the cloud job when HoopClips allows it.")
            }

            if downloadResponse != nil {
                Button {
                    Task { await saveRenderedVideoToPhotos() }
                } label: {
                    fullWidthActionLabel(
                        "Save to Photos",
                        systemImage: "photo.badge.arrow.down.fill",
                        verticalPadding: 12
                    )
                }
                .buttonStyle(.borderedProminent)
                .tint(AppTheme.successGreen)
                .disabled(isPreparingShare || viewModel.exportService.exportedURL == nil)
                .accessibilityIdentifier("export.aiEdit.saveToPhotosButton")
                .accessibilityHint("Saves the finished video to your photo library.")

                Button(action: shareRenderedVideo) {
                    fullWidthActionLabel(
                        isPreparingShare ? "Preparing" : "Share",
                        systemImage: "square.and.arrow.up.fill",
                        verticalPadding: 12
                    )
                }
                .buttonStyle(.bordered)
                .tint(AppTheme.neonPurple)
                .disabled(isPreparingShare)
                .accessibilityIdentifier("export.aiEdit.shareButton")
                .accessibilityHint("Downloads the finished video and opens the system share sheet for editors, Files, Photos, and social apps.")
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.04)
    }

    private func fullWidthActionLabel(
        _ title: String,
        systemImage: String,
        font: Font = .headline,
        minimumHeight: CGFloat = 46,
        verticalPadding: CGFloat = 14
    ) -> some View {
        Label(title, systemImage: systemImage)
            .font(font)
            .multilineTextAlignment(.center)
            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
            .minimumScaleFactor(0.82)
            .fixedSize(horizontal: false, vertical: true)
            .frame(
                maxWidth: .infinity,
                minHeight: dynamicTypeSize.isAccessibilitySize ? minimumHeight + 10 : minimumHeight
            )
            .padding(.vertical, verticalPadding)
    }

    private var revisionCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Revise Edit")
                        .font(.headline)
                        .foregroundStyle(.white)
                        .accessibilityIdentifier("export.aiEdit.revision.card")
                    Text(revisionStatusText)
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer()
            }

            LazyVGrid(columns: revisionCommandGridColumns, alignment: .leading, spacing: 8) {
                ForEach(revisionCommands) { command in
                    Button {
                        requestRevision(command)
                    } label: {
                        Label(command.title, systemImage: command.icon)
                            .font(.caption.bold())
                            .foregroundStyle(pendingRevisionCommand == command ? .white : AppTheme.subtleText)
                            .multilineTextAlignment(.leading)
                            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                            .minimumScaleFactor(0.84)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 10)
                            .background(pendingRevisionCommand == command ? AppTheme.accentPurple.opacity(0.92) : AppTheme.cardBg.opacity(0.78), in: .rect(cornerRadius: 12))
                    }
                    .buttonStyle(.plain)
                    .disabled(isWorking || !aiEditRevisionsAvailable)
                    .accessibilityElement(children: .ignore)
                    .accessibilityIdentifier(command.accessibilityIdentifier)
                    .accessibilityLabel(command.title)
                    .accessibilityHint("Asks the cloud AI edit agent to revise the current edit plan.")
                }
            }

            if let revisionResponse {
                Text(revisionResponse.patch.summary)
                    .font(.caption)
                    .foregroundStyle(AppTheme.warningYellow)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("export.aiEdit.revision.summaryLabel")

                if let plannerText = revisionPlannerText(for: revisionResponse) {
                    Text(plannerText)
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("export.aiEdit.revision.plannerLabel")
                }
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.neonPurple.opacity(0.18), glow: AppTheme.neonPurple, glowOpacity: 0.05)
    }

    private var statusIcon: String {
        switch phase {
        case .rendered:
            return "checkmark.seal.fill"
        case .failed, .failedTimeout, .cancelled:
            return "exclamationmark.triangle.fill"
        case .renderRequested, .planning, .planReady, .created, .queued, .rendering:
            return "cloud.fill"
        }
    }

    private var statusColor: Color {
        switch phase {
        case .rendered:
            return AppTheme.successGreen
        case .failed, .failedTimeout, .cancelled:
            return AppTheme.dangerRed
        case .renderRequested, .planning, .planReady, .created, .queued, .rendering:
            return AppTheme.neonPurple
        }
    }

    private var activeWorkTimeline: CloudEditWorkTimeline {
        if let serverTimeline = renderStatus?.workTimeline {
            return serverTimeline
        }

        let planReady = editPlan != nil
        let renderJobID = renderStatus?.renderJobId
        let editJobID = editJob?.editJobId ?? editPlan?.editJobId ?? "pending"
        let failed = phase == .failed || phase == .failedTimeout || phase == .cancelled
        let templateName = selectedTemplateTitle
        let selectedClipCount = editPlan?.clips.count
        let candidateClipCount = viewModel.cloudEditCandidatePoolCount
        let slowMotionCount = editPlan.map(slowMotionMomentCount(in:)) ?? 0
        let brandingDetail = editPlan.map { plan in
            "\(plan.watermark.enabled ? "Watermark included" : "Watermark not included"), \(plan.outro.enabled ? "outro included" : "outro not included")."
        }

        return CloudEditWorkTimeline(
            editJobId: editJobID,
            revisionId: revisionResponse?.revisionId,
            renderJobId: renderJobID,
            status: phase,
            generatedAt: nil,
            steps: [
                CloudEditWorkStep(
                    stepId: "video_uploaded",
                    title: "Uploaded game video",
                    detail: viewModel.cloudEditSourceObjectKey == nil ? nil : "Cloud source is ready for editing.",
                    status: viewModel.cloudEditSourceObjectKey == nil ? (failed ? .failed : .pending) : .complete,
                    startedAt: nil,
                    completedAt: nil
                ),
                CloudEditWorkStep(
                    stepId: "finding_highlights",
                    title: "Finding your best plays",
                    detail: "Reviewed \(candidateClipCount) candidate clips.",
                    status: candidateClipCount > 0 ? .complete : (isWorking ? .running : .pending),
                    startedAt: nil,
                    completedAt: nil
                ),
                CloudEditWorkStep(
                    stepId: "selecting_best_clips",
                    title: "Selecting strongest clips",
                    detail: selectedClipCount.map { "Selected \($0) clips from \(candidateClipCount) candidates." },
                    status: planReady ? .complete : (isWorking ? .running : (failed ? .failed : .pending)),
                    startedAt: nil,
                    completedAt: nil
                ),
                CloudEditWorkStep(
                    stepId: "removing_duplicates",
                    title: "Checking duplicate plays",
                    detail: "Kept clips are reviewed before the edit plan is rendered.",
                    status: planReady ? .complete : (failed ? .failed : .pending),
                    startedAt: nil,
                    completedAt: nil
                ),
                CloudEditWorkStep(
                    stepId: "applying_template",
                    title: "Applying \(templateName) style",
                    detail: "Template: \(templateName).",
                    status: planReady ? .complete : (failed ? .failed : .pending),
                    startedAt: nil,
                    completedAt: nil
                ),
                CloudEditWorkStep(
                    stepId: "adding_slow_motion",
                    title: "Adding slow motion",
                    detail: "Slow-motion moments: \(slowMotionCount).",
                    status: planReady ? .complete : (failed ? .failed : .pending),
                    startedAt: nil,
                    completedAt: nil
                ),
                CloudEditWorkStep(
                    stepId: "adding_watermark_outro",
                    title: "Adding HoopClips branding",
                    detail: brandingDetail,
                    status: planReady ? .complete : (failed ? .failed : .pending),
                    startedAt: nil,
                    completedAt: nil
                ),
                CloudEditWorkStep(
                    stepId: "rendering_mp4",
                    title: "Making final video",
                    detail: phase == .rendered ? "HoopClips finished the video." : "HoopClips is creating the video.",
                    status: renderingStepStatus,
                    startedAt: nil,
                    completedAt: nil
                ),
                CloudEditWorkStep(
                    stepId: "finalizing_download",
                    title: "Finalizing your video",
                    detail: downloadResponse == nil ? nil : "Download is ready for preview and sharing.",
                    status: finalizingStepStatus,
                    startedAt: nil,
                    completedAt: nil
                ),
            ]
        )
    }

    private var shouldShowAIWorkTimeline: Bool {
        hasStartedAIEditJob || hasServerWorkTimeline
    }

    private var shouldShowCloudLocker: Bool {
        proUXFlags.cloudLockerEnabled && (hasStartedAIEditJob || !renderHistory.isEmpty)
    }

    private var hasStartedAIEditJob: Bool {
        isWorking || editJob != nil || editPlan != nil || renderStatus != nil || revisionResponse != nil
    }

    private var hasServerWorkTimeline: Bool {
        renderStatus?.workTimeline != nil
    }

    private var activeWorkReceipt: CloudEditWorkReceipt? {
        if let serverReceipt = renderStatus?.workReceipt {
            return serverReceipt
        }
        guard phase == .rendered || downloadResponse != nil else { return nil }
        guard let editPlan else { return nil }
        let policy = activePolicy
        let slowMotionCount = slowMotionMomentCount(in: editPlan)
        let outputDuration = renderStatus?.durationSeconds
        let storageExpiresAt = renderStatus?.retentionMetadata?.expiresAt
        let selectedClipCount = editPlan.clips.count
        let candidateClipCount = viewModel.cloudEditCandidatePoolCount
        var rows = [
            "Rendered with \(policy.displayName) plan limits.",
            "\(policy.queueTitle): \(policy.queueDetail)",
            "Selected \(selectedClipCount) clips from \(candidateClipCount) candidates.",
            "Applied \(selectedTemplateTitle) template.",
            "Added \(slowMotionCount) slow-motion moments.",
            "Export limit: \(policy.maxOutputResolution).",
            "Branding: \(editPlan.watermark.enabled ? "watermark included" : "watermark removed"), \(editPlan.outro.enabled ? "outro included" : "outro removed").",
            "Revision limit: \(policy.maxRevisionsPerEdit) per edit.",
        ]
        if let outputDuration {
            rows.insert("Finished \(Clip.formatTime(outputDuration)) video.", at: 5)
        }
        if let storageExpiresAt {
            rows.append("Stored until \(storageExpiresAt).")
        } else {
            rows.append(policy.retentionSummary + ".")
        }

        return CloudEditWorkReceipt(
            editJobId: editJob?.editJobId ?? editPlan.editJobId,
            revisionId: revisionResponse?.revisionId,
            renderJobId: renderStatus?.renderJobId,
            selectedClipCount: selectedClipCount,
            candidateClipCount: candidateClipCount,
            templateId: editPlan.templateId,
            templateName: selectedTemplateTitle,
            slowMotionMomentCount: slowMotionCount,
            outputDurationSeconds: outputDuration,
            outputResolution: policy.maxOutputResolution,
            aspectRatio: editPlan.aspectRatio,
            watermarkIncluded: editPlan.watermark.enabled,
            outroIncluded: editPlan.outro.enabled,
            storageExpiresAt: storageExpiresAt,
            planTier: policy.planTier,
            priorityQueue: policy.planTier != .free,
            gptRerankApplied: nil,
            gptRerankModel: nil,
            gptRerankSampledClipCount: nil,
            gptRerankSampledFrameCount: nil,
            gptRerankKeptClipCount: nil,
            gptRerankRejectedClipCount: nil,
            gptRerankFallbackReason: nil,
            gptUncertainReviewClipCount: nil,
            gptUncertainReviewClipIds: nil,
            teamUncertainCandidateCount: nil,
            teamUncertainSelectedClipCount: nil,
            defensiveSelectedClipCount: nil,
            timingQualitySelectedClipCount: nil,
            timingIssueCandidateCount: nil,
            timingIssueSelectedClipCount: nil,
            shotOutcomeEvidenceSelectedClipCount: nil,
            shotOutcomeIssueSelectedClipCount: nil,
            labelOnlyOutcomeSelectedClipCount: nil,
            summaryRows: rows
        )
    }

    private var renderingStepStatus: CloudEditWorkStepStatus {
        switch phase {
        case .rendered:
            return .complete
        case .failed, .failedTimeout, .cancelled:
            return .failed
        case .renderRequested, .created, .queued, .rendering:
            return .running
        case .planning, .planReady:
            return .pending
        }
    }

    private var finalizingStepStatus: CloudEditWorkStepStatus {
        if downloadResponse != nil {
            return .complete
        }
        switch phase {
        case .rendered:
            return .running
        case .failed, .failedTimeout, .cancelled:
            return .failed
        case .renderRequested, .planning, .planReady, .created, .queued, .rendering:
            return .pending
        }
    }

    private func slowMotionMomentCount(in plan: CloudEditPlanSummary) -> Int {
        plan.clips.reduce(0) { count, clip in
            count + clip.effects.filter { $0.type == "slow_motion" }.count
        }
    }

    private func timelineSummaryStep(in timeline: CloudEditWorkTimeline) -> CloudEditWorkStep {
        if let failedStep = timeline.steps.first(where: { $0.status == .failed }) {
            return failedStep
        }
        if let runningStep = timeline.steps.first(where: { $0.status == .running }) {
            return runningStep
        }
        if phase == .rendered,
           let completedStep = timeline.steps.last(where: { $0.status == .complete }) {
            return completedStep
        }
        if let pendingStep = timeline.steps.first(where: { $0.status == .pending }) {
            return pendingStep
        }
        return timeline.steps.last ?? CloudEditWorkStep(
            stepId: "status",
            title: phase.displayLabel,
            detail: renderStateGuidance,
            status: phase == .rendered ? .complete : (phase == .failed || phase == .failedTimeout || phase == .cancelled ? .failed : .pending),
            startedAt: nil,
            completedAt: nil
        )
    }

    private func workStepIcon(for status: CloudEditWorkStepStatus) -> String {
        switch status {
        case .pending:
            return "circle"
        case .running:
            return "sparkles"
        case .complete:
            return "checkmark.circle.fill"
        case .failed:
            return "xmark.octagon.fill"
        }
    }

    private func workStepColor(for status: CloudEditWorkStepStatus) -> Color {
        switch status {
        case .pending:
            return AppTheme.subtleText.opacity(0.55)
        case .running:
            return AppTheme.warningYellow
        case .complete:
            return AppTheme.successGreen
        case .failed:
            return AppTheme.dangerRed
        }
    }

    private func receiptPlanSummary(for receipt: CloudEditWorkReceipt) -> String {
        let policy = activePolicy
        let tier = receipt.planTier ?? policy.planTier
        if tier.isFree {
            return "Rendered with Free plan limits: \(policy.maxOutputResolution), standard queue, and \(policy.brandingSummary.lowercased())."
        }
        return "Rendered with priority cloud editing when available, \(policy.maxOutputResolution), and \(policy.brandingSummary.lowercased())."
    }

    private func receiptRows(for receipt: CloudEditWorkReceipt) -> [String] {
        var rows: [String] = receipt.summaryRows
        if let selected = receipt.selectedClipCount, let candidates = receipt.candidateClipCount {
            rows.appendIfMissing("Selected \(selected) clips from \(candidates) candidates.")
        }
        if let templateName = receipt.templateName {
            rows.appendIfMissing("Applied \(templateName) template.")
        }
        rows.appendIfMissing("Added \(receipt.slowMotionMomentCount) slow-motion moments.")
        if let duration = receipt.outputDurationSeconds {
            rows.appendIfMissing("Finished \(Clip.formatTime(duration)) video.")
        }
        if let outputResolution = receipt.outputResolution {
            rows.appendIfMissing("Export limit: \(outputResolution).")
        }
        if let watermark = receipt.watermarkIncluded, let outro = receipt.outroIncluded {
            rows.appendIfMissing("Branding: \(watermark ? "watermark included" : "watermark removed"), \(outro ? "outro included" : "outro removed").")
        }
        if let storageExpiresAt = receipt.storageExpiresAt {
            rows.appendIfMissing("Stored until \(storageExpiresAt).")
        }
        if let planTier = receipt.planTier {
            rows.appendIfMissing(planTier.isFree ? "Rendered on the standard queue." : "Priority queue enabled when available.")
        }
        let uncertainReviewCount = receipt.gptUncertainReviewClipCount ?? receipt.gptUncertainReviewClipIds?.count
        if let uncertainReviewCount, uncertainReviewCount > 0 {
            rows.appendIfMissing("Kept \(uncertainReviewCount) uncertain team candidate\(uncertainReviewCount == 1 ? "" : "s") available for Review.")
        }
        if let evidenceCount = receipt.shotOutcomeEvidenceSelectedClipCount, evidenceCount > 0 {
            rows.appendIfMissing("Shot outcome evidence: \(evidenceCount) selected \(evidenceCount == 1 ? "clip" : "clips") passed rim/result tracking checks.")
        }
        if let labelOnlyCount = receipt.labelOnlyOutcomeSelectedClipCount, labelOnlyCount > 0 {
            rows.appendIfMissing("Needs review: \(labelOnlyCount) selected shot \(labelOnlyCount == 1 ? "outcome" : "outcomes") came from label-only evidence.")
        } else if let issueCount = receipt.shotOutcomeIssueSelectedClipCount, issueCount > 0 {
            rows.appendIfMissing("Needs review: \(issueCount) selected shot \(issueCount == 1 ? "outcome" : "outcomes") had weak result evidence.")
        }
        return rows
    }

    private func templateDisplayName(for templateID: String?) -> String {
        guard let templateID else { return "AI Edit" }
        if let preset = CloudEditPreset.allCases.first(where: { $0.templateID == templateID }) {
            return preset.title
        }
        if let template = CloudEditProTemplate.allCases.first(where: { $0.templateID == templateID }) {
            return template.title
        }
        return templateID
            .replacingOccurrences(of: "_", with: " ")
            .capitalized
    }

    private func lockerRenderSubtitle(for render: CloudEditRenderStatusResponse) -> String {
        var parts: [String] = []
        if let duration = render.durationSeconds {
            parts.append(Clip.formatTime(duration))
        }
        parts.append(render.aspectRatio.rawValue)
        if let expiresAt = render.retentionMetadata?.expiresAt ?? render.workReceipt?.storageExpiresAt {
            parts.append("Expires \(formattedLockerDate(expiresAt))")
        } else {
            let policy = render.policy ?? activePolicy
            parts.append(policy.retentionSummary)
        }
        if render.revisionId != nil {
            parts.append("Revised")
        }
        return parts.joined(separator: " - ")
    }

    private func isLockerRenderExpired(_ render: CloudEditRenderStatusResponse, now: Date = Date()) -> Bool {
        guard let expirationDate = lockerExpirationDate(for: render) else { return false }
        return expirationDate <= now
    }

    private func lockerExpirationDate(for render: CloudEditRenderStatusResponse) -> Date? {
        guard let rawValue = render.retentionMetadata?.expiresAt ?? render.workReceipt?.storageExpiresAt else { return nil }
        return parsedLockerDate(rawValue)
    }

    private func formattedLockerDate(_ rawValue: String) -> String {
        if let date = parsedLockerDate(rawValue) {
            return date.formatted(date: .abbreviated, time: .shortened)
        }
        return String(rawValue.replacingOccurrences(of: "T", with: " ").prefix(16))
    }

    private func parsedLockerDate(_ rawValue: String) -> Date? {
        let normalized = rawValue.replacingOccurrences(of: "+00:00", with: "Z")
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: normalized) ?? {
            formatter.formatOptions = [.withInternetDateTime]
            return formatter.date(from: normalized)
        }()
    }

    private func lockerStatusTitle(for status: CloudEditRenderState) -> String {
        switch status {
        case .rendered:
            return "Ready"
        case .failed:
            return "Failed"
        case .failedTimeout:
            return "Timed out"
        case .cancelled:
            return "Cancelled"
        case .rendering:
            return "Rendering"
        case .queued:
            return "Queued"
        case .renderRequested, .created:
            return "Requested"
        case .planning, .planReady:
            return "Planning"
        }
    }

    private func lockerStatusColor(for status: CloudEditRenderState) -> Color {
        switch status {
        case .rendered:
            return AppTheme.successGreen
        case .failed, .failedTimeout, .cancelled:
            return AppTheme.dangerRed
        case .renderRequested, .planning, .planReady, .created, .queued, .rendering:
            return AppTheme.neonPurple
        }
    }

    private func canRerenderLockerRender(_ render: CloudEditRenderStatusResponse) -> Bool {
        guard aiEditLiveRenderingAvailable else { return false }
        switch render.status {
        case .renderRequested, .created, .queued, .rendering:
            return false
        case .planning, .planReady, .rendered, .failed, .failedTimeout, .cancelled:
            return true
        }
    }

    private var aiEditPlanningAvailable: Bool {
        serviceVersion?.featureFlags?.allowsEditPlanning ?? true
    }

    private var aiEditLiveRenderingAvailable: Bool {
        serviceVersion?.featureFlags?.allowsLiveRendering ?? true
    }

    private var aiEditRevisionsAvailable: Bool {
        serviceVersion?.featureFlags?.allowsRevisions ?? true
    }

    private var aiEditTemplatePacksAvailable: Bool {
        serviceVersion?.featureFlags?.allowsTemplatePacks ?? true
    }

    private var gptEditingReadinessMessage: String? {
        guard let flags = serviceVersion?.featureFlags else { return nil }
        if !flags.allowsGptClipEditing {
            return "AI clip selection is temporarily paused by HoopClips."
        }
        if !flags.allowsGptPlanEditing {
            return "AI edit planning is temporarily paused by HoopClips."
        }
        if !flags.allowsGptRevisionEditing {
            return "AI revision planning is temporarily paused by HoopClips."
        }
        return nil
    }

    private var cloudEditActionBlockedMessage: String? {
        if let cloudEditVersionBlockMessage {
            return cloudEditVersionBlockMessage
        }
        if let launchReadinessFlagMessage {
            return launchReadinessFlagMessage
        }
        if !aiEditPlanningAvailable {
            return CloudEditError.friendlyBackendMessage(
                code: "ai_edit_disabled",
                fallback: "Cloud AI editing is temporarily paused."
            )
        }
        if !aiEditLiveRenderingAvailable {
            return CloudEditError.friendlyBackendMessage(
                code: "ai_edit_live_render_disabled",
                fallback: "Cloud rendering is temporarily paused."
            )
        }
        if !aiEditTemplatePacksAvailable {
            return CloudEditError.friendlyBackendMessage(
                code: "ai_edit_template_pack_disabled",
                fallback: "Cloud template packs are temporarily paused."
            )
        }
        if let gptEditingReadinessMessage {
            return gptEditingReadinessMessage
        }
        return nil
    }

    private var launchReadinessFlagMessage: String? {
        guard let flags = serviceVersion?.featureFlags, !flags.hasRequiredLaunchReadinessFlags else { return nil }
        return "HoopClips cloud is missing required launch flags; deploy the current service before TestFlight smoke."
    }

    private var cloudEditVersionBlockMessage: String? {
        guard AppConstants.cloudEditEnabled else { return nil }
        guard serviceStatusBlocksRendering else { return nil }
        if let serviceStatusErrorMessage {
            return "Cloud editing config check failed: \(serviceStatusErrorMessage)"
        }
        return "Cloud editing config check failed."
    }

    private var primaryActionDisabled: Bool {
        isWorking || !viewModel.canRequestCloudEdit || cloudEditActionBlockedMessage != nil
    }

    private var primaryActionHint: String {
        cloudEditActionBlockedMessage
            ?? viewModel.cloudEditUnavailableReason
            ?? "Requests a cloud edit plan and render."
    }

    private var serviceStatusMessage: String? {
        if let cloudEditActionBlockedMessage {
            return cloudEditActionBlockedMessage
        }
        if serviceStatusIsChecking {
            return "Checking cloud status. You can still start the edit."
        }
        if !aiEditRevisionsAvailable {
            return "AI edit revisions are temporarily paused by HoopClips."
        }
        if let serviceStatusErrorMessage {
            return serviceStatusErrorMessage
        }
        return nil
    }

    private var serviceStatusIcon: String {
        if cloudEditActionBlockedMessage != nil {
            return "exclamationmark.triangle.fill"
        }
        if serviceStatusIsChecking {
            return "arrow.clockwise.circle"
        }
        if serviceStatusErrorMessage != nil {
            return serviceStatusBlocksRendering ? "exclamationmark.triangle" : "info.circle.fill"
        }
        return "pause.circle"
    }

    private var serviceStatusColor: Color {
        cloudEditActionBlockedMessage == nil ? AppTheme.warningYellow : AppTheme.dangerRed
    }

    private var shouldShowCloudStatusRetry: Bool {
        serviceStatusErrorMessage != nil
            && !serviceStatusBlocksRendering
            && !serviceStatusIsChecking
    }

    private var revisionCommands: [CloudEditRevisionCommand] {
        [
            .makeShorter,
            .makeLonger,
            .makeMoreHype,
            .makeNBAStyle,
            .addMoreSlowMotion,
            .useOriginalAudio,
            .removeWeakClips,
            .switchFormatVertical,
            .switchFormatWidescreen,
        ]
    }

    private var primaryActionTitle: String {
        if cloudEditVersionBlockMessage != nil {
            return "Fix Cloud Config"
        }
        if launchReadinessFlagMessage != nil {
            return "Update Cloud Backend"
        }
        if !aiEditPlanningAvailable {
            return "AI Edit Paused"
        }
        if !aiEditLiveRenderingAvailable {
            return "Cloud Rendering Paused"
        }
        if !aiEditTemplatePacksAvailable {
            return "Templates Paused"
        }
        if gptEditingReadinessMessage != nil {
            return "AI Editing Paused"
        }
        if !viewModel.canRequestCloudEdit {
            return "Finish Cloud Analysis"
        }
        if revisionResponse != nil, downloadResponse == nil {
            return "Make Revised Video"
        }
        return downloadResponse == nil ? "Make My Reel" : "Render Again"
    }

    private var clipPoolChipText: String {
        if viewModel.keptClips.isEmpty {
            return "\(viewModel.cloudEditCandidatePoolCount) AI candidates"
        }
        return "\(viewModel.keptClips.count) kept clips"
    }

    private var primaryActionIcon: String {
        if cloudEditActionBlockedMessage != nil {
            return "pause.circle.fill"
        }
        return revisionResponse != nil && downloadResponse == nil ? "arrow.triangle.2.circlepath.circle.fill" : "sparkles.tv.fill"
    }

    private var revisionStatusText: String {
        if let pendingRevisionCommand, revisionResponse != nil, downloadResponse == nil {
            return "\(pendingRevisionCommand.title) revision is ready. Make the new video when you are ready."
        }
        if let pendingRevisionCommand {
            return "Last revision: \(pendingRevisionCommand.title). Pick another change or make it again."
        }
        return "Ask HoopClips for a cleaner edit, then make the revised video."
    }

    private func revisionPlannerText(for response: CloudEditRevisionResponse) -> String? {
        if response.gptRevisionPatchApplied == true {
            return "HoopClips planned this revision and is ready to render it."
        }
        switch response.gptRevisionPatchStatus {
        case "fallback":
            if let reason = response.gptRevisionPatchFallbackReason, !reason.isEmpty {
                return "HoopClips used the safe revision path: \(reason.replacingOccurrences(of: "_", with: " "))."
            }
            return "HoopClips used the safe revision path."
        case "disabled":
            return "HoopClips used the standard revision path."
        case "rejected":
            return "HoopClips could not safely apply that revision."
        case "not_requested":
            return "Deterministic revision patch."
        default:
            return nil
        }
    }

    private var activePolicy: CloudEditPolicySummary {
        policySummary ?? (isProUser ? .proDefault : .freeDefault)
    }

    private var selectedTemplateID: String {
        selectedProTemplate?.templateID ?? selectedPreset.templateID
    }

    private var selectedTemplateTitle: String {
        selectedProTemplate?.title ?? selectedPreset.title
    }

    private var selectedSetupSummary: String {
        "\(selectedTemplateTitle) - \(selectedAspectRatio.rawValue) - \(formattedDuration(selectedDuration))."
    }

    private var aiEditDetailsSummary: String {
        let policy = activePolicy
        var summary = [
            "\(policy.displayName): \(policy.maxDailyRenders) edits/day",
            policy.maxOutputResolution,
            policy.brandingSummary,
        ]

        if hasStartedAIEditJob {
            summary.append("cloud status")
        }
        if activeWorkReceipt != nil {
            summary.append("receipt")
        }
        if shouldShowCloudLocker {
            summary.append("locker")
        }

        return summary.joined(separator: " - ")
    }

    private var teamTargetChipText: String {
        let selection = viewModel.settings.highlightTeamSelection
        if selection.mode == .team {
            return "Team: \(selection.displayTitle)"
        }
        return "All teams"
    }

    private var sanitizedUserEditPrompt: String? {
        CloudEditUserPromptBuilder.effectivePrompt(
            userPrompt: userEditPrompt,
            teamSelection: viewModel.settings.highlightTeamSelection,
            maxCharacters: Self.maxUserPromptCharacters
        )
    }

    private var defaultCloudEditFocusSummary: String {
        CloudEditUserPromptBuilder.defaultFocusSummary(
            teamSelection: viewModel.settings.highlightTeamSelection
        )
    }

    private var smartSetupSummary: String? {
        let intent = CloudEditUserIntent.parse(userEditPrompt)
        guard intent.hasStructuredChoices else { return nil }

        var parts: [String] = []
        let intendedTemplateID: String
        if let proTemplate = intent.proTemplate {
            if activePolicy.premiumTemplatesAllowed {
                parts.append(proTemplate.title)
                intendedTemplateID = proTemplate.templateID
            } else {
                parts.append("Closest free style: \(proTemplate.preset.title)")
                intendedTemplateID = proTemplate.preset.templateID
            }
        } else if let preset = intent.preset {
            parts.append(preset.title)
            intendedTemplateID = preset.templateID
        } else {
            intendedTemplateID = selectedTemplateID
        }

        if let aspectRatio = intent.aspectRatio {
            let allowedAspectRatios = displayedAspectRatios(for: intendedTemplateID)
            if allowedAspectRatios.contains(aspectRatio) {
                parts.append(aspectRatio.title)
            } else if let closestAspectRatio = allowedAspectRatios.first {
                parts.append("Closest shape: \(closestAspectRatio.title)")
            }
        }

        if let durationSeconds = intent.durationSeconds,
           let closestDuration = nearestAllowedDuration(to: durationSeconds) {
            if closestDuration == durationSeconds {
                parts.append(formattedDuration(closestDuration))
            } else {
                parts.append("Closest length: \(formattedDuration(closestDuration))")
            }
        }

        guard !parts.isEmpty else { return nil }
        return "Smart setup from note: \(parts.joined(separator: " - "))"
    }

    private func applyQuickPrompt(_ quickPrompt: AIEditQuickPrompt) {
        let trimmed = userEditPrompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            userEditPrompt = quickPrompt.prompt
            applyStructuredUserPromptIntent()
            return
        }

        let normalizedPrompt = quickPrompt.prompt.lowercased()
        guard !trimmed.lowercased().contains(normalizedPrompt) else { return }

        let separator = trimmed.hasSuffix(".") || trimmed.hasSuffix("!") || trimmed.hasSuffix("?") ? " " : ". "
        userEditPrompt = String((trimmed + separator + quickPrompt.prompt).prefix(Self.maxUserPromptCharacters))
        applyStructuredUserPromptIntent()
    }

    private func applyStructuredUserPromptIntent() {
        let intent = CloudEditUserIntent.parse(userEditPrompt)
        guard intent.hasStructuredChoices else { return }

        if let proTemplate = intent.proTemplate, activePolicy.premiumTemplatesAllowed {
            selectProTemplate(proTemplate)
        } else if let preset = intent.proTemplate?.preset ?? intent.preset {
            selectFreePreset(preset)
        }

        if let aspectRatio = intent.aspectRatio, displayedAspectRatios.contains(aspectRatio) {
            selectedAspectRatio = aspectRatio
        }

        if let durationSeconds = intent.durationSeconds,
           let closestDuration = nearestAllowedDuration(to: durationSeconds) {
            selectedDuration = closestDuration
        }
    }

    private var proIntentWarningText: String? {
        guard activePolicy.planTier.isFree else { return nil }
        let prompt = userEditPrompt.lowercased()
        guard !prompt.isEmpty else { return nil }
        let lockedTerms = ["nba", "cinematic", "mixtape", "recruiting", "team highlight", "team package"]
        guard lockedTerms.contains(where: { prompt.contains($0) }) else { return nil }
        return "That exact style is Pro. Free will use the closest available style."
    }

    private var renderStateGuidance: String {
        switch phase {
        case .planning:
            return "Cloud is preparing your edit plan from selected clips."
        case .planReady:
            return "Plan is ready. Start render to create the finished video."
        case .renderRequested, .created, .queued:
            return "Render is in queue. You can switch apps while HoopClips keeps rendering."
        case .rendering:
            return "Making your highlight reel in the cloud. Return for the finished file."
        case .rendered:
            return "Your video is ready to preview and share."
        case .failed:
            return "The video did not finish. Retry when the backend is available."
        case .failedTimeout:
            return "Render timed out. Try a shorter duration and retry."
        case .cancelled:
            return "Render was cancelled."
        }
    }

    private var backgroundJobReminderText: String? {
        AIEditBackgroundJobCopy.reminder(
            for: phase,
            hasCloudSource: viewModel.cloudEditSourceObjectKey != nil
        )
    }

    private var activeAIWorkPhrase: String? {
        guard isWorking || editJob != nil || renderStatus != nil || revisionResponse != nil else { return nil }
        if phase == .rendered || phase == .failed || phase == .failedTimeout || phase == .cancelled {
            return nil
        }

        if let runningStep = activeWorkTimeline.steps.first(where: { $0.status == .running }) {
            return activeAIWorkPhrase(for: runningStep.stepId)
        }

        switch phase {
        case .planning:
            return "Cloud edit is reviewing candidate clips to build a plan."
        case .planReady:
            return "Plan is ready. Next step: render the finished MP4."
        case .renderRequested, .created:
            return "Sending the edit plan to the cloud render service."
        case .queued:
            return "Cloud edit is in queue. HoopClips refreshes from live job status."
        case .rendering:
            return "HoopClips is producing the cloud MP4."
        case .rendered, .failed, .failedTimeout, .cancelled:
            return nil
        }
    }

    private func activeAIWorkPhrase(for stepID: String) -> String {
        switch stepID {
        case "video_uploaded":
            return "Cloud source is ready for editing."
        case "finding_highlights":
            return "Cloud job is scanning candidate highlights."
        case "selecting_best_clips":
            return "Cloud job is selecting the best highlights."
        case "removing_duplicates":
            return "Cloud job is removing duplicates and weak moments."
        case "applying_template":
            return "Template rules are being applied."
        case "adding_slow_motion":
            return "Slow-motion moments are being validated in the edit plan."
        case "adding_watermark_outro":
            return "Plan rules, watermark, and outro are being validated."
        case "rendering_mp4":
            return "HoopClips is rendering the cloud MP4."
        case "finalizing_download":
            return "Preparing preview and share access."
        default:
            return "HoopClips is updating this edit from real cloud job status."
        }
    }

    private func selectFreePreset(_ preset: CloudEditPreset) {
        selectedProTemplate = nil
        selectedPreset = preset
        selectedAspectRatio = preset.aspectRatio
        selectedDuration = defaultDuration(options: preset.durationOptions)
        showAllDurationOptions = false
    }

    private func selectProTemplate(_ template: CloudEditProTemplate) {
        selectedProTemplate = template
        selectedPreset = template.preset
        selectedAspectRatio = template.aspectRatio
        selectedDuration = defaultDuration(options: template.durationOptions)
        showAllDurationOptions = false
    }

    private func defaultDuration(options: [Int]) -> Int {
        let available = options.filter { $0 <= activePolicy.maxRenderSeconds }
        return available.dropFirst().first ?? available.first ?? min(options[0], activePolicy.maxRenderSeconds)
    }

    private var allowedDurationOptions: [Int] {
        (selectedProTemplate?.durationOptions ?? selectedPreset.durationOptions)
            .filter { $0 <= activePolicy.maxRenderSeconds }
            .sorted()
    }

    private var displayedDurationOptions: [Int] {
        let options = Self.visibleDurationOptions(
            allowedOptions: allowedDurationOptions,
            selectedDuration: selectedDuration,
            showAllOptions: showAllDurationOptions
        )
        return options
    }

    private var shouldShowDurationOptionsToggle: Bool {
        allowedDurationOptions.count > displayedDurationOptions.count || showAllDurationOptions
    }

    static func visibleDurationOptions(
        allowedOptions: [Int],
        selectedDuration: Int,
        showAllOptions: Bool
    ) -> [Int] {
        let sortedAllowed = allowedOptions.sorted()
        guard !showAllOptions else { return sortedAllowed }

        let commonDurations = [30, 60, 120, 270]
        var options = sortedAllowed.filter { commonDurations.contains($0) }
        if options.isEmpty {
            options = Array(sortedAllowed.prefix(4))
        } else if !options.contains(selectedDuration) {
            options.append(selectedDuration)
        }

        if !options.contains(selectedDuration) {
            options.insert(selectedDuration, at: 0)
        }
        return Array(Set(options)).sorted()
    }

    private func nearestAllowedDuration(to requestedSeconds: Int) -> Int? {
        let options = allowedDurationOptions
        return options.min { lhs, rhs in
            let lhsDistance = abs(lhs - requestedSeconds)
            let rhsDistance = abs(rhs - requestedSeconds)
            if lhsDistance == rhsDistance {
                return lhs > rhs
            }
            return lhsDistance < rhsDistance
        }
    }

    private var displayedAspectRatios: [CloudEditAspectRatio] {
        displayedAspectRatios(for: selectedTemplateID)
    }

    private func displayedAspectRatios(for templateID: String) -> [CloudEditAspectRatio] {
        if templateID == CloudEditPreset.coachReview.templateID {
            return [.source, .widescreen]
        }
        return [.vertical, .widescreen]
    }

    private func formattedDuration(_ seconds: Int) -> String {
        if seconds < 60 {
            return "\(seconds)s"
        }
        let minutes = seconds / 60
        let remainingSeconds = seconds % 60
        if remainingSeconds == 0 {
            return "\(minutes)m"
        }
        return "\(minutes):\(String(format: "%02d", remainingSeconds))"
    }

    private func aiChip(icon: String, text: String) -> some View {
        Label(text, systemImage: icon)
            .font(.caption.bold())
            .foregroundStyle(.white)
            .lineLimit(dynamicTypeSize.isAccessibilitySize ? nil : 3)
            .minimumScaleFactor(0.84)
            .fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(AppTheme.cardBg.opacity(0.74), in: .rect(cornerRadius: 12))
    }

    private func styleAccessibilityIdentifier(for preset: CloudEditPreset) -> String {
        switch preset {
        case .personalHighlight:
            return "export.aiEdit.style.personalHighlight"
        case .fullGameHighlight:
            return "export.aiEdit.style.fullGameHighlight"
        case .coachReview:
            return "export.aiEdit.style.coachReview"
        }
    }

    private func durationAccessibilityIdentifier(for duration: Int) -> String {
        "export.aiEdit.length.\(duration)s"
    }

    private func formatAccessibilityIdentifier(for aspectRatio: CloudEditAspectRatio) -> String {
        switch aspectRatio {
        case .vertical:
            return "export.aiEdit.format.vertical"
        case .widescreen:
            return "export.aiEdit.format.widescreen"
        case .source:
            return "export.aiEdit.format.source"
        }
    }

    private func startEdit() {
        guard !isWorking else { return }
        if let cloudEditActionBlockedMessage {
            errorMessage = cloudEditActionBlockedMessage
            phase = .failed
            HoopsAccessibility.announce("Cloud AI editing is paused.")
            return
        }
        if revisionResponse == nil || downloadResponse != nil {
            applyStructuredUserPromptIntent()
        }
        if let selectedProTemplate, !isProUser {
            proInfoSheet = .template(selectedProTemplate)
            return
        }
        if revisionResponse != nil, downloadResponse == nil {
            Task { await runRevisionRenderFlow() }
        } else {
            Task { await runEditFlow() }
        }
    }

    private func requestRevision(_ command: CloudEditRevisionCommand) {
        guard !isWorking else { return }
        guard aiEditRevisionsAvailable else {
            errorMessage = CloudEditError.friendlyBackendMessage(
                code: "ai_edit_revision_disabled",
                fallback: "AI edit revisions are temporarily paused."
            )
            HoopsAccessibility.announce("AI edit revisions are paused.")
            return
        }
        Task { await runRevisionFlow(command) }
    }

    private func shareRenderedVideo() {
        guard !isPreparingShare else { return }
        Task { await prepareShareSheet() }
    }

    @MainActor
    private func saveRenderedVideoToPhotos() async {
        guard viewModel.exportService.exportedURL != nil else {
            errorMessage = "Preview the finished video first, then save it to Photos."
            return
        }
        await viewModel.saveToPhotos()
        if viewModel.showingSaveSuccess {
            HoopsAccessibility.announce("HoopClips video saved to Photos.")
        }
    }

    @MainActor
    private func refreshCloudEditVersion() async {
        guard AppConstants.cloudEditEnabled else {
            serviceVersion = nil
            serviceStatusErrorMessage = nil
            serviceStatusBlocksRendering = false
            serviceStatusIsChecking = false
            return
        }

        serviceStatusIsChecking = true
        defer { serviceStatusIsChecking = false }

        do {
            serviceVersion = try await cloudEditService.fetchVersion()
            serviceStatusErrorMessage = nil
            serviceStatusBlocksRendering = false
        } catch {
            let blocksRendering = CloudEditStatusRefreshPolicy.blocksRendering(for: error)
            if blocksRendering {
                serviceVersion = nil
            }
            serviceStatusErrorMessage = CloudEditStatusRefreshPolicy.statusMessage(for: error)
            serviceStatusBlocksRendering = blocksRendering
        }
    }

    @MainActor
    private func refreshRenderHistory(showError: Bool = false) async {
        guard proUXFlags.cloudLockerEnabled, AppConstants.cloudEditEnabled else { return }
        guard !isLoadingRenderHistory else { return }
        isLoadingRenderHistory = true
        if showError {
            lockerErrorMessage = nil
        }
        defer { isLoadingRenderHistory = false }

        do {
            let history = try await cloudEditService.fetchRenderHistory(
                installID: viewModel.installID,
                limit: 20
            )
            renderHistory = history.renders
            syncVisibleRenderFromHistory(history.renders)
            lockerErrorMessage = nil
        } catch {
            if showError {
                lockerErrorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            }
        }
    }

    @MainActor
    private func syncVisibleRenderFromHistory(_ renders: [CloudEditRenderStatusResponse]) {
        guard let refreshedRender = CloudEditForegroundRefreshPolicy.matchingRenderStatus(
            currentRender: renderStatus,
            activeEditJobID: editJob?.editJobId ?? editPlan?.editJobId,
            activeRevisionID: revisionResponse?.revisionId,
            history: renders
        ) else {
            return
        }

        renderStatus = refreshedRender
        policySummary = refreshedRender.policy ?? policySummary
        phase = refreshedRender.status
    }

    @MainActor
    private func redownloadLockerRender(_ render: CloudEditRenderStatusResponse) async {
        guard !isPreparingShare, !isLockerRenderExpired(render) else { return }
        lockerBusyRenderJobID = render.renderJobId
        isPreparingShare = true
        lockerErrorMessage = nil
        defer {
            isPreparingShare = false
            lockerBusyRenderJobID = nil
        }

        do {
            let download = try await cloudEditService.fetchDownloadURL(
                renderJobID: render.renderJobId,
                installID: viewModel.installID
            )
            downloadResponse = download
            renderStatus = render
            policySummary = render.policy ?? policySummary
            phase = render.status
            try await attachDownloadedCloudPreview(from: download)
            showingShareSheet = true
            LaunchTelemetry.shared.recordAIEditEvent(
                "ios.cloud_locker.downloaded",
                editJobID: render.editJobId,
                renderJobID: render.renderJobId,
                revisionID: render.revisionId,
                templateID: render.templateId,
                planTier: render.planTier?.rawValue
            )
        } catch {
            lockerErrorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            HoopsAccessibility.announce("Could not download that cloud render.")
        }
    }

    @MainActor
    private func saveLockerRenderToPhotos(_ render: CloudEditRenderStatusResponse) async {
        guard !isPreparingShare, !isLockerRenderExpired(render) else { return }
        lockerBusyRenderJobID = render.renderJobId
        isPreparingShare = true
        lockerErrorMessage = nil
        defer {
            isPreparingShare = false
            lockerBusyRenderJobID = nil
        }

        do {
            let download = try await cloudEditService.fetchDownloadURL(
                renderJobID: render.renderJobId,
                installID: viewModel.installID
            )
            downloadResponse = download
            renderStatus = render
            policySummary = render.policy ?? policySummary
            phase = render.status
            try await attachDownloadedCloudPreview(from: download)
            await viewModel.saveToPhotos()
            LaunchTelemetry.shared.recordAIEditEvent(
                "ios.cloud_locker.saved_to_photos",
                editJobID: render.editJobId,
                renderJobID: render.renderJobId,
                revisionID: render.revisionId,
                templateID: render.templateId,
                planTier: render.planTier?.rawValue
            )
        } catch {
            lockerErrorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            HoopsAccessibility.announce("Could not save that HoopClips video.")
        }
    }

    @MainActor
    private func rerenderLockerEdit(_ render: CloudEditRenderStatusResponse) async {
        guard !isWorking, canRerenderLockerRender(render) else { return }
        lockerBusyRenderJobID = render.renderJobId
        isWorking = true
        errorMessage = nil
        lockerErrorMessage = nil
        previewPlayer = nil
        downloadResponse = nil
        localShareURL = nil
        phase = .renderRequested
        HoopsAccessibility.announce("Requesting a fresh cloud render.")
        defer {
            isWorking = false
            lockerBusyRenderJobID = nil
        }

        do {
            let requested = try await cloudEditService.requestLockerRerender(
                render: render,
                installID: viewModel.installID
            )
            renderStatus = requested
            policySummary = requested.policy ?? policySummary
            phase = requested.status

            let finalStatus: CloudEditRenderStatusResponse
            if requested.status == .rendered {
                finalStatus = requested
            } else {
                finalStatus = try await cloudEditService.pollRenderStatus(
                    editJobID: render.editJobId,
                    installID: viewModel.installID
                )
            }
            renderStatus = finalStatus
            policySummary = finalStatus.policy ?? policySummary
            phase = finalStatus.status

            guard finalStatus.status == .rendered else {
                let code = finalStatus.failureReason ?? "render_failed"
                throw CloudEditError.backend(
                    code: code,
                    message: CloudEditError.friendlyBackendMessage(code: code, fallback: "Cloud re-rendering did not finish.")
                )
            }

            let download = try await cloudEditService.fetchDownloadURL(
                renderJobID: finalStatus.renderJobId,
                installID: viewModel.installID
            )
            downloadResponse = download
            try await attachDownloadedCloudPreview(from: download)
            await refreshRenderHistory()
            LaunchTelemetry.shared.recordAIEditEvent(
                "ios.cloud_locker.rerendered",
                editJobID: finalStatus.editJobId,
                renderJobID: finalStatus.renderJobId,
                revisionID: finalStatus.revisionId,
                templateID: finalStatus.templateId,
                planTier: finalStatus.planTier?.rawValue
            )
            HoopsAccessibility.announce("Fresh cloud render is ready.")
        } catch {
            phase = .failed
            let message = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            lockerErrorMessage = message
            errorMessage = message
            LaunchTelemetry.shared.recordAIEditEvent(
                "ios.cloud_locker.rerender_failed",
                editJobID: render.editJobId,
                renderJobID: render.renderJobId,
                revisionID: render.revisionId,
                templateID: render.templateId,
                planTier: render.planTier?.rawValue,
                failureReason: message
            )
            HoopsAccessibility.announce("Cloud re-render failed.")
        }
    }

    @MainActor
    private func runEditFlow() async {
        isWorking = true
        errorMessage = nil
        lockerErrorMessage = nil
        previewPlayer = nil
        downloadResponse = nil
        revisionResponse = nil
        pendingRevisionCommand = nil
        localShareURL = nil
        phase = .planning
        HoopsAccessibility.announce("HoopClips is finding your best plays.")
        defer { isWorking = false }

        do {
            #if DEBUG
            if Self.shouldSimulateRenderFailure {
                phase = .rendering
                HoopsAccessibility.announce("Rendering your highlight reel in the cloud.")
                throw CloudEditError.backend(
                    code: "ui_smoke_render_failed",
                    message: "Simulated cloud render failure for UI smoke."
                )
            }
            #endif

            let request = try viewModel.createCloudEditRequest(
                preset: selectedPreset,
                templateID: selectedTemplateID,
                targetDurationSeconds: selectedDuration,
                aspectRatio: selectedAspectRatio,
                isProUser: isProUser,
                revenueCatAppUserID: revenueCatAppUserID,
                userPrompt: sanitizedUserEditPrompt
            )
            let job = try await cloudEditService.createEditJob(request)
            editJob = job
            policySummary = job.policy ?? (request.planTier == .pro ? .proDefault : .freeDefault)

            let planResponse = try await cloudEditService.fetchEditPlan(
                editJobID: job.editJobId,
                installID: viewModel.installID
            )
            editPlan = planResponse.plan
            policySummary = planResponse.policy ?? policySummary
            phase = .planReady
            LaunchTelemetry.shared.recordAIEditEvent(
                "edit_plan.created",
                editJobID: job.editJobId,
                templateID: planResponse.plan.templateId,
                planTier: request.planTier.rawValue
            )
            HoopsAccessibility.announce("HoopClips built the edit plan and is rendering your highlight reel.")

            guard viewModel.cloudEditSourceObjectKey != nil else {
                throw CloudEditError.missingSourceObject
            }
            let requested = try await cloudEditService.requestStoredRender(
                editJobID: job.editJobId,
                installID: viewModel.installID,
                idempotencyKey: "ios-render-\(job.editJobId)",
                forceNew: false
            )
            renderStatus = requested
            policySummary = requested.policy ?? policySummary
            phase = requested.status

            let finalStatus = try await cloudEditService.pollRenderStatus(
                editJobID: job.editJobId,
                installID: viewModel.installID
            )
            renderStatus = finalStatus
            policySummary = finalStatus.policy ?? policySummary
            phase = finalStatus.status

            guard finalStatus.status == .rendered else {
                let code = finalStatus.failureReason ?? "render_failed"
                throw CloudEditError.backend(
                    code: code,
                    message: CloudEditError.friendlyBackendMessage(code: code, fallback: "Cloud rendering did not finish.")
                )
            }

            let download = try await cloudEditService.fetchDownloadURL(
                editJobID: job.editJobId,
                installID: viewModel.installID
            )
            downloadResponse = download
            try await attachDownloadedCloudPreview(from: download)
            LaunchTelemetry.shared.recordAIEditEvent(
                "ios.preview.loaded",
                editJobID: job.editJobId,
                renderJobID: finalStatus.renderJobId,
                templateID: planResponse.plan.templateId,
                planTier: request.planTier.rawValue
            )
            HoopsAccessibility.announce("Your HoopClips AI edit is ready.")
            await refreshRenderHistory()
        } catch {
            phase = .failed
            errorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            LaunchTelemetry.shared.recordAIEditEvent("render.failed", editJobID: editJob?.editJobId, templateID: editPlan?.templateId, failureReason: errorMessage)
            HoopsAccessibility.announce("Cloud AI edit failed.")
        }
    }

    @MainActor
    private func runRevisionFlow(_ command: CloudEditRevisionCommand) async {
        guard let editJob else {
            errorMessage = "Create an AI edit first, then revise it."
            return
        }
        isWorking = true
        errorMessage = nil
        lockerErrorMessage = nil
        phase = .planning
        HoopsAccessibility.announce("HoopClips is revising your AI edit.")
        defer { isWorking = false }

        do {
            let revision = try await cloudEditService.requestRevision(
                editJobID: editJob.editJobId,
                installID: viewModel.installID,
                command: command
            )
            revisionResponse = revision
            pendingRevisionCommand = command
            editPlan = revision.revisedPlan
            renderStatus = nil
            downloadResponse = nil
            previewPlayer = nil
            localShareURL = nil
            phase = .planReady
            LaunchTelemetry.shared.recordAIEditEvent(
                "edit_revision.created",
                editJobID: editJob.editJobId,
                revisionID: revision.revisionId,
                templateID: revision.revisedPlan.templateId,
                planTier: policySummary?.planTier.rawValue
            )
            HoopsAccessibility.announce("Revision ready. Make the new video when you are ready.")
        } catch {
            phase = .failed
            errorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            HoopsAccessibility.announce("Cloud AI edit revision failed.")
        }
    }

    @MainActor
    private func runRevisionRenderFlow() async {
        guard let editJob, let revisionResponse else {
            await runEditFlow()
            return
        }
        isWorking = true
        errorMessage = nil
        lockerErrorMessage = nil
        previewPlayer = nil
        downloadResponse = nil
        localShareURL = nil
        phase = .renderRequested
        HoopsAccessibility.announce("Rendering your revised highlight reel in the cloud.")
        defer { isWorking = false }

        do {
            let requested = try await cloudEditService.requestRevisionRender(
                editJobID: editJob.editJobId,
                revisionID: revisionResponse.revisionId,
                installID: viewModel.installID,
                forceNew: false
            )
            renderStatus = requested
            policySummary = requested.policy ?? policySummary
            phase = requested.status

            let finalStatus = try await cloudEditService.pollRenderStatus(
                editJobID: editJob.editJobId,
                installID: viewModel.installID
            )
            renderStatus = finalStatus
            policySummary = finalStatus.policy ?? policySummary
            phase = finalStatus.status

            guard finalStatus.status == .rendered else {
                let code = finalStatus.failureReason ?? "render_failed"
                throw CloudEditError.backend(
                    code: code,
                    message: CloudEditError.friendlyBackendMessage(code: code, fallback: "Cloud revision rendering did not finish.")
                )
            }

            let download = try await cloudEditService.fetchDownloadURL(
                editJobID: editJob.editJobId,
                installID: viewModel.installID
            )
            downloadResponse = download
            try await attachDownloadedCloudPreview(from: download)
            LaunchTelemetry.shared.recordAIEditEvent(
                "ios.preview.loaded",
                editJobID: editJob.editJobId,
                renderJobID: finalStatus.renderJobId,
                revisionID: revisionResponse.revisionId,
                templateID: revisionResponse.revisedPlan.templateId,
                planTier: policySummary?.planTier.rawValue
            )
            HoopsAccessibility.announce("Your revised HoopClips AI edit is ready.")
            await refreshRenderHistory()
        } catch {
            phase = .failed
            errorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            HoopsAccessibility.announce("Cloud revision render failed.")
        }
    }

    @MainActor
    private func refreshDownloadURL(for download: CloudEditDownloadResponse) async throws -> CloudEditDownloadResponse {
        try await cloudEditService.fetchDownloadURL(
            renderJobID: download.renderJobId,
            installID: viewModel.installID
        )
    }

    @MainActor
    private func attachDownloadedCloudPreview(from download: CloudEditDownloadResponse) async throws {
        var activeDownload = download
        let temporaryURL: URL
        do {
            temporaryURL = try await cloudEditService.downloadRenderedVideo(from: activeDownload)
        } catch CloudEditError.downloadURLExpired {
            activeDownload = try await refreshDownloadURL(for: activeDownload)
            downloadResponse = activeDownload
            temporaryURL = try await cloudEditService.downloadRenderedVideo(from: activeDownload)
        }
        viewModel.attachCloudRenderedExport(from: temporaryURL)
        localShareURL = viewModel.exportService.exportedURL ?? temporaryURL
        previewPlayer = AVPlayer(url: localShareURL ?? temporaryURL)
        applyPreviewAudioMute()
        previewPlayer?.play()
    }

    @MainActor
    private func prepareShareSheet() async {
        guard var downloadResponse else { return }
        isPreparingShare = true
        errorMessage = nil
        lockerErrorMessage = nil
        defer { isPreparingShare = false }

        do {
            if downloadResponse.expiresAt <= Date().addingTimeInterval(30) {
                errorMessage = "Refreshing download link"
                downloadResponse = try await refreshDownloadURL(for: downloadResponse)
                self.downloadResponse = downloadResponse
                errorMessage = nil
            }
            let temporaryURL: URL
            do {
                temporaryURL = try await cloudEditService.downloadRenderedVideo(from: downloadResponse)
            } catch CloudEditError.downloadURLExpired {
                errorMessage = "Refreshing download link"
                let freshDownload = try await refreshDownloadURL(for: downloadResponse)
                self.downloadResponse = freshDownload
                temporaryURL = try await cloudEditService.downloadRenderedVideo(from: freshDownload)
                errorMessage = nil
            }
            viewModel.attachCloudRenderedExport(from: temporaryURL)
            localShareURL = viewModel.exportService.exportedURL ?? temporaryURL
            showingShareSheet = true
            LaunchTelemetry.shared.recordAIEditEvent(
                "ios.share.opened",
                editJobID: editJob?.editJobId,
                renderJobID: downloadResponse.renderJobId,
                revisionID: revisionResponse?.revisionId,
                templateID: editPlan?.templateId,
                planTier: policySummary?.planTier.rawValue
            )
        } catch {
            let failureDescription = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            errorMessage = "Could not prepare the video for sharing. Try again in a moment."
            LaunchTelemetry.shared.recordAIEditEvent(
                "ios.share.failed",
                editJobID: editJob?.editJobId,
                renderJobID: downloadResponse.renderJobId,
                revisionID: revisionResponse?.revisionId,
                templateID: editPlan?.templateId,
                planTier: policySummary?.planTier.rawValue,
                failureReason: failureDescription
            )
            HoopsAccessibility.announce("Could not open sharing for this render.")
        }
    }

    #if DEBUG
    private static var shouldSimulateRenderFailure: Bool {
        AIEditUISmokeConfig.isEnabled && AIEditUISmokeConfig.fixture == .failingRender
    }
    #endif
}

private extension Array where Element == String {
    mutating func appendIfMissing(_ value: String) {
        guard !contains(value) else { return }
        append(value)
    }
}
