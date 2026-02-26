import Foundation

struct AnalysisSettings: Codable, Sendable {
    var audioWeight: Double = 0.15
    var motionWeight: Double = 0.35
    var poseWeight: Double = 0.35
    var sceneWeight: Double = 0.15
    var confidenceThreshold: Double = 0.4
    var minClipDuration: Double = 2.0
    var maxClipDuration: Double = 15.0
    var clipPadding: Double = 1.5
    var framesSampledPerSecond: Double = 3.0
    var preferKeepUncertain: Bool = true
    
    // ML Configuration
    var mlWindowSize: Int = 60
    var minMLPredictionCount: Int = 3
    var scoreSmoothingWindow: Int = 3
}
