import SwiftUI

struct ExportView: View {
    @Bindable var viewModel: HighlightsViewModel
    @State private var exportTrigger = 0
    @State private var saveTrigger = 0
    @State private var showShareSheet = false

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
            HStack {
                Image(systemName: "film.stack.fill")
                    .foregroundStyle(AppTheme.neonPurple)
                Text("Highlight Reel")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
            }

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
        .background(AppTheme.cardBg, in: .rect(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(AppTheme.accentPurple.opacity(0.2), lineWidth: 1)
        )
    }

    private var themeSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Theme", systemImage: "paintbrush.fill")
                .font(.headline)
                .foregroundStyle(.white)

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
    }

    private var musicSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Music", systemImage: "music.note")
                .font(.headline)
                .foregroundStyle(.white)

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
    }

    private var qualitySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Quality", systemImage: "slider.horizontal.3")
                .font(.headline)
                .foregroundStyle(.white)

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
                .background(AppTheme.cardBg, in: .rect(cornerRadius: 16))
            } else {
                Button {
                    exportTrigger += 1
                    Task { await viewModel.exportHighlights() }
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: "square.and.arrow.up.fill")
                            .font(.title3)
                        Text("Export Highlight Reel")
                            .font(.headline)
                    }
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 18)
                    .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 16))
                }
                .sensoryFeedback(.impact(weight: .heavy), trigger: exportTrigger)
            }
        }
    }
}
