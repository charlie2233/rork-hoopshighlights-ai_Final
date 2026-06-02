import Foundation

enum AIEditPromptCopy {
    static let title = "Tell HoopClips how to edit"
    static let heroSubtitle = "No note needed. Add one only for a focus like defense, NBA recap, or 4:30 reel."
    static let placeholder = "Example: more hype, defense, NBA recap, 4:30 reel."
    static let quickFocusTitle = "Tap a focus"
    static let accessibilityLabel = "AI Edit note"
    static let accessibilityHint = "Type a short editing focus. The cloud editor validates the note before rendering."
}

enum AIEditBackgroundJobCopy {
    static func reminder(for phase: CloudEditRenderState, hasCloudSource: Bool) -> String? {
        guard hasCloudSource else { return nil }

        switch phase {
        case .planning:
            return "Once you start AI Edit, you can switch apps while HoopClips works in the cloud."
        case .planReady:
            return "The plan is ready. After render starts, you can switch apps and come back for the finished video."
        case .renderRequested, .created, .queued, .rendering:
            return "Safe to switch apps now. HoopClips keeps the cloud job running; reopen the app to see the latest status."
        case .rendered, .failed, .failedTimeout, .cancelled:
            return nil
        }
    }
}
