import SwiftUI
import AVKit

struct ReviewView: View {
    @Bindable var viewModel: HighlightsViewModel
    @State private var selectedClip: Clip?
    @State private var clipPlayer: AVPlayer?
    @State private var clipLoopObserverToken: NSObjectProtocol?
    @State private var clipPlaybackRange: ClosedRange<Double>?
    @State private var filterOption: FilterOption = .all
    @State private var sortByScore = true
    @State private var expandedClipID: UUID?
    @State private var keepTrigger = 0
    @State private var discardTrigger = 0

    private enum FilterOption: String, CaseIterable {
        case all = "All"
        case kept = "Kept"
        case discarded = "Discarded"
    }

    private var filteredClips: [Clip] {
        let base: [Clip]
        switch filterOption {
        case .all: base = viewModel.clips
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
                AppTheme.darkBg.ignoresSafeArea()

                if viewModel.clips.isEmpty {
                    emptyState
                } else {
                    ScrollView {
                        VStack(spacing: 16) {
                            headerStats
                            reviewProgressStrip
                            quickActionsBar
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
                            Button("Discard All", systemImage: "xmark.circle") {
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
                    }
                }
            }
            .sheet(item: $selectedClip, onDismiss: teardownClipPlayer) { clip in
                clipDetailSheet(clip: clip)
            }
        }
    }

    private var emptyState: some View {
        ContentUnavailableView {
            Label("No Clips Yet", systemImage: "film.stack")
        } description: {
            Text("Import a video and run AI analysis to detect highlights")
        }
        .foregroundStyle(.white)
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
                label: "Discarded",
                icon: "xmark.circle.fill",
                color: AppTheme.dangerRed
            )
            reviewStatCard(
                value: Clip.formatTime(viewModel.keptClips.reduce(0) { $0 + $1.duration }),
                label: "Total Time",
                icon: "clock.fill",
                color: AppTheme.warningYellow
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
        viewModel.clips.filter { $0.confidence >= 0.8 && !$0.isKept }.count
    }

    private var lowConfidenceKeptCount: Int {
        viewModel.clips.filter { $0.confidence < 0.5 && $0.isKept }.count
    }

    private var quickActionsBar: some View {
        HStack(spacing: 10) {
            reviewQuickActionButton(
                title: "Keep High",
                subtitle: "\(highConfidencePendingCount) clips",
                icon: "checkmark.seal.fill",
                tint: AppTheme.successGreen,
                isDisabled: highConfidencePendingCount == 0
            ) {
                withAnimation(.snappy) {
                    viewModel.keepHighConfidenceClips()
                }
            }

            reviewQuickActionButton(
                title: "Discard Low",
                subtitle: "\(lowConfidenceKeptCount) clips",
                icon: "xmark.seal.fill",
                tint: AppTheme.dangerRed,
                isDisabled: lowConfidenceKeptCount == 0
            ) {
                withAnimation(.snappy) {
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
    }

    private var filterBar: some View {
        HStack(spacing: 8) {
            ForEach(FilterOption.allCases, id: \.self) { option in
                Button {
                    withAnimation(.snappy) { filterOption = option }
                } label: {
                    Text(option.rawValue)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(filterOption == option ? .white : AppTheme.subtleText)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(
                            filterOption == option ? AppTheme.accentPurple : AppTheme.cardBg,
                            in: .capsule
                        )
                }
            }
            Spacer()
        }
        .padding(10)
        .rorkCard(cornerRadius: 14, fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.45)), stroke: AppTheme.softBorder, glowOpacity: 0.03)
    }

    private var clipsList: some View {
        LazyVStack(spacing: 12) {
            ForEach(filteredClips) { clip in
                clipCard(clip: clip)
                    .transition(.asymmetric(
                        insertion: .scale.combined(with: .opacity),
                        removal: .opacity
                    ))
            }
        }
        .animation(.snappy, value: filterOption)
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
                    }

                    Spacer()

                    confidenceBadge(level: clip.confidenceLevel, value: clip.confidence)
                }
                .padding(12)
            }
            .buttonStyle(.plain)

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

                if clip.action == .dunk {
                    Button {
                        withAnimation(.snappy) {
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
                }

                Spacer()

                Button {
                    withAnimation(.snappy) {
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
                        Text(clip.isKept ? "Discard" : "Keep")
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
                AppTheme.darkBg.ignoresSafeArea()

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
}
