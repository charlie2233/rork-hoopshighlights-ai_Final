import Foundation

nonisolated enum CloudAnalysisProgressCopy {
    private static let maxVisibleTeamTitleCharacters = 28

    static func approximateRemainingTime(
        statusMessage: String,
        analysisMode: AnalysisExecutionMode,
        progress: Double,
        durationSeconds: Double
    ) -> String? {
        guard analysisMode == .cloud,
              durationSeconds.isFinite,
              durationSeconds > 0 else {
            return nil
        }

        let status = statusMessage.lowercased()
        let totalRange = approximateAnalysisRangeMinutes(for: durationSeconds)
        if status.contains("upload") {
            return "Upload first; after handoff, analysis is roughly \(formatMinuteRange(totalRange)). Large files can take a while."
        }

        if status.contains("queued") || status.contains("waiting") {
            return "Queue can add time; once running, analysis is roughly \(formatMinuteRange(totalRange))."
        }

        let boundedProgress = min(max(progress, 0.05), 0.95)
        let remainingScale = max(0.08, 1.0 - boundedProgress)
        let remainingRange = (
            lower: max(1, Int(ceil(Double(totalRange.lower) * remainingScale))),
            upper: max(1, Int(ceil(Double(totalRange.upper) * remainingScale)))
        )
        return "Approx time left: about \(formatMinuteRange(remainingRange)). Rough guide; long games can take a while."
    }

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

    private static func approximateAnalysisRangeMinutes(for durationSeconds: Double) -> (lower: Int, upper: Int) {
        let sourceMinutes = max(1.0, durationSeconds / 60.0)
        let lower = max(1.0, (sourceMinutes * 0.16) + 0.8)
        let upper = max(lower + 1.0, (sourceMinutes * 0.32) + 2.0)
        return (Int(ceil(lower)), Int(ceil(upper)))
    }

    private static func formatMinuteRange(_ range: (lower: Int, upper: Int)) -> String {
        if range.upper <= range.lower {
            return "\(range.lower) min"
        }
        return "\(range.lower)-\(range.upper) min"
    }
}
