import SwiftUI
import AVKit
import PhotosUI
import UniformTypeIdentifiers
import UIKit

struct VideoPlayerView: View {
    @Bindable var viewModel: HighlightsViewModel
    var onOpenHistory: () -> Void = {}
    @Environment(SubscriptionManager.self) private var subscriptionManager
    @Environment(AuthService.self) private var authService
    @Environment(AppLanguageStore.self) private var languageStore
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @Environment(\.scenePhase) private var scenePhase
    @AppStorage("hoops.cloudVideoConsentAccepted.v1") private var cloudVideoConsentAccepted = false
    @State private var player: AVPlayer?
    @State private var showingFilePicker = false
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var showSourcePicker = false
    @State private var analysisStarted = false
    @State private var showingPaywall = false
    @State private var showingNoClipsAlert = false
    @State private var showingDurationLimitAlert = false
    @State private var isImportingVideo = false
    @State private var importStatusMessage = ""
    @State private var activeImportID: UUID?
    @State private var importTask: Task<Void, Never>?
    @State private var teamScanTask: Task<Void, Never>?
    @State private var importBackgroundTaskID: UIBackgroundTaskIdentifier = .invalid
    @State private var importErrorMessage: String?
    @State private var importRecoveryOffersHistory = false
    @State private var lastAnalysisAnnouncementPercent = -1
    @State private var showingCloudVideoConsent = false
    @State private var pendingCloudVideoConsentAction: CloudVideoConsentAction?

    private let videoImportReminderNanoseconds: UInt64 = 8 * 1_000_000_000
    private let videoImportLongRunningReminderNanoseconds: UInt64 = 45 * 1_000_000_000
    private let videoImportTimeoutNanoseconds: UInt64 = 5 * 60 * 1_000_000_000
    private let videoImportCompletionGraceNanoseconds: UInt64 = 2 * 1_000_000_000
    private let videoImportRecoveryPollNanoseconds: UInt64 = 2 * 1_000_000_000

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
            .fileImporter(isPresented: $showingFilePicker, allowedContentTypes: VideoImportPolicy.supportedContentTypes) { result in
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
                completeImportAfterLoadedVideo()
            }
            .onChange(of: viewModel.videoURL) { _, newValue in
                syncPlayer(with: newValue)
                if newValue != nil {
                    recoverCompletedImportIfNeeded()
                }
            }
            .onChange(of: viewModel.isVideoLoaded) { _, isVideoLoaded in
                if !isVideoLoaded {
                    analysisStarted = false
                    lastAnalysisAnnouncementPercent = -1
                    teamScanTask?.cancel()
                    teamScanTask = nil
                } else {
                    completeImportAfterLoadedVideo()
                    HoopsAccessibility.announce("Video imported. Choose a target reel length, then start analysis.")
                    startTeamScanIfNeeded()
                }
            }
            .onChange(of: viewModel.currentProjectID) { _, _ in
                recoverCompletedImportIfNeeded()
            }
            .onChange(of: scenePhase) { _, phase in
                guard phase == .active else { return }
                recoverCompletedImportIfNeeded()
            }
            .onChange(of: isImportingVideo) { _, isImporting in
                HoopsAccessibility.announce(isImporting ? currentImportStatusMessage : "Video import finished.")
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
            .sheet(isPresented: $showingCloudVideoConsent) {
                CloudVideoConsentSheet(
                    primaryActionTitle: cloudConsentPrimaryActionTitle,
                    onAccept: acceptCloudVideoConsent,
                    onCancel: cancelCloudVideoConsent
                )
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
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
            .alert(importAlertTitle, isPresented: Binding(
                get: { importErrorMessage != nil },
                set: { if !$0 { clearImportError() } }
            )) {
                if importRecoveryOffersHistory {
                    Button("Open History") {
                        LaunchTelemetry.shared.recordStabilityCheckpoint("video_import.open_history_from_alert")
                        clearImportError()
                        onOpenHistory()
                    }
                }
                Button("OK", role: .cancel) {
                    clearImportError()
                }
            } message: {
                Text(importErrorMessage ?? "Choose another video and try again.")
            }
        }
    }

    private func importVideo(from url: URL) {
        beginVideoImport(source: "files") {
            guard await preflightVideoImport(url: url, source: "files") != nil else {
                return false
            }
            await updateImportStatus(for: .copyingSource)
            let didLoadVideo = await viewModel.loadVideo(url: url) { phase in
                await updateImportStatus(for: phase)
            }
            if didLoadVideo {
                await MainActor.run {
                    completeImportAfterLoadedVideo()
                }
            }
            return didLoadVideo
        }
    }

    private func importVideo(from item: PhotosPickerItem) {
        beginVideoImport(source: "photos") {
            do {
                try Task.checkCancellation()

                await MainActor.run {
                    importStatusMessage = "Reading video from Photos..."
                }
                guard let importedVideo = try await VideoImportTransfer.loadFileBackedVideo(from: item) else {
                    await MainActor.run {
                        importErrorMessage = "HoopClips could not access a local video file from Photos. Save it to Files and import from there, or choose a shorter downloaded clip."
                    }
                    LaunchTelemetry.shared.recordStabilityCheckpoint(
                        "video_import.file_access_failed",
                        metadata: "source=photos"
                    )
                    return false
                }
                defer {
                    VideoImportTransfer.scheduleTemporaryFileRemoval(at: importedVideo.url)
                }

                try Task.checkCancellation()
                guard await preflightVideoImport(url: importedVideo.url, source: "photos") != nil else {
                    return false
                }

                try Task.checkCancellation()
                await updateImportStatus(for: .copyingSource)
                let didLoadVideo = await viewModel.loadVideo(url: importedVideo.url) { phase in
                    await updateImportStatus(for: phase)
                }
                if didLoadVideo {
                    await MainActor.run {
                        completeImportAfterLoadedVideo()
                    }
                }
                return didLoadVideo
            } catch is CancellationError {
                LaunchTelemetry.shared.recordStabilityCheckpoint(
                    "video_import.cancelled",
                    metadata: "source=photos"
                )
                return false
            } catch {
                await MainActor.run {
                    importErrorMessage = "HoopClips could not import that video: \(error.localizedDescription)"
                }
                LaunchTelemetry.shared.recordStabilityCheckpoint(
                    "video_import.failed",
                    metadata: "source=photos reason=\(error.localizedDescription)"
                )
                return false
            }
        }
    }

    private func beginVideoImport(source: String, _ operation: @escaping () async -> Bool) {
        guard !isImportingVideo else { return }
        importTask?.cancel()

        let importID = UUID()
        activeImportID = importID
        isImportingVideo = true
        importStatusMessage = languageStore.text(.preparingVideo)
        clearImportError()
        beginImportBackgroundTask(source: source)
        LaunchTelemetry.shared.recordStabilityCheckpoint(
            "video_import.started",
            metadata: "source=\(source)"
        )

        let task = Task {
            let importRecoveryTask = Task {
                while !Task.isCancelled {
                    do {
                        try await Task.sleep(nanoseconds: videoImportRecoveryPollNanoseconds)
                    } catch {
                        return
                    }

                    let recovered = await MainActor.run {
                        guard activeImportID == importID, isImportingVideo else { return false }
                        return recoverSuccessfulImportIfNeeded(source: source, phase: "poll")
                    }
                    if recovered {
                        return
                    }
                }
            }

            let importWatchdogTask = Task {
                do {
                    try await Task.sleep(nanoseconds: videoImportReminderNanoseconds)
                } catch {
                    return
                }

                await MainActor.run {
                    guard activeImportID == importID, isImportingVideo else { return }
                    if recoverSuccessfulImportIfNeeded(source: source, phase: "slow_reminder") {
                        return
                    }
                    LaunchTelemetry.shared.recordStabilityCheckpoint(
                        "video_import.slow",
                        metadata: "source=\(source)"
                    )
                    importRecoveryOffersHistory = true
                    importStatusMessage = "Still copying the video. If it already finished, check History."
                }

                do {
                    try await Task.sleep(nanoseconds: videoImportLongRunningReminderNanoseconds - videoImportReminderNanoseconds)
                } catch {
                    return
                }

                await MainActor.run {
                    guard activeImportID == importID, isImportingVideo else { return }
                    if recoverSuccessfulImportIfNeeded(source: source, phase: "long_running_reminder") {
                        return
                    }
                    LaunchTelemetry.shared.recordStabilityCheckpoint(
                        "video_import.long_running",
                        metadata: "source=\(source)"
                    )
                    importRecoveryOffersHistory = true
                    importStatusMessage = "Still saving the project. If it already finished, HoopClips will open it or show it in History."
                }

                do {
                    try await Task.sleep(nanoseconds: videoImportTimeoutNanoseconds - videoImportLongRunningReminderNanoseconds)
                } catch {
                    return
                }

                await MainActor.run {
                    guard activeImportID == importID, isImportingVideo else { return }
                    if recoverSuccessfulImportIfNeeded(source: source, phase: "timeout") {
                        return
                    }
                    LaunchTelemetry.shared.recordStabilityCheckpoint(
                        "video_import.timeout",
                        metadata: "source=\(source)"
                    )
                    showImportRecoveryError(
                        "HoopClips is still waiting for that video. It may already be saved in History."
                    )
                    importTask?.cancel()
                    clearImportState()
                }
            }

            let didLoadVideo = await operation()
            importRecoveryTask.cancel()
            importWatchdogTask.cancel()
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                didLoadVideo ? "video_import.loaded" : "video_import.not_loaded",
                metadata: "source=\(source)"
            )

            await MainActor.run {
                finishVideoImport(importID: importID, didLoadVideo: didLoadVideo, source: source)
            }
        }

        importTask = task
    }

    private func preflightVideoImport(url: URL, source: String) async -> VideoImportPreflightSummary? {
        await MainActor.run {
            importStatusMessage = "Checking video details..."
        }

        do {
            let summary = try await VideoImportPolicy.preflight(url: url)
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "video_import.preflight_passed",
                metadata: summary.telemetryMetadata(source: source)
            )
            await MainActor.run {
                importStatusMessage = "Video checked. Saving to HoopClips..."
            }
            return summary
        } catch let error as VideoImportPreflightError {
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "video_import.preflight_failed",
                metadata: "source=\(source) code=\(error.code)"
            )
            await MainActor.run {
                importErrorMessage = error.userFacingMessage
            }
            return nil
        } catch {
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "video_import.preflight_failed",
                metadata: "source=\(source) code=metadata_unreadable"
            )
            await MainActor.run {
                importErrorMessage = "HoopClips could not read that video's details. Try saving it to Files or exporting a fresh copy from Photos."
            }
            return nil
        }
    }

    private func updateImportStatus(for phase: ProjectImportPhase) async {
        await MainActor.run {
            importStatusMessage = phase.importStatusMessage
        }
    }

    private func beginImportBackgroundTask(source: String) {
        guard importBackgroundTaskID == .invalid else { return }
        importBackgroundTaskID = UIApplication.shared.beginBackgroundTask(withName: "HoopsVideoImport") {
            Task { @MainActor in
                LaunchTelemetry.shared.recordStabilityCheckpoint(
                    "video_import.background_time_expired",
                    metadata: "source=\(source)"
                )
                cancelActiveImport()
            }
        }
    }

    private func endImportBackgroundTask() {
        guard importBackgroundTaskID != .invalid else { return }
        UIApplication.shared.endBackgroundTask(importBackgroundTaskID)
        importBackgroundTaskID = .invalid
    }

    private func finishVideoImport(importID: UUID, didLoadVideo: Bool, source: String) {
        guard activeImportID == importID || viewModel.isVideoLoaded || didLoadVideo else { return }

        if didLoadVideo {
            if recoverSuccessfulImportIfNeeded(source: source, phase: "operation_loaded") {
                return
            }
            importStatusMessage = "Opening project..."
            Task { @MainActor in
                do {
                    try await Task.sleep(nanoseconds: videoImportCompletionGraceNanoseconds)
                } catch {
                    return
                }

                guard activeImportID == importID || isImportingVideo else { return }
                if recoverSuccessfulImportIfNeeded(source: source, phase: "completion_grace") {
                    return
                }

                LaunchTelemetry.shared.recordStabilityCheckpoint(
                    "video_import.loaded_but_not_visible",
                    metadata: "source=\(source)"
                )
                clearImportState()
                showImportRecoveryError(
                    "HoopClips saved the video, but this screen could not open it yet. Open it from History."
                )
            }
            return
        }

        if recoverSuccessfulImportIfNeeded(source: source, phase: "operation_not_loaded") {
            return
        }

        clearImportState()
        if importErrorMessage == nil {
            importErrorMessage = "HoopClips could not read that video. Try importing it from Files or choose another clip."
        }
    }

    private var importAlertTitle: String {
        importRecoveryOffersHistory ? "Check History" : "Video Import Failed"
    }

    private func showImportRecoveryError(_ message: String) {
        importRecoveryOffersHistory = true
        importErrorMessage = message
    }

    private func clearImportError() {
        importErrorMessage = nil
        importRecoveryOffersHistory = false
    }

    private func openHistoryFromImportRecovery() {
        LaunchTelemetry.shared.recordStabilityCheckpoint("video_import.open_history_from_status")
        _ = recoverSuccessfulImportIfNeeded(source: "import_status", phase: "history_shortcut")
        clearImportError()
        onOpenHistory()
    }

    private func completeImportAfterLoadedVideo() {
        guard viewModel.reconcileCurrentProjectLoadState() else { return }
        syncPlayer(with: viewModel.videoURL)
        clearImportError()
        if isImportingVideo || activeImportID != nil || importTask != nil {
            clearImportState()
        }
    }

    private func recoverCompletedImportIfNeeded() {
        guard viewModel.reconcileCurrentProjectLoadState() else { return }
        completeImportAfterLoadedVideo()
        startTeamScanIfNeeded()
    }

    private func recoverSuccessfulImportIfNeeded(source: String, phase: String = "visible") -> Bool {
        if viewModel.reconcileCurrentProjectLoadState() {
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "video_import.visible",
                metadata: "source=\(source) phase=\(phase)"
            )
            syncPlayer(with: viewModel.videoURL)
            completeImportAfterLoadedVideo()
            startTeamScanIfNeeded()
            return true
        }
        return false
    }

    private func startTeamScanIfNeeded() {
        guard AppConstants.cloudAnalysisEnabled else { return }
        guard viewModel.isVideoLoaded, viewModel.clips.isEmpty else { return }
        guard viewModel.cloudDetectedTeams.isEmpty else { return }
        guard teamScanTask == nil else { return }
        guard cloudVideoConsentAccepted else {
            requestCloudVideoConsent(for: .teamScan)
            return
        }

        teamScanTask = Task { @MainActor in
            await viewModel.scanTeamsBeforeAnalysis()
            teamScanTask = nil
        }
    }

    private func startAnalysisFromButton() {
        guard !requiresProForCurrentVideo else {
            showingDurationLimitAlert = true
            return
        }
        guard !viewModel.isCloudTeamScanInProgress else { return }
        guard !viewModel.requiresHighlightTeamSelectionConfirmation else {
            HoopsAccessibility.announce("Choose a highlight team or All teams before analysis.")
            return
        }
        guard !AppConstants.cloudAnalysisEnabled || cloudVideoConsentAccepted else {
            requestCloudVideoConsent(for: .startAnalysis)
            return
        }

        analysisStarted = true
        Task {
            await viewModel.startAnalysis()
            if viewModel.clips.isEmpty {
                showingNoClipsAlert = true
            }
        }
    }

    private func requestCloudVideoConsent(for action: CloudVideoConsentAction) {
        pendingCloudVideoConsentAction = action
        showingCloudVideoConsent = true
    }

    private var cloudConsentPrimaryActionTitle: String {
        switch pendingCloudVideoConsentAction {
        case .startAnalysis:
            return "I Agree, Start Analysis"
        case .teamScan, nil:
            return "I Agree, Scan Teams"
        }
    }

    private func acceptCloudVideoConsent() {
        cloudVideoConsentAccepted = true
        showingCloudVideoConsent = false
        let action = pendingCloudVideoConsentAction
        pendingCloudVideoConsentAction = nil

        switch action {
        case .startAnalysis:
            startAnalysisFromButton()
        case .teamScan, nil:
            startTeamScanIfNeeded()
        }
    }

    private func cancelCloudVideoConsent() {
        pendingCloudVideoConsentAction = nil
        showingCloudVideoConsent = false
    }

    private func cancelActiveImport() {
        importTask?.cancel()
        teamScanTask?.cancel()
        teamScanTask = nil
        LaunchTelemetry.shared.recordStabilityCheckpoint("video_import.cancel_requested")
        clearImportState()
    }

    private func clearImportState() {
        isImportingVideo = false
        importStatusMessage = ""
        activeImportID = nil
        importTask = nil
        endImportBackgroundTask()
    }

    private var currentImportStatusMessage: String {
        importStatusMessage.isEmpty ? languageStore.text(.preparingVideo) : importStatusMessage
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
        clearImportError()
    }

    private var importSection: some View {
        VStack(spacing: 32) {
            Spacer().frame(height: 40)

            HoopsMotionHero()

            VStack(spacing: 12) {
                Text(languageStore.text(.turnGamesTitle))
                    .font(.title2.bold())
                    .foregroundStyle(.white)
                    .multilineTextAlignment(.center)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                    .minimumScaleFactor(0.86)
                    .fixedSize(horizontal: false, vertical: true)

                Text(languageStore.text(.turnGamesSubtitle))
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.subtleText)
                    .multilineTextAlignment(.center)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                    .minimumScaleFactor(0.84)
                    .fixedSize(horizontal: false, vertical: true)
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
                    Text(isImportingVideo ? currentImportStatusMessage : languageStore.text(.selectVideo))
                        .font(.headline)
                        .multilineTextAlignment(.center)
                        .lineLimit(3)
                        .minimumScaleFactor(0.88)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .padding(.horizontal, 14)
                .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 16))
            }
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(AppTheme.neonPurple.opacity(0.25), lineWidth: 1)
            )
            .disabled(isImportingVideo)
            .opacity(isImportingVideo ? 0.82 : 1)
            .accessibilityLabel(isImportingVideo ? currentImportStatusMessage : languageStore.text(.selectVideo))
            .accessibilityHint("Opens choices for importing a basketball video from Photos or Files.")
            .accessibilityValue(isImportingVideo ? currentImportStatusMessage : "Ready")

            if isImportingVideo {
                importStatusCard
            }

            LazyVGrid(columns: importFeatureGridColumns, alignment: .leading, spacing: 12) {
                featurePill(icon: "sparkles", text: languageStore.text(.smartHighlights))
                featurePill(icon: "bolt.fill", text: languageStore.text(.fastReels))
                featurePill(icon: "film.stack.fill", text: languageStore.text(.autoTrim))
                featurePill(icon: "basketball.fill", text: languageStore.text(.getExposure))
            }
        }
        .padding(18)
        .rorkCard(cornerRadius: 22, stroke: AppTheme.softBorder, glowOpacity: 0.18)
    }

    private var importStatusCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 10) {
                ProgressView()
                    .tint(AppTheme.neonPurple)
                    .padding(.top, 2)
                    .accessibilityHidden(true)

                VStack(alignment: .leading, spacing: 4) {
                    Text(currentImportStatusMessage)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 3)
                        .minimumScaleFactor(0.86)
                        .fixedSize(horizontal: false, vertical: true)

                    Text("Keep HoopClips open while the local copy finishes. If iOS completes it in the background, the project will show in History.")
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                        .minimumScaleFactor(0.84)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .layoutPriority(1)
            }

            LazyVGrid(columns: importStatusActionGridColumns, spacing: 8) {
                if importRecoveryOffersHistory {
                    Button {
                        openHistoryFromImportRecovery()
                    } label: {
                        importStatusActionLabel(
                            title: "Check History",
                            icon: "clock.arrow.circlepath",
                            foreground: AppTheme.warningYellow,
                            fill: AppTheme.warningYellow.opacity(0.12),
                            stroke: AppTheme.warningYellow.opacity(0.24)
                        )
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Check History")
                    .accessibilityHint("Opens History in case the video was already saved there.")
                    .accessibilityIdentifier("import.status.checkHistoryButton")
                }

                Button {
                    cancelActiveImport()
                } label: {
                    importStatusActionLabel(
                        title: languageStore.text(.cancelImport),
                        icon: "xmark.circle.fill",
                        foreground: AppTheme.subtleText,
                        fill: AppTheme.cardBg.opacity(0.72),
                        stroke: AppTheme.softBorder
                    )
                }
                .buttonStyle(.plain)
                .accessibilityLabel(languageStore.text(.cancelImport))
                .accessibilityValue(currentImportStatusMessage)
                .accessibilityHint("Stops the current video import and returns to the import screen.")
                .accessibilityIdentifier("import.status.cancelButton")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(AppTheme.surfaceBg.opacity(0.72), in: .rect(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(AppTheme.softBorder, lineWidth: 1)
        )
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("import.status.card")
    }

    private var importStatusActionGridColumns: [GridItem] {
        [
            GridItem(.adaptive(minimum: dynamicTypeSize.isAccessibilitySize ? 164 : 128), spacing: 8, alignment: .top)
        ]
    }

    private func importStatusActionLabel(
        title: String,
        icon: String,
        foreground: Color,
        fill: Color,
        stroke: Color
    ) -> some View {
        Label(title, systemImage: icon)
            .font(.footnote.weight(.semibold))
            .foregroundStyle(foreground)
            .multilineTextAlignment(.center)
            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
            .minimumScaleFactor(0.86)
            .fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 52 : 42)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(fill, in: .rect(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(stroke, lineWidth: 1)
            )
    }

    private var importFeatureGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize >= .accessibility1 ? 176 : 136
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 260), spacing: 12, alignment: .top)
        ]
    }

    private func featurePill(icon: String, text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
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
                .lineLimit(2)
                .minimumScaleFactor(0.86)
                .fixedSize(horizontal: false, vertical: true)

            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, minHeight: dynamicTypeSize >= .accessibility1 ? 62 : 52, alignment: .leading)
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
                        .padding(.top, 1)
                    Text(url.lastPathComponent)
                        .font(.caption.monospaced())
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(2)
                        .minimumScaleFactor(0.82)
                        .fixedSize(horizontal: false, vertical: true)
                        .layoutPriority(1)
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
                            .padding(.top, 1)
                        Text(analysisBannerText)
                            .font(.caption.weight(.medium))
                            .foregroundStyle(AppTheme.warningYellow)
                            .lineLimit(3)
                            .minimumScaleFactor(0.84)
                            .fixedSize(horizontal: false, vertical: true)
                            .layoutPriority(1)
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
                    startAnalysisFromButton()
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: "brain.head.profile.fill")
                            .font(.title3)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(languageStore.text(.analyzeWithAI))
                                .font(.headline)
                                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                                .minimumScaleFactor(0.84)
                                .fixedSize(horizontal: false, vertical: true)
                            Text(analysisButtonSubtitle)
                                .font(.caption)
                                .foregroundStyle(.white.opacity(0.86))
                                .lineLimit(2)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .layoutPriority(1)
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
            HStack(alignment: .top, spacing: 10) {
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
                        .lineLimit(4)
                        .minimumScaleFactor(0.9)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 0)
            }

            teamScanStatusRow

            LazyVGrid(columns: teamTargetGridColumns, alignment: .leading, spacing: 8) {
                ForEach(viewModel.availableHighlightTeamChoices, id: \.selectionKey) { selection in
                    teamTargetButton(selection)
                }
            }

            if viewModel.settings.highlightTeamSelection.mode == .team {
                selectedTeamNameField
            } else if viewModel.requiresHighlightTeamSelectionConfirmation {
                Label("Not sure? Use All teams and check plays in Review.", systemImage: "questionmark.circle.fill")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(AppTheme.subtleText)
                    .fixedSize(horizontal: false, vertical: true)
            }

            opponentTeamNameField
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

    private var teamTargetGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize >= .accessibility1 ? 220 : 150
        let maximumWidth: CGFloat = dynamicTypeSize >= .accessibility1 ? 360 : 280
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: maximumWidth), spacing: 8, alignment: .top)
        ]
    }

    private func teamTargetButton(_ selection: HighlightTeamSelection) -> some View {
        let isSelected = viewModel.settings.highlightTeamSelection.selectionKey == selection.selectionKey
        let isConfirmedSelection = isSelected && !viewModel.requiresHighlightTeamSelectionConfirmation

        return Button {
            HoopsAccessibility.animate(reduceMotion: reduceMotion, .snappy(duration: 0.18)) {
                viewModel.confirmHighlightTeamSelection(selection)
            }
        } label: {
            VStack(spacing: dynamicTypeSize.isAccessibilitySize ? 8 : 6) {
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
                    .multilineTextAlignment(.center)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 3)
                    .minimumScaleFactor(0.82)
                    .fixedSize(horizontal: false, vertical: true)
                    .layoutPriority(1)
                    .accessibilityIdentifier(selection.accessibilityIdentifier)
            }
            .foregroundStyle(isConfirmedSelection ? AppTheme.darkBg : AppTheme.neonPurple)
            .frame(maxWidth: .infinity, minHeight: dynamicTypeSize >= .accessibility1 ? 92 : 72)
            .padding(.horizontal, 8)
            .padding(.vertical, 8)
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

    private var selectedTeamNameField: some View {
        teamSetupTextField(
            icon: "pencil",
            placeholder: "Team name (optional)",
            value: Binding(
                get: { viewModel.selectedHighlightTeamNameDraft },
                set: { viewModel.renameSelectedHighlightTeam($0) }
            ),
            accessibilityIdentifier: "analysis.teamTarget.nameField"
        )
    }

    private var opponentTeamNameField: some View {
        teamSetupTextField(
            icon: "person.crop.circle.badge.questionmark",
            placeholder: "Opponent name (optional)",
            value: Binding(
                get: { viewModel.opponentTeamNameDraft },
                set: { viewModel.renameOpponentTeam($0) }
            ),
            accessibilityIdentifier: "analysis.teamTarget.opponentNameField"
        )
    }

    private func teamSetupTextField(
        icon: String,
        placeholder: String,
        value: Binding<String>,
        accessibilityIdentifier: String
    ) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.neonPurple)
                .frame(width: 22)

            TextField(
                placeholder,
                text: value
            )
            .font(.caption.weight(.medium))
            .foregroundStyle(.white)
            .textInputAutocapitalization(.words)
            .submitLabel(.done)
            .accessibilityIdentifier(accessibilityIdentifier)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(AppTheme.surfaceBg.opacity(0.72), in: .rect(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(AppTheme.neonPurple.opacity(0.18), lineWidth: 1)
        )
        .accessibilityElement(children: .contain)
    }

    private var teamTargetSubtitle: String {
        if viewModel.isCloudTeamScanInProgress {
            return viewModel.cloudTeamScanStatusMessage ?? "Scanning jersey colors before analysis."
        }
        if viewModel.requiresHighlightTeamSelectionConfirmation {
            return "Pick your team, rename it if helpful, or use All teams."
        }
        if !viewModel.cloudDetectedTeams.isEmpty {
            return "HoopClips keeps uncertain plays in Review so you can decide."
        }
        return cloudVideoConsentAccepted
            ? "Team targeting unlocks after the cloud scan finds jersey colors."
            : "First scan asks before uploading video to the HoopClips cloud."
    }

    private var teamScanStatusRow: some View {
        HStack(alignment: .top, spacing: 8) {
            if viewModel.isCloudTeamScanInProgress {
                ProgressView()
                    .tint(AppTheme.neonPurple)
                    .controlSize(.small)
                Text(viewModel.cloudTeamScanStatusMessage ?? "Scanning teams")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(AppTheme.neonPurple)
                    .fixedSize(horizontal: false, vertical: true)
            } else if !viewModel.cloudDetectedTeams.isEmpty {
                Image(systemName: viewModel.requiresHighlightTeamSelectionConfirmation ? "hand.tap.fill" : "checkmark.seal.fill")
                    .font(.caption)
                    .padding(.top, 1)
                    .foregroundStyle(viewModel.requiresHighlightTeamSelectionConfirmation ? AppTheme.warningYellow : AppTheme.successGreen)
                Text(teamScanDetectedStatusText)
                    .font(.caption.weight(.medium))
                    .foregroundStyle(viewModel.requiresHighlightTeamSelectionConfirmation ? AppTheme.warningYellow : AppTheme.successGreen)
                    .lineLimit(3)
                    .fixedSize(horizontal: false, vertical: true)
            } else if viewModel.cloudTeamScanErrorMessage != nil {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.caption)
                    .padding(.top, 1)
                    .foregroundStyle(AppTheme.warningYellow)
                Text("Team scan unavailable")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(AppTheme.warningYellow)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
                Button("Retry") {
                    startTeamScanIfNeeded()
                }
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.neonPurple)
            } else {
                Image(systemName: "sparkles")
                    .font(.caption)
                    .padding(.top, 1)
                    .foregroundStyle(AppTheme.subtleText)
                Text("All teams is available until jersey colors are detected")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(AppTheme.subtleText)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
        }
        .frame(minHeight: 20)
        .accessibilityIdentifier("analysis.teamTarget.status")
        .accessibilityElement(children: .combine)
    }

    private var teamScanDetectedStatusText: String {
        if viewModel.requiresHighlightTeamSelectionConfirmation {
            return "Choose target team or All teams"
        }
        let labels = viewModel.cloudDetectedTeams.map(\.label)
        if labels.count > 2 {
            return "\(labels.count) teams found. Choose one or All teams."
        }
        return labels.joined(separator: " vs ")
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
            targetHighlightLengthHeader

            LazyVGrid(columns: targetDurationGridColumns, spacing: 8) {
                ForEach([30.0, 60.0, 90.0, 180.0, 270.0], id: \.self) { preset in
                    targetDurationPresetButton(preset)
                }
            }

            Slider(value: $viewModel.settings.targetHighlightDuration, in: 15.0...270.0, step: 5.0)
                .tint(AppTheme.warningYellow)
                .accessibilityLabel(languageStore.text(.settingsTargetHighlight))
                .accessibilityValue(formattedTargetDuration(viewModel.settings.targetHighlightDuration))
                .accessibilityHint("Sets the target reel length before analysis.")
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

    private var targetHighlightLengthHeader: some View {
        ViewThatFits(in: .horizontal) {
            targetHighlightLengthHeaderContent(placesValueInline: true)
            targetHighlightLengthHeaderContent(placesValueInline: false)
        }
    }

    private func targetHighlightLengthHeaderContent(placesValueInline: Bool) -> some View {
        HStack(alignment: .top, spacing: 10) {
            ZStack {
                Circle()
                    .fill(AppTheme.warningYellow.opacity(0.14))
                    .frame(width: 34, height: 34)
                Image(systemName: "timer.circle.fill")
                    .font(.headline)
                    .foregroundStyle(AppTheme.warningYellow)
            }
            .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: placesValueInline ? 2 : 8) {
                Text(languageStore.text(.settingsTargetHighlight))
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                    .lineLimit(2)
                    .minimumScaleFactor(0.9)
                    .fixedSize(horizontal: false, vertical: true)
                Text(languageStore.text(.settingsTargetHighlightHelp))
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
                    .fixedSize(horizontal: false, vertical: true)

                if !placesValueInline {
                    targetDurationBadge
                }
            }

            if placesValueInline {
                Spacer(minLength: 8)
                targetDurationBadge
            }
        }
    }

    private var targetDurationBadge: some View {
        Text(formattedTargetDuration(viewModel.settings.targetHighlightDuration))
            .font(.subheadline.weight(.bold).monospacedDigit())
            .foregroundStyle(AppTheme.warningYellow)
            .lineLimit(1)
            .minimumScaleFactor(0.82)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(AppTheme.warningYellow.opacity(0.12), in: .capsule)
            .accessibilityLabel("Target length \(formattedTargetDuration(viewModel.settings.targetHighlightDuration))")
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
                .lineLimit(1)
                .minimumScaleFactor(0.82)
                .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 54 : 42)
                .padding(.horizontal, 8)
                .background(
                    isSelected ? AppTheme.warningYellow : AppTheme.warningYellow.opacity(0.10),
                    in: .rect(cornerRadius: 12)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(AppTheme.warningYellow.opacity(isSelected ? 0 : 0.28), lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Set target reel length to \(formattedTargetDuration(duration))")
        .accessibilityValue(isSelected ? "Selected" : "Not selected")
        .hoopsSelectedState(isSelected)
    }

    private var targetDurationGridColumns: [GridItem] {
        [
            GridItem(.adaptive(minimum: dynamicTypeSize.isAccessibilitySize ? 116 : 88, maximum: 136), spacing: 8, alignment: .top)
        ]
    }

    private var analysisProgressView: some View {
        VStack(spacing: 16) {
            analysisProgressHeader

            ProgressView(value: viewModel.analysisService.progress)
                .tint(AppTheme.accentPurple)
                .scaleEffect(y: 2)
                .accessibilityLabel(analysisProgressTitle)
                .accessibilityValue("\(Int(viewModel.analysisService.progress * 100)) percent")

            Text(viewModel.analysisService.statusMessage)
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
                .multilineTextAlignment(.center)
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                .minimumScaleFactor(0.84)
                .fixedSize(horizontal: false, vertical: true)

            Text(analysisProgressDetailText)
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
                .multilineTextAlignment(.center)
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                .minimumScaleFactor(0.84)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.accentPurple.opacity(0.2))
        .accessibilityElement(children: .combine)
        .accessibilityLabel(analysisProgressTitle)
        .accessibilityValue("\(Int(viewModel.analysisService.progress * 100)) percent. \(viewModel.analysisService.statusMessage). \(analysisProgressDetailText)")
    }

    private var analysisProgressHeader: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                analysisProgressTitleLabel
                Spacer(minLength: 8)
                analysisProgressPercentText
            }

            VStack(alignment: .center, spacing: 6) {
                analysisProgressTitleLabel
                analysisProgressPercentText
            }
        }
    }

    private var analysisProgressTitleLabel: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Image(systemName: "brain.head.profile.fill")
                .foregroundStyle(AppTheme.neonPurple)
                .symbolEffect(.variableColor.iterative, isActive: true)
            Text(analysisProgressTitle)
                .font(.headline)
                .foregroundStyle(.white)
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                .minimumScaleFactor(0.84)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var analysisProgressPercentText: some View {
        Text("\(Int(viewModel.analysisService.progress * 100))%")
            .font(.subheadline.monospacedDigit())
            .foregroundStyle(AppTheme.neonPurple)
            .lineLimit(1)
            .minimumScaleFactor(0.8)
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

            LazyVGrid(columns: analysisStatGridColumns, alignment: .leading, spacing: 10) {
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
                            .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                            .minimumScaleFactor(0.84)
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

    private var analysisStatGridColumns: [GridItem] {
        [
            GridItem(.adaptive(minimum: dynamicTypeSize.isAccessibilitySize ? 126 : 94), spacing: 10, alignment: .top)
        ]
    }

    private func statBadge(value: String, label: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title3.bold().monospacedDigit())
                .foregroundStyle(color)
                .lineLimit(1)
                .minimumScaleFactor(0.72)
            Text(label)
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                .minimumScaleFactor(0.84)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 58 : 44)
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
        if status.contains("team") || status.contains("jersey") {
            return "Choosing teams"
        }
        if status.contains("candidate") || status.contains("clip") || status.contains("highlight") || status.contains("detecting") {
            return "Finding clips"
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

    private var analysisProgressDetailText: String {
        let status = viewModel.analysisService.statusMessage.lowercased()

        if status.contains("upload") {
            return "Uploading the source video to the cloud before analysis starts."
        }

        if status.contains("team") || status.contains("jersey") {
            return "Scanning jersey colors so you can target one team or keep all teams."
        }

        if status.contains("queued") || status.contains("waiting") {
            return "Cloud worker is next in line; the next update appears when the job advances."
        }

        if status.contains("candidate") || status.contains("finding") || status.contains("detecting") || status.contains("clip") || status.contains("highlight") {
            if viewModel.settings.highlightTeamSelection.mode == .team {
                return "Focusing on \(viewModel.settings.highlightTeamSelection.displayTitle) and keeping uncertain plays for Review."
            }
            return "Building a high-recall clip pool from both teams for Review."
        }

        if status.contains("frame") || status.contains("scoring") || status.contains("motion") || status.contains("audio") || status.contains("action") {
            return "Scoring motion, audio peaks, and basketball action in the cloud."
        }

        if status.contains("finalizing") || status.contains("refining") {
            return "Validated clips are coming back for Review."
        }

        if viewModel.analysisMode == .cloud {
            return "Cloud analysis is active; the next update appears when the backend advances."
        }

        return "Analysis is running on device because cloud mode is unavailable."
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

private enum CloudVideoConsentAction {
    case teamScan
    case startAnalysis
}

private struct CloudVideoConsentSheet: View {
    let primaryActionTitle: String
    let onAccept: () -> Void
    let onCancel: () -> Void

    var body: some View {
        NavigationStack {
            ZStack {
                AppTheme.darkBg.ignoresSafeArea()

                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Use Cloud AI")
                                .font(.title2.bold())
                                .foregroundStyle(.white)
                            Text("HoopClips needs cloud processing to scan teams, find highlights, and make edited videos for this build.")
                                .font(.subheadline)
                                .foregroundStyle(AppTheme.subtleText)
                                .fixedSize(horizontal: false, vertical: true)
                        }

                        VStack(alignment: .leading, spacing: 12) {
                            consentRow(icon: "icloud.and.arrow.up.fill", text: "Your source video is uploaded to HoopClips cloud services for team scan and analysis.")
                            consentRow(icon: "basketball.fill", text: "AI looks for teams, plays, blocks, steals, and useful review clips.")
                            consentRow(icon: "film.stack.fill", text: "Finished edits and cloud locker copies can be stored for a limited time.")
                            consentRow(icon: "iphone", text: "Imported files, History, and saved downloads also remain on this device.")
                        }

                        if let privacyURL = AppConstants.privacyPolicyURL {
                            Link(destination: privacyURL) {
                                Label("Privacy Policy", systemImage: "lock.shield.fill")
                                    .font(.footnote.weight(.semibold))
                            }
                            .foregroundStyle(AppTheme.neonPurple)
                        }

                        VStack(spacing: 10) {
                            Button {
                                onAccept()
                            } label: {
                                Text(primaryActionTitle)
                                    .font(.headline)
                                    .foregroundStyle(.white)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 14)
                                    .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 14))
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("analysis.cloudConsent.acceptButton")

                            Button {
                                onCancel()
                            } label: {
                                Text("Not Now")
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundStyle(AppTheme.subtleText)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 12)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(20)
                }
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Close") {
                        onCancel()
                    }
                    .foregroundStyle(AppTheme.subtleText)
                }
            }
        }
    }

    private func consentRow(icon: String, text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(AppTheme.neonPurple)
                .frame(width: 22)
            Text(text)
                .font(.footnote)
                .foregroundStyle(.white.opacity(0.86))
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

enum VideoImportPolicy {
    static let maxCloudUploadBytes: Int64 = 500 * 1024 * 1024
    static let maxCloudDurationSeconds: Double = AppConstants.cloudAnalysisMaxDuration
    static let requiredScratchBytes: Int64 = 256 * 1024 * 1024

    static let supportedContentTypes: [UTType] = [
        .video,
        .movie,
        .mpeg4Movie,
        .quickTimeMovie
    ]

    static let usesFileBackedTransferOnly = true

    static func preflight(url: URL) async throws -> VideoImportPreflightSummary {
        let fileExtension = url.pathExtension
        guard isSupportedVideoExtension(fileExtension) else {
            throw VideoImportPreflightError.unsupportedType(fileExtension.isEmpty ? "unknown" : fileExtension)
        }

        let fileSizeBytes = try fileSizeBytes(for: url)
        let availableCapacityBytes = availableCapacityBytesForImport()
        let summary = try await metadataSummary(
            for: url,
            fileSizeBytes: fileSizeBytes,
            availableCapacityBytes: availableCapacityBytes
        )
        try validate(summary)
        return summary
    }

    static func validateTemporaryCopyCapacity(for sourceURL: URL) throws {
        let fileSizeBytes = try fileSizeBytes(for: sourceURL)
        try validateLocalStorage(fileSizeBytes: fileSizeBytes, availableCapacityBytes: availableCapacityBytesForImport())
    }

    static func validate(_ summary: VideoImportPreflightSummary) throws {
        guard summary.fileSizeBytes > 0 else {
            throw VideoImportPreflightError.unreadableFileSize
        }
        guard summary.fileSizeBytes <= maxCloudUploadBytes else {
            throw VideoImportPreflightError.fileTooLarge(
                actualBytes: summary.fileSizeBytes,
                maxBytes: maxCloudUploadBytes
            )
        }
        try validateLocalStorage(
            fileSizeBytes: summary.fileSizeBytes,
            availableCapacityBytes: summary.availableCapacityBytes
        )
        guard let durationSeconds = summary.durationSeconds, durationSeconds.isFinite, durationSeconds > 0 else {
            throw VideoImportPreflightError.unreadableDuration
        }
        guard durationSeconds <= maxCloudDurationSeconds else {
            throw VideoImportPreflightError.videoTooLong(
                actualSeconds: durationSeconds,
                maxSeconds: maxCloudDurationSeconds
            )
        }
        guard summary.dimensions != nil else {
            throw VideoImportPreflightError.noVideoTrack
        }
    }

    static func evaluatePreflight(
        fileSizeBytes: Int64,
        durationSeconds: Double?,
        dimensions: CGSize?,
        codecNames: [String],
        availableCapacityBytes: Int64?,
        fileExtension: String = "mov"
    ) throws -> VideoImportPreflightSummary {
        let summary = VideoImportPreflightSummary(
            fileSizeBytes: fileSizeBytes,
            durationSeconds: durationSeconds,
            dimensions: dimensions,
            codecNames: codecNames,
            availableCapacityBytes: availableCapacityBytes,
            fileExtension: fileExtension
        )
        try validate(summary)
        return summary
    }

    static func formattedBytes(_ bytes: Int64) -> String {
        let formatter = ByteCountFormatter()
        formatter.allowedUnits = [.useMB, .useGB]
        formatter.countStyle = .file
        return formatter.string(fromByteCount: bytes)
    }

    static func preferredImportedVideoFileExtension(
        sourceExtension: String,
        fallbackExtension: String
    ) -> String {
        let fallback = normalizedFileExtension(fallbackExtension).isEmpty ? "mov" : normalizedFileExtension(fallbackExtension)
        let candidate = normalizedFileExtension(sourceExtension)
        guard !candidate.isEmpty else { return fallback }
        guard let type = UTType(filenameExtension: candidate) else { return fallback }
        if type.conforms(to: .video) || type.conforms(to: .movie) || supportedContentTypes.contains(type) {
            return candidate
        }
        return fallback
    }

    private static func metadataSummary(
        for url: URL,
        fileSizeBytes: Int64,
        availableCapacityBytes: Int64?
    ) async throws -> VideoImportPreflightSummary {
        let asset = AVURLAsset(url: url)
        let duration = try await asset.load(.duration)
        let durationSeconds = CMTimeGetSeconds(duration)
        let videoTracks = try await asset.loadTracks(withMediaType: .video)
        guard let videoTrack = videoTracks.first else {
            return VideoImportPreflightSummary(
                fileSizeBytes: fileSizeBytes,
                durationSeconds: durationSeconds,
                dimensions: nil,
                codecNames: [],
                availableCapacityBytes: availableCapacityBytes,
                fileExtension: url.pathExtension
            )
        }

        let naturalSize = try await videoTrack.load(.naturalSize)
        let preferredTransform = try await videoTrack.load(.preferredTransform)
        let transformedSize = naturalSize.applying(preferredTransform)
        let dimensions = CGSize(
            width: abs(transformedSize.width.rounded()),
            height: abs(transformedSize.height.rounded())
        )
        let formatDescriptions = (try? await videoTrack.load(.formatDescriptions)) ?? []
        let codecNames = formatDescriptions
            .map { CMFormatDescriptionGetMediaSubType($0).fourCharacterCodeString }
            .filter { !$0.isEmpty }

        return VideoImportPreflightSummary(
            fileSizeBytes: fileSizeBytes,
            durationSeconds: durationSeconds,
            dimensions: dimensions,
            codecNames: Array(Set(codecNames)).sorted(),
            availableCapacityBytes: availableCapacityBytes,
            fileExtension: url.pathExtension
        )
    }

    private static func validateLocalStorage(fileSizeBytes: Int64, availableCapacityBytes: Int64?) throws {
        guard let availableCapacityBytes else { return }
        let requiredBytes = fileSizeBytes + requiredScratchBytes
        guard availableCapacityBytes >= requiredBytes else {
            throw VideoImportPreflightError.notEnoughStorage(
                availableBytes: availableCapacityBytes,
                requiredBytes: requiredBytes
            )
        }
    }

    private static func fileSizeBytes(for url: URL) throws -> Int64 {
        let values = try url.resourceValues(forKeys: [.fileSizeKey])
        guard let fileSize = values.fileSize, fileSize > 0 else {
            throw VideoImportPreflightError.unreadableFileSize
        }
        return Int64(fileSize)
    }

    private static func availableCapacityBytesForImport() -> Int64? {
        let values = try? URL.temporaryDirectory.resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey])
        return values?.volumeAvailableCapacityForImportantUsage
    }

    private static func isSupportedVideoExtension(_ fileExtension: String) -> Bool {
        let trimmed = normalizedFileExtension(fileExtension)
        guard !trimmed.isEmpty else { return true }
        guard let type = UTType(filenameExtension: trimmed) else { return true }
        return type.conforms(to: .video) || type.conforms(to: .movie) || supportedContentTypes.contains(type)
    }

    private static func normalizedFileExtension(_ fileExtension: String) -> String {
        fileExtension
            .trimmingCharacters(in: CharacterSet(charactersIn: ". \n\t"))
            .lowercased()
    }
}

struct VideoImportPreflightSummary: Equatable, Sendable {
    let fileSizeBytes: Int64
    let durationSeconds: Double?
    let dimensions: CGSize?
    let codecNames: [String]
    let availableCapacityBytes: Int64?
    let fileExtension: String

    func telemetryMetadata(source: String) -> String {
        let durationText = durationSeconds.map { String(Int($0.rounded())) } ?? "unknown"
        let dimensionsText: String
        if let dimensions {
            dimensionsText = "\(Int(dimensions.width))x\(Int(dimensions.height))"
        } else {
            dimensionsText = "unknown"
        }
        let codecText = codecNames.isEmpty ? "unknown" : codecNames.joined(separator: ",")
        return "source=\(source) fileSizeBytes=\(fileSizeBytes) durationSeconds=\(durationText) resolution=\(dimensionsText) codecs=\(codecText)"
    }
}

enum VideoImportPreflightError: LocalizedError, Equatable {
    case unsupportedType(String)
    case unreadableFileSize
    case unreadableDuration
    case noVideoTrack
    case fileTooLarge(actualBytes: Int64, maxBytes: Int64)
    case videoTooLong(actualSeconds: Double, maxSeconds: Double)
    case notEnoughStorage(availableBytes: Int64, requiredBytes: Int64)

    var code: String {
        switch self {
        case .unsupportedType:
            return "unsupported_type"
        case .unreadableFileSize:
            return "unreadable_file_size"
        case .unreadableDuration:
            return "unreadable_duration"
        case .noVideoTrack:
            return "no_video_track"
        case .fileTooLarge:
            return "file_too_large"
        case .videoTooLong:
            return "video_too_long"
        case .notEnoughStorage:
            return "not_enough_storage"
        }
    }

    var userFacingMessage: String {
        switch self {
        case .unsupportedType(let fileExtension):
            return "HoopClips supports movie files like MP4, MOV, and QuickTime. This file type (\(fileExtension)) is not supported."
        case .unreadableFileSize:
            return "HoopClips could not read that video's file size. Save it to Files and try importing it again."
        case .unreadableDuration:
            return "HoopClips could not read that video's duration. Export a fresh MP4 or MOV copy and try again."
        case .noVideoTrack:
            return "That file does not contain a readable video track. Choose a different basketball video."
        case .fileTooLarge(let actualBytes, let maxBytes):
            return "This video is \(VideoImportPolicy.formattedBytes(actualBytes)). HoopClips cloud analysis accepts up to \(VideoImportPolicy.formattedBytes(maxBytes)). Choose a shorter clip or export a smaller copy before importing."
        case .videoTooLong(let actualSeconds, let maxSeconds):
            return "This video is \(Clip.formatTime(actualSeconds)). HoopClips cloud analysis accepts videos up to \(Clip.formatTime(maxSeconds)). Choose a shorter game file before importing."
        case .notEnoughStorage(let availableBytes, let requiredBytes):
            return "This import needs about \(VideoImportPolicy.formattedBytes(requiredBytes)) free on this iPhone. You have about \(VideoImportPolicy.formattedBytes(availableBytes)) available."
        }
    }

    var errorDescription: String? {
        userFacingMessage
    }
}

private extension FourCharCode {
    var fourCharacterCodeString: String {
        let bytes: [UInt8] = [
            UInt8((self >> 24) & 0xff),
            UInt8((self >> 16) & 0xff),
            UInt8((self >> 8) & 0xff),
            UInt8(self & 0xff)
        ]
        return String(bytes: bytes, encoding: .macOSRoman) ?? "\(self)"
    }
}

private extension ProjectImportPhase {
    var importStatusMessage: String {
        switch self {
        case .copyingSource:
            return "Copying video into HoopClips..."
        case .readingMetadata:
            return "Reading video details..."
        case .generatingPreview:
            return "Building project preview..."
        case .savingProject:
            return "Opening project..."
        }
    }
}

private enum VideoImportTransfer {
    static func loadFileBackedVideo(from item: PhotosPickerItem) async throws -> ImportedVideoFile? {
        try await Task.detached(priority: .userInitiated) {
            try Task.checkCancellation()
            return try await item.loadTransferable(type: ImportedVideoFile.self)
        }.value
    }

    static func removeTemporaryFile(at url: URL) async throws {
        try await Task.detached(priority: .utility) {
            try Task.checkCancellation()
            guard url.path.hasPrefix(URL.temporaryDirectory.path) else {
                return
            }
            try FileManager.default.removeItem(at: url)
        }.value
    }

    static func scheduleTemporaryFileRemoval(at url: URL) {
        Task.detached(priority: .utility) {
            guard !Task.isCancelled else { return }
            guard url.path.hasPrefix(URL.temporaryDirectory.path) else {
                return
            }
            try? FileManager.default.removeItem(at: url)
        }
    }
}

private struct ImportedVideoFile: Transferable {
    let url: URL

    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(contentType: .video) { video in
            SentTransferredFile(video.url)
        } importing: { received in
            try copyImportedVideo(from: received.file, fallbackExtension: "mov")
        }

        FileRepresentation(contentType: .movie) { video in
            SentTransferredFile(video.url)
        } importing: { received in
            try copyImportedVideo(from: received.file, fallbackExtension: "mov")
        }

        FileRepresentation(contentType: .mpeg4Movie) { video in
            SentTransferredFile(video.url)
        } importing: { received in
            try copyImportedVideo(from: received.file, fallbackExtension: "mp4")
        }

        FileRepresentation(contentType: .quickTimeMovie) { video in
            SentTransferredFile(video.url)
        } importing: { received in
            try copyImportedVideo(from: received.file, fallbackExtension: "mov")
        }
    }

    private static func copyImportedVideo(from sourceURL: URL, fallbackExtension: String) throws -> ImportedVideoFile {
        let accessing = sourceURL.startAccessingSecurityScopedResource()
        defer {
            if accessing {
                sourceURL.stopAccessingSecurityScopedResource()
            }
        }

        let fileExtension = VideoImportPolicy.preferredImportedVideoFileExtension(
            sourceExtension: sourceURL.pathExtension,
            fallbackExtension: fallbackExtension
        )
        let tempURL = URL.temporaryDirectory.appending(path: "imported_video_\(UUID().uuidString).\(fileExtension)")
        try VideoImportPolicy.validateTemporaryCopyCapacity(for: sourceURL)
        try FileManager.default.copyItem(at: sourceURL, to: tempURL)
        return ImportedVideoFile(url: tempURL)
    }
}
