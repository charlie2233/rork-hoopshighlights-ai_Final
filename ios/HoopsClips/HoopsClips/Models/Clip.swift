import Foundation

nonisolated struct Clip: Identifiable, Codable, Sendable {
    let id: UUID
    var startTime: Double
    var endTime: Double
    var eventCenter: Double?
    var action: HighlightAction
    var confidence: Double
    var isKept: Bool
    var label: String
    var audioScore: Double
    var visualScore: Double
    var motionScore: Double
    var combinedScore: Double
    var playbackSpeed: Double
    var isSlowMotionEnabled: Bool
    var detectionMethod: DetectionMethod
    var nativeShotSignals: NativeShotSignals?
    var teamAttribution: ClipTeamAttribution?

    var duration: Double { endTime - startTime }

    var formattedStartTime: String { Self.formatTime(startTime) }
    var formattedEndTime: String { Self.formatTime(endTime) }
    var formattedDuration: String { Self.formatTime(duration) }

    var confidenceLevel: ConfidenceLevel {
        if confidence >= 0.8 { return .high }
        if confidence >= 0.5 { return .medium }
        return .low
    }

    init(
        id: UUID = UUID(),
        startTime: Double,
        endTime: Double,
        eventCenter: Double? = nil,
        action: HighlightAction = .unknown,
        confidence: Double = 0.0,
        isKept: Bool = true,
        label: String = "",
        audioScore: Double = 0.0,
        visualScore: Double = 0.0,
        motionScore: Double = 0.0,
        combinedScore: Double = 0.0,
        playbackSpeed: Double = 1.0,
        isSlowMotionEnabled: Bool = false,
        detectionMethod: DetectionMethod = .heuristic,
        nativeShotSignals: NativeShotSignals? = nil,
        teamAttribution: ClipTeamAttribution? = nil
    ) {
        self.id = id
        self.startTime = startTime
        self.endTime = endTime
        self.eventCenter = eventCenter
        self.action = action
        self.confidence = confidence
        self.isKept = isKept
        self.label = label.isEmpty ? action.rawValue : label
        self.audioScore = audioScore
        self.visualScore = visualScore
        self.motionScore = motionScore
        self.combinedScore = combinedScore
        self.playbackSpeed = playbackSpeed
        self.isSlowMotionEnabled = isSlowMotionEnabled
        self.detectionMethod = detectionMethod
        self.nativeShotSignals = nativeShotSignals
        self.teamAttribution = teamAttribution
    }

    static func formatTime(_ time: Double) -> String {
        let minutes = Int(time) / 60
        let seconds = Int(time) % 60
        let fraction = Int((time.truncatingRemainder(dividingBy: 1)) * 10)
        return String(format: "%d:%02d.%d", minutes, seconds, fraction)
    }
}

nonisolated enum ConfidenceLevel: String, Codable, Sendable {
    case high = "High"
    case medium = "Medium"
    case low = "Low"
}

nonisolated enum DetectionMethod: String, Codable, Sendable {
    case ml = "AI"
    case cloud = "Cloud"
    case heuristic = "Rule"
    case manual = "Manual"
}
