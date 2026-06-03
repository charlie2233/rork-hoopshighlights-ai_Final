import Foundation

enum VideoImportStatusCopy {
    static let readingFromPhotos = "Reading from Photos..."
    static let checkingDetails = "Checking video details..."
    static let checkedSaving = "Checks passed. Saving to HoopClips..."
    static let copyingSource = "Copying video into HoopClips..."
    static let readingMetadata = "Reading video details..."
    static let generatingPreview = "Building project preview..."
    static let openingProject = "Opening project..."
    static let slowReminder = "Still saving. HoopClips is updating automatically."
    static let longRunningReminder = "Still saving. Open History to confirm progress."
    static let statusDetail = "Import stays active in HoopClips. Open History if this takes longer."
    static let historyActionTitle = "View History"
    static let recoveryAlertTitle = "View History"
    static let timeoutRecovery = "Import is taking too long. Open History if it finished while this screen was open."
    static let savedButNotVisible = "Project saved. Open History if the source is not shown here."
    static let defaultFailure = "Could not read that video. Try Files or a shorter clip."
}
