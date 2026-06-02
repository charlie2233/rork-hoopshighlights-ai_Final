import Foundation

enum VideoImportStatusCopy {
    static let readingFromPhotos = "Reading video from Photos..."
    static let checkingDetails = "Checking video details..."
    static let checkedSaving = "Video checked. Saving to HoopClips..."
    static let copyingSource = "Copying video into HoopClips..."
    static let readingMetadata = "Reading video details..."
    static let generatingPreview = "Building project preview..."
    static let openingProject = "Opening project..."
    static let slowReminder = "Still saving. HoopClips keeps checking automatically."
    static let longRunningReminder = "Still saving. If iOS finished the copy, HoopClips will open it here."
    static let statusDetail = "Large videos can take a moment. HoopClips keeps checking and opens the project when ready."
    static let historyActionTitle = "Open History"
    static let recoveryAlertTitle = "Open from History"
    static let timeoutRecovery = "HoopClips is still waiting. If iOS finished the copy, open the project from History."
    static let savedButNotVisible = "HoopClips saved the video. Open it from History if it does not appear here."
    static let defaultFailure = "HoopClips could not read that video. Try importing it from Files or choose another clip."
}
