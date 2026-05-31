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

private struct AIEditQuickPrompt: Identifiable {
    let id: String
    let title: String
    let prompt: String
    let icon: String
}

struct AIEditView: View {
    @Bindable var viewModel: HighlightsViewModel
    let isProUser: Bool
    var revenueCatAppUserID: String? = nil
    var presentation: AIEditPresentation = .sheet
    var onRequestProUpgrade: (() -> Void)?

    @Environment(\.dismiss) private var dismiss
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
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

    private let cloudEditService: any CloudEditServicing
    private let proUXFlags = CloudEditProUXFlags.safeDefault
    private static let maxUserPromptCharacters = 240
    private static let quickPrompts: [AIEditQuickPrompt] = [
        AIEditQuickPrompt(
            id: "hype",
            title: "More hype",
            prompt: "Make it more hype and prioritize clear made shots, blocks, steals, and big defensive stops.",
            icon: "bolt.fill"
        ),
        AIEditQuickPrompt(
            id: "defense",
            title: "Focus defense",
            prompt: "Focus on defense: blocks, steals, stops, and transition plays.",
            icon: "shield.lefthalf.filled"
        ),
        AIEditQuickPrompt(
            id: "clear-outcomes",
            title: "Clear outcomes",
            prompt: "Prefer clips with a visible outcome. Keep uncertain but strong moments so I can review them.",
            icon: "scope"
        ),
        AIEditQuickPrompt(
            id: "team-recap",
            title: "Team recap",
            prompt: "Make a clean team recap with balanced players, offense, defense, and game flow.",
            icon: "person.3.fill"
        )
    ]

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
            await refreshCloudEditVersion()
            await refreshRenderHistory()
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
            planTierCard
            if activePolicy.planTier.isFree, proUXFlags.proUpsellEnabled {
                proValueCard
            }
            stylePicker
            formatPicker
            durationPicker
            promptCard
            statusCard
            aiWorkTimelineCard
            if proUXFlags.cloudLockerEnabled {
                cloudLockerCard
            }

            if let previewPlayer {
                previewCard(player: previewPlayer)
            }

            if let receipt = activeWorkReceipt {
                aiWorkReceiptCard(receipt)
            }

            if editPlan != nil, downloadResponse != nil || revisionResponse != nil {
                revisionCard
            }

            actionCard
        }
    }

    private var heroCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("AI Edit Agent", systemImage: "wand.and.stars")
                .font(.title2.bold())
                .foregroundStyle(.white)
                .accessibilityIdentifier("export.aiEdit.section")

            Text("Pick a style, add a side note, and HoopClips makes the finished video in the cloud.")
                .font(.subheadline)
                .foregroundStyle(AppTheme.subtleText)

            HStack(spacing: 8) {
                aiChip(icon: "film.stack.fill", text: "\(viewModel.keptClips.count) kept clips")
                aiChip(icon: selectedAspectRatio.icon, text: selectedAspectRatio.rawValue)
                aiChip(icon: "timer", text: formattedDuration(selectedDuration))
            }

            Text("You can leave the app while the real cloud job runs.")
                .font(.caption.bold())
                .foregroundStyle(AppTheme.warningYellow)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("export.aiEdit.backgroundRender.message")
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
                        .accessibilityIdentifier("export.aiEdit.plan.current")
                    Text("\(policy.maxDailyRenders) video edits/day - \(policy.maxOutputResolution) max")
                        .font(.caption.bold())
                        .foregroundStyle(AppTheme.warningYellow)
                        .accessibilityIdentifier("export.aiEdit.queue.label")
                }
                Spacer()
            }

            VStack(alignment: .leading, spacing: 8) {
                ForEach(policy.planLimitRows, id: \.self) { row in
                    Label(row, systemImage: "checkmark.circle.fill")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.88))
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                if policy.planTier.isFree {
                    Label("Failed HoopClips jobs do not use a free edit.", systemImage: "arrow.counterclockwise.circle.fill")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(AppTheme.warningYellow)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
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
                ForEach(CloudEditPolicySummary.proValueRows, id: \.self) { row in
                    Label(row, systemImage: "sparkles")
                        .font(.caption2.bold())
                        .foregroundStyle(.white.opacity(0.9))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 8)
                        .background(AppTheme.accentPurple.opacity(0.22), in: .capsule)
                }
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.neonPurple.opacity(0.2), glow: AppTheme.neonPurple, glowOpacity: 0.06)
        .accessibilityIdentifier("export.aiEdit.proValueCard")
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
                            HStack(spacing: 6) {
                                Text(preset.title)
                                    .font(.subheadline.bold())
                                    .foregroundStyle(.white)
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
                        }
                        Spacer()
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
                                HStack(spacing: 6) {
                                    Text(template.title)
                                        .font(.subheadline.bold())
                                        .foregroundStyle(.white)
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
                            }
                            Spacer()
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
            HStack {
                Text("Target Length")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
                Text(formattedDuration(selectedDuration))
                    .font(.subheadline.monospacedDigit().bold())
                    .foregroundStyle(AppTheme.warningYellow)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(displayedDurationOptions, id: \.self) { duration in
                        Button {
                            if duration <= activePolicy.maxRenderSeconds {
                                selectedDuration = duration
                            }
                        } label: {
                            Text(formattedDuration(duration))
                                .font(.subheadline.bold())
                                .foregroundStyle(duration > activePolicy.maxRenderSeconds ? AppTheme.subtleText.opacity(0.45) : (selectedDuration == duration ? .white : AppTheme.subtleText))
                                .frame(minWidth: 64)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 10)
                                .background(selectedDuration == duration ? AppTheme.accentPurple : AppTheme.cardBg.opacity(duration > activePolicy.maxRenderSeconds ? 0.45 : 1), in: .capsule)
                        }
                        .buttonStyle(.plain)
                        .disabled(duration > activePolicy.maxRenderSeconds)
                        .accessibilityLabel(formattedDuration(duration))
                        .accessibilityIdentifier(durationAccessibilityIdentifier(for: duration))
                        .accessibilityValue(duration > activePolicy.maxRenderSeconds ? "Unavailable on \(activePolicy.displayName)" : (selectedDuration == duration ? "Selected" : "Not selected"))
                    }
                }
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.04)
    }

    private var formatPicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Video Shape")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
                Text(selectedAspectRatio.rawValue)
                    .font(.subheadline.monospacedDigit().bold())
                    .foregroundStyle(AppTheme.warningYellow)
            }

            HStack(spacing: 8) {
                ForEach(displayedAspectRatios, id: \.rawValue) { aspectRatio in
                    Button {
                        selectedAspectRatio = aspectRatio
                    } label: {
                        VStack(spacing: 6) {
                            Image(systemName: aspectRatio.icon)
                                .font(.headline)
                            Text(aspectRatio.title)
                                .font(.caption.bold())
                            Text(aspectRatio.subtitle)
                                .font(.caption2)
                                .lineLimit(2)
                                .multilineTextAlignment(.center)
                        }
                        .foregroundStyle(selectedAspectRatio == aspectRatio ? .white : AppTheme.subtleText)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
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
            HStack {
                Label("Side Note", systemImage: "text.bubble.fill")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
                Text("\(userEditPrompt.count)/\(Self.maxUserPromptCharacters)")
                    .font(.caption2.monospacedDigit().bold())
                    .foregroundStyle(userEditPrompt.count >= Self.maxUserPromptCharacters ? AppTheme.warningYellow : AppTheme.subtleText)
            }

            ZStack(alignment: .topLeading) {
                TextEditor(text: $userEditPrompt)
                    .font(.subheadline)
                    .foregroundStyle(.white)
                    .scrollContentBackground(.hidden)
                    .frame(minHeight: 86)
                    .padding(10)
                    .background(AppTheme.cardBg.opacity(0.72), in: .rect(cornerRadius: 12))
                    .overlay {
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(AppTheme.softBorder, lineWidth: 1)
                    }
                    .accessibilityIdentifier("export.aiEdit.userPrompt")
                    .onChange(of: userEditPrompt) { _, newValue in
                        if newValue.count > Self.maxUserPromptCharacters {
                            userEditPrompt = String(newValue.prefix(Self.maxUserPromptCharacters))
                        }
                    }

                if userEditPrompt.isEmpty {
                    Text("Example: more hype, focus on defense, NBA recap, 30s vertical mixtape.")
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.subtleText.opacity(0.68))
                        .padding(.horizontal, 16)
                        .padding(.vertical, 18)
                        .allowsHitTesting(false)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            LazyVGrid(columns: quickPromptGridColumns, alignment: .leading, spacing: 8) {
                ForEach(Self.quickPrompts) { quickPrompt in
                    Button {
                        applyQuickPrompt(quickPrompt)
                    } label: {
                        Label(quickPrompt.title, systemImage: quickPrompt.icon)
                            .font(.caption.weight(.semibold))
                            .multilineTextAlignment(.center)
                            .lineLimit(2)
                            .minimumScaleFactor(0.86)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 52 : 42)
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

    private var quickPromptGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize.isAccessibilitySize ? 168 : 132
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 240), spacing: 8, alignment: .top)
        ]
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
            } else {
                Text(viewModel.cloudEditUnavailableReason ?? renderStateGuidance)
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
            }

            if let activeAIWorkPhrase {
                Label(activeAIWorkPhrase, systemImage: "sparkles")
                    .font(.caption.bold())
                    .foregroundStyle(AppTheme.warningYellow)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("export.aiEdit.activeWorkPhrase")
            }

            if let renderStatus, let duration = renderStatus.durationSeconds {
                Text("Rendered duration: \(Clip.formatTime(duration))")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(AppTheme.subtleText)
            }

            if let serviceStatusMessage {
                Label(serviceStatusMessage, systemImage: serviceStatusIcon)
                    .font(.caption)
                    .foregroundStyle(serviceStatusColor)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("export.aiEdit.serviceStatus")
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

    private var aiWorkTimelineCard: some View {
        let timeline = activeWorkTimeline
        return VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("AI Edit Timeline", systemImage: "sparkles.rectangle.stack.fill")
                    .font(.headline)
                    .foregroundStyle(.white)
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

            Text("Only real HoopClips job updates are shown; pending steps stay as a checklist until the server reports progress.")
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
                .fixedSize(horizontal: false, vertical: true)

            VStack(alignment: .leading, spacing: 9) {
                ForEach(timeline.steps) { step in
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
                            if let detail = step.detail, !detail.isEmpty {
                                Text(detail)
                                    .font(.caption2)
                                    .foregroundStyle(AppTheme.subtleText)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                        Spacer(minLength: 0)
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("export.aiEdit.timeline.\(step.stepId)")
                }
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.neonPurple.opacity(0.16), glow: AppTheme.neonPurple, glowOpacity: 0.05)
        .accessibilityIdentifier("export.aiEdit.timeline")
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

            HStack(spacing: 8) {
                if render.status == .rendered {
                    Button {
                        Task { await saveLockerRenderToPhotos(render) }
                    } label: {
                        Label(
                            isExpired ? "Expired" : (isBusy && isPreparingShare ? "Saving" : "Save"),
                            systemImage: isExpired ? "exclamationmark.triangle.fill" : "photo.badge.arrow.down.fill"
                        )
                            .font(.caption.bold())
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(AppTheme.successGreen)
                    .disabled(isExpired || isWorking || isPreparingShare || lockerBusyRenderJobID != nil)
                    .accessibilityIdentifier("export.aiEdit.cloudLocker.save.\(render.renderJobId)")

                    Button {
                        Task { await redownloadLockerRender(render) }
                    } label: {
                        Label(
                            isExpired ? "Expired" : (isBusy && isPreparingShare ? "Preparing Share" : "Share"),
                            systemImage: isExpired ? "exclamationmark.triangle.fill" : "square.and.arrow.up.fill"
                        )
                            .font(.caption.bold())
                            .frame(maxWidth: .infinity)
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
                        .frame(maxWidth: .infinity)
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
            Text("Preview")
                .font(.headline)
                .foregroundStyle(.white)

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
                Label(primaryActionTitle, systemImage: primaryActionIcon)
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
            }
            .buttonStyle(.borderedProminent)
            .tint(AppTheme.accentPurple)
            .disabled(primaryActionDisabled)
            .accessibilityIdentifier(revisionResponse != nil && downloadResponse == nil ? "export.aiEdit.renderRevisionButton" : "export.aiEdit.generateButton")
            .accessibilityHint(primaryActionHint)

            if phase == .failed {
                Button(action: startEdit) {
                    Label("Try Again", systemImage: "arrow.clockwise")
                        .font(.caption.bold())
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
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
                    Label("Save to Photos", systemImage: "photo.badge.arrow.down.fill")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                }
                .buttonStyle(.borderedProminent)
                .tint(AppTheme.successGreen)
                .disabled(isPreparingShare || viewModel.exportService.exportedURL == nil)
                .accessibilityIdentifier("export.aiEdit.saveToPhotosButton")
                .accessibilityHint("Saves the finished video to your photo library.")

                Button(action: shareRenderedVideo) {
                    Label(isPreparingShare ? "Getting Video Ready" : "Share", systemImage: "square.and.arrow.up.fill")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                }
                .buttonStyle(.bordered)
                .tint(AppTheme.neonPurple)
                .disabled(isPreparingShare)
                .accessibilityIdentifier("export.aiEdit.shareButton")
                .accessibilityHint("Downloads the finished video and opens the system share sheet.")
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.04)
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

            LazyVGrid(columns: [GridItem(.adaptive(minimum: 132), spacing: 8)], spacing: 8) {
                ForEach(revisionCommands) { command in
                    Button {
                        requestRevision(command)
                    } label: {
                        Label(command.title, systemImage: command.icon)
                            .font(.caption.bold())
                            .foregroundStyle(pendingRevisionCommand == command ? .white : AppTheme.subtleText)
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
        let candidateClipCount = viewModel.keptClips.count
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
        let candidateClipCount = viewModel.keptClips.count
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
        cloudEditActionBlockedMessage ?? "Requests a cloud edit plan and render."
    }

    private var serviceStatusMessage: String? {
        if let cloudEditActionBlockedMessage {
            return cloudEditActionBlockedMessage
        }
        if serviceStatusIsChecking {
            return "Checking HoopClips status. You can still start the edit."
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
            return "exclamationmark.triangle"
        }
        return "pause.circle"
    }

    private var serviceStatusColor: Color {
        cloudEditActionBlockedMessage == nil ? AppTheme.warningYellow : AppTheme.dangerRed
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
        if revisionResponse != nil, downloadResponse == nil {
            return "Make Revised Video"
        }
        return downloadResponse == nil ? "Make My Reel" : "Render Again"
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
            return "HoopClips planned this revision and approved it for rendering."
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

    private var sanitizedUserEditPrompt: String? {
        let trimmed = userEditPrompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        return String(trimmed.prefix(Self.maxUserPromptCharacters))
    }

    private func applyQuickPrompt(_ quickPrompt: AIEditQuickPrompt) {
        let trimmed = userEditPrompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            userEditPrompt = quickPrompt.prompt
            return
        }

        let normalizedPrompt = quickPrompt.prompt.lowercased()
        guard !trimmed.lowercased().contains(normalizedPrompt) else { return }

        let separator = trimmed.hasSuffix(".") || trimmed.hasSuffix("!") || trimmed.hasSuffix("?") ? " " : ". "
        userEditPrompt = String((trimmed + separator + quickPrompt.prompt).prefix(Self.maxUserPromptCharacters))
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
            return "Ready to ask HoopClips to build your AI edit in the cloud."
        case .planReady:
            return "HoopClips picked clips and applied your style. Next step is making the finished video."
        case .renderRequested, .created, .queued:
            return "Your highlight reel is queued. You can leave the app - HoopClips keeps editing in the cloud."
        case .rendering:
            return "Making your highlight reel in the cloud. Come back anytime to check the finished video."
        case .rendered:
            return "Your video is ready to preview and share."
        case .failed:
            return "The video did not finish. You can retry when HoopClips is ready."
        case .failedTimeout:
            return "Making the video timed out. Try a shorter edit or retry when HoopClips is ready."
        case .cancelled:
            return "Render was cancelled."
        }
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
            return "Cloud edit is reviewing candidate clips and building the plan."
        case .planReady:
            return "The edit plan is ready; making the video is the next real step."
        case .renderRequested, .created:
            return "The approved edit plan is being sent to HoopClips."
        case .queued:
            return "Cloud edit is queued; HoopClips will keep checking real job status."
        case .rendering:
            return "HoopClips is producing the approved video."
        case .rendered, .failed, .failedTimeout, .cancelled:
            return nil
        }
    }

    private func activeAIWorkPhrase(for stepID: String) -> String {
        switch stepID {
        case "video_uploaded":
            return "Cloud source is ready for editing."
        case "finding_highlights":
            return "Cloud job is reviewing candidate clips."
        case "selecting_best_clips":
            return "Cloud job is selecting highlights from the candidate pool."
        case "removing_duplicates":
            return "Cloud job is checking duplicate and low-value moments."
        case "applying_template":
            return "Template rules are being applied to the edit plan."
        case "adding_slow_motion":
            return "Slow-motion moments are being validated in the edit plan."
        case "adding_watermark_outro":
            return "Plan rules, watermark, and outro are being validated."
        case "rendering_mp4":
            return "HoopClips is producing the approved video."
        case "finalizing_download":
            return "Preview and share access are being finalized."
        default:
            return "HoopClips is updating this edit from real cloud job status."
        }
    }

    private func selectFreePreset(_ preset: CloudEditPreset) {
        selectedProTemplate = nil
        selectedPreset = preset
        selectedAspectRatio = preset.aspectRatio
        selectedDuration = defaultDuration(options: preset.durationOptions)
    }

    private func selectProTemplate(_ template: CloudEditProTemplate) {
        selectedProTemplate = template
        selectedPreset = template.preset
        selectedAspectRatio = template.aspectRatio
        selectedDuration = defaultDuration(options: template.durationOptions)
    }

    private func defaultDuration(options: [Int]) -> Int {
        let available = options.filter { $0 <= activePolicy.maxRenderSeconds }
        return available.dropFirst().first ?? available.first ?? min(options[0], activePolicy.maxRenderSeconds)
    }

    private var displayedDurationOptions: [Int] {
        var options = selectedProTemplate?.durationOptions ?? selectedPreset.durationOptions
        if !options.contains(selectedDuration) {
            options.insert(selectedDuration, at: 0)
        }
        return options.sorted()
    }

    private var displayedAspectRatios: [CloudEditAspectRatio] {
        if selectedTemplateID == CloudEditPreset.coachReview.templateID {
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
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(AppTheme.cardBg.opacity(0.74), in: .capsule)
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
        } catch CloudEditError.notConfigured {
            serviceVersion = nil
            serviceStatusErrorMessage = AppConstants.cloudEditEnabled ? CloudEditError.notConfigured.errorDescription : nil
            serviceStatusBlocksRendering = true
        } catch CloudEditError.invalidResponse {
            serviceVersion = nil
            serviceStatusErrorMessage = CloudEditError.invalidResponse.errorDescription
            serviceStatusBlocksRendering = true
        } catch CloudEditError.backend(_, let message) {
            serviceVersion = nil
            serviceStatusErrorMessage = message
            serviceStatusBlocksRendering = true
        } catch {
            serviceVersion = nil
            serviceStatusErrorMessage = cloudStatusWarningMessage(for: error)
            serviceStatusBlocksRendering = false
        }
    }

    private func cloudStatusWarningMessage(for error: Error) -> String {
        if let urlError = error as? URLError, urlError.code == .timedOut {
            return "Cloud status check timed out. Start a render to use the real cloud job response."
        }
        return "Cloud status check failed. Start a render to use the real cloud job response."
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
            lockerErrorMessage = nil
        } catch {
            if showError {
                lockerErrorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            }
        }
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
