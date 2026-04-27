import SwiftUI
import AVKit
import UIKit

struct HistoryView: View {
    @Bindable var viewModel: HighlightsViewModel
    @State private var selectedProject: PersistedProjectRecord?

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
                                    projects: [currentProject]
                                )
                            }

                            if !viewModel.pastProjectRecords.isEmpty {
                                projectSection(
                                    title: "Past Projects",
                                    icon: "clock.arrow.circlepath",
                                    subtitle: "Reopen past runs and replay saved videos",
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
        }
    }

    private var emptyState: some View {
        HoopsEmptyStateCard(
            title: "No Project History Yet",
            message: "Import a video and hoopclips will keep the project, timeline, and saved export here.",
            icon: "clock.arrow.circlepath"
        )
    }

    private func projectSection(
        title: String,
        icon: String,
        subtitle: String,
        projects: [PersistedProjectRecord]
    ) -> some View {
        VStack(spacing: 12) {
            RorkSectionHeader(
                title: title,
                icon: icon,
                subtitle: subtitle
            )

            ForEach(projects) { project in
                Button {
                    selectedProject = project
                } label: {
                    historyRow(for: project)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.05)
    }

    private func historyRow(for project: PersistedProjectRecord) -> some View {
        HStack(spacing: 12) {
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
                            .font(.title3)
                            .foregroundStyle(AppTheme.neonPurple)
                    }
                }
            }
            .frame(width: 92, height: 56)
            .clipShape(.rect(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(AppTheme.softBorder, lineWidth: 1)
            )

            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text(project.displayTitle)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                        .lineLimit(1)
                    Spacer(minLength: 8)
                    Image(systemName: "chevron.right")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(AppTheme.subtleText)
                }

                Text("Updated \(project.updatedAt.formatted(date: .abbreviated, time: .shortened))")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
                    .lineLimit(1)

                HStack(spacing: 8) {
                    historyBadge(
                        icon: "film.stack.fill",
                        text: "\(project.keptClipCount)/\(project.totalClipCount)"
                    )

                    if project.hasLatestExport {
                        historyBadge(
                            icon: "square.and.arrow.up.fill",
                            text: "Export"
                        )
                    }

                    if let analysisMode = project.analysisMode {
                        historyBadge(
                            icon: userFacingAnalysisModeIcon(analysisMode),
                            text: userFacingAnalysisModeLabel(analysisMode)
                        )
                    }
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

    private func historyBadge(icon: String, text: String) -> some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption2.weight(.semibold))
            Text(text)
                .font(.caption2.weight(.medium))
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(AppTheme.cardBg, in: Capsule())
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
    @State private var previewPlayer: AVPlayer?
    @State private var previewTitle: String?

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

            HStack(spacing: 10) {
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
                    detailLine(label: "Last Export", value: lastExportedAt.formatted(date: .abbreviated, time: .shortened))
                }
                if let analysisStatusSummary = project.analysisStatusSummary, !analysisStatusSummary.isEmpty {
                    detailLine(label: "Status", value: analysisStatusSummary)
                }
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.softBorder, glowOpacity: 0.05)
    }

    private var playbackCard: some View {
        VStack(spacing: 12) {
            RorkSectionHeader(
                title: "Playback",
                icon: "play.rectangle.fill",
                subtitle: "Preview the saved source or latest export"
            )

            if let previewPlayer {
                VideoPlayer(player: previewPlayer)
                    .frame(height: 220)
                    .clipShape(.rect(cornerRadius: 16))
                    .overlay(
                        RoundedRectangle(cornerRadius: 16)
                            .stroke(AppTheme.softBorder, lineWidth: 1)
                    )

                if let previewTitle {
                    Text(previewTitle)
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                }
            } else {
                VStack(spacing: 8) {
                    Image(systemName: "play.circle")
                        .font(.title)
                        .foregroundStyle(AppTheme.neonPurple)
                    Text("Tap Play Source or Play Latest Export to preview this project.")
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                        .multilineTextAlignment(.center)
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
    }

    private var actionsCard: some View {
        VStack(spacing: 12) {
            RorkSectionHeader(
                title: "Actions",
                icon: "bolt.fill",
                subtitle: "Reopen the project or inspect saved media"
            )

            Button {
                onOpenProject()
                dismiss()
            } label: {
                actionLabel(
                    title: isCurrentProject ? "Currently Open" : "Open Project",
                    subtitle: canOpenProject
                        ? "Load this project back into Player, Review, and Export"
                        : "Source video is missing, so this project cannot be reopened",
                    icon: "arrow.counterclockwise.circle.fill",
                    tint: AppTheme.neonPurple
                )
            }
            .buttonStyle(.plain)
            .disabled(!canOpenProject || isCurrentProject)
            .opacity((canOpenProject && !isCurrentProject) ? 1.0 : 0.5)

            Button {
                startPreview(url: sourceURL, title: "Source Video")
            } label: {
                actionLabel(
                    title: "Play Source",
                    subtitle: sourceURL == nil ? "Source file is no longer available" : "Replay the saved imported video",
                    icon: "video.fill",
                    tint: AppTheme.warningYellow
                )
            }
            .buttonStyle(.plain)
            .disabled(sourceURL == nil)
            .opacity(sourceURL == nil ? 0.5 : 1.0)

            Button {
                startPreview(url: latestExportURL, title: "Latest Export")
            } label: {
                actionLabel(
                    title: "Play Latest Export",
                    subtitle: latestExportURL == nil ? "No export is saved for this project yet" : "Replay the latest saved highlight reel",
                    icon: "square.and.arrow.up.fill",
                    tint: AppTheme.successGreen
                )
            }
            .buttonStyle(.plain)
            .disabled(latestExportURL == nil)
            .opacity(latestExportURL == nil ? 0.5 : 1.0)

            Button(role: .destructive) {
                onDeleteProject()
                dismiss()
            } label: {
                actionLabel(
                    title: "Delete Project",
                    subtitle: "Remove this project and its saved files from the device",
                    icon: "trash.fill",
                    tint: AppTheme.dangerRed
                )
            }
            .buttonStyle(.plain)
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
                        HStack {
                            Text(event.kind.label)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.white)
                            Spacer()
                            Text(event.timestamp.formatted(date: .abbreviated, time: .shortened))
                                .font(.caption2)
                                .foregroundStyle(AppTheme.subtleText)
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

    private func detailLine(label: String, value: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.white)
                .frame(width: 72, alignment: .leading)
            Text(value)
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func actionLabel(title: String, subtitle: String, icon: String, tint: Color) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(tint)
                .frame(width: 34, height: 34)
                .background(tint.opacity(0.12), in: .circle)

            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.white)
                Text(subtitle)
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            Spacer(minLength: 0)
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
