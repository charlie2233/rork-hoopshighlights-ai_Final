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
        fastUploadMode: Bool,
        latestUploadProgress: String,
        latestUploadSourceOptimization: String,
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
            "fastUploadMode=\(fastUploadMode)",
            "latestUploadProgress=\(safeSummaryValue(latestUploadProgress))",
            "latestUploadSourceOptimization=\(safeSummaryValue(latestUploadSourceOptimization))",
            "longVideoUploadEvidence=\(longVideoUploadEvidence(from: latestUploadProgress, latestUploadSourceOptimization: latestUploadSourceOptimization, analysisStatus: analysisStatus))",
            "latestUnexpectedExit=\(safeSummaryValue(latestUnexpectedExit))",
            "latestCrashReportDelivery=\(safeSummaryValue(latestCrashReportDelivery))",
            "privacy=no secrets, URLs, object keys, or local file paths"
        ].joined(separator: "\n")
    }

    private static func longVideoUploadEvidence(
        from latestUploadProgress: String,
        latestUploadSourceOptimization: String,
        analysisStatus: String
    ) -> String {
        let combined = "\(latestUploadProgress) \(latestUploadSourceOptimization) \(analysisStatus)".lowercased()
        var evidence: [String] = []

        if combined.contains("compact") || combined.contains("optimized") {
            evidence.append("optimized_source")
        }
        if combined.contains("fastuploadmode=true") || combined.contains("fast_upload_mode") {
            evidence.append("fast_upload_mode")
        }
        if combined.contains("chunk") {
            evidence.append("chunks")
        }
        if combined.contains("resume") || combined.contains("resum") {
            evidence.append("resume")
        }
        if combined.contains("fast") || combined.contains("lane") || combined.contains("parallel") {
            evidence.append("fast_lanes")
        }
        if combined.contains("saved") || combined.contains("completed=") || combined.contains("progresspercent=") {
            evidence.append("saved_progress")
        }
        if combined.contains("/s") || combined.contains("mb/s") || combined.contains("kb/s") {
            evidence.append("speed")
        }
        if combined.contains("left") || combined.contains("eta") {
            evidence.append("eta")
        }

        guard !evidence.isEmpty else { return "none" }
        return safeSummaryValue(evidence.joined(separator: "+"))
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

nonisolated enum SmokeProofBundleCopy {
    static let title = "HoopClips Issue Bundle"

    static func bundle(
        generatedAt: String,
        buildSummary: String,
        uploadState: String,
        crashSummary: String,
        crashDelivery: String
    ) -> String {
        [
            title,
            "generatedAt=\(safeBundleValue(generatedAt))",
            "",
            "buildSummary:",
            buildSummary,
            "",
            "uploadState:",
            uploadState,
            "",
            "latestUnexpectedExit=\(safeBundleValue(crashSummary))",
            "latestCrashReportDelivery=\(safeBundleValue(crashDelivery))",
            "privacy=no secrets, URLs, object keys, or local file paths"
        ].joined(separator: "\n")
    }

    private static func safeBundleValue(_ value: String) -> String {
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

        return String(compact.prefix(240))
    }
}
