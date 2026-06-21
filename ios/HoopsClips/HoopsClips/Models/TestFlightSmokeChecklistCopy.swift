import Foundation

nonisolated enum TestFlightSmokeChecklistCopy {
    static let title = "HoopClips TestFlight Smoke Checklist"

    static func checklist(
        generatedAt: String,
        appVersion: String,
        build: String,
        environment: String,
        cloudLaunchMode: String
    ) -> String {
        [
            title,
            "generatedAt=\(safeValue(generatedAt))",
            "appVersion=\(safeValue(appVersion))",
            "build=\(safeValue(build))",
            "environment=\(safeValue(environment))",
            "cloudLaunchMode=\(safeValue(cloudLaunchMode))",
            "1. Install this exact TestFlight build.",
            "2. Import a long basketball video.",
            "3. Confirm Uploading -> Analyzing -> Review ready stays readable.",
            "4. Switch apps during upload, return, and copy build summary.",
            "5. Open Review. If analysis is active, it must say Analyzing, please wait.",
            "6. Keep/Nah clips, undo once, scrub one clip, and tag one issue if needed.",
            "7. Make reel in AI Edit, preview it, request one revision, preview again.",
            "8. Share/open the finished reel.",
            "9. If anything crashes or feels frozen, copy smoke proof and upload proof.",
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
