import Foundation

nonisolated struct ReviewEmptyStateContent: Equatable, Sendable {
    let title: String
    let message: String
    let icon: String
}

nonisolated enum ReviewEmptyStateCopy {
    static func content(
        isVideoImportInProgress: Bool,
        isAnalyzing: Bool,
        progress: Double,
        statusMessage: String
    ) -> ReviewEmptyStateContent {
        let isWaitingForReviewClips = isVideoImportInProgress || isAnalyzing
        guard isWaitingForReviewClips else {
            return ReviewEmptyStateContent(
                title: "Review opens after analysis",
                message: "Go to Player, import a video, then tap AI Analysis. Your best plays will show here ready to keep or skip.",
                icon: "film.stack.fill"
            )
        }

        let progressText = progressLabel(for: progress).map { " \($0) done." } ?? ""
        let sanitizedStatus = sanitizedStatusMessage(statusMessage)
        let statusText = sanitizedStatus.map { " \($0)" } ?? ""
        return ReviewEmptyStateContent(
            title: "Analyzing, please wait",
            message: "HoopClips is \(workLabel(isVideoImportInProgress: isVideoImportInProgress, statusMessage: statusMessage)).\(progressText)\(statusText) Review opens automatically when clips are ready.",
            icon: "brain.head.profile.fill"
        )
    }

    private static func workLabel(isVideoImportInProgress: Bool, statusMessage: String) -> String {
        let status = statusMessage.lowercased()
        if isVideoImportInProgress || status.contains("upload") {
            return "uploading your video"
        }
        return "scanning your video"
    }

    private static func progressLabel(for progress: Double) -> String? {
        guard progress.isFinite, progress > 0 else { return nil }
        let percent = Int((min(max(progress, 0), 1) * 100).rounded(.down))
        guard percent > 0 else { return nil }
        return "\(percent)%"
    }

    private static func sanitizedStatusMessage(_ statusMessage: String) -> String? {
        let status = statusMessage.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !status.isEmpty else { return nil }
        return status.hasSuffix(".") ? status : "\(status)."
    }
}
