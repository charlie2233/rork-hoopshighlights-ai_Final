import Foundation

nonisolated enum PlayerRecoveryDisplayPolicy {
    static let autoDismissDelayNanoseconds: UInt64 = 7 * 1_000_000_000
    static let proofSource = "HoopClips Player support note"

    static func shouldAutoDismiss(
        videoLoaded: Bool,
        importInProgress: Bool,
        analysisIsAnalyzing: Bool,
        clipCount: Int
    ) -> Bool {
        !videoLoaded
            && !importInProgress
            && !analysisIsAnalyzing
            && clipCount == 0
    }

    static func friendlyMessage(for summary: String) -> String {
        let lowercased = summary.lowercased()
        if lowercased.contains("analysis was active") || lowercased.contains("analyzing") {
            return "HoopClips closed while analysis was running. Stay on Player or reopen the app; Review waits until clips are ready."
        }
        if lowercased.contains("upload") || lowercased.contains("background") {
            return "HoopClips closed during upload/background work. Your upload proof is saved, and reopening refreshes progress."
        }
        if lowercased.contains("review") || lowercased.contains("no_reviewable_clips") {
            return "Review was safely blocked because clips were not ready yet. Stay on Player while analysis finishes, then open Review."
        }
        return "The last session ended before a normal close. HoopClips saved a short support note, then this card will hide automatically."
    }
}
