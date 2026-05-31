import Foundation

nonisolated struct AnalysisSettings: Codable, Sendable {
    var audioWeight: Double = 0.15
    var motionWeight: Double = 0.35
    var poseWeight: Double = 0.35
    var sceneWeight: Double = 0.15
    var confidenceThreshold: Double = 0.4
    var minClipDuration: Double = 2.0
    var maxClipDuration: Double = 15.0
    var targetHighlightDuration: Double = 45.0
    var highlightTeamSelection: HighlightTeamSelection = .allTeams
    var customHighlightTeamNames: [String: String] = [:]
    var opponentTeamName: String?
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
        case highlightTeamSelection
        case customHighlightTeamNames
        case opponentTeamName
        case clipPadding
        case framesSampledPerSecond
        case preferKeepUncertain
        case mlWindowSize
        case minMLPredictionCount
        case scoreSmoothingWindow
        case enableSmartCropping
    }

    nonisolated init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        audioWeight = try container.decodeIfPresent(Double.self, forKey: .audioWeight) ?? 0.15
        motionWeight = try container.decodeIfPresent(Double.self, forKey: .motionWeight) ?? 0.35
        poseWeight = try container.decodeIfPresent(Double.self, forKey: .poseWeight) ?? 0.35
        sceneWeight = try container.decodeIfPresent(Double.self, forKey: .sceneWeight) ?? 0.15
        confidenceThreshold = try container.decodeIfPresent(Double.self, forKey: .confidenceThreshold) ?? 0.4
        minClipDuration = try container.decodeIfPresent(Double.self, forKey: .minClipDuration) ?? 2.0
        maxClipDuration = try container.decodeIfPresent(Double.self, forKey: .maxClipDuration) ?? 15.0
        targetHighlightDuration = try container.decodeIfPresent(Double.self, forKey: .targetHighlightDuration) ?? 45.0
        highlightTeamSelection = try container.decodeIfPresent(HighlightTeamSelection.self, forKey: .highlightTeamSelection) ?? .allTeams
        customHighlightTeamNames = try container.decodeIfPresent([String: String].self, forKey: .customHighlightTeamNames) ?? [:]
        opponentTeamName = try container.decodeIfPresent(String.self, forKey: .opponentTeamName)
        clipPadding = try container.decodeIfPresent(Double.self, forKey: .clipPadding) ?? 1.5
        framesSampledPerSecond = try container.decodeIfPresent(Double.self, forKey: .framesSampledPerSecond) ?? 3.0
        preferKeepUncertain = try container.decodeIfPresent(Bool.self, forKey: .preferKeepUncertain) ?? true
        mlWindowSize = try container.decodeIfPresent(Int.self, forKey: .mlWindowSize) ?? 60
        minMLPredictionCount = try container.decodeIfPresent(Int.self, forKey: .minMLPredictionCount) ?? 3
        scoreSmoothingWindow = try container.decodeIfPresent(Int.self, forKey: .scoreSmoothingWindow) ?? 3
        enableSmartCropping = try container.decodeIfPresent(Bool.self, forKey: .enableSmartCropping) ?? true
    }

    nonisolated func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(audioWeight, forKey: .audioWeight)
        try container.encode(motionWeight, forKey: .motionWeight)
        try container.encode(poseWeight, forKey: .poseWeight)
        try container.encode(sceneWeight, forKey: .sceneWeight)
        try container.encode(confidenceThreshold, forKey: .confidenceThreshold)
        try container.encode(minClipDuration, forKey: .minClipDuration)
        try container.encode(maxClipDuration, forKey: .maxClipDuration)
        try container.encode(targetHighlightDuration, forKey: .targetHighlightDuration)
        try container.encode(highlightTeamSelection, forKey: .highlightTeamSelection)
        try container.encode(customHighlightTeamNames, forKey: .customHighlightTeamNames)
        try container.encodeIfPresent(opponentTeamName, forKey: .opponentTeamName)
        try container.encode(clipPadding, forKey: .clipPadding)
        try container.encode(framesSampledPerSecond, forKey: .framesSampledPerSecond)
        try container.encode(preferKeepUncertain, forKey: .preferKeepUncertain)
        try container.encode(mlWindowSize, forKey: .mlWindowSize)
        try container.encode(minMLPredictionCount, forKey: .minMLPredictionCount)
        try container.encode(scoreSmoothingWindow, forKey: .scoreSmoothingWindow)
        try container.encode(enableSmartCropping, forKey: .enableSmartCropping)
    }
}
