import SwiftUI
import AVKit

struct ReviewView: View {
    @Bindable var viewModel: HighlightsViewModel
    @Binding var selectedTab: Int
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var selectedClip: Clip?
    @State private var clipPlayer: AVPlayer?
    @AppStorage("hoops.previewAudioMuted.v1") private var previewAudioMuted = false
    @State private var clipLoopObserverToken: NSObjectProtocol?
    @State private var clipPlaybackRange: ClosedRange<Double>?
    @State private var filterOption: FilterOption = .all
    @State private var hasAutoFocusedPriorityFilter = false
    @State private var sortByScore = true
    @State private var expandedClipID: UUID?
    @State private var focusedClipID: UUID?
    @State private var showAllFilterChips = false
    @State private var keepTrigger = 0
    @State private var discardTrigger = 0
    @State private var reviewUndoToast: ReviewDecisionUndoToast?
    @State private var reviewUndoToastDismissTask: Task<Void, Never>?
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    private let tabTransitionAnimation = Animation.interactiveSpring(
        response: 0.42,
        dampingFraction: 0.96,
        blendDuration: 0.12
    )

    private enum FilterOption: String, CaseIterable {
        case all = "All"
        case priority = "Priority"
        case selectedTeam = "Team"
        case teamUncertain = "Check Team"
        case defense = "Defense"
        case blocks = "Blocks"
        case steals = "Steals"
        case sound = "Sound"
        case needsReview = "Check"
        case kept = "Kept"
        case discarded = "Skipped"
    }

    private struct ReviewDecisionUndoToast: Identifiable, Equatable {
        let id = UUID()
        let clipID: UUID
        let clipLabel: String
        let previousKeep: Bool
        let decidedKeep: Bool

        var title: String {
            decidedKeep ? "Kept clip" : "Marked nah"
        }

        var message: String {
            "\(clipLabel) updated. Undo if that was a misclick."
        }
    }

    private var filteredClips: [Clip] {
        let base: [Clip]
        switch filterOption {
        case .all: base = viewModel.clips
        case .priority: base = priorityReviewClips
        case .selectedTeam: base = viewModel.clips.filter(clipMatchesSelectedTeam)
        case .teamUncertain: base = viewModel.clips.filter(clipNeedsTeamReview)
        case .defense: base = viewModel.clips.filter(isDefensiveClip)
        case .blocks: base = viewModel.clips.filter(isBlockClip)
        case .steals: base = viewModel.clips.filter(isStealClip)
        case .sound: base = viewModel.audioReactionReviewClips
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
                            reviewCarousel
                            filterBar
                            priorityReviewCard
                            reviewContextStrip
                            quickActionsBar
                            aiEditEntryCard
                        }
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                        .padding(.bottom, 100)
                    }
                }

                reviewUndoToastView
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
            .onAppear {
                focusPriorityReviewIfNeeded()
                settleFocusedClipIfNeeded()
            }
            .onChange(of: priorityReviewClips.map(\.id)) { _, _ in
                focusPriorityReviewIfNeeded()
                settleFocusedClipIfNeeded()
            }
            .onChange(of: filteredClips.map(\.id)) { _, _ in
                settleFocusedClipIfNeeded()
            }
            .onChange(of: currentReviewClip?.id) { _, _ in
                if let currentReviewClip {
                    prepareClipPlayer(for: currentReviewClip)
                } else {
                    teardownClipPlayer()
                }
            }
            .onDisappear {
                reviewUndoToastDismissTask?.cancel()
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

    @ViewBuilder
    private var reviewUndoToastView: some View {
        if let reviewUndoToast {
            VStack {
                Spacer()

                HStack(spacing: 12) {
                    Image(systemName: reviewUndoToast.decidedKeep ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .font(.title3.weight(.bold))
                        .foregroundStyle(reviewUndoToast.decidedKeep ? AppTheme.successGreen : AppTheme.dangerRed)
                        .accessibilityHidden(true)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(reviewUndoToast.title)
                            .font(.subheadline.weight(.heavy))
                            .foregroundStyle(.white)
                        Text(reviewUndoToast.message)
                            .font(.caption)
                            .foregroundStyle(AppTheme.subtleText)
                            .lineLimit(2)
                    }
                    .layoutPriority(1)

                    Button {
                        undoLastReviewDecision(reviewUndoToast)
                    } label: {
                        Text("Undo")
                            .font(.caption.weight(.heavy))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(AppTheme.neonPurple.opacity(0.32), in: .capsule)
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("review.carousel.undoToast.undoButton")
                    .accessibilityLabel("Undo last review decision")
                }
                .padding(14)
                .background(
                    LinearGradient(
                        colors: [
                            Color(red: 0.05, green: 0.04, blue: 0.15).opacity(0.96),
                            AppTheme.accentPurple.opacity(0.42)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    in: .rect(cornerRadius: 18)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 18)
                        .stroke(AppTheme.neonPurple.opacity(0.34), lineWidth: 1)
                )
                .shadow(color: AppTheme.neonPurple.opacity(0.24), radius: 18, y: 8)
                .padding(.horizontal, 16)
                .padding(.bottom, 88)
                .transition(.move(edge: .bottom).combined(with: .opacity))
                .accessibilityIdentifier("review.carousel.undoToast")
            }
        }
    }

    private var headerStats: some View {
        LazyVGrid(columns: reviewStatGridColumns, spacing: 10) {
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

    private var reviewStatGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize.isAccessibilitySize ? 148 : 76
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 180), spacing: 10, alignment: .top)
        ]
    }

    private func reviewStatCard(value: String, label: String, icon: String, color: Color) -> some View {
        VStack(spacing: 6) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(color)
            Text(value)
                .font(.headline.monospacedDigit())
                .foregroundStyle(.white)
                .lineLimit(1)
                .minimumScaleFactor(0.82)
            Text(label)
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 112 : 92)
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
        let selectedCount = viewModel.keptClips.count
        let needsCheckCount = viewModel.needsReviewClips.count
        let progress = Double(selectedCount) / Double(total)
        let summary = ReviewProgressCopy.summary(
            selectedCount: selectedCount,
            totalCount: viewModel.clips.count,
            needsCheckCount: needsCheckCount
        )

        return VStack(alignment: .leading, spacing: 10) {
            ViewThatFits(in: .horizontal) {
                HStack {
                    Label(ReviewProgressCopy.title, systemImage: "checklist")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                        .lineLimit(2)
                    Spacer()
                    Text(summary)
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(2)
                        .minimumScaleFactor(0.84)
                        .multilineTextAlignment(.trailing)
                        .fixedSize(horizontal: false, vertical: true)
                }

                VStack(alignment: .leading, spacing: 3) {
                    Label(ReviewProgressCopy.title, systemImage: "checklist")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                    Text(summary)
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(3)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            ProgressView(value: progress)
                .tint(AppTheme.neonPurple)
                .scaleEffect(y: 1.8)
                .accessibilityLabel(ReviewProgressCopy.title)
                .accessibilityValue(
                    ReviewProgressCopy.accessibilityValue(
                        selectedCount: selectedCount,
                        totalCount: viewModel.clips.count,
                        needsCheckCount: needsCheckCount
                    )
                )

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

    private var currentReviewIndex: Int {
        guard !filteredClips.isEmpty else { return 0 }
        if let focusedClipID,
           let index = filteredClips.firstIndex(where: { $0.id == focusedClipID }) {
            return index
        }
        return 0
    }

    private var currentReviewClip: Clip? {
        guard !filteredClips.isEmpty else { return nil }
        return filteredClips[currentReviewIndex]
    }

    private var canReviewPreviousClip: Bool {
        currentReviewClip != nil && currentReviewIndex > 0
    }

    private var canReviewNextClip: Bool {
        currentReviewClip != nil && currentReviewIndex < filteredClips.count - 1
    }

    private var reviewCarouselChipColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize.isAccessibilitySize ? 142 : 92
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 190), spacing: 8, alignment: .top)
        ]
    }

    @ViewBuilder
    private var reviewCarousel: some View {
        if let clip = currentReviewClip {
            VStack(alignment: .leading, spacing: 14) {
                reviewCarouselHeader(clip: clip)
                reviewCarouselPlayer(clip: clip)
                reviewCarouselClipSummary(clip)
                reviewDecisionButtons(clip: clip)
                reviewCarouselEvidenceChips(clip)

                if expandedClipID == clip.id {
                    VStack(alignment: .leading, spacing: 12) {
                        clipScoreBreakdown(clip: clip, includeDivider: false)
                        clipEvidenceRows(clip: clip, maxRows: 3)
                    }
                    .padding(12)
                    .background(AppTheme.cardBg.opacity(0.58), in: .rect(cornerRadius: 14))
                    .transition(.move(edge: .top).combined(with: .opacity))
                }
            }
            .padding(14)
            .rorkCard(
                cornerRadius: 24,
                fill: AnyShapeStyle(
                    LinearGradient(
                        colors: [
                            Color(red: 0.04, green: 0.03, blue: 0.12).opacity(0.98),
                            AppTheme.accentPurple.opacity(0.26),
                            AppTheme.surfaceBg.opacity(0.96)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                ),
                stroke: AppTheme.neonPurple.opacity(0.32),
                glow: AppTheme.neonPurple,
                glowOpacity: 0.14
            )
            .overlay {
                RoundedRectangle(cornerRadius: 24)
                    .stroke(
                        LinearGradient(
                            colors: [
                                AppTheme.neonPurple.opacity(0.52),
                                .white.opacity(0.08),
                                AppTheme.accentPurple.opacity(0.24)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        lineWidth: 1
                    )
            }
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("review.carousel")
        } else {
            VStack(alignment: .leading, spacing: 12) {
                Label(emptyStateTitle, systemImage: "line.3.horizontal.decrease.circle")
                    .font(.headline)
                    .foregroundStyle(.white)

                Text("Try All clips or another filter to keep reviewing.")
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)

                Button {
                    HoopsAccessibility.animate(reduceMotion: reduceMotion) {
                        filterOption = .all
                        focusedClipID = viewModel.clips.first?.id
                    }
                    settleFocusedClipIfNeeded()
                } label: {
                    Label("Show All Clips", systemImage: "film.stack.fill")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(AppTheme.neonPurple.opacity(0.22), in: .capsule)
                }
                .buttonStyle(.plain)
            }
            .padding(16)
            .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder, glowOpacity: 0.04)
        }
    }

    private func reviewCarouselHeader(clip: Clip) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .center, spacing: 12) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Review Clips")
                        .font(.title3.weight(.heavy))
                        .foregroundStyle(.white)

                    Label("Clip \(currentReviewIndex + 1) of \(filteredClips.count)", systemImage: "sparkles")
                        .font(.caption.bold().monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(AppTheme.neonPurple.opacity(0.16), in: .capsule)
                }

                Spacer(minLength: 0)

                Text(clip.isKept ? "KEEPING" : "NAH")
                    .font(.caption.bold().monospaced())
                    .foregroundStyle(clip.isKept ? AppTheme.successGreen : AppTheme.dangerRed)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background((clip.isKept ? AppTheme.successGreen : AppTheme.dangerRed).opacity(0.14), in: .capsule)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Review Clips")
                    .font(.title3.weight(.heavy))
                    .foregroundStyle(.white)

                HStack(spacing: 8) {
                    Label("Clip \(currentReviewIndex + 1) of \(filteredClips.count)", systemImage: "sparkles")
                        .font(.caption.bold().monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)

                    Text(clip.isKept ? "KEEPING" : "NAH")
                        .font(.caption.bold().monospaced())
                        .foregroundStyle(clip.isKept ? AppTheme.successGreen : AppTheme.dangerRed)
                }
            }
        }
    }

    private func reviewCarouselPlayer(clip: Clip) -> some View {
        ZStack {
            Group {
                if let clipPlayer {
                    VideoPlayer(player: clipPlayer)
                        .accessibilityLabel("Current review clip preview")
                        .accessibilityValue("\(clip.label), \(clip.formattedStartTime) to \(clip.formattedEndTime)")
                        .accessibilityHint("Loops the current clip while you choose Keep or Nah.")
                } else {
                    ContentUnavailableView {
                        Label("Preview Unavailable", systemImage: "video.slash.fill")
                    } description: {
                        Text("The source video is not available, but you can still keep or nah this clip.")
                    }
                    .foregroundStyle(.white)
                    .background(AppTheme.cardBg)
                }
            }
            .frame(height: dynamicTypeSize.isAccessibilitySize ? 320 : 286)
            .clipShape(.rect(cornerRadius: 20))
            .overlay(
                RoundedRectangle(cornerRadius: 20)
                    .stroke(AppTheme.neonPurple.opacity(0.42), lineWidth: 1)
            )
            .shadow(color: AppTheme.neonPurple.opacity(0.24), radius: 18, y: 10)

            HStack {
                reviewCarouselArrowButton(systemImage: "chevron.left", accessibilityLabel: "Previous clip", isEnabled: canReviewPreviousClip) {
                    moveFocusedClip(by: -1)
                }

                Spacer()

                reviewCarouselArrowButton(systemImage: "chevron.right", accessibilityLabel: "Next clip", isEnabled: canReviewNextClip) {
                    moveFocusedClip(by: 1)
                }
            }
            .padding(.horizontal, 10)

            VStack {
                HStack {
                    Spacer()
                    Button {
                        previewAudioMuted.toggle()
                        applyClipPreviewAudioMute()
                    } label: {
                        Image(systemName: previewAudioMuted ? "speaker.slash.fill" : "speaker.wave.2.fill")
                            .font(.caption.weight(.bold))
                            .foregroundStyle(.white)
                            .padding(10)
                            .background(AppTheme.neonPurple.opacity(0.52), in: Circle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("review.carousel.muteToggle")
                    .accessibilityLabel(previewAudioMuted ? "Unmute current clip" : "Mute current clip")
                }
                Spacer()
            }
            .padding(12)
        }
    }

    private func reviewCarouselArrowButton(
        systemImage: String,
        accessibilityLabel: String,
        isEnabled: Bool,
        action: @escaping () -> Void
    ) -> some View {
        Button {
            action()
        } label: {
            Image(systemName: systemImage)
                .font(.title3.weight(.heavy))
                .foregroundStyle(.white)
                .frame(width: 46, height: 66)
                .background(AppTheme.neonPurple.opacity(isEnabled ? 0.46 : 0.16), in: .capsule)
                .overlay(
                    Capsule()
                        .stroke(AppTheme.neonPurple.opacity(isEnabled ? 0.34 : 0.10), lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
        .disabled(!isEnabled)
        .opacity(isEnabled ? 1.0 : 0.44)
        .accessibilityLabel(accessibilityLabel)
    }

    private func reviewCarouselClipSummary(_ clip: Clip) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 12) {
                clipActionIcon(clip)

                VStack(alignment: .leading, spacing: 5) {
                    Text(clip.label)
                        .font(.title3.bold())
                        .foregroundStyle(.white)
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                        .minimumScaleFactor(0.82)
                        .fixedSize(horizontal: false, vertical: true)

                    clipTimingText(clip)
                    clipContextBadges(clip)
                }
                .layoutPriority(1)
            }

            Button {
                HoopsAccessibility.animate(reduceMotion: reduceMotion) {
                    expandedClipID = expandedClipID == clip.id ? nil : clip.id
                }
            } label: {
                Label(expandedClipID == clip.id ? "Hide why" : "Why this clip?", systemImage: "checkmark.seal.fill")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.neonPurple)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(AppTheme.neonPurple.opacity(0.14), in: .capsule)
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("review.carousel.whyButton")
        }
    }

    private func reviewDecisionButtons(clip: Clip) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 10) {
                reviewDecisionButton(clip: clip, keep: true)
                reviewDecisionButton(clip: clip, keep: false)
            }

            VStack(spacing: 10) {
                reviewDecisionButton(clip: clip, keep: true)
                reviewDecisionButton(clip: clip, keep: false)
            }
        }
    }

    private func reviewDecisionButton(clip: Clip, keep: Bool) -> some View {
        let tint = keep ? AppTheme.successGreen : AppTheme.dangerRed
        let isSelected = clip.isKept == keep

        return Button {
            setClip(clip, keep: keep)
        } label: {
            HStack(spacing: 10) {
                Image(systemName: keep ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .font(.title3.weight(.heavy))
                    .accessibilityHidden(true)
                Text(keep ? "KEEP" : "NAH")
                    .font(.headline.weight(.heavy))
                    .tracking(0.8)
                    .lineLimit(1)
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 64 : 56)
            .background(
                LinearGradient(
                    colors: [
                        tint.opacity(isSelected ? 0.98 : 0.62),
                        tint.opacity(isSelected ? 0.72 : 0.36)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ),
                in: .rect(cornerRadius: 18)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 18)
                    .stroke(.white.opacity(isSelected ? 0.28 : 0.12), lineWidth: 1)
            )
            .shadow(color: tint.opacity(isSelected ? 0.28 : 0.08), radius: isSelected ? 18 : 8, y: 8)
        }
        .buttonStyle(.plain)
        .sensoryFeedback(.impact(weight: .medium), trigger: keep ? keepTrigger : discardTrigger)
        .accessibilityIdentifier(keep ? "review.carousel.keepButton" : "review.carousel.nahButton")
        .accessibilityLabel(keep ? "Keep clip" : "Nah, skip clip")
        .accessibilityValue(isSelected ? "Selected" : "Not selected")
        .hoopsSelectedState(isSelected)
    }

    private func reviewCarouselEvidenceChips(_ clip: Clip) -> some View {
        LazyVGrid(columns: reviewCarouselChipColumns, alignment: .leading, spacing: 8) {
            RorkMetricChip(
                icon: "chart.bar.fill",
                value: "\(Int(clip.combinedScore * 100))%",
                label: "Score",
                tint: AppTheme.neonPurple
            )
            RorkMetricChip(
                icon: "scope",
                value: "\(Int(clip.confidence * 100))%",
                label: "Confidence",
                tint: actionColor(for: clip.action)
            )
            RorkMetricChip(
                icon: "timer",
                value: clip.formattedDuration,
                label: "Length",
                tint: AppTheme.warningYellow
            )
            RorkMetricChip(
                icon: clipNeedsTeamReview(clip) ? "person.2.badge.gearshape.fill" : "checkmark.seal.fill",
                value: clipNeedsTeamReview(clip) ? "Check" : "Ready",
                label: "Review",
                tint: clipNeedsTeamReview(clip) ? AppTheme.warningYellow : AppTheme.successGreen
            )
        }
    }

    private func settleFocusedClipIfNeeded() {
        guard let firstClip = filteredClips.first else {
            focusedClipID = nil
            teardownClipPlayer()
            return
        }

        if let focusedClipID,
           let focusedClip = filteredClips.first(where: { $0.id == focusedClipID }) {
            if clipPlayer == nil {
                prepareClipPlayer(for: focusedClip)
            }
            return
        }

        focusedClipID = firstClip.id
        prepareClipPlayer(for: firstClip)
    }

    private func moveFocusedClip(by offset: Int) {
        guard currentReviewClip != nil else { return }
        let targetIndex = currentReviewIndex + offset
        guard filteredClips.indices.contains(targetIndex) else { return }

        HoopsAccessibility.animate(reduceMotion: reduceMotion) {
            expandedClipID = nil
            focusedClipID = filteredClips[targetIndex].id
        }
        prepareClipPlayer(for: filteredClips[targetIndex])
    }

    private func setClip(_ clip: Clip, keep: Bool) {
        let previousKeep = clip.isKept
        let visibleClipsBeforeDecision = filteredClips

        HoopsAccessibility.animate(reduceMotion: reduceMotion) {
            if previousKeep != keep {
                viewModel.toggleClip(clip)
            }
            if keep {
                keepTrigger += 1
            } else {
                discardTrigger += 1
            }
        }

        showUndoToast(for: clip, previousKeep: previousKeep, decidedKeep: keep)
        advanceAfterDecision(from: clip, visibleClipsBeforeDecision: visibleClipsBeforeDecision)
    }

    private func advanceAfterDecision(from clip: Clip, visibleClipsBeforeDecision: [Clip]) {
        guard let previousIndex = visibleClipsBeforeDecision.firstIndex(where: { $0.id == clip.id }) else {
            settleFocusedClipIfNeeded()
            return
        }

        if visibleClipsBeforeDecision.indices.contains(previousIndex + 1) {
            let nextClip = visibleClipsBeforeDecision[previousIndex + 1]
            guard filteredClips.contains(where: { $0.id == nextClip.id }) else {
                settleFocusedClipIfNeeded()
                return
            }

            HoopsAccessibility.animate(reduceMotion: reduceMotion) {
                expandedClipID = nil
                focusedClipID = nextClip.id
            }
            prepareClipPlayer(for: nextClip)
        } else if filteredClips.contains(where: { $0.id == clip.id }) {
            return
        } else if visibleClipsBeforeDecision.indices.contains(previousIndex - 1) {
            let previousClip = visibleClipsBeforeDecision[previousIndex - 1]
            guard filteredClips.contains(where: { $0.id == previousClip.id }) else {
                settleFocusedClipIfNeeded()
                return
            }

            HoopsAccessibility.animate(reduceMotion: reduceMotion) {
                expandedClipID = nil
                focusedClipID = previousClip.id
            }
            prepareClipPlayer(for: previousClip)
        } else {
            settleFocusedClipIfNeeded()
        }
    }

    private func showUndoToast(for clip: Clip, previousKeep: Bool, decidedKeep: Bool) {
        let toast = ReviewDecisionUndoToast(
            clipID: clip.id,
            clipLabel: clip.label,
            previousKeep: previousKeep,
            decidedKeep: decidedKeep
        )

        reviewUndoToastDismissTask?.cancel()
        withAnimation(.spring(response: 0.32, dampingFraction: 0.86)) {
            reviewUndoToast = toast
        }

        reviewUndoToastDismissTask = Task {
            try? await Task.sleep(nanoseconds: 4_000_000_000)
            guard !Task.isCancelled else { return }
            await MainActor.run {
                guard reviewUndoToast?.id == toast.id else { return }
                withAnimation(.easeOut(duration: 0.18)) {
                    reviewUndoToast = nil
                }
            }
        }
    }

    private func undoLastReviewDecision(_ toast: ReviewDecisionUndoToast) {
        reviewUndoToastDismissTask?.cancel()

        guard let clip = viewModel.clips.first(where: { $0.id == toast.clipID }) else {
            withAnimation(.easeOut(duration: 0.18)) {
                reviewUndoToast = nil
            }
            return
        }

        HoopsAccessibility.animate(reduceMotion: reduceMotion) {
            if clip.isKept != toast.previousKeep {
                viewModel.toggleClip(clip)
            }
            expandedClipID = nil
            focusedClipID = clip.id
        }
        prepareClipPlayer(for: clip)

        withAnimation(.easeOut(duration: 0.18)) {
            reviewUndoToast = nil
        }
    }

    private var highConfidencePendingCount: Int {
        viewModel.clips.filter {
            !$0.isKept && viewModel.shouldAutoKeepHighConfidenceClip($0)
        }.count
    }

    private var highConfidencePendingSubtitle: String {
        let noun = highConfidencePendingCount == 1 ? "clip" : "clips"
        if selectedTeamFilterIsAvailable {
            return "\(highConfidencePendingCount) target team \(noun)"
        }
        return "\(highConfidencePendingCount) strong \(noun)"
    }

    private var lowConfidenceKeptCount: Int {
        viewModel.clips.filter {
            $0.confidence < 0.5
                && $0.isKept
                && !HighlightsViewModel.protectsClipFromQuickSkip(
                    $0,
                    teamSelection: viewModel.settings.highlightTeamSelection
                )
        }.count
    }

    private var lowConfidenceKeptSubtitle: String {
        let noun = lowConfidenceKeptCount == 1 ? "clip" : "clips"
        return "\(lowConfidenceKeptCount) \(noun) safe to skip"
    }

    private var selectedTeamFilterIsAvailable: Bool {
        viewModel.settings.highlightTeamSelection.mode == .team
    }

    private var availableFilterOptions: [FilterOption] {
        var options: [FilterOption] = [.all]

        for option in allOptionalFilterOptions where shouldShowFilter(option) {
            options.append(option)
        }

        if !options.contains(filterOption) {
            options.append(filterOption)
        }
        return options
    }

    private var visibleFilterOptions: [FilterOption] {
        ReviewFilterDisplayPolicy.visibleItems(
            available: availableFilterOptions,
            primary: primaryFilterOptions,
            active: filterOption,
            showAll: showAllFilterChips
        )
    }

    private var hiddenFilterOptions: [FilterOption] {
        ReviewFilterDisplayPolicy.hiddenItems(
            available: availableFilterOptions,
            primary: primaryFilterOptions,
            active: filterOption,
            showAll: showAllFilterChips
        )
    }

    private var allOptionalFilterOptions: [FilterOption] {
        [.priority, .selectedTeam, .teamUncertain, .defense, .blocks, .steals, .sound, .needsReview, .kept, .discarded]
    }

    private var primaryFilterOptions: Set<FilterOption> {
        [.all, .priority, .selectedTeam, .teamUncertain, .needsReview]
    }

    private func shouldShowFilter(_ option: FilterOption) -> Bool {
        if option == filterOption { return true }
        switch option {
        case .all:
            return true
        case .priority:
            return clipCount(for: option) > 0
        case .selectedTeam:
            return selectedTeamFilterIsAvailable && clipCount(for: option) > 0
        case .teamUncertain, .defense, .blocks, .steals, .sound, .needsReview, .kept, .discarded:
            return clipCount(for: option) > 0
        }
    }

    private var selectedTeamSummaryTitle: String {
        let selection = viewModel.settings.highlightTeamSelection
        guard selection.mode == .team else { return "All teams" }
        return selection.displayTitle
    }

    private var priorityReviewClips: [Clip] {
        viewModel.priorityReviewClips
    }

    private var priorityReviewFilter: FilterOption {
        priorityReviewClips.isEmpty ? .all : .priority
    }

    @ViewBuilder
    private var priorityReviewCard: some View {
        if !priorityReviewClips.isEmpty {
            Button {
                HoopsAccessibility.animate(reduceMotion: reduceMotion) {
                    filterOption = priorityReviewFilter
                }
            } label: {
                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: "scope")
                        .font(.headline.weight(.semibold))
                        .foregroundStyle(AppTheme.warningYellow)
                        .frame(width: 34, height: 34)
                        .background(AppTheme.warningYellow.opacity(0.14), in: .circle)

                    VStack(alignment: .leading, spacing: 4) {
                        Text("Review these first")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.white)
                            .lineLimit(2)
                            .minimumScaleFactor(0.86)
                            .fixedSize(horizontal: false, vertical: true)
                        Text(viewModel.priorityReviewSummary ?? "Team calls, blocks, steals, sound cues, and unclear outcomes.")
                            .font(.caption)
                            .foregroundStyle(AppTheme.subtleText)
                            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                            .minimumScaleFactor(0.84)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .layoutPriority(1)

                    Spacer(minLength: 0)

                    Text("\(priorityReviewClips.count)")
                        .font(.caption.bold().monospacedDigit())
                        .foregroundStyle(AppTheme.warningYellow)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(AppTheme.warningYellow.opacity(0.14), in: .capsule)
                }
                .padding(12)
                .contentShape(.rect)
            }
            .buttonStyle(.plain)
            .rorkCard(
                cornerRadius: 14,
                fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.58)),
                stroke: AppTheme.warningYellow.opacity(0.24),
                glow: AppTheme.warningYellow,
                glowOpacity: 0.05
            )
            .accessibilityIdentifier("review.priorityReviewButton")
            .accessibilityLabel("Review these first")
            .accessibilityValue("\(priorityReviewClips.count) clips")
            .accessibilityHint("Filters Review to clips that need a closer look before making the AI edit.")
        }
    }

    private var reviewContextStrip: some View {
        LazyVGrid(columns: reviewContextGridColumns, spacing: 8) {
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
            RorkMetricChip(
                icon: "waveform",
                value: "\(clipCount(for: .sound))",
                label: "Sound",
                tint: .blue
            )
        }
        .padding(10)
        .rorkCard(cornerRadius: 14, fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.45)), stroke: AppTheme.softBorder, glowOpacity: 0.03)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Review context")
        .accessibilityValue("\(selectedTeamSummaryTitle), \(clipCount(for: .defense)) defensive clips, \(clipCount(for: .teamUncertain)) clips need team check, \(clipCount(for: .sound)) sound-reaction clips")
    }

    private var reviewContextGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize.isAccessibilitySize ? 150 : 104
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 240), spacing: 8, alignment: .top)
        ]
    }

    private var quickActionsBar: some View {
        LazyVGrid(columns: reviewActionGridColumns, spacing: 10) {
            reviewQuickActionButton(
                title: "Keep Strong",
                subtitle: highConfidencePendingSubtitle,
                icon: "checkmark.seal.fill",
                tint: AppTheme.successGreen,
                isDisabled: highConfidencePendingCount == 0
            ) {
                HoopsAccessibility.animate(reduceMotion: reduceMotion) {
                    viewModel.keepHighConfidenceClips()
                }
            }

            reviewQuickActionButton(
                title: "Skip Weak",
                subtitle: lowConfidenceKeptSubtitle,
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

    private var reviewActionGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize.isAccessibilitySize ? 176 : 148
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 260), spacing: 10, alignment: .top)
        ]
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

    private func focusPriorityReviewIfNeeded() {
        guard !hasAutoFocusedPriorityFilter else { return }
        guard filterOption == .all, !priorityReviewClips.isEmpty else { return }
        hasAutoFocusedPriorityFilter = true
        HoopsAccessibility.animate(reduceMotion: reduceMotion) {
            filterOption = .priority
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
                    .frame(width: 32, height: 32)
                    .background(tint.opacity(0.12), in: .circle)
                    .accessibilityHidden(true)

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                        .lineLimit(2)
                        .minimumScaleFactor(0.84)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(subtitle)
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(2)
                        .minimumScaleFactor(0.82)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .layoutPriority(1)

                Spacer(minLength: 0)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 10)
            .frame(minHeight: dynamicTypeSize.isAccessibilitySize ? 68 : 54, alignment: .leading)
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
        LazyVGrid(columns: filterGridColumns, alignment: .leading, spacing: 8) {
            ForEach(visibleFilterOptions, id: \.self) { option in
                filterChip(option)
            }

            if !hiddenFilterOptions.isEmpty || showAllFilterChips {
                moreFiltersChip
            }
        }
        .padding(10)
        .rorkCard(cornerRadius: 14, fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.45)), stroke: AppTheme.softBorder, glowOpacity: 0.03)
    }

    private func filterChip(_ option: FilterOption) -> some View {
        Button {
            HoopsAccessibility.animate(reduceMotion: reduceMotion) { filterOption = option }
        } label: {
            filterChipLabel(
                title: filterTitle(for: option),
                isSelected: filterOption == option,
                icon: nil
            )
        }
        .accessibilityLabel("\(option.rawValue) clips")
        .accessibilityValue(filterAccessibilityValue(for: option))
        .accessibilityHint("Filters the review list.")
        .hoopsSelectedState(filterOption == option)
    }

    private var moreFiltersChip: some View {
        Button {
            HoopsAccessibility.animate(reduceMotion: reduceMotion) {
                showAllFilterChips.toggle()
            }
        } label: {
            filterChipLabel(
                title: ReviewFilterDisplayPolicy.moreFiltersTitle(
                    hiddenCount: hiddenFilterOptions.count,
                    showAll: showAllFilterChips
                ),
                isSelected: showAllFilterChips,
                icon: showAllFilterChips ? "chevron.up" : "line.3.horizontal.decrease.circle"
            )
        }
        .accessibilityLabel(showAllFilterChips ? "Show fewer review filters" : "Show more review filters")
        .accessibilityValue(showAllFilterChips ? "All filters visible" : "\(hiddenFilterOptions.count) filters hidden")
        .accessibilityHint("Shows or hides extra filters like defense, blocks, steals, sound, kept, and skipped.")
    }

    private func filterChipLabel(title: String, isSelected: Bool, icon: String?) -> some View {
        Label {
            Text(title)
                .font(.subheadline.weight(.medium))
                .lineLimit(2)
                .minimumScaleFactor(0.84)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
        } icon: {
            if let icon {
                Image(systemName: icon)
                    .font(.caption.weight(.semibold))
                    .accessibilityHidden(true)
            }
        }
        .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 48 : 36)
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .foregroundStyle(isSelected ? .white : AppTheme.subtleText)
        .background(
            isSelected ? AppTheme.accentPurple : AppTheme.cardBg,
            in: .capsule
        )
    }

    private var filterGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize.isAccessibilitySize ? 150 : 94
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 180), spacing: 8, alignment: .top)
        ]
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
        case .priority:
            return "No priority clips"
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
        case .sound:
            return "No sound cues"
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
        case .priority:
            return "Priority \(priorityReviewClips.count)"
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
        case .sound:
            return "Sound \(clipCount(for: option))"
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
        case .priority:
            return priorityReviewClips.count
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
        case .sound:
            return viewModel.audioReactionReviewClips.count
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
                clipCardHeader(clip)
            }
            .buttonStyle(.plain)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(clipAccessibilityLabel(clip))
            .accessibilityValue(clipAccessibilityValue(clip))
            .accessibilityHint("Opens clip detail preview.")

            if expandedClipID == clip.id {
                VStack(spacing: 12) {
                    Divider().overlay(AppTheme.accentPurple.opacity(0.2))
                    clipEvidenceRows(clip: clip, maxRows: 4)
                    clipScoreBreakdown(clip: clip, includeDivider: false)
                }
                    .padding(.horizontal, 12)
                    .padding(.bottom, 12)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }

            clipCardActions(clip: clip)
        }
        .rorkCard(
            cornerRadius: 16,
            stroke: clip.isKept ? AppTheme.accentPurple.opacity(0.22) : AppTheme.softBorder,
            glow: clip.isKept ? AppTheme.neonPurple : AppTheme.accentPurple,
            glowOpacity: clip.isKept ? 0.09 : 0.04
        )
        .opacity(clip.isKept ? 1.0 : 0.6)
    }

    private func clipCardActions(clip: Clip) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 8) {
                clipScoreDetailsButton(clip)
                clipSlowMotionButton(clip)

                Spacer(minLength: 8)

                clipKeepSkipButton(clip)
            }

            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    clipScoreDetailsButton(clip)
                    clipSlowMotionButton(clip)
                    Spacer(minLength: 0)
                }

                clipKeepSkipButton(clip, fillsWidth: true)
            }
        }
        .padding(.horizontal, 12)
        .padding(.bottom, 8)
    }

    private var clipActionIconSize: CGFloat {
        dynamicTypeSize.isAccessibilitySize ? 48 : 40
    }

    private var clipKeepSkipMinHeight: CGFloat {
        dynamicTypeSize.isAccessibilitySize ? 48 : 40
    }

    private func clipScoreDetailsButton(_ clip: Clip) -> some View {
        Button {
            expandedClipID = expandedClipID == clip.id ? nil : clip.id
        } label: {
            Image(systemName: "chart.bar.fill")
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.subtleText)
                .frame(width: clipActionIconSize, height: clipActionIconSize)
                .background(AppTheme.cardBg.opacity(0.45), in: .circle)
                .contentShape(Circle())
        }
        .accessibilityLabel(expandedClipID == clip.id ? "Hide score details" : "Show score details")
        .accessibilityValue("Combined score \(Int(clip.combinedScore * 100)) percent")
        .accessibilityHint("Shows audio, motion, visual, and combined score breakdown.")
    }

    @ViewBuilder
    private func clipSlowMotionButton(_ clip: Clip) -> some View {
        if clip.action == .dunk {
            Button {
                HoopsAccessibility.animate(reduceMotion: reduceMotion) {
                    viewModel.toggleSlowMotion(clip)
                }
            } label: {
                Image(systemName: clip.isSlowMotionEnabled ? "tortoise.fill" : "hare.fill")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(clip.isSlowMotionEnabled ? AppTheme.neonPurple : AppTheme.subtleText)
                    .frame(width: clipActionIconSize, height: clipActionIconSize)
                    .background(
                        clip.isSlowMotionEnabled ? AppTheme.neonPurple.opacity(0.15) : AppTheme.cardBg.opacity(0.45),
                        in: .circle
                    )
                    .contentShape(Circle())
            }
            .accessibilityLabel(clip.isSlowMotionEnabled ? "Disable slow motion" : "Enable slow motion")
            .accessibilityValue(clip.isSlowMotionEnabled ? "Selected" : "Not selected")
            .accessibilityHint("Applies slow motion to this dunk clip in the exported reel.")
            .hoopsSelectedState(clip.isSlowMotionEnabled)
        }
    }

    private func clipKeepSkipButton(_ clip: Clip, fillsWidth: Bool = false) -> some View {
        let tint = clip.isKept ? AppTheme.dangerRed : AppTheme.successGreen

        return Button {
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
                    .accessibilityHidden(true)
                Text(clip.isKept ? "Skip" : "Keep")
                    .font(.caption.bold())
                    .lineLimit(1)
                    .minimumScaleFactor(0.82)
            }
            .foregroundStyle(tint)
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .frame(minWidth: fillsWidth ? 0 : 86, maxWidth: fillsWidth ? .infinity : nil, minHeight: clipKeepSkipMinHeight)
            .background(tint.opacity(0.15), in: .capsule)
            .contentShape(Capsule())
        }
        .sensoryFeedback(.impact(weight: .light), trigger: keepTrigger)
        .sensoryFeedback(.impact(weight: .light), trigger: discardTrigger)
        .accessibilityLabel(clip.isKept ? "Skip clip" : "Keep clip")
        .accessibilityValue(clip.isKept ? "Kept" : "Skipped")
        .accessibilityHint("Toggles whether this clip is included in the finished video.")
        .hoopsSelectedState(clip.isKept)
    }

    private func clipCardHeader(_ clip: Clip) -> some View {
        Group {
            if dynamicTypeSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 10) {
                    HStack(spacing: 10) {
                        clipActionIcon(clip)

                        confidenceBadge(level: clip.confidenceLevel, value: clip.confidence)
                            .fixedSize(horizontal: true, vertical: true)

                        Spacer(minLength: 0)
                    }

                    clipCardText(clip)
                }
            } else {
                HStack(alignment: .top, spacing: 12) {
                    clipActionIcon(clip)

                    VStack(alignment: .leading, spacing: 8) {
                        clipCardText(clip)

                        confidenceBadge(level: clip.confidenceLevel, value: clip.confidence)
                            .fixedSize(horizontal: true, vertical: true)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
        .padding(12)
    }

    private func clipActionIcon(_ clip: Clip) -> some View {
        ZStack {
            RoundedRectangle(cornerRadius: 10)
                .fill(actionColor(for: clip.action).opacity(0.15))
            Image(systemName: clip.action.icon)
                .font(.title3)
                .foregroundStyle(actionColor(for: clip.action))
        }
        .frame(width: 44, height: 44)
        .accessibilityHidden(true)
    }

    private func clipCardText(_ clip: Clip) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(clip.label)
                    .font(.headline)
                    .foregroundStyle(.white)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                    .minimumScaleFactor(0.84)
                    .fixedSize(horizontal: false, vertical: true)
                    .layoutPriority(1)

                if clip.detectionMethod == .ml {
                    Image(systemName: "sparkles")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.neonPurple)
                        .accessibilityLabel("AI detected")
                }
            }

            clipTimingText(clip)

            clipContextBadges(clip)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private func clipTimingText(_ clip: Clip) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 8) {
                Text("\(clip.formattedStartTime) — \(clip.formattedEndTime)")
                Text("•")
                Text(clip.formattedDuration)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text("\(clip.formattedStartTime) — \(clip.formattedEndTime)")
                Text(clip.formattedDuration)
            }
        }
        .font(.caption.monospacedDigit())
        .foregroundStyle(AppTheme.subtleText)
        .lineLimit(2)
        .fixedSize(horizontal: false, vertical: true)
    }

    private func clipDetailHeader(_ clip: Clip) -> some View {
        Group {
            if dynamicTypeSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 10) {
                    HStack(spacing: 10) {
                        clipActionIcon(clip)
                        clipDetectionBadge(clip)
                        Spacer(minLength: 0)
                    }

                    clipDetailTitle(clip)
                    clipContextBadges(clip)

                    confidenceBadge(level: clip.confidenceLevel, value: clip.confidence)
                        .fixedSize(horizontal: true, vertical: true)
                }
            } else {
                HStack(alignment: .top, spacing: 12) {
                    clipActionIcon(clip)

                    VStack(alignment: .leading, spacing: 8) {
                        HStack(alignment: .firstTextBaseline, spacing: 8) {
                            clipDetailTitle(clip)
                            clipDetectionBadge(clip)
                        }

                        clipContextBadges(clip)

                        confidenceBadge(level: clip.confidenceLevel, value: clip.confidence)
                            .fixedSize(horizontal: true, vertical: true)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }

    @ViewBuilder
    private func clipDetailTitle(_ clip: Clip) -> some View {
        Text(clip.label)
            .font(.title2.bold())
            .foregroundStyle(.white)
            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
            .minimumScaleFactor(0.82)
            .fixedSize(horizontal: false, vertical: true)
            .layoutPriority(1)
    }

    @ViewBuilder
    private func clipDetectionBadge(_ clip: Clip) -> some View {
        if clip.detectionMethod == .ml {
            Text("AI")
                .font(.caption2.bold())
                .foregroundStyle(.white)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(AppTheme.neonPurple, in: .capsule)
                .fixedSize(horizontal: true, vertical: true)
                .accessibilityLabel("AI detected")
        }
    }

    private func clipDetailTimingText(_ clip: Clip) -> some View {
        LazyVGrid(columns: clipDetailTimingGridColumns, alignment: .leading, spacing: 8) {
            Label(clip.formattedStartTime, systemImage: "play.fill")
            Label(clip.formattedEndTime, systemImage: "stop.fill")
            Label(clip.formattedDuration, systemImage: "timer")
        }
        .font(.caption)
        .foregroundStyle(AppTheme.subtleText)
        .lineLimit(2)
        .fixedSize(horizontal: false, vertical: true)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var clipDetailTimingGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize.isAccessibilitySize ? 132 : 92
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 220), spacing: 10, alignment: .leading)
        ]
    }

    private func clipScoreBreakdown(clip: Clip, includeDivider: Bool = true) -> some View {
        VStack(spacing: 8) {
            if includeDivider {
                Divider().overlay(AppTheme.accentPurple.opacity(0.2))
            }
            scoreBar(label: "Audio", value: clip.audioScore, color: .blue)
            scoreBar(label: "Motion", value: clip.motionScore, color: .orange)
            scoreBar(label: "Visual", value: clip.visualScore, color: .green)
            scoreBar(label: "Combined", value: clip.combinedScore, color: AppTheme.neonPurple)
        }
    }

    private func clipEvidenceRows(clip: Clip, maxRows: Int? = nil) -> some View {
        let rows = maxRows.map { Array(clip.reviewEvidenceRows.prefix($0)) } ?? clip.reviewEvidenceRows

        return VStack(alignment: .leading, spacing: 10) {
            ForEach(rows) { row in
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: row.systemImage)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(row.needsReview ? AppTheme.warningYellow : AppTheme.neonPurple)
                        .frame(width: 20)

                    VStack(alignment: .leading, spacing: 2) {
                        ViewThatFits(in: .horizontal) {
                            HStack(spacing: 6) {
                                evidenceRowTitle(row)
                                evidenceRowCheckBadge(row)
                            }

                            VStack(alignment: .leading, spacing: 3) {
                                evidenceRowTitle(row)
                                evidenceRowCheckBadge(row)
                            }
                        }

                        Text(row.detail)
                            .font(.caption2)
                            .foregroundStyle(AppTheme.subtleText)
                            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 6 : 4)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    Spacer(minLength: 0)
                }
                .accessibilityElement(children: .combine)
                .accessibilityLabel(row.title)
                .accessibilityValue(row.detail)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func evidenceRowTitle(_ row: ClipReviewEvidenceRow) -> some View {
        Text(row.title)
            .font(.caption.weight(.semibold))
            .foregroundStyle(.white)
            .lineLimit(2)
            .minimumScaleFactor(0.86)
            .fixedSize(horizontal: false, vertical: true)
    }

    @ViewBuilder
    private func evidenceRowCheckBadge(_ row: ClipReviewEvidenceRow) -> some View {
        if row.needsReview {
            Text("Check")
                .font(.caption2.weight(.bold))
                .foregroundStyle(AppTheme.warningYellow)
                .lineLimit(1)
                .minimumScaleFactor(0.86)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(AppTheme.warningYellow.opacity(0.14), in: .capsule)
        }
    }

    private func scoreBar(label: String, value: Double, color: Color) -> some View {
        let clampedValue = max(0.0, min(value, 1.0))
        let percentText = "\(Int(clampedValue * 100))%"

        return ViewThatFits(in: .horizontal) {
            HStack(spacing: 8) {
                scoreBarLabel(label)
                    .frame(width: dynamicTypeSize.isAccessibilitySize ? 76 : 60, alignment: .leading)

                scoreBarTrack(value: clampedValue, color: color)

                scoreBarValue(percentText)
                    .frame(width: dynamicTypeSize.isAccessibilitySize ? 48 : 35, alignment: .trailing)
            }

            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    scoreBarLabel(label)
                    Spacer(minLength: 8)
                    scoreBarValue(percentText)
                }

                scoreBarTrack(value: clampedValue, color: color)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(label)
        .accessibilityValue("\(Int(clampedValue * 100)) percent")
    }

    private func scoreBarLabel(_ label: String) -> some View {
        Text(label)
            .font(.caption2)
            .foregroundStyle(AppTheme.subtleText)
            .lineLimit(1)
            .minimumScaleFactor(0.78)
    }

    private func scoreBarValue(_ value: String) -> some View {
        Text(value)
            .font(.caption2.monospacedDigit())
            .foregroundStyle(AppTheme.subtleText)
            .lineLimit(1)
            .minimumScaleFactor(0.78)
    }

    private func scoreBarTrack(value: Double, color: Color) -> some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(Color.white.opacity(0.05))
                Capsule()
                    .fill(color)
                    .frame(width: geo.size.width * CGFloat(value))
            }
        }
        .frame(height: dynamicTypeSize.isAccessibilitySize ? 8 : 6)
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
        let reviewBadges = contextualReviewBadges(for: clip)
        if !reviewBadges.isEmpty {
            HStack(spacing: 6) {
                ForEach(reviewBadges, id: \.self) { badge in
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
        if teamTitle != nil || !contextualReviewBadges(for: clip).isEmpty || isDefensiveClip(clip) {
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 6) {
                    clipContextBadgeItems(clip)
                }

                LazyVGrid(columns: clipContextBadgeGridColumns, alignment: .leading, spacing: 6) {
                    clipContextBadgeItems(clip)
                }
            }
        }
    }

    private var clipContextBadgeGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize.isAccessibilitySize ? 128 : 86
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 220), spacing: 6, alignment: .leading)
        ]
    }

    @ViewBuilder
    private func clipContextBadgeItems(_ clip: Clip) -> some View {
        let reviewBadges = contextualReviewBadges(for: clip)
        if let teamTitle = clipTeamDisplayTitle(clip) {
            Label(teamTitle, systemImage: clipNeedsTeamReview(clip) ? "person.2.badge.gearshape.fill" : "person.2.fill")
                .font(.caption2.weight(.semibold))
                .foregroundStyle(clipNeedsTeamReview(clip) ? AppTheme.warningYellow : AppTheme.neonPurple)
                .lineLimit(2)
                .minimumScaleFactor(0.82)
                .fixedSize(horizontal: false, vertical: true)
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
                .lineLimit(2)
                .minimumScaleFactor(0.82)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.horizontal, 7)
                .padding(.vertical, 3)
                .background(Color.orange.opacity(0.14), in: .capsule)
                .accessibilityLabel("defensive highlight")
                .accessibilityValue(defensiveBadgeTitle(for: clip))
        }

        ForEach(reviewBadges, id: \.self) { badge in
            Label(badge.title, systemImage: badge.systemImage)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(AppTheme.warningYellow)
                .lineLimit(2)
                .minimumScaleFactor(0.82)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.horizontal, 7)
                .padding(.vertical, 3)
                .background(AppTheme.warningYellow.opacity(0.14), in: .capsule)
                .accessibilityLabel(badge.accessibilityLabel)
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
        HighlightsViewModel.needsTeamReview(
            clip,
            teamSelection: viewModel.settings.highlightTeamSelection
        )
    }

    private func contextualReviewBadges(for clip: Clip) -> [ClipReviewBadge] {
        HighlightsViewModel.reviewBadges(
            for: clip,
            teamSelection: viewModel.settings.highlightTeamSelection
        )
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
        HighlightsViewModel.isDefensiveReviewClip(clip)
    }

    private func isBlockClip(_ clip: Clip) -> Bool {
        HighlightsViewModel.isBlockReviewClip(clip)
    }

    private func isStealClip(_ clip: Clip) -> Bool {
        HighlightsViewModel.isStealReviewClip(clip)
    }

    private func isForcedTurnoverClip(_ clip: Clip) -> Bool {
        HighlightsViewModel.isForcedTurnoverReviewClip(clip)
    }

    private func isDefensiveStopClip(_ clip: Clip) -> Bool {
        HighlightsViewModel.isDefensiveStopReviewClip(clip)
    }

    private func defensiveBadgeTitle(for clip: Clip) -> String {
        if isBlockClip(clip) { return "Block" }
        if isStealClip(clip) { return "Steal" }
        if isForcedTurnoverClip(clip) { return "Forced TO" }
        if isDefensiveStopClip(clip) { return "Stop" }
        return "Defense"
    }

    private func defensiveBadgeIcon(for clip: Clip) -> String {
        if isBlockClip(clip) { return "shield.fill" }
        if isStealClip(clip) { return "hand.raised.fill" }
        if isForcedTurnoverClip(clip) { return "arrow.triangle.2.circlepath.circle.fill" }
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
        player.isMuted = previewAudioMuted
        player.volume = previewAudioMuted ? 0 : 1
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

    private func applyClipPreviewAudioMute() {
        clipPlayer?.isMuted = previewAudioMuted
        clipPlayer?.volume = previewAudioMuted ? 0 : 1
    }

    private func clipDetailSheet(clip: Clip) -> some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.16)

                ScrollView {
                    VStack(spacing: 20) {
                        if let clipPlayer {
                            ZStack(alignment: .topTrailing) {
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

                                Button {
                                    previewAudioMuted.toggle()
                                    applyClipPreviewAudioMute()
                                } label: {
                                    Image(systemName: previewAudioMuted ? "speaker.slash.fill" : "speaker.wave.2.fill")
                                        .font(.caption.weight(.bold))
                                        .foregroundStyle(.white)
                                        .padding(9)
                                        .background(.black.opacity(0.58), in: Circle())
                                }
                                .buttonStyle(.plain)
                                .padding(10)
                                .accessibilityIdentifier("review.clipPreview.muteToggle")
                                .accessibilityLabel(previewAudioMuted ? "Unmute clip preview" : "Mute clip preview")
                            }
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
                            clipDetailHeader(clip)
                            clipDetailTimingText(clip)
                        }
                        .padding(16)
                        .background(AppTheme.cardBg, in: .rect(cornerRadius: 16))

                        clipScoreBreakdown(clip: clip)
                            .padding(16)
                            .background(AppTheme.cardBg, in: .rect(cornerRadius: 16))

                        VStack(alignment: .leading, spacing: 12) {
                            RorkSectionHeader(
                                title: "Review Evidence",
                                icon: "checkmark.seal.fill",
                                subtitle: "Why this clip is here and what to check"
                            )
                            clipEvidenceRows(clip: clip)
                        }
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
        let reviewNotes = contextualReviewBadges(for: clip).map(\.accessibilityLabel)
        let reviewText = reviewNotes.isEmpty ? "" : " Review flags: \(reviewNotes.joined(separator: ", "))."
        return "\(keepState). Confidence \(Int(clip.confidence * 100)) percent. Duration \(clip.formattedDuration).\(reviewText)"
    }
}
