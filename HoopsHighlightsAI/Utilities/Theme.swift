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
    static let cardBorder = accentPurple.opacity(0.18)
    static let softBorder = Color.white.opacity(0.06)

    static let purpleGradient = LinearGradient(
        colors: [accentPurple, deepPurple],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    static let cardGradient = LinearGradient(
        colors: [surfaceBg.opacity(0.9), cardBg],
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

extension View {
    func rorkCard(
        cornerRadius: CGFloat = 16,
        fill: AnyShapeStyle = AnyShapeStyle(AppTheme.cardGradient),
        stroke: Color = AppTheme.cardBorder,
        glow: Color = AppTheme.neonPurple,
        glowOpacity: Double = 0.12
    ) -> some View {
        self
            .background(
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .fill(fill)
                    .shadow(color: glow.opacity(glowOpacity), radius: 18, x: 0, y: 10)
            )
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .stroke(stroke, lineWidth: 1)
            )
            .overlay(alignment: .topLeading) {
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .fill(
                        LinearGradient(
                            colors: [Color.white.opacity(0.06), .clear],
                            startPoint: .topLeading,
                            endPoint: .center
                        )
                    )
                    .blendMode(.screen)
                    .allowsHitTesting(false)
            }
    }
}

struct RorkSectionHeader: View {
    let title: String
    let icon: String
    var subtitle: String?

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(AppTheme.accentPurple.opacity(0.15))
                    .frame(width: 34, height: 34)
                Image(systemName: icon)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(AppTheme.neonPurple)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline)
                    .foregroundStyle(.white)
                if let subtitle {
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(AppTheme.subtleText)
                }
            }

            Spacer(minLength: 0)
        }
    }
}

struct RorkMetricChip: View {
    let icon: String
    let value: String
    let label: String
    var tint: Color = AppTheme.neonPurple

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.caption.weight(.semibold))
                .foregroundStyle(tint)
                .frame(width: 18)

            VStack(alignment: .leading, spacing: 2) {
                Text(value)
                    .font(.caption.bold().monospacedDigit())
                    .foregroundStyle(.white)
                Text(label)
                    .font(.caption2)
                    .foregroundStyle(AppTheme.subtleText)
            }

            Spacer(minLength: 0)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(AppTheme.surfaceBg.opacity(0.75), in: Capsule())
        .overlay(
            Capsule()
                .stroke(AppTheme.softBorder, lineWidth: 1)
        )
    }
}
