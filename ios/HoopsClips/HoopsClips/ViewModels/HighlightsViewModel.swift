import Foundation
import AVFoundation
import PhotosUI
import SwiftUI
import UIKit

@Observable
@MainActor
final class HighlightsViewModel {
    private let settingsDefaultsKey = "hoopsclips.analysisSettings.v1"
    private let installIDDefaultsKey = "hoopsclips.installID.v1"
    private let maxProjectCount = 20
    private let maxProjectEventCount = 50
    private var backgroundTaskID: UIBackgroundTaskIdentifier = .invalid
    private let projectStore: ProjectHistoryStore
    private var projectLibrary: PersistedProjectLibrary
    private var suppressProjectPersistence = false
    private var pendingCloudAnalysisJob: PreparedCloudAnalysisJob?
    private var activeCloudTeamScanID: UUID?
    private var lastAnalysisStatusSummary: String?
    private var lastAnalyzedAt: Date?
    private var lastExportedAt: Date?

    var currentProjectID: UUID?
    var videoURL: URL?
    var videoDuration: Double = 0
    var videoThumbnail: CGImage?
    var isVideoLoaded = false

    var analysisService = VideoAnalysisService()
    var cloudAnalysisService = CloudAnalysisService()
    var exportService = VideoExportService()

    var selectedTheme: ExportTheme = .cinematic {
        didSet { persistCurrentProject() }
    }
    var selectedMusic: MusicTrack = .none {
        didSet { persistCurrentProject() }
    }
    var selectedQuality: ExportQuality = .high {
        didSet { persistCurrentProject() }
    }
    var selectedFormat: ExportFileFormat = .mp4 {
        didSet { persistCurrentProject() }
    }
    var exportPostProcessing = ExportPostProcessingOptions() {
        didSet { persistCurrentProject() }
    }
    var customAudioURL: URL?
    let installID: String
    var settings: AnalysisSettings {
        didSet { persistSettings() }
    }

    var clips: [Clip] { analysisService.clips }

    var keptClips: [Clip] { clips.filter(\.isKept) }
    var discardedClips: [Clip] { clips.filter { !$0.isKept } }
    var needsReviewClips: [Clip] { clips.filter(\.needsUserReview) }
    var cloudEditCandidatePoolCount: Int {
        Self.cloudEditRequestCandidateClips(
            from: clips,
            teamSelection: settings.highlightTeamSelection
        ).count
    }

    var showingVideoPicker = false
    var showingSaveSuccess = false
    var analysisMode: AnalysisExecutionMode = AppRuntimeConfig.shared.launchAnalysisMode
    var cloudQuotaRemaining: Int?
    var isCloudFallbackOffered = false
    var cloudAnalysisJobID: String?
    var cloudEditSourceObjectKey: String?
    var cloudDetectedTeams: [CloudTeamOption] = []
    var hasConfirmedHighlightTeamSelection = false
    var isCloudTeamScanInProgress = false
    var cloudTeamScanStatusMessage: String?
    var cloudTeamScanErrorMessage: String?

    var analysisModeDisplayName: String {
        switch analysisMode {
        case .cloud:
            return "Enhanced"
        case .local, .localFallback:
            return "On-device"
        }
    }

    var launchModeSummary: String {
        AppConstants.cloudLaunchStatusLabel
    }

    var canRequestCloudEdit: Bool {
        AppConstants.cloudEditEnabled
            && cloudEditSourceObjectKey != nil
            && !keptClips.isEmpty
    }

    var cloudEditUnavailableReason: String? {
        if !AppConstants.cloudEditEnabled {
            return "Cloud AI editing is not configured in this build."
        }
        if cloudEditSourceObjectKey == nil {
            return "Run cloud analysis first so HoopClips has the uploaded source video."
        }
        if keptClips.isEmpty {
            return "Keep at least one clip before making an AI edit."
        }
        return nil
    }

    var availableHighlightTeamChoices: [HighlightTeamSelection] {
        let scannedChoices = cloudDetectedTeams.map { team in
            let displayLabel = sanitizedCustomTeamName(settings.customHighlightTeamNames[team.teamId]) ?? team.label
            return HighlightTeamSelection(
                mode: .team,
                teamId: team.teamId,
                label: displayLabel,
                colorLabel: team.colorLabel,
                primaryColorHex: team.primaryColorHex,
                confidenceThreshold: 0.85,
                includeUncertain: true
            )
        }

        if scannedChoices.isEmpty {
            return [.allTeams]
        }

        return [.allTeams] + scannedChoices
    }

    var selectedHighlightTeamNameDraft: String {
        guard settings.highlightTeamSelection.mode == .team else { return "" }
        return settings.highlightTeamSelection.label ?? ""
    }

    var opponentTeamNameDraft: String {
        settings.opponentTeamName ?? ""
    }

    var requiresHighlightTeamSelectionConfirmation: Bool {
        AppConstants.cloudAnalysisEnabled
            && !cloudDetectedTeams.isEmpty
            && !hasConfirmedHighlightTeamSelection
    }

    var historyProjects: [PersistedProjectRecord] {
        projectLibrary.projects.sorted { lhs, rhs in
            if lhs.lastOpenedAt != rhs.lastOpenedAt {
                return lhs.lastOpenedAt > rhs.lastOpenedAt
            }
            return lhs.updatedAt > rhs.updatedAt
        }
    }

    var currentProjectRecord: PersistedProjectRecord? {
        guard let currentProjectID else { return nil }
        return projectLibrary.projects.first(where: { $0.id == currentProjectID })
    }

    var pastProjectRecords: [PersistedProjectRecord] {
        historyProjects.filter { $0.id != currentProjectID }
    }

    init() {
        #if DEBUG
        Self.applyAIEditLiveSmokeRuntimeOverrides()
        #endif

        let existingInstallID = UserDefaults.standard.string(forKey: installIDDefaultsKey)
        let resolvedInstallID: String
        if let existingInstallID, !existingInstallID.isEmpty {
            resolvedInstallID = existingInstallID
        } else {
            resolvedInstallID = UUID().uuidString
        }
        installID = resolvedInstallID
        if existingInstallID != resolvedInstallID {
            UserDefaults.standard.set(resolvedInstallID, forKey: installIDDefaultsKey)
        }

        if let data = UserDefaults.standard.data(forKey: settingsDefaultsKey),
           let decoded = try? JSONDecoder().decode(AnalysisSettings.self, from: data) {
            settings = decoded
        } else {
            settings = AnalysisSettings()
        }

        let store = ProjectHistoryStore()
        projectStore = store
        projectLibrary = (try? store.loadLibrary()) ?? .empty
        currentProjectID = projectLibrary.currentProjectID

        repairBrokenProjectReferences()
        restoreCurrentProjectIfAvailable()

        #if DEBUG
        applyAIEditLiveSmokeProjectIfNeeded()
        #endif
    }

    @discardableResult
    func loadVideo(
        url: URL,
        importProgress: (@Sendable (ProjectImportPhase) async -> Void)? = nil
    ) async -> Bool {
        let accessing = url.startAccessingSecurityScopedResource()
        defer { if accessing { url.stopAccessingSecurityScopedResource() } }
        let fileSize = (try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? -1
        LaunchTelemetry.shared.recordStabilityCheckpoint(
            "video_import.persist_begin",
            metadata: "fileSizeBytes=\(fileSize)"
        )

        persistCurrentProject()

        do {
            try Task.checkCancellation()
            clearPendingCloudAnalysisJob()
            settings.highlightTeamSelection = .allTeams
            settings.opponentTeamName = nil
            let project = try await projectStore.createProjectFromImportedVideo(
                sourceURL: url.standardizedFileURL,
                onProgress: importProgress
            )
            try Task.checkCancellation()
            insertProject(project, makeCurrent: true)
            applyPersistedProject(project)
            persistCurrentProject(reason: .imported, message: "Imported \(project.sourceFilename)")
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "video_import.persisted",
                metadata: "durationSeconds=\(Int(project.sourceDuration.rounded()))"
            )
            return true
        } catch is CancellationError {
            LaunchTelemetry.shared.recordStabilityCheckpoint("video_import.persist_cancelled")
            return false
        } catch {
            print("Failed to load video: \(error.localizedDescription)")
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "video_import.persist_failed",
                metadata: "reason=\(error.localizedDescription)"
            )
            return false
        }
    }

    func startAnalysis() async {
        guard let url = videoURL else { return }
        guard !requiresHighlightTeamSelectionConfirmation else {
            cloudTeamScanStatusMessage = "Choose a team before analysis"
            return
        }
        await AnalysisNotificationService.shared.prepareForAnalysis()
        beginBackgroundAnalysisTask()
        defer { endBackgroundAnalysisTask() }
        LaunchTelemetry.shared.recordStabilityCheckpoint(
            "analysis.started",
            metadata: "mode=\(AppConstants.cloudAnalysisEnabled ? "cloud" : "local") durationSeconds=\(Int(videoDuration.rounded()))"
        )

        analysisService.updateSettings(settings)

        guard AppConstants.cloudAnalysisEnabled else {
            await runPrimaryLocalAnalysis(for: url, status: "Analyzing on device")
            return
        }

        analysisMode = .cloud
        isCloudFallbackOffered = false
        analysisService.beginExternalAnalysis(status: "Preparing cloud upload")

        do {
            let result: CloudAnalysisResult
            if let preparedJob = pendingCloudAnalysisJob, preparedJob.sourceURL == url.standardizedFileURL {
                result = try await cloudAnalysisService.analyzePreparedVideo(
                    preparedJob,
                    teamSelection: settings.highlightTeamSelection,
                    installID: installID
                ) { [weak service = analysisService] progress, status in
                    service?.updateExternalAnalysis(progress: progress, status: status)
                }
            } else {
                result = try await cloudAnalysisService.analyzeVideo(
                    url: url,
                    duration: videoDuration,
                    installID: installID,
                    teamSelection: settings.highlightTeamSelection
                ) { [weak service = analysisService] progress, status in
                    service?.updateExternalAnalysis(progress: progress, status: status)
                }
            }
            cloudQuotaRemaining = nil
            analysisService.applyCloudAnalysis(result, duration: videoDuration)
            cloudAnalysisJobID = result.analysisJobId
            cloudEditSourceObjectKey = result.sourceObjectKey
            cloudDetectedTeams = result.detectedTeams
            if let effectiveTeamSelection = result.teamSelection {
                settings.highlightTeamSelection = effectiveTeamSelection
                hasConfirmedHighlightTeamSelection = true
            } else if result.detectedTeams.isEmpty {
                hasConfirmedHighlightTeamSelection = true
            }
            pendingCloudAnalysisJob = nil
            applyDefaultRedundantClipSuppression()
            AnalysisNotificationService.shared.notifyAnalysisCompleted(
                clipsCount: analysisService.clips.count,
                usedFallback: false
            )
            recordAnalysisCompleted()
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "analysis.completed",
                metadata: "mode=cloud clips=\(analysisService.clips.count)"
            )
        } catch let error where error.isTaskCancellation {
            analysisService.finishExternalAnalysis(with: "Analysis cancelled")
            LaunchTelemetry.shared.recordStabilityCheckpoint("analysis.cancelled", metadata: "mode=cloud")
            return
        } catch let error as CloudAnalysisError {
            switch error {
            case .quotaExceeded(let remaining):
                cloudQuotaRemaining = remaining
            default:
                break
            }
            await fallbackToLocalAnalysis(from: error)
        } catch {
            await fallbackToLocalAnalysis(from: CloudAnalysisError.network(error.localizedDescription))
        }
    }

    func scanTeamsBeforeAnalysis() async {
        guard let url = videoURL else { return }
        guard AppConstants.cloudAnalysisEnabled else { return }
        guard !analysisService.isAnalyzing, !isCloudTeamScanInProgress else { return }
        let scanSourceURL = url.standardizedFileURL
        guard pendingCloudAnalysisJob?.sourceURL != scanSourceURL else { return }
        beginBackgroundAnalysisTask()
        defer { endBackgroundAnalysisTask() }
        LaunchTelemetry.shared.recordStabilityCheckpoint(
            "team_scan.started",
            metadata: "durationSeconds=\(Int(videoDuration.rounded()))"
        )

        let scanID = UUID()
        activeCloudTeamScanID = scanID
        isCloudTeamScanInProgress = true
        defer {
            if activeCloudTeamScanID == scanID {
                isCloudTeamScanInProgress = false
                activeCloudTeamScanID = nil
            }
        }
        cloudTeamScanErrorMessage = nil
        cloudTeamScanStatusMessage = "Preparing cloud team scan"
        settings.highlightTeamSelection = .allTeams
        hasConfirmedHighlightTeamSelection = false
        analysisMode = .cloud

        do {
            let preparedJob = try await cloudAnalysisService.prepareTeamScan(
                url: url,
                duration: videoDuration,
                installID: installID
            ) { [weak self] progress, status in
                self?.cloudTeamScanStatusMessage = status
                self?.analysisService.updateExternalAnalysis(progress: progress, status: status)
            }

            guard videoURL?.standardizedFileURL == scanSourceURL else { return }
            pendingCloudAnalysisJob = preparedJob
            cloudDetectedTeams = preparedJob.detectedTeams
            resetStaleHighlightTeamSelection(against: preparedJob.detectedTeams)
            hasConfirmedHighlightTeamSelection = preparedJob.detectedTeams.isEmpty
            cloudTeamScanStatusMessage = preparedJob.detectedTeams.isEmpty
                ? "No clear jersey colors found yet"
                : "Choose a team before analysis"
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "team_scan.completed",
                metadata: "teams=\(preparedJob.detectedTeams.count)"
            )
        } catch let error where error.isTaskCancellation {
            if videoURL?.standardizedFileURL == scanSourceURL {
                clearPendingCloudAnalysisJob()
            }
            LaunchTelemetry.shared.recordStabilityCheckpoint("team_scan.cancelled")
            return
        } catch let error as CloudAnalysisError {
            guard videoURL?.standardizedFileURL == scanSourceURL else { return }
            if case .quotaExceeded(let remaining) = error {
                cloudQuotaRemaining = remaining
            }
            cloudTeamScanErrorMessage = error.localizedDescription
            cloudTeamScanStatusMessage = "Team scan unavailable"
            pendingCloudAnalysisJob = nil
            cloudDetectedTeams = []
            settings.highlightTeamSelection = .allTeams
            hasConfirmedHighlightTeamSelection = true
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "team_scan.failed",
                metadata: "reason=\(error.localizedDescription)"
            )
        } catch {
            guard videoURL?.standardizedFileURL == scanSourceURL else { return }
            cloudTeamScanErrorMessage = error.localizedDescription
            cloudTeamScanStatusMessage = "Team scan unavailable"
            pendingCloudAnalysisJob = nil
            cloudDetectedTeams = []
            settings.highlightTeamSelection = .allTeams
            hasConfirmedHighlightTeamSelection = true
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "team_scan.failed",
                metadata: "reason=\(error.localizedDescription)"
            )
        }
    }

    func confirmHighlightTeamSelection(_ selection: HighlightTeamSelection) {
        var resolvedSelection = selection
        if let teamID = selection.teamId,
           let customName = sanitizedCustomTeamName(settings.customHighlightTeamNames[teamID]) {
            resolvedSelection.label = customName
        }
        settings.highlightTeamSelection = resolvedSelection
        hasConfirmedHighlightTeamSelection = true
        if !cloudDetectedTeams.isEmpty {
            cloudTeamScanStatusMessage = resolvedSelection.mode == .all
                ? "All teams selected"
                : "\(resolvedSelection.displayTitle) selected"
        }
    }

    func renameSelectedHighlightTeam(_ displayName: String) {
        guard settings.highlightTeamSelection.mode == .team,
              let teamID = settings.highlightTeamSelection.teamId else {
            return
        }

        let customName = sanitizedCustomTeamName(displayName)
        if let customName {
            settings.customHighlightTeamNames[teamID] = customName
            settings.highlightTeamSelection.label = customName
        } else {
            settings.customHighlightTeamNames.removeValue(forKey: teamID)
            settings.highlightTeamSelection.label = cloudDetectedTeams.first(where: { $0.teamId == teamID })?.label
                ?? settings.highlightTeamSelection.colorLabel
                ?? "Selected team"
        }

        cloudTeamScanStatusMessage = "\(settings.highlightTeamSelection.displayTitle) selected"
        persistCurrentProject()
    }

    func renameOpponentTeam(_ displayName: String) {
        settings.opponentTeamName = sanitizedCustomTeamName(displayName)
        persistCurrentProject()
    }

    private func runPrimaryLocalAnalysis(for url: URL, status: String) async {
        guard !AppConstants.requiresCloudVideoPipeline else {
            let message = "Cloud analysis is required for this build."
            analysisMode = .cloud
            isCloudFallbackOffered = false
            analysisService.finishExternalAnalysis(with: message)
            recordAnalysisFailure(message: message)
            return
        }

        analysisMode = .local
        isCloudFallbackOffered = false
        cloudQuotaRemaining = nil
        cloudAnalysisJobID = nil
        cloudEditSourceObjectKey = nil
        cloudDetectedTeams = []
        clearPendingCloudAnalysisJob()
        analysisService.beginExternalAnalysis(status: status)
        await analysisService.analyze(url: url, settings: settings)
        applyDefaultRedundantClipSuppression()
        AnalysisNotificationService.shared.notifyAnalysisCompleted(
            clipsCount: analysisService.clips.count,
            usedFallback: false
        )
        recordAnalysisCompleted()
    }

    func toggleClip(_ clip: Clip) {
        guard let index = analysisService.clips.firstIndex(where: { $0.id == clip.id }) else { return }
        analysisService.clips[index].isKept.toggle()
        persistCurrentProject()
    }

    func toggleSlowMotion(_ clip: Clip) {
        guard let index = analysisService.clips.firstIndex(where: { $0.id == clip.id }) else { return }
        analysisService.clips[index].isSlowMotionEnabled.toggle()
        persistCurrentProject()
    }

    func keepAllClips() {
        for index in analysisService.clips.indices {
            analysisService.clips[index].isKept = true
        }
        persistCurrentProject()
    }

    func discardAllClips() {
        for index in analysisService.clips.indices {
            analysisService.clips[index].isKept = false
        }
        persistCurrentProject()
    }

    func keepHighConfidenceClips() {
        for index in analysisService.clips.indices
        where Self.isAutoKeepHighConfidenceEligible(
            analysisService.clips[index],
            teamSelection: settings.highlightTeamSelection
        ) {
            analysisService.clips[index].isKept = true
        }
        persistCurrentProject()
    }

    func discardLowConfidenceClips() {
        for index in analysisService.clips.indices
        where analysisService.clips[index].confidence < 0.5
            && !Self.protectsClipFromQuickSkip(analysisService.clips[index]) {
            analysisService.clips[index].isKept = false
        }
        persistCurrentProject()
    }

    nonisolated static func protectsClipFromQuickSkip(_ clip: Clip) -> Bool {
        clip.needsUserReview || defensiveCloudEditCandidateFamily(clip) != nil
    }

    func shouldAutoKeepHighConfidenceClip(_ clip: Clip) -> Bool {
        Self.isAutoKeepHighConfidenceEligible(clip, teamSelection: settings.highlightTeamSelection)
    }

    nonisolated static func isAutoKeepHighConfidenceEligible(
        _ clip: Clip,
        teamSelection: HighlightTeamSelection = .allTeams
    ) -> Bool {
        guard clip.confidence >= 0.8, !clip.needsUserReview else { return false }
        return clipMatchesHighlightTeamSelection(clip, selection: teamSelection)
    }

    nonisolated private static func clipMatchesHighlightTeamSelection(
        _ clip: Clip,
        selection: HighlightTeamSelection
    ) -> Bool {
        guard selection.mode == .team else { return true }
        guard let attribution = clip.teamAttribution else { return false }
        guard attribution.confidence >= selection.confidenceThreshold else { return false }

        let selectedKeys = normalizedHighlightTeamKeys(selection.teamId, selection.colorLabel, selection.label)
        let attributedKeys = normalizedHighlightTeamKeys(attribution.teamId, attribution.colorLabel, attribution.label)
        guard !selectedKeys.isEmpty, !attributedKeys.isEmpty else { return false }
        return !selectedKeys.isDisjoint(with: attributedKeys)
    }

    nonisolated private static func normalizedHighlightTeamKeys(_ values: String?...) -> Set<String> {
        Set(values.compactMap(normalizedHighlightTeamKey))
    }

    nonisolated private static func normalizedHighlightTeamKey(_ value: String?) -> String? {
        guard let value else { return nil }
        let normalized = value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return normalized.isEmpty ? nil : normalized
    }

    func selectCustomAudio(url: URL) {
        let accessing = url.startAccessingSecurityScopedResource()
        defer { if accessing { url.stopAccessingSecurityScopedResource() } }

        guard let currentProjectID else { return }

        do {
            let project = try projectStore.attachCustomAudio(for: currentProjectID, from: url.standardizedFileURL)
            refreshProjectLibrarySnapshot()
            customAudioURL = projectStore.existingURL(for: project.customAudioRelativePath)
            selectedMusic = .custom
        } catch {
            print("Failed to save custom audio: \(error.localizedDescription)")
        }
    }

    func exportHighlights(isProUser: Bool) async {
        guard let url = videoURL else { return }
        guard !AppConstants.requiresCloudVideoPipeline else {
            exportService.markUnavailable(AppConstants.localVideoExportUnavailableMessage)
            return
        }

        await exportService.exportHighlights(
            sourceURL: url,
            clips: keptClips,
            theme: selectedTheme,
            music: selectedMusic,
            customMusicURL: customAudioURL,
            isProUser: isProUser,
            quality: selectedQuality,
            format: selectedFormat,
            postProcessing: exportPostProcessing
        )

        guard let currentProjectID,
              let tempExportURL = exportService.exportedURL else {
            return
        }

        do {
            let project = try projectStore.attachLatestExport(
                for: currentProjectID,
                from: tempExportURL,
                preferredExtension: tempExportURL.pathExtension.isEmpty ? selectedFormat.fileExtension : tempExportURL.pathExtension
            )
            refreshProjectLibrarySnapshot()
            exportService.exportedURL = projectStore.existingURL(for: project.latestExportRelativePath)
            lastExportedAt = Date()
            let exportName = project.latestExportFilename ?? "highlight reel"
            persistCurrentProject(reason: .exportCompleted, message: "Exported \(exportName)")
        } catch {
            print("Failed to persist export: \(error.localizedDescription)")
        }
    }

    func saveToPhotos() async {
        guard let url = exportService.exportedURL else { return }
        let success = await exportService.saveToPhotos(url: url)
        if success {
            showingSaveSuccess = true
            persistCurrentProject(reason: .saveToPhotos, message: "Saved the latest export to Photos")
        }
    }

    func createCloudEditRequest(
        preset: CloudEditPreset,
        templateID: String? = nil,
        targetDurationSeconds: Int,
        aspectRatio: CloudEditAspectRatio? = nil,
        isProUser: Bool,
        revenueCatAppUserID: String? = nil,
        userPrompt: String? = nil
    ) throws -> CreateCloudEditJobRequest {
        guard let sourceObjectKey = cloudEditSourceObjectKey else {
            throw CloudEditError.missingSourceObject
        }

        let candidateSourceClips = Self.cloudEditRequestCandidateClips(
            from: clips,
            teamSelection: settings.highlightTeamSelection
        )
        let duplicateGroups = Self.cloudEditDuplicateGroupAssignments(for: candidateSourceClips)
        let candidates = candidateSourceClips.map { clip in
            let inferredCenter = clip.startTime + (clip.duration / 2.0)
            let center = max(clip.startTime, min(clip.endTime, clip.eventCenter ?? inferredCenter))
            return CloudEditCandidateClip(
                id: clip.id.uuidString,
                start: clip.startTime,
                end: clip.endTime,
                eventCenter: center,
                label: clip.label,
                confidence: clip.confidence,
                excitement: clip.combinedScore,
                watchability: max(clip.visualScore, clip.motionScore),
                motionScore: clip.motionScore,
                audioPeak: clip.audioScore,
                combinedScore: clip.combinedScore,
                duplicateGroup: duplicateGroups[clip.id],
                userReviewDecision: Self.cloudEditUserReviewDecision(
                    for: clip,
                    teamSelection: settings.highlightTeamSelection
                ),
                nativeShotSignals: clip.nativeShotSignals,
                teamAttribution: clip.teamAttribution,
                teamAttributionStatus: clip.teamAttributionStatus
            )
        }

        return CreateCloudEditJobRequest(
            videoId: currentProjectID?.uuidString ?? "current_project",
            analysisJobId: cloudAnalysisJobID ?? currentProjectID?.uuidString ?? "current_analysis",
            installId: installID,
            sourceObjectKey: sourceObjectKey,
            preset: preset.rawValue,
            templateId: templateID ?? preset.templateID,
            targetDurationSeconds: targetDurationSeconds,
            aspectRatio: aspectRatio ?? preset.aspectRatio,
            planTier: isProUser ? .pro : .free,
            revenueCatAppUserID: revenueCatAppUserID,
            userPrompt: userPrompt,
            teamSelection: settings.highlightTeamSelection,
            clips: Array(candidates)
        )
    }

    nonisolated static let cloudEditCandidateRequestLimit = 220
    nonisolated private static let cloudEditMinimumReviewCandidateReserve = 16
    nonisolated private static let cloudEditReviewCandidateReserveDivisor = 3
    nonisolated private static let cloudEditDuplicateOverlapThreshold = 0.68
    nonisolated private static let cloudEditDuplicateEventCenterTolerance = 1.5
    nonisolated private static let cloudEditSelectedTeamReserveMinScore = 0.72
    nonisolated private static let cloudEditSelectedTeamReserveMinConfidence = 0.70
    nonisolated private static let cloudEditSelectedTeamReserveMinWatchability = 0.64

    nonisolated static func cloudEditRequestCandidateClips(
        from clips: [Clip],
        limit: Int = cloudEditCandidateRequestLimit,
        teamSelection: HighlightTeamSelection = .allTeams
    ) -> [Clip] {
        let cappedLimit = max(0, limit)
        guard cappedLimit > 0 else { return [] }

        let keptSource = clips.filter(\.isKept)
        let keptCandidates = rankedCloudEditCandidateClips(from: keptSource, limit: cappedLimit)
        let reviewOnlyCandidates = rankedCloudEditCandidateClips(
            from: clips.filter { !$0.isKept && isCloudEditReviewReserveCandidate($0, teamSelection: teamSelection) },
            limit: cappedLimit
        )

        guard !reviewOnlyCandidates.isEmpty else {
            return keptCandidates
        }

        let reviewReserveLimit = cloudEditReviewCandidateReserveLimit(
            reviewCandidateCount: reviewOnlyCandidates.count,
            cappedLimit: cappedLimit
        )
        let keptLimit = max(0, cappedLimit - reviewReserveLimit)
        var selected = rankedCloudEditCandidateClips(from: keptSource, limit: keptLimit)
        selected.append(contentsOf: reviewOnlyCandidates.prefix(reviewReserveLimit))
        if selected.count < cappedLimit {
            var selectedIDs = Set(selected.map(\.id))
            let extraKeptCandidates = keptCandidates.filter { !selectedIDs.contains($0.id) }
            let keptSlots = cappedLimit - selected.count
            selected.append(contentsOf: extraKeptCandidates.prefix(keptSlots))
            selectedIDs = Set(selected.map(\.id))
            let extraReviewCandidates = reviewOnlyCandidates.dropFirst(reviewReserveLimit)
                .filter { !selectedIDs.contains($0.id) }
            selected.append(contentsOf: extraReviewCandidates.prefix(cappedLimit - selected.count))
        }
        return selected.prefix(cappedLimit).sorted { lhs, rhs in
            if lhs.isKept != rhs.isKept {
                return lhs.isKept
            }
            return lhs.startTime < rhs.startTime
        }
    }

    nonisolated private static func cloudEditReviewCandidateReserveLimit(
        reviewCandidateCount: Int,
        cappedLimit: Int
    ) -> Int {
        guard reviewCandidateCount > 0, cappedLimit > 0 else { return 0 }
        let fractionalReserve = max(1, cappedLimit / cloudEditReviewCandidateReserveDivisor)
        let minimumReserve = cappedLimit >= 16
            ? cloudEditMinimumReviewCandidateReserve
            : max(1, cappedLimit / 3)
        return min(reviewCandidateCount, cappedLimit, max(fractionalReserve, minimumReserve))
    }

    nonisolated static func cloudEditDuplicateGroupAssignments(for clips: [Clip]) -> [UUID: String] {
        var groups: [[Clip]] = []
        let sortedClips = clips
            .filter { $0.duration > 0 }
            .sorted { lhs, rhs in
                if lhs.startTime != rhs.startTime {
                    return lhs.startTime < rhs.startTime
                }
                return lhs.endTime < rhs.endTime
            }

        for clip in sortedClips {
            if let index = groups.firstIndex(where: { group in
                group.contains { cloudEditClipsAreDuplicateMoments(clip, $0) }
            }) {
                groups[index].append(clip)
            } else {
                groups.append([clip])
            }
        }

        var assignments: [UUID: String] = [:]
        for (index, group) in groups.enumerated() where group.count > 1 {
            guard let representative = group.min(by: { lhs, rhs in
                if lhs.combinedScore != rhs.combinedScore {
                    return lhs.combinedScore > rhs.combinedScore
                }
                return lhs.startTime < rhs.startTime
            }) else { continue }

            let center = cloudEditEventCenter(for: representative)
            let centerBucket = max(0, Int(center.rounded()))
            let family = cloudEditDuplicateFamily(for: representative)
            let groupID = "dup_\(family)_\(centerBucket)_\(index)"
            for clip in group {
                assignments[clip.id] = groupID
            }
        }

        return assignments
    }

    nonisolated private static func cloudEditUserReviewDecision(
        for clip: Clip,
        teamSelection: HighlightTeamSelection = .allTeams
    ) -> String {
        if clip.isKept {
            return "kept"
        }
        if isCloudEditReviewReserveCandidate(clip, teamSelection: teamSelection) {
            return "unreviewed"
        }
        return "discarded"
    }

    nonisolated private static func isCloudEditReviewReserveCandidate(
        _ clip: Clip,
        teamSelection: HighlightTeamSelection = .allTeams
    ) -> Bool {
        clip.needsUserReview
            || defensiveCloudEditCandidateFamily(clip) != nil
            || isSelectedTeamCloudEditReviewReserveCandidate(clip, teamSelection: teamSelection)
    }

    nonisolated private static func isSelectedTeamCloudEditReviewReserveCandidate(
        _ clip: Clip,
        teamSelection: HighlightTeamSelection
    ) -> Bool {
        guard teamSelection.mode == .team else { return false }
        guard clipMatchesHighlightTeamSelection(clip, selection: teamSelection) else { return false }
        guard isCloudEditCandidateQualityEligible(clip) else { return false }

        let watchability = max(clip.visualScore, clip.motionScore)
        return clip.combinedScore >= cloudEditSelectedTeamReserveMinScore
            && clip.confidence >= cloudEditSelectedTeamReserveMinConfidence
            && watchability >= cloudEditSelectedTeamReserveMinWatchability
    }

    nonisolated private static func cloudEditClipsAreDuplicateMoments(_ lhs: Clip, _ rhs: Clip) -> Bool {
        guard lhs.id != rhs.id else { return false }
        guard lhs.duration > 0, rhs.duration > 0 else { return false }
        guard cloudEditDuplicateFamily(for: lhs) == cloudEditDuplicateFamily(for: rhs) else { return false }

        if let lhsTeamID = lhs.teamAttribution?.teamId,
           let rhsTeamID = rhs.teamAttribution?.teamId,
           lhsTeamID != rhsTeamID {
            return false
        }

        let overlap = max(0.0, min(lhs.endTime, rhs.endTime) - max(lhs.startTime, rhs.startTime))
        let overlapRatio = overlap / max(min(lhs.duration, rhs.duration), 0.001)
        let centerDelta = abs(cloudEditEventCenter(for: lhs) - cloudEditEventCenter(for: rhs))

        return overlapRatio >= cloudEditDuplicateOverlapThreshold
            && centerDelta <= cloudEditDuplicateEventCenterTolerance
    }

    nonisolated private static func cloudEditEventCenter(for clip: Clip) -> Double {
        let inferredCenter = clip.startTime + max(clip.duration, 0.0) / 2.0
        return max(clip.startTime, min(clip.endTime, clip.eventCenter ?? inferredCenter))
    }

    nonisolated private static func cloudEditDuplicateFamily(for clip: Clip) -> String {
        if let defensiveFamily = defensiveCloudEditCandidateFamily(clip) {
            return defensiveFamily
        }
        if isShotLikeCloudEditCandidate(clip) {
            return "shot"
        }

        switch clip.action {
        case .fastBreak:
            return "fast_break"
        case .crossover:
            return "handle"
        case .unknown:
            return cloudEditSanitizedDuplicateToken(from: clip.label)
        case .dunk, .layup, .madeShot, .threePointer, .alleyOop, .posterize, .buzzerBeater:
            return "shot"
        case .steal:
            return "steal"
        case .block:
            return "block"
        }
    }

    nonisolated private static func cloudEditSanitizedDuplicateToken(from text: String) -> String {
        let token = text
            .lowercased()
            .split { !$0.isLetter && !$0.isNumber }
            .prefix(3)
            .joined(separator: "_")
        return token.isEmpty ? "highlight" : String(token.prefix(32))
    }

    nonisolated static func rankedCloudEditCandidateClips(from clips: [Clip], limit: Int = 40) -> [Clip] {
        let cappedLimit = max(0, limit)
        let ranked = clips.filter(isCloudEditCandidateQualityEligible).sorted { lhs, rhs in
            let lhsScore = cloudEditCandidateScore(lhs)
            let rhsScore = cloudEditCandidateScore(rhs)
            if lhsScore != rhsScore {
                return lhsScore > rhsScore
            }

            if lhs.confidence != rhs.confidence {
                return lhs.confidence > rhs.confidence
            }

            return lhs.startTime < rhs.startTime
        }

        guard cappedLimit > 0 else { return [] }

        var selected = Array(ranked.prefix(cappedLimit))
        var selectedIDs = Set(selected.map(\.id))
        var reserveIDs = Set<UUID>()

        func reserveFirstMissing(where predicate: (Clip) -> Bool) {
            guard selected.contains(where: predicate) == false else { return }
            guard let candidate = ranked.first(where: { predicate($0) && !selectedIDs.contains($0.id) }) else { return }
            reserveIDs.insert(candidate.id)
            selectedIDs.insert(candidate.id)
        }

        for family in ["block", "steal", "forced_turnover", "defensive_stop"] {
            reserveFirstMissing { defensiveCloudEditCandidateFamily($0) == family }
        }
        reserveFirstMissing(where: \.needsUserReview)

        if !reserveIDs.isEmpty {
            selected.append(contentsOf: ranked.filter { reserveIDs.contains($0.id) })
            selected = selected.sorted { lhs, rhs in
                let lhsReserved = reserveIDs.contains(lhs.id)
                let rhsReserved = reserveIDs.contains(rhs.id)
                if lhsReserved != rhsReserved {
                    return lhsReserved
                }

                let lhsScore = cloudEditCandidateScore(lhs)
                let rhsScore = cloudEditCandidateScore(rhs)
                if lhsScore != rhsScore {
                    return lhsScore > rhsScore
                }

                return lhs.startTime < rhs.startTime
            }
        }

        return selected.prefix(cappedLimit).sorted { $0.startTime < $1.startTime }
    }

    nonisolated private static func isCloudEditCandidateQualityEligible(_ clip: Clip) -> Bool {
        guard clip.duration >= 2.0 else { return false }
        guard isShotLikeCloudEditCandidate(clip) else { return true }
        guard clip.duration >= 3.0 else { return false }
        let center = clip.eventCenter ?? (clip.startTime + (clip.duration / 2.0))
        let leadIn = center - clip.startTime
        let followThrough = clip.endTime - center
        return leadIn >= 1.2 && followThrough >= 0.8
    }

    nonisolated private static func cloudEditCandidateScore(_ clip: Clip) -> Double {
        let watchability = max(clip.visualScore, clip.motionScore)
        let durationScore = min(max(clip.duration / 8.0, 0.0), 1.0)
        var score = (clip.combinedScore * 0.45)
            + (clip.confidence * 0.25)
            + (watchability * 0.20)
            + (clip.audioScore * 0.06)
            + (durationScore * 0.04)

        if let eventCenter = clip.eventCenter {
            let leadIn = eventCenter - clip.startTime
            let followThrough = clip.endTime - eventCenter
            if leadIn >= 1.2 && followThrough >= 0.8 {
                score += 0.08
            } else if isShotLikeCloudEditCandidate(clip) {
                score -= 0.30
            }
        } else if isShotLikeCloudEditCandidate(clip) {
            score -= 0.04
        }

        if let defensiveFamily = defensiveCloudEditCandidateFamily(clip) {
            score += defensiveFamily == "block" || defensiveFamily == "steal" ? 0.14 : 0.10
        }
        if clip.needsUserReview {
            score += 0.05
        }

        return score
    }

    nonisolated private static func isShotLikeCloudEditCandidate(_ clip: Clip) -> Bool {
        let text = "\(clip.label) \(clip.action.rawValue)".lowercased()
        return ["shot", "bucket", "basket", "layup", "dunk", "finish", "jumper", "three", "3pt"].contains { text.contains($0) }
    }

    nonisolated private static func defensiveCloudEditCandidateFamily(_ clip: Clip) -> String? {
        let text = "\(clip.label) \(clip.action.rawValue)".lowercased()
        let tokens = Set(text.split { !$0.isLetter && !$0.isNumber }.map(String.init))
        if !tokens.isDisjoint(with: ["block", "blocked", "contest", "contested", "swat", "swatted", "rejection"])
            || text.contains("blocked shot") {
            return "block"
        }
        if !tokens.isDisjoint(with: ["steal", "strip", "stripped", "takeaway", "pickpocket"]) {
            return "steal"
        }
        if !tokens.isDisjoint(with: ["deflection", "deflected", "charge"])
            || text.contains("loose ball")
            || (tokens.contains("turnover") && !tokens.isDisjoint(with: ["forced", "force", "defensive", "defense"])) {
            return "forced_turnover"
        }
        if text.contains("defensive stop")
            || text.contains("defense stop")
            || tokens.contains("lockdown")
            || (tokens.contains("stop") && !tokens.isDisjoint(with: ["defensive", "defense", "forced"])) {
            return "defensive_stop"
        }
        return nil
    }

    func attachCloudRenderedExport(from temporaryURL: URL) {
        guard let currentProjectID else {
            exportService.exportedURL = temporaryURL
            return
        }

        do {
            let project = try projectStore.attachLatestExport(
                for: currentProjectID,
                from: temporaryURL,
                preferredExtension: "mp4"
            )
            refreshProjectLibrarySnapshot()
            exportService.exportedURL = projectStore.existingURL(for: project.latestExportRelativePath)
            lastExportedAt = Date()
            persistCurrentProject(reason: .exportCompleted, message: "Downloaded cloud AI edit")
        } catch {
            exportService.exportedURL = temporaryURL
            print("Failed to persist cloud AI edit: \(error.localizedDescription)")
        }
    }

    func resetProject() {
        persistCurrentProject()
        currentProjectID = nil
        projectLibrary.currentProjectID = nil
        saveProjectLibrary()
        clearLiveProjectState()
    }

    func openProject(id: UUID) {
        guard let project = projectLibrary.projects.first(where: { $0.id == id }),
              projectSourceURL(for: project) != nil else {
            return
        }

        applyPersistedProject(project)
        persistCurrentProject(reason: .reopened, message: "Reopened \(project.displayTitle)")
    }

    func renameProject(id: UUID, title: String) {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedTitle.isEmpty,
              let projectIndex = projectLibrary.projects.firstIndex(where: { $0.id == id }) else {
            return
        }

        var project = projectLibrary.projects[projectIndex]
        guard project.displayTitle != trimmedTitle else { return }

        project.title = trimmedTitle
        project.updatedAt = Date()
        project.appendEvent(kind: .renamed, message: "Renamed project to \(trimmedTitle)", limit: maxProjectEventCount)
        projectLibrary.projects[projectIndex] = project
        saveProjectLibrary()
    }

    func deleteProject(id: UUID) {
        let wasCurrentProject = currentProjectID == id

        do {
            try projectStore.deleteProject(id: id)
            refreshProjectLibrarySnapshot()
        } catch {
            print("Failed to delete project: \(error.localizedDescription)")
            projectLibrary.projects.removeAll { $0.id == id }
        }

        if wasCurrentProject {
            currentProjectID = nil
            projectLibrary.currentProjectID = nil
            clearLiveProjectState()
            saveProjectLibrary()
        }
    }

    func clearProjectHistory() {
        do {
            try projectStore.deleteAllProjects()
            projectLibrary = .empty
        } catch {
            print("Failed to clear project history: \(error.localizedDescription)")
            projectLibrary = .empty
            saveProjectLibrary()
        }

        currentProjectID = nil
        clearLiveProjectState()
    }

    func projectSourceURL(for project: PersistedProjectRecord) -> URL? {
        projectStore.existingURL(for: project.sourceRelativePath)
    }

    func projectLatestExportURL(for project: PersistedProjectRecord) -> URL? {
        projectStore.existingURL(for: project.latestExportRelativePath)
    }

    func projectThumbnailImage(for project: PersistedProjectRecord) -> UIImage? {
        return projectStore.thumbnailImage(for: project)
    }

    func canOpenProject(_ project: PersistedProjectRecord) -> Bool {
        projectSourceURL(for: project) != nil
    }

    private func applyDefaultRedundantClipSuppression() {
        analysisService.clips = defaultRedundantClipSuppressedClips(from: analysisService.clips)
    }

    private func recordAnalysisCompleted() {
        lastAnalyzedAt = Date()
        lastAnalysisStatusSummary = analysisService.statusMessage
        let count = analysisService.clips.count
        let message = "Analysis found \(count) highlight" + (count == 1 ? "" : "s")
        persistCurrentProject(reason: .analysisCompleted, message: message)
    }

    private func recordAnalysisFailure(message: String) {
        lastAnalysisStatusSummary = message
        persistCurrentProject(reason: .analysisFailed, message: message)
    }

    private func persistCurrentProject(reason: ProjectEventKind? = nil, message: String? = nil) {
        guard !suppressProjectPersistence,
              let currentProjectID,
              let projectIndex = projectLibrary.projects.firstIndex(where: { $0.id == currentProjectID }) else {
            return
        }

        let now = Date()
        var project = projectLibrary.projects[projectIndex]
        project.updatedAt = now
        project.lastOpenedAt = now
        project.sourceDuration = videoDuration > 0 ? videoDuration : project.sourceDuration
        project.totalClipCount = analysisService.clips.count
        project.keptClipCount = keptClips.count
        project.clips = analysisService.clips
        project.selectedTheme = selectedTheme
        project.selectedMusic = selectedMusic
        project.selectedQuality = selectedQuality
        project.selectedFormat = selectedFormat
        project.exportPostProcessing = exportPostProcessing
        project.analysisMode = analysisMode
        project.analysisStatusSummary = lastAnalysisStatusSummary
        project.cloudAnalysisJobID = cloudAnalysisJobID
        project.cloudEditSourceObjectKey = cloudEditSourceObjectKey
        project.highlightTeamSelection = settings.highlightTeamSelection
        project.opponentTeamName = settings.opponentTeamName
        project.cloudDetectedTeams = cloudDetectedTeams
        project.cloudDiagnostics = analysisService.lastCloudDiagnostics
        project.lastAnalyzedAt = lastAnalyzedAt
        project.lastExportedAt = lastExportedAt

        if let customAudioRelativePath = projectStore.managedRelativePath(for: customAudioURL) {
            project.customAudioRelativePath = customAudioRelativePath
        }

        if let latestExportRelativePath = projectStore.managedRelativePath(for: exportService.exportedURL) {
            project.latestExportRelativePath = latestExportRelativePath
            project.latestExportFilename = exportService.exportedURL?.lastPathComponent
        }

        if let reason, let message {
            project.appendEvent(kind: reason, message: message, limit: maxProjectEventCount)
        }

        projectLibrary.projects[projectIndex] = project
        projectLibrary.currentProjectID = currentProjectID
        saveProjectLibrary()
    }

    private func restoreCurrentProjectIfAvailable() {
        guard let currentProjectID = projectLibrary.currentProjectID,
              let project = projectLibrary.projects.first(where: { $0.id == currentProjectID }),
              projectSourceURL(for: project) != nil else {
            self.currentProjectID = nil
            projectLibrary.currentProjectID = nil
            saveProjectLibrary()
            return
        }

        applyPersistedProject(project)
    }

    private func applyPersistedProject(_ project: PersistedProjectRecord) {
        suppressProjectPersistence = true
        defer { suppressProjectPersistence = false }

        currentProjectID = project.id
        projectLibrary.currentProjectID = project.id
        videoURL = projectStore.existingURL(for: project.sourceRelativePath)
        videoDuration = project.sourceDuration
        videoThumbnail = projectThumbnailImage(for: project)?.cgImage
        isVideoLoaded = videoURL != nil

        analysisService.isAnalyzing = false
        analysisService.progress = 0
        analysisService.clips = project.clips
        analysisService.lastRunDiagnostics = nil
        analysisService.lastCloudDiagnostics = nil
        analysisService.statusMessage = project.analysisStatusSummary
            ?? (project.clips.isEmpty ? "" : "Found \(project.clips.count) highlight\(project.clips.count == 1 ? "" : "s")")

        exportService.isExporting = false
        exportService.exportProgress = 0
        exportService.exportedURL = projectStore.existingURL(for: project.latestExportRelativePath)
        exportService.statusMessage = project.latestExportRelativePath == nil ? "" : "Export ready"

        selectedTheme = project.selectedTheme
        selectedMusic = project.selectedMusic
        selectedQuality = project.selectedQuality
        selectedFormat = project.selectedFormat
        exportPostProcessing = project.exportPostProcessing
        customAudioURL = projectStore.existingURL(for: project.customAudioRelativePath)

        analysisMode = project.analysisMode ?? AppRuntimeConfig.shared.launchAnalysisMode
        cloudAnalysisJobID = project.cloudAnalysisJobID
        cloudEditSourceObjectKey = project.cloudEditSourceObjectKey
        settings.highlightTeamSelection = project.highlightTeamSelection ?? .allTeams
        settings.opponentTeamName = project.opponentTeamName
        cloudDetectedTeams = project.cloudDetectedTeams ?? []
        analysisService.lastCloudDiagnostics = project.cloudDiagnostics
        hasConfirmedHighlightTeamSelection = project.highlightTeamSelection != nil || cloudDetectedTeams.isEmpty
        clearPendingCloudAnalysisJob()
        lastAnalysisStatusSummary = project.analysisStatusSummary
        lastAnalyzedAt = project.lastAnalyzedAt
        lastExportedAt = project.lastExportedAt
        showingSaveSuccess = false
        cloudQuotaRemaining = nil
        isCloudFallbackOffered = false
    }

    private func clearLiveProjectState() {
        suppressProjectPersistence = true
        defer { suppressProjectPersistence = false }

        videoURL = nil
        videoDuration = 0
        videoThumbnail = nil
        isVideoLoaded = false

        analysisService.isAnalyzing = false
        analysisService.progress = 0
        analysisService.statusMessage = ""
        analysisService.clips = []
        analysisService.lastRunDiagnostics = nil
        analysisService.lastCloudDiagnostics = nil

        exportService.isExporting = false
        exportService.exportedURL = nil
        exportService.exportProgress = 0
        exportService.statusMessage = ""

        selectedTheme = .cinematic
        selectedMusic = .none
        selectedQuality = .high
        selectedFormat = .mp4
        exportPostProcessing = ExportPostProcessingOptions()
        customAudioURL = nil

        showingSaveSuccess = false
        analysisMode = AppRuntimeConfig.shared.launchAnalysisMode
        cloudQuotaRemaining = nil
        isCloudFallbackOffered = false
        lastAnalysisStatusSummary = nil
        cloudAnalysisJobID = nil
        cloudEditSourceObjectKey = nil
        cloudDetectedTeams = []
        hasConfirmedHighlightTeamSelection = false
        settings.highlightTeamSelection = .allTeams
        settings.opponentTeamName = nil
        clearPendingCloudAnalysisJob()
        lastAnalyzedAt = nil
        lastExportedAt = nil
    }

    private func clearPendingCloudAnalysisJob() {
        pendingCloudAnalysisJob = nil
        activeCloudTeamScanID = nil
        isCloudTeamScanInProgress = false
        cloudTeamScanStatusMessage = nil
        cloudTeamScanErrorMessage = nil
    }

    private func resetStaleHighlightTeamSelection(against detectedTeams: [CloudTeamOption]) {
        guard settings.highlightTeamSelection.mode == .team else { return }
        let selectedKey = settings.highlightTeamSelection.selectionKey
        let detectedKeys = Set(detectedTeams.flatMap { team in
            [
                team.teamId,
                team.colorLabel,
                team.label
            ].compactMap { $0 }
        })
        if !detectedKeys.contains(selectedKey) {
            settings.highlightTeamSelection = .allTeams
        }
    }

    private func sanitizedCustomTeamName(_ value: String?) -> String? {
        guard let value else { return nil }
        let collapsed = value
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: " ")
        guard !collapsed.isEmpty else { return nil }
        return String(collapsed.prefix(36))
    }

    private func insertProject(_ project: PersistedProjectRecord, makeCurrent: Bool) {
        projectLibrary.projects.removeAll { $0.id == project.id }
        projectLibrary.projects.insert(project, at: 0)

        if makeCurrent {
            currentProjectID = project.id
            projectLibrary.currentProjectID = project.id
        }

        trimHistoryIfNeeded()
        saveProjectLibrary()
    }

    private func trimHistoryIfNeeded() {
        while projectLibrary.projects.count > maxProjectCount {
            guard let removable = projectLibrary.projects
                .filter({ $0.id != currentProjectID })
                .sorted(by: { $0.lastOpenedAt < $1.lastOpenedAt })
                .first else {
                break
            }

            projectLibrary.projects.removeAll { $0.id == removable.id }
            try? projectStore.deleteProject(id: removable.id)
        }
    }

    private func saveProjectLibrary() {
        do {
            try projectStore.saveLibrary(projectLibrary)
        } catch {
            print("Failed to save project history: \(error.localizedDescription)")
        }
    }

    private func refreshProjectLibrarySnapshot() {
        if let reloadedLibrary = try? projectStore.loadLibrary() {
            projectLibrary = reloadedLibrary
            if currentProjectID == nil {
                currentProjectID = reloadedLibrary.currentProjectID
            } else {
                projectLibrary.currentProjectID = currentProjectID
            }
        }
    }

    private func repairBrokenProjectReferences() {
        var changed = false

        if projectLibrary.currentProjectID != nil,
           projectLibrary.projects.contains(where: { $0.id == projectLibrary.currentProjectID }) == false {
            projectLibrary.currentProjectID = nil
            currentProjectID = nil
            changed = true
        }

        for index in projectLibrary.projects.indices {
            if let exportPath = projectLibrary.projects[index].latestExportRelativePath,
               projectStore.existingURL(for: exportPath) == nil {
                projectLibrary.projects[index].latestExportRelativePath = nil
                projectLibrary.projects[index].latestExportFilename = nil
                changed = true
            }

            if let customAudioPath = projectLibrary.projects[index].customAudioRelativePath,
               projectStore.existingURL(for: customAudioPath) == nil {
                projectLibrary.projects[index].customAudioRelativePath = nil
                changed = true
            }

            if projectLibrary.currentProjectID == projectLibrary.projects[index].id,
               projectStore.existingURL(for: projectLibrary.projects[index].sourceRelativePath) == nil {
                projectLibrary.currentProjectID = nil
                currentProjectID = nil
                changed = true
            }
        }

        if changed {
            saveProjectLibrary()
        }
    }

    private func persistSettings() {
        guard let data = try? JSONEncoder().encode(settings) else { return }
        UserDefaults.standard.set(data, forKey: settingsDefaultsKey)
    }

    private func beginBackgroundAnalysisTask() {
        guard backgroundTaskID == .invalid else { return }
        backgroundTaskID = UIApplication.shared.beginBackgroundTask(withName: "HoopsAnalysis") { [weak self] in
            Task { @MainActor in
                self?.endBackgroundAnalysisTask()
            }
        }
    }

    private func endBackgroundAnalysisTask() {
        guard backgroundTaskID != .invalid else { return }
        UIApplication.shared.endBackgroundTask(backgroundTaskID)
        backgroundTaskID = .invalid
    }

    #if DEBUG
    private static var isAIEditLiveSmokeEnabled: Bool {
        AIEditUISmokeConfig.isEnabled
    }

    private static func applyAIEditLiveSmokeRuntimeOverrides() {
        guard isAIEditLiveSmokeEnabled else { return }

        if let analysisURL = AIEditUISmokeConfig.cloudAnalysisBaseURL {
            UserDefaults.standard.set(analysisURL, forKey: "hoops.cloudAnalysisBaseURL")
        }

        if let editURL = AIEditUISmokeConfig.cloudEditBaseURL {
            UserDefaults.standard.set(editURL, forKey: "hoops.cloudEditBaseURL")
        }

        if let installID = AIEditUISmokeConfig.installID {
            UserDefaults.standard.set(installID, forKey: "hoopsclips.installID.v1")
        }
    }

    private func applyAIEditLiveSmokeProjectIfNeeded() {
        guard Self.isAIEditLiveSmokeEnabled else { return }

        let fixture = AIEditUISmokeConfig.fixture
        if fixture == .teamChoice {
            applyTeamChoiceUISmokeProject()
            return
        }

        guard let resolvedSourceObjectKey = AIEditUISmokeConfig.sourceObjectKey else { return }

        currentProjectID = nil
        videoURL = nil
        videoDuration = 18
        videoThumbnail = nil
        isVideoLoaded = false
        analysisMode = .cloud
        cloudAnalysisJobID = "phase-edit3c-\(fixture.rawValue)-analysis"
        cloudEditSourceObjectKey = resolvedSourceObjectKey
        lastAnalysisStatusSummary = "Found 2 highlights"
        lastAnalyzedAt = Date()
        cloudQuotaRemaining = nil
        isCloudFallbackOffered = false

        analysisService.isAnalyzing = false
        analysisService.progress = 1
        analysisService.statusMessage = "Found 2 highlights"
        analysisService.lastRunDiagnostics = nil
        analysisService.clips = [
            Clip(
                startTime: 0,
                endTime: 5,
                action: .fastBreak,
                confidence: 0.95,
                isKept: true,
                label: "Fast Break",
                audioScore: 0.48,
                visualScore: 0.95,
                motionScore: 0.94,
                combinedScore: 0.95,
                playbackSpeed: 1,
                isSlowMotionEnabled: true,
                detectionMethod: .cloud
            ),
            Clip(
                startTime: 8,
                endTime: 13,
                action: .madeShot,
                confidence: 0.90,
                isKept: true,
                label: "Made Shot",
                audioScore: 0.45,
                visualScore: 0.90,
                motionScore: 0.89,
                combinedScore: 0.90,
                playbackSpeed: 1,
                isSlowMotionEnabled: false,
                detectionMethod: .cloud
            )
        ]
    }

    private func applyTeamChoiceUISmokeProject() {
        currentProjectID = nil
        videoURL = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("hoopclips-team-choice-ui-smoke.mov")
        videoDuration = 64
        videoThumbnail = nil
        isVideoLoaded = true
        analysisMode = .cloud
        cloudAnalysisJobID = nil
        cloudEditSourceObjectKey = nil
        lastAnalysisStatusSummary = nil
        lastAnalyzedAt = nil
        cloudQuotaRemaining = nil
        isCloudFallbackOffered = false
        pendingCloudAnalysisJob = nil
        cloudDetectedTeams = [
            CloudTeamOption(
                teamId: "team_blue",
                label: "Blue jerseys",
                colorLabel: "blue",
                primaryColorHex: "#2563EB",
                confidence: 0.91,
                source: "debug_ui_smoke"
            ),
            CloudTeamOption(
                teamId: "team_white",
                label: "White jerseys",
                colorLabel: "white",
                primaryColorHex: "#F8FAFC",
                confidence: 0.88,
                source: "debug_ui_smoke"
            )
        ]
        settings.highlightTeamSelection = .allTeams
        hasConfirmedHighlightTeamSelection = false
        isCloudTeamScanInProgress = false
        cloudTeamScanStatusMessage = "Choose a team before analysis"
        cloudTeamScanErrorMessage = nil

        analysisService.isAnalyzing = false
        analysisService.progress = 0
        analysisService.statusMessage = "Choose a team before analysis"
        analysisService.lastRunDiagnostics = nil
        analysisService.clips = []
    }
    #endif

    private func fallbackToLocalAnalysis(from error: CloudAnalysisError) async {
        let hardFailureCodes: Set<String> = ["unsupported_duration", "file_too_large"]
        cloudAnalysisJobID = nil
        cloudEditSourceObjectKey = nil
        if AppConstants.requiresCloudVideoPipeline {
            let message = "Cloud analysis is required for this build. \(error.localizedDescription)"
            analysisMode = .cloud
            isCloudFallbackOffered = false
            analysisService.finishExternalAnalysis(with: message)
            recordAnalysisFailure(message: message)
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "analysis.failed",
                metadata: "mode=cloud reason=\(error.localizedDescription)"
            )
            return
        }

        if case .notConfigured = error {
            analysisMode = .localFallback
            isCloudFallbackOffered = false
            guard let url = videoURL else {
                analysisService.finishExternalAnalysis(with: error.localizedDescription)
                recordAnalysisFailure(message: error.localizedDescription)
                LaunchTelemetry.shared.recordStabilityCheckpoint(
                    "analysis.failed",
                    metadata: "mode=localFallback reason=\(error.localizedDescription)"
                )
                return
            }
            analysisService.updateExternalAnalysis(progress: 0.0, status: "Analyzing on device")
            await analysisService.analyze(url: url, settings: settings)
            applyDefaultRedundantClipSuppression()
            AnalysisNotificationService.shared.notifyAnalysisCompleted(
                clipsCount: analysisService.clips.count,
                usedFallback: false
            )
            recordAnalysisCompleted()
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "analysis.completed",
                metadata: "mode=localFallback clips=\(analysisService.clips.count)"
            )
            return
        }

        if case .backend(let code, let message) = error, hardFailureCodes.contains(code) {
            analysisMode = .cloud
            analysisService.finishExternalAnalysis(with: message)
            isCloudFallbackOffered = false
            recordAnalysisFailure(message: message)
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "analysis.failed",
                metadata: "mode=cloud code=\(code)"
            )
            return
        }

        analysisMode = .localFallback
        isCloudFallbackOffered = true
        analysisService.updateExternalAnalysis(progress: 0.0, status: "Analyzing on device")
        guard let url = videoURL else {
            analysisService.finishExternalAnalysis(with: error.localizedDescription)
            recordAnalysisFailure(message: error.localizedDescription)
            LaunchTelemetry.shared.recordStabilityCheckpoint(
                "analysis.failed",
                metadata: "mode=localFallback reason=\(error.localizedDescription)"
            )
            return
        }
        await analysisService.analyze(url: url, settings: settings)
        applyDefaultRedundantClipSuppression()
        AnalysisNotificationService.shared.notifyAnalysisCompleted(
            clipsCount: analysisService.clips.count,
            usedFallback: true
        )
        recordAnalysisCompleted()
        LaunchTelemetry.shared.recordStabilityCheckpoint(
            "analysis.completed",
            metadata: "mode=localFallback clips=\(analysisService.clips.count)"
        )
    }
}

internal func defaultRedundantClipSuppressedClips(from clips: [Clip]) -> [Clip] {
    let keptIndices = clips.indices
        .filter { clips[$0].isKept }
        .sorted { clips[$0].startTime < clips[$1].startTime }
    guard keptIndices.count > 1 else { return clips }

    var updated = clips
    var visited: Set<Int> = []

    for seedIndex in keptIndices {
        guard !visited.contains(seedIndex) else { continue }
        visited.insert(seedIndex)

        var cluster = [seedIndex]
        var frontier = [seedIndex]

        while let currentIndex = frontier.popLast() {
            for candidateIndex in keptIndices where !visited.contains(candidateIndex) {
                if clipsShouldBeClusteredAsRedundant(clips[currentIndex], clips[candidateIndex]) {
                    visited.insert(candidateIndex)
                    frontier.append(candidateIndex)
                    cluster.append(candidateIndex)
                }
            }
        }

        guard cluster.count > 1 else { continue }

        var winningIndex = cluster[0]
        for candidateIndex in cluster.dropFirst() {
            if isPreferredRedundantClipCandidate(clips[candidateIndex], over: clips[winningIndex]) {
                winningIndex = candidateIndex
            }
        }

        for losingIndex in cluster where losingIndex != winningIndex {
            updated[losingIndex].isKept = false
        }
    }

    return updated
}

internal func clipsShouldBeClusteredAsRedundant(_ lhs: Clip, _ rhs: Clip) -> Bool {
    if clipOverlapRatio(lhs, rhs) > 0.35 {
        return true
    }

    guard lhs.action == rhs.action, lhs.action != .unknown else {
        return false
    }

    return abs(lhs.startTime - rhs.startTime) <= 2.0
}

internal func clipOverlapRatio(_ lhs: Clip, _ rhs: Clip) -> Double {
    let intersection = max(0.0, min(lhs.endTime, rhs.endTime) - max(lhs.startTime, rhs.startTime))
    guard intersection > 0 else { return 0.0 }

    let baseline = min(lhs.duration, rhs.duration)
    guard baseline > 0 else { return 0.0 }

    return intersection / baseline
}

internal func isPreferredRedundantClipCandidate(_ lhs: Clip, over rhs: Clip) -> Bool {
    if lhs.combinedScore != rhs.combinedScore {
        return lhs.combinedScore > rhs.combinedScore
    }

    if lhs.confidence != rhs.confidence {
        return lhs.confidence > rhs.confidence
    }

    if lhs.duration != rhs.duration {
        return lhs.duration < rhs.duration
    }

    return lhs.startTime < rhs.startTime
}

private extension Error {
    var isTaskCancellation: Bool {
        if self is CancellationError {
            return true
        }

        if let urlError = self as? URLError, urlError.code == .cancelled {
            return true
        }

        let nsError = self as NSError
        if nsError.domain == NSURLErrorDomain && nsError.code == NSURLErrorCancelled {
            return true
        }

        if nsError.localizedDescription.localizedCaseInsensitiveContains("cancel") {
            return true
        }

        if let underlying = nsError.userInfo[NSUnderlyingErrorKey] as? Error {
            return underlying.isTaskCancellation
        }

        return false
    }
}
