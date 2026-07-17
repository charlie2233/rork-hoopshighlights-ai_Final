import Foundation

enum VideoImportStatusCopy {
    static let readingFromPhotos = "Reading from Photos..."
    static let checkingDetails = "Checking video details..."
    static let checkedSaving = "Checks passed. Saving to HoopClips..."
    static let copyingSource = "Copying video into HoopClips..."
    static let readingMetadata = "Reading video details..."
    static let generatingPreview = "Building project preview..."
    static let openingProject = "Opening project..."
    static let slowReminder = "Still saving. HoopClips keeps checking in History."
    static let longRunningReminder = "Still saving. Open History to resume later."
    static let historyActionTitle = "Open History"
    static let historyActionHint = "Resume or watch the saved source."
    static let recoveryAlertTitle = "Open History"
    static let timeoutRecovery = "Import is taking too long. Open History to resume if it finished."
    static let savedButNotVisible = "Project saved. Open History to resume or watch source."
    static let defaultFailure = "Could not read that video. Try Files or a shorter clip."

    static func compactStage(for message: String, offersRecovery: Bool) -> String {
        if offersRecovery {
            return "Taking longer than usual"
        }

        let status = message.lowercased()
        if status.contains("photo") || status.contains("reading") {
            return "Reading video"
        }
        if status.contains("check") || status.contains("detail") || status.contains("limit") {
            return "Checking video"
        }
        if status.contains("copy") || status.contains("sav") || status.contains("large video") {
            return "Saving video"
        }
        if status.contains("preview") {
            return "Creating preview"
        }
        if status.contains("open") {
            return "Opening project"
        }
        return "Getting things ready"
    }
}
