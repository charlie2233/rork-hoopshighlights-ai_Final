import SwiftUI
import AVFoundation
import AVKit
import UniformTypeIdentifiers

struct ExportView: View {
    @Environment(SubscriptionManager.self) private var subscriptionManager
    @Environment(AuthService.self) private var authService
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @Bindable var viewModel: HighlightsViewModel
    @State private var exportTrigger = 0
    @State private var saveTrigger = 0
    @State private var shareTrigger = 0
    @State private var showingPaywall = false
    @State private var showSystemShareSheet = false
    @State private var showExportPreviewSheet = false
    @State private var musicPreviewManager = MusicPreviewManager()
    @State private var exportPreviewPlayer: AVPlayer?
    @State private var expandedExportPreviewPlayer: AVPlayer?
    @AppStorage("hoops.previewAudioMuted.v1") private var previewAudioMuted = false
    @State private var exportPreviewHasAudioTrack: Bool?
    @State private var exportPreviewAudioCheckTask: Task<Void, Never>?
    @State private var shareURL: URL?
    @State private var lastAutoPresentedExportURL: URL?
    @State private var shareErrorMessage: String?
    @State private var showFileImporter = false
    @State private var lastExportAnnouncementPercent = -1
    @State private var showAdvancedLocalExportControls = false

    var body: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.20)

                if !canShowExportWorkspace {
                    emptyState
                } else {
                    ScrollView {
                        VStack(spacing: 24) {
                            summaryCard
                            aiEditAgentSection
                            if AppConstants.requiresCloudVideoPipeline {
                                quickActionsSection
                            } else {
                                localExportSetupCard
                                if showAdvancedLocalExportControls {
                                    themeSection
                                    musicSection
                                    qualitySection
                                    formatSection
                                    postProcessingSection
                                }
                                quickActionsSection
                                exportButton
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                        .padding(.bottom, 100)
                    }
                }
            }
            .navigationTitle("Export")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .sheet(isPresented: $showingPaywall) {
                PaywallView(subscriptionManager: subscriptionManager, authService: authService)
            }
            .sheet(isPresented: $showSystemShareSheet, onDismiss: clearShareSelection) {
                if let shareURL {
                    SystemShareSheet(
                        items: SystemShareSheet.videoItems(
                            for: shareURL,
                            title: shareSheetTitle
                        ),
                        subject: shareSheetTitle,
                        completion: { _, _, _, error in
                            guard let error else { return }
                            Task { @MainActor in
                                shareErrorMessage = "Could not open the share sheet: \(error.localizedDescription)"
                            }
                        }
                    )
                } else {
                    EmptyView()
                }
            }
            .sheet(isPresented: $showExportPreviewSheet) {
                if let exportedURL = viewModel.exportService.exportedURL {
                    exportPreviewSheet(url: exportedURL)
                } else {
                    EmptyView()
                }
            }
            .alert("Saved!", isPresented: $viewModel.showingSaveSuccess) {
                Button("OK", role: .cancel) { }
            } message: {
                Text("Highlight reel saved to your photo library.")
            }
            .alert("Share Failed", isPresented: Binding(
                get: { shareErrorMessage != nil },
                set: { if !$0 { shareErrorMessage = nil } }
            )) {
                Button("OK", role: .cancel) { shareErrorMessage = nil }
            } message: {
                Text(shareErrorMessage ?? "Try saving to Photos, then share from your camera roll.")
            }
            .onAppear {
                configureExportPreviewPlayer(for: viewModel.exportService.exportedURL)
            }
            .onChange(of: viewModel.exportService.exportedURL) { _, newValue in
                configureExportPreviewPlayer(for: newValue)
                if showExportPreviewSheet {
                    configureExpandedExportPreviewPlayer(for: newValue)
                }
                guard let newValue,
                      !viewModel.exportService.isExporting,
                      isExportFileAvailable(newValue),
                      newValue != lastAutoPresentedExportURL else {
                    return
                }
                configureExpandedExportPreviewPlayer(for: newValue)
                showExportPreviewSheet = true
                lastAutoPresentedExportURL = newValue
                HoopsAccessibility.announce("Export complete. Preview is ready.")
            }
            .onChange(of: viewModel.exportService.statusMessage) { _, message in
                guard viewModel.exportService.isExporting else { return }
                HoopsAccessibility.announce(message)
            }
            .onChange(of: viewModel.exportService.exportProgress) { _, progress in
                announceExportProgress(progress)
            }
            .onChange(of: viewModel.showingSaveSuccess) { _, isShowing in
                if isShowing {
                    HoopsAccessibility.announce("Highlight reel saved to Photos.")
                }
            }
            .onChange(of: shareErrorMessage) { _, message in
                guard let message else { return }
                HoopsAccessibility.announce(message)
            }
            .onDisappear {
                pausePreviewPlayers()
            }
        }
    }

    private var emptyState: some View {
        HoopsEmptyStateCard(
            title: "Analyze first",
            message: "Run AI Analysis first. Review is optional; AI Edit can still build your reel.",
            icon: "square.and.arrow.up.fill"
        )
    }

    private var summaryCard: some View {
        VStack(spacing: 12) {
            RorkSectionHeader(
                title: "Tell HoopClips what reel you want",
                icon: "sparkles.tv.fill",
                subtitle: viewModel.keptClips.isEmpty
                    ? "Pick a vibe below, then make the reel."
                    : "Kept clips stay in. Pick a vibe, then make the reel."
            )

            LazyVGrid(columns: summaryMetricGridColumns, alignment: .leading, spacing: 10) {
                summaryMetric(
                    value: summaryPrimaryValue,
                    label: summaryPrimaryLabel
                )
                summaryMetric(
                    value: summarySecondaryValue,
                    label: summarySecondaryLabel
                )
            }

            if !AppConstants.requiresCloudVideoPipeline && hasLockedSelections {
                HStack(spacing: 8) {
                    Image(systemName: "lock.fill")
                        .font(.caption.weight(.semibold))
                    Text("Selected export options include Pro-only features.")
                        .font(.caption.weight(.medium))
                    Spacer()
                    Button("Unlock Pro") {
                        showingPaywall = true
                    }
                    .font(.caption.bold())
                    .foregroundStyle(AppTheme.neonPurple)
                }
                .foregroundStyle(AppTheme.warningYellow)
                .padding(10)
                .background(AppTheme.warningYellow.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(AppTheme.warningYellow.opacity(0.18), lineWidth: 1)
                )
            }

            LazyVGrid(columns: summaryClipGridColumns, alignment: .leading, spacing: 8) {
                if viewModel.keptClips.isEmpty {
                    summaryClipChip(icon: "text.bubble.fill", text: "Describe it below")
                    summaryClipChip(icon: "wand.and.stars", text: "AI picks clips")
                } else {
                    summaryClipChip(icon: "text.bubble.fill", text: "Describe it below")
                    ForEach(Array(viewModel.keptClips.prefix(summaryClipPreviewLimit))) { clip in
                        summaryClipChip(icon: clip.action.icon, text: clip.label)
                    }

                    if summaryClipOverflowCount > 0 {
                        summaryClipChip(icon: "plus.circle.fill", text: "+\(summaryClipOverflowCount) more")
                    }
                }
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.accentPurple.opacity(0.2))
    }

    private var aiEditAgentSection: some View {
        AIEditView(
            viewModel: viewModel,
            isProUser: subscriptionManager.isProUser,
            revenueCatAppUserID: subscriptionManager.revenueCatAppUserID,
            presentation: .exportSection,
            onRequestProUpgrade: { showingPaywall = true }
        )
    }

    private var localExportSetupCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(AppTheme.accentPurple.opacity(0.20))
                        .frame(width: 42, height: 42)
                    Image(systemName: "slider.horizontal.below.rectangle")
                        .font(.headline)
                        .foregroundStyle(AppTheme.neonPurple)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text("Export setup")
                        .font(.headline)
                        .foregroundStyle(.white)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)

                    Text(localExportSetupSummary)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(hasLockedSelections ? AppTheme.warningYellow : AppTheme.subtleText)
                        .lineLimit(3)
                        .minimumScaleFactor(0.86)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("export.localSetup.summary")
                }

                Spacer(minLength: 0)
            }

            Button {
                HoopsAccessibility.animate(reduceMotion: reduceMotion, .snappy(duration: 0.18)) {
                    showAdvancedLocalExportControls.toggle()
                }
            } label: {
                Label(
                    showAdvancedLocalExportControls ? "Hide advanced export options" : "Advanced export options",
                    systemImage: showAdvancedLocalExportControls ? "chevron.up.circle.fill" : "slider.horizontal.3"
                )
                .font(.caption.bold())
                .multilineTextAlignment(.center)
                .lineLimit(3)
                .minimumScaleFactor(0.84)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, minHeight: 42)
                .padding(.horizontal, 8)
            }
            .buttonStyle(.bordered)
            .tint(AppTheme.neonPurple)
            .accessibilityIdentifier("export.localSetup.advancedButton")
            .accessibilityValue(showAdvancedLocalExportControls ? "Advanced export options shown" : "Advanced export options hidden")
            .accessibilityHint("Shows or hides style, music, quality, format, and effects options.")
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.neonPurple.opacity(0.16), glow: AppTheme.neonPurple, glowOpacity: 0.04)
        .accessibilityIdentifier("export.localSetup.card")
    }

    private var themeSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            RorkSectionHeader(
                title: "Theme",
                icon: "paintbrush.fill",
                subtitle: "Visual overlays and color treatment for the reel"
            )

            LazyVGrid(columns: themeOptionGridColumns, spacing: 10) {
                ForEach(ExportTheme.allCases) { theme in
                    let isLocked = isThemeLocked(theme)
                    Button {
                        guard !isLocked else {
                            showingPaywall = true
                            return
                        }
                        HoopsAccessibility.animate(reduceMotion: reduceMotion) { viewModel.selectedTheme = theme }
                    } label: {
                        VStack(spacing: 8) {
                            HStack(spacing: 4) {
                                if isLocked {
                                    Image(systemName: "lock.fill")
                                        .font(.caption2.weight(.bold))
                                }
                                Image(systemName: theme.icon)
                                    .font(.title2)
                            }
                            .foregroundStyle(viewModel.selectedTheme == theme ? .white : (isLocked ? AppTheme.warningYellow : AppTheme.subtleText))

                            Text(theme.rawValue)
                                .font(.caption.weight(.medium))
                                .foregroundStyle(viewModel.selectedTheme == theme ? .white : (isLocked ? AppTheme.warningYellow : AppTheme.subtleText))
                                .multilineTextAlignment(.center)
                                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                                .minimumScaleFactor(0.84)
                                .fixedSize(horizontal: false, vertical: true)

                            if isLocked {
                                Text("PRO")
                                    .font(.caption2.bold())
                                    .foregroundStyle(AppTheme.warningYellow)
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 3)
                                    .background(AppTheme.warningYellow.opacity(0.10), in: Capsule())
                                    .fixedSize(horizontal: true, vertical: true)
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .frame(minHeight: dynamicTypeSize.isAccessibilitySize ? 116 : 94)
                        .padding(.vertical, 14)
                        .background(
                            viewModel.selectedTheme == theme ? AppTheme.accentPurple : AppTheme.cardBg,
                            in: .rect(cornerRadius: 12)
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(
                                    viewModel.selectedTheme == theme ? AppTheme.neonPurple : Color.clear,
                                    lineWidth: 2
                                )
                        )
                        .overlay(alignment: .topTrailing) {
                            if isLocked {
                                Image(systemName: "crown.fill")
                                    .font(.caption2.bold())
                                    .foregroundStyle(AppTheme.warningYellow)
                                    .padding(6)
                            }
                        }
                        .opacity(isLocked && viewModel.selectedTheme != theme ? 0.88 : 1)
                    }
                    .accessibilityLabel(theme.rawValue)
                    .accessibilityValue(optionAccessibilityValue(isSelected: viewModel.selectedTheme == theme, isLocked: isLocked))
                    .accessibilityHint(isLocked ? "Requires Pro. Opens the paywall." : "Sets the export theme.")
                    .hoopsSelectedState(viewModel.selectedTheme == theme)
                }
            }

            Text(viewModel.selectedTheme.description)
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
                .padding(.leading, 4)
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 3)
                .fixedSize(horizontal: false, vertical: true)

            if !subscriptionManager.isProUser {
                Text("Pro unlocks Neon, Cinematic, and Hype export themes.")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.warningYellow)
                    .padding(.leading, 4)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 3)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.05)
    }

    private var musicSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            RorkSectionHeader(
                title: "Music",
                icon: "music.note",
                subtitle: "Choose from built-in loops or bring your own audio"
            )

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(MusicTrack.allCases) { track in
                        let isLocked = isMusicLocked(track)
                        let isSelected = viewModel.selectedMusic == track
                        
                        ZStack(alignment: .topTrailing) {
                            Button {
                                guard !isLocked else {
                                    showingPaywall = true
                                    return
                                }
                                if track == .custom {
                                    showFileImporter = true
                                } else {
                                    HoopsAccessibility.animate(reduceMotion: reduceMotion) { viewModel.selectedMusic = track }
                                }
                            } label: {
                                HStack(spacing: 8) {
                                    if isLocked {
                                        Image(systemName: "lock.fill")
                                            .font(.caption.weight(.bold))
                                    }
                                    Image(systemName: track.icon)
                                        .font(.subheadline)
                                    Text(track.rawValue)
                                        .font(.subheadline.weight(.medium))
                                    if isLocked {
                                        Text("PRO")
                                            .font(.caption2.bold())
                                            .padding(.horizontal, 6)
                                            .padding(.vertical, 3)
                                            .background(AppTheme.warningYellow.opacity(0.12), in: Capsule())
                                    }
                                }
                                .foregroundStyle(
                                    isSelected
                                    ? .white
                                    : (isLocked ? AppTheme.warningYellow : AppTheme.subtleText)
                                )
                                .padding(.horizontal, 14)
                                .padding(.vertical, 10)
                                .background(
                                    isSelected ? AppTheme.accentPurple : AppTheme.cardBg,
                                    in: .capsule
                                )
                                .overlay(
                                    Capsule()
                                        .stroke(
                                            isSelected ? AppTheme.neonPurple : Color.clear,
                                            lineWidth: 2
                                        )
                                )
                                .opacity(isLocked && !isSelected ? 0.9 : 1)
                            }
                            .accessibilityLabel(track.rawValue)
                            .accessibilityValue(optionAccessibilityValue(isSelected: isSelected, isLocked: isLocked))
                            .accessibilityHint(musicAccessibilityHint(for: track, isLocked: isLocked))
                            .hoopsSelectedState(isSelected)
                            
                            if track != .none && track != .custom && !isLocked {
                                Button {
                                    musicPreviewManager.togglePreview(for: track)
                                } label: {
                                    Image(systemName: musicPreviewManager.currentTrack == track && musicPreviewManager.isPlaying ? "stop.circle.fill" : "play.circle.fill")
                                        .font(.title3)
                                        .symbolRenderingMode(.hierarchical)
                                        .foregroundStyle(isSelected ? .white : AppTheme.accentPurple)
                                        .background(Circle().fill(AppTheme.cardBg))
                                }
                                .accessibilityLabel(musicPreviewManager.currentTrack == track && musicPreviewManager.isPlaying ? "Stop \(track.rawValue) preview" : "Preview \(track.rawValue)")
                                .accessibilityHint("Plays a short sample of this music track.")
                                .offset(x: 8, y: -8)
                            }
                        }
                    }
                }
                .padding(.top, 8)
                .padding(.trailing, 8)
            }
            .contentMargins(.horizontal, 0)
            .fileImporter(
                isPresented: $showFileImporter,
                allowedContentTypes: [.audio],
                allowsMultipleSelection: false
            ) { result in
                switch result {
                case .success(let urls):
                    if let url = urls.first {
                        viewModel.selectCustomAudio(url: url)
                    }
                case .failure(let error):
                    shareErrorMessage = "Could not select custom audio: \(error.localizedDescription)"
                }
            }

            if !subscriptionManager.isProUser {
                Text("Pro unlocks premium music packs.")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.warningYellow)
                    .padding(.leading, 4)
            }

            Text(viewModel.selectedMusic.description)
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .padding(.leading, 4)
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.05)
    }

    private var qualitySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            RorkSectionHeader(
                title: "Quality",
                icon: "slider.horizontal.3",
                subtitle: "Higher quality improves clarity but takes longer"
            )

            LazyVGrid(columns: exportOptionGridColumns, alignment: .leading, spacing: 10) {
                ForEach(ExportQuality.allCases) { quality in
                    Button {
                        HoopsAccessibility.animate(reduceMotion: reduceMotion) { viewModel.selectedQuality = quality }
                    } label: {
                        VStack(spacing: 4) {
                            Text(quality.rawValue)
                                .font(.headline)
                                .lineLimit(1)
                                .minimumScaleFactor(0.82)
                            Text(quality.description)
                                .font(.caption2)
                                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 3)
                                .multilineTextAlignment(.center)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .foregroundStyle(viewModel.selectedQuality == quality ? .white : AppTheme.subtleText)
                        .frame(maxWidth: .infinity)
                        .frame(minHeight: dynamicTypeSize.isAccessibilitySize ? 92 : 72)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 12)
                        .background(
                            viewModel.selectedQuality == quality ? AppTheme.accentPurple : AppTheme.cardBg,
                            in: .rect(cornerRadius: 12)
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(
                                    viewModel.selectedQuality == quality ? AppTheme.neonPurple : Color.clear,
                                    lineWidth: 2
                                )
                        )
                    }
                    .accessibilityLabel(quality.rawValue)
                    .accessibilityValue(viewModel.selectedQuality == quality ? "Selected" : "Not selected")
                    .accessibilityHint("Sets export render quality.")
                    .hoopsSelectedState(viewModel.selectedQuality == quality)
                }
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.05)
    }

    private var formatSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            RorkSectionHeader(
                title: "Format",
                icon: "doc.badge.gearshape",
                subtitle: "Choose output container for compatibility or Apple workflows"
            )

            LazyVGrid(columns: exportOptionGridColumns, alignment: .leading, spacing: 10) {
                ForEach(ExportFileFormat.allCases) { format in
                    Button {
                        HoopsAccessibility.animate(reduceMotion: reduceMotion) { viewModel.selectedFormat = format }
                    } label: {
                        VStack(alignment: .leading, spacing: 6) {
                            HStack(spacing: 8) {
                                Image(systemName: format.icon)
                                    .font(.subheadline.weight(.semibold))
                                Text(format.rawValue)
                                    .font(.headline)
                                    .lineLimit(1)
                                    .minimumScaleFactor(0.82)
                            }
                            Text(format.description)
                                .font(.caption2)
                                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 3)
                                .multilineTextAlignment(.leading)
                                .fixedSize(horizontal: false, vertical: true)
                                .foregroundStyle(
                                    viewModel.selectedFormat == format
                                    ? Color.white.opacity(0.8)
                                    : AppTheme.subtleText
                                )
                        }
                        .foregroundStyle(viewModel.selectedFormat == format ? .white : AppTheme.subtleText)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .frame(minHeight: dynamicTypeSize.isAccessibilitySize ? 104 : 82, alignment: .leading)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 12)
                        .background(
                            viewModel.selectedFormat == format ? AppTheme.accentPurple : AppTheme.cardBg,
                            in: .rect(cornerRadius: 12)
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(
                                    viewModel.selectedFormat == format ? AppTheme.neonPurple : Color.clear,
                                    lineWidth: 2
                                )
                        )
                    }
                    .accessibilityLabel(format.rawValue)
                    .accessibilityValue(viewModel.selectedFormat == format ? "Selected" : "Not selected")
                    .accessibilityHint(format.description)
                    .hoopsSelectedState(viewModel.selectedFormat == format)
                }
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.05)
    }

    private var postProcessingSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            RorkSectionHeader(
                title: "Post-Processing",
                icon: "sparkles",
                subtitle: "Automatic polish around each clip's key moment"
            )

            Toggle(
                isOn: Binding(
                    get: { viewModel.exportPostProcessing.enableAutoZoom },
                    set: { viewModel.exportPostProcessing.enableAutoZoom = $0 }
                )
            ) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Auto Zoom-In")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Text("Adds a subtle punch-in around the action peak")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                }
            }
            .tint(AppTheme.accentPurple)

            Divider().overlay(AppTheme.accentPurple.opacity(0.2))

            Toggle(
                isOn: Binding(
                    get: { viewModel.exportPostProcessing.enableSmartSlowMotion },
                    set: { viewModel.exportPostProcessing.enableSmartSlowMotion = $0 }
                )
            ) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Smart Slow-Mo")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Text("Automatically slows big moments; manual slow-mo from Review still applies")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                }
            }
            .tint(AppTheme.accentPurple)

            Text("Effects are applied around the middle of each kept clip to emphasize the key moment.")
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .padding(.leading, 4)
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.05)
    }

    @ViewBuilder
    private var quickActionsSection: some View {
        if let exportedURL = viewModel.exportService.exportedURL, !viewModel.exportService.isExporting {
            let exportAvailable = isExportFileAvailable(exportedURL)

            VStack(alignment: .leading, spacing: 12) {
                RorkSectionHeader(
                    title: "Review & Share",
                    icon: "paperplane.fill",
                    subtitle: "Preview the saved reel before saving or sharing"
                )

                if exportAvailable {
                    VStack(alignment: .leading, spacing: 8) {
                        Group {
                            if let exportPreviewPlayer {
                                ZStack(alignment: .topTrailing) {
                                    VideoPlayer(player: exportPreviewPlayer)
                                        .accessibilityLabel("Export preview")
                                        .accessibilityValue(exportedURL.lastPathComponent)
                                        .accessibilityHint("Use playback controls to review the exported highlight reel.")

                                    exportPreviewMuteButton(accessibilityIdentifier: "export.preview.muteToggle")
                                }
                            } else {
                                ProgressView()
                                    .tint(AppTheme.neonPurple)
                                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                                    .background(AppTheme.surfaceBg)
                                    .accessibilityLabel("Loading export preview")
                            }
                        }
                        .frame(height: 220)
                        .clipShape(.rect(cornerRadius: 16))
                        .overlay(
                            RoundedRectangle(cornerRadius: 16)
                                .stroke(AppTheme.accentPurple.opacity(0.28), lineWidth: 1)
                        )
                        .overlay(alignment: .topLeading) {
                            Text("Latest AI edit")
                                .font(.caption2.monospaced())
                                .foregroundStyle(.white)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 6)
                                .background(Color.black.opacity(0.45), in: .capsule)
                                .padding(10)
                                .allowsHitTesting(false)
                        }
                        .overlay(alignment: .bottomTrailing) {
                            Button {
                                showExportPreviewSheet = true
                            } label: {
                                HStack(spacing: 6) {
                                    Image(systemName: "arrow.up.left.and.arrow.down.right")
                                        .font(.caption.weight(.bold))
                                    Text("Expand Preview")
                                        .font(.caption.bold())
                                }
                                .foregroundStyle(.white)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 8)
                                .background(AppTheme.surfaceBg.opacity(0.92), in: .capsule)
                                .overlay(
                                    Capsule()
                                        .stroke(AppTheme.softBorder, lineWidth: 1)
                                )
                            }
                            .buttonStyle(.plain)
                            .padding(10)
                            .accessibilityLabel("Expand export preview")
                            .accessibilityHint("Opens a larger preview of the saved reel.")
                        }

                        Text("Your saved reel opens in review first. You can reopen it here anytime.")
                            .font(.caption2)
                            .foregroundStyle(AppTheme.subtleText)
                    }
                } else {
                    VStack(alignment: .leading, spacing: 6) {
                        Label("Reel not ready", systemImage: "exclamationmark.triangle.fill")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(AppTheme.warningYellow)
                        Text(ExportReelCopy.previewShareMissingMessage)
                            .font(.caption2)
                            .foregroundStyle(AppTheme.subtleText)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .background(AppTheme.surfaceBg, in: RoundedRectangle(cornerRadius: 14))
                    .overlay(
                        RoundedRectangle(cornerRadius: 14)
                            .stroke(AppTheme.warningYellow.opacity(0.22), lineWidth: 1)
                    )
                }

                LazyVGrid(columns: quickActionButtonGridColumns, alignment: .leading, spacing: 10) {
                    Button {
                        presentShareSheet(for: exportedURL)
                    } label: {
                        exportActionLabel(
                            title: "Share",
                            icon: "square.and.arrow.up.fill",
                            foreground: .white,
                            fill: AnyShapeStyle(AppTheme.purpleGradient),
                            stroke: AppTheme.neonPurple.opacity(0.28)
                        )
                    }
                    .buttonStyle(.plain)
                    .disabled(!exportAvailable)
                    .opacity(exportAvailable ? 1.0 : 0.5)
                    .sensoryFeedback(.impact(weight: .light), trigger: shareTrigger)
                    .accessibilityLabel("Share or open in another app")
                    .accessibilityValue(exportAvailable ? exportedURL.lastPathComponent : "Export unavailable")
                    .accessibilityHint("Opens the system share sheet for CapCut, iMovie, Files, Photos, and social apps.")

                    Button {
                        saveTrigger += 1
                        Task { await viewModel.saveToPhotos() }
                    } label: {
                        exportActionLabel(
                            title: "Save",
                            icon: "photo.badge.arrow.down.fill",
                            foreground: AppTheme.successGreen,
                            fill: AnyShapeStyle(AppTheme.successGreen.opacity(0.12)),
                            stroke: AppTheme.successGreen.opacity(0.22)
                        )
                    }
                    .buttonStyle(.plain)
                    .disabled(!exportAvailable)
                    .opacity(exportAvailable ? 1.0 : 0.5)
                    .sensoryFeedback(.impact(weight: .light), trigger: saveTrigger)
                    .accessibilityLabel("Save to Photos")
                    .accessibilityValue(exportAvailable ? "Ready" : "Export unavailable")
                        .accessibilityHint("Saves the saved reel to Photos.")
                }
            }
            .padding(16)
            .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.06)
        }
    }

    private var exportButton: some View {
        VStack(spacing: 12) {
            if viewModel.exportService.isExporting {
                VStack(spacing: 12) {
                    ProgressView(value: viewModel.exportService.exportProgress)
                        .tint(AppTheme.accentPurple)
                        .scaleEffect(y: 2)
                        .accessibilityLabel("Export progress")
                        .accessibilityValue("\(Int(viewModel.exportService.exportProgress * 100)) percent")

                    Text(viewModel.exportService.statusMessage)
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                }
                .padding(16)
                .rorkCard(cornerRadius: 16, stroke: AppTheme.accentPurple.opacity(0.2))
                .accessibilityElement(children: .combine)
                .accessibilityLabel("Exporting highlight reel")
                .accessibilityValue("\(Int(viewModel.exportService.exportProgress * 100)) percent. \(viewModel.exportService.statusMessage)")
            } else {
                let cloudRenderRequired = AppConstants.requiresCloudVideoPipeline
                Button {
                    exportTrigger += 1
                    if hasLockedSelections {
                        showingPaywall = true
                        return
                    }
                    if cloudRenderRequired {
                        viewModel.exportService.markUnavailable(AppConstants.localVideoExportUnavailableMessage)
                        return
                    }
                    Task { await viewModel.exportHighlights(isProUser: subscriptionManager.isProUser) }
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: exportButtonIcon(isCloudRequired: cloudRenderRequired))
                            .font(.title3)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(exportButtonTitle(isCloudRequired: cloudRenderRequired))
                                .font(.headline)
                            Text(exportButtonSubtitle(isCloudRequired: cloudRenderRequired))
                                .font(.caption)
                                .opacity(0.72)
                                .lineLimit(2)
                                .minimumScaleFactor(0.84)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .layoutPriority(1)
                        Spacer()
                        Image(systemName: "sparkles")
                    }
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 18)
                    .background(hasLockedSelections ? lockedExportGradient : AppTheme.purpleGradient, in: .rect(cornerRadius: 16))
                }
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(AppTheme.neonPurple.opacity(0.25), lineWidth: 1)
                )
                .sensoryFeedback(.impact(weight: .heavy), trigger: exportTrigger)
                .accessibilityLabel(exportButtonAccessibilityLabel(isCloudRequired: cloudRenderRequired))
                .accessibilityValue("\(viewModel.selectedTheme.rawValue), \(viewModel.selectedQuality.rawValue), \(viewModel.selectedFormat.rawValue)")
                .accessibilityHint(exportButtonAccessibilityHint(isCloudRequired: cloudRenderRequired))
            }
        }
    }

    private var hasLockedSelections: Bool {
        isThemeLocked(viewModel.selectedTheme) || isMusicLocked(viewModel.selectedMusic)
    }

    private var canShowExportWorkspace: Bool {
        !viewModel.keptClips.isEmpty || viewModel.hasCloudEditCandidatePool
    }

    private var summaryPrimaryValue: String {
        viewModel.keptClips.isEmpty ? "\(viewModel.cloudEditCandidatePoolCount)" : "\(viewModel.keptClips.count)"
    }

    private var summaryPrimaryLabel: String {
        viewModel.keptClips.isEmpty ? "Candidates" : "Clips"
    }

    private var summarySecondaryValue: String {
        viewModel.keptClips.isEmpty ? "AI picks" : Clip.formatTime(viewModel.keptClips.reduce(0) { $0 + $1.duration })
    }

    private var summarySecondaryLabel: String {
        viewModel.keptClips.isEmpty ? "Selection" : "Duration"
    }

    private var summaryMetricGridColumns: [GridItem] {
        [
            GridItem(.adaptive(minimum: dynamicTypeSize.isAccessibilitySize ? 132 : 104), spacing: 10, alignment: .leading)
        ]
    }

    private var summaryClipGridColumns: [GridItem] {
        [
            GridItem(.adaptive(minimum: dynamicTypeSize.isAccessibilitySize ? 156 : 118, maximum: 260), spacing: 8, alignment: .top)
        ]
    }

    private var summaryClipPreviewLimit: Int {
        dynamicTypeSize.isAccessibilitySize ? 4 : 6
    }

    private var summaryClipOverflowCount: Int {
        max(0, viewModel.keptClips.count - summaryClipPreviewLimit)
    }

    private var quickActionButtonGridColumns: [GridItem] {
        [
            GridItem(.adaptive(minimum: dynamicTypeSize.isAccessibilitySize ? 156 : 128), spacing: 10, alignment: .top)
        ]
    }

    private var themeOptionGridColumns: [GridItem] {
        [
            GridItem(.adaptive(minimum: dynamicTypeSize.isAccessibilitySize ? 168 : 116), spacing: 10, alignment: .top)
        ]
    }

    private var exportOptionGridColumns: [GridItem] {
        [
            GridItem(.adaptive(minimum: dynamicTypeSize.isAccessibilitySize ? 168 : 116), spacing: 10, alignment: .top)
        ]
    }

    private func summaryMetric(value: String, label: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(value)
                .font(.title.bold().monospacedDigit())
                .foregroundStyle(AppTheme.neonPurple)
                .lineLimit(1)
                .minimumScaleFactor(0.72)
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.subtleText)
                .lineLimit(2)
                .minimumScaleFactor(0.86)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 66 : 52, alignment: .leading)
    }

    private func summaryClipChip(icon: String, text: String) -> some View {
        HStack(alignment: .top, spacing: 6) {
            Image(systemName: icon)
                .font(.caption2.weight(.semibold))
                .padding(.top, 1)
            Text(text)
                .font(.caption2.weight(.semibold))
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                .minimumScaleFactor(0.82)
                .fixedSize(horizontal: false, vertical: true)
                .layoutPriority(1)
            Spacer(minLength: 0)
        }
        .foregroundStyle(.white)
        .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 44 : 32, alignment: .leading)
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(AppTheme.surfaceBg, in: .rect(cornerRadius: 12))
    }

    private func exportActionLabel(
        title: String,
        icon: String,
        foreground: Color,
        fill: AnyShapeStyle,
        stroke: Color
    ) -> some View {
        Label(title, systemImage: icon)
            .font(.subheadline.bold())
            .multilineTextAlignment(.center)
            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
            .minimumScaleFactor(0.84)
            .fixedSize(horizontal: false, vertical: true)
            .foregroundStyle(foreground)
            .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 52 : 44)
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(fill, in: .rect(cornerRadius: 14))
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(stroke, lineWidth: 1)
            )
    }

    private var localExportSetupSummary: String {
        let summary = "\(viewModel.selectedTheme.rawValue) • \(viewModel.selectedQuality.rawValue) • \(viewModel.selectedFormat.rawValue)"
        if hasLockedSelections {
            return "\(summary). One selected option needs Pro."
        }
        return "\(summary). Ready to export."
    }

    private var lockedExportGradient: LinearGradient {
        LinearGradient(
            colors: [
                AppTheme.warningYellow.opacity(0.95),
                AppTheme.accentPurple.opacity(0.9)
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    private func exportButtonIcon(isCloudRequired: Bool) -> String {
        if hasLockedSelections {
            return "lock.fill"
        }
        return isCloudRequired ? "sparkles.tv.fill" : "square.and.arrow.up.fill"
    }

    private func exportButtonTitle(isCloudRequired: Bool) -> String {
        if hasLockedSelections {
            return "Unlock Pro to Export"
        }
        return isCloudRequired ? "Make AI Reel" : "Export Highlight Reel"
    }

    private func exportButtonSubtitle(isCloudRequired: Bool) -> String {
        if isCloudRequired {
            return "HoopClips makes the final video for you"
        }
        return "\(viewModel.selectedTheme.rawValue) • \(viewModel.selectedQuality.rawValue) • \(viewModel.selectedFormat.rawValue)"
    }

    private func exportButtonAccessibilityLabel(isCloudRequired: Bool) -> String {
        if hasLockedSelections {
            return "Unlock Pro to export"
        }
        return isCloudRequired ? "Make AI reel" : "Export highlight reel"
    }

    private func exportButtonAccessibilityHint(isCloudRequired: Bool) -> String {
        if hasLockedSelections {
            return "Selected options include Pro-only features and will open the paywall."
        }
        if isCloudRequired {
            return "Use AI Edit to make a saved reel before sharing."
        }
        return "Creates a video from kept clips."
    }

    private var shareSheetTitle: String {
        "HoopClips Highlight Reel"
    }

    private func isThemeLocked(_ theme: ExportTheme) -> Bool {
        theme.requiresPro && !subscriptionManager.isProUser
    }

    private func isMusicLocked(_ track: MusicTrack) -> Bool {
        track.requiresPro && !subscriptionManager.isProUser
    }

    private func selectionTitle(_ title: String, isLocked: Bool) -> String {
        isLocked ? "\(title) • Pro" : title
    }

    private func optionAccessibilityValue(isSelected: Bool, isLocked: Bool) -> String {
        switch (isSelected, isLocked) {
        case (true, true): return "Selected, locked"
        case (true, false): return "Selected"
        case (false, true): return "Locked"
        case (false, false): return "Not selected"
        }
    }

    private func musicAccessibilityHint(for track: MusicTrack, isLocked: Bool) -> String {
        if isLocked { return "Requires Pro. Opens the paywall." }
        if track == .custom { return "Opens Files to choose custom audio." }
        return "Sets the export music track."
    }

    private func presentShareSheet(for url: URL) {
        guard isExportFileAvailable(url), !showSystemShareSheet else { return }
        shareURL = url
        shareTrigger += 1
        showSystemShareSheet = true
    }

    private func clearShareSelection() {
        shareURL = nil
    }

    private func announceExportProgress(_ progress: Double) {
        guard viewModel.exportService.isExporting else {
            lastExportAnnouncementPercent = -1
            return
        }

        let percent = Int((progress * 100).rounded())
        let bucket = (percent / 25) * 25
        guard bucket >= 25, bucket <= 100, bucket != lastExportAnnouncementPercent else { return }
        lastExportAnnouncementPercent = bucket
        HoopsAccessibility.announce("Export \(bucket) percent complete.")
    }

    private func isExportFileAvailable(_ url: URL) -> Bool {
        FileManager.default.fileExists(atPath: url.path)
    }

    private func configureExportPreviewPlayer(for url: URL?) {
        guard let url, isExportFileAvailable(url) else {
            teardownExportPreviewPlayer()
            return
        }

        if let currentURL = (exportPreviewPlayer?.currentItem?.asset as? AVURLAsset)?.url,
           currentURL == url {
            return
        }

        exportPreviewPlayer?.pause()
        exportPreviewPlayer = AVPlayer(url: url)
        inspectExportPreviewAudioTrack(for: url)
        applyExportPreviewAudioMute()
    }

    private func configureExpandedExportPreviewPlayer(for url: URL?) {
        guard let url, isExportFileAvailable(url) else {
            teardownExpandedExportPreviewPlayer()
            return
        }

        if let currentURL = (expandedExportPreviewPlayer?.currentItem?.asset as? AVURLAsset)?.url,
           currentURL == url {
            return
        }

        expandedExportPreviewPlayer?.pause()
        expandedExportPreviewPlayer = AVPlayer(url: url)
        inspectExportPreviewAudioTrack(for: url)
        applyExportPreviewAudioMute()
    }

    private func teardownExportPreviewPlayer() {
        exportPreviewPlayer?.pause()
        exportPreviewPlayer = nil
        clearExportPreviewAudioTrackState()
    }

    private func teardownExpandedExportPreviewPlayer() {
        expandedExportPreviewPlayer?.pause()
        expandedExportPreviewPlayer = nil
    }

    private func pausePreviewPlayers() {
        exportPreviewPlayer?.pause()
        expandedExportPreviewPlayer?.pause()
    }

    private func applyExportPreviewAudioMute() {
        exportPreviewPlayer?.isMuted = previewAudioMuted
        exportPreviewPlayer?.volume = previewAudioMuted ? 0 : 1
        expandedExportPreviewPlayer?.isMuted = previewAudioMuted
        expandedExportPreviewPlayer?.volume = previewAudioMuted ? 0 : 1
    }

    private func clearExportPreviewAudioTrackState() {
        exportPreviewAudioCheckTask?.cancel()
        exportPreviewAudioCheckTask = nil
        exportPreviewHasAudioTrack = nil
    }

    private func inspectExportPreviewAudioTrack(for url: URL) {
        exportPreviewAudioCheckTask?.cancel()
        exportPreviewHasAudioTrack = nil
        let expectedURL = url.standardizedFileURL
        exportPreviewAudioCheckTask = Task { @MainActor in
            let asset = AVURLAsset(url: expectedURL)
            let hasAudio = ((try? await asset.loadTracks(withMediaType: .audio)) ?? []).isEmpty == false
            guard !Task.isCancelled else { return }
            exportPreviewHasAudioTrack = hasAudio
        }
    }

    private func exportPreviewMuteButton(accessibilityIdentifier: String) -> some View {
        VStack(alignment: .trailing, spacing: 8) {
            Button {
                previewAudioMuted.toggle()
                applyExportPreviewAudioMute()
            } label: {
                Image(systemName: previewAudioMuted ? "speaker.slash.fill" : "speaker.wave.2.fill")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.white)
                    .padding(9)
                    .background(.black.opacity(0.58), in: Circle())
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier(accessibilityIdentifier)
            .accessibilityLabel(previewAudioMuted ? "Unmute export preview" : "Mute export preview")

            if exportPreviewHasAudioTrack == false && !previewAudioMuted {
                Text("No reel audio")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 9)
                    .padding(.vertical, 6)
                    .background(.black.opacity(0.62), in: Capsule())
                    .accessibilityIdentifier("\(accessibilityIdentifier).noAudio")
            }
        }
        .padding(10)
    }

    private func exportPreviewSheet(url: URL) -> some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.16)

                if !isExportFileAvailable(url) {
                    ContentUnavailableView {
                        Label("Reel not ready", systemImage: "video.slash.fill")
                    } description: {
                        Text(ExportReelCopy.previewMissingMessage)
                    }
                    .foregroundStyle(.white)
                    .padding(16)
                } else if let expandedExportPreviewPlayer {
                    VStack(alignment: .leading, spacing: 12) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(url.lastPathComponent)
                                .font(.caption.monospaced())
                                .foregroundStyle(AppTheme.subtleText)
                                .lineLimit(2)
                                .minimumScaleFactor(0.82)
                                .fixedSize(horizontal: false, vertical: true)

                            HStack(spacing: 8) {
                                RorkMetricChip(
                                    icon: "film.stack.fill",
                                    value: "\(viewModel.keptClips.count)",
                                    label: "Clips",
                                    tint: AppTheme.neonPurple
                                )
                            }

                            Text("Review your reel before saving or sharing.")
                                .font(.caption)
                                .foregroundStyle(AppTheme.subtleText)
                        }

                        ZStack(alignment: .topTrailing) {
                            VideoPlayer(player: expandedExportPreviewPlayer)
                                .clipShape(.rect(cornerRadius: 16))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 16)
                                        .stroke(AppTheme.accentPurple.opacity(0.28), lineWidth: 1)
                                )
                                .accessibilityLabel("Expanded export preview")
                                .accessibilityValue(url.lastPathComponent)
                                .accessibilityHint("Use playback controls to review the exported highlight reel.")

                            exportPreviewMuteButton(accessibilityIdentifier: "export.preview.expanded.muteToggle")
                        }
                    }
                    .padding(16)
                } else {
                    ProgressView()
                        .tint(AppTheme.neonPurple)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .accessibilityLabel("Loading export preview")
                }
            }
            .navigationTitle("Review Reel")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        showExportPreviewSheet = false
                    }
                    .foregroundStyle(AppTheme.neonPurple)
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationBackground(AppTheme.darkBg)
        .onAppear {
            configureExpandedExportPreviewPlayer(for: url)
        }
        .onDisappear {
            teardownExpandedExportPreviewPlayer()
        }
    }
}

nonisolated enum ExportReelCopy {
    static let previewMissingMessage = "Make the reel with AI Edit to preview."
    static let previewShareMissingMessage = "Make the reel with AI Edit before sharing."
}
