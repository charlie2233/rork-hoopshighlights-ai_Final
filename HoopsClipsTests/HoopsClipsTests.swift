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

}
