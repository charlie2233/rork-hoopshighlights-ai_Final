import Foundation
import UIKit

enum EditorAppInstallState: Sendable, Equatable {
    case installed
    case notInstalled
    case unknown
}

struct EditorAppShortcut: Identifiable, Sendable, Equatable {
    let id: String
    let displayName: String
    let iconSystemName: String
    let detectionScheme: String?
    let installState: EditorAppInstallState

    var isInstalled: Bool {
        installState == .installed
    }

    var statusText: String {
        switch installState {
        case .installed:
            return "Installed"
        case .notInstalled:
            return "Open share sheet"
        case .unknown:
            return "Share to continue"
        }
    }

    func withInstallState(_ state: EditorAppInstallState) -> EditorAppShortcut {
        EditorAppShortcut(
            id: id,
            displayName: displayName,
            iconSystemName: iconSystemName,
            detectionScheme: detectionScheme,
            installState: state
        )
    }
}

enum EditorAppSupport {
    static let defaultShortcuts: [EditorAppShortcut] = [
        EditorAppShortcut(
            id: "adobe",
            displayName: "Adobe",
            iconSystemName: "sparkles.tv",
            detectionScheme: nil,
            installState: .unknown
        ),
        EditorAppShortcut(
            id: "capcut",
            displayName: "CapCut",
            iconSystemName: "scissors",
            detectionScheme: "capcut",
            installState: .unknown
        ),
        EditorAppShortcut(
            id: "imovie",
            displayName: "iMovie",
            iconSystemName: "film",
            detectionScheme: "imovie",
            installState: .unknown
        ),
    ]

    @MainActor
    static func resolvedShortcuts() -> [EditorAppShortcut] {
        defaultShortcuts.map(resolveInstallState)
    }

    @MainActor
    private static func resolveInstallState(for shortcut: EditorAppShortcut) -> EditorAppShortcut {
        guard let detectionScheme = shortcut.detectionScheme,
              let url = URL(string: "\(detectionScheme)://") else {
            return shortcut.withInstallState(.unknown)
        }

        let isInstalled = UIApplication.shared.canOpenURL(url)
        return shortcut.withInstallState(isInstalled ? .installed : .notInstalled)
    }
}
