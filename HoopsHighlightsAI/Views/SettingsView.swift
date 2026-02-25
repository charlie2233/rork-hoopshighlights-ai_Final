import SwiftUI

struct SettingsView: View {
    @Bindable var viewModel: HighlightsViewModel
    @State private var showingResetAlert = false

    var body: some View {
        NavigationStack {
            ZStack {
                AppTheme.darkBg.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 24) {
                        settingsSummaryCard
                        aiWeightsSection
                        clipSettingsSection
                        performanceSection
                        aboutSection
                        dangerZone
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                    .padding(.bottom, 100)
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .alert("Reset Settings?", isPresented: $showingResetAlert) {
                Button("Reset", role: .destructive) {
                    viewModel.settings = AnalysisSettings()
                }
                Button("Cancel", role: .cancel) { }
            } message: {
                Text("This will restore all AI settings to their defaults.")
            }
        }
    }

    private var aiWeightsSection: some View {
        settingsCard(title: "AI Analysis Weights", icon: "brain.head.profile.fill") {
            weightSlider(label: "Audio (Crowd Noise)", value: $viewModel.settings.audioWeight, color: .blue)
            weightSlider(label: "Motion Detection", value: $viewModel.settings.motionWeight, color: .orange)
            weightSlider(label: "Body Pose Analysis", value: $viewModel.settings.poseWeight, color: .green)
            weightSlider(label: "Scene Brightness", value: $viewModel.settings.sceneWeight, color: .yellow)

            let total = viewModel.settings.audioWeight + viewModel.settings.motionWeight + viewModel.settings.poseWeight + viewModel.settings.sceneWeight
            HStack {
                Text("Total Weight")
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
                Spacer()
                Text(String(format: "%.0f%%", total * 100))
                    .font(.caption.bold().monospacedDigit())
                    .foregroundStyle(abs(total - 1.0) < 0.05 ? AppTheme.successGreen : AppTheme.warningYellow)
            }
            .padding(.top, 4)
        }
    }

    private var settingsSummaryCard: some View {
        let weightsTotal = viewModel.settings.audioWeight
            + viewModel.settings.motionWeight
            + viewModel.settings.poseWeight
            + viewModel.settings.sceneWeight
        let normalized = abs(weightsTotal - 1.0) < 0.05

        return VStack(alignment: .leading, spacing: 12) {
            RorkSectionHeader(
                title: "Detection Profile",
                icon: "sparkles",
                subtitle: "Current AI tuning snapshot used for new analysis runs"
            )

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: "scope",
                    value: "\(Int(viewModel.settings.confidenceThreshold * 100))%",
                    label: "Threshold"
                )
                RorkMetricChip(
                    icon: "gauge.with.dots.needle.67percent",
                    value: "\(Int(viewModel.settings.framesSampledPerSecond)) fps",
                    label: "Sampling",
                    tint: AppTheme.warningYellow
                )
            }

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: normalized ? "checkmark.seal.fill" : "exclamationmark.triangle.fill",
                    value: normalized ? "Balanced" : "Adjust",
                    label: "Weights",
                    tint: normalized ? AppTheme.successGreen : AppTheme.warningYellow
                )
                RorkMetricChip(
                    icon: viewModel.settings.preferKeepUncertain ? "checkmark.circle.fill" : "xmark.circle.fill",
                    value: viewModel.settings.preferKeepUncertain ? "On" : "Off",
                    label: "Keep Uncertain",
                    tint: viewModel.settings.preferKeepUncertain ? AppTheme.successGreen : AppTheme.dangerRed
                )
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 18, stroke: AppTheme.softBorder, glowOpacity: 0.06)
    }

    private var clipSettingsSection: some View {
        settingsCard(title: "Clip Detection", icon: "scissors") {
            VStack(spacing: 4) {
                HStack {
                    Text("Confidence Threshold")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text("\(Int(viewModel.settings.confidenceThreshold * 100))%")
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.confidenceThreshold, in: 0.1...0.9, step: 0.05)
                    .tint(AppTheme.accentPurple)
                Text("Lower = more clips (may include false positives)")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }

            Divider().overlay(AppTheme.accentPurple.opacity(0.2))

            HStack {
                Text("Min Clip Duration")
                    .font(.subheadline)
                    .foregroundStyle(.white)
                Spacer()
                Text(String(format: "%.1fs", viewModel.settings.minClipDuration))
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(AppTheme.neonPurple)
            }
            Slider(value: $viewModel.settings.minClipDuration, in: 1.0...5.0, step: 0.5)
                .tint(AppTheme.accentPurple)

            Divider().overlay(AppTheme.accentPurple.opacity(0.2))

            HStack {
                Text("Max Clip Duration")
                    .font(.subheadline)
                    .foregroundStyle(.white)
                Spacer()
                Text(String(format: "%.0fs", viewModel.settings.maxClipDuration))
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(AppTheme.neonPurple)
            }
            Slider(value: $viewModel.settings.maxClipDuration, in: 5.0...30.0, step: 1.0)
                .tint(AppTheme.accentPurple)

            Divider().overlay(AppTheme.accentPurple.opacity(0.2))

            HStack {
                Text("Clip Padding")
                    .font(.subheadline)
                    .foregroundStyle(.white)
                Spacer()
                Text(String(format: "%.1fs", viewModel.settings.clipPadding))
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(AppTheme.neonPurple)
            }
            Slider(value: $viewModel.settings.clipPadding, in: 0.5...3.0, step: 0.5)
                .tint(AppTheme.accentPurple)

            Divider().overlay(AppTheme.accentPurple.opacity(0.2))

            Toggle(isOn: $viewModel.settings.preferKeepUncertain) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Keep Uncertain Clips")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Text("When unsure, keep clips for manual review")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                }
            }
            .tint(AppTheme.accentPurple)
        }
    }

    private var performanceSection: some View {
        settingsCard(title: "Performance", icon: "gauge.with.dots.needle.67percent") {
            VStack(spacing: 4) {
                HStack {
                    Text("Frames Per Second")
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text(String(format: "%.0f fps", viewModel.settings.framesSampledPerSecond))
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(AppTheme.neonPurple)
                }
                Slider(value: $viewModel.settings.framesSampledPerSecond, in: 1.0...10.0, step: 1.0)
                    .tint(AppTheme.accentPurple)
                Text("Higher = more accurate but slower analysis")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }
        }
    }

    private var aboutSection: some View {
        settingsCard(title: "About", icon: "info.circle.fill") {
            VStack(spacing: 12) {
                HStack {
                    Text("Hoops Highlights AI")
                        .font(.headline)
                        .foregroundStyle(.white)
                    Spacer()
                    Text("v1.0")
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.subtleText)
                }

                Text("AI-powered basketball highlight detection using on-device Vision framework analysis. Combines body pose estimation, motion detection, audio peak analysis, and scene classification for accurate clip extraction.")
                    .font(.caption)
                    .foregroundStyle(AppTheme.subtleText)
                    .fixedSize(horizontal: false, vertical: true)

                HStack(spacing: 16) {
                    aiFeatureTag("Vision API")
                    aiFeatureTag("Body Pose")
                    aiFeatureTag("Audio Analysis")
                    aiFeatureTag("Motion")
                }
            }
        }
    }

    private func aiFeatureTag(_ text: String) -> some View {
        Text(text)
            .font(.caption2)
            .foregroundStyle(AppTheme.neonPurple)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(AppTheme.accentPurple.opacity(0.15), in: .capsule)
    }

    private var dangerZone: some View {
        Button {
            showingResetAlert = true
        } label: {
            VStack(spacing: 6) {
                HStack {
                    Image(systemName: "arrow.counterclockwise")
                    Text("Reset to Defaults")
                        .fontWeight(.semibold)
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption.bold())
                }
                .font(.subheadline)
                .foregroundStyle(AppTheme.dangerRed)

                HStack {
                    Text("Restore all AI tuning values to the original Rork MAX defaults.")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.subtleText)
                    Spacer()
                }
            }
            .frame(maxWidth: .infinity)
            .padding(14)
            .background(AppTheme.dangerRed.opacity(0.08), in: .rect(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(AppTheme.dangerRed.opacity(0.18), lineWidth: 1)
            )
        }
    }

    private func settingsCard(title: String, icon: String, @ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            RorkSectionHeader(title: title, icon: icon)

            VStack(spacing: 12) {
                content()
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.accentPurple.opacity(0.15), glowOpacity: 0.05)
    }

    private func weightSlider(label: String, value: Binding<Double>, color: Color) -> some View {
        VStack(spacing: 4) {
            HStack {
                Circle()
                    .fill(color)
                    .frame(width: 8, height: 8)
                Text(label)
                    .font(.subheadline)
                    .foregroundStyle(.white)
                Spacer()
                Text("\(Int(value.wrappedValue * 100))%")
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(color)
            }
            Slider(value: value, in: 0...1.0, step: 0.05)
                .tint(color)
        }
    }
}
