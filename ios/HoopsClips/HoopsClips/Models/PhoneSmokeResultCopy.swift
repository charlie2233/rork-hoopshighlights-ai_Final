import Foundation

nonisolated enum PhoneSmokeResultStatus: String, CaseIterable, Identifiable, Sendable {
    case notRun = "not_run"
    case passed = "passed"
    case issue = "issue"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .notRun:
            return "Not run"
        case .passed:
            return "Passed"
        case .issue:
            return "Issue"
        }
    }

    var icon: String {
        switch self {
        case .notRun:
            return "circle"
        case .passed:
            return "checkmark.circle.fill"
        case .issue:
            return "exclamationmark.triangle.fill"
        }
    }
}

nonisolated enum PhoneSmokeIssueNoteCopy {
    static func sanitized(_ value: String, enabled: Bool = true) -> String {
        guard enabled else { return "none" }

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

        return String(compact.prefix(160))
    }
}
