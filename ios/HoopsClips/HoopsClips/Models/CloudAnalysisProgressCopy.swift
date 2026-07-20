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
    private static let fastUploadModeDefaultsKey = "hoopsclips.cloudUpload.fastUploadMode.v1"
    private static let compactUploadFallbackWindow = "fallback to original in about 4 min"
    private static let automaticUploadOptimizationDurationSeconds: Double = 12 * 60
    private static let automaticUploadOptimizationFileSizeBytes: Int64 = 256 * 1_024 * 1_024

    static func isFastUploadModeEnabled() -> Bool {
        UserDefaults.standard.bool(forKey: fastUploadModeDefaultsKey)
    }

    static func fastUploadModeFact() -> String? {
        isFastUploadModeEnabled() ? "Fast Upload Mode on" : nil
    }

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
            if let chunkProgress = uploadChunkProgressSummary(from: statusMessage) {
                return "Reconnecting to saved upload: \(chunkProgress). Finished chunks stay saved; resume uses fast lanes when available."
            }
            return "Reconnecting to saved upload. Finished chunks stay saved; resume uses fast lanes when available."
        }

        if status.contains("upload") && status.contains("retry") {
            if let retryProgress = uploadRetryProgressSummary(from: statusMessage) {
                return "Retrying upload: \(retryProgress). Finished chunks stay saved; fast lanes are reused when available."
            }
            return "Retrying upload. Finished chunks stay saved; HoopClips keeps trying with fast lanes before you restart."
        }

        if status.contains("upload") && isSlowUploadStatus(status) {
            if let chunkProgress = uploadChunkProgressSummary(from: statusMessage) {
                return "Slow connection, still uploading \(chunkProgress). Switch apps if needed; reopen for fresh progress."
            }
            return "Connection is slow, but upload is alive. Switch apps if needed; reopen HoopClips to refresh progress."
        }

        if status.contains("upload") {
            if let chunkProgress = uploadChunkProgressSummary(from: statusMessage) {
                return "Uploading \(chunkProgress). Safe to switch apps; completed chunks stay saved for fast resume."
            }
            return "Background upload active. Huge videos use resumable chunks and fast resume. Reopen for live progress."
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
            if let chunkProgress = uploadChunkProgressSummary(from: statusMessage) {
                return "Resuming saved upload: \(chunkProgress). Completed chunks are preserved and fast lanes are used when available."
            }
            return "Resuming saved upload. Completed chunks are preserved and fast lanes are used when available."
        }

        if status.contains("upload") && status.contains("retry") {
            if let retryProgress = uploadRetryProgressSummary(from: statusMessage) {
                return "Retrying upload: \(retryProgress). Completed chunks are preserved for fast resume."
            }
            return "Retrying saved upload. Completed chunks are preserved for fast resume."
        }

        if status.contains("upload") && isSlowUploadStatus(status) {
            if let chunkProgress = uploadChunkProgressSummary(from: statusMessage) {
                return "Slow upload, still on \(chunkProgress). Wi-Fi helps most; switching apps is OK."
            }
            return "Slow upload, still working. Wi-Fi helps most; switching apps is OK because chunks can resume."
        }

        if status.contains("upload") {
            if let chunkProgress = uploadChunkProgressSummary(from: statusMessage) {
                return "Background upload active: \(chunkProgress). Safe to switch apps and reopen for live progress."
            }
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
        let chunkProgress = uploadChunkProgressSummary(from: statusMessage)
        let retryProgress = uploadRetryProgressSummary(from: statusMessage)

        var parts: [String] = []
        if let retryProgress {
            parts.append(retryProgress)
        }
        if let chunkProgress {
            parts.append(chunkProgress)
        }
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

    static func uploadTransferPercent(statusMessage: String) -> Int? {
        guard let stage = statusMessage
            .components(separatedBy: " · ")
            .first?
            .trimmingCharacters(in: .whitespacesAndNewlines),
              stage.lowercased().contains("upload") else {
            return nil
        }

        let pattern = #"\b(\d{1,3})\s*%"#
        guard let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(
                  in: stage,
                  range: NSRange(stage.startIndex..<stage.endIndex, in: stage)
              ),
              match.numberOfRanges >= 2,
              let percentRange = Range(match.range(at: 1), in: stage),
              let percent = Int(stage[percentRange]),
              (0...100).contains(percent) else {
            return nil
        }

        return percent
    }

    static func displayProgress(overallProgress: Double, statusMessage: String) -> Double {
        let safeOverallProgress = overallProgress.isFinite
            ? min(max(overallProgress, 0), 1)
            : 0
        guard let uploadPercent = uploadTransferPercent(statusMessage: statusMessage) else {
            return safeOverallProgress
        }
        return Double(uploadPercent) / 100
    }

    static func compactUploadTransferMetrics(statusMessage: String) -> String? {
        guard statusMessage.lowercased().contains("upload") else { return nil }

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

        let parts = [byteProgress, speed, remaining].compactMap { $0 }
        guard !parts.isEmpty else { return nil }
        return parts.joined(separator: " · ")
    }

    static func uploadResumeProgressSummary(from summary: String) -> String? {
        var values: [String: String] = [:]
        for token in summary.split(separator: " ") {
            let parts = token.split(separator: "=", maxSplits: 1)
            guard parts.count == 2 else { continue }
            values[String(parts[0])] = String(parts[1])
        }

        if let progress = Int(values["progressPercent"] ?? "") {
            let boundedProgress = min(max(progress, 0), 100)
            guard boundedProgress > 0 else { return nil }
            return "\(boundedProgress)% saved"
        }

        guard let completedBytes = Int64(values["completedBytes"] ?? ""),
              let totalBytes = Int64(values["totalBytes"] ?? ""),
              totalBytes > 0 else {
            return nil
        }

        let percent = min(100, max(0, Int((Double(completedBytes) / Double(totalBytes) * 100).rounded())))
        guard percent > 0 else { return nil }
        return "\(percent)% saved"
    }

    private static func uploadRetryProgressSummary(from statusMessage: String) -> String? {
        let lowercasedStatus = statusMessage.lowercased()
        guard lowercasedStatus.contains("retry") else { return nil }

        let segments = statusMessage
            .components(separatedBy: " · ")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        let retrySegment = segments.first { $0.lowercased().contains("retry") } ?? statusMessage
        var compact = retrySegment
            .replacingOccurrences(of: " after try ", with: ", try ", options: [.caseInsensitive])
            .replacingOccurrences(of: "retrying in ", with: "Retry in ", options: [.caseInsensitive])
            .replacingOccurrences(of: "retrying after ", with: "Retrying after ", options: [.caseInsensitive])
            .trimmingCharacters(in: .whitespacesAndNewlines)

        if !compact.localizedCaseInsensitiveContains("retry") {
            compact = "Retrying saved chunk"
        }

        return String(compact.prefix(72))
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
                message: "No need to restart yet. HoopClips is retrying saved chunks with fast lanes when available; send diagnostics if progress does not change for several minutes.",
                icon: "arrow.clockwise.icloud.fill"
            )
        }

        if combined.contains("stalled")
            || combined.contains("stalled=true")
            || combined.contains("source_still_uploading")
            || combined.contains("active_sessions_pending") {
            return CloudAnalysisSlowUploadHelp(
                title: "Upload is still active",
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
        let fastUploadModeEnabled = isFastUploadModeEnabled()
        let isLongSource = durationSeconds.isFinite
            && durationSeconds >= automaticUploadOptimizationDurationSeconds
        let isLargeSource = (fileSizeBytes ?? 0) >= automaticUploadOptimizationFileSizeBytes
        let prefersCompactSource = fastUploadModeEnabled
            || durationSeconds.isFinite && durationSeconds >= 45 * 60
            || (fileSizeBytes ?? 0) >= 1_400 * 1_024 * 1_024
        let isUploadStruggling = status.contains("upload") && isSlowUploadStatus(status)
        let shouldOptimize = fastUploadModeEnabled || isLongSource || isLargeSource || isUploadStruggling

        let reasons = [
            fastUploadModeEnabled ? "fast_upload_mode" : nil,
            isLongSource ? "long_source" : nil,
            isLargeSource ? "large_source" : nil,
            isUploadStruggling ? "slow_upload" : nil
        ]
            .compactMap { $0 }
            .joined(separator: "+")
        let reason = reasons.isEmpty ? "none" : reasons
        let sourceSizeMB = fileSizeBytes.map { max(0, Int((Double($0) / 1_048_576.0).rounded())) }
        let durationMinutes = durationSeconds.isFinite ? max(0, Int((durationSeconds / 60.0).rounded())) : 0
        let quickFact = uploadSourceOptimizationQuickFact(
            shouldOptimize: shouldOptimize,
            status: status,
            isLongSource: isLongSource,
            isLargeSource: isLargeSource,
            isUploadStruggling: isUploadStruggling,
            fastUploadModeEnabled: fastUploadModeEnabled,
            prefersCompactSource: prefersCompactSource,
            durationMinutes: durationMinutes,
            sourceSizeMB: sourceSizeMB
        )
        let proof = [
            "recommended=\(shouldOptimize)",
            "reason=\(reason)",
            "fastUploadMode=\(fastUploadModeEnabled)",
            "durationMinutes=\(durationMinutes)",
            "sourceSizeMB=\(sourceSizeMB.map(String.init) ?? "unknown")",
            "automaticDurationThresholdMinutes=\(Int(automaticUploadOptimizationDurationSeconds / 60))",
            "automaticSizeThresholdMB=\(automaticUploadOptimizationFileSizeBytes / 1_048_576)",
            "optimizedSourceStatus=available",
            "preferredOptimizationProfile=\(prefersCompactSource ? "compact_540p" : "balanced_720p")",
            "currentPath=optimized_when_recommended_else_original_background_chunked_upload_with_fast_resume"
        ].joined(separator: " ")

        return CloudAnalysisUploadSourceOptimization(
            shouldPreferOptimizedSource: shouldOptimize,
            quickFact: quickFact,
            proof: proof
        )
    }

    private static func uploadSourceOptimizationQuickFact(
        shouldOptimize: Bool,
        status: String,
        isLongSource: Bool,
        isLargeSource: Bool,
        isUploadStruggling: Bool,
        fastUploadModeEnabled: Bool,
        prefersCompactSource: Bool,
        durationMinutes: Int,
        sourceSizeMB: Int?
    ) -> String? {
        guard shouldOptimize else { return nil }

        if fastUploadModeEnabled {
            if durationMinutes > 0 {
                return "Fast Upload Mode: compact upload for \(durationMinutes) min video"
            }
            let sizeText = sourceSizeMB.map { "\($0) MB" }
            if let sizeText {
                return "Fast Upload Mode: compact upload from \(sizeText)"
            }
            return "Fast Upload Mode: compact upload"
        }

        return "Smaller source suggested"
    }

    static func uploadSourceSavingsFact(from summary: String) -> String? {
        let values = uploadOptimizationSummaryValues(from: summary)
        if values["reason"] == "preparation_timed_out" {
            return "Compact prep timed out; uploading original"
        }

        guard values["result"] == "optimized",
              let savedMB = Int(values["savedMB"] ?? ""),
              savedMB > 0 else {
            return nil
        }
        let profileLabel = values["profile"] == "compact_540p" ? "compact upload" : "upload"

        if let optimizedMB = Int(values["optimizedMB"] ?? ""),
           optimizedMB > 0 {
            return "Saved \(savedMB) MB; \(profileLabel) is \(optimizedMB) MB"
        }

        if let originalMB = Int(values["originalMB"] ?? ""),
           originalMB > 0 {
            return "Saved \(savedMB) MB from \(originalMB) MB source"
        }

        return "Saved \(savedMB) MB before upload"
    }

    private static func uploadOptimizationSummaryValues(from summary: String) -> [String: String] {
        summary
            .split(whereSeparator: \.isWhitespace)
            .reduce(into: [String: String]()) { values, component in
                let pair = component.split(separator: "=", maxSplits: 1).map(String.init)
                guard pair.count == 2 else { return }
                values[pair[0]] = pair[1]
            }
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
        let chunkProgress = uploadChunkProgressSummary(from: statusMessage)

        var summaryParts: [String] = []
        if let chunkProgress {
            summaryParts.append(chunkProgress)
        }
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

    private static func uploadChunkProgressSummary(from statusMessage: String) -> String? {
        let lowercasedStatus = statusMessage.lowercased()
        if lowercasedStatus.contains("chunks complete")
            || lowercasedStatus.contains("resumed chunks complete")
            || lowercasedStatus.contains("saved chunks assembled") {
            return "all chunks uploaded"
        }

        if lowercasedStatus.contains("chunked upload starting") {
            return "chunked upload starting"
        }

        guard lowercasedStatus.contains("chunk") else { return nil }

        let pattern = #"\bchunk(?:\s|_|-|=)*(\d{1,3})\s*/\s*(\d{1,3})"#
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else {
            return nil
        }
        let range = NSRange(statusMessage.startIndex..<statusMessage.endIndex, in: statusMessage)
        guard let match = regex.firstMatch(in: statusMessage, options: [], range: range),
              match.numberOfRanges >= 3,
              let currentRange = Range(match.range(at: 1), in: statusMessage),
              let totalRange = Range(match.range(at: 2), in: statusMessage),
              let current = Int(statusMessage[currentRange]),
              let total = Int(statusMessage[totalRange]),
              current > 0,
              total > 0,
              current <= total else {
            return nil
        }

        return "chunk \(current)/\(total)"
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
