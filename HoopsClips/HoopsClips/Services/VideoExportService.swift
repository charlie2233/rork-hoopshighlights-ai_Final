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
        quality: ExportQuality,
        format: ExportFileFormat
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
            let sourceDuration = try await asset.load(.duration)
            let sourceDurationSeconds = CMTimeGetSeconds(sourceDuration)
            let sourceVideoTracks = try await asset.loadTracks(withMediaType: .video)
            let sourceAudioTracks = try await asset.loadTracks(withMediaType: .audio)

            guard let sourceVideo = sourceVideoTracks.first else {
                statusMessage = "No video track found"
                isExporting = false
                return
            }

            let sourceTransform = try await sourceVideo.load(.preferredTransform)
            videoTrack.preferredTransform = sourceTransform

            let timelineSegments = buildTimelineSegments(from: keptClips, assetDuration: sourceDurationSeconds)
            guard !timelineSegments.isEmpty else {
                statusMessage = "No clips to export"
                isExporting = false
                return
            }

            var insertTime = CMTime.zero
            for (index, segment) in timelineSegments.enumerated() {
                let range = segment.sourceTimeRange()

                try videoTrack.insertTimeRange(range, of: sourceVideo, at: insertTime)

                if let sourceAudio = sourceAudioTracks.first {
                    try audioTrack.insertTimeRange(range, of: sourceAudio, at: insertTime)
                }

                insertTime = insertTime + range.duration

                exportProgress = Double(index + 1) / Double(timelineSegments.count) * 0.5
                statusMessage = "Adding clip \(index + 1) of \(timelineSegments.count)..."
            }

            statusMessage = "Preparing theme overlays..."

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

            let preferredType = format.avFileType
            let outputType: AVFileType
            if exportSession.supportedFileTypes.contains(preferredType) {
                outputType = preferredType
            } else if exportSession.supportedFileTypes.contains(.mp4) {
                outputType = .mp4
            } else if let first = exportSession.supportedFileTypes.first {
                outputType = first
            } else {
                statusMessage = "No supported export file types"
                isExporting = false
                return
            }

            let fileExtension: String = switch outputType {
            case .mov: "mov"
            case .mp4: "mp4"
            default: format.fileExtension
            }

            let outputURL = URL.temporaryDirectory.appending(path: "HoopsHighlight_\(Int(Date().timeIntervalSince1970)).\(fileExtension)")
            exportSession.outputURL = outputURL
            exportSession.outputFileType = outputType
            exportSession.shouldOptimizeForNetworkUse = true

            do {
                let renderer = ExportThemeRenderer()
                let themedComposition = try await renderer.makeThemedVideoComposition(
                    asset: composition,
                    sourceVideoTrack: sourceVideo,
                    segments: timelineSegments,
                    theme: theme,
                    quality: quality
                )
                exportSession.videoComposition = themedComposition
            } catch {
                statusMessage = "Theme rendering unavailable, exporting without effects"
            }

            statusMessage = "Rendering \(theme.rawValue) export..."

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
