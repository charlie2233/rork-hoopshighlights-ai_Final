import SwiftUI
import AVKit
import PhotosUI

struct VideoPlayerView: View {
    @Bindable var viewModel: HighlightsViewModel
    @Environment(SubscriptionManager.self) private var subscriptionManager
    @State private var player: AVPlayer?
    @State private var showingFilePicker = false
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var showSourcePicker = false
    @State private var analysisStarted = false
    @State private var pulseAnimation = false
    @State private var showingPaywall = false
    @State private var showingNoClipsAlert = false
    @State private var showingDurationLimitAlert = false

    var body: some View {
        NavigationStack {
            ZStack {
                AppTheme.darkBg.ignoresSafeArea()

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
            .navigationTitle("Hoops AI")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                if viewModel.isVideoLoaded {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            viewModel.resetProject()
                            player = nil
                            analysisStarted = false
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundStyle(AppTheme.subtleText)
                        }
                    }
                }
            }
            .confirmationDialog("Import Video", isPresented: $showSourcePicker) {
                Button("Photo Library") {
                    viewModel.showingVideoPicker = true
                }
                Button("Files") {
                    showingFilePicker = true
                }
            }
            .photosPicker(isPresented: $viewModel.showingVideoPicker, selection: $selectedPhotoItem, matching: .videos)
            .fileImporter(isPresented: $showingFilePicker, allowedContentTypes: [.movie, .video, .mpeg4Movie, .quickTimeMovie]) { result in
                if case .success(let url) = result {
                    Task { await viewModel.loadVideo(url: url) }
                }
            }
            .onChange(of: selectedPhotoItem) { _, newValue in
                guard let item = newValue else { return }
                selectedPhotoItem = nil
                Task {
                    if let data = try? await item.loadTransferable(type: Data.self) {
                        let tempURL = URL.temporaryDirectory.appending(path: "imported_video_\(UUID().uuidString).mp4")
                        try? data.write(to: tempURL, options: .atomic)
                        await viewModel.loadVideo(url: tempURL)
                    }
                }
            }
            .onChange(of: viewModel.isVideoLoaded) { _, loaded in
                if loaded, let url = viewModel.videoURL {
                    player = AVPlayer(url: url)
                }
            }
            .sheet(isPresented: $showingPaywall) {
                PaywallView(subscriptionManager: subscriptionManager)
            }
            .alert("No Highlights Found", isPresented: $showingNoClipsAlert) {
                Button("OK", role: .cancel) { }
            } message: {
                if viewModel.isCloudFallbackOffered {
                    Text("Cloud analysis and local fallback both finished without finding enough confident highlights in this clip.")
                } else {
                    Text("AI couldn't detect enough confident highlights in this video.")
                }
            }
            .alert("Pro Required for Longer Videos", isPresented: $showingDurationLimitAlert) {
                Button("Not Now", role: .cancel) { }
                Button("Go Pro") {
                    showingPaywall = true
                }
            } message: {
                Text("Free tier can analyze videos up to \(formatDuration(AppConstants.nonProMaxAnalysisDuration)). This video is \(formatDuration(viewModel.videoDuration)).")
            }
        }
    }

    private var importSection: some View {
        VStack(spacing: 32) {
            Spacer().frame(height: 40)

            ZStack {
                Circle()
                    .fill(AppTheme.accentPurple.opacity(0.15))
                    .frame(width: 140, height: 140)
                    .scaleEffect(pulseAnimation ? 1.15 : 1.0)
                    .animation(.easeInOut(duration: 2.0).repeatForever(autoreverses: true), value: pulseAnimation)

                Circle()
                    .fill(AppTheme.accentPurple.opacity(0.08))
                    .frame(width: 180, height: 180)
                    .scaleEffect(pulseAnimation ? 1.1 : 1.0)
                    .animation(.easeInOut(duration: 2.5).repeatForever(autoreverses: true), value: pulseAnimation)

                Image(systemName: "basketball.fill")
                    .font(.system(size: 56))
                    .foregroundStyle(AppTheme.neonPurple)
                    .symbolEffect(.bounce, options: .repeating.speed(0.3), value: pulseAnimation)
            }
            .onAppear { pulseAnimation = true }

            VStack(spacing: 12) {
                Text("Import Game Footage")
                    .font(.title2.bold())
                    .foregroundStyle(.white)

                Text("AI will analyze your basketball video\nand extract the best highlights")
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.subtleText)
                    .multilineTextAlignment(.center)
            }
            .padding(.horizontal, 10)

            Button {
                showSourcePicker = true
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "plus.circle.fill")
                        .font(.title3)
                    Text("Select Video")
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

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                featurePill(icon: "brain.head.profile.fill", text: "AI Detection")
                featurePill(icon: "bolt.fill", text: "Fast Processing")
                featurePill(icon: "film.stack.fill", text: "Auto Clips")
                featurePill(icon: "sparkles.rectangle.stack.fill", text: "Rork MAX UI")
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
                title: "Source Video",
                icon: "video.fill",
                subtitle: viewModel.isVideoLoaded ? "Loaded and ready for AI analysis" : nil
            )

            if let player = player {
                VideoPlayer(player: player)
                    .frame(height: 220)
                    .clipShape(.rect(cornerRadius: 16))
                    .overlay(
                        RoundedRectangle(cornerRadius: 16)
                            .stroke(AppTheme.accentPurple.opacity(0.3), lineWidth: 1)
                    )
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
                    label: "Duration",
                    tint: AppTheme.warningYellow
                )

                if let url = viewModel.videoURL {
                    RorkMetricChip(
                        icon: "doc.fill",
                        value: url.pathExtension.uppercased().isEmpty ? "VIDEO" : url.pathExtension.uppercased(),
                        label: "Format",
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
                title: "AI Analysis",
                icon: "brain.head.profile.fill",
                subtitle: "Detects key basketball moments and builds reviewable clips"
            )

            if viewModel.analysisService.isAnalyzing {
                analysisProgressView
            } else if !viewModel.clips.isEmpty {
                analysisCompleteView
            } else {
                if !subscriptionManager.isProUser || viewModel.cloudQuotaRemaining != nil {
                    HStack(spacing: 8) {
                        Image(systemName: "sparkles")
                            .foregroundStyle(AppTheme.warningYellow)
                        Text(analysisBannerText)
                            .font(.caption.weight(.medium))
                            .foregroundStyle(AppTheme.warningYellow)
                        Spacer()
                        if subscriptionManager.freeUsesRemaining == 0 && subscriptionManager.isProUser == false {
                            Button("Go Pro") { showingPaywall = true }
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
                            Text("Analyze with AI")
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

                estimatedTimeView
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder)
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

            Text(viewModel.analysisService.statusMessage)
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.accentPurple.opacity(0.2))
    }

    private var analysisCompleteView: some View {
        VStack(spacing: 12) {
            HStack {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(AppTheme.successGreen)
                Text("Analysis Complete")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
            }

            HStack(spacing: 16) {
                statBadge(value: "\(viewModel.clips.count)", label: "Clips Found", color: AppTheme.neonPurple)
                statBadge(value: "\(viewModel.keptClips.count)", label: "Kept", color: AppTheme.successGreen)
                statBadge(value: formatDuration(viewModel.keptClips.reduce(0) { $0 + $1.duration }), label: "Duration", color: AppTheme.warningYellow)
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
            Text("Estimated: ~\(estimatedSeconds)s cloud analysis")
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
                title: "Project Snapshot",
                icon: "sparkles",
                subtitle: "Quick context before review and export"
            )

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: "film.stack.fill",
                    value: "\(viewModel.clips.count)",
                    label: "Detected",
                    tint: AppTheme.neonPurple
                )
                RorkMetricChip(
                    icon: "checkmark.circle.fill",
                    value: "\(viewModel.keptClips.count)",
                    label: "Kept",
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

    private var analysisBannerText: String {
        if requiresProForCurrentVideo {
            return "Free tier supports up to \(formatDuration(AppConstants.nonProMaxAnalysisDuration)). Upgrade to analyze longer games."
        }
        if let remaining = viewModel.cloudQuotaRemaining {
            if remaining > 0 {
                return "Cloud AI quota remaining today: \(remaining)"
            }
            return "Cloud AI quota is exhausted today. Local fallback still runs when possible."
        }
        return "Cloud AI runs slower, but it targets much better highlight accuracy."
    }

    private var analysisProgressTitle: String {
        let status = viewModel.analysisService.statusMessage.lowercased()
        if status.contains("upload") {
            return "Uploading..."
        }
        if status.contains("queued") {
            return "Queued..."
        }
        if status.contains("cloud") {
            return "Cloud Analyzing..."
        }
        if status.contains("local analysis") {
            return "Fallback..."
        }
        if status.contains("finalizing") {
            return "Finalizing..."
        }
        if status.contains("refining") {
            return "Refining..."
        }
        return "Analyzing..."
    }

    private var requiresProForCurrentVideo: Bool {
        !subscriptionManager.isProUser && viewModel.videoDuration > AppConstants.nonProMaxAnalysisDuration
    }

    private var analysisButtonSubtitle: String {
        if requiresProForCurrentVideo {
            return "Upgrade to analyze videos longer than \(formatDuration(AppConstants.nonProMaxAnalysisDuration))"
        }
        return "Cloud-first, slower, and much more accurate"
    }
}
