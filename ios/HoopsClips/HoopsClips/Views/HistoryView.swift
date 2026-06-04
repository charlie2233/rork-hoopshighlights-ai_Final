import SwiftUI
import AVKit
import UIKit

struct HistoryView: View {
    @Bindable var viewModel: HighlightsViewModel
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

                if viewModel.historyProjects.isEmpty {
                    emptyState
                } else {
                    ScrollView {
                        VStack(spacing: 16) {
                            if let currentProject = viewModel.currentProjectRecord {
                                projectSection(
                                    title: "Current Project",
                                    icon: "bolt.circle.fill",
                                    subtitle: "Your active session is saved automatically",
                                    accessibilityIdentifier: "history.section.currentProject",
                                    projects: [currentProject]
                                )
                            }

                            if !viewModel.pastProjectRecords.isEmpty {
                                projectSection(
                                    title: "Past Projects",
                                    icon: "clock.arrow.circlepath",
                                    subtitle: "Reopen past runs and replay saved videos",
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
            title: "No Project History Yet",
            message: "Import a video and HoopClips will keep the project, timeline, and saved export here.",
            icon: "clock.arrow.circlepath"
        )
        .accessibilityIdentifier("history.emptyState")
    }

    private func projectSection(
        title: String,
        icon: String,
        subtitle: String,
        accessibilityIdentifier: String,
        projects: [PersistedProjectRecord]
    ) -> some View {
        VStack(spacing: 12) {
            RorkSectionHeader(
                title: title,
                icon: icon,
                subtitle: subtitle
            )

            ForEach(projects) { project in
                VStack(spacing: 8) {
                    historyRow(for: project)

                    LazyVGrid(columns: historyActionGridColumns, alignment: .leading, spacing: 8) {
                        Button {
                            selectedProject = project
                        } label: {
                            historyActionLabel(title: "Saved Project", icon: "info.circle.fill", tint: AppTheme.neonPurple)
                                .accessibilityLabel("Show saved project details for \(project.displayTitle)")
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("history.project.details")

                        Button {
                            viewModel.openProject(id: project.id)
                        } label: {
                            historyActionLabel(
                                title: viewModel.currentProjectID == project.id ? "Current" : "Resume",
                                icon: "arrow.counterclockwise.circle.fill",
                                tint: AppTheme.successGreen
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
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.05)
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
        .background(AppTheme.surfaceBg.opacity(0.72), in: RoundedRectangle(cornerRadius: 14))
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(AppTheme.softBorder, lineWidth: 1)
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
                    Image(systemName: "video.fill")
                        .font(isExpanded ? .title2 : .title3)
                        .foregroundStyle(AppTheme.neonPurple)
                }
            }
        }
        .frame(maxWidth: isExpanded ? .infinity : 92)
        .frame(width: isExpanded ? nil : 92, height: isExpanded ? 132 : 56)
        .clipShape(.rect(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(AppTheme.softBorder, lineWidth: 1)
        )
        .accessibilityHidden(true)
    }

    private func historySummary(for project: PersistedProjectRecord) -> some View {
        VStack(alignment: .leading, spacing: dynamicTypeSize.isAccessibilitySize ? 10 : 6) {
            HStack(alignment: .top) {
                projectTitleEditor(for: project)
                Spacer(minLength: 0)
            }

            Text("Updated \(project.updatedAt.formatted(date: .abbreviated, time: .shortened))")
                .font(.caption)
                .foregroundStyle(.white.opacity(0.78))
                .fixedSize(horizontal: false, vertical: true)

            LazyVGrid(columns: historyBadgeGridColumns, alignment: .leading, spacing: 8) {
                historyBadge(
                    icon: "film.stack.fill",
                    text: project.historyClipBadgeText,
                    accessibilityLabel: project.historyClipBadgeAccessibilityText
                )

                if project.hasLatestExport {
                    historyBadge(
                        icon: "square.and.arrow.up.fill",
                        text: project.historyExportBadgeText,
                        accessibilityLabel: "Saved reel ready to preview or share"
                    )
                }

                if let analysisMode = project.analysisMode {
                    historyBadge(
                        icon: userFacingAnalysisModeIcon(analysisMode),
                        text: userFacingAnalysisModeLabel(analysisMode)
                    )
                }

                if let teamTarget = projectTeamTargetShortLabel(project) {
                    historyBadge(
                        icon: project.highlightTeamSelection?.mode == .team ? "person.2.fill" : "person.3.fill",
                        text: teamTarget
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

    private func historyBadge(icon: String, text: String, accessibilityLabel: String? = nil) -> some View {
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
        .background(AppTheme.cardBg, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
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
                detailLine(label: "Source", value: project.sourceFilename)
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
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.05)
        .accessibilityIdentifier(accessibilityIdentifier)
    }

    private var playbackCard: some View {
        VStack(spacing: 12) {
            RorkSectionHeader(
                title: "Playback",
                icon: "play.rectangle.fill",
                subtitle: "Preview the source video or saved reel"
            )

            if let previewPlayer {
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
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.05)
        .accessibilityIdentifier("history.detail.playback")
    }

    private var actionsCard: some View {
        VStack(spacing: 12) {
            RorkSectionHeader(
                title: "Actions",
                icon: "bolt.fill",
                subtitle: "Resume, watch, share, or delete"
            )

            Button {
                onOpenProject()
                dismiss()
            } label: {
                actionLabel(
                    title: isCurrentProject ? "Currently Open" : "Resume Project",
                    subtitle: canOpenProject
                        ? HistoryProjectActionCopy.openAvailableSubtitle
                        : HistoryProjectActionCopy.openUnavailableSubtitle,
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
                    subtitle: sourceURL == nil ? HistoryProjectActionCopy.sourceMissingSubtitle : HistoryProjectActionCopy.sourceAvailableSubtitle,
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
                    subtitle: latestExportURL == nil ? HistoryProjectActionCopy.exportMissingSubtitle : HistoryProjectActionCopy.exportAvailableSubtitle,
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
                    subtitle: latestExportURL == nil ? HistoryProjectActionCopy.exportMissingSubtitle : HistoryProjectActionCopy.shareAvailableSubtitle,
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
                    subtitle: HistoryProjectActionCopy.deleteSubtitle,
                    icon: "trash.fill",
                    tint: AppTheme.dangerRed
                )
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("history.detail.deleteProject")
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.05)
    }

    private var timelineCard: some View {
        VStack(spacing: 12) {
            RorkSectionHeader(
                title: "What Happened",
                icon: "list.bullet.rectangle.fill",
                subtitle: "Recent project events"
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
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.05)
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
            Text(subtitle)
                .font(.caption2)
                .foregroundStyle(AppTheme.subtleText)
                .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 3)
                .minimumScaleFactor(0.86)
                .frame(maxWidth: .infinity, alignment: .leading)
                .fixedSize(horizontal: false, vertical: true)
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
        previewPlayer?.play()
        previewTitle = title
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
    static let openAvailableSubtitle = "Continue editing this project"
    static let openUnavailableSubtitle = "Source video missing"
    static let sourceAvailableSubtitle = "Watch original video"
    static let sourceMissingSubtitle = "Source file missing"
    static let exportAvailableSubtitle = "Watch saved reel"
    static let exportMissingSubtitle = "No saved export yet"
    static let shareAvailableSubtitle = "Share saved reel"
    static let shareMissingMessage = "Saved reel missing. Run AI Edit again."
    static let deleteSubtitle = "Remove saved files"
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
