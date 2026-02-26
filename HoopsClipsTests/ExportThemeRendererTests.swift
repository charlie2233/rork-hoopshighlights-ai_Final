import Testing
import CoreGraphics
@testable import HoopsClips

struct ExportThemeRendererTests {
    @Test
    func themeProfilesExistForAllThemes() {
        #expect(ExportTheme.allCases.count == 6)

        for theme in ExportTheme.allCases {
            let profile = theme.profile
            #expect(profile.labelStyle.displayDuration > 0)
            #expect(profile.contrast > 0)
        }
    }

    @Test
    func timelineSegmentsAreContiguousAndSummed() {
        let clips = [
            Clip(startTime: 4, endTime: 6, confidence: 0.91, label: "Dunk"),
            Clip(startTime: 1, endTime: 2.5, confidence: 0.55, label: "Layup"),
            Clip(startTime: -2, endTime: 0.5, confidence: 0.62, label: "Steal"),
            Clip(startTime: 9.5, endTime: 15.0, confidence: 0.42, label: "Three"),
            Clip(startTime: 8.0, endTime: 8.0, confidence: 0.3, label: "Invalid")
        ]

        let segments = buildTimelineSegments(from: clips, assetDuration: 10)
        #expect(segments.count == 4)

        for index in 1..<segments.count {
            #expect(isApproximatelyEqual(segments[index].outputStartTime, segments[index - 1].outputEndTime))
        }

        let sourceDurationSum = segments.reduce(0.0) { $0 + ($1.sourceEndTime - $1.sourceStartTime) }
        let outputDurationSum = segments.reduce(0.0) { $0 + ($1.outputEndTime - $1.outputStartTime) }

        #expect(isApproximatelyEqual(sourceDurationSum, outputDurationSum))
        #expect(isApproximatelyEqual(outputDurationSum, segments.last?.outputEndTime ?? 0))

        // Final segment is clamped from 9.5...15.0 to 9.5...10.0
        #expect(isApproximatelyEqual(segments.last?.sourceStartTime ?? 0, 9.5))
        #expect(isApproximatelyEqual(segments.last?.sourceEndTime ?? 0, 10.0))
    }

    @Test
    func labelVisibilityAlphaMatchesFadeCurve() {
        let duration = 0.9
        #expect(isApproximatelyEqual(labelVisibilityAlpha(at: -0.1, displayDuration: duration), 0))
        #expect(isApproximatelyEqual(labelVisibilityAlpha(at: 0.0, displayDuration: duration), 0))
        #expect(labelVisibilityAlpha(at: 0.05, displayDuration: duration) > 0.45)
        #expect(isApproximatelyEqual(labelVisibilityAlpha(at: 0.2, displayDuration: duration), 1.0))
        #expect(labelVisibilityAlpha(at: 0.85, displayDuration: duration) < 0.4)
        #expect(isApproximatelyEqual(labelVisibilityAlpha(at: 1.0, displayDuration: duration), 0))
    }

    @Test
    func renderGeometryPreservesAspectRatioForPortraitTransform() {
        let naturalSize = CGSize(width: 1920, height: 1080)
        let portraitTransform = CGAffineTransform(a: 0, b: 1, c: -1, d: 0, tx: 1080, ty: 0)

        let geometry = makeRenderGeometry(
            naturalSize: naturalSize,
            preferredTransform: portraitTransform,
            quality: .standard
        )

        #expect(geometry.renderSize.height > geometry.renderSize.width)
        #expect(geometry.longestEdge <= 1280)

        let ratio = geometry.renderSize.width / geometry.renderSize.height
        let expectedRatio = 1080.0 / 1920.0
        #expect(abs(ratio - expectedRatio) < 0.02)
    }
}

private func isApproximatelyEqual(_ lhs: Double, _ rhs: Double, tolerance: Double = 0.0001) -> Bool {
    abs(lhs - rhs) <= tolerance
}
