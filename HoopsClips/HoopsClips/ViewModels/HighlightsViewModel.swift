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
    private var backgroundTaskID: UIBackgroundTaskIdentifier = .invalid

    var videoURL: URL?
    var videoDuration: Double = 0
    var videoThumbnail: CGImage?
    var isVideoLoaded = false

    var analysisService = VideoAnalysisService()
    var cloudAnalysisService = CloudAnalysisService()
    var exportService = VideoExportService()

    var selectedTheme: ExportTheme = .cinematic
    var selectedMusic: MusicTrack = .none
    var selectedQuality: ExportQuality = .high
    var selectedFormat: ExportFileFormat = .mp4
    var exportPostProcessing = ExportPostProcessingOptions()
    var customAudioURL: URL?
    let installID: String
    var settings: AnalysisSettings {
        didSet { persistSettings() }
    }

    var clips: [Clip] { analysisService.clips }

    var keptClips: [Clip] { clips.filter(\.isKept) }
    var discardedClips: [Clip] { clips.filter { !$0.isKept } }

    var showingVideoPicker = false
    var showingSaveSuccess = false
    var analysisMode: AnalysisExecutionMode = .cloud
    var cloudQuotaRemaining: Int?
    var isCloudFallbackOffered = false

    init() {
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
    }

    func loadVideo(url: URL) async {
        let accessing = url.startAccessingSecurityScopedResource()
        defer { if accessing { url.stopAccessingSecurityScopedResource() } }

        let sourceURL = url.standardizedFileURL
        let tempURL = URL.temporaryDirectory.appending(path: sourceURL.lastPathComponent).standardizedFileURL
        let workingURL: URL

        if sourceURL == tempURL {
            // Already in app temp location (for example PhotosPicker data import); no copy needed.
            workingURL = sourceURL
        } else {
            try? FileManager.default.removeItem(at: tempURL)
            do {
                try FileManager.default.copyItem(at: sourceURL, to: tempURL)
                workingURL = tempURL
            } catch {
                print("Failed to copy video: \(error.localizedDescription)")
                return
            }
        }

        videoURL = workingURL
        let asset = AVURLAsset(url: workingURL)

        if let duration = try? await asset.load(.duration) {
            videoDuration = CMTimeGetSeconds(duration)
        }

        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.maximumSize = CGSize(width: 400, height: 225)
        if let (image, _) = try? await generator.image(at: .zero) {
            videoThumbnail = image
        }

        isVideoLoaded = true
    }

    func startAnalysis() async {
        guard let url = videoURL else { return }
        await AnalysisNotificationService.shared.prepareForAnalysis()
        beginBackgroundAnalysisTask()
        defer { endBackgroundAnalysisTask() }

        analysisMode = .cloud
        isCloudFallbackOffered = false
        analysisService.updateSettings(settings)
        analysisService.beginExternalAnalysis(status: "Preparing upload")

        do {
            let result = try await cloudAnalysisService.analyzeVideo(
                url: url,
                duration: videoDuration,
                installID: installID
            ) { [weak service = analysisService] progress, status in
                service?.updateExternalAnalysis(progress: progress, status: status)
            }
            cloudQuotaRemaining = nil
            analysisService.applyCloudAnalysis(result, duration: videoDuration)
            applyDefaultRedundantClipSuppression()
            AnalysisNotificationService.shared.notifyAnalysisCompleted(
                clipsCount: analysisService.clips.count,
                usedFallback: false
            )
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

    func toggleClip(_ clip: Clip) {
        guard let index = analysisService.clips.firstIndex(where: { $0.id == clip.id }) else { return }
        analysisService.clips[index].isKept.toggle()
    }

    func toggleSlowMotion(_ clip: Clip) {
        guard let index = analysisService.clips.firstIndex(where: { $0.id == clip.id }) else { return }
        analysisService.clips[index].isSlowMotionEnabled.toggle()
    }

    func keepAllClips() {
        for i in analysisService.clips.indices {
            analysisService.clips[i].isKept = true
        }
    }

    func discardAllClips() {
        for i in analysisService.clips.indices {
            analysisService.clips[i].isKept = false
        }
    }

    func keepHighConfidenceClips() {
        for i in analysisService.clips.indices where analysisService.clips[i].confidence >= 0.8 {
            analysisService.clips[i].isKept = true
        }
    }

    func discardLowConfidenceClips() {
        for i in analysisService.clips.indices where analysisService.clips[i].confidence < 0.5 {
            analysisService.clips[i].isKept = false
        }
    }

    func selectCustomAudio(url: URL) {
        let accessing = url.startAccessingSecurityScopedResource()
        defer { if accessing { url.stopAccessingSecurityScopedResource() } }
        
        let tempURL = URL.temporaryDirectory.appending(path: "custom_audio_" + url.lastPathComponent)
        try? FileManager.default.removeItem(at: tempURL)
        do {
            try FileManager.default.copyItem(at: url, to: tempURL)
            customAudioURL = tempURL
            selectedMusic = .custom
        } catch {
            print("Failed to copy audio: \(error)")
        }
    }

    func exportHighlights(isProUser: Bool) async {
        guard let url = videoURL else { return }
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
    }

    func saveToPhotos() async {
        guard let url = exportService.exportedURL else { return }
        let success = await exportService.saveToPhotos(url: url)
        if success {
            showingSaveSuccess = true
        }
    }

    func resetProject() {
        videoURL = nil
        videoDuration = 0
        videoThumbnail = nil
        isVideoLoaded = false
        analysisService.clips = []
        analysisService.progress = 0
        analysisService.statusMessage = ""
        exportService.exportedURL = nil
        exportService.exportProgress = 0
    }

    private func applyDefaultRedundantClipSuppression() {
        analysisService.clips = defaultRedundantClipSuppressedClips(from: analysisService.clips)
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

    private func fallbackToLocalAnalysis(from error: CloudAnalysisError) async {
        let hardFailureCodes: Set<String> = ["unsupported_duration", "file_too_large"]
        if case .notConfigured = error {
            analysisMode = .localFallback
            isCloudFallbackOffered = false
            guard let url = videoURL else {
                analysisService.finishExternalAnalysis(with: error.localizedDescription)
                return
            }
            analysisService.updateExternalAnalysis(progress: 0.0, status: "Analyzing on device")
            await analysisService.analyze(url: url, settings: settings)
            applyDefaultRedundantClipSuppression()
            AnalysisNotificationService.shared.notifyAnalysisCompleted(
                clipsCount: analysisService.clips.count,
                usedFallback: false
            )
            return
        }

        if case .backend(let code, let message) = error, hardFailureCodes.contains(code) {
            analysisMode = .cloud
            analysisService.finishExternalAnalysis(with: message)
            isCloudFallbackOffered = false
            return
        }

        analysisMode = .localFallback
        isCloudFallbackOffered = true
        analysisService.updateExternalAnalysis(progress: 0.0, status: "Falling back to local analysis")
        guard let url = videoURL else {
            analysisService.finishExternalAnalysis(with: error.localizedDescription)
            return
        }
        await analysisService.analyze(url: url, settings: settings)
        applyDefaultRedundantClipSuppression()
        AnalysisNotificationService.shared.notifyAnalysisCompleted(
            clipsCount: analysisService.clips.count,
            usedFallback: true
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
