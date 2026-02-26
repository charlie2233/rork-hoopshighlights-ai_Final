import Foundation
import Vision
import CoreML

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
        
        // Output size: 60 frames * 18 joints * 2 coordinates (x, y) = 2160
        guard let multiArray = try? MLMultiArray(shape: [2160], dataType: .double) else {
            return nil
        }
        
        // Initialize with zeros
        for i in 0..<multiArray.count {
            multiArray[i] = 0
        }
        
        // Fill data
        for (t, pose) in relevantPoses.enumerated() {
            // Calculate offset based on where we are in the window
            // If we have fewer than 60 frames, we fill the end of the buffer?
            // User says "Once the buffer is full (count == 60)", so we assume 60 frames usually.
            // But if we do support fewer, we should probably align to the end (most recent).
            // However, the Python script pads with zeros at the END if fewer frames.
            // But for sliding window, we usually have full 60.
            // Let's assume we fill from the beginning of the supplied frames.
            // If poses has 60 frames, t goes 0..59.
            
            for (j, jointName) in jointNames.enumerated() {
                let flatIndex = (t * jointNames.count * 2) + (j * 2)
                
                if let point = pose.points[jointName], point.confidence > 0.0 {
                    // Vision coordinates are normalized (0,0) bottom-left to (1,1) top-right.
                    let x = point.x
                    let y = point.y
                    
                    multiArray[flatIndex] = NSNumber(value: x)
                    multiArray[flatIndex + 1] = NSNumber(value: y)
                }
            }
        }
        
        return multiArray
    }
    
    // Helper to convert from Vision observations
    static func convert(_ observations: [VNHumanBodyPoseObservation]) -> [PoseFrame] {
        return observations.map { obs in
            var points: [VNHumanBodyPoseObservation.JointName: PosePoint] = [:]
            
            for joint in jointNames {
                if let recognized = try? obs.recognizedPoint(joint), recognized.confidence > 0 {
                    points[joint] = PosePoint(
                        x: recognized.location.x,
                        y: recognized.location.y,
                        confidence: Double(recognized.confidence)
                    )
                }
            }
            return PoseFrame(points: points)
        }
    }
}
