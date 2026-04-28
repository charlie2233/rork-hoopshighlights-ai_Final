import AVKit
import SwiftUI

struct AIEditView: View {
    @Bindable var viewModel: HighlightsViewModel
    let isProUser: Bool

    @Environment(\.dismiss) private var dismiss
    @State private var selectedPreset: CloudEditPreset = .personalHighlight
    @State private var selectedDuration = CloudEditPreset.personalHighlight.durationOptions[1]
    @State private var phase: CloudEditRenderState = .planning
    @State private var editJob: CloudEditJobResponse?
    @State private var editPlan: CloudEditPlanSummary?
    @State private var renderStatus: CloudEditRenderStatusResponse?
    @State private var downloadResponse: CloudEditDownloadResponse?
    @State private var revisionResponse: CloudEditRevisionResponse?
    @State private var pendingRevisionCommand: CloudEditRevisionCommand?
    @State private var previewPlayer: AVPlayer?
    @State private var localShareURL: URL?
    @State private var errorMessage: String?
    @State private var isWorking = false
    @State private var isPreparingShare = false
    @State private var showingShareSheet = false

    private let cloudEditService = CloudEditService()

    var body: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.18)

                ScrollView {
                    VStack(spacing: 18) {
                        heroCard
                        stylePicker
                        durationPicker
                        statusCard

                        if let previewPlayer {
                            previewCard(player: previewPlayer)
                        }

                        if editPlan != nil, downloadResponse != nil || revisionResponse != nil {
                            revisionCard
                        }

                        actionCard
                    }
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
            .sheet(isPresented: $showingShareSheet) {
                if let localShareURL {
                    SystemShareSheet(
                        items: SystemShareSheet.videoItems(
                            for: localShareURL,
                            title: "Hoopclips AI Edit"
                        ),
                        subject: "Hoopclips AI Edit"
                    )
                }
            }
            .onChange(of: selectedPreset) { _, preset in
                selectedDuration = preset.durationOptions[min(1, preset.durationOptions.count - 1)]
            }
        }
    }

    private var heroCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Make Highlight Reel", systemImage: "wand.and.stars")
                .font(.title2.bold())
                .foregroundStyle(.white)

            Text("Hoopclips will ask the cloud AI edit agent to plan and render a finished MP4 from your kept clips.")
                .font(.subheadline)
                .foregroundStyle(AppTheme.subtleText)

            HStack(spacing: 8) {
                aiChip(icon: "film.stack.fill", text: "\(viewModel.keptClips.count) kept clips")
                aiChip(icon: selectedPreset.aspectRatio == .vertical ? "rectangle.portrait.fill" : "rectangle.fill", text: selectedPreset.aspectRatio.rawValue)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.accentPurple.opacity(0.22), glow: AppTheme.neonPurple, glowOpacity: 0.10)
    }

    private var stylePicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Style")
                .font(.headline)
                .foregroundStyle(.white)

            ForEach(CloudEditPreset.allCases) { preset in
                Button {
                    selectedPreset = preset
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: selectedPreset == preset ? "checkmark.circle.fill" : "circle")
                            .foregroundStyle(selectedPreset == preset ? AppTheme.successGreen : AppTheme.subtleText)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(preset.title)
                                .font(.subheadline.bold())
                                .foregroundStyle(.white)
                            Text(preset.subtitle)
                                .font(.caption)
                                .foregroundStyle(AppTheme.subtleText)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        Spacer()
                    }
                    .padding(12)
                    .background(selectedPreset == preset ? AppTheme.accentPurple.opacity(0.18) : AppTheme.cardBg.opacity(0.72), in: .rect(cornerRadius: 14))
                    .overlay {
                        RoundedRectangle(cornerRadius: 14)
                            .stroke(selectedPreset == preset ? AppTheme.neonPurple.opacity(0.35) : AppTheme.softBorder, lineWidth: 1)
                    }
                }
                .buttonStyle(.plain)
                .accessibilityLabel(preset.title)
                .accessibilityIdentifier(styleAccessibilityIdentifier(for: preset))
                .accessibilityValue(selectedPreset == preset ? "Selected" : "Not selected")
                .accessibilityHint("Selects the AI edit style.")
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
                Text("\(selectedDuration)s")
                    .font(.subheadline.monospacedDigit().bold())
                    .foregroundStyle(AppTheme.warningYellow)
            }

            HStack(spacing: 8) {
                ForEach(selectedPreset.durationOptions, id: \.self) { duration in
                    Button {
                        selectedDuration = duration
                    } label: {
                        Text("\(duration)s")
                            .font(.subheadline.bold())
                            .foregroundStyle(selectedDuration == duration ? .white : AppTheme.subtleText)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 10)
                            .background(selectedDuration == duration ? AppTheme.accentPurple : AppTheme.cardBg, in: .capsule)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("\(duration) seconds")
                    .accessibilityIdentifier(durationAccessibilityIdentifier(for: duration))
                    .accessibilityValue(selectedDuration == duration ? "Selected" : "Not selected")
                }
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.04)
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
                    .accessibilityIdentifier("edit.status.label")
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
                Text(viewModel.cloudEditUnavailableReason ?? "Ready to request a cloud-rendered AI edit.")
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
            }

            if let renderStatus, let duration = renderStatus.durationSeconds {
                Text("Rendered duration: \(Clip.formatTime(duration))")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(AppTheme.subtleText)
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
                .accessibilityIdentifier("edit.preview.player")
                .accessibilityLabel("Rendered AI edit preview")
                .accessibilityHint("Plays the cloud-rendered MP4.")
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.04)
    }

    private var actionCard: some View {
        VStack(spacing: 10) {
            if let errorMessage {
                Text(errorMessage)
                    .font(.caption)
                    .foregroundStyle(AppTheme.dangerRed)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("edit.failure.reasonLabel")
            }

            Button(action: startEdit) {
                Label(primaryActionTitle, systemImage: primaryActionIcon)
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
            }
            .buttonStyle(.borderedProminent)
            .tint(AppTheme.accentPurple)
            .disabled(isWorking || !viewModel.canRequestCloudEdit)
            .accessibilityIdentifier(revisionResponse != nil && downloadResponse == nil ? "edit.revision.renderButton" : "edit.render.startButton")
            .accessibilityHint("Requests a cloud edit plan and render.")

            if downloadResponse != nil {
                Button(action: shareRenderedVideo) {
                    Label(isPreparingShare ? "Preparing MP4..." : "Download / Share / Open In", systemImage: "square.and.arrow.up.fill")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                }
                .buttonStyle(.bordered)
                .tint(AppTheme.neonPurple)
                .disabled(isPreparingShare)
                .accessibilityIdentifier("edit.share.button")
                .accessibilityHint("Downloads the rendered MP4 and opens the system share sheet.")
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
                    .disabled(isWorking)
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
                    .accessibilityIdentifier("edit.revision.summaryLabel")
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.neonPurple.opacity(0.18), glow: AppTheme.neonPurple, glowOpacity: 0.05)
        .accessibilityIdentifier("edit.revision.card")
    }

    private var statusIcon: String {
        switch phase {
        case .rendered:
            return "checkmark.seal.fill"
        case .failed, .cancelled:
            return "exclamationmark.triangle.fill"
        case .renderRequested, .planning, .planReady, .created, .queued, .rendering:
            return "cloud.fill"
        }
    }

    private var statusColor: Color {
        switch phase {
        case .rendered:
            return AppTheme.successGreen
        case .failed, .cancelled:
            return AppTheme.dangerRed
        case .renderRequested, .planning, .planReady, .created, .queued, .rendering:
            return AppTheme.neonPurple
        }
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
        if revisionResponse != nil, downloadResponse == nil {
            return "Render Revision"
        }
        return downloadResponse == nil ? "Create AI Edit" : "Render Again"
    }

    private var primaryActionIcon: String {
        revisionResponse != nil && downloadResponse == nil ? "arrow.triangle.2.circlepath.circle.fill" : "sparkles.tv.fill"
    }

    private var revisionStatusText: String {
        if let pendingRevisionCommand, revisionResponse != nil, downloadResponse == nil {
            return "\(pendingRevisionCommand.title) revision is ready. Render it to create a new MP4."
        }
        if let pendingRevisionCommand {
            return "Last revision: \(pendingRevisionCommand.title). Pick another change or render again."
        }
        return "Ask Hoopclips to patch the edit plan, then render the revised MP4."
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
            return "edit.style.personalHighlightButton"
        case .fullGameHighlight:
            return "edit.style.fullGameHighlightButton"
        case .coachReview:
            return "edit.style.coachReviewButton"
        }
    }

    private func durationAccessibilityIdentifier(for duration: Int) -> String {
        "edit.duration.\(duration)sButton"
    }

    private func startEdit() {
        guard !isWorking else { return }
        if revisionResponse != nil, downloadResponse == nil {
            Task { await runRevisionRenderFlow() }
        } else {
            Task { await runEditFlow() }
        }
    }

    private func requestRevision(_ command: CloudEditRevisionCommand) {
        guard !isWorking else { return }
        Task { await runRevisionFlow(command) }
    }

    private func shareRenderedVideo() {
        guard !isPreparingShare else { return }
        Task { await prepareShareSheet() }
    }

    @MainActor
    private func runEditFlow() async {
        isWorking = true
        errorMessage = nil
        previewPlayer = nil
        downloadResponse = nil
        revisionResponse = nil
        pendingRevisionCommand = nil
        localShareURL = nil
        phase = .planning
        HoopsAccessibility.announce("Creating cloud AI edit plan.")
        defer { isWorking = false }

        do {
            #if DEBUG
            if Self.shouldSimulateRenderFailure {
                phase = .rendering
                HoopsAccessibility.announce("Rendering video.")
                try? await Task.sleep(nanoseconds: 350_000_000)
                throw CloudEditError.backend(
                    code: "ui_smoke_render_failed",
                    message: "Simulated cloud render failure for UI smoke."
                )
            }
            #endif

            let request = try viewModel.createCloudEditRequest(
                preset: selectedPreset,
                targetDurationSeconds: selectedDuration,
                isProUser: isProUser
            )
            let job = try await cloudEditService.createEditJob(request)
            editJob = job

            let planResponse = try await cloudEditService.fetchEditPlan(
                editJobID: job.editJobId,
                installID: viewModel.installID
            )
            editPlan = planResponse.plan
            phase = .planReady
            HoopsAccessibility.announce("Cloud AI edit plan ready. Rendering video.")

            guard let sourceObjectKey = viewModel.cloudEditSourceObjectKey else {
                throw CloudEditError.missingSourceObject
            }
            let requested = try await cloudEditService.requestRender(
                editJobID: job.editJobId,
                installID: viewModel.installID,
                sourceObjectKey: sourceObjectKey,
                planTier: request.planTier,
                editPlan: planResponse.plan,
                sourceClips: request.clips
            )
            renderStatus = requested
            phase = requested.status

            let finalStatus = try await cloudEditService.pollRenderStatus(
                editJobID: job.editJobId,
                installID: viewModel.installID
            )
            renderStatus = finalStatus
            phase = finalStatus.status

            guard finalStatus.status == .rendered else {
                throw CloudEditError.backend(
                    code: finalStatus.failureReason ?? "render_failed",
                    message: finalStatus.failureReason ?? "Cloud rendering did not finish."
                )
            }

            let download = try await cloudEditService.fetchDownloadURL(
                editJobID: job.editJobId,
                installID: viewModel.installID
            )
            downloadResponse = download
            if let url = URL(string: download.downloadUrl) {
                previewPlayer = AVPlayer(url: url)
                previewPlayer?.play()
            }
            HoopsAccessibility.announce("Cloud AI edit rendered.")
        } catch {
            phase = .failed
            errorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
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
        phase = .planning
        HoopsAccessibility.announce("Revising cloud AI edit.")
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
            HoopsAccessibility.announce("Revision ready. Render revision to create a new video.")
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
        previewPlayer = nil
        downloadResponse = nil
        localShareURL = nil
        phase = .renderRequested
        HoopsAccessibility.announce("Rendering revised cloud AI edit.")
        defer { isWorking = false }

        do {
            let requested = try await cloudEditService.requestRevisionRender(
                editJobID: editJob.editJobId,
                revisionID: revisionResponse.revisionId,
                installID: viewModel.installID
            )
            renderStatus = requested
            phase = requested.status

            let finalStatus = try await cloudEditService.pollRenderStatus(
                editJobID: editJob.editJobId,
                installID: viewModel.installID
            )
            renderStatus = finalStatus
            phase = finalStatus.status

            guard finalStatus.status == .rendered else {
                throw CloudEditError.backend(
                    code: finalStatus.failureReason ?? "render_failed",
                    message: finalStatus.failureReason ?? "Cloud revision rendering did not finish."
                )
            }

            let download = try await cloudEditService.fetchDownloadURL(
                editJobID: editJob.editJobId,
                installID: viewModel.installID
            )
            downloadResponse = download
            if let url = URL(string: download.downloadUrl) {
                previewPlayer = AVPlayer(url: url)
                previewPlayer?.play()
            }
            HoopsAccessibility.announce("Revised cloud AI edit rendered.")
        } catch {
            phase = .failed
            errorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            HoopsAccessibility.announce("Cloud revision render failed.")
        }
    }

    @MainActor
    private func prepareShareSheet() async {
        guard var downloadResponse else { return }
        isPreparingShare = true
        errorMessage = nil
        defer { isPreparingShare = false }

        do {
            if downloadResponse.expiresAt <= Date().addingTimeInterval(30), let editJob {
                downloadResponse = try await cloudEditService.fetchDownloadURL(
                    editJobID: editJob.editJobId,
                    installID: viewModel.installID
                )
                self.downloadResponse = downloadResponse
            }
            let temporaryURL: URL
            do {
                temporaryURL = try await cloudEditService.downloadRenderedVideo(from: downloadResponse)
            } catch CloudEditError.downloadURLExpired {
                guard let editJob else {
                    throw CloudEditError.downloadURLExpired
                }
                let freshDownload = try await cloudEditService.fetchDownloadURL(
                    editJobID: editJob.editJobId,
                    installID: viewModel.installID
                )
                self.downloadResponse = freshDownload
                temporaryURL = try await cloudEditService.downloadRenderedVideo(from: freshDownload)
            }
            viewModel.attachCloudRenderedExport(from: temporaryURL)
            localShareURL = viewModel.exportService.exportedURL ?? temporaryURL
            showingShareSheet = true
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    #if DEBUG
    private static var shouldSimulateRenderFailure: Bool {
        AIEditUISmokeConfig.isEnabled && AIEditUISmokeConfig.fixture == .failingRender
    }
    #endif
}
