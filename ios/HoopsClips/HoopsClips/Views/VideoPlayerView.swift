import SwiftUI
import AVKit
import PhotosUI
import UniformTypeIdentifiers

struct VideoPlayerView: View {
    @Bindable var viewModel: HighlightsViewModel
    @Environment(SubscriptionManager.self) private var subscriptionManager
    @Environment(AuthService.self) private var authService
    @Environment(AppLanguageStore.self) private var languageStore
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var player: AVPlayer?
    @State private var showingFilePicker = false
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var showSourcePicker = false
    @State private var analysisStarted = false
    @State private var showingPaywall = false
    @State private var showingNoClipsAlert = false
    @State private var showingDurationLimitAlert = false
    @State private var isImportingVideo = false
    @State private var activeImportID: UUID?
    @State private var importTask: Task<Void, Never>?
    @State private var teamScanTask: Task<Void, Never>?
    @State private var importErrorMessage: String?
    @State private var lastAnalysisAnnouncementPercent = -1

    private let videoImportTimeoutNanoseconds: UInt64 = 90 * 1_000_000_000

    var body: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop()

                ScrollView {
                    VStack(spacing: 24) {
                        if viewModel.isVideoLoaded {
                            videoSection
                            projectOverviewCard
                            analysisSection
                        } else {
                            importSection
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                    .padding(.bottom, 100)
                }
            }
            .navigationTitle(languageStore.text(.playerTitle))
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                if viewModel.isVideoLoaded {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            returnToImportHome()
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundStyle(AppTheme.subtleText)
                        }
                        .accessibilityLabel("Close current video")
                        .accessibilityHint("Returns to the import screen and clears this project.")
                    }
                }
            }
            .confirmationDialog(languageStore.text(.importVideo), isPresented: $showSourcePicker) {
                Button(languageStore.text(.photoLibrary)) {
                    viewModel.showingVideoPicker = true
                }
                Button(languageStore.text(.files)) {
                    showingFilePicker = true
                }
            }
            .photosPicker(isPresented: $viewModel.showingVideoPicker, selection: $selectedPhotoItem, matching: .videos)
            .fileImporter(isPresented: $showingFilePicker, allowedContentTypes: [.movie, .video, .mpeg4Movie, .quickTimeMovie]) { result in
                if case .success(let url) = result {
                    importVideo(from: url)
                } else if case .failure(let error) = result {
                    importErrorMessage = "Could not import that file: \(error.localizedDescription)"
                }
            }
            .onChange(of: selectedPhotoItem) { _, newValue in
                guard let item = newValue else { return }
                selectedPhotoItem = nil
                importVideo(from: item)
            }
            .onAppear {
                syncPlayer(with: viewModel.videoURL)
            }
            .onChange(of: viewModel.videoURL) { _, newValue in
                syncPlayer(with: newValue)
            }
            .onChange(of: viewModel.isVideoLoaded) { _, isVideoLoaded in
                if !isVideoLoaded {
                    analysisStarted = false
                    lastAnalysisAnnouncementPercent = -1
                    teamScanTask?.cancel()
                    teamScanTask = nil
                } else {
                    HoopsAccessibility.announce("Video imported. Choose a target highlight length, then start analysis.")
                    startTeamScanIfNeeded()
                }
            }
            .onChange(of: isImportingVideo) { _, isImporting in
                HoopsAccessibility.announce(isImporting ? languageStore.text(.preparingVideo) : "Video import finished.")
            }
            .onChange(of: viewModel.analysisService.statusMessage) { _, message in
                guard viewModel.analysisService.isAnalyzing else { return }
                HoopsAccessibility.announce(message)
            }
            .onChange(of: viewModel.analysisService.progress) { _, progress in
                announceAnalysisProgress(progress)
            }
            .onChange(of: viewModel.clips.count) { _, clipCount in
                guard clipCount > 0 else { return }
                HoopsAccessibility.announce("\(clipCount) clips found. Review is ready.")
            }
            .sheet(isPresented: $showingPaywall) {
                PaywallView(subscriptionManager: subscriptionManager, authService: authService)
            }
            .alert(languageStore.text(.noHighlightsFound), isPresented: $showingNoClipsAlert) {
                Button("OK", role: .cancel) { }
            } message: {
                if viewModel.isCloudFallbackOffered {
                    Text(languageStore.text(.noHighlightsMessage))
                } else {
                    Text(languageStore.text(.noHighlightsAlternateMessage))
                }
            }
            .alert(languageStore.text(.proRequiredTitle), isPresented: $showingDurationLimitAlert) {
                Button(languageStore.text(.notNow), role: .cancel) { }
                Button(languageStore.text(.goPro)) {
                    showingPaywall = true
                }
            } message: {
                Text("\(languageStore.text(.proRequiredMessagePrefix)) \(formatDuration(AppConstants.nonProMaxAnalysisDuration)). \(languageStore.text(.proRequiredMessageMiddle)) \(formatDuration(viewModel.videoDuration)).")
            }
            .alert("Video Import Failed", isPresented: Binding(
                get: { importErrorMessage != nil },
                set: { if !$0 { importErrorMessage = nil } }
            )) {
                Button("OK", role: .cancel) { importErrorMessage = nil }
            } message: {
                Text(importErrorMessage ?? "Choose another video and try again.")
            }
        }
    }

    private func importVideo(from url: URL) {
        beginVideoImport {
            await viewModel.loadVideo(url: url)
        }
    }

    private func importVideo(from item: PhotosPickerItem) {
        beginVideoImport {
            do {
                try Task.checkCancellation()

                guard let importedVideo = try await item.loadTransferable(type: ImportedVideoFile.self) else {
                    await MainActor.run {
                        importErrorMessage = "Hoopclips could not access a local video file from Photos. Save it to Files and import from there, or choose a shorter downloaded clip."
                    }
                    return false
                }

                try Task.checkCancellation()
                return await viewModel.loadVideo(url: importedVideo.url)
            } catch is CancellationError {
                return false
            } catch {
                await MainActor.run {
                    importErrorMessage = "Hoopclips could not import that video: \(error.localizedDescription)"
                }
                return false
            }
        }
    }

    private func beginVideoImport(_ operation: @escaping () async -> Bool) {
        guard !isImportingVideo else { return }
        importTask?.cancel()

        let importID = UUID()
        activeImportID = importID
        isImportingVideo = true
        importErrorMessage = nil

        let task = Task {
            let timeoutTask = Task {
                do {
                    try await Task.sleep(nanoseconds: videoImportTimeoutNanoseconds)
                } catch {
                    return
                }

                await MainActor.run {
                    guard activeImportID == importID, isImportingVideo else { return }
                    importErrorMessage = "Hoopclips is still waiting for that video. Try a shorter local clip, or save it to Files and import it again."
                    importTask?.cancel()
                    clearImportState()
                }
            }

            let didLoadVideo = await operation()
            timeoutTask.cancel()

            await MainActor.run {
                guard activeImportID == importID else { return }

                clearImportState()
                if importErrorMessage == nil && (!didLoadVideo || !viewModel.isVideoLoaded) {
                    importErrorMessage = "Hoopclips could not read that video. Try importing it from Files or choose another clip."
                }
            }
        }

        importTask = task
    }

    private func startTeamScanIfNeeded() {
        guard AppConstants.cloudAnalysisEnabled else { return }
        guard viewModel.isVideoLoaded, viewModel.clips.isEmpty else { return }
        guard teamScanTask == nil else { return }

        teamScanTask = Task { @MainActor in
            await viewModel.scanTeamsBeforeAnalysis()
            teamScanTask = nil
        }
    }

    private func cancelActiveImport() {
        importTask?.cancel()
        teamScanTask?.cancel()
        teamScanTask = nil
        clearImportState()
    }

    private func clearImportState() {
        isImportingVideo = false
        activeImportID = nil
        importTask = nil
    }

    private func syncPlayer(with url: URL?) {
        guard let url else {
            player?.pause()
            player = nil
            return
        }

        if let currentURL = (player?.currentItem?.asset as? AVURLAsset)?.url,
           currentURL == url {
            return
        }

        player?.pause()
        player = AVPlayer(url: url)
    }

    private func returnToImportHome() {
        viewModel.resetProject()
        player = nil
        selectedPhotoItem = nil
        showSourcePicker = false
        showingFilePicker = false
        viewModel.showingVideoPicker = false
        showingPaywall = false
        showingNoClipsAlert = false
        showingDurationLimitAlert = false
        analysisStarted = false
        teamScanTask?.cancel()
        teamScanTask = nil
        cancelActiveImport()
        importErrorMessage = nil
    }

    private var importSection: some View {
        VStack(spacing: 32) {
            Spacer().frame(height: 40)

            HoopsMotionHero()

            VStack(spacing: 12) {
                Text(languageStore.text(.turnGamesTitle))
                    .font(.title2.bold())
                    .foregroundStyle(.white)

                Text(languageStore.text(.turnGamesSubtitle))
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.subtleText)
                    .multilineTextAlignment(.center)
            }
            .padding(.horizontal, 10)

            Button {
                showSourcePicker = true
            } label: {
                HStack(spacing: 12) {
                    if isImportingVideo {
                        ProgressView()
                            .tint(.white)
                            .controlSize(.small)
                    } else {
                        Image(systemName: "plus.circle.fill")
                            .font(.title3)
                    }
                    Text(isImportingVideo ? languageStore.text(.preparingVideo) : languageStore.text(.selectVideo))
                        .font(.headline)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 16))
            }
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(AppTheme.neonPurple.opacity(0.25), lineWidth: 1)
            )
            .disabled(isImportingVideo)
            .opacity(isImportingVideo ? 0.82 : 1)
            .accessibilityLabel(isImportingVideo ? languageStore.text(.preparingVideo) : languageStore.text(.selectVideo))
            .accessibilityHint("Opens choices for importing a basketball video from Photos or Files.")
            .accessibilityValue(isImportingVideo ? "In progress" : "Ready")

            if isImportingVideo {
                Button {
                    cancelActiveImport()
                } label: {
                    Text(languageStore.text(.cancelImport))
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(AppTheme.subtleText)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(AppTheme.surfaceBg.opacity(0.7), in: .capsule)
                        .overlay(
                            Capsule()
                                .stroke(AppTheme.softBorder, lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)
                .accessibilityLabel(languageStore.text(.cancelImport))
                .accessibilityHint("Stops the current video import.")
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                featurePill(icon: "sparkles", text: languageStore.text(.smartHighlights))
                featurePill(icon: "bolt.fill", text: languageStore.text(.fastReels))
                featurePill(icon: "film.stack.fill", text: languageStore.text(.autoTrim))
                featurePill(icon: "basketball.fill", text: "Hoopclips")
            }
        }
        .padding(18)
        .rorkCard(cornerRadius: 22, stroke: AppTheme.softBorder, glowOpacity: 0.18)
    }

    private func featurePill(icon: String, text: String) -> some View {
        HStack(spacing: 10) {
            ZStack {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(AppTheme.accentPurple.opacity(0.14))
                    .frame(width: 32, height: 32)
                Image(systemName: icon)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.neonPurple)
            }

            Text(text)
                .font(.caption.weight(.medium))
                .foregroundStyle(.white)
                .lineLimit(1)

            Spacer(minLength: 0)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 10)
        .rorkCard(cornerRadius: 14, fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.7)), stroke: AppTheme.softBorder, glowOpacity: 0.04)
    }

    private var videoSection: some View {
        VStack(spacing: 16) {
            RorkSectionHeader(
                title: languageStore.text(.sourceVideo),
                icon: "video.fill",
                subtitle: viewModel.isVideoLoaded ? languageStore.text(.sourceVideoSubtitle) : nil
            )

            if let player = player {
                VideoPlayer(player: player)
                    .frame(height: 220)
                    .clipShape(.rect(cornerRadius: 16))
                    .overlay(
                        RoundedRectangle(cornerRadius: 16)
                            .stroke(AppTheme.accentPurple.opacity(0.3), lineWidth: 1)
                    )
                    .accessibilityLabel("Source video preview")
                    .accessibilityHint("Use playback controls to review the imported video.")
            } else if let thumbnail = viewModel.videoThumbnail {
                Image(decorative: thumbnail, scale: 1.0)
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(height: 220)
                    .clipShape(.rect(cornerRadius: 16))
            }

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: "clock.fill",
                    value: formatDuration(viewModel.videoDuration),
                    label: languageStore.text(.duration),
                    tint: AppTheme.warningYellow
                )

                if let url = viewModel.videoURL {
                    RorkMetricChip(
                        icon: "doc.fill",
                        value: url.pathExtension.uppercased().isEmpty ? "VIDEO" : url.pathExtension.uppercased(),
                        label: languageStore.text(.format),
                        tint: AppTheme.neonPurple
                    )
                }
            }

            if let url = viewModel.videoURL {
                HStack(spacing: 8) {
                    Image(systemName: "folder.fill")
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                    Text(url.lastPathComponent)
                        .font(.caption.monospaced())
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(1)
                    Spacer()
                }
                .padding(.horizontal, 4)
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder)
    }

    private var analysisSection: some View {
        VStack(spacing: 16) {
            RorkSectionHeader(
                title: languageStore.text(.aiAnalysis),
                icon: "brain.head.profile.fill",
                subtitle: analysisSectionSubtitle
            )

            if viewModel.analysisService.isAnalyzing {
                analysisProgressView
            } else if !viewModel.clips.isEmpty {
                analysisCompleteView
            } else {
                teamTargetControl
                targetHighlightLengthControl

                if !subscriptionManager.isProUser || viewModel.cloudQuotaRemaining != nil {
                    HStack(spacing: 8) {
                        Image(systemName: "sparkles")
                            .foregroundStyle(AppTheme.warningYellow)
                        Text(analysisBannerText)
                            .font(.caption.weight(.medium))
                            .foregroundStyle(AppTheme.warningYellow)
                        Spacer()
                        if subscriptionManager.freeUsesRemaining == 0 && subscriptionManager.isProUser == false {
                            Button(languageStore.text(.goPro)) { showingPaywall = true }
                                .font(.caption.bold())
                                .foregroundStyle(AppTheme.neonPurple)
                        }
                    }
                    .padding(12)
                    .rorkCard(cornerRadius: 12, fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.65)), stroke: AppTheme.softBorder, glowOpacity: 0.03)
                }

                Button {
                    guard !requiresProForCurrentVideo else {
                        showingDurationLimitAlert = true
                        return
                    }
                    guard !viewModel.isCloudTeamScanInProgress else { return }
                    guard !viewModel.requiresHighlightTeamSelectionConfirmation else {
                        HoopsAccessibility.announce("Choose a highlight team or All teams before analysis.")
                        return
                    }
                    analysisStarted = true
                    Task {
                        await viewModel.startAnalysis()
                        if viewModel.clips.isEmpty {
                            showingNoClipsAlert = true
                        }
                    }
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: "brain.head.profile.fill")
                            .font(.title3)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(languageStore.text(.analyzeWithAI))
                                .font(.headline)
                            Text(analysisButtonSubtitle)
                                .font(.caption)
                                .opacity(0.7)
                        }
                        Spacer()
                        Image(systemName: "chevron.right")
                    }
                    .foregroundStyle(.white)
                    .padding(16)
                    .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 16))
                }
                .disabled(viewModel.isCloudTeamScanInProgress || viewModel.requiresHighlightTeamSelectionConfirmation)
                .opacity(viewModel.isCloudTeamScanInProgress || viewModel.requiresHighlightTeamSelectionConfirmation ? 0.72 : 1)
                .sensoryFeedback(.impact(weight: .medium), trigger: analysisStarted)
                .accessibilityIdentifier("analysis.startButton")

                if AppConstants.requiresCloudVideoPipeline {
                    cloudAnalysisPathView
                }
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder)
    }

    private var teamTargetControl: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                ZStack {
                    Circle()
                        .fill(AppTheme.neonPurple.opacity(0.14))
                        .frame(width: 34, height: 34)
                    Image(systemName: "person.3.fill")
                        .font(.headline)
                        .foregroundStyle(AppTheme.neonPurple)
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text("Highlight Team")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                    Text(teamTargetSubtitle)
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(2)
                }

                Spacer(minLength: 0)
            }

            teamScanStatusRow

            HStack(spacing: 8) {
                ForEach(viewModel.availableHighlightTeamChoices, id: \.selectionKey) { selection in
                    teamTargetButton(selection)
                }
            }
        }
        .padding(14)
        .accessibilityIdentifier("analysis.teamTarget.section")
        .rorkCard(
            cornerRadius: 16,
            fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.68)),
            stroke: AppTheme.neonPurple.opacity(0.18),
            glow: AppTheme.neonPurple,
            glowOpacity: 0.04
        )
    }

    private func teamTargetButton(_ selection: HighlightTeamSelection) -> some View {
        let isSelected = viewModel.settings.highlightTeamSelection.selectionKey == selection.selectionKey
        let isConfirmedSelection = isSelected && !viewModel.requiresHighlightTeamSelectionConfirmation

        return Button {
            HoopsAccessibility.animate(reduceMotion: reduceMotion, .snappy(duration: 0.18)) {
                viewModel.confirmHighlightTeamSelection(selection)
            }
        } label: {
            VStack(spacing: 4) {
                if selection.mode == .all {
                    Image(systemName: "person.3.fill")
                        .font(.caption.weight(.bold))
                } else {
                    Circle()
                        .fill(teamSwatchColor(for: selection))
                        .frame(width: 14, height: 14)
                        .overlay(
                            Circle()
                                .stroke(isConfirmedSelection ? AppTheme.darkBg.opacity(0.25) : AppTheme.neonPurple.opacity(0.35), lineWidth: 1)
                        )
                }
                Text(selection.displayTitle)
                    .font(.caption.weight(.semibold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)
                    .accessibilityIdentifier(selection.accessibilityIdentifier)
            }
            .foregroundStyle(isConfirmedSelection ? AppTheme.darkBg : AppTheme.neonPurple)
            .frame(maxWidth: .infinity, minHeight: 48)
            .padding(.horizontal, 6)
            .background(
                isConfirmedSelection ? AppTheme.neonPurple : AppTheme.neonPurple.opacity(0.10),
                in: .rect(cornerRadius: 12)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(AppTheme.neonPurple.opacity(isConfirmedSelection ? 0 : 0.28), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Target \(selection.displayTitle)")
        .accessibilityValue(isConfirmedSelection ? "Selected" : isSelected ? "Tap to confirm" : "Not selected")
        .accessibilityHint(selection.displaySubtitle)
        .accessibilityIdentifier(selection.accessibilityIdentifier)
        .hoopsSelectedState(isConfirmedSelection)
    }

    private var teamTargetSubtitle: String {
        if viewModel.isCloudTeamScanInProgress {
            return viewModel.cloudTeamScanStatusMessage ?? "Scanning jersey colors before analysis."
        }
        if viewModel.requiresHighlightTeamSelectionConfirmation {
            return "Choose a jersey-color team or tap All teams before analysis."
        }
        if !viewModel.cloudDetectedTeams.isEmpty {
            return "Detected teams are labeled by jersey color. Uncertain plays stay in Review."
        }
        return "Team targeting unlocks after the cloud scan finds jersey colors. Use All teams for now."
    }

    private var teamScanStatusRow: some View {
        HStack(spacing: 8) {
            if viewModel.isCloudTeamScanInProgress {
                ProgressView()
                    .tint(AppTheme.neonPurple)
                    .controlSize(.small)
                Text(viewModel.cloudTeamScanStatusMessage ?? "Scanning teams")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(AppTheme.neonPurple)
            } else if !viewModel.cloudDetectedTeams.isEmpty {
                Image(systemName: viewModel.requiresHighlightTeamSelectionConfirmation ? "hand.tap.fill" : "checkmark.seal.fill")
                    .font(.caption)
                    .foregroundStyle(viewModel.requiresHighlightTeamSelectionConfirmation ? AppTheme.warningYellow : AppTheme.successGreen)
                Text(teamScanDetectedStatusText)
                    .font(.caption.weight(.medium))
                    .foregroundStyle(viewModel.requiresHighlightTeamSelectionConfirmation ? AppTheme.warningYellow : AppTheme.successGreen)
                    .lineLimit(1)
            } else if viewModel.cloudTeamScanErrorMessage != nil {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.caption)
                    .foregroundStyle(AppTheme.warningYellow)
                Text("Team scan unavailable")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(AppTheme.warningYellow)
                Spacer(minLength: 0)
                Button("Retry") {
                    startTeamScanIfNeeded()
                }
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.neonPurple)
            } else {
                Image(systemName: "sparkles")
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
                Text("All teams is available until jersey colors are detected")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(AppTheme.subtleText)
            }
            Spacer(minLength: 0)
        }
        .frame(minHeight: 20)
        .accessibilityIdentifier("analysis.teamTarget.status")
        .accessibilityElement(children: .combine)
    }

    private var teamScanDetectedStatusText: String {
        if viewModel.requiresHighlightTeamSelectionConfirmation {
            return "Choose target team"
        }
        return viewModel.cloudDetectedTeams.map(\.label).joined(separator: " vs ")
    }

    private func teamSwatchColor(for selection: HighlightTeamSelection) -> Color {
        if let hexColor = colorFromHex(selection.primaryColorHex) {
            return hexColor
        }

        switch selection.colorLabel?.lowercased() {
        case "black", "dark":
            return .black
        case "white", "light":
            return .white
        case "red":
            return .red
        case "blue":
            return .blue
        case "green":
            return .green
        case "yellow":
            return .yellow
        case "orange":
            return .orange
        case "purple":
            return .purple
        case "gray", "grey":
            return .gray
        default:
            return AppTheme.neonPurple
        }
    }

    private func colorFromHex(_ value: String?) -> Color? {
        guard let value else { return nil }
        let normalized = value.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmed = normalized.hasPrefix("#") ? String(normalized.dropFirst()) : normalized
        guard trimmed.count == 6, let integer = UInt64(trimmed, radix: 16) else { return nil }
        let red = Double((integer >> 16) & 0xff) / 255.0
        let green = Double((integer >> 8) & 0xff) / 255.0
        let blue = Double(integer & 0xff) / 255.0
        return Color(red: red, green: green, blue: blue)
    }

    private var targetHighlightLengthControl: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                ZStack {
                    Circle()
                        .fill(AppTheme.warningYellow.opacity(0.14))
                        .frame(width: 34, height: 34)
                    Image(systemName: "timer.circle.fill")
                        .font(.headline)
                        .foregroundStyle(AppTheme.warningYellow)
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text(languageStore.text(.settingsTargetHighlight))
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                    Text(languageStore.text(.settingsTargetHighlightHelp))
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(2)
                }

                Spacer(minLength: 0)

                Text(formattedTargetDuration(viewModel.settings.targetHighlightDuration))
                    .font(.subheadline.weight(.bold).monospacedDigit())
                    .foregroundStyle(AppTheme.warningYellow)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(AppTheme.warningYellow.opacity(0.12), in: .capsule)
            }

            HStack(spacing: 8) {
                ForEach([30.0, 45.0, 60.0, 90.0], id: \.self) { preset in
                    targetDurationPresetButton(preset)
                }
            }

            Slider(value: $viewModel.settings.targetHighlightDuration, in: 15.0...180.0, step: 5.0)
                .tint(AppTheme.warningYellow)
                .accessibilityLabel(languageStore.text(.settingsTargetHighlight))
                .accessibilityValue(formattedTargetDuration(viewModel.settings.targetHighlightDuration))
                .accessibilityHint("Sets the target length for the highlight reel before analysis.")
        }
        .padding(14)
        .rorkCard(
            cornerRadius: 16,
            fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.68)),
            stroke: AppTheme.warningYellow.opacity(0.18),
            glow: AppTheme.warningYellow,
            glowOpacity: 0.04
        )
    }

    private func targetDurationPresetButton(_ duration: Double) -> some View {
        let isSelected = abs(viewModel.settings.targetHighlightDuration - duration) < 0.1

        return Button {
            HoopsAccessibility.animate(reduceMotion: reduceMotion, .snappy(duration: 0.18)) {
                viewModel.settings.targetHighlightDuration = duration
            }
        } label: {
            Text(formattedTargetDuration(duration))
                .font(.caption.weight(.semibold).monospacedDigit())
                .foregroundStyle(isSelected ? AppTheme.darkBg : AppTheme.warningYellow)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(
                    isSelected ? AppTheme.warningYellow : AppTheme.warningYellow.opacity(0.10),
                    in: .capsule
                )
                .overlay(
                    Capsule()
                        .stroke(AppTheme.warningYellow.opacity(isSelected ? 0 : 0.28), lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Set target highlight length to \(formattedTargetDuration(duration))")
        .accessibilityValue(isSelected ? "Selected" : "Not selected")
        .hoopsSelectedState(isSelected)
    }

    private var analysisProgressView: some View {
        VStack(spacing: 16) {
            HStack {
                Image(systemName: "brain.head.profile.fill")
                    .foregroundStyle(AppTheme.neonPurple)
                    .symbolEffect(.variableColor.iterative, isActive: true)
                Text(analysisProgressTitle)
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
                Text("\(Int(viewModel.analysisService.progress * 100))%")
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(AppTheme.neonPurple)
            }

            ProgressView(value: viewModel.analysisService.progress)
                .tint(AppTheme.accentPurple)
                .scaleEffect(y: 2)
                .accessibilityLabel(analysisProgressTitle)
                .accessibilityValue("\(Int(viewModel.analysisService.progress * 100)) percent")

            Text(viewModel.analysisService.statusMessage)
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.accentPurple.opacity(0.2))
        .accessibilityElement(children: .combine)
        .accessibilityLabel(analysisProgressTitle)
        .accessibilityValue("\(Int(viewModel.analysisService.progress * 100)) percent. \(viewModel.analysisService.statusMessage)")
    }

    private var analysisCompleteView: some View {
        VStack(spacing: 12) {
            HStack {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(AppTheme.successGreen)
                Text(languageStore.text(.analysisComplete))
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
            }

            HStack(spacing: 16) {
                statBadge(value: "\(viewModel.clips.count)", label: languageStore.text(.clipsFound), color: AppTheme.neonPurple)
                statBadge(value: "\(viewModel.keptClips.count)", label: languageStore.text(.kept), color: AppTheme.successGreen)
                statBadge(value: formatDuration(viewModel.keptClips.reduce(0) { $0 + $1.duration }), label: languageStore.text(.duration), color: AppTheme.warningYellow)
            }

            if !analysisQualitySummaryRows.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(analysisQualitySummaryRows, id: \.self) { row in
                        Label(row, systemImage: "checkmark.seal.fill")
                            .font(.caption.weight(.medium))
                            .foregroundStyle(AppTheme.subtleText)
                            .lineLimit(2)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityElement(children: .combine)
                .accessibilityLabel("Analysis quality summary")
                .accessibilityValue(analysisQualitySummaryRows.joined(separator: " "))
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.successGreen.opacity(0.28), glow: AppTheme.successGreen, glowOpacity: 0.10)
    }

    private func statBadge(value: String, label: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title3.bold().monospacedDigit())
                .foregroundStyle(color)
            Text(label)
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
        }
        .frame(maxWidth: .infinity)
    }

    private var analysisQualitySummaryRows: [String] {
        guard let diagnostics = viewModel.analysisService.lastCloudDiagnostics else { return [] }
        var rows: [String] = []

        if diagnostics.usedTeamQuickScan == true {
            let candidates = diagnostics.preTeamFilterSegments ?? diagnostics.candidateSegments
            rows.append("Team scan reviewed \(candidates) candidate \(candidates == 1 ? "clip" : "clips") before filtering.")
        }

        let matched = diagnostics.teamMatchedReviewSegments ?? 0
        let uncertain = diagnostics.teamUncertainReviewSegments ?? 0
        if matched > 0 || uncertain > 0 {
            rows.append("\(matched) selected-team \(matched == 1 ? "clip" : "clips") and \(uncertain) uncertain \(uncertain == 1 ? "clip" : "clips") are in Review.")
        }

        let opponentFiltered = diagnostics.teamOpponentFilteredSegments ?? 0
        if opponentFiltered > 0 {
            rows.append("\(opponentFiltered) opponent \(opponentFiltered == 1 ? "clip was" : "clips were") filtered before Review.")
        }

        let defensive = diagnostics.defensiveReviewSegments ?? 0
        if defensive > 0 {
            let blocks = diagnostics.blockReviewSegments ?? 0
            let steals = diagnostics.stealReviewSegments ?? 0
            let forcedTurnovers = diagnostics.forcedTurnoverReviewSegments ?? 0
            let defensiveStops = diagnostics.defensiveStopReviewSegments ?? 0
            let defensiveDetails = [
                countSummary(blocks, singular: "block", plural: "blocks"),
                countSummary(steals, singular: "steal", plural: "steals"),
                countSummary(forcedTurnovers, singular: "forced turnover", plural: "forced turnovers"),
                countSummary(defensiveStops, singular: "defensive stop", plural: "defensive stops"),
            ].compactMap { $0 }
            let detailText = defensiveDetails.isEmpty ? "." : ", including \(defensiveDetails.joined(separator: ", "))."
            rows.append("Defense kept \(defensive) \(defensive == 1 ? "clip" : "clips")\(detailText)")
        }

        return rows
    }

    private func countSummary(_ count: Int, singular: String, plural: String) -> String? {
        guard count > 0 else { return nil }
        return "\(count) \(count == 1 ? singular : plural)"
    }

    private var cloudAnalysisPathView: some View {
        HStack(spacing: 8) {
            Image(systemName: "cloud.fill")
                .foregroundStyle(AppTheme.subtleText)
            Text("Cloud analysis runs in HoopClips backend for this build.")
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .rorkCard(cornerRadius: 12, fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.65)), stroke: AppTheme.softBorder, glowOpacity: 0.03)
    }

    private var projectOverviewCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            RorkSectionHeader(
                title: languageStore.text(.projectSnapshot),
                icon: "sparkles",
                subtitle: languageStore.text(.projectSnapshotSubtitle)
            )

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: "film.stack.fill",
                    value: "\(viewModel.clips.count)",
                    label: languageStore.text(.detected),
                    tint: AppTheme.neonPurple
                )
                RorkMetricChip(
                    icon: "checkmark.circle.fill",
                    value: "\(viewModel.keptClips.count)",
                    label: languageStore.text(.kept),
                    tint: AppTheme.successGreen
                )
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder, glowOpacity: 0.08)
    }

    private func formatDuration(_ seconds: Double) -> String {
        let mins = Int(seconds) / 60
        let secs = Int(seconds) % 60
        return String(format: "%d:%02d", mins, secs)
    }

    private func formattedTargetDuration(_ seconds: Double) -> String {
        if seconds < 60 {
            return "\(Int(seconds))s"
        }

        let minutes = Int(seconds) / 60
        let remainingSeconds = Int(seconds) % 60
        if remainingSeconds == 0 {
            return "\(minutes)m"
        }
        return "\(minutes)m \(remainingSeconds)s"
    }

    private var analysisBannerText: String {
        if requiresProForCurrentVideo {
            return "\(languageStore.text(.freeTierLimitPrefix)) \(formatDuration(AppConstants.nonProMaxAnalysisDuration)). \(languageStore.text(.freeTierLimitSuffix))"
        }
        if let remaining = viewModel.cloudQuotaRemaining {
            if remaining > 0 {
                let suffix = remaining == 1
                    ? languageStore.text(.freeAnalysisRemainingSingular)
                    : languageStore.text(.freeAnalysisRemainingPlural)
                return "\(remaining) \(suffix)"
            }
            return languageStore.text(.dailyAnalysesUsed)
        }
        return languageStore.text(.readyToFind)
    }

    private var analysisProgressTitle: String {
        let status = viewModel.analysisService.statusMessage.lowercased()
        if status.contains("upload") {
            return languageStore.text(.uploading)
        }
        if status.contains("queued") {
            return languageStore.text(.queued)
        }
        if status.contains("device") {
            return languageStore.text(.analyzing)
        }
        if status.contains("local analysis") {
            return languageStore.text(.analyzing)
        }
        if status.contains("finalizing") {
            return languageStore.text(.finalizing)
        }
        if status.contains("refining") {
            return languageStore.text(.refining)
        }
        return languageStore.text(.analyzing)
    }

    private var requiresProForCurrentVideo: Bool {
        !subscriptionManager.isProUser && viewModel.videoDuration > AppConstants.nonProMaxAnalysisDuration
    }

    private var analysisButtonSubtitle: String {
        if requiresProForCurrentVideo {
            return "\(languageStore.text(.analysisButtonUpgradePrefix)) \(formatDuration(AppConstants.nonProMaxAnalysisDuration))"
        }
        if viewModel.isCloudTeamScanInProgress {
            return viewModel.cloudTeamScanStatusMessage ?? "Scanning teams first"
        }
        if viewModel.requiresHighlightTeamSelectionConfirmation {
            return "Choose a team or All teams first"
        }
        return languageStore.text(.analysisButtonSubtitle)
    }

    private var analysisSectionSubtitle: String {
        languageStore.text(.aiAnalysisSubtitle)
    }

    private func announceAnalysisProgress(_ progress: Double) {
        guard viewModel.analysisService.isAnalyzing else {
            lastAnalysisAnnouncementPercent = -1
            return
        }

        let percent = Int((progress * 100).rounded())
        let bucket = (percent / 25) * 25
        guard bucket >= 25, bucket <= 100, bucket != lastAnalysisAnnouncementPercent else { return }
        lastAnalysisAnnouncementPercent = bucket
        HoopsAccessibility.announce("Analysis \(bucket) percent complete.")
    }
}

private struct ImportedVideoFile: Transferable {
    let url: URL

    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(contentType: .video) { video in
            SentTransferredFile(video.url)
        } importing: { received in
            try copyImportedVideo(from: received.file)
        }

        FileRepresentation(contentType: .movie) { video in
            SentTransferredFile(video.url)
        } importing: { received in
            try copyImportedVideo(from: received.file)
        }

        FileRepresentation(contentType: .mpeg4Movie) { video in
            SentTransferredFile(video.url)
        } importing: { received in
            try copyImportedVideo(from: received.file)
        }

        FileRepresentation(contentType: .quickTimeMovie) { video in
            SentTransferredFile(video.url)
        } importing: { received in
            try copyImportedVideo(from: received.file)
        }
    }

    private static func copyImportedVideo(from sourceURL: URL) throws -> ImportedVideoFile {
        let fileExtension = sourceURL.pathExtension.isEmpty ? "mov" : sourceURL.pathExtension
        let tempURL = URL.temporaryDirectory.appending(path: "imported_video_\(UUID().uuidString).\(fileExtension)")
        try FileManager.default.copyItem(at: sourceURL, to: tempURL)
        return ImportedVideoFile(url: tempURL)
    }
}
