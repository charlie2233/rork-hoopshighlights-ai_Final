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
    static let statusDetail = "Keep HoopClips open while saving. Open History to resume."
    static let historyActionTitle = "Open History"
    static let historyActionHint = "Resume or watch the saved source."
    static let recoveryAlertTitle = "Open History"
    static let timeoutRecovery = "Import is taking too long. Open History to resume if it finished."
    static let savedButNotVisible = "Project saved. Open History to resume or watch source."
    static let defaultFailure = "Could not read that video. Try Files or a shorter clip."
}
