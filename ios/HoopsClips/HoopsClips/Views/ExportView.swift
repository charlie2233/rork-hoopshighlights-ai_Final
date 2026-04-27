import SwiftUI
import AVKit
import UniformTypeIdentifiers

struct ExportView: View {
    private enum QuickShareCategory {
        case editor
        case social
    }

    @Environment(SubscriptionManager.self) private var subscriptionManager
    @Environment(AuthService.self) private var authService
    @Bindable var viewModel: HighlightsViewModel
    @State private var exportTrigger = 0
    @State private var saveTrigger = 0
    @State private var shareTrigger = 0
    @State private var showingPaywall = false
    @State private var showSystemShareSheet = false
    @State private var showExportPreviewSheet = false
    @State private var musicPreviewManager = MusicPreviewManager()
    @State private var editorShortcuts = EditorAppSupport.defaultShortcuts
    @State private var socialShortcuts = SocialAppSupport.defaultShortcuts
    @State private var exportPreviewPlayer: AVPlayer?
    @State private var expandedExportPreviewPlayer: AVPlayer?
    @State private var shareURL: URL?
    @State private var lastAutoPresentedExportURL: URL?
    @State private var selectedShareTargetHint: String?
    @State private var selectedShareCategory: QuickShareCategory?
    @State private var shareErrorMessage: String?
    @State private var showFileImporter = false

    var body: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.20)

                if viewModel.keptClips.isEmpty {
                    emptyState
                } else {
                    ScrollView {
                        VStack(spacing: 24) {
                            summaryCard
                            themeSection
                            musicSection
                            qualitySection
                            formatSection
                            postProcessingSection
                            quickActionsSection
                            exportButton
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
                        items: SystemShareSheet.videoItems(for: shareURL, title: "Hoops Highlight Reel"),
                        subject: "Hoops Highlight Reel",
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
                refreshEditorShortcuts()
                refreshSocialShortcuts()
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
            }
            .onDisappear {
                pausePreviewPlayers()
            }
        }
    }

    private var emptyState: some View {
        HoopsEmptyStateCard(
            title: "No Clips to Export",
            message: "Keep a few moments in Review first. Then Hoops Clips can turn them into a share-ready highlight reel.",
            icon: "square.and.arrow.up.fill"
        )
    }

    private var summaryCard: some View {
        VStack(spacing: 12) {
            RorkSectionHeader(
                title: "Highlight Reel",
                icon: "film.stack.fill",
                subtitle: "Export only uses clips marked Keep from Review"
            )

            HStack(spacing: 20) {
                VStack(spacing: 4) {
                    Text("\(viewModel.keptClips.count)")
                        .font(.title.bold().monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                    Text("Clips")
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                }

                VStack(spacing: 4) {
                    Text(Clip.formatTime(viewModel.keptClips.reduce(0) { $0 + $1.duration }))
                        .font(.title.bold().monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                    Text("Duration")
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                }

                Spacer()
            }

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: "paintbrush.fill",
                    value: selectionTitle(viewModel.selectedTheme.rawValue, isLocked: isThemeLocked(viewModel.selectedTheme)),
                    label: "Theme"
                )
                RorkMetricChip(
                    icon: "slider.horizontal.3",
                    value: viewModel.selectedQuality.rawValue,
                    label: "Quality",
                    tint: AppTheme.warningYellow
                )
            }

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: viewModel.selectedFormat.icon,
                    value: viewModel.selectedFormat.rawValue,
                    label: "Format",
                    tint: AppTheme.successGreen
                )
                RorkMetricChip(
                    icon: "music.note",
                    value: selectionTitle(viewModel.selectedMusic == .none ? "No Music" : "Music", isLocked: isMusicLocked(viewModel.selectedMusic)),
                    label: viewModel.selectedMusic == .none ? "Audio" : viewModel.selectedMusic.rawValue,
                    tint: AppTheme.neonPurple
                )
            }

            if hasLockedSelections {
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

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(viewModel.keptClips) { clip in
                        HStack(spacing: 4) {
                            Image(systemName: clip.action.icon)
                                .font(.caption2)
                            Text(clip.label)
                                .font(.caption2)
                        }
                        .foregroundStyle(.white)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(AppTheme.surfaceBg, in: .capsule)
                    }
                }
            }
            .contentMargins(.horizontal, 0)
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.accentPurple.opacity(0.2))
    }

    private var themeSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            RorkSectionHeader(
                title: "Theme",
                icon: "paintbrush.fill",
                subtitle: "Visual overlays and color treatment for the reel"
            )

            LazyVGrid(columns: [GridItem(.adaptive(minimum: 100), spacing: 10)], spacing: 10) {
                ForEach(ExportTheme.allCases) { theme in
                    let isLocked = isThemeLocked(theme)
                    Button {
                        guard !isLocked else {
                            showingPaywall = true
                            return
                        }
                        withAnimation(.snappy) { viewModel.selectedTheme = theme }
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

                            if isLocked {
                                Text("PRO")
                                    .font(.caption2.bold())
                                    .foregroundStyle(AppTheme.warningYellow)
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 3)
                                    .background(AppTheme.warningYellow.opacity(0.10), in: Capsule())
                            }
                        }
                        .frame(maxWidth: .infinity)
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
                }
            }

            Text(viewModel.selectedTheme.description)
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
                .padding(.leading, 4)

            if !subscriptionManager.isProUser {
                Text("Pro unlocks Neon, Cinematic, and Hype export themes.")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.warningYellow)
                    .padding(.leading, 4)
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
                subtitle: "Choose soundtrack mood for the final cut"
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
                                    withAnimation(.snappy) { viewModel.selectedMusic = track }
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
                    print("File selection failed: \(error.localizedDescription)")
                }
            }

            if !subscriptionManager.isProUser {
                Text("Pro unlocks premium music packs.")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.warningYellow)
                    .padding(.leading, 4)
            }
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

            HStack(spacing: 10) {
                ForEach(ExportQuality.allCases) { quality in
                    Button {
                        withAnimation(.snappy) { viewModel.selectedQuality = quality }
                    } label: {
                        VStack(spacing: 4) {
                            Text(quality.rawValue)
                                .font(.headline)
                            Text(quality.description)
                                .font(.caption2)
                                .lineLimit(2)
                                .multilineTextAlignment(.center)
                        }
                        .foregroundStyle(viewModel.selectedQuality == quality ? .white : AppTheme.subtleText)
                        .frame(maxWidth: .infinity)
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

            HStack(spacing: 10) {
                ForEach(ExportFileFormat.allCases) { format in
                    Button {
                        withAnimation(.snappy) { viewModel.selectedFormat = format }
                    } label: {
                        VStack(alignment: .leading, spacing: 6) {
                            HStack(spacing: 8) {
                                Image(systemName: format.icon)
                                    .font(.subheadline.weight(.semibold))
                                Text(format.rawValue)
                                    .font(.headline)
                            }
                            Text(format.description)
                                .font(.caption2)
                                .lineLimit(2)
                                .multilineTextAlignment(.leading)
                                .foregroundStyle(
                                    viewModel.selectedFormat == format
                                    ? Color.white.opacity(0.8)
                                    : AppTheme.subtleText
                                )
                        }
                        .foregroundStyle(viewModel.selectedFormat == format ? .white : AppTheme.subtleText)
                        .frame(maxWidth: .infinity, alignment: .leading)
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
                    subtitle: "Preview the latest export before saving or sharing"
                )

                if exportAvailable {
                    VStack(alignment: .leading, spacing: 8) {
                        Group {
                            if let exportPreviewPlayer {
                                VideoPlayer(player: exportPreviewPlayer)
                            } else {
                                ProgressView()
                                    .tint(AppTheme.neonPurple)
                                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                                    .background(AppTheme.surfaceBg)
                            }
                        }
                        .frame(height: 220)
                        .clipShape(.rect(cornerRadius: 16))
                        .overlay(
                            RoundedRectangle(cornerRadius: 16)
                                .stroke(AppTheme.accentPurple.opacity(0.28), lineWidth: 1)
                        )
                        .overlay(alignment: .topLeading) {
                            Text(exportedURL.lastPathComponent)
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
                        }

                        Text("Your latest export opens in review first. You can reopen it here anytime.")
                            .font(.caption2)
                            .foregroundStyle(AppTheme.subtleText)
                    }
                } else {
                    VStack(alignment: .leading, spacing: 6) {
                        Label("Export preview unavailable", systemImage: "exclamationmark.triangle.fill")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(AppTheme.warningYellow)
                        Text("The latest export file is no longer available on this device. Re-export to preview or share it again.")
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

                HStack(spacing: 10) {
                    Button {
                        presentShareSheet(for: exportedURL)
                    } label: {
                        HStack(spacing: 10) {
                            Image(systemName: "square.and.arrow.up.fill")
                                .font(.subheadline.weight(.semibold))
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Open In / Share")
                                    .font(.subheadline.bold())
                                Text(exportedURL.lastPathComponent)
                                    .font(.caption2.monospaced())
                                    .foregroundStyle(Color.white.opacity(0.72))
                                    .lineLimit(1)
                            }
                            Spacer()
                            Image(systemName: "bolt.fill")
                                .font(.caption.bold())
                        }
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 12)
                        .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 14))
                        .overlay(
                            RoundedRectangle(cornerRadius: 14)
                                .stroke(AppTheme.neonPurple.opacity(0.28), lineWidth: 1)
                        )
                    }
                    .buttonStyle(.plain)
                    .disabled(!exportAvailable)
                    .opacity(exportAvailable ? 1.0 : 0.5)
                    .sensoryFeedback(.impact(weight: .light), trigger: shareTrigger)

                    Button {
                        saveTrigger += 1
                        Task { await viewModel.saveToPhotos() }
                    } label: {
                        VStack(spacing: 4) {
                            Image(systemName: "photo.badge.arrow.down.fill")
                                .font(.subheadline.weight(.semibold))
                            Text("Save")
                                .font(.caption.bold())
                        }
                        .foregroundStyle(AppTheme.successGreen)
                        .frame(width: 74)
                        .padding(.vertical, 12)
                        .background(AppTheme.successGreen.opacity(0.12), in: .rect(cornerRadius: 14))
                        .overlay(
                            RoundedRectangle(cornerRadius: 14)
                                .stroke(AppTheme.successGreen.opacity(0.22), lineWidth: 1)
                        )
                    }
                    .buttonStyle(.plain)
                    .disabled(!exportAvailable)
                    .opacity(exportAvailable ? 1.0 : 0.5)
                    .sensoryFeedback(.impact(weight: .light), trigger: saveTrigger)
                }

                VStack(alignment: .leading, spacing: 10) {
                    HStack(spacing: 8) {
                        Image(systemName: "sparkles.rectangle.stack.fill")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(AppTheme.warningYellow)
                        Text("Send to editor")
                            .font(.caption.bold())
                            .foregroundStyle(.white)
                        Spacer()
                    }

                    HStack(spacing: 10) {
                        ForEach(editorShortcuts) { shortcut in
                            Button {
                                presentShareSheet(
                                    for: exportedURL,
                                    preferredTarget: shortcut.displayName,
                                    category: .editor
                                )
                            } label: {
                                VStack(alignment: .leading, spacing: 8) {
                                    HStack(spacing: 6) {
                                        Image(systemName: shortcut.iconSystemName)
                                            .font(.caption.weight(.semibold))
                                        Text(shortcut.displayName)
                                            .font(.caption.bold())
                                            .lineLimit(1)
                                    }
                                    .foregroundStyle(.white)

                                    Text(shortcut.statusText)
                                        .font(.caption2.weight(.medium))
                                        .foregroundStyle(shortcut.isInstalled ? AppTheme.successGreen : AppTheme.subtleText)
                                        .lineLimit(1)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 10)
                                .background(
                                    shortcut.isInstalled
                                    ? AppTheme.successGreen.opacity(0.12)
                                    : AppTheme.surfaceBg,
                                    in: RoundedRectangle(cornerRadius: 12)
                                )
                                .overlay(
                                    RoundedRectangle(cornerRadius: 12)
                                        .stroke(
                                            shortcut.isInstalled
                                            ? AppTheme.successGreen.opacity(0.28)
                                            : AppTheme.softBorder,
                                            lineWidth: 1
                                        )
                                )
                            }
                            .buttonStyle(.plain)
                            .disabled(!exportAvailable)
                            .opacity(exportAvailable ? 1.0 : 0.5)
                        }
                    }

                    Text(editorShareHelperText)
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                }

                VStack(alignment: .leading, spacing: 10) {
                    HStack(spacing: 8) {
                        Image(systemName: "bubble.left.and.bubble.right.fill")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(AppTheme.neonPurple)
                        Text("Quick post")
                            .font(.caption.bold())
                            .foregroundStyle(.white)
                        Spacer()
                    }

                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                        ForEach(socialShortcuts) { shortcut in
                            Button {
                                presentShareSheet(
                                    for: exportedURL,
                                    preferredTarget: shortcut.displayName,
                                    category: .social
                                )
                            } label: {
                                VStack(alignment: .leading, spacing: 8) {
                                    HStack(spacing: 6) {
                                        Image(systemName: shortcut.iconSystemName)
                                            .font(.caption.weight(.semibold))
                                        Text(shortcut.displayName)
                                            .font(.caption.bold())
                                            .lineLimit(1)
                                    }
                                    .foregroundStyle(.white)

                                    Text(shortcut.statusText)
                                        .font(.caption2.weight(.medium))
                                        .foregroundStyle(shortcut.isInstalled ? AppTheme.successGreen : AppTheme.subtleText)
                                        .lineLimit(1)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 10)
                                .background(
                                    shortcut.isInstalled
                                    ? AppTheme.neonPurple.opacity(0.14)
                                    : AppTheme.surfaceBg,
                                    in: RoundedRectangle(cornerRadius: 12)
                                )
                                .overlay(
                                    RoundedRectangle(cornerRadius: 12)
                                        .stroke(
                                            shortcut.isInstalled
                                            ? AppTheme.neonPurple.opacity(0.28)
                                            : AppTheme.softBorder,
                                            lineWidth: 1
                                        )
                                )
                            }
                            .buttonStyle(.plain)
                            .disabled(!exportAvailable)
                            .opacity(exportAvailable ? 1.0 : 0.5)
                        }
                    }

                    Text(socialShareHelperText)
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
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

                    Text(viewModel.exportService.statusMessage)
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                }
                .padding(16)
                .rorkCard(cornerRadius: 16, stroke: AppTheme.accentPurple.opacity(0.2))
            } else {
                Button {
                    exportTrigger += 1
                    if hasLockedSelections {
                        showingPaywall = true
                        return
                    }
                    Task { await viewModel.exportHighlights(isProUser: subscriptionManager.isProUser) }
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: hasLockedSelections ? "lock.fill" : "square.and.arrow.up.fill")
                            .font(.title3)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(hasLockedSelections ? "Unlock Pro to Export" : "Export Highlight Reel")
                                .font(.headline)
                            Text("\(viewModel.selectedTheme.rawValue) • \(viewModel.selectedQuality.rawValue) • \(viewModel.selectedFormat.rawValue)")
                                .font(.caption)
                                .opacity(0.72)
                                .lineLimit(1)
                        }
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
            }
        }
    }

    private var hasLockedSelections: Bool {
        isThemeLocked(viewModel.selectedTheme) || isMusicLocked(viewModel.selectedMusic)
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

    private var editorShareHelperText: String {
        if selectedShareCategory == .editor, let selectedShareTargetHint {
            return "Choose \(selectedShareTargetHint) in the share sheet to continue editing."
        }
        return "Pick Adobe, CapCut, or iMovie in the share sheet to continue editing."
    }

    private var socialShareHelperText: String {
        if selectedShareCategory == .social, let selectedShareTargetHint {
            return "Choose \(selectedShareTargetHint) in the share sheet to post."
        }
        return "Pick your social app in the share sheet to post, or save to Photos first."
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

    private func presentShareSheet(
        for url: URL,
        preferredTarget: String? = nil,
        category: QuickShareCategory? = nil
    ) {
        guard isExportFileAvailable(url), !showSystemShareSheet else { return }
        shareURL = url
        selectedShareTargetHint = preferredTarget
        selectedShareCategory = category
        shareTrigger += 1
        showSystemShareSheet = true
    }

    private func clearShareSelection() {
        shareURL = nil
        selectedShareTargetHint = nil
        selectedShareCategory = nil
    }

    private func refreshEditorShortcuts() {
        editorShortcuts = EditorAppSupport.resolvedShortcuts()
    }

    private func refreshSocialShortcuts() {
        socialShortcuts = SocialAppSupport.resolvedShortcuts()
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
    }

    private func teardownExportPreviewPlayer() {
        exportPreviewPlayer?.pause()
        exportPreviewPlayer = nil
    }

    private func teardownExpandedExportPreviewPlayer() {
        expandedExportPreviewPlayer?.pause()
        expandedExportPreviewPlayer = nil
    }

    private func pausePreviewPlayers() {
        exportPreviewPlayer?.pause()
        expandedExportPreviewPlayer?.pause()
    }

    private func exportPreviewSheet(url: URL) -> some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.16)

                if !isExportFileAvailable(url) {
                    ContentUnavailableView {
                        Label("Review Unavailable", systemImage: "video.slash.fill")
                    } description: {
                        Text("This exported file is no longer available. Re-export the reel to preview it again.")
                    }
                    .foregroundStyle(.white)
                    .padding(16)
                } else if let expandedExportPreviewPlayer {
                    VStack(alignment: .leading, spacing: 12) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(url.lastPathComponent)
                                .font(.caption.monospaced())
                                .foregroundStyle(AppTheme.subtleText)
                                .lineLimit(1)

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

                        VideoPlayer(player: expandedExportPreviewPlayer)
                            .clipShape(.rect(cornerRadius: 16))
                            .overlay(
                                RoundedRectangle(cornerRadius: 16)
                                    .stroke(AppTheme.accentPurple.opacity(0.28), lineWidth: 1)
                            )
                    }
                    .padding(16)
                } else {
                    ProgressView()
                        .tint(AppTheme.neonPurple)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
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
