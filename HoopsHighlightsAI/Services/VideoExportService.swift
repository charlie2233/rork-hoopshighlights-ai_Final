import Foundation
import AVFoundation
import Photos

@Observable
@MainActor
final class VideoExportService {
    var isExporting = false
    var exportProgress: Double = 0.0
    var statusMessage = ""
    var exportedURL: URL?

    func exportHighlights(
        sourceURL: URL,
        clips: [Clip],
        theme: ExportTheme,
        quality: ExportQuality
    ) async {
        isExporting = true
        exportProgress = 0.0
        statusMessage = "Preparing export..."
        exportedURL = nil

        let asset = AVURLAsset(url: sourceURL)

        let composition = AVMutableComposition()
        guard let videoTrack = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid),
              let audioTrack = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) else {
            statusMessage = "Failed to create composition"
            isExporting = false
            return
        }

        let keptClips = clips.filter(\.isKept).sorted { $0.startTime < $1.startTime }
        guard !keptClips.isEmpty else {
            statusMessage = "No clips to export"
            isExporting = false
            return
        }

        do {
            let sourceVideoTracks = try await asset.loadTracks(withMediaType: .video)
            let sourceAudioTracks = try await asset.loadTracks(withMediaType: .audio)

            guard let sourceVideo = sourceVideoTracks.first else {
                statusMessage = "No video track found"
                isExporting = false
                return
            }

            var insertTime = CMTime.zero

            for (index, clip) in keptClips.enumerated() {
                let startCM = CMTime(seconds: clip.startTime, preferredTimescale: 600)
                let endCM = CMTime(seconds: clip.endTime, preferredTimescale: 600)
                let range = CMTimeRange(start: startCM, end: endCM)

                try videoTrack.insertTimeRange(range, of: sourceVideo, at: insertTime)

                if let sourceAudio = sourceAudioTracks.first {
                    try audioTrack.insertTimeRange(range, of: sourceAudio, at: insertTime)
                }

                insertTime = CMTimeAdd(insertTime, CMTimeSubtract(endCM, startCM))

                exportProgress = Double(index + 1) / Double(keptClips.count) * 0.5
                statusMessage = "Adding clip \(index + 1) of \(keptClips.count)..."
            }

            statusMessage = "Rendering video..."

            let presetName: String
            switch quality {
            case .standard: presetName = AVAssetExportPreset1280x720
            case .high: presetName = AVAssetExportPreset1920x1080
            case .ultra: presetName = AVAssetExportPresetHighestQuality
            }

            guard let exportSession = AVAssetExportSession(asset: composition, presetName: presetName) else {
                statusMessage = "Failed to create export session"
                isExporting = false
                return
            }

            let outputURL = URL.temporaryDirectory.appending(path: "HoopsHighlight_\(Int(Date().timeIntervalSince1970)).mp4")
            exportSession.outputURL = outputURL
            exportSession.outputFileType = .mp4
            exportSession.shouldOptimizeForNetworkUse = true

            let timer = Timer.scheduledTimer(withTimeInterval: 0.2, repeats: true) { [weak self] _ in
                Task { @MainActor in
                    self?.exportProgress = 0.5 + Double(exportSession.progress) * 0.5
                }
            }

            await exportSession.export()
            timer.invalidate()

            if exportSession.status == .completed {
                exportedURL = outputURL
                exportProgress = 1.0
                statusMessage = "Export complete!"
            } else {
                statusMessage = "Export failed: \(exportSession.error?.localizedDescription ?? "Unknown error")"
            }
        } catch {
            statusMessage = "Error: \(error.localizedDescription)"
        }

        isExporting = false
    }

    func saveToPhotos(url: URL) async -> Bool {
        do {
            try await PHPhotoLibrary.shared().performChanges {
                PHAssetChangeRequest.creationRequestForAssetFromVideo(atFileURL: url)
            }
            return true
        } catch {
            statusMessage = "Failed to save: \(error.localizedDescription)"
            return false
        }
    }
}
