import SwiftUI

struct UploadsWorkflowView: View {
    @Bindable var viewModel: HighlightsViewModel
    @Binding var selectedTab: Int
    var onOpenHistory: () -> Void
    var onOpenSettings: () -> Void
    var onOpenReview: () -> Void

    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VideoPlayerView(
            viewModel: viewModel,
            onOpenHistory: onOpenHistory,
            onOpenReview: onOpenReview
        )
        .safeAreaInset(edge: .top, spacing: 0) {
            uploadQueuePanel
                .padding(.horizontal, 14)
                .padding(.top, 4)
                .padding(.bottom, 6)
        }
    }

    private var uploadQueuePanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                Label("Uploads", systemImage: "icloud.and.arrow.up.fill")
                    .font(.headline.weight(.heavy))
                    .foregroundStyle(.white)

                Spacer(minLength: 0)

                Button {
                    onOpenHistory()
                } label: {
                    Image(systemName: "clock.arrow.circlepath")
                        .font(.subheadline.weight(.bold))
                        .frame(width: 34, height: 34)
                }
                .buttonStyle(.plain)
                .foregroundStyle(AppTheme.neonPurple)
                .background(AppTheme.neonPurple.opacity(0.14), in: Circle())
                .accessibilityLabel("Open history")
                .accessibilityIdentifier("uploads.historyButton")

                Button {
                    onOpenSettings()
                } label: {
                    Image(systemName: "gearshape.fill")
                        .font(.subheadline.weight(.bold))
                        .frame(width: 34, height: 34)
                }
                .buttonStyle(.plain)
                .foregroundStyle(AppTheme.subtleText)
                .background(AppTheme.surfaceBg.opacity(0.72), in: Circle())
                .accessibilityLabel("Open settings")
                .accessibilityIdentifier("uploads.settingsButton")
            }

            ForEach(uploadQueueItems) { item in
                uploadQueueRow(item)
            }
        }
        .padding(12)
        .background(AppTheme.cardBg.opacity(0.94), in: .rect(cornerRadius: 18))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(AppTheme.neonPurple.opacity(0.18), lineWidth: 1)
        )
        .shadow(color: AppTheme.neonPurple.opacity(0.12), radius: 16, y: 8)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("uploads.queue.panel")
    }

    private func uploadQueueRow(_ item: UploadQueueItem) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(alignment: .top, spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 11, style: .continuous)
                        .fill(queueTint(for: item.phase).opacity(0.18))
                        .frame(width: 36, height: 36)
                    Image(systemName: queueIcon(for: item.phase))
                        .font(.subheadline.weight(.heavy))
                        .foregroundStyle(queueTint(for: item.phase))
                }
                .accessibilityHidden(true)

                VStack(alignment: .leading, spacing: 3) {
                    Text(item.phase.title)
                        .font(.subheadline.weight(.heavy))
                        .foregroundStyle(.white)
                        .lineLimit(1)

                    Text(item.status)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(AppTheme.subtleText)
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? 4 : 2)
                        .fixedSize(horizontal: false, vertical: true)

                    Text(item.contractSummary)
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(AppTheme.subtleText.opacity(0.78))
                        .lineLimit(1)
                        .minimumScaleFactor(0.78)
                }
                .layoutPriority(1)

                Text("\(item.progressPercent)%")
                    .font(.caption.bold())
                    .foregroundStyle(queueTint(for: item.phase))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 5)
                    .background(queueTint(for: item.phase).opacity(0.13), in: .capsule)
            }

            ProgressView(value: item.progress)
                .tint(queueTint(for: item.phase))
                .accessibilityLabel("Upload queue progress")
                .accessibilityValue("\(item.progressPercent)%")

            if item.phase == .reviewReady {
                Button {
                    openReviewFromQueue()
                } label: {
                    Label("Open Review", systemImage: "checkmark.seal.fill")
                        .font(.caption.bold())
                        .frame(maxWidth: .infinity, minHeight: 36)
                }
                .buttonStyle(.borderedProminent)
                .tint(AppTheme.neonPurple)
                .accessibilityIdentifier("uploads.queue.openReviewButton")
            }
        }
        .padding(10)
        .background(AppTheme.surfaceBg.opacity(0.58), in: .rect(cornerRadius: 14))
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(queueTint(for: item.phase).opacity(0.14), lineWidth: 1)
        )
        .accessibilityIdentifier("uploads.queue.item.\(item.phase.rawValue)")
    }

    private var uploadQueueItems: [UploadQueueItem] {
        let assetContracts = uploadAssetContracts
        if !assetContracts.isEmpty {
            return UploadQueueProjection.items(assets: assetContracts)
        }

        return UploadQueueProjection.items(
            isVideoLoaded: viewModel.isVideoLoaded,
            isImporting: viewModel.isVideoImportInProgress,
            importStatusMessage: viewModel.videoImportStatusMessage,
            isAnalyzing: viewModel.analysisService.isAnalyzing,
            analysisProgress: viewModel.analysisService.progress,
            analysisStatusMessage: viewModel.analysisService.statusMessage,
            cloudAnalysisJobID: viewModel.cloudAnalysisJobID,
            cloudEditSourceObjectKey: viewModel.cloudEditSourceObjectKey,
            clipCount: viewModel.clips.count,
            pendingUploadManifestSummary: CloudAnalysisService.pendingBackgroundUploadManifestSummary()
        )
    }

    private var uploadAssetContracts: [UploadAssetQueueContract] {
        guard let assetId = viewModel.cloudUploadAssetID,
              let storageKey = viewModel.cloudUploadAssetStorageKey,
              let status = viewModel.cloudUploadAssetStatus else {
            return []
        }

        return [
            UploadAssetQueueContract(
                assetId: assetId,
                storageKey: storageKey,
                proxyKey: viewModel.cloudUploadAssetProxyKey,
                status: status,
                uploadedBytes: viewModel.cloudUploadAssetUploadedBytes,
                fileSizeBytes: viewModel.cloudUploadAssetFileSizeBytes,
                progress: viewModel.cloudUploadAssetProgress,
                checksumSha256: viewModel.cloudUploadAssetChecksumSha256,
                integrityStatus: viewModel.cloudUploadAssetIntegrityStatus,
                analysisJobId: viewModel.cloudAnalysisJobID,
                clipCount: viewModel.clips.count,
                retryCount: viewModel.cloudUploadAssetRetryCount,
                retryable: viewModel.cloudUploadAssetRetryable,
                lastErrorCode: viewModel.cloudUploadAssetLastErrorCode,
                cancellationReason: viewModel.cloudUploadAssetCancellationReason,
                renderAttachmentCount: viewModel.cloudUploadAssetRenderAttachmentCount ?? 0,
                failureReason: viewModel.cloudUploadAssetFailureReason
            )
        ]
    }

    private func openReviewFromQueue() {
        guard !reduceMotion else {
            selectedTab = 1
            onOpenReview()
            return
        }
        withAnimation(.interactiveSpring(response: 0.28, dampingFraction: 0.88)) {
            selectedTab = 1
        }
        onOpenReview()
    }

    private func queueIcon(for phase: UploadQueuePhase) -> String {
        switch phase {
        case .empty: return "tray"
        case .ready: return "play.circle.fill"
        case .importing: return "doc.badge.arrow.up.fill"
        case .uploading: return "icloud.and.arrow.up.fill"
        case .analyzing: return "sparkles"
        case .reviewReady: return "checkmark.seal.fill"
        case .failed: return "exclamationmark.triangle.fill"
        }
    }

    private func queueTint(for phase: UploadQueuePhase) -> Color {
        switch phase {
        case .empty: return AppTheme.subtleText
        case .ready: return AppTheme.courtBlue
        case .importing, .uploading: return AppTheme.warningYellow
        case .analyzing: return AppTheme.neonPurple
        case .reviewReady: return AppTheme.successGreen
        case .failed: return AppTheme.dangerRed
        }
    }
}

struct AIEditWorkflowView: View {
    @Bindable var viewModel: HighlightsViewModel
    var onRequestProUpgrade: () -> Void

    @Environment(SubscriptionManager.self) private var subscriptionManager
    @Environment(AuthService.self) private var authService

    var body: some View {
        NavigationStack {
            ZStack {
                HoopsMotionBackdrop(glowOpacity: 0.18)

                ScrollView {
                    VStack(spacing: 18) {
                        workflowHeader
                        AIEditView(
                            viewModel: viewModel,
                            isProUser: subscriptionManager.isProUser,
                            revenueCatAppUserID: subscriptionManager.revenueCatAppUserID,
                            presentation: .exportSection,
                            onRequestProUpgrade: onRequestProUpgrade
                        )
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                    .padding(.bottom, 100)
                }
            }
            .navigationTitle("AI Edit")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(AppTheme.darkBg, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
        .environment(subscriptionManager)
        .environment(authService)
    }

    private var workflowHeader: some View {
        VStack(alignment: .leading, spacing: 12) {
            RorkSectionHeader(
                title: "AI Edit job",
                icon: "wand.and.stars.inverse",
                subtitle: viewModel.canRequestCloudEdit
                    ? "Choose style, duration, aspect ratio, then let the cloud build the edit plan and render job."
                    : (viewModel.cloudEditUnavailableReason ?? "Review or analyze clips before rendering.")
            )

            HStack(spacing: 10) {
                RorkMetricChip(
                    icon: "film.stack.fill",
                    value: "\(viewModel.cloudEditCandidatePoolCount)",
                    label: "Candidates",
                    tint: AppTheme.neonPurple
                )
                RorkMetricChip(
                    icon: viewModel.cloudEditSourceObjectKey == nil ? "icloud.slash.fill" : "icloud.fill",
                    value: viewModel.cloudEditSourceObjectKey == nil ? "Pending" : "Ready",
                    label: "Source",
                    tint: viewModel.cloudEditSourceObjectKey == nil ? AppTheme.warningYellow : AppTheme.successGreen
                )
            }
        }
        .padding(16)
        .rorkCard(cornerRadius: 16, stroke: AppTheme.neonPurple.opacity(0.18), glow: AppTheme.neonPurple, glowOpacity: 0.05)
        .accessibilityIdentifier("aiEdit.workflow.header")
    }
}
