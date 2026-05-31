import SwiftUI
import AVKit

struct ReviewView: View {
    @Bindable var viewModel: HighlightsViewModel
    @Binding var selectedTab: Int
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var selectedClip: Clip?
    @State private var clipPlayer: AVPlayer?
    @State private var clipLoopObserverToken: NSObjectProtocol?
    @State private var clipPlaybackRange: ClosedRange<Double>?
    @State private var filterOption: FilterOption = .all
    @State private var sortByScore = true
    @State private var expandedClipID: UUID?
    @State private var keepTrigger = 0
    @State private var discardTrigger = 0
    private let tabTransitionAnimation = Animation.interactiveSpring(
        response: 0.42,
        dampingFraction: 0.96,
        blendDuration: 0.12
    )

    private enum FilterOption: String, CaseIterable {
        case all = "All"
        case selectedTeam = "Team"
        case teamUncertain = "Check Team"
        case defense = "Defense"
        case blocks = "Blocks"
        case steals = "Steals"
        case needsReview = "Check"
        case kept = "Kept"
        case discarded = "Skipped"
    }

    private var filteredClips: [Clip] {
        let base: [Clip]
        switch filterOption {
        case .all: base = viewModel.clips
        case .selectedTeam: base = viewModel.clips.filter(clipMatchesSelectedTeam)
        case .teamUncertain: base = viewModel.clips.filter(clipNeedsTeamReview)
        case .defense: base = viewModel.clips.filter(isDefensiveClip)
        case .blocks: base = viewModel.clips.filter(isBlockClip)
        case .steals: base = viewModel.clips.filter(isStealClip)
        case .needsReview: base = viewModel.needsReviewClips
        case .kept: base = viewModel.keptClips
        case .discarded: base = viewModel.discardedClips
        }
        if sortByScore {
            return base.sorted { $0.combinedScore > $1.combinedScore }
        }
        return base.sorted { $0.startTime < $1.startTime }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.20)

                if viewModel.clips.isEmpty {
                    emptyState
                } else {
                    ScrollView {
                        VStack(spacing: 16) {
                            headerStats
                            reviewProgressStrip
                            reviewContextStrip
                            quickActionsBar
                            aiEditEntryCard
                            filterBar
                            clipsList
                        }
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                        .padding(.bottom, 100)
                    }
                }
            }
            .navigationTitle("Review")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                if !viewModel.clips.isEmpty {
                    ToolbarItem(placement: .topBarTrailing) {
                        Menu {
                            Button("Keep All", systemImage: "checkmark.circle") {
                                viewModel.keepAllClips()
                            }
                            Button("Skip All", systemImage: "xmark.circle") {
                                viewModel.discardAllClips()
                            }
                            Divider()
                            Button(sortByScore ? "Sort by Time" : "Sort by Score", systemImage: sortByScore ? "clock" : "chart.bar") {
                                sortByScore.toggle()
                            }
                        } label: {
                            Image(systemName: "ellipsis.circle.fill")
                                .foregroundStyle(AppTheme.neonPurple)
                        }
                        .accessibilityLabel("More review actions")
                        .accessibilityHint("Keep all, skip all, or change sorting.")
                    }
                }
            }
            .sheet(item: $selectedClip, onDismiss: teardownClipPlayer) { clip in
                clipDetailSheet(clip: clip)
            }
        }
    }

    private var emptyState: some View {
        HoopsEmptyStateCard(
            title: "No Clips Yet",
            message: "Import a video and run analysis. Your best plays will land here ready to keep, skip, and fine-tune.",
            icon: "film.stack.fill"
        )
    }

    private var headerStats: some View {
        HStack(spacing: 12) {
            reviewStatCard(
                value: "\(viewModel.keptClips.count)",
                label: "Keeping",
                icon: "checkmark.circle.fill",
                color: AppTheme.successGreen
            )
            reviewStatCard(
                value: "\(viewModel.discardedClips.count)",
                label: "Skipped",
                icon: "xmark.circle.fill",
                color: AppTheme.dangerRed
            )
            reviewStatCard(
                value: "\(viewModel.needsReviewClips.count)",
                label: "Check",
                icon: "exclamationmark.triangle.fill",
                color: AppTheme.warningYellow
            )
            reviewStatCard(
                value: Clip.formatTime(viewModel.keptClips.reduce(0) { $0 + $1.duration }),
                label: "Total Time",
                icon: "clock.fill",
                color: AppTheme.neonPurple
            )
        }
    }

    private func reviewStatCard(value: String, label: String, icon: String, color: Color) -> some View {
        VStack(spacing: 6) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(color)
            Text(value)
                .font(.headline.monospacedDigit())
                .foregroundStyle(.white)
            Text(label)
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .rorkCard(
            cornerRadius: 12,
            fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.75)),
            stroke: color.opacity(0.22),
            glow: color,
            glowOpacity: 0.07
        )
    }

    private var reviewProgressStrip: some View {
        let total = max(viewModel.clips.count, 1)
        let progress = Double(viewModel.keptClips.count) / Double(total)

        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                Label("Review Progress", systemImage: "checklist")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                Spacer()
                Text("\(viewModel.keptClips.count)/\(viewModel.clips.count) kept")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(AppTheme.subtleText)
            }

            ProgressView(value: progress)
                .tint(AppTheme.neonPurple)
                .scaleEffect(y: 1.8)
                .accessibilityLabel("Review progress")
                .accessibilityValue("\(viewModel.keptClips.count) of \(viewModel.clips.count) clips kept")

            HStack(spacing: 8) {
                RorkMetricChip(
                    icon: sortByScore ? "chart.bar.fill" : "clock.fill",
                    value: sortByScore ? "Score" : "Time",
                    label: "Sort",
                    tint: AppTheme.neonPurple
                )
                RorkMetricChip(
                    icon: "line.3.horizontal.decrease.circle.fill",
                    value: filterOption.rawValue,
                    label: "Filter",
                    tint: AppTheme.warningYellow
                )
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.06)
    }

    private var highConfidencePendingCount: Int {
        viewModel.clips.filter { $0.confidence >= 0.8 && !$0.isKept && !$0.needsUserReview }.count
    }

    private var lowConfidenceKeptCount: Int {
        viewModel.clips.filter { $0.confidence < 0.5 && $0.isKept }.count
    }

    private var selectedTeamFilterIsAvailable: Bool {
        viewModel.settings.highlightTeamSelection.mode == .team
    }

    private var availableFilterOptions: [FilterOption] {
        var options: [FilterOption] = [.all]
        if selectedTeamFilterIsAvailable {
            options.append(.selectedTeam)
        }
        options.append(contentsOf: [.teamUncertain, .defense, .blocks, .steals, .needsReview, .kept, .discarded])
        return options
    }

    private var selectedTeamSummaryTitle: String {
        let selection = viewModel.settings.highlightTeamSelection
        guard selection.mode == .team else { return "All teams" }
        return selection.displayTitle
    }

    private var reviewContextStrip: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                RorkMetricChip(
                    icon: selectedTeamFilterIsAvailable ? "person.2.fill" : "person.3.fill",
                    value: selectedTeamSummaryTitle,
                    label: "Team",
                    tint: selectedTeamFilterIsAvailable ? AppTheme.warningYellow : AppTheme.neonPurple
                )
                RorkMetricChip(
                    icon: "shield.fill",
                    value: "\(clipCount(for: .defense))",
                    label: "Defense",
                    tint: .orange
                )
                RorkMetricChip(
                    icon: "person.2.badge.gearshape.fill",
                    value: "\(clipCount(for: .teamUncertain))",
                    label: "Team Check",
                    tint: AppTheme.warningYellow
                )
            }
            .padding(.horizontal, 2)
        }
        .padding(10)
        .rorkCard(cornerRadius: 14, fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.45)), stroke: AppTheme.softBorder, glowOpacity: 0.03)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Review context")
        .accessibilityValue("\(selectedTeamSummaryTitle), \(clipCount(for: .defense)) defensive clips, \(clipCount(for: .teamUncertain)) clips need team check")
    }

    private var quickActionsBar: some View {
        HStack(spacing: 10) {
            reviewQuickActionButton(
                title: "Keep Best",
                subtitle: "\(highConfidencePendingCount) clips",
                icon: "checkmark.seal.fill",
                tint: AppTheme.successGreen,
                isDisabled: highConfidencePendingCount == 0
            ) {
                HoopsAccessibility.animate(reduceMotion: reduceMotion) {
                    viewModel.keepHighConfidenceClips()
                }
            }

            reviewQuickActionButton(
                title: "Skip Low",
                subtitle: "\(lowConfidenceKeptCount) clips",
                icon: "xmark.seal.fill",
                tint: AppTheme.dangerRed,
                isDisabled: lowConfidenceKeptCount == 0
            ) {
                HoopsAccessibility.animate(reduceMotion: reduceMotion) {
                    viewModel.discardLowConfidenceClips()
                }
            }
        }
        .padding(10)
        .rorkCard(
            cornerRadius: 14,
            fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.55)),
            stroke: AppTheme.softBorder,
            glowOpacity: 0.04
        )
    }

    private var aiEditEntryCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                Image(systemName: "wand.and.stars.inverse")
                    .font(.title2)
                    .foregroundStyle(AppTheme.warningYellow)
                    .frame(width: 42, height: 42)
                    .background(AppTheme.warningYellow.opacity(0.15), in: .circle)

                VStack(alignment: .leading, spacing: 4) {
                    Text("Make Highlight Reel")
                        .font(.headline)
                        .foregroundStyle(.white)
                    Text(viewModel.cloudEditUnavailableReason ?? "Pick a style, add a note, and HoopClips will make the video.")
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer()
            }

            Button {
                openExport()
            } label: {
                Label("Make My Highlight", systemImage: "sparkles")
                    .font(.subheadline.bold())
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 11)
            }
            .buttonStyle(.borderedProminent)
            .tint(AppTheme.accentPurple)
            .disabled(!viewModel.canRequestCloudEdit)
            .accessibilityIdentifier("review.continueToExportButton")
            .accessibilityHint("Opens AI Edit with style, length, preview, save, and share controls.")
        }
        .padding(14)
        .rorkCard(
            cornerRadius: 16,
            stroke: viewModel.canRequestCloudEdit ? AppTheme.neonPurple.opacity(0.28) : AppTheme.softBorder,
            glow: AppTheme.neonPurple,
            glowOpacity: viewModel.canRequestCloudEdit ? 0.08 : 0.03
        )
    }

    private func openExport() {
        guard selectedTab != 2 else { return }
        guard !reduceMotion else {
            selectedTab = 2
            return
        }

        withAnimation(tabTransitionAnimation) {
            selectedTab = 2
        }
    }

    private func reviewQuickActionButton(
        title: String,
        subtitle: String,
        icon: String,
        tint: Color,
        isDisabled: Bool,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(spacing: 10) {
                Image(systemName: icon)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(tint)
                    .frame(width: 28, height: 28)
                    .background(tint.opacity(0.12), in: .circle)

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                    Text(subtitle)
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(AppTheme.subtleText)
                }

                Spacer(minLength: 0)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 10)
            .background(
                AppTheme.cardBg.opacity(isDisabled ? 0.35 : 0.75),
                in: .rect(cornerRadius: 12)
            )
            .overlay {
                RoundedRectangle(cornerRadius: 12)
                    .stroke(tint.opacity(isDisabled ? 0.08 : 0.2), lineWidth: 1)
            }
            .opacity(isDisabled ? 0.55 : 1.0)
        }
        .buttonStyle(.plain)
        .disabled(isDisabled)
        .accessibilityLabel(title)
        .accessibilityValue(isDisabled ? "Unavailable. \(subtitle)" : subtitle)
        .accessibilityHint(isDisabled ? "No matching clips for this action." : "Applies this action to matching clips.")
    }

    private var filterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(availableFilterOptions, id: \.self) { option in
                    Button {
                        HoopsAccessibility.animate(reduceMotion: reduceMotion) { filterOption = option }
                    } label: {
                        Text(filterTitle(for: option))
                            .font(.subheadline.weight(.medium))
                            .lineLimit(1)
                            .foregroundStyle(filterOption == option ? .white : AppTheme.subtleText)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 8)
                            .background(
                                filterOption == option ? AppTheme.accentPurple : AppTheme.cardBg,
                                in: .capsule
                            )
                    }
                    .accessibilityLabel("\(option.rawValue) clips")
                    .accessibilityValue(filterAccessibilityValue(for: option))
                    .accessibilityHint("Filters the review list.")
                    .hoopsSelectedState(filterOption == option)
                }
            }
        }
        .padding(10)
        .rorkCard(cornerRadius: 14, fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.45)), stroke: AppTheme.softBorder, glowOpacity: 0.03)
    }

    private var clipsList: some View {
        Group {
            if filteredClips.isEmpty {
                filteredEmptyState
            } else {
                LazyVStack(spacing: 12) {
                    ForEach(filteredClips) { clip in
                        clipCard(clip: clip)
                            .transition(.asymmetric(
                                insertion: .scale.combined(with: .opacity),
                                removal: .opacity
                            ))
                    }
                }
            }
        }
        .animation(.snappy, value: filterOption)
    }

    private var filteredEmptyState: some View {
        VStack(spacing: 8) {
            Image(systemName: "checkmark.seal.fill")
                .font(.title2)
                .foregroundStyle(AppTheme.successGreen)
            Text(emptyStateTitle)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.white)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 24)
        .rorkCard(
            cornerRadius: 14,
            fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.45)),
            stroke: AppTheme.softBorder,
            glowOpacity: 0.03
        )
        .accessibilityElement(children: .combine)
    }

    private var emptyStateTitle: String {
        switch filterOption {
        case .all:
            return "No clips"
        case .selectedTeam:
            return "No selected-team clips"
        case .teamUncertain:
            return "No clips to check"
        case .defense:
            return "No defensive clips"
        case .blocks:
            return "No block clips"
        case .steals:
            return "No steal clips"
        case .needsReview:
            return "No clips to check"
        case .kept:
            return "No kept clips"
        case .discarded:
            return "No skipped clips"
        }
    }

    private func filterTitle(for option: FilterOption) -> String {
        switch option {
        case .all:
            return "All \(viewModel.clips.count)"
        case .selectedTeam:
            return "Team \(clipCount(for: option))"
        case .teamUncertain:
            return "Check Team \(clipCount(for: option))"
        case .defense:
            return "Defense \(clipCount(for: option))"
        case .blocks:
            return "Blocks \(clipCount(for: option))"
        case .steals:
            return "Steals \(clipCount(for: option))"
        case .needsReview:
            return "Check \(viewModel.needsReviewClips.count)"
        case .kept:
            return "Kept \(viewModel.keptClips.count)"
        case .discarded:
            return "Skipped \(viewModel.discardedClips.count)"
        }
    }

    private func filterAccessibilityValue(for option: FilterOption) -> String {
        let count = clipCount(for: option)
        return filterOption == option ? "Selected, \(count) clips" : "\(count) clips"
    }

    private func clipCount(for option: FilterOption) -> Int {
        switch option {
        case .all:
            return viewModel.clips.count
        case .selectedTeam:
            return viewModel.clips.filter(clipMatchesSelectedTeam).count
        case .teamUncertain:
            return viewModel.clips.filter(clipNeedsTeamReview).count
        case .defense:
            return viewModel.clips.filter(isDefensiveClip).count
        case .blocks:
            return viewModel.clips.filter(isBlockClip).count
        case .steals:
            return viewModel.clips.filter(isStealClip).count
        case .needsReview:
            return viewModel.needsReviewClips.count
        case .kept:
            return viewModel.keptClips.count
        case .discarded:
            return viewModel.discardedClips.count
        }
    }

    private func clipCard(clip: Clip) -> some View {
        VStack(spacing: 0) {
            Button {
                selectedClip = clip
            } label: {
                HStack(spacing: 12) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 10)
                            .fill(actionColor(for: clip.action).opacity(0.15))
                            .frame(width: 44, height: 44)
                        Image(systemName: clip.action.icon)
                            .font(.title3)
                            .foregroundStyle(actionColor(for: clip.action))
                    }

                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 6) {
                            Text(clip.label)
                                .font(.headline)
                                .foregroundStyle(.white)
                            
                            if clip.detectionMethod == .ml {
                                Image(systemName: "sparkles")
                                    .font(.caption2)
                                    .foregroundStyle(AppTheme.neonPurple)
                            }
                        }
                        
                        HStack(spacing: 8) {
                            Text("\(clip.formattedStartTime) — \(clip.formattedEndTime)")
                                .font(.caption.monospacedDigit())
                            Text("•")
                            Text(clip.formattedDuration)
                                .font(.caption.monospacedDigit())
                        }
                        .foregroundStyle(AppTheme.subtleText)

                        clipContextBadges(clip)
                    }

                    Spacer()

                    confidenceBadge(level: clip.confidenceLevel, value: clip.confidence)
                }
                .padding(12)
            }
            .buttonStyle(.plain)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(clipAccessibilityLabel(clip))
            .accessibilityValue(clipAccessibilityValue(clip))
            .accessibilityHint("Opens clip detail preview.")

            if expandedClipID == clip.id {
                clipScoreBreakdown(clip: clip)
                    .padding(.horizontal, 12)
                    .padding(.bottom, 12)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }

            HStack(spacing: 8) {
                Button {
                    expandedClipID = expandedClipID == clip.id ? nil : clip.id
                } label: {
                    Image(systemName: "chart.bar.fill")
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .padding(8)
                }
                .accessibilityLabel(expandedClipID == clip.id ? "Hide score details" : "Show score details")
                .accessibilityValue("Combined score \(Int(clip.combinedScore * 100)) percent")
                .accessibilityHint("Shows audio, motion, visual, and combined score breakdown.")

                if clip.action == .dunk {
                    Button {
                        HoopsAccessibility.animate(reduceMotion: reduceMotion) {
                            viewModel.toggleSlowMotion(clip)
                        }
                    } label: {
                        Image(systemName: clip.isSlowMotionEnabled ? "tortoise.fill" : "hare.fill")
                            .font(.caption)
                            .foregroundStyle(clip.isSlowMotionEnabled ? AppTheme.neonPurple : AppTheme.subtleText)
                            .padding(8)
                            .background(
                                clip.isSlowMotionEnabled ? AppTheme.neonPurple.opacity(0.15) : Color.clear,
                                in: .circle
                            )
                    }
                    .accessibilityLabel(clip.isSlowMotionEnabled ? "Disable slow motion" : "Enable slow motion")
                    .accessibilityValue(clip.isSlowMotionEnabled ? "Selected" : "Not selected")
                    .accessibilityHint("Applies slow motion to this dunk clip in the exported reel.")
                    .hoopsSelectedState(clip.isSlowMotionEnabled)
                }

                Spacer()

                Button {
                    HoopsAccessibility.animate(reduceMotion: reduceMotion) {
                        viewModel.toggleClip(clip)
                        if clip.isKept {
                            discardTrigger += 1
                        } else {
                            keepTrigger += 1
                        }
                    }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: clip.isKept ? "xmark" : "checkmark")
                            .font(.caption.bold())
                        Text(clip.isKept ? "Skip" : "Keep")
                            .font(.caption.bold())
                    }
                    .foregroundStyle(clip.isKept ? AppTheme.dangerRed : AppTheme.successGreen)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(
                        (clip.isKept ? AppTheme.dangerRed : AppTheme.successGreen).opacity(0.15),
                        in: .capsule
                    )
                }
                .sensoryFeedback(.impact(weight: .light), trigger: keepTrigger)
                .sensoryFeedback(.impact(weight: .light), trigger: discardTrigger)
                .accessibilityLabel(clip.isKept ? "Skip clip" : "Keep clip")
                .accessibilityValue(clip.isKept ? "Kept" : "Skipped")
                .accessibilityHint("Toggles whether this clip is included in the finished video.")
                .hoopsSelectedState(clip.isKept)
            }
            .padding(.horizontal, 12)
            .padding(.bottom, 8)
        }
        .rorkCard(
            cornerRadius: 16,
            stroke: clip.isKept ? AppTheme.accentPurple.opacity(0.22) : AppTheme.softBorder,
            glow: clip.isKept ? AppTheme.neonPurple : AppTheme.accentPurple,
            glowOpacity: clip.isKept ? 0.09 : 0.04
        )
        .opacity(clip.isKept ? 1.0 : 0.6)
    }

    private func clipScoreBreakdown(clip: Clip) -> some View {
        VStack(spacing: 8) {
            Divider().overlay(AppTheme.accentPurple.opacity(0.2))
            scoreBar(label: "Audio", value: clip.audioScore, color: .blue)
            scoreBar(label: "Motion", value: clip.motionScore, color: .orange)
            scoreBar(label: "Visual", value: clip.visualScore, color: .green)
            scoreBar(label: "Combined", value: clip.combinedScore, color: AppTheme.neonPurple)
        }
    }

    private func scoreBar(label: String, value: Double, color: Color) -> some View {
        HStack(spacing: 8) {
            Text(label)
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .frame(width: 60, alignment: .leading)

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(Color.white.opacity(0.05))
                    Capsule()
                        .fill(color)
                        .frame(width: geo.size.width * min(value, 1.0))
                }
            }
            .frame(height: 6)

            Text("\(Int(value * 100))%")
                .font(.caption2.monospacedDigit())
                .foregroundStyle(AppTheme.subtleText)
                .frame(width: 35, alignment: .trailing)
        }
    }

    private func confidenceBadge(level: ConfidenceLevel, value: Double) -> some View {
        let color: Color = switch level {
        case .high: AppTheme.successGreen
        case .medium: AppTheme.warningYellow
        case .low: .orange
        }

        return Text("\(Int(value * 100))%")
            .font(.caption.bold().monospacedDigit())
            .foregroundStyle(color)
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(color.opacity(0.15), in: .capsule)
            .accessibilityLabel("Confidence")
            .accessibilityValue("\(Int(value * 100)) percent, \(level.rawValue)")
    }

    @ViewBuilder
    private func clipReviewBadges(_ clip: Clip) -> some View {
        if !clip.reviewBadges.isEmpty {
            HStack(spacing: 6) {
                ForEach(clip.reviewBadges, id: \.self) { badge in
                    Label(badge.title, systemImage: badge.systemImage)
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(AppTheme.warningYellow)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                        .background(AppTheme.warningYellow.opacity(0.14), in: .capsule)
                        .accessibilityLabel(badge.accessibilityLabel)
                }
            }
        }
    }

    @ViewBuilder
    private func clipContextBadges(_ clip: Clip) -> some View {
        let teamTitle = clipTeamDisplayTitle(clip)
        if teamTitle != nil || !clip.reviewBadges.isEmpty || isDefensiveClip(clip) {
            HStack(spacing: 6) {
                if let teamTitle {
                    Label(teamTitle, systemImage: clipNeedsTeamReview(clip) ? "person.2.badge.gearshape.fill" : "person.2.fill")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(clipNeedsTeamReview(clip) ? AppTheme.warningYellow : AppTheme.neonPurple)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                        .background((clipNeedsTeamReview(clip) ? AppTheme.warningYellow : AppTheme.neonPurple).opacity(0.14), in: .capsule)
                        .accessibilityLabel(clipNeedsTeamReview(clip) ? "team attribution needs review" : "team attribution")
                        .accessibilityValue(teamTitle)
                }

                if isDefensiveClip(clip) {
                    Label(defensiveBadgeTitle(for: clip), systemImage: defensiveBadgeIcon(for: clip))
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(.orange)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                        .background(Color.orange.opacity(0.14), in: .capsule)
                        .accessibilityLabel("defensive highlight")
                        .accessibilityValue(defensiveBadgeTitle(for: clip))
                }

                ForEach(clip.reviewBadges, id: \.self) { badge in
                    Label(badge.title, systemImage: badge.systemImage)
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(AppTheme.warningYellow)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                        .background(AppTheme.warningYellow.opacity(0.14), in: .capsule)
                        .accessibilityLabel(badge.accessibilityLabel)
                }
            }
        }
    }

    private func clipTeamDisplayTitle(_ clip: Clip) -> String? {
        guard let teamAttribution = clip.teamAttribution else { return nil }
        return teamAttribution.label ?? teamAttribution.colorLabel ?? readableTeamIdentifier(teamAttribution.teamId)
    }

    private func readableTeamIdentifier(_ value: String?) -> String? {
        guard let value, !value.isEmpty else { return nil }
        return value
            .replacingOccurrences(of: "_", with: " ")
            .split(separator: " ")
            .map { $0.capitalized }
            .joined(separator: " ")
    }

    private func clipMatchesSelectedTeam(_ clip: Clip) -> Bool {
        let selection = viewModel.settings.highlightTeamSelection
        guard selection.mode == .team,
              let attribution = clip.teamAttribution,
              !clipNeedsTeamReview(clip) else {
            return false
        }
        return normalizedTeamKeys(for: selection).contains { key in
            normalizedTeamKeys(for: attribution).contains(key)
        }
    }

    private func clipNeedsTeamReview(_ clip: Clip) -> Bool {
        if clip.teamAttributionStatus == "uncertain" {
            return true
        }
        guard let attribution = clip.teamAttribution else {
            return viewModel.settings.highlightTeamSelection.mode == .team
        }
        return attribution.confidence < viewModel.settings.highlightTeamSelection.confidenceThreshold
    }

    private func normalizedTeamKeys(for selection: HighlightTeamSelection) -> [String] {
        [selection.teamId, selection.colorLabel, selection.label]
            .compactMap(normalizedTeamKey)
    }

    private func normalizedTeamKeys(for attribution: ClipTeamAttribution) -> [String] {
        [attribution.teamId, attribution.colorLabel, attribution.label]
            .compactMap(normalizedTeamKey)
    }

    private func normalizedTeamKey(_ value: String?) -> String? {
        guard let value else { return nil }
        let normalized = value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return normalized.isEmpty ? nil : normalized
    }

    private func isDefensiveClip(_ clip: Clip) -> Bool {
        isBlockClip(clip) || isStealClip(clip) || normalizedClipLabel(clip).contains(where: { token in
            ["defense", "defensive", "deflection", "pressure", "lockdown", "contest", "charge", "stop", "turnover", "forced", "strip"].contains(token)
        })
    }

    private func isBlockClip(_ clip: Clip) -> Bool {
        clip.action == .block || normalizedClipLabel(clip).contains("block") || normalizedClipLabel(clip).contains("blocked")
    }

    private func isStealClip(_ clip: Clip) -> Bool {
        clip.action == .steal || normalizedClipLabel(clip).contains("steal") || normalizedClipLabel(clip).contains("strip")
    }

    private func normalizedClipLabel(_ clip: Clip) -> Set<String> {
        let words = clip.label.lowercased().split { !$0.isLetter && !$0.isNumber }
        return Set(words.map(String.init))
    }

    private func defensiveBadgeTitle(for clip: Clip) -> String {
        if isBlockClip(clip) { return "Block" }
        if isStealClip(clip) { return "Steal" }
        return "Defense"
    }

    private func defensiveBadgeIcon(for clip: Clip) -> String {
        if isBlockClip(clip) { return "shield.fill" }
        if isStealClip(clip) { return "hand.raised.fill" }
        return "figure.basketball"
    }

    private func actionColor(for action: HighlightAction) -> Color {
        switch action {
        case .dunk, .posterize: return .red
        case .layup, .madeShot: return AppTheme.successGreen
        case .threePointer, .buzzerBeater: return AppTheme.warningYellow
        case .steal, .crossover: return .blue
        case .block: return .orange
        case .fastBreak, .alleyOop: return AppTheme.neonPurple
        case .unknown: return AppTheme.subtleText
        }
    }

    private func prepareClipPlayer(for clip: Clip) {
        teardownClipPlayer()
        clipPlaybackRange = clip.startTime...clip.endTime

        guard let url = viewModel.videoURL else { return }

        let playerItem = AVPlayerItem(url: url)
        let clipEnd = CMTime(seconds: clip.endTime, preferredTimescale: 600)
        let clipStart = CMTime(seconds: clip.startTime, preferredTimescale: 600)
        playerItem.forwardPlaybackEndTime = clipEnd

        let player = AVPlayer(playerItem: playerItem)
        clipLoopObserverToken = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: playerItem,
            queue: .main
        ) { [weak player] _ in
            guard let player else { return }
            player.seek(to: clipStart, toleranceBefore: .zero, toleranceAfter: .zero) { _ in
                player.play()
            }
        }

        clipPlayer = player
        player.seek(to: clipStart, toleranceBefore: .zero, toleranceAfter: .zero) { _ in
            player.play()
        }
    }

    private func teardownClipPlayer() {
        clipPlayer?.pause()
        clipPlayer = nil
        clipPlaybackRange = nil

        if let clipLoopObserverToken {
            NotificationCenter.default.removeObserver(clipLoopObserverToken)
            self.clipLoopObserverToken = nil
        }
    }

    private func clipDetailSheet(clip: Clip) -> some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.16)

                ScrollView {
                    VStack(spacing: 20) {
                        if let clipPlayer {
                            VideoPlayer(player: clipPlayer)
                                .frame(height: 220)
                                .clipShape(.rect(cornerRadius: 16))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 16)
                                        .stroke(AppTheme.accentPurple.opacity(0.3), lineWidth: 1)
                                )
                                .accessibilityLabel("Clip preview")
                                .accessibilityValue("\(clip.label), \(clip.formattedStartTime) to \(clip.formattedEndTime)")
                                .accessibilityHint("Loops the selected highlight clip.")
                        } else {
                            ContentUnavailableView {
                                Label("Clip Preview Unavailable", systemImage: "video.slash.fill")
                            } description: {
                                Text("The source video is not available, so this clip can’t be previewed right now.")
                            }
                            .frame(height: 220)
                            .foregroundStyle(.white)
                            .background(AppTheme.cardBg, in: .rect(cornerRadius: 16))
                        }

                        if clipPlaybackRange != nil {
                            Text("Looping selected clip")
                                .font(.caption2.weight(.medium))
                                .foregroundStyle(AppTheme.subtleText)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        VStack(spacing: 12) {
                            HStack {
                                Image(systemName: clip.action.icon)
                                    .font(.title2)
                                    .foregroundStyle(actionColor(for: clip.action))
                                Text(clip.label)
                                    .font(.title2.bold())
                                    .foregroundStyle(.white)
                                
                                if clip.detectionMethod == .ml {
                                    Text("AI")
                                        .font(.caption2.bold())
                                        .foregroundStyle(.white)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(AppTheme.neonPurple, in: .capsule)
                                }

                                clipContextBadges(clip)
                                
                                Spacer()
                                confidenceBadge(level: clip.confidenceLevel, value: clip.confidence)
                            }

                            HStack(spacing: 16) {
                                Label(clip.formattedStartTime, systemImage: "play.fill")
                                Label(clip.formattedEndTime, systemImage: "stop.fill")
                                Label(clip.formattedDuration, systemImage: "timer")
                            }
                            .font(.caption)
                            .foregroundStyle(AppTheme.subtleText)
                        }
                        .padding(16)
                        .background(AppTheme.cardBg, in: .rect(cornerRadius: 16))

                        clipScoreBreakdown(clip: clip)
                            .padding(16)
                            .background(AppTheme.cardBg, in: .rect(cornerRadius: 16))
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 40)
                }
            }
            .navigationTitle("Clip Detail")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { selectedClip = nil }
                        .foregroundStyle(AppTheme.neonPurple)
                }
            }
        }
        .presentationDetents([.large])
        .presentationDragIndicator(.visible)
        .presentationBackground(AppTheme.darkBg)
        .onAppear {
            prepareClipPlayer(for: clip)
        }
        .onDisappear {
            teardownClipPlayer()
        }
    }

    private func clipAccessibilityLabel(_ clip: Clip) -> String {
        "\(clip.label), \(clip.formattedStartTime) to \(clip.formattedEndTime)"
    }

    private func clipAccessibilityValue(_ clip: Clip) -> String {
        let keepState = clip.isKept ? "Kept" : "Skipped"
        let reviewNotes = clip.reviewBadges.map(\.accessibilityLabel)
        let reviewText = reviewNotes.isEmpty ? "" : " Review flags: \(reviewNotes.joined(separator: ", "))."
        return "\(keepState). Confidence \(Int(clip.confidence * 100)) percent. Duration \(clip.formattedDuration).\(reviewText)"
    }
}
