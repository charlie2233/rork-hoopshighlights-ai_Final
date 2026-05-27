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
            return "Run cloud analysis first so Hoopclips has the uploaded source video."
        }
        if keptClips.isEmpty {
            return "Keep at least one clip before making an AI edit."
        }
        return nil
    }

    var availableHighlightTeamChoices: [HighlightTeamSelection] {
        let scannedChoices = cloudDetectedTeams.map { team in
            HighlightTeamSelection(
                mode: .team,
                teamId: team.teamId,
                label: team.label,
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
    func loadVideo(url: URL) async -> Bool {
        let accessing = url.startAccessingSecurityScopedResource()
        defer { if accessing { url.stopAccessingSecurityScopedResource() } }

        persistCurrentProject()

        do {
            try Task.checkCancellation()
            clearPendingCloudAnalysisJob()
            settings.highlightTeamSelection = .allTeams
            let project = try await projectStore.createProjectFromImportedVideo(sourceURL: url.standardizedFileURL)
            try Task.checkCancellation()
            insertProject(project, makeCurrent: true)
            applyPersistedProject(project)
            persistCurrentProject(reason: .imported, message: "Imported \(project.sourceFilename)")
            return true
        } catch is CancellationError {
            return false
        } catch {
            print("Failed to load video: \(error.localizedDescription)")
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

        analysisService.updateSettings(settings)

        guard AppConstants.cloudAnalysisEnabled else {
            await runPrimaryLocalAnalysis(for: url, status: "Analyzing on device")
            return
        }

        analysisMode = .cloud
        isCloudFallbackOffered = false
        analysisService.beginExternalAnalysis(status: "Preparing upload")

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
            pendingCloudAnalysisJob = nil
            applyDefaultRedundantClipSuppression()
            AnalysisNotificationService.shared.notifyAnalysisCompleted(
                clipsCount: analysisService.clips.count,
                usedFallback: false
            )
            recordAnalysisCompleted()
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

        isCloudTeamScanInProgress = true
        cloudTeamScanErrorMessage = nil
        cloudTeamScanStatusMessage = "Preparing team scan"
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
        } catch is CancellationError {
            if videoURL?.standardizedFileURL == scanSourceURL {
                clearPendingCloudAnalysisJob()
            }
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
        } catch {
            guard videoURL?.standardizedFileURL == scanSourceURL else { return }
            cloudTeamScanErrorMessage = error.localizedDescription
            cloudTeamScanStatusMessage = "Team scan unavailable"
            pendingCloudAnalysisJob = nil
            cloudDetectedTeams = []
            settings.highlightTeamSelection = .allTeams
            hasConfirmedHighlightTeamSelection = true
        }

        isCloudTeamScanInProgress = false
    }

    func confirmHighlightTeamSelection(_ selection: HighlightTeamSelection) {
        settings.highlightTeamSelection = selection
        hasConfirmedHighlightTeamSelection = true
        if !cloudDetectedTeams.isEmpty {
            cloudTeamScanStatusMessage = selection.mode == .all
                ? "All teams selected"
                : "\(selection.displayTitle) selected"
        }
    }

    private func runPrimaryLocalAnalysis(for url: URL, status: String) async {
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
        for index in analysisService.clips.indices where analysisService.clips[index].confidence >= 0.8 {
            analysisService.clips[index].isKept = true
        }
        persistCurrentProject()
    }

    func discardLowConfidenceClips() {
        for index in analysisService.clips.indices where analysisService.clips[index].confidence < 0.5 {
            analysisService.clips[index].isKept = false
        }
        persistCurrentProject()
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
            exportService.markUnavailable("Cloud rendering is required for this build. Use AI Edit to render, preview, download, or share.")
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

        let candidates = Self.rankedCloudEditCandidateClips(from: keptClips).map { clip in
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
                duplicateGroup: nil,
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

    nonisolated static func rankedCloudEditCandidateClips(from clips: [Clip], limit: Int = 40) -> [Clip] {
        let ranked = clips.sorted { lhs, rhs in
            let lhsEligible = isCloudEditCandidateQualityEligible(lhs)
            let rhsEligible = isCloudEditCandidateQualityEligible(rhs)
            if lhsEligible != rhsEligible {
                return lhsEligible
            }

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

        return ranked.prefix(max(0, limit)).sorted { $0.startTime < $1.startTime }
    }

    nonisolated private static func isCloudEditCandidateQualityEligible(_ clip: Clip) -> Bool {
        guard clip.duration >= 2.0 else { return false }
        guard isShotLikeCloudEditCandidate(clip) else { return true }
        let center = clip.eventCenter ?? (clip.startTime + (clip.duration / 2.0))
        let leadIn = center - clip.startTime
        let followThrough = clip.endTime - center
        return leadIn >= 0.75 && followThrough >= 0.45
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
            if leadIn >= 0.75 && followThrough >= 0.45 {
                score += 0.08
            } else if isShotLikeCloudEditCandidate(clip) {
                score -= 0.30
            }
        } else if isShotLikeCloudEditCandidate(clip) {
            score -= 0.04
        }

        return score
    }

    nonisolated private static func isShotLikeCloudEditCandidate(_ clip: Clip) -> Bool {
        let text = "\(clip.label) \(clip.action.rawValue)".lowercased()
        return ["shot", "bucket", "basket", "layup", "dunk", "finish", "jumper", "three", "3pt"].contains { text.contains($0) }
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
        cloudDetectedTeams = []
        hasConfirmedHighlightTeamSelection = false
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
        clearPendingCloudAnalysisJob()
        lastAnalyzedAt = nil
        lastExportedAt = nil
    }

    private func clearPendingCloudAnalysisJob() {
        pendingCloudAnalysisJob = nil
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
            return
        }

        if case .notConfigured = error {
            analysisMode = .localFallback
            isCloudFallbackOffered = false
            guard let url = videoURL else {
                analysisService.finishExternalAnalysis(with: error.localizedDescription)
                recordAnalysisFailure(message: error.localizedDescription)
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
            return
        }

        if case .backend(let code, let message) = error, hardFailureCodes.contains(code) {
            analysisMode = .cloud
            analysisService.finishExternalAnalysis(with: message)
            isCloudFallbackOffered = false
            recordAnalysisFailure(message: message)
            return
        }

        analysisMode = .localFallback
        isCloudFallbackOffered = true
        analysisService.updateExternalAnalysis(progress: 0.0, status: "Analyzing on device")
        guard let url = videoURL else {
            analysisService.finishExternalAnalysis(with: error.localizedDescription)
            recordAnalysisFailure(message: error.localizedDescription)
            return
        }
        await analysisService.analyze(url: url, settings: settings)
        applyDefaultRedundantClipSuppression()
        AnalysisNotificationService.shared.notifyAnalysisCompleted(
            clipsCount: analysisService.clips.count,
            usedFallback: true
        )
        recordAnalysisCompleted()
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
