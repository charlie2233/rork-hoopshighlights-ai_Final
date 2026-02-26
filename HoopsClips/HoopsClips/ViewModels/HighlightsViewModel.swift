import Foundation
import AVFoundation
import PhotosUI
import SwiftUI

@Observable
@MainActor
final class HighlightsViewModel {
    private let settingsDefaultsKey = "hoopsclips.analysisSettings.v1"

    var videoURL: URL?
    var videoDuration: Double = 0
    var videoThumbnail: CGImage?
    var isVideoLoaded = false

    var analysisService = VideoAnalysisService()
    var exportService = VideoExportService()

    var selectedTheme: ExportTheme = .cinematic
    var selectedMusic: MusicTrack = .none
    var selectedQuality: ExportQuality = .high
    var selectedFormat: ExportFileFormat = .mp4
    var customAudioURL: URL?
    var settings: AnalysisSettings {
        didSet { persistSettings() }
    }

    var clips: [Clip] { analysisService.clips }

    var keptClips: [Clip] { clips.filter(\.isKept) }
    var discardedClips: [Clip] { clips.filter { !$0.isKept } }

    var showingVideoPicker = false
    var showingExportComplete = false
    var showingSaveSuccess = false

    init() {
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
        await analysisService.analyze(url: url, settings: settings)
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
            format: selectedFormat
        )
        if exportService.exportedURL != nil {
            showingExportComplete = true
        }
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

    private func persistSettings() {
        guard let data = try? JSONEncoder().encode(settings) else { return }
        UserDefaults.standard.set(data, forKey: settingsDefaultsKey)
    }
}
