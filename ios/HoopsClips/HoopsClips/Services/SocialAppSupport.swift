import Foundation
import UIKit

struct SocialAppShortcut: Identifiable, Sendable, Equatable {
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

    func withInstallState(_ state: EditorAppInstallState) -> SocialAppShortcut {
        SocialAppShortcut(
            id: id,
            displayName: displayName,
            iconSystemName: iconSystemName,
            detectionScheme: detectionScheme,
            installState: state
        )
    }
}

enum SocialAppSupport {
    static let defaultShortcuts: [SocialAppShortcut] = [
        SocialAppShortcut(
            id: "instagram",
            displayName: "Instagram",
            iconSystemName: "camera.circle",
            detectionScheme: "instagram",
            installState: .unknown
        ),
        SocialAppShortcut(
            id: "tiktok",
            displayName: "TikTok",
            iconSystemName: "music.note.tv",
            detectionScheme: "tiktok",
            installState: .unknown
        ),
        SocialAppShortcut(
            id: "youtube",
            displayName: "YouTube",
            iconSystemName: "play.rectangle",
            detectionScheme: "youtube",
            installState: .unknown
        ),
    ]

    @MainActor
    static func resolvedShortcuts() -> [SocialAppShortcut] {
        defaultShortcuts.map(resolveInstallState)
    }

    @MainActor
    private static func resolveInstallState(for shortcut: SocialAppShortcut) -> SocialAppShortcut {
        guard let detectionScheme = shortcut.detectionScheme,
              let url = URL(string: "\(detectionScheme)://") else {
            return shortcut.withInstallState(.unknown)
        }

        let isInstalled = UIApplication.shared.canOpenURL(url)
        return shortcut.withInstallState(isInstalled ? .installed : .notInstalled)
    }
}
