import Foundation

nonisolated struct CloudAnalysisSlowUploadHelp: Equatable, Sendable {
    let title: String
    let message: String
    let icon: String
}

nonisolated struct CloudAnalysisUploadSourceOptimization: Equatable, Sendable {
    let shouldPreferOptimizedSource: Bool
    let quickFact: String?
    let proof: String
}

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
            if isSlowUploadStatus(status) {
                if let liveEstimateSummary = liveUploadEstimateSummary(from: statusMessage) {
                    return "Slow network, still uploading: \(liveEstimateSummary). Safe to switch apps; HoopClips will resume chunks when reopened."
                }
                return "Slow network, still uploading. Safe to switch apps; HoopClips will resume chunks when reopened. Analysis after upload is about \(formatMinuteRange(totalRange))."
            }
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

        if status.contains("upload") && isSlowUploadStatus(status) {
            return "Connection is slow, but upload is alive. Switch apps if needed; reopen HoopClips to refresh progress."
        }

        if status.contains("upload") {
            return "Background upload active. Huge videos use resumable chunks when supported; switch apps and reopen for live progress."
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

        if status.contains("upload") && isSlowUploadStatus(status) {
            return "Slow upload, still working. Wi-Fi helps most; switching apps is OK because chunks can resume."
        }

        if status.contains("upload") {
            return "Background upload active. Wi-Fi is fastest for huge videos; safe to switch apps and reopen HoopClips for live progress."
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

    static func compactUploadProgressSummary(statusMessage: String) -> String? {
        let lowercasedStatus = statusMessage.lowercased()
        guard lowercasedStatus.contains("upload") else { return nil }

        let segments = statusMessage
            .components(separatedBy: " · ")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        let byteProgress = segments.first { segment in
            segment.contains("/")
                && (segment.contains("MB") || segment.contains("GB") || segment.contains("KB"))
        }
        let speed = segments.first { $0.contains("/s") }
        let remaining = segments.first { segment in
            let lowercasedSegment = segment.lowercased()
            return lowercasedSegment.hasPrefix("about ") && lowercasedSegment.contains(" left")
        }

        var parts: [String] = []
        if let byteProgress {
            parts.append(byteProgress)
        }
        if let speed {
            parts.append("Speed \(speed)")
        }
        if let remaining {
            let remainingValue = remaining
                .replacingOccurrences(of: "about ", with: "", options: [.caseInsensitive])
                .replacingOccurrences(of: " left", with: "", options: [.caseInsensitive])
            if !remainingValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                parts.append("ETA \(remainingValue)")
            }
        }
        if parts.isEmpty, isSlowUploadStatus(lowercasedStatus) {
            parts.append("Waiting for connection")
        }

        guard !parts.isEmpty else { return nil }
        return parts.joined(separator: " · ")
    }

    static func slowUploadHelp(
        statusMessage: String,
        latestUploadProgress: String,
        latestBackgroundUploadProof: String?,
        recentBackgroundUploadProofTrail: String?
    ) -> CloudAnalysisSlowUploadHelp? {
        let combined = [
            statusMessage,
            latestUploadProgress,
            latestBackgroundUploadProof ?? "",
            recentBackgroundUploadProofTrail ?? ""
        ]
            .joined(separator: " ")
            .lowercased()

        guard combined.contains("upload") else { return nil }
        guard isSlowUploadStatus(combined)
            || combined.contains("stalled=true")
            || combined.contains("source_still_uploading")
            || combined.contains("active_sessions_pending")
            || combined.contains("connectivity")
            || combined.contains("network") else {
            return nil
        }

        if combined.contains("waiting for connection")
            || combined.contains("waiting for connectivity")
            || combined.contains("connectivity")
            || combined.contains("network") {
            return CloudAnalysisSlowUploadHelp(
                title: "Waiting for connection",
                message: "Wi-Fi helps most. HoopClips keeps the saved upload and retries chunks when the connection comes back.",
                icon: "wifi.exclamationmark"
            )
        }

        if combined.contains("retry") || combined.contains("retrying") {
            return CloudAnalysisSlowUploadHelp(
                title: "Retrying upload",
                message: "No need to restart yet. HoopClips is retrying saved chunks; send proof if it stays stuck.",
                icon: "arrow.clockwise.icloud.fill"
            )
        }

        if combined.contains("stalled")
            || combined.contains("stalled=true")
            || combined.contains("source_still_uploading")
            || combined.contains("active_sessions_pending") {
            return CloudAnalysisSlowUploadHelp(
                title: "Upload is still moving",
                message: "Large videos can pause between iOS updates. Keep Wi-Fi on; switch apps if needed and reopen for fresh progress.",
                icon: "speedometer"
            )
        }

        return CloudAnalysisSlowUploadHelp(
            title: "Slow upload",
            message: "Wi-Fi + staying near the router helps most. Huge videos use resumable chunks when supported.",
            icon: "tortoise.fill"
        )
    }

    static func uploadSourceOptimization(
        durationSeconds: Double,
        fileSizeBytes: Int64?,
        statusMessage: String,
        latestUploadProgress: String
    ) -> CloudAnalysisUploadSourceOptimization {
        let status = "\(statusMessage) \(latestUploadProgress)".lowercased()
        let isLongSource = durationSeconds.isFinite && durationSeconds >= 30 * 60
        let isHugeSource = (fileSizeBytes ?? 0) >= 900 * 1_024 * 1_024
        let isUploadStruggling = status.contains("upload") && isSlowUploadStatus(status)
        let shouldOptimize = isLongSource || isHugeSource || isUploadStruggling

        let reasons = [
            isLongSource ? "long_source" : nil,
            isHugeSource ? "huge_source" : nil,
            isUploadStruggling ? "slow_upload" : nil
        ]
            .compactMap { $0 }
            .joined(separator: "+")
        let reason = reasons.isEmpty ? "none" : reasons
        let sourceSizeMB = fileSizeBytes.map { max(0, Int((Double($0) / 1_048_576.0).rounded())) }
        let durationMinutes = durationSeconds.isFinite ? max(0, Int((durationSeconds / 60.0).rounded())) : 0
        let quickFact = shouldOptimize ? "Smaller source suggested" : nil
        let proof = [
            "recommended=\(shouldOptimize)",
            "reason=\(reason)",
            "durationMinutes=\(durationMinutes)",
            "sourceSizeMB=\(sourceSizeMB.map(String.init) ?? "unknown")",
            "optimizedSourceStatus=not_enabled",
            "currentPath=original_background_chunked_upload"
        ].joined(separator: " ")

        return CloudAnalysisUploadSourceOptimization(
            shouldPreferOptimizedSource: shouldOptimize,
            quickFact: quickFact,
            proof: proof
        )
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

    private static func isSlowUploadStatus(_ status: String) -> Bool {
        status.contains("slow")
            || status.contains("paused")
            || status.contains("stall")
            || status.contains("stalled")
            || status.contains("retry")
            || status.contains("retrying")
            || status.contains("waiting for connection")
            || status.contains("waiting for connectivity")
    }
}
