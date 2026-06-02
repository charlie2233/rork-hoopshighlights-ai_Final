import Foundation

enum VideoImportStatusCopy {
    static let readingFromPhotos = "Reading from Photos..."
    static let checkingDetails = "Checking video details..."
    static let checkedSaving = "Checked. Saving to HoopClips..."
    static let copyingSource = "Copying video into HoopClips..."
    static let readingMetadata = "Reading video details..."
    static let generatingPreview = "Building project preview..."
    static let openingProject = "Opening project..."
    static let slowReminder = "Still saving. HoopClips keeps checking automatically."
    static let longRunningReminder = "Still saving. Check History if the video finished."
    static let statusDetail = "Keep HoopClips open while importing. Check History if it finished."
    static let historyActionTitle = "Check History"
    static let recoveryAlertTitle = "Check History"
    static let timeoutRecovery = "Still waiting. Check History if the video finished saving."
    static let savedButNotVisible = "Video saved. Check History if it is not here."
    static let defaultFailure = "Could not read that video. Try Files or another clip."
}
