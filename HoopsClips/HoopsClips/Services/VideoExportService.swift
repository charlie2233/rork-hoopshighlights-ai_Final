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
        music: MusicTrack,
        customMusicURL: URL? = nil,
        isProUser: Bool,
        quality: ExportQuality,
        format: ExportFileFormat
    ) async {
        exportedURL = nil

        if let restrictionMessage = premiumRestrictionMessage(theme: theme, music: music, isProUser: isProUser) {
            isExporting = false
            exportProgress = 0.0
            statusMessage = restrictionMessage
            return
        }

        isExporting = true
        exportProgress = 0.0
        statusMessage = "Preparing export..."

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
                let clip = keptClips.first { $0.id == segment.clipID }
                
                // Normal speed insertion
                if clip?.isSlowMotionEnabled == true {
                    // Slow motion logic: Normal -> Slow -> Normal
                    // Center of the clip is the "action peak"
                    let totalDuration = range.duration
                    let slowMoDuration = CMTime(seconds: 1.5, preferredTimescale: 600) // 1.5s of action slowed down
                    
                    if totalDuration > slowMoDuration {
                        let midPoint = range.start + CMTime(seconds: totalDuration.seconds / 2.0, preferredTimescale: 600)
                        let slowStart = midPoint - CMTime(seconds: slowMoDuration.seconds / 2.0, preferredTimescale: 600)
                        let slowEnd = midPoint + CMTime(seconds: slowMoDuration.seconds / 2.0, preferredTimescale: 600)
                        
                        // 1. Pre-slowmo (Normal speed)
                        let preRange = CMTimeRange(start: range.start, end: slowStart)
                        try videoTrack.insertTimeRange(preRange, of: sourceVideo, at: insertTime)
                        if let sourceAudio = sourceAudioTracks.first {
                            try audioTrack.insertTimeRange(preRange, of: sourceAudio, at: insertTime)
                        }
                        insertTime = insertTime + preRange.duration
                        
                        // 2. Slow motion (0.5x speed -> 2x duration)
                        let slowRange = CMTimeRange(start: slowStart, end: slowEnd)
                        let slowDuration = CMTime(seconds: slowRange.duration.seconds * 2.0, preferredTimescale: 600)
                        try videoTrack.insertTimeRange(slowRange, of: sourceVideo, at: insertTime)
                        videoTrack.scaleTimeRange(CMTimeRange(start: insertTime, duration: slowRange.duration), toDuration: slowDuration)
                        
                        // Audio for slow motion (pitch preserved automatically by AVExportSession usually, or we accept deep voice)
                        if let sourceAudio = sourceAudioTracks.first {
                            try audioTrack.insertTimeRange(slowRange, of: sourceAudio, at: insertTime)
                            audioTrack.scaleTimeRange(CMTimeRange(start: insertTime, duration: slowRange.duration), toDuration: slowDuration)
                        }
                        insertTime = insertTime + slowDuration
                        
                        // 3. Post-slowmo (Normal speed)
                        let postRange = CMTimeRange(start: slowEnd, end: range.end)
                        try videoTrack.insertTimeRange(postRange, of: sourceVideo, at: insertTime)
                        if let sourceAudio = sourceAudioTracks.first {
                            try audioTrack.insertTimeRange(postRange, of: sourceAudio, at: insertTime)
                        }
                        insertTime = insertTime + postRange.duration
                        
                    } else {
                        // Clip too short for fancy slow-mo, just insert normally
                        try videoTrack.insertTimeRange(range, of: sourceVideo, at: insertTime)
                        if let sourceAudio = sourceAudioTracks.first {
                            try audioTrack.insertTimeRange(range, of: sourceAudio, at: insertTime)
                        }
                        insertTime = insertTime + range.duration
                    }
                } else {
                    // Standard insertion
                    try videoTrack.insertTimeRange(range, of: sourceVideo, at: insertTime)
                    
                    if let sourceAudio = sourceAudioTracks.first {
                        try audioTrack.insertTimeRange(range, of: sourceAudio, at: insertTime)
                    }
                    
                    insertTime = insertTime + range.duration
                }

                exportProgress = Double(index + 1) / Double(timelineSegments.count) * 0.5
                statusMessage = "Adding clip \(index + 1) of \(timelineSegments.count)..."
            }

            var audioMix: AVMutableAudioMix?
            
            var effectiveMusicURL: URL?
            if music == .custom, let customURL = customMusicURL {
                effectiveMusicURL = customURL
                statusMessage = "Adding custom audio..."
            } else if let musicFilename = music.filename {
                statusMessage = "Adding background music..."
                
                // Find music file - check root and subdirectory
                var musicURL = Bundle.main.url(forResource: musicFilename, withExtension: nil)
                if musicURL == nil {
                    // Try Resources/Audio subdirectory if flattened with folder ref
                    musicURL = Bundle.main.url(forResource: musicFilename, withExtension: nil, subdirectory: "Resources/Audio")
                }
                if musicURL == nil {
                    // Try splitting name/ext
                    let name = (musicFilename as NSString).deletingPathExtension
                    let ext = (musicFilename as NSString).pathExtension
                    musicURL = Bundle.main.url(forResource: name, withExtension: ext)
                    
                    if musicURL == nil {
                        musicURL = Bundle.main.url(forResource: name, withExtension: ext, subdirectory: "Resources/Audio")
                    }
                }
                effectiveMusicURL = musicURL
                if effectiveMusicURL == nil {
                    print("Music file not found: \(musicFilename)")
                }
            }
            
            if let url = effectiveMusicURL {
                let musicAsset = AVURLAsset(url: url)
                    if let musicTrackSource = try? await musicAsset.loadTracks(withMediaType: .audio).first {
                        let musicDuration = try await musicAsset.load(.duration)
                        let targetDuration = insertTime
                        
                        if let bgMusicTrack = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) {
                            var currentMusicTime = CMTime.zero
                            while currentMusicTime < targetDuration {
                                let remainingTime = targetDuration - currentMusicTime
                                let duration = min(remainingTime, musicDuration)
                                let timeRange = CMTimeRange(start: .zero, duration: duration)
                                
                                try bgMusicTrack.insertTimeRange(timeRange, of: musicTrackSource, at: currentMusicTime)
                                currentMusicTime = currentMusicTime + duration
                            }
                            
                            let mix = AVMutableAudioMix()
                            let musicInputParams = AVMutableAudioMixInputParameters(track: bgMusicTrack)
                            musicInputParams.setVolume(0.3, at: .zero)
                            
                            let originalAudioInputParams = AVMutableAudioMixInputParameters(track: audioTrack)
                            originalAudioInputParams.setVolume(1.0, at: .zero)
                            
                            mix.inputParameters = [musicInputParams, originalAudioInputParams]
                            audioMix = mix
                        }
                    }
                } else {
                    print("Music file not found: \(musicFilename)")
                }
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
            exportSession.audioMix = audioMix

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

    private func premiumRestrictionMessage(
        theme: ExportTheme,
        music: MusicTrack,
        isProUser: Bool
    ) -> String? {
        guard !isProUser else { return nil }

        let themeLocked = theme.requiresPro
        let musicLocked = music.requiresPro

        switch (themeLocked, musicLocked) {
        case (false, false):
            return nil
        case (true, true):
            return "Pro required for selected theme and music"
        case (true, false):
            return "Pro required for \(theme.rawValue) theme"
        case (false, true):
            return "Pro required for \(music.rawValue) music"
        }
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
