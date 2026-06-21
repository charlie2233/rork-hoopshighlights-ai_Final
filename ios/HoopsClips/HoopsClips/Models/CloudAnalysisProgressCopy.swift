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
            if let liveEstimateSummary = liveUploadEstimateSummary(from: statusMessage) {
                return "Upload \(liveEstimateSummary). Safe to switch apps. Large files use resumable background upload; Wi-Fi is fastest. Analysis after upload is about \(formatMinuteRange(totalRange))."
            }
            return "Large uploads stay resumable in background. Wi-Fi is fastest; cellular can work if iOS allows it. After upload, analysis is about \(formatMinuteRange(totalRange))."
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

        if status.contains("resuming") && status.contains("upload") {
            return "Reconnecting to the saved background upload. HoopClips will skip chunks that already finished."
        }

        if status.contains("upload") {
            return "Background upload is active. Large videos upload in resumable chunks when the server supports it; you can switch apps and reopen for live progress."
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
                return "Cloud analysis is active. You can switch apps and reopen HoopClips for live status."
            }
            return "Scoring motion, audio peaks, and basketball action."
        }

        if status.contains("finalizing") || status.contains("refining") {
            return "Cloud is validating candidates and preparing Review."
        }

        if analysisMode == .cloud {
            return "Cloud analysis is active. You can switch apps and reopen HoopClips for live status."
        }

        return "Analysis is running on device because cloud mode is unavailable."
    }

    static func backgroundReminder(statusMessage: String, analysisMode: AnalysisExecutionMode) -> String? {
        guard analysisMode == .cloud else { return nil }

        let status = statusMessage.lowercased()
        if status.contains("resuming") && status.contains("upload") {
            return "Resuming saved background upload. Completed chunks are preserved."
        }

        if status.contains("upload") {
            return "Background upload active. Wi-Fi is fastest for huge videos; safe to switch apps and reopen HoopClips to refresh ETA and progress."
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
            return "Cloud job handed off. You can switch apps; HoopClips will reconnect when opened."
        }

        return "Cloud job handed off. You can switch apps; HoopClips will reconnect when opened."
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

    private static func liveUploadEstimateSummary(from statusMessage: String) -> String? {
        let parts = statusMessage
            .components(separatedBy: " · ")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        let eta = parts.first { part in
            let lowercased = part.lowercased()
            return lowercased.hasPrefix("about ") && lowercased.hasSuffix(" left")
        }
        let speed = parts.first { part in
            let lowercased = part.lowercased()
            return lowercased.contains("mb/s") || lowercased.contains("kb/s")
        }
        let bytes = parts.first { part in
            let lowercased = part.lowercased()
            return lowercased.contains("/") && (lowercased.contains(" mb") || lowercased.contains(" gb"))
        }

        var summaryParts: [String] = []
        if let eta {
            summaryParts.append("ETA \(eta)")
        }
        if let speed {
            summaryParts.append(speed)
        }
        if let bytes {
            summaryParts.append(bytes)
        }

        guard !summaryParts.isEmpty else {
            return nil
        }
        return summaryParts.joined(separator: " · ")
    }
}
