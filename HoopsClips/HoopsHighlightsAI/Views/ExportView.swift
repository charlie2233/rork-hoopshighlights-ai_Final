import SwiftUI

struct ExportView: View {
    @Bindable var viewModel: HighlightsViewModel
    @State private var exportTrigger = 0
    @State private var saveTrigger = 0

    var body: some View {
        NavigationStack {
            ZStack {
                AppTheme.darkBg.ignoresSafeArea()

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
            .alert("Export Complete!", isPresented: $viewModel.showingExportComplete) {
                Button("Save to Photos") {
                    Task { await viewModel.saveToPhotos() }
                }
                if let url = viewModel.exportService.exportedURL {
                    ShareLink(item: url) {
                        Text("Share")
                    }
                }
                Button("Done", role: .cancel) { }
            } message: {
                Text("Your highlight reel is ready. \(viewModel.keptClips.count) clips compiled.")
            }
            .alert("Saved!", isPresented: $viewModel.showingSaveSuccess) {
                Button("OK", role: .cancel) { }
            } message: {
                Text("Highlight reel saved to your photo library.")
            }
        }
    }

    private var emptyState: some View {
        ContentUnavailableView {
            Label("No Clips to Export", systemImage: "film.stack")
        } description: {
            Text("Keep some clips in the Review tab to create a highlight reel")
        }
        .foregroundStyle(.white)
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
                    value: viewModel.selectedTheme.rawValue,
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
                    value: viewModel.selectedMusic == .none ? "No Music" : "Music",
                    label: viewModel.selectedMusic == .none ? "Audio" : viewModel.selectedMusic.rawValue,
                    tint: AppTheme.neonPurple
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
                    Button {
                        withAnimation(.snappy) { viewModel.selectedTheme = theme }
                    } label: {
                        VStack(spacing: 8) {
                            Image(systemName: theme.icon)
                                .font(.title2)
                                .foregroundStyle(viewModel.selectedTheme == theme ? .white : AppTheme.subtleText)
                            Text(theme.rawValue)
                                .font(.caption.weight(.medium))
                                .foregroundStyle(viewModel.selectedTheme == theme ? .white : AppTheme.subtleText)
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
                    }
                }
            }

            Text(viewModel.selectedTheme.description)
                .font(.caption)
                .foregroundStyle(AppTheme.subtleText)
                .padding(.leading, 4)
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
                        Button {
                            withAnimation(.snappy) { viewModel.selectedMusic = track }
                        } label: {
                            HStack(spacing: 8) {
                                Image(systemName: track.icon)
                                    .font(.subheadline)
                                Text(track.rawValue)
                                    .font(.subheadline.weight(.medium))
                            }
                            .foregroundStyle(viewModel.selectedMusic == track ? .white : AppTheme.subtleText)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 10)
                            .background(
                                viewModel.selectedMusic == track ? AppTheme.accentPurple : AppTheme.cardBg,
                                in: .capsule
                            )
                            .overlay(
                                Capsule()
                                    .stroke(
                                        viewModel.selectedMusic == track ? AppTheme.neonPurple : Color.clear,
                                        lineWidth: 2
                                    )
                            )
                        }
                    }
                }
            }
            .contentMargins(.horizontal, 0)
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

    @ViewBuilder
    private var quickActionsSection: some View {
        if let exportedURL = viewModel.exportService.exportedURL, !viewModel.exportService.isExporting {
            VStack(alignment: .leading, spacing: 12) {
                RorkSectionHeader(
                    title: "Quick Share",
                    icon: "paperplane.fill",
                    subtitle: "iOS share sheet for the latest export"
                )

                HStack(spacing: 10) {
                    ShareLink(item: exportedURL) {
                        HStack(spacing: 10) {
                            Image(systemName: "square.and.arrow.up.fill")
                                .font(.subheadline.weight(.semibold))
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Share Now")
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
                    .sensoryFeedback(.impact(weight: .light), trigger: saveTrigger)
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
                    Task { await viewModel.exportHighlights() }
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: "square.and.arrow.up.fill")
                            .font(.title3)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Export Highlight Reel")
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
                    .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 16))
                }
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(AppTheme.neonPurple.opacity(0.25), lineWidth: 1)
                )
                .sensoryFeedback(.impact(weight: .heavy), trigger: exportTrigger)
            }
        }
    }
}
