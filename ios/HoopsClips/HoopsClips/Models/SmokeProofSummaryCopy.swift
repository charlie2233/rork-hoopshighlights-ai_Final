import Foundation

nonisolated enum SmokeProofSummaryCopy {
    static let title = "HoopClips Build Summary"

    static func summary(
        generatedAt: String,
        appVersion: String,
        build: String,
        environment: String,
        cloudLaunchMode: String,
        phoneSmokeResult: String = "not_run",
        phoneSmokeIssueNote: String = "none",
        videoLoaded: Bool,
        videoDurationSeconds: Int,
        importInProgress: Bool,
        analysisIsAnalyzing: Bool,
        analysisProgressPercent: Int,
        analysisStatus: String,
        clips: Int,
        keptClips: Int,
        needsReviewClips: Int,
        lastAnalysisBlockReason: String,
        latestUploadProgress: String,
        latestUnexpectedExit: String,
        latestCrashReportDelivery: String
    ) -> String {
        [
            title,
            "generatedAt=\(safeSummaryValue(generatedAt))",
            "appVersion=\(safeSummaryValue(appVersion))",
            "build=\(safeSummaryValue(build))",
            "environment=\(safeSummaryValue(environment))",
            "cloudLaunchMode=\(safeSummaryValue(cloudLaunchMode))",
            "phoneSmokeResult=\(safeSummaryValue(phoneSmokeResult))",
            "phoneSmokeIssueNote=\(safeSummaryValue(phoneSmokeIssueNote))",
            "videoLoaded=\(videoLoaded)",
            "videoDurationSeconds=\(max(0, videoDurationSeconds))",
            "importInProgress=\(importInProgress)",
            "analysisIsAnalyzing=\(analysisIsAnalyzing)",
            "analysisProgressPercent=\(min(max(analysisProgressPercent, 0), 100))",
            "analysisStatus=\(safeSummaryValue(analysisStatus))",
            "clips=\(max(0, clips))",
            "keptClips=\(max(0, keptClips))",
            "needsReviewClips=\(max(0, needsReviewClips))",
            "lastAnalysisBlockReason=\(safeSummaryValue(lastAnalysisBlockReason))",
            "latestUploadProgress=\(safeSummaryValue(latestUploadProgress))",
            "latestUnexpectedExit=\(safeSummaryValue(latestUnexpectedExit))",
            "latestCrashReportDelivery=\(safeSummaryValue(latestCrashReportDelivery))",
            "privacy=no secrets, URLs, object keys, or local file paths"
        ].joined(separator: "\n")
    }

    private static func safeSummaryValue(_ value: String) -> String {
        let compact = value
            .replacingOccurrences(of: "\n", with: " ")
            .replacingOccurrences(of: "\t", with: " ")
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: "_")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !compact.isEmpty else { return "none" }

        let lowercased = compact.lowercased()
        let forbiddenMarkers = [
            "http://",
            "https://",
            "uploads/",
            "edits/",
            "renders/",
            "render_logs/",
            "sourceobjectkey",
            "source_object_key",
            "object_key",
            "presigned",
            "signature",
            "x-amz",
            "x-goog",
            "authorization",
            "bearer",
            "file://",
            "/var/",
            "/users/"
        ]
        if forbiddenMarkers.contains(where: { lowercased.contains($0) }) {
            return "redacted"
        }

        return String(compact.prefix(180))
    }
}
