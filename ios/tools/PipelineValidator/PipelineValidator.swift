import Foundation
import CoreML
import Vision

// MARK: - Types from PoseExtractor
struct OutputData: Codable {
    let label: String
    let poses: [[Double]] // Flat array of [x, y, confidence] for 18 joints
}

// MARK: - Types from VideoAnalysisService (Stubbed/Copied)

struct PosePoint {
    let x: Double
    let y: Double
    let confidence: Double
}

struct PoseFrame {
    // Map joint name to point
    let points: [VNHumanBodyPoseObservation.JointName: PosePoint]
}

final class PoseInputBuilder {
    static let windowSize = 60
    
    // Order matches the training script
    static let jointNames: [VNHumanBodyPoseObservation.JointName] = [
        .nose, .leftEye, .rightEye, .leftEar, .rightEar,
        .leftShoulder, .rightShoulder, .leftElbow, .rightElbow, .leftWrist, .rightWrist,
        .leftHip, .rightHip, .leftKnee, .rightKnee, .leftAnkle, .rightAnkle, .neck
    ]
    
    static func buildInput(from poses: [PoseFrame]) -> MLMultiArray? {
        // Target window size
        let relevantPoses = Array(poses.suffix(windowSize))
        
        guard let multiArray = try? MLMultiArray(shape: [1, 3, 18, 60], dataType: .double) else {
            return nil
        }
        
        // Initialize with zeros
        for i in 0..<multiArray.count {
            multiArray[i] = 0
        }
        
        // Align to the end of the window if we have fewer than 60 frames
        for (t, pose) in relevantPoses.enumerated() {
            let timeIndex = 60 - relevantPoses.count + t
            
            for (j, jointName) in jointNames.enumerated() {
                if let point = pose.points[jointName], point.confidence > 0.1 {
                    let x = point.x
                    let y = point.y
                    let c = point.confidence
                    
                    multiArray[[0, 0, j, timeIndex] as [NSNumber]] = NSNumber(value: x)
                    multiArray[[0, 1, j, timeIndex] as [NSNumber]] = NSNumber(value: y)
                    multiArray[[0, 2, j, timeIndex] as [NSNumber]] = NSNumber(value: c)
                }
            }
        }
        
        return multiArray
    }
}

// MARK: - Heuristic Logic Stub
enum HighlightAction: String, CaseIterable {
    case dunk, layup, threePointer, steal, block, fastBreak, posterize, madeShot, unknown
}

struct Clip {
    var startTime: Double
    var endTime: Double
    var confidence: Double
    var isKept: Bool
    var audioScore: Double
    var visualScore: Double
    var motionScore: Double
    var combinedScore: Double
    var action: HighlightAction = .unknown
    var label: String = ""
    
    var duration: Double { endTime - startTime }
}

struct FrameScore {
    let timestamp: Double
    let poseScore: Double
    let motionScore: Double
    // observation is not needed for this stub as we pass poses separately or pre-calc
}

func classifyActions(clip: Clip, maxPose: Double, maxMotion: Double, avgMotion: Double) -> Clip {
    var classified = clip
    
    // 2. Fallback Heuristics
    if maxPose > 0.7 && maxMotion > 0.6 {
        if clip.audioScore > 0.7 {
            classified.action = .dunk
        } else {
            classified.action = .posterize
        }
    } else if maxPose > 0.5 && avgMotion > 0.5 {
        if clip.duration < 4.0 {
            classified.action = .layup
        } else {
            classified.action = .madeShot
        }
    } else if maxMotion > 0.7 {
        classified.action = .fastBreak
    } else if maxMotion > 0.5 && maxPose > 0.3 {
        if clip.audioScore > 0.5 {
            classified.action = .threePointer
        } else {
            classified.action = .steal
        }
    } else if maxPose > 0.4 {
        classified.action = .block
    } else if clip.audioScore > 0.6 {
        classified.action = .madeShot
    } else {
        classified.action = .unknown
    }

    classified.label = classified.action.rawValue
    return classified
}

// MARK: - Main Execution

func main() {
    print("Starting Pipeline Validator...")
    
    // 1. Find JSON files
    let fileManager = FileManager.default
    // Hardcoded path to where we know we outputted things.
    // Adjust this relative path if you run from different CWD.
    let rootPath = "HoopsClips/Resources/TestVideos/pose_output" 
    
    guard fileManager.fileExists(atPath: rootPath) else {
        print("Error: Path \(rootPath) not found.")
        return
    }
    
    let subdirs = ["shoot_3pt", "dunk", "other"]
    
    for subdir in subdirs {
        let dirPath = "\(rootPath)/\(subdir)"
        guard let files = try? fileManager.contentsOfDirectory(atPath: dirPath) else { continue }
        
        for file in files where file.hasSuffix(".json") {
            let fullPath = "\(dirPath)/\(file)"
            print("\nProcessing \(file)...")
            
            do {
                let data = try Data(contentsOf: URL(fileURLWithPath: fullPath))
                let outputData = try JSONDecoder().decode(OutputData.self, from: data)
                
                print("  Label: \(outputData.label)")
                print("  Frames: \(outputData.poses.count)")
                
                // Convert raw doubles to PoseFrames
                let poseFrames = outputData.poses.map { frameData -> PoseFrame in
                    var points: [VNHumanBodyPoseObservation.JointName: PosePoint] = [:]
                    
                    // order matches PoseExtractor: 
                    // .nose, .leftEye, .rightEye, .leftEar, .rightEar,
                    // .leftShoulder, .rightShoulder, .leftElbow, .rightElbow, .leftWrist, .rightWrist,
                    // .leftHip, .rightHip, .leftKnee, .rightKnee, .leftAnkle, .rightAnkle, .neck
                    
                    for (index, jointName) in PoseInputBuilder.jointNames.enumerated() {
                        let base = index * 3
                        if base + 2 < frameData.count {
                            let x = frameData[base]
                            let y = frameData[base+1]
                            let c = frameData[base+2]
                            
                            if c > 0 {
                                points[jointName] = PosePoint(x: x, y: y, confidence: c)
                            }
                        }
                    }
                    return PoseFrame(points: points)
                }
                
                // 2. Validate ML Input Generation
                if let input = PoseInputBuilder.buildInput(from: poseFrames) {
                    print("  [PASS] Generated MLMultiArray with shape \(input.shape)")
                    
                    // Check for non-zero values
                    var nonZeroCount = 0
                    let count = input.count
                    for i in 0..<count {
                        if input[i].doubleValue != 0 {
                            nonZeroCount += 1
                        }
                    }
                    print("  [INFO] Non-zero elements in input: \(nonZeroCount)")
                    
                    if nonZeroCount > 0 {
                         print("  [PASS] Input vector contains data")
                    } else if poseFrames.count > 0 && poseFrames.contains(where: { !$0.points.isEmpty }) {
                         print("  [WARN] Input vector is empty despite having frames? (Maybe confidence threshold filtered them out)")
                    }
                    
                } else {
                    print("  [FAIL] Failed to generate MLMultiArray")
                }
                
                // 3. Validate Heuristic Fallback
                // Create a fake clip based on the file type
                var mockClip = Clip(
                    startTime: 0,
                    endTime: Double(outputData.poses.count) / 30.0,
                    confidence: 0.8,
                    isKept: true,
                    audioScore: 0.5,
                    visualScore: 0.5,
                    motionScore: 0.5,
                    combinedScore: 0.8
                )
                
                // Adjust scores based on file name to trigger specific heuristics
                if file.contains("shoot") {
                    // Simulate stats for a shot
                    let classified = classifyActions(clip: mockClip, maxPose: 0.4, maxMotion: 0.6, avgMotion: 0.55)
                    print("  [TEST] Heuristic Classification for Shot stats: \(classified.action) (Expected: madeShot/threePointer/unknown)")
                } else if file.contains("dunk") || file.contains("block") {
                    // Simulate stats for a dunk/block (high pose, high motion)
                    let classified = classifyActions(clip: mockClip, maxPose: 0.8, maxMotion: 0.7, avgMotion: 0.6)
                    print("  [TEST] Heuristic Classification for Dunk/Block stats: \(classified.action) (Expected: posterize/dunk)")
                } else {
                    let classified = classifyActions(clip: mockClip, maxPose: 0.1, maxMotion: 0.2, avgMotion: 0.2)
                    print("  [TEST] Heuristic Classification for Low Activity: \(classified.action) (Expected: unknown)")
                }
                
            } catch {
                print("  [ERROR] Failed to process: \(error)")
            }
        }
    }
}

main()
