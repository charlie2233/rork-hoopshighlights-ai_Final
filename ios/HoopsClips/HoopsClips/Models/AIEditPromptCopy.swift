import Foundation

enum AIEditPromptCopy {
    static let title = "Tell HoopClips how to edit"
    static let heroSubtitle = "Tap Solo for one-player reels, or add a short focus like defense, recap, or 4:30 reel."
    static let placeholder = "Try: defense, NBA recap, 4:30 reel, more hype."
    static let quickFocusTitle = "Tap a focus"
    static let clearNoteTitle = "Clear note"
    static let accessibilityLabel = "AI Edit note"
    static let accessibilityHint = "Type a short editing focus. HoopClips uses it to shape the reel."
    static let clearNoteAccessibilityHint = "Clears the editing note without changing selected export options."
}

enum AIEditBackgroundJobCopy {
    static func reminder(for phase: CloudEditRenderState, hasCloudSource: Bool) -> String? {
        guard hasCloudSource else { return nil }

        switch phase {
        case .planning:
            return "Video is ready. Start AI Edit to hand off the cloud job; then you can switch apps."
        case .planReady:
            return "The reel plan is ready. Start it and come back for the finished video."
        case .renderRequested, .created, .queued, .rendering:
            return "cloud job is running. Safe to switch apps; reopen the app to refresh."
        case .rendered, .failed, .failedTimeout, .cancelled:
            return nil
        }
    }
}
