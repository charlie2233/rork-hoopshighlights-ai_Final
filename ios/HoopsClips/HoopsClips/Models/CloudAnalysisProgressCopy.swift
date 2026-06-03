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
            return "Upload is active. Keep HoopClips open until upload finishes; then you can switch apps."
        }

        if status.contains("team") || status.contains("jersey") {
            return "Scanning jersey colors so you can target one team or keep all teams."
        }

        if status.contains("queued") || status.contains("waiting") {
            return "Cloud job is waiting in queue. Return to HoopClips to refresh live status."
        }

        if status.contains("candidate")
            || status.contains("finding")
            || status.contains("detecting")
            || status.contains("clip")
            || status.contains("highlight") {
            if analysisMode == .cloud, teamSelection.mode == .team {
                let teamTitle = compactTeamTitle(teamSelection.displayTitle)
                let separator = teamTitle.hasSuffix("...") ? " " : " and "
                return "Focusing on \(teamTitle)\(separator)including uncertain plays for Review."
            }
            return "Building a high-recall clip pool from both teams for Review."
        }

        if status.contains("frame")
            || status.contains("scoring")
            || status.contains("motion")
            || status.contains("audio")
            || status.contains("action") {
            if analysisMode == .cloud {
                return "Cloud analysis is still running. Return to HoopClips to see the latest clips."
            }
            return "Scoring motion, audio peaks, and basketball action."
        }

        if status.contains("finalizing") || status.contains("refining") {
            return "Cloud is validating candidates and preparing Review."
        }

        if analysisMode == .cloud {
            return "Cloud analysis is active. Reopen HoopClips to see the latest result."
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
            return "You can leave HoopClips while this runs. Status refreshes when you return."
        }

        return "You can leave HoopClips while this runs and reopen it for real job status."
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
