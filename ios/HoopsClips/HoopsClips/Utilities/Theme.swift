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

struct HoopsMotionBackdrop: View {
    var glowOpacity: Double = 0.24
    var courtOpacity: Double = 0.10

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 24.0)) { timeline in
            let time = timeline.date.timeIntervalSinceReferenceDate
            let leadX = CGFloat(sin(time * 0.22)) * 54
            let leadY = CGFloat(cos(time * 0.18)) * 42
            let trailX = CGFloat(cos(time * 0.16)) * 48
            let trailY = CGFloat(sin(time * 0.20)) * 38
            let shimmer = (sin(time * 0.7) + 1.0) / 2.0

            ZStack {
                AppTheme.darkBg

                AppTheme.meshBackground
                    .opacity(0.18 + shimmer * 0.04)

                Circle()
                    .fill(AppTheme.neonPurple.opacity(glowOpacity))
                    .frame(width: 220, height: 220)
                    .blur(radius: 58)
                    .offset(x: -120 + leadX, y: -275 + leadY)

                Circle()
                    .fill(AppTheme.warningYellow.opacity(glowOpacity * 0.34))
                    .frame(width: 180, height: 180)
                    .blur(radius: 62)
                    .offset(x: 150 + trailX, y: 80 + trailY)

                Circle()
                    .stroke(AppTheme.neonPurple.opacity(courtOpacity), lineWidth: 1)
                    .frame(width: 360, height: 360)
                    .offset(x: -170 + trailX * 0.35, y: 210 + leadY * 0.25)

                VStack(spacing: 54) {
                    ForEach(0..<5, id: \.self) { index in
                        RoundedRectangle(cornerRadius: 999, style: .continuous)
                            .fill(Color.white.opacity(courtOpacity * 0.42))
                            .frame(width: 270, height: 1)
                            .rotationEffect(.degrees(-18))
                            .offset(x: CGFloat(index - 2) * 34 + leadX * 0.06)
                    }
                }
                .offset(y: -10 + trailY * 0.08)
            }
            .ignoresSafeArea()
            .allowsHitTesting(false)
            .accessibilityHidden(true)
        }
    }
}

struct HoopsMotionHero: View {
    var icon: String = "basketball.fill"
    var size: CGFloat = 240
    var accent: Color = AppTheme.neonPurple
    var secondary: Color = AppTheme.warningYellow

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30.0)) { timeline in
            let time = timeline.date.timeIntervalSinceReferenceDate
            let nearRingX = CGFloat(sin(time * 0.92)) * size * 0.058
            let nearRingY = CGFloat(cos(time * 0.78)) * size * 0.042
            let farRingX = CGFloat(cos(time * 0.54)) * size * 0.083
            let farRingY = CGFloat(sin(time * 0.68)) * size * 0.067
            let iconLift = CGFloat(sin(time * 1.8)) * size * 0.021
            let shimmer = CGFloat((sin(time * 1.4) + 1.0) / 2.0)

            ZStack {
                RadialGradient(
                    colors: [
                        accent.opacity(0.28),
                        AppTheme.accentPurple.opacity(0.08),
                        .clear
                    ],
                    center: .center,
                    startRadius: 8,
                    endRadius: size * 0.49
                )
                .frame(width: size * 0.98, height: size * 0.98)
                .blur(radius: 10)
                .scaleEffect(0.96 + shimmer * 0.08)

                Circle()
                    .stroke(
                        AngularGradient(
                            colors: [
                                accent.opacity(0.05),
                                accent.opacity(0.44),
                                secondary.opacity(0.26),
                                accent.opacity(0.05)
                            ],
                            center: .center
                        ),
                        style: StrokeStyle(lineWidth: 7, lineCap: .round, dash: [34, 18])
                    )
                    .frame(width: size * 0.74, height: size * 0.74)
                    .rotationEffect(.degrees(time * 22))
                    .offset(x: farRingX, y: farRingY)
                    .blur(radius: 0.2)

                Circle()
                    .stroke(
                        LinearGradient(
                            colors: [
                                AppTheme.accentPurple.opacity(0.08),
                                accent.opacity(0.48),
                                AppTheme.accentPurple.opacity(0.12)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        style: StrokeStyle(lineWidth: 4, lineCap: .round, dash: [18, 11])
                    )
                    .frame(width: size * 0.58, height: size * 0.58)
                    .rotationEffect(.degrees(-time * 34))
                    .offset(x: nearRingX, y: nearRingY)

                RoundedRectangle(cornerRadius: 26, style: .continuous)
                    .stroke(AppTheme.softBorder.opacity(0.7), lineWidth: 1)
                    .frame(width: size * 0.72, height: size * 0.49)
                    .rotationEffect(.degrees(-8 + sin(time * 0.55) * 2))
                    .offset(y: size * 0.033)

                heroSpark(size: size * 0.033, opacity: 0.75, x: -size * 0.325 + CGFloat(sin(time * 1.6)) * 7, y: -size * 0.208 + CGFloat(cos(time * 1.2)) * 6)
                heroSpark(size: size * 0.021, opacity: 0.58, x: size * 0.325 + CGFloat(cos(time * 1.4)) * 8, y: -size * 0.117 + CGFloat(sin(time * 1.1)) * 7)
                heroSpark(size: size * 0.025, opacity: 0.50, x: -size * 0.233 + CGFloat(cos(time * 1.15)) * 7, y: size * 0.275 + CGFloat(sin(time * 1.5)) * 6)

                ZStack {
                    Circle()
                        .fill(.white.opacity(0.08))
                        .frame(width: size * 0.43, height: size * 0.43)
                        .overlay(
                            Circle()
                                .stroke(accent.opacity(0.36), lineWidth: 1)
                        )
                        .shadow(color: accent.opacity(0.45), radius: 18, x: 0, y: 0)

                    Image(systemName: icon)
                        .font(.system(size: size * 0.267, weight: .bold))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [secondary, accent],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .rotationEffect(.degrees(sin(time * 0.9) * 5))
                        .symbolEffect(.bounce, options: .repeating.speed(0.26), value: Int(time))
                }
                .offset(y: iconLift)
            }
            .frame(width: size, height: size * 0.875)
            .accessibilityHidden(true)
        }
    }

    private func heroSpark(size: CGFloat, opacity: Double, x: CGFloat, y: CGFloat) -> some View {
        Circle()
            .fill(secondary.opacity(opacity))
            .frame(width: size, height: size)
            .shadow(color: secondary.opacity(0.45), radius: 8, x: 0, y: 0)
            .offset(x: x, y: y)
    }
}

struct HoopsEmptyStateCard: View {
    let title: String
    let message: String
    var icon: String = "basketball.fill"
    var actionTitle: String?
    var action: (() -> Void)?

    var body: some View {
        VStack(spacing: 18) {
            HoopsMotionHero(icon: icon, size: 188)

            VStack(spacing: 8) {
                Text(title)
                    .font(.title3.bold())
                    .foregroundStyle(.white)
                    .multilineTextAlignment(.center)

                Text(message)
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.subtleText)
                    .multilineTextAlignment(.center)
                    .lineSpacing(3)
            }

            if let actionTitle, let action {
                Button(action: action) {
                    Text(actionTitle)
                        .font(.headline)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(AppTheme.purpleGradient, in: .rect(cornerRadius: 14))
                        .overlay(
                            RoundedRectangle(cornerRadius: 14, style: .continuous)
                                .stroke(AppTheme.neonPurple.opacity(0.28), lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .rorkCard(cornerRadius: 22, stroke: AppTheme.softBorder, glowOpacity: 0.12)
        .padding(.horizontal, 16)
    }
}
