import Foundation

enum AIEditPromptCopy {
    static let title = "Tell HoopClips how to edit"
    static let heroSubtitle = "Add a short focus only when you want a specific style, like defense, recap, or 4:30 reel."
    static let placeholder = "Example: more hype, defense, NBA recap, 4:30 reel."
    static let quickFocusTitle = "Tap a focus"
    static let clearNoteTitle = "Clear note"
    static let accessibilityLabel = "AI Edit note"
    static let accessibilityHint = "Type a short editing focus. HoopClips sends the note to the cloud editor and validates it before rendering."
    static let clearNoteAccessibilityHint = "Clears the editing note without changing selected export options."
}

enum AIEditBackgroundJobCopy {
    static func reminder(for phase: CloudEditRenderState, hasCloudSource: Bool) -> String? {
        guard hasCloudSource else { return nil }

        switch phase {
        case .planning:
            return "Cloud source is ready. Start AI Edit to create the plan; after cloud render starts, you can switch apps."
        case .planReady:
            return "The plan is ready. Start cloud render and return later for the finished video."
        case .renderRequested, .created, .queued, .rendering:
            return "Safe to switch apps now. HoopClips keeps the cloud job running; return to refresh status."
        case .rendered, .failed, .failedTimeout, .cancelled:
            return nil
        }
    }
}
