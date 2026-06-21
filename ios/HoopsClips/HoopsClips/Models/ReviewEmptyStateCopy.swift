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
                message: "Go to Player, import a video, then tap Get Highlights. Clips will show here ready to keep or skip.",
                icon: "film.stack.fill"
            )
        }

        let title = isUploading(isVideoImportInProgress: isVideoImportInProgress, statusMessage: statusMessage)
            ? "Uploading video"
            : "Finding highlights"
        let progressText = progressLabel(for: progress).map { " \($0) done." } ?? ""
        let statusText = sanitizedStatusMessage(statusMessage).map { " Now: \($0)" } ?? ""
        return ReviewEmptyStateContent(
            title: title,
            message: "Please wait. Review opens automatically when clips are ready.\(progressText)\(statusText)",
            icon: "brain.head.profile.fill"
        )
    }

    private static func isUploading(isVideoImportInProgress: Bool, statusMessage: String) -> Bool {
        let status = statusMessage.lowercased()
        return isVideoImportInProgress || status.contains("upload")
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
        let firstStatus = status
            .components(separatedBy: " · ")
            .first?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? status
        let compactStatus = String(firstStatus.prefix(72)).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !compactStatus.isEmpty else { return nil }
        return compactStatus.hasSuffix(".") ? compactStatus : "\(compactStatus)."
    }
}
