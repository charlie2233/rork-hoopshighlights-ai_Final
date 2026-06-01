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
    var teamAttributionStatus: String?

    var duration: Double { endTime - startTime }

    var formattedStartTime: String { Self.formatTime(startTime) }
    var formattedEndTime: String { Self.formatTime(endTime) }
    var formattedDuration: String { Self.formatTime(duration) }

    var confidenceLevel: ConfidenceLevel {
        if confidence >= 0.8 { return .high }
        if confidence >= 0.5 { return .medium }
        return .low
    }

    var reviewBadges: [ClipReviewBadge] {
        var badges: [ClipReviewBadge] = []
        if teamAttributionStatus == "uncertain" || (teamAttribution?.confidence ?? 1.0) < 0.85 {
            badges.append(.teamUncertain)
        }
        if let nativeShotSignals {
            if nativeShotSignals.outcome == "uncertain" {
                badges.append(.outcomeUncertain)
            }
            if nativeShotSignals.isShotLike && !nativeShotSignals.timingWindowOk {
                badges.append(.timingUncertain)
            }
        }
        return badges
    }

    var needsUserReview: Bool {
        !reviewBadges.isEmpty
    }

    var reviewEvidenceRows: [ClipReviewEvidenceRow] {
        var rows: [ClipReviewEvidenceRow] = [
            ClipReviewEvidenceRow(
                id: "decision",
                title: needsUserReview ? "Why kept" : (isKept ? "Why kept" : "Why skipped"),
                detail: reviewDecisionReason,
                systemImage: needsUserReview || isKept ? "checkmark.seal.fill" : "xmark.circle.fill",
                needsReview: needsUserReview
            ),
            ClipReviewEvidenceRow(
                id: "keyframes",
                title: "Key moments",
                detail: keyframeEvidenceText,
                systemImage: "rectangle.stack.fill",
                needsReview: false
            )
        ]

        if let teamEvidenceRow {
            rows.append(teamEvidenceRow)
        }
        if let outcomeEvidenceRow {
            rows.append(outcomeEvidenceRow)
        }
        if let timingEvidenceRow {
            rows.append(timingEvidenceRow)
        }

        return rows
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
        teamAttribution: ClipTeamAttribution? = nil,
        teamAttributionStatus: String? = nil
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
        self.teamAttributionStatus = teamAttributionStatus
    }

    static func formatTime(_ time: Double) -> String {
        let minutes = Int(time) / 60
        let seconds = Int(time) % 60
        let fraction = Int((time.truncatingRemainder(dividingBy: 1)) * 10)
        return String(format: "%d:%02d.%d", minutes, seconds, fraction)
    }

    private var reviewDecisionReason: String {
        if needsUserReview {
            return "Kept for review because team, timing, or outcome still needs a human check."
        }
        if !isKept {
            return "Skipped clips stay out of the finished edit unless you tap Keep."
        }
        if action == .block || action == .steal {
            return "Kept as a defensive highlight with strong motion and visual signals."
        }
        if confidence >= 0.8 {
            return "Kept because confidence is high and the clip has strong highlight signals."
        }
        return "Kept as a possible highlight; review it before making the final edit."
    }

    private var keyframeEvidenceText: String {
        let center = eventCenter ?? startTime + max(duration, 0) / 2
        return "Start \(Self.formatTime(startTime)) · Action \(Self.formatTime(center)) · Finish \(Self.formatTime(endTime))"
    }

    private var teamEvidenceRow: ClipReviewEvidenceRow? {
        let needsReview = teamAttributionStatus == "uncertain" || (teamAttribution?.confidence ?? 1.0) < 0.85

        guard let teamAttribution else {
            guard teamAttributionStatus == "uncertain" else { return nil }
            return ClipReviewEvidenceRow(
                id: "team",
                title: "Team needs check",
                detail: "No confident team evidence came back, so this stays available for Review.",
                systemImage: "person.2.badge.gearshape.fill",
                needsReview: true
            )
        }

        let teamName = teamAttribution.label ?? teamAttribution.colorLabel ?? Self.readableIdentifier(teamAttribution.teamId) ?? "Selected team"
        var details = ["\(teamName), \(Self.percent(teamAttribution.confidence)) confidence"]
        if let source = teamAttribution.source, !source.isEmpty {
            details.append(Self.readableIdentifier(source) ?? source)
        }
        if let evidenceRoleGroups = teamAttribution.evidenceRoleGroups, !evidenceRoleGroups.isEmpty {
            details.append("frames: \(evidenceRoleGroups.joined(separator: ", "))")
        } else if let evidenceFrameRefs = teamAttribution.evidenceFrameRefs, !evidenceFrameRefs.isEmpty {
            details.append("\(evidenceFrameRefs.count) evidence frames")
        }

        return ClipReviewEvidenceRow(
            id: "team",
            title: needsReview ? "Team needs check" : "Team evidence",
            detail: details.joined(separator: " · "),
            systemImage: needsReview ? "person.2.badge.gearshape.fill" : "person.2.fill",
            needsReview: needsReview
        )
    }

    private var outcomeEvidenceRow: ClipReviewEvidenceRow? {
        guard let nativeShotSignals else { return nil }
        let needsReview = nativeShotSignals.outcome == "uncertain"
        let outcome = Self.readableIdentifier(nativeShotSignals.outcome) ?? nativeShotSignals.outcome
        var details = ["\(outcome), \(Self.percent(nativeShotSignals.outcomeConfidence)) confidence"]
        if let source = nativeShotSignals.outcomeEvidenceSource, !source.isEmpty {
            details.append(Self.readableIdentifier(source) ?? source)
        }
        if let reliability = nativeShotSignals.outcomeReliabilityScore {
            details.append("reliability \(Self.percent(reliability))")
        }

        return ClipReviewEvidenceRow(
            id: "outcome",
            title: needsReview ? "Outcome needs check" : "Outcome evidence",
            detail: details.joined(separator: " · "),
            systemImage: needsReview ? "questionmark.circle.fill" : "scope",
            needsReview: needsReview
        )
    }

    private var timingEvidenceRow: ClipReviewEvidenceRow? {
        guard let nativeShotSignals, nativeShotSignals.isShotLike else { return nil }
        let details = [
            "setup \(Self.oneDecimal(nativeShotSignals.leadInSeconds))s",
            "finish \(Self.oneDecimal(nativeShotSignals.followThroughSeconds))s",
            "context \(Self.percent(nativeShotSignals.contextQualityScore))",
            "center \(Self.percent(nativeShotSignals.eventCenterQuality))"
        ]

        return ClipReviewEvidenceRow(
            id: "timing",
            title: nativeShotSignals.timingWindowOk ? "Timing evidence" : "Timing needs check",
            detail: details.joined(separator: " · "),
            systemImage: nativeShotSignals.timingWindowOk ? "timer.circle.fill" : "clock.badge.exclamationmark.fill",
            needsReview: !nativeShotSignals.timingWindowOk
        )
    }

    private static func percent(_ value: Double) -> String {
        "\(Int((value * 100).rounded()))%"
    }

    private static func oneDecimal(_ value: Double) -> String {
        String(format: "%.1f", value)
    }

    private static func readableIdentifier(_ value: String?) -> String? {
        guard let value, !value.isEmpty else { return nil }
        return value
            .replacingOccurrences(of: "_", with: " ")
            .split(separator: " ")
            .map { $0.capitalized }
            .joined(separator: " ")
    }
}

nonisolated struct ClipReviewEvidenceRow: Identifiable, Sendable, Equatable {
    let id: String
    let title: String
    let detail: String
    let systemImage: String
    let needsReview: Bool
}

nonisolated enum ClipReviewBadge: String, Codable, Sendable, Equatable, Hashable, CaseIterable {
    case teamUncertain
    case outcomeUncertain
    case timingUncertain

    var title: String {
        switch self {
        case .teamUncertain: return "Team?"
        case .outcomeUncertain: return "Outcome?"
        case .timingUncertain: return "Timing?"
        }
    }

    var systemImage: String {
        switch self {
        case .teamUncertain: return "person.2.fill"
        case .outcomeUncertain: return "questionmark.circle"
        case .timingUncertain: return "clock.fill"
        }
    }

    var accessibilityLabel: String {
        switch self {
        case .teamUncertain: return "team attribution needs review"
        case .outcomeUncertain: return "outcome needs review"
        case .timingUncertain: return "clip timing needs review"
        }
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
