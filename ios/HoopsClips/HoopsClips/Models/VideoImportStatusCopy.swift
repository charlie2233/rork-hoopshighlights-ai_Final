import Foundation

enum VideoImportStatusCopy {
    static let readingFromPhotos = "Reading from Photos..."
    static let checkingDetails = "Checking video details..."
    static let checkedSaving = "Checks passed. Saving to HoopClips..."
    static let copyingSource = "Copying video into HoopClips..."
    static let readingMetadata = "Reading video details..."
    static let generatingPreview = "Building project preview..."
    static let openingProject = "Opening project..."
    static let slowReminder = "Still saving. Keep HoopClips open while the source is copied."
    static let longRunningReminder = "Still saving. Check History if this screen closes."
    static let statusDetail = "Keep HoopClips open while saving. Check History if this takes longer."
    static let historyActionTitle = "Check History"
    static let recoveryAlertTitle = "Check History"
    static let timeoutRecovery = "Import is taking too long. Check History if it finished while this screen was open."
    static let savedButNotVisible = "Project saved. Check History if the source is not shown here."
    static let defaultFailure = "Could not read that video. Try Files or a shorter clip."
}
