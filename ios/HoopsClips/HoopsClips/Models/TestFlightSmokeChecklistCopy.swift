import Foundation

nonisolated enum TestFlightSmokeChecklistCopy {
    static let title = "HoopClips TestFlight Smoke Checklist"

    static func checklist(
        generatedAt: String,
        appVersion: String,
        build: String,
        environment: String,
        cloudLaunchMode: String,
        phoneSmokeResult: String = "not_run",
        phoneSmokeIssueNote: String = "none",
        videoLoaded: Bool = false,
        videoDurationSeconds: Int = 0,
        analysisIsAnalyzing: Bool = false,
        analysisProgressPercent: Int = 0,
        analysisStatus: String = "none",
        reviewReady: Bool = false,
        clipCount: Int = 0,
        keptClipCount: Int = 0,
        needsReviewClipCount: Int = 0,
        fastUploadMode: Bool = false,
        pendingUploadSummary: String = "none",
        latestUploadProgress: String = "none",
        latestUploadSourceOptimization: String = "none"
    ) -> String {
        [
            title,
            "generatedAt=\(safeValue(generatedAt))",
            "appVersion=\(safeValue(appVersion))",
            "build=\(safeValue(build))",
            "environment=\(safeValue(environment))",
            "cloudLaunchMode=\(safeValue(cloudLaunchMode))",
            "phoneSmokeResult=\(safeValue(phoneSmokeResult))",
            "phoneSmokeIssueNote=\(safeValue(phoneSmokeIssueNote))",
            "currentProof:",
            "- videoLoaded=\(videoLoaded)",
            "- videoDurationSeconds=\(max(videoDurationSeconds, 0))",
            "- analysisIsAnalyzing=\(analysisIsAnalyzing)",
            "- analysisProgressPercent=\(min(max(analysisProgressPercent, 0), 100))",
            "- analysisStatus=\(safeValue(analysisStatus))",
            "- reviewReady=\(reviewReady)",
            "- clipCount=\(max(clipCount, 0))",
            "- keptClipCount=\(max(keptClipCount, 0))",
            "- needsReviewClipCount=\(max(needsReviewClipCount, 0))",
            "- fastUploadMode=\(fastUploadMode)",
            "- pendingUpload=\(safeValue(pendingUploadSummary))",
            "- latestUploadProgress=\(safeValue(latestUploadProgress))",
            "- latestUploadSourceOptimization=\(safeValue(latestUploadSourceOptimization))",
            "longVideoProofTargets:",
            "- Fast Upload Mode state is visible in proof",
            "- compact/balanced upload optimization summary is present",
            "- upload shows bytes, speed, or chunk progress",
            "- app-switch return does not restart from 0",
            "- saved chunks / fast resume appears when retrying",
            "- Review says Analyzing, please wait while cloud is active",
            "1. Install this exact TestFlight build.",
            "2. In Settings, choose Fast Upload Mode on/off for this run and note it in proof.",
            "3. Import the long basketball video.",
            "4. Start AI Analysis and confirm Uploading -> Analyzing -> Review ready stays readable.",
            "5. Switch apps during upload, return, and confirm progress resumes instead of restarting.",
            "6. Copy upload proof after return; look for compact upload, chunk, saved, resume, or fast-lane wording.",
            "7. Open Review. If analysis is active, it must say Analyzing, please wait.",
            "8. Keep/Nah clips, undo once, scrub one clip, and tag one issue if needed.",
            "9. Make reel in AI Edit, preview it, request one revision, preview again.",
            "10. Share/open the finished reel.",
            "11. If anything crashes or feels frozen, copy smoke proof and upload proof.",
            "12. Before pasting proof, set Phone smoke result to Passed or Issue.",
            "privacy=no secrets, URLs, object keys, or local file paths"
        ].joined(separator: "\n")
    }

    private static func safeValue(_ value: String) -> String {
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
            "sourceobjectkey",
            "object_key",
            "presigned",
            "signature",
            "x-amz",
            "x-goog",
            "authorization",
            "file://",
            "/var/",
            "/users/"
        ]
        if forbiddenMarkers.contains(where: { lowercased.contains($0) }) {
            return "redacted"
        }

        return String(compact.prefix(120))
    }
}
