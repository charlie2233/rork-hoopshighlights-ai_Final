import SwiftUI
import UIKit

enum HoopsAccessibility {
    @MainActor
    static func announce(_ message: String) {
        guard UIAccessibility.isVoiceOverRunning, !message.isEmpty else { return }
        UIAccessibility.post(notification: .announcement, argument: message)
    }

    @MainActor
    static func animate(
        reduceMotion: Bool,
        _ animation: Animation = .snappy,
        updates: () -> Void
    ) {
        if reduceMotion {
            updates()
        } else {
            withAnimation(animation, updates)
        }
    }
}

extension View {
    @ViewBuilder
    func hoopsSelectedState(_ isSelected: Bool) -> some View {
        if isSelected {
            accessibilityAddTraits(.isSelected)
        } else {
            self
        }
    }
}
