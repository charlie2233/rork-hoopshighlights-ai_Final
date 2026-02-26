import Foundation
import AVFoundation
import PhotosUI
import SwiftUI

@Observable
@MainActor
final class HighlightsViewModel {
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
    var settings = AnalysisSettings()

    var clips: [Clip] { analysisService.clips }

    var keptClips: [Clip] { clips.filter(\.isKept) }
    var discardedClips: [Clip] { clips.filter { !$0.isKept } }

    var showingVideoPicker = false
    var showingExportComplete = false
    var showingSaveSuccess = false

    func loadVideo(url: URL) async {
        let accessing = url.startAccessingSecurityScopedResource()
        defer { if accessing { url.stopAccessingSecurityScopedResource() } }

        let tempURL = URL.temporaryDirectory.appending(path: url.lastPathComponent)
        try? FileManager.default.removeItem(at: tempURL)
        do {
            try FileManager.default.copyItem(at: url, to: tempURL)
        } catch {
            return
        }

        videoURL = tempURL
        let asset = AVURLAsset(url: tempURL)

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

    func exportHighlights() async {
        guard let url = videoURL else { return }
        await exportService.exportHighlights(
            sourceURL: url,
            clips: keptClips,
            theme: selectedTheme,
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
}
