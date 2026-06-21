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
