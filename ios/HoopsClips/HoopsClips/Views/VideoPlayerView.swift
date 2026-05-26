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
                } else {
                    HoopsAccessibility.announce("Video imported. Choose a target highlight length, then start analysis.")
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

                if let importedVideo = try await item.loadTransferable(type: ImportedVideoFile.self) {
                    try Task.checkCancellation()
                    return await viewModel.loadVideo(url: importedVideo.url)
                }

                if let data = try await item.loadTransferable(type: Data.self) {
                    try Task.checkCancellation()
                    let tempURL = URL.temporaryDirectory.appending(path: "imported_video_\(UUID().uuidString).mov")
                    try data.write(to: tempURL, options: .atomic)
                    try Task.checkCancellation()
                    return await viewModel.loadVideo(url: tempURL)
                }

                importErrorMessage = "Hoopclips could not access that video from Photos. Try saving it to Files and importing from there."
                return false
            } catch is CancellationError {
                return false
            } catch {
                importErrorMessage = "Hoopclips could not import that video: \(error.localizedDescription)"
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

        let task = Task { @MainActor in
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

            guard activeImportID == importID else { return }

            clearImportState()
            if importErrorMessage == nil && (!didLoadVideo || !viewModel.isVideoLoaded) {
                importErrorMessage = "Hoopclips could not read that video. Try importing it from Files or choose another clip."
            }
        }

        importTask = task
    }

    private func cancelActiveImport() {
        importTask?.cancel()
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
                .sensoryFeedback(.impact(weight: .medium), trigger: analysisStarted)

                if AppConstants.requiresCloudVideoPipeline {
                    cloudAnalysisPathView
                } else {
                    estimatedTimeView
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
                    Text("Cloud AI targets this team and keeps uncertain clips for Review.")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(2)
                }

                Spacer(minLength: 0)
            }

            HStack(spacing: 8) {
                ForEach(HighlightTeamSelection.defaultChoices, id: \.selectionKey) { selection in
                    teamTargetButton(selection)
                }
            }
        }
        .padding(14)
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
        let icon = selection.mode == .all ? "person.3.fill" : "circle.lefthalf.filled"

        return Button {
            HoopsAccessibility.animate(reduceMotion: reduceMotion, .snappy(duration: 0.18)) {
                viewModel.settings.highlightTeamSelection = selection
            }
        } label: {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.caption.weight(.bold))
                Text(selection.displayTitle)
                    .font(.caption.weight(.semibold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)
            }
            .foregroundStyle(isSelected ? AppTheme.darkBg : AppTheme.neonPurple)
            .frame(maxWidth: .infinity, minHeight: 48)
            .padding(.horizontal, 6)
            .background(
                isSelected ? AppTheme.neonPurple : AppTheme.neonPurple.opacity(0.10),
                in: .rect(cornerRadius: 12)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(AppTheme.neonPurple.opacity(isSelected ? 0 : 0.28), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Target \(selection.displayTitle)")
        .accessibilityValue(isSelected ? "Selected" : "Not selected")
        .accessibilityHint(selection.displaySubtitle)
        .hoopsSelectedState(isSelected)
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

    private var estimatedTimeView: some View {
        HStack(spacing: 8) {
            Image(systemName: "timer")
                .foregroundStyle(AppTheme.subtleText)
            let estimatedSeconds = Int(max(viewModel.videoDuration * 0.42, 12))
            Text("\(languageStore.text(.estimated)): ~\(estimatedSeconds)s \(languageStore.text(.analysis))")
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .rorkCard(cornerRadius: 12, fill: AnyShapeStyle(AppTheme.surfaceBg.opacity(0.65)), stroke: AppTheme.softBorder, glowOpacity: 0.03)
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
        FileRepresentation(contentType: .movie) { video in
            SentTransferredFile(video.url)
        } importing: { received in
            let sourceURL = received.file
            let fileExtension = sourceURL.pathExtension.isEmpty ? "mov" : sourceURL.pathExtension
            let tempURL = URL.temporaryDirectory.appending(path: "imported_video_\(UUID().uuidString).\(fileExtension)")
            try FileManager.default.copyItem(at: sourceURL, to: tempURL)
            return ImportedVideoFile(url: tempURL)
        }
    }
}
