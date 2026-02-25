import SwiftUI

enum AppTheme {
    static let accentPurple = Color(red: 0.486, green: 0.227, blue: 0.929)
    static let deepPurple = Color(red: 0.290, green: 0.078, blue: 0.549)
    static let darkBg = Color(red: 0.067, green: 0.027, blue: 0.118)
    static let cardBg = Color(red: 0.110, green: 0.055, blue: 0.180)
    static let surfaceBg = Color(red: 0.145, green: 0.075, blue: 0.230)
    static let neonPurple = Color(red: 0.651, green: 0.337, blue: 1.0)
    static let electricViolet = Color(red: 0.545, green: 0.208, blue: 0.957)
    static let subtleText = Color(white: 0.55)
    static let successGreen = Color(red: 0.298, green: 0.851, blue: 0.392)
    static let dangerRed = Color(red: 0.957, green: 0.263, blue: 0.345)
    static let warningYellow = Color(red: 1.0, green: 0.804, blue: 0.0)

    static let purpleGradient = LinearGradient(
        colors: [accentPurple, deepPurple],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    static let meshBackground = MeshGradient(
        width: 3, height: 3,
        points: [
            [0.0, 0.0], [0.5, 0.0], [1.0, 0.0],
            [0.0, 0.5], [0.5, 0.5], [1.0, 0.5],
            [0.0, 1.0], [0.5, 1.0], [1.0, 1.0]
        ],
        colors: [
            Color(red: 0.05, green: 0.01, blue: 0.10),
            Color(red: 0.15, green: 0.03, blue: 0.25),
            Color(red: 0.05, green: 0.01, blue: 0.10),
            Color(red: 0.10, green: 0.02, blue: 0.20),
            Color(red: 0.30, green: 0.08, blue: 0.50),
            Color(red: 0.10, green: 0.02, blue: 0.20),
            Color(red: 0.05, green: 0.01, blue: 0.10),
            Color(red: 0.15, green: 0.03, blue: 0.25),
            Color(red: 0.05, green: 0.01, blue: 0.10)
        ]
    )
}
