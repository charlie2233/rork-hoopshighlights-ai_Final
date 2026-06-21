import Foundation
import AVFoundation
import Photos

// The export progress timer fires on the main run loop; keep the AVFoundation read main-actor confined.
private struct MainActorProgressSource<Value>: @unchecked Sendable {
    let value: Value
}

@Observable
@MainActor
final class VideoExportService {
    var isExporting = false
    var exportProgress: Double = 0.0
    var statusMessage = ""
    var exportedURL: URL?

    func markUnavailable(_ message: String) {
        isExporting = false
        exportProgress = 0.0
        exportedURL = nil
        statusMessage = message
    }

    @discardableResult
    func blockLocalExportIfCloudRequired() -> Bool {
        blockLocalExportIfCloudRequired(requiresCloudRendering: AppConstants.requiresCloudVideoPipeline)
    }

    @discardableResult
    func blockLocalExportIfCloudRequired(requiresCloudRendering: Bool) -> Bool {
        guard requiresCloudRendering else { return false }
        markUnavailable(AppConstants.localVideoExportUnavailableMessage)
        return true
    }

    func exportHighlights(
        sourceURL: URL,
        clips: [Clip],
        theme: ExportTheme,
        music: MusicTrack,
        customMusicURL: URL? = nil,
        isProUser: Bool,
        quality: ExportQuality,
        format: ExportFileFormat,
        postProcessing: ExportPostProcessingOptions
    ) async {
        guard !blockLocalExportIfCloudRequired() else { return }

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

            let timelineSegments = makeExportTimelineSegments(
                from: keptClips,
                assetDuration: sourceDurationSeconds,
                options: postProcessing
            )
            guard !timelineSegments.isEmpty else {
                statusMessage = "No clips to export"
                isExporting = false
                return
            }

            let clipsByID = Dictionary(uniqueKeysWithValues: keptClips.map { ($0.id, $0) })
            var insertTime = CMTime.zero
            for (index, segment) in timelineSegments.enumerated() {
                let range = segment.sourceTimeRange()
                guard let clip = clipsByID[segment.clipID] else { continue }

                let useSegmentedSlowMotion = shouldApplySlowMotion(to: clip, options: postProcessing)
                    && canApplySegmentedSlowMotion(sourceDuration: segment.sourceDuration)

                if useSegmentedSlowMotion {
                    // Center of the clip is the v1 action peak.
                    let totalDuration = range.duration
                    let slowMoDuration = CMTime(seconds: exportSlowMotionSourceWindowDuration, preferredTimescale: 600)
                    let midPoint = range.start + CMTime(seconds: totalDuration.seconds / 2.0, preferredTimescale: 600)
                    let slowStart = midPoint - CMTime(seconds: slowMoDuration.seconds / 2.0, preferredTimescale: 600)
                    let slowEnd = midPoint + CMTime(seconds: slowMoDuration.seconds / 2.0, preferredTimescale: 600)

                    let preRange = CMTimeRange(start: range.start, end: slowStart)
                    try videoTrack.insertTimeRange(preRange, of: sourceVideo, at: insertTime)
                    if let sourceAudio = sourceAudioTracks.first {
                        try audioTrack.insertTimeRange(preRange, of: sourceAudio, at: insertTime)
                    }
                    insertTime = insertTime + preRange.duration

                    let slowRange = CMTimeRange(start: slowStart, end: slowEnd)
                    let slowDuration = CMTime(
                        seconds: slowRange.duration.seconds / exportSlowMotionPlaybackRate,
                        preferredTimescale: 600
                    )
                    try videoTrack.insertTimeRange(slowRange, of: sourceVideo, at: insertTime)
                    videoTrack.scaleTimeRange(CMTimeRange(start: insertTime, duration: slowRange.duration), toDuration: slowDuration)

                    if let sourceAudio = sourceAudioTracks.first {
                        try audioTrack.insertTimeRange(slowRange, of: sourceAudio, at: insertTime)
                        audioTrack.scaleTimeRange(CMTimeRange(start: insertTime, duration: slowRange.duration), toDuration: slowDuration)
                    }
                    insertTime = insertTime + slowDuration

                    let postRange = CMTimeRange(start: slowEnd, end: range.end)
                    try videoTrack.insertTimeRange(postRange, of: sourceVideo, at: insertTime)
                    if let sourceAudio = sourceAudioTracks.first {
                        try audioTrack.insertTimeRange(postRange, of: sourceAudio, at: insertTime)
                    }
                    insertTime = insertTime + postRange.duration
                } else {
                    try videoTrack.insertTimeRange(range, of: sourceVideo, at: insertTime)
                    if let sourceAudio = sourceAudioTracks.first {
                        try audioTrack.insertTimeRange(range, of: sourceAudio, at: insertTime)
                    }
                    insertTime = insertTime + range.duration
                }

                exportProgress = Double(index + 1) / Double(timelineSegments.count) * 0.5
                statusMessage = "Adding clip \(index + 1) of \(timelineSegments.count)..."
            }

            let brandedOutroStartTime: Double?
            let outroDurationSeconds = brandedOutroDuration(isProUser: isProUser)
            if outroDurationSeconds > 0 {
                statusMessage = "Adding HoopClips outro..."
                brandedOutroStartTime = CMTimeGetSeconds(insertTime)
                let outroDuration = CMTime(seconds: outroDurationSeconds, preferredTimescale: 600)
                let outroRange = CMTimeRange(start: insertTime, duration: outroDuration)
                videoTrack.insertEmptyTimeRange(outroRange)
                audioTrack.insertEmptyTimeRange(outroRange)
                insertTime = insertTime + outroDuration
            } else {
                brandedOutroStartTime = nil
            }

            var audioMix: AVMutableAudioMix?
            
            var effectiveMusicURL: URL?
            if music == .custom, let customURL = customMusicURL {
                effectiveMusicURL = customURL
                statusMessage = "Adding custom audio..."
            } else if let musicFilename = music.filename {
                statusMessage = "Adding background music..."
                
                // Find music file
                var musicURL = Bundle.main.url(forResource: musicFilename, withExtension: nil)
                if musicURL == nil {
                    musicURL = Bundle.main.url(forResource: musicFilename, withExtension: nil, subdirectory: "Resources/Audio")
                }
                if musicURL == nil {
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

            let outputURL = URL.temporaryDirectory.appending(path: "HoopsHighlight_\(UUID().uuidString).\(fileExtension)")
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
                    quality: quality,
                    brandedOutroStartTime: brandedOutroStartTime,
                    postProcessing: postProcessing
                )
                exportSession.videoComposition = themedComposition
            } catch {
                statusMessage = "Theme rendering unavailable, exporting without effects"
            }

            statusMessage = "Rendering \(theme.rawValue) export..."
            let progressSource = MainActorProgressSource(value: exportSession)

            let timer = Timer.scheduledTimer(withTimeInterval: 0.2, repeats: true) { _ in
                MainActor.assumeIsolated {
                    self.exportProgress = 0.5 + Double(progressSource.value.progress) * 0.5
                }
            }

            await exportSession.export()
            timer.invalidate()

            if exportSession.status == .completed {
                isExporting = false
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

    private func makeExportTimelineSegments(
        from clips: [Clip],
        assetDuration: Double,
        options: ExportPostProcessingOptions
    ) -> [ExportTimelineSegment] {
        let baseSegments = buildTimelineSegments(from: clips, assetDuration: assetDuration)
        let clipsByID = Dictionary(uniqueKeysWithValues: clips.map { ($0.id, $0) })
        var outputCursor = 0.0

        return baseSegments.map { segment in
            let adjustedDuration: Double
            if let clip = clipsByID[segment.clipID] {
                adjustedDuration = exportedClipOutputDuration(
                    sourceDuration: segment.sourceDuration,
                    shouldSlowMotion: shouldApplySlowMotion(to: clip, options: options)
                )
            } else {
                adjustedDuration = segment.sourceDuration
            }

            let adjustedSegment = ExportTimelineSegment(
                outputStartTime: outputCursor,
                outputEndTime: outputCursor + adjustedDuration,
                sourceStartTime: segment.sourceStartTime,
                sourceEndTime: segment.sourceEndTime,
                clipID: segment.clipID,
                clipLabel: segment.clipLabel,
                clipConfidence: segment.clipConfidence,
                clipAction: segment.clipAction
            )
            outputCursor += adjustedDuration
            return adjustedSegment
        }
    }

    private func shouldApplySlowMotion(to clip: Clip, options: ExportPostProcessingOptions) -> Bool {
        shouldApplyExportSlowMotion(to: clip, options: options)
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

internal let exportSlowMotionSourceWindowDuration = 1.5
internal let exportSlowMotionPlaybackRate = 0.5
internal let exportSegmentedSlowMotionEnabled = false
// Cloud Edit owns policy branding/outros. The local AVFoundation fallback should
// never append an empty slate because that reads as an unwanted black-screen
// effect after a highlight.
internal let nonProExportOutroDuration = 0.0

internal func brandedOutroDuration(isProUser: Bool) -> Double {
    isProUser ? 0 : nonProExportOutroDuration
}

internal func shouldApplyExportSlowMotion(to clip: Clip, options: ExportPostProcessingOptions) -> Bool {
    if clip.isSlowMotionEnabled {
        return true
    }

    guard options.enableSmartSlowMotion else {
        return false
    }

    guard clip.duration >= 3.5, clip.confidence >= 0.72 else {
        return false
    }

    switch clip.action {
    case .dunk, .posterize, .block, .alleyOop, .buzzerBeater:
        return true
    default:
        return false
    }
}

internal func canApplySegmentedSlowMotion(sourceDuration: Double) -> Bool {
    exportSegmentedSlowMotionEnabled && sourceDuration > exportSlowMotionSourceWindowDuration
}

internal func exportedClipOutputDuration(sourceDuration: Double, shouldSlowMotion: Bool) -> Double {
    guard shouldSlowMotion, canApplySegmentedSlowMotion(sourceDuration: sourceDuration) else {
        return sourceDuration
    }

    return sourceDuration + (exportSlowMotionSourceWindowDuration / exportSlowMotionPlaybackRate) - exportSlowMotionSourceWindowDuration
}
