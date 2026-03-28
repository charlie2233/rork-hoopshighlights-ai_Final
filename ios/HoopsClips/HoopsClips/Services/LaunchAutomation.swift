import Foundation

enum LaunchAutomation {
    private static let environment = ProcessInfo.processInfo.environment

    static var isEnabled: Bool {
        environment["HOOPS_AUTOMATION_ENABLED"] == "1"
    }

    static var shouldSignInAnonymously: Bool {
        isEnabled && environment["HOOPS_AUTOMATION_AUTH_MODE"]?.lowercased() == "guest"
    }

    static var sampleVideoURL: URL? {
        guard isEnabled,
              let path = environment["HOOPS_AUTOMATION_SAMPLE_VIDEO_PATH"],
              !path.isEmpty else {
            return nil
        }

        return URL(fileURLWithPath: path)
    }

    static var shouldAutoAnalyze: Bool {
        isEnabled && environment["HOOPS_AUTOMATION_AUTO_ANALYZE"] == "1"
    }
}
