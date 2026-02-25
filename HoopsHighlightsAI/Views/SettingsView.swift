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
            HStack {
                Image(systemName: "arrow.counterclockwise")
                Text("Reset to Defaults")
            }
            .font(.subheadline)
            .foregroundStyle(AppTheme.dangerRed)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(AppTheme.dangerRed.opacity(0.1), in: .rect(cornerRadius: 12))
        }
    }

    private func settingsCard(title: String, icon: String, @ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Label(title, systemImage: icon)
                .font(.headline)
                .foregroundStyle(.white)

            VStack(spacing: 12) {
                content()
            }
        }
        .padding(16)
        .background(AppTheme.cardBg, in: .rect(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(AppTheme.accentPurple.opacity(0.15), lineWidth: 1)
        )
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
