//
//  HoopsClipsTests.swift
//  HoopsClipsTests
//
//  Created by Rork on February 25, 2026.
//

import Testing
import Foundation
import CoreML
import Vision
@testable import HoopsClips

struct HoopsClipsTests {

    // Test removed because it relies on local JSON files that were cleaned up
    // @Test func testModelPipelineWithLayupJson() async throws { ... }

    @Test func testHeuristicFallback() async {
        // Prepare a Clip that should trigger "Posterize" or "Dunk" via heuristics
        // Heuristic: maxPose > 0.7 && maxMotion > 0.6
        // If audioScore > 0.7 -> Dunk, else Posterize
        
        let startTime = 0.0
        let endTime = 3.0
        let clip = Clip(
            startTime: startTime,
            endTime: endTime,
            action: .unknown,
            confidence: 0.8,
            isKept: true,
            label: "Test Clip",
            audioScore: 0.8, // Should trigger Dunk
            visualScore: 0.8,
            motionScore: 0.8,
            combinedScore: 0.8
        )
        
        // Prepare FrameScores
        // We need frames within start/end time
        var frames: [FrameScore] = []
        for i in 0..<30 {
            let time = Double(i) * 0.1
            // High pose and motion scores
            let frame = FrameScore(
                timestamp: time,
                poseScore: 0.8,
                motionScore: 0.7,
                sceneScore: 0.5,
                poseCoverage: 0.8,
                brightness: 0.5,
                audioBurst: 0.8,
                observation: nil // No observation, so predictAction will return nil/fail
            )
            frames.append(frame)
        }
        
        let service = await VideoAnalysisService()
        
        // Call classifyActions (now internal)
        let classifiedClips = await service.classifyActions(clips: [clip], frameScores: frames)
        
        #expect(classifiedClips.count == 1)
        let result = classifiedClips.first!
        
        print("Classified Action: \(result.action.rawValue)")
        
        // Check if fallback worked
        // Should be .dunk because audioScore (0.8) > 0.7 and pose/motion are high
        #expect(result.action == .dunk)
        #expect(result.label == "Dunk")
        
        // Test another case: Made Shot
        // Heuristic: maxPose > 0.5 && avgMotion > 0.5 && duration > 4.0 -> Made Shot
        
        let longClip = Clip(
            startTime: 0.0,
            endTime: 5.0,
            action: .unknown,
            confidence: 0.6,
            isKept: true,
            label: "Test Long Clip",
            audioScore: 0.2,
            visualScore: 0.6,
            motionScore: 0.6,
            combinedScore: 0.6
        )
        
        var longFrames: [FrameScore] = []
        for i in 0..<50 {
            let time = Double(i) * 0.1
            let frame = FrameScore(
                timestamp: time,
                poseScore: 0.5,
                motionScore: 0.45,
                sceneScore: 0.5,
                poseCoverage: 0.5,
                brightness: 0.5,
                audioBurst: 0.2,
                observation: nil
            )
            longFrames.append(frame)
        }
        
        let classifiedLong = await service.classifyActions(clips: [longClip], frameScores: longFrames)
        let resultLong = classifiedLong.first!
        
        print("Classified Action Long: \(resultLong.action.rawValue)")
        #expect(resultLong.action == .madeShot)
    }

    @Test func testAdaptiveWeightsRebalance() {
        let base = AnalysisWeights(audio: 0.15, motion: 0.35, pose: 0.35, scene: 0.15)
        let tuned = AnalysisQualityTuning.adaptiveWeights(
            base: base,
            averagePoseCoverage: 0.20,
            averageBrightness: 0.20
        )

        let sum = tuned.audio + tuned.motion + tuned.pose + tuned.scene
        #expect(abs(sum - 1.0) < 0.0001)
        #expect(tuned.pose < base.pose)
        #expect(tuned.scene < base.scene)
        #expect(tuned.motion > base.motion)
    }

    @Test func testHysteresisSegmentationAvoidsFragmentation() {
        let points: [ScorePoint] = [
            .init(time: 0.0, score: 0.20),
            .init(time: 1.0, score: 0.62),
            .init(time: 2.0, score: 0.54),
            .init(time: 3.0, score: 0.51),
            .init(time: 4.0, score: 0.18),
            .init(time: 5.0, score: 0.64),
            .init(time: 6.0, score: 0.55),
            .init(time: 7.0, score: 0.12)
        ]

        let windows = AnalysisQualityTuning.segmentWithHysteresis(
            points: points,
            highThreshold: 0.60,
            lowThreshold: 0.50,
            minDuration: 1.5,
            maxDuration: 10.0,
            padding: 0.2,
            durationLimit: 8.0,
            mergeGap: 1.8
        )

        #expect(windows.count == 1)
        #expect(windows[0].peakScore >= 0.62)
    }

    @Test func testWeightedWinningLabelPrefersStrongSignal() {
        let votes: [PredictionVote] = [
            .init(label: "Dunk", confidence: 0.91, recencyWeight: 1.2),
            .init(label: "Dunk", confidence: 0.82, recencyWeight: 1.1),
            .init(label: "Layup", confidence: 0.40, recencyWeight: 1.0),
            .init(label: "Layup", confidence: 0.39, recencyWeight: 0.9),
            .init(label: "Layup", confidence: 0.36, recencyWeight: 0.8)
        ]

        let winner = AnalysisQualityTuning.weightedWinningLabel(
            votes: votes,
            minCount: 2,
            minMargin: 0.10
        )

        #expect(winner == "Dunk")
    }

    @Test func testSocialShortcutsCoverCommonShareTargets() {
        let shortcutIDs = Set(SocialAppSupport.defaultShortcuts.map(\.id))

        #expect(shortcutIDs.isSuperset(of: [
            "instagram",
            "tiktok",
            "youtube",
            "snapchat",
            "whatsapp",
            "facebook",
            "x"
        ]))
    }

    @Test func testEditorShortcutsCoverCommonEditingTargets() {
        let shortcutIDs = Set(EditorAppSupport.defaultShortcuts.map(\.id))

        #expect(shortcutIDs.isSuperset(of: [
            "adobe",
            "capcut",
            "imovie",
            "vn",
            "lumafusion",
            "splice",
            "final-cut-camera"
        ]))
    }

    @Test func testBundledMusicTracksHaveUniqueFilenames() {
        let filenames = MusicTrack.allCases.compactMap(\.filename)

        #expect(MusicTrack.allCases.count >= 12)
        #expect(filenames.count == Set(filenames).count)
        #expect(filenames.contains("arena_bounce.m4a"))
        #expect(filenames.contains("fast_break.m4a"))
        #expect(filenames.contains("halftime_funk.m4a"))
        #expect(filenames.contains("clutch_time.m4a"))
        #expect(filenames.contains("retro_arcade.m4a"))
        #expect(filenames.contains("victory_lap.m4a"))

        for filename in filenames {
            let splitName = (filename as NSString).deletingPathExtension
            let splitExtension = (filename as NSString).pathExtension
            let resourceURL = Bundle.main.url(forResource: filename, withExtension: nil)
                ?? Bundle.main.url(forResource: filename, withExtension: nil, subdirectory: "Resources/Audio")
                ?? Bundle.main.url(forResource: splitName, withExtension: splitExtension)
                ?? Bundle.main.url(forResource: splitName, withExtension: splitExtension, subdirectory: "Resources/Audio")

            #expect(resourceURL != nil, "Missing bundled audio resource: \(filename)")
        }
    }

    @Test func testCloudClipMappingPreservesCloudMetadata() {
        let cloudClip = CloudClip(
            startTime: 12.5,
            endTime: 17.0,
            confidence: 0.91,
            label: "Dunk",
            action: "Dunk",
            audioScore: 0.8,
            visualScore: 0.7,
            motionScore: 0.9,
            combinedScore: 0.86,
            detectionMethod: "Cloud",
            shouldAutoKeep: true,
            shouldEnableSlowMotion: true
        )

        let mapped = cloudClip.makeClip()

        #expect(mapped.action == .dunk)
        #expect(mapped.detectionMethod == .cloud)
        #expect(mapped.isKept)
        #expect(mapped.isSlowMotionEnabled)
        #expect(abs(mapped.duration - 4.5) < 0.001)
    }

    @Test func testCloudJobResponseDecodesNestedResults() throws {
        let payload = """
        {
          "jobId": "job-123",
          "status": "succeeded",
          "progress": 1.0,
          "stage": "Finalizing clips",
          "errorCode": null,
          "errorMessage": null,
          "analysisVersion": "v1",
          "results": {
            "clipCount": 1,
            "clips": [
              {
                "startTime": 1.2,
                "endTime": 4.6,
                "confidence": 0.88,
                "label": "Three Pointer",
                "action": "Three Pointer",
                "audioScore": 0.7,
                "visualScore": 0.6,
                "motionScore": 0.65,
                "combinedScore": 0.74,
                "detectionMethod": "cloud",
                "shouldAutoKeep": true,
                "shouldEnableSlowMotion": false
              }
            ],
            "diagnostics": {
              "processingMs": 18250,
              "backendModelVersion": "cloud-v1",
              "usedVideoIntelligence": false,
              "usedGeminiRelabeling": false,
              "candidateSegments": 4,
              "finalSegments": 1
            }
          }
        }
        """

        let decoder = JSONDecoder()
        let response = try decoder.decode(CloudAnalysisJobResponse.self, from: Data(payload.utf8))

        #expect(response.status == "succeeded")
        #expect(response.results?.clipCount == 1)
        #expect(response.results?.clips.first?.label == "Three Pointer")
        #expect(response.results?.diagnostics.backendModelVersion == "cloud-v1")
    }

    @Test func testAudioFallbackSplitsContinuousSignalIntoBoundedClips() async {
        let service = await VideoAnalysisService()
        let peaks = [Double](repeating: 1.0, count: 600)

        let clips = await service.buildAudioOnlyClips(audioPeaks: peaks, duration: 60.0)

        #expect(!clips.isEmpty)
        #expect(clips.count > 1)
        #expect(clips.allSatisfy { $0.duration <= AnalysisSettings().maxClipDuration + 0.001 })
        #expect(clips.allSatisfy { $0.endTime <= 60.0 && $0.startTime >= 0.0 })
    }

    @Test func testAudioFallbackCentersSingleBurst() async {
        let service = await VideoAnalysisService()
        var peaks = [Double](repeating: 0.0, count: 300)
        peaks[120] = 1.0
        peaks[121] = 0.8

        let clips = await service.buildAudioOnlyClips(audioPeaks: peaks, duration: 30.0)

        #expect(clips.count == 1)
        #expect(clips[0].duration <= AnalysisSettings().maxClipDuration + 0.001)
        #expect(abs(clips[0].startTime - 9.0) < 1.0)
        #expect(abs(clips[0].endTime - 15.0) < 1.0)
    }

    @Test func testAudioFallbackSeparatesSparseBursts() async {
        let service = await VideoAnalysisService()
        var peaks = [Double](repeating: 0.0, count: 600)
        peaks[50] = 1.0
        peaks[250] = 0.95
        peaks[450] = 0.9

        let clips = await service.buildAudioOnlyClips(audioPeaks: peaks, duration: 60.0)

        #expect(clips.count == 3)
        #expect(clips[0].startTime < clips[1].startTime)
        #expect(clips[1].startTime < clips[2].startTime)
        #expect(clips.allSatisfy { $0.duration <= AnalysisSettings().maxClipDuration + 0.001 })
    }

    @Test func testNormalizeOverlongHeuristicClipSplitsIt() async {
        let service = await VideoAnalysisService()
        let original = Clip(
            startTime: 0.0,
            endTime: 60.0,
            confidence: 0.78,
            isKept: true,
            label: "Action",
            audioScore: 0.8,
            visualScore: 0.2,
            motionScore: 0.3,
            combinedScore: 0.7,
            detectionMethod: .heuristic
        )

        let normalized = await service.normalizeDetectedClips([original], duration: 60.0)

        #expect(!normalized.isEmpty)
        #expect(normalized.count <= 3)
        #expect(normalized.allSatisfy { $0.duration <= AnalysisSettings().maxClipDuration + 0.001 })
        #expect(normalized.allSatisfy { $0.endTime - $0.startTime < 60.0 })
    }

    @Test func testNormalizeOverlongCloudClipSplitsIt() async {
        let service = await VideoAnalysisService()
        let original = Clip(
            startTime: 2.0,
            endTime: 58.0,
            action: .dunk,
            confidence: 0.91,
            isKept: true,
            label: "Dunk",
            audioScore: 0.8,
            visualScore: 0.7,
            motionScore: 0.9,
            combinedScore: 0.88,
            detectionMethod: .cloud
        )

        let normalized = await service.normalizeDetectedClips([original], duration: 60.0)

        #expect(!normalized.isEmpty)
        #expect(normalized.allSatisfy { $0.detectionMethod == .cloud })
        #expect(normalized.allSatisfy { $0.duration <= AnalysisSettings().maxClipDuration + 0.001 })
    }

    @Test func testNormalizeKeepsValidClipUntouched() async {
        let service = await VideoAnalysisService()
        let original = Clip(
            startTime: 10.0,
            endTime: 18.0,
            action: .madeShot,
            confidence: 0.72,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.4,
            visualScore: 0.5,
            motionScore: 0.5,
            combinedScore: 0.6,
            detectionMethod: .ml
        )

        let normalized = await service.normalizeDetectedClips([original], duration: 60.0)

        #expect(normalized.count == 1)
        #expect(abs(normalized[0].startTime - original.startTime) < 0.001)
        #expect(abs(normalized[0].endTime - original.endTime) < 0.001)
        #expect(normalized[0].detectionMethod == .ml)
    }

    @Test func testTargetHighlightDurationCapsDefaultAutoKeptClips() async {
        let service = await VideoAnalysisService()
        var settings = AnalysisSettings()
        settings.targetHighlightDuration = 18.0
        await service.updateSettings(settings)

        let result = CloudAnalysisResult(
            clipCount: 3,
            clips: [
                CloudClip(
                    startTime: 0.0,
                    endTime: 8.0,
                    confidence: 0.92,
                    label: "Dunk",
                    action: "Dunk",
                    audioScore: 0.9,
                    visualScore: 0.7,
                    motionScore: 0.8,
                    combinedScore: 0.9,
                    detectionMethod: "Cloud",
                    shouldAutoKeep: true,
                    shouldEnableSlowMotion: true
                ),
                CloudClip(
                    startTime: 12.0,
                    endTime: 20.0,
                    confidence: 0.88,
                    label: "Three Pointer",
                    action: "Three Pointer",
                    audioScore: 0.7,
                    visualScore: 0.6,
                    motionScore: 0.7,
                    combinedScore: 0.8,
                    detectionMethod: "Cloud",
                    shouldAutoKeep: true,
                    shouldEnableSlowMotion: false
                ),
                CloudClip(
                    startTime: 24.0,
                    endTime: 32.0,
                    confidence: 0.84,
                    label: "Made Shot",
                    action: "Made Shot",
                    audioScore: 0.6,
                    visualScore: 0.6,
                    motionScore: 0.6,
                    combinedScore: 0.7,
                    detectionMethod: "Cloud",
                    shouldAutoKeep: true,
                    shouldEnableSlowMotion: false
                )
            ],
            diagnostics: CloudDiagnostics(
                processingMs: 1200,
                backendModelVersion: "test",
                usedVideoIntelligence: false,
                usedGeminiRelabeling: false,
                candidateSegments: 3,
                finalSegments: 3
            )
        )

        await service.applyCloudAnalysis(result, duration: 60.0)
        let clips = await service.clips
        let kept = clips.filter(\.isKept)

        #expect(clips.count == 3)
        #expect(kept.count == 2)
        #expect(kept.reduce(0.0) { $0 + $1.duration } <= settings.targetHighlightDuration + 0.001)
    }

    @Test func testDefaultRedundantSuppressionPrefersHigherScoreWhenClipsOverlap() {
        let weaker = Clip(
            startTime: 10.8,
            endTime: 14.8,
            action: .dunk,
            confidence: 0.84,
            isKept: true,
            label: "Dunk B",
            combinedScore: 0.81
        )
        let stronger = Clip(
            startTime: 10.0,
            endTime: 14.0,
            action: .dunk,
            confidence: 0.92,
            isKept: true,
            label: "Dunk A",
            combinedScore: 0.93
        )

        let result = defaultRedundantClipSuppressedClips(from: [weaker, stronger])

        #expect(result.count == 2)
        #expect(!result[0].isKept)
        #expect(result[1].isKept)
        #expect(result[0].id == weaker.id)
        #expect(result[1].id == stronger.id)
    }

    @Test func testDefaultRedundantSuppressionClustersMatchingActionsNearInTime() {
        let stronger = Clip(
            startTime: 20.0,
            endTime: 21.2,
            action: .block,
            confidence: 0.88,
            isKept: true,
            label: "Block A",
            combinedScore: 0.86
        )
        let weaker = Clip(
            startTime: 21.6,
            endTime: 22.8,
            action: .block,
            confidence: 0.79,
            isKept: true,
            label: "Block B",
            combinedScore: 0.74
        )

        let result = defaultRedundantClipSuppressedClips(from: [stronger, weaker])

        #expect(result[0].isKept)
        #expect(!result[1].isKept)
    }

    @Test func testDefaultRedundantSuppressionKeepsDifferentActionsWhenOnlyTimeIsClose() {
        let dunk = Clip(
            startTime: 30.0,
            endTime: 31.2,
            action: .dunk,
            confidence: 0.9,
            isKept: true,
            label: "Dunk",
            combinedScore: 0.9
        )
        let block = Clip(
            startTime: 31.0,
            endTime: 32.2,
            action: .block,
            confidence: 0.87,
            isKept: true,
            label: "Block",
            combinedScore: 0.82
        )

        let result = defaultRedundantClipSuppressedClips(from: [dunk, block])

        #expect(result[0].isKept)
        #expect(result[1].isKept)
    }

    @Test func testSmartSlowMotionQualifiesHighConfidenceDunk() {
        let clip = Clip(
            startTime: 0.0,
            endTime: 4.2,
            action: .dunk,
            confidence: 0.82,
            isKept: true,
            label: "Dunk"
        )

        #expect(shouldApplyExportSlowMotion(to: clip, options: ExportPostProcessingOptions()))
    }

    @Test func testSmartSlowMotionRejectsLowConfidenceDunk() {
        let clip = Clip(
            startTime: 0.0,
            endTime: 4.2,
            action: .dunk,
            confidence: 0.71,
            isKept: true,
            label: "Dunk"
        )

        #expect(!shouldApplyExportSlowMotion(to: clip, options: ExportPostProcessingOptions()))
    }

    @Test func testManualSlowMotionStillAppliesWhenSmartSlowMotionIsDisabled() {
        let clip = Clip(
            startTime: 0.0,
            endTime: 2.5,
            action: .layup,
            confidence: 0.2,
            isKept: true,
            label: "Layup",
            isSlowMotionEnabled: true
        )
        let options = ExportPostProcessingOptions(enableAutoZoom: true, enableSmartSlowMotion: false)

        #expect(shouldApplyExportSlowMotion(to: clip, options: options))
    }

    @Test func testActionZoomScaleReturnsIdentityOutsideActiveWindow() {
        let scale = actionZoomScale(
            at: 0.0,
            segmentDuration: 4.0,
            action: .dunk,
            options: ExportPostProcessingOptions()
        )

        #expect(abs(scale - 1.0) < 0.0001)
    }

    @Test func testActionZoomScaleHitsMaxAtClipMidpoint() {
        let scale = actionZoomScale(
            at: 2.0,
            segmentDuration: 4.0,
            action: .dunk,
            options: ExportPostProcessingOptions()
        )

        #expect(abs(scale - 1.16) < 0.0001)
    }

    @Test func testActionZoomScaleReturnsToIdentityAtWindowBoundaries() {
        let startBoundaryScale = actionZoomScale(
            at: 1.4,
            segmentDuration: 4.0,
            action: .dunk,
            options: ExportPostProcessingOptions()
        )
        let endBoundaryScale = actionZoomScale(
            at: 2.6,
            segmentDuration: 4.0,
            action: .dunk,
            options: ExportPostProcessingOptions()
        )

        #expect(abs(startBoundaryScale - 1.0) < 0.0001)
        #expect(abs(endBoundaryScale - 1.0) < 0.0001)
    }

}
