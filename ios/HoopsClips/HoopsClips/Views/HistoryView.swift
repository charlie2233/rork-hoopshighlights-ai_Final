import SwiftUI
import AVFoundation
import AVKit
import UIKit

struct HistoryView: View {
    @Bindable var viewModel: HighlightsViewModel
    let onReturnToPlayer: (() -> Void)?
    @State private var selectedProject: PersistedProjectRecord?
    @State private var projectPendingDeletion: PersistedProjectRecord?
    @State private var showingDeleteProjectConfirmation = false
    @State private var showingClearHistoryConfirmation = false
    @State private var renamingProjectID: UUID?
    @State private var renameDraft = ""
    @FocusState private var focusedRenameProjectID: UUID?
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.18)

                if viewModel.historyProjects.isEmpty && !shouldShowCurrentWorkCard {
                    emptyState
                } else {
                    ScrollView {
                        VStack(spacing: 16) {
                            if shouldShowCurrentWorkCard {
                                currentWorkStatusCard
                            }

                            if let currentProject = viewModel.currentProjectRecord,
                               !shouldShowCurrentWorkCard {
                                projectSection(
                                    title: "Current Project",
                                    icon: "bolt.circle.fill",
                                    subtitle: currentProjectSectionSubtitle,
                                    accent: AppTheme.rimOrange,
                                    accessibilityIdentifier: "history.section.currentProject",
                                    projects: [currentProject]
                                )
                            }

                            if !viewModel.pastProjectRecords.isEmpty {
                                projectSection(
                                    title: "Past Projects",
                                    icon: "clock.arrow.circlepath",
                                    subtitle: "Reopen past runs and replay saved videos",
                                    accent: AppTheme.courtBlue,
                                    accessibilityIdentifier: "history.section.pastProjects",
                                    projects: viewModel.pastProjectRecords
                                )
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                        .padding(.bottom, 100)
                    }
                }
            }
            .navigationTitle("History")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    if !viewModel.historyProjects.isEmpty {
                        Button("Clear") {
                            showingClearHistoryConfirmation = true
                        }
                        .foregroundStyle(AppTheme.dangerRed)
                    }
                }
            }
            .sheet(item: $selectedProject) { project in
                HistoryProjectDetailView(
                    project: project,
                    isCurrentProject: viewModel.currentProjectID == project.id,
                    canOpenProject: viewModel.canOpenProject(project),
                    sourceURL: viewModel.projectSourceURL(for: project),
                    latestExportURL: viewModel.projectLatestExportURL(for: project),
                    thumbnailImage: viewModel.projectThumbnailImage(for: project),
                    onOpenProject: {
                        viewModel.openProject(id: project.id)
                    },
                    onDeleteProject: {
                        viewModel.deleteProject(id: project.id)
                    }
                )
            }
            .alert("Delete this project?", isPresented: $showingDeleteProjectConfirmation, presenting: projectPendingDeletion) { project in
                Button("Delete Project", role: .destructive) {
                    viewModel.deleteProject(id: project.id)
                    if selectedProject?.id == project.id {
                        selectedProject = nil
                    }
                    projectPendingDeletion = nil
                }
                Button("Cancel", role: .cancel) {
                    projectPendingDeletion = nil
                }
            } message: { project in
                Text("This removes \"\(project.displayTitle)\" and its saved files from this device.")
            }
            .alert("Clear all history?", isPresented: $showingClearHistoryConfirmation) {
                Button("Clear History", role: .destructive) {
                    selectedProject = nil
                    viewModel.clearProjectHistory()
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This deletes every saved HoopClips project, including saved source videos, exports, thumbnails, and custom audio stored in history.")
            }
            .onChange(of: focusedRenameProjectID) { oldValue, newValue in
                guard let oldValue,
                      oldValue != newValue,
                      renamingProjectID == oldValue,
                      let project = viewModel.historyProjects.first(where: { $0.id == oldValue }) else {
                    return
                }
                commitRename(for: project)
            }
        }
    }

    private var emptyState: some View {
        HoopsEmptyStateCard(
            title: "Projects save here",
            message: "Start on Player. After you import and analyze a video, your project will appear here.",
            icon: "clock.arrow.circlepath"
        )
        .accessibilityIdentifier("history.emptyState")
    }

    private var shouldShowCurrentWorkCard: Bool {
        viewModel.isVideoImportInProgress
            || viewModel.analysisService.isAnalyzing
            || viewModel.isCloudTeamScanInProgress
            || viewModel.canRetryUploadAfterCancel
    }

    private var currentProjectSectionSubtitle: String {
        shouldShowCurrentWorkCard
            ? "This is still saved while HoopClips works"
            : "Your active session is saved automatically"
    }

    private var currentWorkProgress: Double {
        if viewModel.analysisService.isAnalyzing {
            return min(max(viewModel.analysisService.progress, 0.03), 0.98)
        }
        if viewModel.isVideoImportInProgress {
            return 0.06
        }
        if viewModel.isCloudTeamScanInProgress {
            return 0.18
        }
        if viewModel.canRetryUploadAfterCancel {
            return 0
        }
        return 0
    }

    private var currentWorkTitle: String {
        if viewModel.canRetryUploadAfterCancel {
            return "Upload paused"
        }
        if viewModel.isVideoImportInProgress {
            return "Importing video"
        }
        if viewModel.isCloudTeamScanInProgress {
            return "Checking teams"
        }
        if viewModel.analysisService.statusMessage.lowercased().contains("upload") {
            return "Uploading to cloud"
        }
        return "Analyzing video"
    }

    private var currentWorkSubtitle: String {
        if viewModel.canRetryUploadAfterCancel {
            if let savedUploadProgressText = currentWorkSavedUploadProgressText {
                return "Your video is still here. \(savedUploadProgressText). Tap Retry when ready."
            }
            return "Your video is still here. Go back to Player and tap Retry upload when ready."
        }
        if let importStatus = viewModel.videoImportStatusMessage, !importStatus.isEmpty {
            return importStatus
        }
        if viewModel.isCloudTeamScanInProgress, let teamStatus = viewModel.cloudTeamScanStatusMessage, !teamStatus.isEmpty {
            return teamStatus
        }
        if !viewModel.analysisService.statusMessage.isEmpty {
            return viewModel.analysisService.statusMessage
        }
        return "HoopClips is keeping this project alive while work continues."
    }

    private var currentWorkSavedUploadProgressText: String? {
        CloudAnalysisProgressCopy.uploadResumeProgressSummary(
            from: CloudAnalysisService.pendingBackgroundUploadManifestSummary()
        )
    }

    private var currentWorkTint: Color {
        if viewModel.canRetryUploadAfterCancel {
            return AppTheme.warningYellow
        }
        if viewModel.isVideoImportInProgress || viewModel.analysisService.statusMessage.lowercased().contains("upload") {
            return Color.cyan
        }
        if viewModel.isCloudTeamScanInProgress {
            return AppTheme.rimOrange
        }
        return AppTheme.neonPurple
    }

    private var currentWorkIcon: String {
        if viewModel.canRetryUploadAfterCancel {
            return "arrow.clockwise.icloud.fill"
        }
        if viewModel.isVideoImportInProgress {
            return "square.and.arrow.down.fill"
        }
        if viewModel.isCloudTeamScanInProgress {
            return "person.3.sequence.fill"
        }
        if viewModel.analysisService.statusMessage.lowercased().contains("upload") {
            return "icloud.and.arrow.up.fill"
        }
        return "sparkles.tv.fill"
    }

    private var currentWorkStatusCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: currentWorkIcon)
                    .font(.title3.weight(.heavy))
                    .foregroundStyle(currentWorkTint)
                    .frame(width: 36, height: 36)
                    .background(currentWorkTint.opacity(0.14), in: Circle())
                    .accessibilityHidden(true)

                VStack(alignment: .leading, spacing: 5) {
                    Text(currentWorkTitle)
                        .font(.headline.weight(.heavy))
                        .foregroundStyle(.white)
                        .fixedSize(horizontal: false, vertical: true)

                    Text(currentWorkSubtitle)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.78))
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 5 : 3)
                        .minimumScaleFactor(0.84)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 0)

                Spacer(minLength: 0)
            }

            ProgressView(value: currentWorkProgress)
                .tint(currentWorkTint)
                .accessibilityLabel(currentWorkTitle)
                .accessibilityValue("\(Int(currentWorkProgress * 100)) percent")

            Text(viewModel.canRetryUploadAfterCancel ? currentWorkRetryNote : "Active work stays saved.")
                .font(.caption2.weight(.bold))
                .foregroundStyle(currentWorkTint)
                .fixedSize(horizontal: false, vertical: true)

            if let onReturnToPlayer {
                Button {
                    onReturnToPlayer()
                } label: {
                    Label(viewModel.canRetryUploadAfterCancel ? "Retry on Player" : "Back to Player", systemImage: "play.circle.fill")
                        .font(.caption.weight(.heavy))
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 11)
                        .background(currentWorkTint.opacity(0.22), in: .rect(cornerRadius: 14))
                        .overlay(
                            RoundedRectangle(cornerRadius: 14)
                                .stroke(currentWorkTint.opacity(0.32), lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("history.currentWork.returnToPlayer")
            }
        }
        .padding(16)
        .background(
            LinearGradient(
                colors: [
                    currentWorkTint.opacity(0.18),
                    AppTheme.surfaceBg.opacity(0.74)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: .rect(cornerRadius: 18)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 18)
                .stroke(currentWorkTint.opacity(0.24), lineWidth: 1)
        )
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("history.currentWorkStatusCard")
    }

    private var currentWorkRetryNote: String {
        if let currentWorkSavedUploadProgressText {
            return "\(currentWorkSavedUploadProgressText). Nothing was deleted."
        }
        return "Nothing was deleted."
    }

    private func projectSection(
        title: String,
        icon: String,
        subtitle: String,
        accent: Color,
        accessibilityIdentifier: String,
        projects: [PersistedProjectRecord]
    ) -> some View {
        VStack(spacing: 12) {
            RorkSectionHeader(
                title: title,
                icon: icon,
                subtitle: subtitle,
                accent: accent
            )

            ForEach(projects) { project in
                VStack(spacing: 8) {
                    historyRow(for: project)

                    LazyVGrid(columns: historyActionGridColumns, alignment: .leading, spacing: 8) {
                        Button {
                            selectedProject = project
                        } label: {
                            historyActionLabel(title: "Details", icon: "info.circle.fill", tint: AppTheme.courtBlue)
                                .accessibilityLabel("Show saved project details for \(project.displayTitle)")
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("history.project.details")

                        Button {
                            viewModel.openProject(id: project.id)
                        } label: {
                            historyActionLabel(
                                title: historyResumeActionTitle(for: project),
                                icon: "arrow.counterclockwise.circle.fill",
                                tint: viewModel.canOpenProject(project) ? AppTheme.successGreen : AppTheme.warningYellow
                            )
                            .accessibilityLabel(resumeAccessibilityLabel(for: project))
                        }
                        .buttonStyle(.plain)
                        .disabled(!viewModel.canOpenProject(project) || viewModel.currentProjectID == project.id)
                        .opacity((viewModel.canOpenProject(project) && viewModel.currentProjectID != project.id) ? 1.0 : 0.54)
                        .accessibilityIdentifier("history.project.resume")

                        Button(role: .destructive) {
                            requestDelete(project)
                        } label: {
                            historyActionLabel(title: "Delete", icon: "trash.fill", tint: AppTheme.dangerRed)
                                .accessibilityLabel("Delete \(project.displayTitle)")
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("history.project.delete")
                    }
                }
                .contextMenu {
                    Button {
                        beginRenaming(project)
                    } label: {
                        Label("Rename Project", systemImage: "pencil")
                    }

                    Button(role: .destructive) {
                        requestDelete(project)
                    } label: {
                        Label("Delete Project", systemImage: "trash")
                    }
                }
            }
        }
        .padding(16)
        .rorkCard(
            cornerRadius: 18,
            fill: AppTheme.accentCardFill(accent, opacity: 0.14),
            stroke: accent.opacity(0.22),
            glow: accent,
            glowOpacity: 0.06
        )
        .accessibilityIdentifier("history.detail.actions")
    }

    private func historyRow(for project: PersistedProjectRecord) -> some View {
        Group {
            if dynamicTypeSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 12) {
                    projectThumbnail(for: project, isExpanded: true)
                    historySummary(for: project)
                }
            } else {
                HStack(alignment: .top, spacing: 12) {
                    projectThumbnail(for: project, isExpanded: false)
                    historySummary(for: project)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(
            LinearGradient(
                colors: [
                    historyProjectAccent(for: project).opacity(0.16),
                    AppTheme.surfaceBg.opacity(0.70)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 14)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(historyProjectAccent(for: project).opacity(0.20), lineWidth: 1)
            )
    }

    private func projectThumbnail(for project: PersistedProjectRecord, isExpanded: Bool) -> some View {
        Group {
            if let thumbnail = viewModel.projectThumbnailImage(for: project) {
                Image(uiImage: thumbnail)
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            } else {
                ZStack {
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(AppTheme.surfaceBg)
                    Image(systemName: project.hasLatestExport ? "play.rectangle.fill" : "video.fill")
                        .font(isExpanded ? .title2 : .title3)
                        .foregroundStyle(historyProjectAccent(for: project))
                }
            }
        }
        .frame(maxWidth: isExpanded ? .infinity : 92)
        .frame(width: isExpanded ? nil : 92, height: isExpanded ? 132 : 56)
        .clipShape(.rect(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(historyProjectAccent(for: project).opacity(0.24), lineWidth: 1)
        )
        .accessibilityHidden(true)
    }

    private func historySummary(for project: PersistedProjectRecord) -> some View {
        VStack(alignment: .leading, spacing: dynamicTypeSize.isAccessibilitySize ? 10 : 6) {
            HStack(alignment: .top) {
                projectTitleEditor(for: project)
                Spacer(minLength: 0)
            }

            Text(historyStatusLine(for: project))
                .font(.caption)
                .foregroundStyle(.white.opacity(0.78))
                .fixedSize(horizontal: false, vertical: true)

            LazyVGrid(columns: historyBadgeGridColumns, alignment: .leading, spacing: 8) {
                historyBadge(
                    icon: "film.stack.fill",
                    text: project.historyClipBadgeText,
                    tint: AppTheme.courtBlue,
                    accessibilityLabel: project.historyClipBadgeAccessibilityText
                )

                if project.hasLatestExport {
                    historyBadge(
                        icon: "square.and.arrow.up.fill",
                        text: project.historyExportBadgeText,
                        tint: AppTheme.successGreen,
                        accessibilityLabel: "Saved reel ready to preview or share"
                    )
                }

                if let analysisMode = project.analysisMode {
                    historyBadge(
                        icon: userFacingAnalysisModeIcon(analysisMode),
                        text: userFacingAnalysisModeLabel(analysisMode),
                        tint: AppTheme.rimOrange
                    )
                }

                if let teamTarget = projectTeamTargetShortLabel(project) {
                    historyBadge(
                        icon: project.highlightTeamSelection?.mode == .team ? "person.2.fill" : "person.3.fill",
                        text: teamTarget,
                        tint: AppTheme.rimOrange
                    )
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private func projectTitleEditor(for project: PersistedProjectRecord) -> some View {
        if renamingProjectID == project.id {
            TextField("Project title", text: $renameDraft, axis: .vertical)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.white)
                .textInputAutocapitalization(.words)
                .submitLabel(.done)
                .lineLimit(1...3)
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
                .background(AppTheme.cardBg, in: .rect(cornerRadius: 10))
                .overlay {
                    RoundedRectangle(cornerRadius: 10)
                        .stroke(AppTheme.neonPurple.opacity(0.28), lineWidth: 1)
                }
                .focused($focusedRenameProjectID, equals: project.id)
                .onSubmit {
                    commitRename(for: project)
                }
                .accessibilityLabel("Project title")
                .accessibilityHint("Rename this saved project.")
        } else {
            Button {
                beginRenaming(project)
            } label: {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text(project.displayTitle)
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                        .minimumScaleFactor(0.88)
                        .fixedSize(horizontal: false, vertical: true)
                        .layoutPriority(1)

                    Image(systemName: "pencil")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(AppTheme.subtleText)
                        .accessibilityHidden(true)
                }
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity, alignment: .leading)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Rename \(project.displayTitle)")
            .accessibilityHint("Edit this project title.")
        }
    }

    private func resumeAccessibilityLabel(for project: PersistedProjectRecord) -> String {
        if viewModel.currentProjectID == project.id {
            return "\(project.displayTitle) is already open"
        }
        if !viewModel.canOpenProject(project) {
            return "\(project.displayTitle) cannot be resumed because its source video is missing"
        }
        return "Resume \(project.displayTitle)"
    }

    private func historyStatusLine(for project: PersistedProjectRecord) -> String {
        let date = project.updatedAt.formatted(date: .abbreviated, time: .shortened)
        let duration = historyDurationLabel(for: project.sourceDuration)
        return "\(historyProjectStateLabel(for: project)) - \(duration) - Updated \(date)"
    }

    private func historyDurationLabel(for seconds: Double) -> String {
        guard seconds.isFinite, seconds > 0 else {
            return "video"
        }

        let totalSeconds = max(1, Int(seconds.rounded()))
        let minutes = totalSeconds / 60
        let remainingSeconds = totalSeconds % 60

        if minutes >= 60 {
            let hours = minutes / 60
            let extraMinutes = minutes % 60
            return extraMinutes > 0 ? "\(hours)h \(extraMinutes)m" : "\(hours)h"
        }

        if minutes > 0 {
            return remainingSeconds > 0 ? "\(minutes)m \(remainingSeconds)s" : "\(minutes)m"
        }

        return "\(remainingSeconds)s"
    }

    private func historyResumeActionTitle(for project: PersistedProjectRecord) -> String {
        if viewModel.currentProjectID == project.id {
            return "Current"
        }
        if !viewModel.canOpenProject(project) {
            return "Missing source"
        }
        return "Resume"
    }

    private func historyProjectStateLabel(for project: PersistedProjectRecord) -> String {
        let summary = project.analysisStatusSummary?.lowercased() ?? ""
        if !viewModel.canOpenProject(project) {
            return "Source missing"
        }
        if summary.contains("cancel") || summary.contains("paused") {
            return "Upload paused"
        }
        if summary.contains("upload") {
            return "Upload saved"
        }
        if summary.contains("analy") || summary.contains("preparing") || summary.contains("team scan") {
            return "Analysis saved"
        }
        if project.hasLatestExport {
            return "Reel saved"
        }
        if project.keptClipCount > 0 {
            return "Ready to review"
        }
        if project.totalClipCount > 0 {
            return "Clips found"
        }
        if project.lastAnalyzedAt != nil {
            return "Analyzed"
        }
        return "Imported"
    }

    private var historyActionGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize.isAccessibilitySize ? 150 : 118
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 260), spacing: 8, alignment: .top)
        ]
    }

    private var historyBadgeGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize.isAccessibilitySize ? 128 : 92
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 220), spacing: 8, alignment: .top)
        ]
    }

    private func historyBadge(icon: String, text: String, tint: Color, accessibilityLabel: String? = nil) -> some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption2.weight(.semibold))
            Text(text)
                .font(.caption2.weight(.medium))
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                .minimumScaleFactor(0.86)
                .fixedSize(horizontal: false, vertical: true)
        }
        .foregroundStyle(.white)
        .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 38 : 28, alignment: .center)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(tint.opacity(0.13), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .stroke(tint.opacity(0.22), lineWidth: 1)
        )
        .accessibilityLabel(accessibilityLabel ?? text)
    }

    private func historyActionLabel(title: String, icon: String, tint: Color) -> some View {
        Label(title, systemImage: icon)
            .font(.caption.bold())
            .foregroundStyle(tint)
            .multilineTextAlignment(.center)
            .lineLimit(2)
            .minimumScaleFactor(0.88)
            .fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, minHeight: dynamicTypeSize.isAccessibilitySize ? 48 : 36)
            .padding(.vertical, 10)
            .background(tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(tint.opacity(0.26), lineWidth: 1)
            )
    }

    private func historyProjectAccent(for project: PersistedProjectRecord) -> Color {
        if viewModel.currentProjectID == project.id {
            return AppTheme.rimOrange
        }
        if project.hasLatestExport {
            return AppTheme.successGreen
        }
        if project.cloudAnalysisJobID != nil {
            return AppTheme.courtBlue
        }
        return AppTheme.rimOrange
    }

    private func beginRenaming(_ project: PersistedProjectRecord) {
        renameDraft = project.displayTitle
        renamingProjectID = project.id
        Task { @MainActor in
            focusedRenameProjectID = project.id
        }
    }

    private func commitRename(for project: PersistedProjectRecord) {
        guard renamingProjectID == project.id else { return }

        let newTitle = renameDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        renamingProjectID = nil
        focusedRenameProjectID = nil

        guard !newTitle.isEmpty else { return }
        viewModel.renameProject(id: project.id, title: newTitle)
    }

    private func requestDelete(_ project: PersistedProjectRecord) {
        projectPendingDeletion = project
        showingDeleteProjectConfirmation = true
    }
}

private struct HistoryProjectDetailView: View {
    let project: PersistedProjectRecord
    let isCurrentProject: Bool
    let canOpenProject: Bool
    let sourceURL: URL?
    let latestExportURL: URL?
    let thumbnailImage: UIImage?
    let onOpenProject: () -> Void
    let onDeleteProject: () -> Void

    @Environment(\.dismiss) private var dismiss
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @State private var previewPlayer: AVPlayer?
    @AppStorage("hoops.previewAudioMuted.v1") private var previewAudioMuted = false
    @State private var previewHasAudioTrack: Bool?
    @State private var previewAudioCheckTask: Task<Void, Never>?
    @State private var previewTitle: String?
    @State private var showingDeleteConfirmation = false
    @State private var shareURL: URL?
    @State private var showingShareSheet = false
    @State private var shareErrorMessage: String?
    @State private var showingShareError = false

    var body: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.18)

                ScrollView {
                    VStack(spacing: 16) {
                        headerCard
                        playbackCard
                        actionsCard
                        timelineCard
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                    .padding(.bottom, 100)
                }
            }
            .navigationTitle(project.displayTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                    .foregroundStyle(AppTheme.neonPurple)
                }
            }
        }
        .onDisappear {
            previewPlayer?.pause()
            previewPlayer = nil
        }
        .alert("Delete this project?", isPresented: $showingDeleteConfirmation) {
            Button("Delete Project", role: .destructive) {
                onDeleteProject()
                dismiss()
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This removes \"\(project.displayTitle)\" and its saved files from this device.")
        }
        .sheet(isPresented: $showingShareSheet, onDismiss: clearShareSelection) {
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
                            showingShareError = true
                        }
                    }
                )
            } else {
                EmptyView()
            }
        }
        .alert("Share unavailable", isPresented: $showingShareError) {
            Button("OK") {
                shareErrorMessage = nil
            }
        } message: {
            Text(shareErrorMessage ?? HistoryProjectActionCopy.shareMissingMessage)
        }
    }

    private var headerCard: some View {
        VStack(spacing: 12) {
            Group {
                if let thumbnailImage {
                    Image(uiImage: thumbnailImage)
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                } else {
                    ZStack {
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .fill(AppTheme.surfaceBg)
                        Image(systemName: "video.fill")
                            .font(.largeTitle)
                            .foregroundStyle(AppTheme.neonPurple)
                    }
                }
            }
            .frame(height: 180)
            .clipShape(.rect(cornerRadius: 16))
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(AppTheme.softBorder, lineWidth: 1)
            )

            LazyVGrid(columns: detailMetricGridColumns, alignment: .leading, spacing: 10) {
                RorkMetricChip(
                    icon: "film.stack.fill",
                    value: "\(project.keptClipCount)",
                    label: "Kept",
                    tint: AppTheme.neonPurple
                )
                RorkMetricChip(
                    icon: "list.bullet.rectangle.portrait.fill",
                    value: "\(project.totalClipCount)",
                    label: "Total",
                    tint: AppTheme.warningYellow
                )
                if let analysisMode = project.analysisMode {
                    RorkMetricChip(
                        icon: userFacingAnalysisModeIcon(analysisMode),
                        value: userFacingAnalysisModeLabel(analysisMode),
                        label: "Analysis",
                        tint: AppTheme.successGreen
                    )
                }
            }

            VStack(alignment: .leading, spacing: 6) {
                detailLine(label: "Source", value: project.sourceDisplayName)
                detailLine(label: "Created", value: project.createdAt.formatted(date: .abbreviated, time: .shortened))
                detailLine(label: "Updated", value: project.updatedAt.formatted(date: .abbreviated, time: .shortened))
                if let lastExportedAt = project.lastExportedAt {
                    detailLine(label: "Saved Reel", value: lastExportedAt.formatted(date: .abbreviated, time: .shortened))
                }
                if let analysisStatusSummary = project.analysisStatusSummary, !analysisStatusSummary.isEmpty {
                    detailLine(label: "Status", value: analysisStatusSummary)
                }
                if let teamTarget = projectTeamTargetDetailLabel(project) {
                    detailLine(label: "Team", value: teamTarget)
                }
            }
        }
        .padding(16)
        .rorkCard(
            cornerRadius: 16,
            fill: AppTheme.accentCardFill(AppTheme.courtBlue, opacity: 0.11),
            stroke: AppTheme.courtBlue.opacity(0.18),
            glow: AppTheme.courtBlue,
            glowOpacity: 0.04
        )
        .accessibilityIdentifier("history.detail.playback")
    }

    private var playbackCard: some View {
        VStack(spacing: 12) {
            RorkSectionHeader(
                title: "Playback",
                icon: "play.rectangle.fill",
                subtitle: "Preview the source video or saved reel",
                accent: AppTheme.courtBlue
            )

            if let previewPlayer {
                ZStack(alignment: .topTrailing) {
                    VideoPlayer(player: previewPlayer)
                        .frame(height: 220)
                        .clipShape(.rect(cornerRadius: 16))
                        .overlay(
                            RoundedRectangle(cornerRadius: 16)
                                .stroke(AppTheme.softBorder, lineWidth: 1)
                        )
                        .accessibilityLabel("Project video preview")
                        .accessibilityValue(previewTitle ?? "Saved project media")
                        .accessibilityHint("Use playback controls to preview this saved project.")
                        .accessibilityIdentifier("history.detail.videoPreview")

                    VStack(alignment: .trailing, spacing: 8) {
                        PreviewAudioStatusChip(
                            isMuted: previewAudioMuted,
                            hasAudioTrack: previewHasAudioTrack,
                            accessibilityIdentifier: "history.preview.audioStatus"
                        )

                        Button {
                            previewAudioMuted.toggle()
                            applyHistoryPreviewAudioMute()
                        } label: {
                            Image(systemName: previewAudioMuted ? "speaker.slash.fill" : "speaker.wave.2.fill")
                                .font(.caption.weight(.bold))
                                .foregroundStyle(.white)
                                .padding(9)
                                .background(.black.opacity(0.58), in: Circle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("history.preview.muteToggle")
                        .accessibilityLabel(previewAudioMuted ? "Unmute history preview" : "Mute history preview")
                    }
                    .padding(10)
                }

                if let previewTitle {
                    Text(previewTitle)
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .accessibilityIdentifier("history.detail.previewTitle")
                }
            } else {
                VStack(spacing: 8) {
                    Image(systemName: "play.circle")
                        .font(.title)
                        .foregroundStyle(AppTheme.neonPurple)
                    Text(HistoryProjectActionCopy.emptyPreviewHint)
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .multilineTextAlignment(.center)
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 3)
                        .minimumScaleFactor(0.86)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 28)
                .background(AppTheme.surfaceBg.opacity(0.72), in: RoundedRectangle(cornerRadius: 16))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(AppTheme.softBorder, lineWidth: 1)
                )
            }
        }
        .padding(16)
        .rorkCard(
            cornerRadius: 16,
            fill: AppTheme.accentCardFill(AppTheme.courtBlue, opacity: 0.10),
            stroke: AppTheme.courtBlue.opacity(0.18),
            glow: AppTheme.courtBlue,
            glowOpacity: 0.04
        )
        .accessibilityIdentifier("history.detail.playback")
    }

    private var actionsCard: some View {
        VStack(spacing: 12) {
            RorkSectionHeader(
                title: "What next?",
                icon: "bolt.fill",
                subtitle: "Resume, watch, share.",
                accent: AppTheme.rimOrange
            )

            Button {
                onOpenProject()
                dismiss()
            } label: {
                actionLabel(
                    title: isCurrentProject ? "Currently Open" : "Resume Project",
                    subtitle: canOpenProject ? "" : HistoryProjectActionCopy.openUnavailableSubtitle,
                    icon: "arrow.counterclockwise.circle.fill",
                    tint: AppTheme.neonPurple
                )
            }
            .buttonStyle(.plain)
            .disabled(!canOpenProject || isCurrentProject)
            .opacity((canOpenProject && !isCurrentProject) ? 1.0 : 0.5)
            .accessibilityIdentifier("history.detail.resumeProject")

            Button {
                startPreview(url: sourceURL, title: "Source Video")
            } label: {
                actionLabel(
                    title: "Watch Source",
                    subtitle: sourceURL == nil ? HistoryProjectActionCopy.sourceMissingSubtitle : "",
                    icon: "video.fill",
                    tint: AppTheme.warningYellow
                )
            }
            .buttonStyle(.plain)
            .disabled(sourceURL == nil)
            .opacity(sourceURL == nil ? 0.5 : 1.0)
            .accessibilityIdentifier("history.detail.watchSource")

            Button {
                startPreview(url: latestExportURL, title: "Saved Reel")
            } label: {
                actionLabel(
                    title: "Watch Saved Reel",
                    subtitle: latestExportURL == nil ? HistoryProjectActionCopy.exportMissingSubtitle : "",
                    icon: "play.rectangle.fill",
                    tint: AppTheme.successGreen
                )
            }
            .buttonStyle(.plain)
            .disabled(latestExportURL == nil)
            .opacity(latestExportURL == nil ? 0.5 : 1.0)
            .accessibilityIdentifier("history.detail.watchSavedReel")

            Button {
                presentShareSheet(for: latestExportURL)
            } label: {
                actionLabel(
                    title: "Share",
                    subtitle: latestExportURL == nil ? HistoryProjectActionCopy.exportMissingSubtitle : "",
                    icon: "square.and.arrow.up.fill",
                    tint: AppTheme.successGreen
                )
            }
            .buttonStyle(.plain)
            .disabled(latestExportURL == nil)
            .opacity(latestExportURL == nil ? 0.5 : 1.0)
            .accessibilityIdentifier("history.project.shareLatestExport")

            Button(role: .destructive) {
                showingDeleteConfirmation = true
            } label: {
                actionLabel(
                    title: "Delete Project",
                    subtitle: "",
                    icon: "trash.fill",
                    tint: AppTheme.dangerRed
                )
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("history.detail.deleteProject")
        }
        .padding(16)
        .rorkCard(
            cornerRadius: 16,
            fill: AppTheme.accentCardFill(AppTheme.rimOrange, opacity: 0.10),
            stroke: AppTheme.rimOrange.opacity(0.18),
            glow: AppTheme.rimOrange,
            glowOpacity: 0.04
        )
    }

    private var timelineCard: some View {
        VStack(spacing: 12) {
            RorkSectionHeader(
                title: "What Happened",
                icon: "list.bullet.rectangle.fill",
                subtitle: "Recent project events",
                accent: AppTheme.rimOrange
            )

            if project.events.isEmpty {
                Text("No events recorded yet.")
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
                    .frame(maxWidth: .infinity, alignment: .leading)
            } else {
                ForEach(project.events.reversed()) { event in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(alignment: .top, spacing: 8) {
                            Text(event.kind.label)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.white)
                                .fixedSize(horizontal: false, vertical: true)
                            Spacer()
                            Text(event.timestamp.formatted(date: .abbreviated, time: .shortened))
                                .font(.caption2)
                                .foregroundStyle(AppTheme.subtleText)
                                .multilineTextAlignment(.trailing)
                                .fixedSize(horizontal: false, vertical: true)
                        }

                        Text(event.message)
                            .font(.caption)
                            .foregroundStyle(AppTheme.subtleText)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .padding(12)
                    .background(AppTheme.surfaceBg.opacity(0.72), in: RoundedRectangle(cornerRadius: 12))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(AppTheme.softBorder, lineWidth: 1)
                    )
                }
            }
        }
        .padding(16)
        .rorkCard(
            cornerRadius: 16,
            fill: AppTheme.accentCardFill(AppTheme.rimOrange, opacity: 0.10),
            stroke: AppTheme.rimOrange.opacity(0.18),
            glow: AppTheme.rimOrange,
            glowOpacity: 0.04
        )
    }

    private var detailMetricGridColumns: [GridItem] {
        let minimumWidth: CGFloat = dynamicTypeSize.isAccessibilitySize ? 150 : 108
        return [
            GridItem(.adaptive(minimum: minimumWidth, maximum: 220), spacing: 10, alignment: .top)
        ]
    }

    @ViewBuilder
    private func detailLine(label: String, value: String) -> some View {
        if dynamicTypeSize.isAccessibilitySize {
            VStack(alignment: .leading, spacing: 3) {
                detailLineLabel(label)
                detailLineValue(value)
            }
        } else {
            HStack(alignment: .top, spacing: 8) {
                detailLineLabel(label)
                    .frame(width: 72, alignment: .leading)
                detailLineValue(value)
            }
        }
    }

    private func detailLineLabel(_ label: String) -> some View {
        Text(label)
            .font(.caption.weight(.semibold))
            .foregroundStyle(.white)
            .fixedSize(horizontal: false, vertical: true)
    }

    private func detailLineValue(_ value: String) -> some View {
        Text(value)
            .font(.caption)
            .foregroundStyle(AppTheme.subtleText)
            .frame(maxWidth: .infinity, alignment: .leading)
            .fixedSize(horizontal: false, vertical: true)
    }

    private func actionLabel(title: String, subtitle: String, icon: String, tint: Color) -> some View {
        let trimmedSubtitle = subtitle.trimmingCharacters(in: .whitespacesAndNewlines)
        let iconView = Image(systemName: icon)
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(tint)
            .frame(width: 34, height: 34)
            .background(tint.opacity(0.12), in: .circle)

        let textStack = VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.white)
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 3 : 2)
                .minimumScaleFactor(0.86)
                .fixedSize(horizontal: false, vertical: true)
            if !trimmedSubtitle.isEmpty {
                Text(trimmedSubtitle)
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                    .minimumScaleFactor(0.86)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }

        return Group {
            if dynamicTypeSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 8) {
                    iconView
                    textStack
                }
            } else {
                HStack(spacing: 12) {
                    iconView
                    textStack
                    Spacer(minLength: 0)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(AppTheme.surfaceBg.opacity(0.72), in: RoundedRectangle(cornerRadius: 14))
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(AppTheme.softBorder, lineWidth: 1)
        )
    }

    private func startPreview(url: URL?, title: String) {
        guard let url else { return }
        previewPlayer?.pause()
        previewPlayer = AVPlayer(url: url)
        inspectHistoryPreviewAudioTrack(for: url)
        applyHistoryPreviewAudioMute()
        previewPlayer?.play()
        previewTitle = title
    }

    private func applyHistoryPreviewAudioMute() {
        PreviewAudioCopy.applyMuted(previewAudioMuted, to: previewPlayer)
    }

    private func inspectHistoryPreviewAudioTrack(for url: URL) {
        previewAudioCheckTask?.cancel()
        previewHasAudioTrack = nil
        let expectedURL = url.standardizedFileURL
        previewAudioCheckTask = Task { @MainActor in
            let asset = AVURLAsset(url: expectedURL)
            let hasAudio = ((try? await asset.loadTracks(withMediaType: .audio)) ?? []).isEmpty == false
            let currentPreviewURL = (previewPlayer?.currentItem?.asset as? AVURLAsset)?.url.standardizedFileURL
            guard !Task.isCancelled,
                  currentPreviewURL == expectedURL else { return }
            previewHasAudioTrack = hasAudio
        }
    }

    private var shareSheetTitle: String {
        "HoopClips Highlight - \(project.displayTitle)"
    }

    private func presentShareSheet(for url: URL?) {
        guard let url else {
            shareErrorMessage = HistoryProjectActionCopy.shareMissingMessage
            showingShareError = true
            return
        }
        guard FileManager.default.fileExists(atPath: url.path) else {
            shareErrorMessage = HistoryProjectActionCopy.shareMissingMessage
            showingShareError = true
            return
        }
        shareURL = url
        showingShareSheet = true
    }

    private func clearShareSelection() {
        shareURL = nil
    }
}

nonisolated enum HistoryProjectActionCopy {
    static let emptyPreviewHint = "Choose a saved video below."
    static let openAvailableSubtitle = ""
    static let openUnavailableSubtitle = "Source not on this device"
    static let sourceAvailableSubtitle = ""
    static let sourceMissingSubtitle = "Source not on this device"
    static let exportAvailableSubtitle = ""
    static let exportMissingSubtitle = "No saved export yet"
    static let shareAvailableSubtitle = ""
    static let shareMissingMessage = "Make the reel again before sharing."
    static let deleteSubtitle = ""
}

fileprivate func userFacingAnalysisModeLabel(_ mode: AnalysisExecutionMode) -> String {
    switch mode {
    case .cloud:
        return "Enhanced"
    case .local, .localFallback:
        return "On-device"
    }
}

fileprivate func userFacingAnalysisModeIcon(_ mode: AnalysisExecutionMode) -> String {
    switch mode {
    case .cloud:
        return "sparkles"
    case .local, .localFallback:
        return "iphone"
    }
}

fileprivate func projectTeamTargetShortLabel(_ project: PersistedProjectRecord) -> String? {
    guard let selection = project.highlightTeamSelection else { return nil }
    let opponent = sanitizedHistoryTeamName(project.opponentTeamName)
    if selection.mode == .all {
        return "All teams"
    }
    if let opponent {
        return "\(selection.displayTitle) vs \(opponent)"
    }
    return selection.displayTitle
}

fileprivate func projectTeamTargetDetailLabel(_ project: PersistedProjectRecord) -> String? {
    guard let selection = project.highlightTeamSelection else { return nil }
    let opponent = sanitizedHistoryTeamName(project.opponentTeamName)
    if selection.mode == .all {
        if let opponent {
            return "All teams, opponent noted as \(opponent). Useful when the user was not sure which team to target."
        }
        return "All teams. Useful when the user was not sure which team to target."
    }

    let reviewCopy = selection.includeUncertain
        ? "Uncertain plays stayed available for Review."
        : "Only confident matches were targeted."
    let opponentCopy = opponent.map { " Opponent: \($0)." } ?? ""
    return "\(selection.displayTitle).\(opponentCopy) \(reviewCopy)"
}

fileprivate func sanitizedHistoryTeamName(_ value: String?) -> String? {
    guard let value else { return nil }
    let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
    return trimmed.isEmpty ? nil : trimmed
}
