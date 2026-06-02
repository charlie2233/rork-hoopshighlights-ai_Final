import Foundation

nonisolated enum ReviewProgressCopy {
    static let title = "Selected clips"

    static func summary(selectedCount: Int, totalCount: Int, needsCheckCount: Int) -> String {
        let safeSelectedCount = max(0, selectedCount)
        let safeTotalCount = max(0, totalCount)
        let safeNeedsCheckCount = max(0, needsCheckCount)
        let base = "\(safeSelectedCount)/\(safeTotalCount) selected"
        guard safeNeedsCheckCount > 0 else { return base }
        return "\(base), \(safeNeedsCheckCount) to check"
    }

    static func accessibilityValue(selectedCount: Int, totalCount: Int, needsCheckCount: Int) -> String {
        let safeSelectedCount = max(0, selectedCount)
        let safeTotalCount = max(0, totalCount)
        let safeNeedsCheckCount = max(0, needsCheckCount)
        let selectedNoun = safeSelectedCount == 1 ? "clip" : "clips"
        let totalNoun = safeTotalCount == 1 ? "clip" : "clips"
        var parts = [
            "\(safeSelectedCount) \(selectedNoun) selected for edit out of \(safeTotalCount) \(totalNoun)."
        ]
        if safeNeedsCheckCount > 0 {
            let checkNoun = safeNeedsCheckCount == 1 ? "clip" : "clips"
            let checkVerb = safeNeedsCheckCount == 1 ? "needs" : "need"
            parts.append("\(safeNeedsCheckCount) \(checkNoun) \(checkVerb) a closer check.")
        }
        return parts.joined(separator: " ")
    }
}
