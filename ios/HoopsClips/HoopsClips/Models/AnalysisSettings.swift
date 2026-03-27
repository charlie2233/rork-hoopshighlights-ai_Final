import Foundation

struct AnalysisSettings: Codable, Sendable {
    var audioWeight: Double = 0.15
    var motionWeight: Double = 0.35
    var poseWeight: Double = 0.35
    var sceneWeight: Double = 0.15
    var confidenceThreshold: Double = 0.4
    var minClipDuration: Double = 2.0
    var maxClipDuration: Double = 15.0
    var targetHighlightDuration: Double = 45.0
    var clipPadding: Double = 1.5
    var framesSampledPerSecond: Double = 3.0
    var preferKeepUncertain: Bool = true
    
    // ML Configuration
    var mlWindowSize: Int = 60
    var minMLPredictionCount: Int = 3
    var scoreSmoothingWindow: Int = 3
    
    // Preprocessing Configuration
    var enableSmartCropping: Bool = true
}

extension AnalysisSettings {
    private enum CodingKeys: String, CodingKey {
        case audioWeight
        case motionWeight
        case poseWeight
        case sceneWeight
        case confidenceThreshold
        case minClipDuration
        case maxClipDuration
        case targetHighlightDuration
        case clipPadding
        case framesSampledPerSecond
        case preferKeepUncertain
        case mlWindowSize
        case minMLPredictionCount
        case scoreSmoothingWindow
        case enableSmartCropping
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        audioWeight = try container.decodeIfPresent(Double.self, forKey: .audioWeight) ?? 0.15
        motionWeight = try container.decodeIfPresent(Double.self, forKey: .motionWeight) ?? 0.35
        poseWeight = try container.decodeIfPresent(Double.self, forKey: .poseWeight) ?? 0.35
        sceneWeight = try container.decodeIfPresent(Double.self, forKey: .sceneWeight) ?? 0.15
        confidenceThreshold = try container.decodeIfPresent(Double.self, forKey: .confidenceThreshold) ?? 0.4
        minClipDuration = try container.decodeIfPresent(Double.self, forKey: .minClipDuration) ?? 2.0
        maxClipDuration = try container.decodeIfPresent(Double.self, forKey: .maxClipDuration) ?? 15.0
        targetHighlightDuration = try container.decodeIfPresent(Double.self, forKey: .targetHighlightDuration) ?? 45.0
        clipPadding = try container.decodeIfPresent(Double.self, forKey: .clipPadding) ?? 1.5
        framesSampledPerSecond = try container.decodeIfPresent(Double.self, forKey: .framesSampledPerSecond) ?? 3.0
        preferKeepUncertain = try container.decodeIfPresent(Bool.self, forKey: .preferKeepUncertain) ?? true
        mlWindowSize = try container.decodeIfPresent(Int.self, forKey: .mlWindowSize) ?? 60
        minMLPredictionCount = try container.decodeIfPresent(Int.self, forKey: .minMLPredictionCount) ?? 3
        scoreSmoothingWindow = try container.decodeIfPresent(Int.self, forKey: .scoreSmoothingWindow) ?? 3
        enableSmartCropping = try container.decodeIfPresent(Bool.self, forKey: .enableSmartCropping) ?? true
    }
}
