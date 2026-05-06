import AVKit
import SwiftUI

enum AIEditPresentation {
    case sheet
    case exportSection
}

struct AIEditView: View {
    @Bindable var viewModel: HighlightsViewModel
    let isProUser: Bool
    var presentation: AIEditPresentation = .sheet

    @Environment(\.dismiss) private var dismiss
    @State private var selectedPreset: CloudEditPreset = .personalHighlight
    @State private var selectedAspectRatio: CloudEditAspectRatio = CloudEditPreset.personalHighlight.aspectRatio
    @State private var selectedDuration = CloudEditPreset.personalHighlight.durationOptions[1]
    @State private var phase: CloudEditRenderState = .planning
    @State private var editJob: CloudEditJobResponse?
    @State private var editPlan: CloudEditPlanSummary?
    @State private var policySummary: CloudEditPolicySummary?
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
        Group {
            switch presentation {
            case .sheet:
                sheetBody
            case .exportSection:
                workflowContent
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
    }

    private var sheetBody: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.18)

                ScrollView {
                    workflowContent
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
        }
    }

    private var workflowContent: some View {
        VStack(spacing: 18) {
            heroCard
            stylePicker
            formatPicker
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
        .onChange(of: selectedPreset) { _, preset in
            selectedAspectRatio = preset.aspectRatio
            selectedDuration = defaultDuration(for: preset)
        }
    }

    private var heroCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("AI Edit Agent", systemImage: "wand.and.stars")
                .font(.title2.bold())
                .foregroundStyle(.white)
                .accessibilityIdentifier("export.aiEdit.section")

            Text("Hoopclips uploads the selected source to cloud services, creates the edit there, and stores the finished MP4 temporarily for preview and sharing.")
                .font(.subheadline)
                .foregroundStyle(AppTheme.subtleText)

            HStack(spacing: 8) {
                aiChip(icon: "film.stack.fill", text: "\(viewModel.keptClips.count) kept clips")
                aiChip(icon: selectedAspectRatio.icon, text: selectedAspectRatio.rawValue)
                aiChip(icon: "timer", text: "\(activePolicy.displayName): \(activePolicy.maxRenderSeconds)s max")
            }

            Text(policyLimitText)
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText.opacity(0.92))
                .accessibilityIdentifier("export.aiEdit.policy.limitLabel")
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.accentPurple.opacity(0.22), glow: AppTheme.neonPurple, glowOpacity: 0.10)
    }

    private var stylePicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Template Pack")
                .font(.headline)
                .foregroundStyle(.white)

            ForEach(CloudEditPreset.allCases) { preset in
                Button {
                    selectedPreset = preset
                } label: {
                    HStack(alignment: .top, spacing: 12) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 12)
                                .fill(selectedPreset == preset ? AppTheme.accentPurple.opacity(0.32) : AppTheme.cardBg.opacity(0.86))
                                .frame(width: 44, height: 44)
                            Image(systemName: preset.icon)
                                .font(.headline)
                                .foregroundStyle(selectedPreset == preset ? AppTheme.warningYellow : AppTheme.neonPurple)
                        }
                        VStack(alignment: .leading, spacing: 3) {
                            HStack(spacing: 6) {
                                Text(preset.title)
                                    .font(.subheadline.bold())
                                    .foregroundStyle(.white)
                                if selectedPreset == preset {
                                    Image(systemName: "checkmark.seal.fill")
                                        .font(.caption)
                                        .foregroundStyle(AppTheme.successGreen)
                                }
                            }
                            Text(preset.subtitle)
                                .font(.caption.bold())
                                .foregroundStyle(AppTheme.warningYellow)
                            Text(preset.bestFor)
                                .font(.caption)
                                .foregroundStyle(AppTheme.subtleText)
                                .fixedSize(horizontal: false, vertical: true)
                            Text(preset.styleSummary)
                                .font(.caption2)
                                .foregroundStyle(AppTheme.subtleText.opacity(0.92))
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        Spacer()
                    }
                    .padding(14)
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
                ForEach(displayedDurationOptions, id: \.self) { duration in
                    Button {
                        if duration <= activePolicy.maxRenderSeconds {
                            selectedDuration = duration
                        }
                    } label: {
                        Text("\(duration)s")
                            .font(.subheadline.bold())
                            .foregroundStyle(duration > activePolicy.maxRenderSeconds ? AppTheme.subtleText.opacity(0.45) : (selectedDuration == duration ? .white : AppTheme.subtleText))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 10)
                            .background(selectedDuration == duration ? AppTheme.accentPurple : AppTheme.cardBg.opacity(duration > activePolicy.maxRenderSeconds ? 0.45 : 1), in: .capsule)
                    }
                    .buttonStyle(.plain)
                    .disabled(duration > activePolicy.maxRenderSeconds)
                    .accessibilityLabel("\(duration) seconds")
                    .accessibilityIdentifier(durationAccessibilityIdentifier(for: duration))
                    .accessibilityValue(duration > activePolicy.maxRenderSeconds ? "Unavailable on \(activePolicy.displayName)" : (selectedDuration == duration ? "Selected" : "Not selected"))
                }
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.04)
    }

    private var formatPicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Target Format")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
                Text(selectedAspectRatio.rawValue)
                    .font(.subheadline.monospacedDigit().bold())
                    .foregroundStyle(AppTheme.warningYellow)
            }

            HStack(spacing: 8) {
                ForEach([CloudEditAspectRatio.vertical, .widescreen], id: \.rawValue) { aspectRatio in
                    Button {
                        selectedAspectRatio = aspectRatio
                    } label: {
                        VStack(spacing: 6) {
                            Image(systemName: aspectRatio.icon)
                                .font(.headline)
                            Text(aspectRatio.title)
                                .font(.caption.bold())
                            Text(aspectRatio.subtitle)
                                .font(.caption2)
                                .lineLimit(2)
                                .multilineTextAlignment(.center)
                        }
                        .foregroundStyle(selectedAspectRatio == aspectRatio ? .white : AppTheme.subtleText)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(selectedAspectRatio == aspectRatio ? AppTheme.accentPurple : AppTheme.cardBg, in: .rect(cornerRadius: 12))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(aspectRatio.title)
                    .accessibilityIdentifier(formatAccessibilityIdentifier(for: aspectRatio))
                    .accessibilityValue(selectedAspectRatio == aspectRatio ? "Selected" : "Not selected")
                    .accessibilityHint("Sets the AI edit output format.")
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
                    .accessibilityIdentifier("export.aiEdit.statusLabel")
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
                Text(viewModel.cloudEditUnavailableReason ?? renderStateGuidance)
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
                .accessibilityIdentifier("export.aiEdit.preview")
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
                    .accessibilityIdentifier("export.aiEdit.failure.reasonLabel")
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
            .accessibilityIdentifier(revisionResponse != nil && downloadResponse == nil ? "export.aiEdit.renderRevisionButton" : "export.aiEdit.generateButton")
            .accessibilityHint("Requests a cloud edit plan and render.")

            if phase == .failed {
                Button(action: startEdit) {
                    Label("Try Again", systemImage: "arrow.clockwise")
                        .font(.caption.bold())
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                }
                .buttonStyle(.bordered)
                .tint(AppTheme.warningYellow)
                .disabled(isWorking || !viewModel.canRequestCloudEdit)
                .accessibilityIdentifier("export.aiEdit.retryButton")
                .accessibilityHint("Retries the cloud render when the backend allows it.")
            }

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
                .accessibilityIdentifier("export.aiEdit.shareButton")
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
                        .accessibilityIdentifier("export.aiEdit.revision.card")
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
                    .accessibilityElement(children: .ignore)
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
                    .accessibilityIdentifier("export.aiEdit.revision.summaryLabel")
            }
        }
        .padding(14)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.neonPurple.opacity(0.18), glow: AppTheme.neonPurple, glowOpacity: 0.05)
    }

    private var statusIcon: String {
        switch phase {
        case .rendered:
            return "checkmark.seal.fill"
        case .failed, .failedTimeout, .cancelled:
            return "exclamationmark.triangle.fill"
        case .renderRequested, .planning, .planReady, .created, .queued, .rendering:
            return "cloud.fill"
        }
    }

    private var statusColor: Color {
        switch phase {
        case .rendered:
            return AppTheme.successGreen
        case .failed, .failedTimeout, .cancelled:
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
        return downloadResponse == nil ? "Generate Highlight Reel" : "Render Again"
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

    private var activePolicy: CloudEditPolicySummary {
        policySummary ?? (isProUser ? .proDefault : .freeDefault)
    }

    private var policyLimitText: String {
        let policy = activePolicy
        let watermark = policy.watermarkRequired || policy.outroRequired ? "watermark/outro included" : "no required watermark"
        return "\(policy.displayName): \(policy.maxDailyRenders) AI edits/day, \(policy.maxRevisionsPerEdit) revisions/edit, \(policy.maxOutputResolution) max, \(watermark)."
    }

    private var renderStateGuidance: String {
        switch phase {
        case .planning:
            return "Ready to request a cloud-rendered AI edit."
        case .planReady:
            return "Plan is ready. Hoopclips will render the MP4 in the cloud."
        case .renderRequested, .created, .queued:
            return "Your highlight reel is queued. Please keep Hoopclips open."
        case .rendering:
            return "Rendering your highlight reel in the cloud."
        case .rendered:
            return "Your MP4 is ready to preview and share."
        case .failed:
            return "Render failed. You can retry when the backend says it is safe."
        case .failedTimeout:
            return "Rendering timed out. Try a shorter edit or retry when the backend is ready."
        case .cancelled:
            return "Render was cancelled."
        }
    }

    private func defaultDuration(for preset: CloudEditPreset) -> Int {
        let available = preset.durationOptions.filter { $0 <= activePolicy.maxRenderSeconds }
        return available.dropFirst().first ?? available.first ?? min(preset.durationOptions[0], activePolicy.maxRenderSeconds)
    }

    private var displayedDurationOptions: [Int] {
        var options = selectedPreset.durationOptions
        if !options.contains(selectedDuration) {
            options.insert(selectedDuration, at: 0)
        }
        return options
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
            return "export.aiEdit.style.personalHighlight"
        case .fullGameHighlight:
            return "export.aiEdit.style.fullGameHighlight"
        case .coachReview:
            return "export.aiEdit.style.coachReview"
        }
    }

    private func durationAccessibilityIdentifier(for duration: Int) -> String {
        "export.aiEdit.length.\(duration)s"
    }

    private func formatAccessibilityIdentifier(for aspectRatio: CloudEditAspectRatio) -> String {
        switch aspectRatio {
        case .vertical:
            return "export.aiEdit.format.vertical"
        case .widescreen:
            return "export.aiEdit.format.widescreen"
        case .source:
            return "export.aiEdit.format.source"
        }
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
                aspectRatio: selectedAspectRatio,
                isProUser: isProUser
            )
            let job = try await cloudEditService.createEditJob(request)
            editJob = job
            policySummary = job.policy ?? (request.planTier == .pro ? .proDefault : .freeDefault)

            let planResponse = try await cloudEditService.fetchEditPlan(
                editJobID: job.editJobId,
                installID: viewModel.installID
            )
            editPlan = planResponse.plan
            policySummary = planResponse.policy ?? policySummary
            phase = .planReady
            LaunchTelemetry.shared.recordAIEditEvent(
                "edit_plan.created",
                editJobID: job.editJobId,
                templateID: planResponse.plan.templateId,
                planTier: request.planTier.rawValue
            )
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
            policySummary = requested.policy ?? policySummary
            phase = requested.status

            let finalStatus = try await cloudEditService.pollRenderStatus(
                editJobID: job.editJobId,
                installID: viewModel.installID
            )
            renderStatus = finalStatus
            policySummary = finalStatus.policy ?? policySummary
            phase = finalStatus.status

            guard finalStatus.status == .rendered else {
                let code = finalStatus.failureReason ?? "render_failed"
                throw CloudEditError.backend(
                    code: code,
                    message: CloudEditError.friendlyBackendMessage(code: code, fallback: "Cloud rendering did not finish.")
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
                LaunchTelemetry.shared.recordAIEditEvent(
                    "ios.preview.loaded",
                    editJobID: job.editJobId,
                    renderJobID: finalStatus.renderJobId,
                    templateID: planResponse.plan.templateId,
                    planTier: request.planTier.rawValue
                )
            }
            HoopsAccessibility.announce("Cloud AI edit rendered.")
        } catch {
            phase = .failed
            errorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            LaunchTelemetry.shared.recordAIEditEvent("render.failed", editJobID: editJob?.editJobId, templateID: editPlan?.templateId, failureReason: errorMessage)
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
            LaunchTelemetry.shared.recordAIEditEvent(
                "edit_revision.created",
                editJobID: editJob.editJobId,
                revisionID: revision.revisionId,
                templateID: revision.revisedPlan.templateId,
                planTier: policySummary?.planTier.rawValue
            )
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
            policySummary = requested.policy ?? policySummary
            phase = requested.status

            let finalStatus = try await cloudEditService.pollRenderStatus(
                editJobID: editJob.editJobId,
                installID: viewModel.installID
            )
            renderStatus = finalStatus
            policySummary = finalStatus.policy ?? policySummary
            phase = finalStatus.status

            guard finalStatus.status == .rendered else {
                let code = finalStatus.failureReason ?? "render_failed"
                throw CloudEditError.backend(
                    code: code,
                    message: CloudEditError.friendlyBackendMessage(code: code, fallback: "Cloud revision rendering did not finish.")
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
                LaunchTelemetry.shared.recordAIEditEvent(
                    "ios.preview.loaded",
                    editJobID: editJob.editJobId,
                    renderJobID: finalStatus.renderJobId,
                    revisionID: revisionResponse.revisionId,
                    templateID: revisionResponse.revisedPlan.templateId,
                    planTier: policySummary?.planTier.rawValue
                )
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
                errorMessage = "Download URL expired, refreshing..."
                downloadResponse = try await cloudEditService.fetchDownloadURL(
                    editJobID: editJob.editJobId,
                    installID: viewModel.installID
                )
                self.downloadResponse = downloadResponse
                errorMessage = nil
            }
            let temporaryURL: URL
            do {
                temporaryURL = try await cloudEditService.downloadRenderedVideo(from: downloadResponse)
            } catch CloudEditError.downloadURLExpired {
                guard let editJob else {
                    throw CloudEditError.downloadURLExpired
                }
                errorMessage = "Download URL expired, refreshing..."
                let freshDownload = try await cloudEditService.fetchDownloadURL(
                    editJobID: editJob.editJobId,
                    installID: viewModel.installID
                )
                self.downloadResponse = freshDownload
                temporaryURL = try await cloudEditService.downloadRenderedVideo(from: freshDownload)
                errorMessage = nil
            }
            viewModel.attachCloudRenderedExport(from: temporaryURL)
            localShareURL = viewModel.exportService.exportedURL ?? temporaryURL
            showingShareSheet = true
            LaunchTelemetry.shared.recordAIEditEvent(
                "ios.share.opened",
                editJobID: editJob?.editJobId,
                renderJobID: downloadResponse.renderJobId,
                revisionID: revisionResponse?.revisionId,
                templateID: editPlan?.templateId,
                planTier: policySummary?.planTier.rawValue
            )
        } catch {
            let failureDescription = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            errorMessage = "Could not prepare the MP4 for sharing. Try again in a moment."
            LaunchTelemetry.shared.recordAIEditEvent(
                "ios.share.failed",
                editJobID: editJob?.editJobId,
                renderJobID: downloadResponse.renderJobId,
                revisionID: revisionResponse?.revisionId,
                templateID: editPlan?.templateId,
                planTier: policySummary?.planTier.rawValue,
                failureReason: failureDescription
            )
            HoopsAccessibility.announce("Could not open sharing for this render.")
        }
    }

    #if DEBUG
    private static var shouldSimulateRenderFailure: Bool {
        AIEditUISmokeConfig.isEnabled && AIEditUISmokeConfig.fixture == .failingRender
    }
    #endif
}
