import Foundation

nonisolated enum CloudAnalysisProgressCopy {
    private static let maxVisibleTeamTitleCharacters = 28

    static func detail(
        statusMessage: String,
        analysisMode: AnalysisExecutionMode,
        teamSelection: HighlightTeamSelection
    ) -> String {
        let status = statusMessage.lowercased()

        if status.contains("upload") {
            return "Keep HoopClips open during upload. After cloud handoff, you can switch apps and come back for clips."
        }

        if status.contains("team") || status.contains("jersey") {
            return "Scanning jersey colors so you can target one team or keep all teams."
        }

        if status.contains("queued") || status.contains("waiting") {
            return "Cloud worker is next in line. Reopen HoopClips to refresh real job status."
        }

        if status.contains("candidate")
            || status.contains("finding")
            || status.contains("detecting")
            || status.contains("clip")
            || status.contains("highlight") {
            if analysisMode == .cloud, teamSelection.mode == .team {
                let teamTitle = compactTeamTitle(teamSelection.displayTitle)
                let separator = teamTitle.hasSuffix("...") ? " " : " and "
                return "Focusing on \(teamTitle)\(separator)keeping uncertain plays for Review."
            }
            return "Building a high-recall clip pool from both teams for Review."
        }

        if status.contains("frame")
            || status.contains("scoring")
            || status.contains("motion")
            || status.contains("audio")
            || status.contains("action") {
            if analysisMode == .cloud {
                return "Cloud analysis keeps running after handoff. Reopen HoopClips to see the latest clips."
            }
            return "Scoring motion, audio peaks, and basketball action."
        }

        if status.contains("finalizing") || status.contains("refining") {
            return "Validated clips are coming back for Review."
        }

        if analysisMode == .cloud {
            return "Cloud analysis is active. Reopen HoopClips for the latest result."
        }

        return "Analysis is running on device because cloud mode is unavailable."
    }

    static func backgroundReminder(statusMessage: String, analysisMode: AnalysisExecutionMode) -> String? {
        guard analysisMode == .cloud else { return nil }

        let status = statusMessage.lowercased()
        if status.contains("upload") {
            return nil
        }

        if status.contains("queued")
            || status.contains("waiting")
            || status.contains("candidate")
            || status.contains("finding")
            || status.contains("detecting")
            || status.contains("clip")
            || status.contains("highlight")
            || status.contains("frame")
            || status.contains("scoring")
            || status.contains("motion")
            || status.contains("audio")
            || status.contains("action")
            || status.contains("finalizing")
            || status.contains("refining") {
            return "Safe to switch apps after upload. HoopClips keeps the cloud analysis job attached to this project."
        }

        return "After cloud handoff, you can switch apps and reopen HoopClips for real job status."
    }

    private static func compactTeamTitle(_ title: String) -> String {
        let trimmed = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let visibleTitle = trimmed.isEmpty ? "selected team" : trimmed
        guard visibleTitle.count > maxVisibleTeamTitleCharacters else {
            return visibleTitle
        }

        let prefixLength = max(0, maxVisibleTeamTitleCharacters - 3)
        let rawPrefix = String(visibleTitle.prefix(prefixLength))
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let wordSafePrefix: String
        if let lastSpace = rawPrefix.lastIndex(of: " ") {
            wordSafePrefix = String(rawPrefix[..<lastSpace])
        } else {
            wordSafePrefix = rawPrefix
        }

        return (wordSafePrefix.isEmpty ? rawPrefix : wordSafePrefix) + "..."
    }
}
