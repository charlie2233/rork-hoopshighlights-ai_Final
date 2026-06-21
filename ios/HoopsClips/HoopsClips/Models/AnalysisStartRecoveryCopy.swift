import Foundation

nonisolated struct AnalysisStartRecoveryContent: Equatable, Sendable {
    let title: String
    let message: String
    let icon: String
}

nonisolated enum AnalysisStartRecoveryCopy {
    static func content(for reason: AnalysisStartBlockReason) -> AnalysisStartRecoveryContent {
        switch reason {
        case .importing:
            return AnalysisStartRecoveryContent(
                title: "Import still finishing",
                message: "Wait here or switch apps. AI Analysis unlocks when the video is saved.",
                icon: "tray.and.arrow.down.fill"
            )
        case .noVideo:
            return AnalysisStartRecoveryContent(
                title: "Import a video first",
                message: "Pick a video above, then HoopClips can upload it for AI Analysis.",
                icon: "video.badge.plus"
            )
        case .alreadyAnalyzing:
            return AnalysisStartRecoveryContent(
                title: "Analysis already running",
                message: "Watch progress here. Review opens automatically when clips are ready.",
                icon: "brain.head.profile.fill"
            )
        case .teamScan:
            return AnalysisStartRecoveryContent(
                title: "Team scan running",
                message: "Give it a few seconds. If teams are unclear, HoopClips uses All teams.",
                icon: "person.3.sequence.fill"
            )
        case .teamSelection:
            return AnalysisStartRecoveryContent(
                title: "Choose target first",
                message: "Solo? Choose All teams. Otherwise pick the team to highlight.",
                icon: "hand.tap.fill"
            )
        }
    }
}
