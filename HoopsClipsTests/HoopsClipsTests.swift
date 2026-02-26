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
                poseScore: 0.6,
                motionScore: 0.6, // avg will be 0.6
                sceneScore: 0.5,
                observation: nil
            )
            longFrames.append(frame)
        }
        
        let classifiedLong = await service.classifyActions(clips: [longClip], frameScores: longFrames)
        let resultLong = classifiedLong.first!
        
        print("Classified Action Long: \(resultLong.action.rawValue)")
        #expect(resultLong.action == .madeShot)
    }

}
