import Foundation
import AVFoundation
import CoreImage
import CoreImage.CIFilterBuiltins
import UIKit

internal struct ExportTimelineSegment: Sendable, Equatable {
    let outputStartTime: Double
    let outputEndTime: Double
    let sourceStartTime: Double
    let sourceEndTime: Double
    let clipID: UUID
    let clipLabel: String
    let clipConfidence: Double
    let clipAction: HighlightAction

    var outputDuration: Double { outputEndTime - outputStartTime }
    var sourceDuration: Double { sourceEndTime - sourceStartTime }

    var labelText: String {
        let confidencePercent = Int((clipConfidence * 100).rounded())
        return "\(clipLabel) • \(confidencePercent)%"
    }

    func contains(outputTime: Double) -> Bool {
        if outputTime == outputEndTime {
            return true
        }
        return outputTime >= outputStartTime && outputTime < outputEndTime
    }

    func sourceTimeRange(timescale: CMTimeScale = 600) -> CMTimeRange {
        CMTimeRange(
            start: CMTime(seconds: sourceStartTime, preferredTimescale: timescale),
            end: CMTime(seconds: sourceEndTime, preferredTimescale: timescale)
        )
    }
}

internal func buildTimelineSegments(from clips: [Clip], assetDuration: Double) -> [ExportTimelineSegment] {
    guard assetDuration > 0 else { return [] }

    var outputCursor = 0.0
    var segments: [ExportTimelineSegment] = []

    for clip in clips.sorted(by: { $0.startTime < $1.startTime }) {
        let clampedStart = min(max(clip.startTime, 0), assetDuration)
        let clampedEnd = min(max(clip.endTime, 0), assetDuration)
        guard clampedEnd > clampedStart else { continue }

        let duration = clampedEnd - clampedStart
        let segment = ExportTimelineSegment(
            outputStartTime: outputCursor,
            outputEndTime: outputCursor + duration,
            sourceStartTime: clampedStart,
            sourceEndTime: clampedEnd,
            clipID: clip.id,
            clipLabel: clip.label,
            clipConfidence: clip.confidence,
            clipAction: clip.action
        )
        segments.append(segment)
        outputCursor += duration
    }

    return segments
}

internal struct ExportRenderGeometry: Sendable, Equatable {
    let renderSize: CGSize
    let renderExtent: CGRect
    let longestEdge: CGFloat
    let scaleBucket: Int
}

internal func makeRenderGeometry(
    naturalSize: CGSize,
    preferredTransform: CGAffineTransform,
    quality: ExportQuality
) -> ExportRenderGeometry {
    let transformedRect = CGRect(origin: .zero, size: naturalSize).applying(preferredTransform)
    let orientedSize = CGSize(
        width: max(abs(transformedRect.width), 1),
        height: max(abs(transformedRect.height), 1)
    )

    let longestSourceEdge = max(orientedSize.width, orientedSize.height)
    let maxEdge: CGFloat = switch quality {
    case .standard: 1280
    case .high: 1920
    case .ultra: min(max(longestSourceEdge, 1), 3840)
    }

    let scale = min(1.0, maxEdge / max(longestSourceEdge, 1))
    let scaledWidth = max(2, round(orientedSize.width * scale))
    let scaledHeight = max(2, round(orientedSize.height * scale))

    let evenWidth = scaledWidth.truncatingRemainder(dividingBy: 2) == 0 ? scaledWidth : scaledWidth + 1
    let evenHeight = scaledHeight.truncatingRemainder(dividingBy: 2) == 0 ? scaledHeight : scaledHeight + 1
    let renderSize = CGSize(width: evenWidth, height: evenHeight)
    let longestRenderEdge = max(renderSize.width, renderSize.height)
    let scaleBucket: Int = switch longestRenderEdge {
    case ..<1000: 720
    case ..<2600: 1080
    default: 2160
    }

    return ExportRenderGeometry(
        renderSize: renderSize,
        renderExtent: CGRect(origin: .zero, size: renderSize),
        longestEdge: longestRenderEdge,
        scaleBucket: scaleBucket
    )
}

internal func labelVisibilityAlpha(at elapsed: Double, displayDuration: Double) -> Double {
    guard displayDuration > 0, elapsed >= 0, elapsed <= displayDuration else { return 0 }

    let fadeIn = min(0.10, displayDuration * 0.45)
    let fadeOut = min(0.18, max(displayDuration - fadeIn, 0))
    let holdEnd = max(displayDuration - fadeOut, fadeIn)

    if fadeIn > 0, elapsed < fadeIn {
        return min(max(elapsed / fadeIn, 0), 1)
    }

    if elapsed <= holdEnd {
        return 1
    }

    if fadeOut <= 0 { return 0 }
    let remaining = displayDuration - elapsed
    return min(max(remaining / fadeOut, 0), 1)
}

internal struct ThemeOverlayFrameContext: Sendable {
    let compositionTime: Double
    let localClipTime: Double
    let segment: ExportTimelineSegment
    let imageExtent: CGRect
}

internal struct ExportThemeProfile: Sendable {
    struct GradientOverlay: Sendable {
        let startColor: SIMD4<Double>
        let endColor: SIMD4<Double>
        let opacity: Double
        let startPoint: CGPoint
        let endPoint: CGPoint
    }

    struct LetterboxStyle: Sendable {
        let barHeightRatio: Double
        let color: SIMD4<Double>
        let opacity: Double
    }

    struct EdgeGlowStyle: Sendable {
        let edgeIntensity: Double
        let bloomRadius: Double
        let bloomIntensity: Double
        let tintColor: SIMD4<Double>
        let opacity: Double
    }

    struct ClipStartFlashStyle: Sendable {
        let duration: Double
        let color: SIMD4<Double>
        let maxOpacity: Double
    }

    struct LabelStyle: Sendable {
        let backgroundColor: SIMD4<Double>
        let borderColor: SIMD4<Double>
        let textColor: SIMD4<Double>
        let shadowColor: SIMD4<Double>?
        let cornerRadius: CGFloat
        let horizontalPadding: CGFloat
        let verticalPadding: CGFloat
        let borderWidth: CGFloat
        let displayDuration: Double
        let topPlacement: Bool
        let margin: CGFloat
        let fixedOpacityMultiplier: Double
    }

    let saturation: Double
    let contrast: Double
    let brightness: Double
    let exposureEV: Double
    let vignetteIntensity: Double
    let vignetteRadius: Double
    let tintOverlay: SIMD4<Double>?
    let tintOpacity: Double
    let gradientOverlay: GradientOverlay?
    let letterboxStyle: LetterboxStyle?
    let edgeGlowStyle: EdgeGlowStyle?
    let labelStyle: LabelStyle
    let clipStartFlashStyle: ClipStartFlashStyle?
}

internal extension ExportTheme {
    var profile: ExportThemeProfile {
        func rgba(_ r: Double, _ g: Double, _ b: Double, _ a: Double = 1) -> SIMD4<Double> {
            .init(r, g, b, a)
        }

        let classicLabel = ExportThemeProfile.LabelStyle(
            backgroundColor: rgba(0.06, 0.05, 0.10, 0.76),
            borderColor: rgba(1.0, 1.0, 1.0, 0.14),
            textColor: rgba(1.0, 1.0, 1.0, 0.95),
            shadowColor: rgba(0.0, 0.0, 0.0, 0.22),
            cornerRadius: 12,
            horizontalPadding: 12,
            verticalPadding: 7,
            borderWidth: 1,
            displayDuration: 0.9,
            topPlacement: false,
            margin: 18,
            fixedOpacityMultiplier: 1.0
        )

        switch self {
        case .classic:
            return ExportThemeProfile(
                saturation: 1.08,
                contrast: 1.04,
                brightness: 0.01,
                exposureEV: 0.03,
                vignetteIntensity: 0.12,
                vignetteRadius: 1.0,
                tintOverlay: rgba(1.0, 0.94, 0.86, 1),
                tintOpacity: 0.04,
                gradientOverlay: nil,
                letterboxStyle: nil,
                edgeGlowStyle: nil,
                labelStyle: classicLabel,
                clipStartFlashStyle: nil
            )

        case .vibrant:
            return ExportThemeProfile(
                saturation: 1.28,
                contrast: 1.12,
                brightness: 0.01,
                exposureEV: 0.08,
                vignetteIntensity: 0.08,
                vignetteRadius: 1.2,
                tintOverlay: nil,
                tintOpacity: 0,
                gradientOverlay: .init(
                    startColor: rgba(0.00, 0.75, 0.72, 1),
                    endColor: rgba(1.00, 0.54, 0.18, 1),
                    opacity: 0.09,
                    startPoint: CGPoint(x: 0, y: 1),
                    endPoint: CGPoint(x: 1, y: 0)
                ),
                letterboxStyle: nil,
                edgeGlowStyle: nil,
                labelStyle: .init(
                    backgroundColor: rgba(0.05, 0.07, 0.12, 0.72),
                    borderColor: rgba(1.0, 0.82, 0.55, 0.24),
                    textColor: rgba(1.0, 1.0, 1.0, 0.98),
                    shadowColor: rgba(0.0, 0.0, 0.0, 0.22),
                    cornerRadius: 12,
                    horizontalPadding: 12,
                    verticalPadding: 7,
                    borderWidth: 1,
                    displayDuration: 0.9,
                    topPlacement: false,
                    margin: 18,
                    fixedOpacityMultiplier: 1.0
                ),
                clipStartFlashStyle: nil
            )

        case .neon:
            return ExportThemeProfile(
                saturation: 1.20,
                contrast: 1.20,
                brightness: -0.02,
                exposureEV: -0.02,
                vignetteIntensity: 0.20,
                vignetteRadius: 1.1,
                tintOverlay: rgba(0.46, 0.14, 0.95, 1),
                tintOpacity: 0.08,
                gradientOverlay: .init(
                    startColor: rgba(0.11, 0.58, 1.0, 1),
                    endColor: rgba(0.64, 0.22, 1.0, 1),
                    opacity: 0.06,
                    startPoint: CGPoint(x: 0, y: 0.5),
                    endPoint: CGPoint(x: 1, y: 0.5)
                ),
                letterboxStyle: nil,
                edgeGlowStyle: .init(
                    edgeIntensity: 3.2,
                    bloomRadius: 8.0,
                    bloomIntensity: 1.0,
                    tintColor: rgba(0.60, 0.28, 1.0, 1),
                    opacity: 0.12
                ),
                labelStyle: .init(
                    backgroundColor: rgba(0.08, 0.03, 0.16, 0.78),
                    borderColor: rgba(0.62, 0.28, 1.0, 0.44),
                    textColor: rgba(0.97, 0.94, 1.0, 1.0),
                    shadowColor: rgba(0.50, 0.24, 1.0, 0.25),
                    cornerRadius: 12,
                    horizontalPadding: 12,
                    verticalPadding: 7,
                    borderWidth: 1.5,
                    displayDuration: 0.9,
                    topPlacement: false,
                    margin: 18,
                    fixedOpacityMultiplier: 1.0
                ),
                clipStartFlashStyle: nil
            )

        case .cinematic:
            return ExportThemeProfile(
                saturation: 0.94,
                contrast: 1.14,
                brightness: -0.01,
                exposureEV: 0.00,
                vignetteIntensity: 0.35,
                vignetteRadius: 1.4,
                tintOverlay: rgba(0.92, 0.90, 0.98, 1),
                tintOpacity: 0.03,
                gradientOverlay: .init(
                    startColor: rgba(0.95, 0.70, 0.40, 1),
                    endColor: rgba(0.22, 0.35, 0.62, 1),
                    opacity: 0.05,
                    startPoint: CGPoint(x: 0, y: 1),
                    endPoint: CGPoint(x: 1, y: 0)
                ),
                letterboxStyle: .init(
                    barHeightRatio: 0.08,
                    color: rgba(0.0, 0.0, 0.0, 1),
                    opacity: 0.92
                ),
                edgeGlowStyle: nil,
                labelStyle: .init(
                    backgroundColor: rgba(0.02, 0.02, 0.02, 0.68),
                    borderColor: rgba(1.0, 1.0, 1.0, 0.10),
                    textColor: rgba(0.98, 0.98, 0.98, 0.95),
                    shadowColor: rgba(0.0, 0.0, 0.0, 0.20),
                    cornerRadius: 10,
                    horizontalPadding: 11,
                    verticalPadding: 6,
                    borderWidth: 1,
                    displayDuration: 0.9,
                    topPlacement: true,
                    margin: 14,
                    fixedOpacityMultiplier: 0.90
                ),
                clipStartFlashStyle: nil
            )

        case .hype:
            return ExportThemeProfile(
                saturation: 1.34,
                contrast: 1.24,
                brightness: 0.01,
                exposureEV: 0.06,
                vignetteIntensity: 0.14,
                vignetteRadius: 1.1,
                tintOverlay: rgba(1.00, 0.26, 0.30, 1),
                tintOpacity: 0.05,
                gradientOverlay: .init(
                    startColor: rgba(1.00, 0.35, 0.12, 1),
                    endColor: rgba(0.70, 0.10, 0.78, 1),
                    opacity: 0.07,
                    startPoint: CGPoint(x: 0.2, y: 1),
                    endPoint: CGPoint(x: 0.8, y: 0)
                ),
                letterboxStyle: nil,
                edgeGlowStyle: nil,
                labelStyle: .init(
                    backgroundColor: rgba(0.11, 0.02, 0.07, 0.80),
                    borderColor: rgba(1.00, 0.34, 0.18, 0.36),
                    textColor: rgba(1.0, 0.98, 0.96, 1.0),
                    shadowColor: rgba(1.00, 0.28, 0.18, 0.14),
                    cornerRadius: 12,
                    horizontalPadding: 13,
                    verticalPadding: 7,
                    borderWidth: 1.2,
                    displayDuration: 0.9,
                    topPlacement: false,
                    margin: 18,
                    fixedOpacityMultiplier: 1.0
                ),
                clipStartFlashStyle: .init(
                    duration: 0.12,
                    color: rgba(1.0, 0.80, 0.55, 1),
                    maxOpacity: 0.18
                )
            )

        case .minimal:
            return ExportThemeProfile(
                saturation: 1.00,
                contrast: 1.02,
                brightness: 0.00,
                exposureEV: 0.00,
                vignetteIntensity: 0.02,
                vignetteRadius: 1.5,
                tintOverlay: nil,
                tintOpacity: 0.0,
                gradientOverlay: nil,
                letterboxStyle: nil,
                edgeGlowStyle: nil,
                labelStyle: .init(
                    backgroundColor: rgba(0.06, 0.06, 0.07, 0.52),
                    borderColor: rgba(1.0, 1.0, 1.0, 0.08),
                    textColor: rgba(0.98, 0.98, 0.98, 0.86),
                    shadowColor: nil,
                    cornerRadius: 10,
                    horizontalPadding: 11,
                    verticalPadding: 6,
                    borderWidth: 1,
                    displayDuration: 0.55,
                    topPlacement: false,
                    margin: 18,
                    fixedOpacityMultiplier: 0.85
                ),
                clipStartFlashStyle: nil
            )
        }
    }
}

internal enum ExportThemeRendererError: LocalizedError {
    case noVideoTrack
    case noVideoComposition

    var errorDescription: String? {
        switch self {
        case .noVideoTrack: return "No video track available for themed export"
        case .noVideoComposition: return "Failed to create video composition"
        }
    }
}

internal final class ClipLabelOverlayCache: @unchecked Sendable {
    private let imagesByClipID: [UUID: CIImage]

    init(imagesByClipID: [UUID: CIImage]) {
        self.imagesByClipID = imagesByClipID
    }

    func image(for clipID: UUID) -> CIImage? {
        imagesByClipID[clipID]
    }
}

internal final class ExportThemeRenderer {
    @MainActor
    func makeThemedVideoComposition(
        asset: AVAsset,
        sourceVideoTrack: AVAssetTrack,
        segments: [ExportTimelineSegment],
        theme: ExportTheme,
        quality: ExportQuality
    ) async throws -> AVMutableVideoComposition {
        let naturalSize = try await sourceVideoTrack.load(.naturalSize)
        let preferredTransform = try await sourceVideoTrack.load(.preferredTransform)
        let geometry = makeRenderGeometry(
            naturalSize: naturalSize,
            preferredTransform: preferredTransform,
            quality: quality
        )
        let profile = theme.profile
        let labelCache = try buildLabelCache(segments: segments, profile: profile, geometry: geometry)

        return try await withCheckedThrowingContinuation { continuation in
            AVMutableVideoComposition.videoComposition(
                with: asset,
                applyingCIFiltersWithHandler: { request in
                    autoreleasepool {
                        let compositionTime = CMTimeGetSeconds(request.compositionTime)
                        let output = Self.renderThemedFrame(
                            sourceImage: request.sourceImage,
                            compositionTime: compositionTime,
                            geometry: geometry,
                            profile: profile,
                            segments: segments,
                            labelCache: labelCache
                        )
                        request.finish(with: output, context: nil)
                    }
                },
                completionHandler: { videoComposition, error in
                    if let error {
                        continuation.resume(throwing: error)
                        return
                    }

                    guard let videoComposition else {
                        continuation.resume(throwing: ExportThemeRendererError.noVideoComposition)
                        return
                    }

                    videoComposition.renderSize = geometry.renderSize
                    videoComposition.frameDuration = CMTime(value: 1, timescale: 30)
                    continuation.resume(returning: videoComposition)
                }
            )
        }
    }

    @MainActor
    func makeClipLabelImage(text: String, style: ExportThemeProfile.LabelStyle, scaleBucket: Int) throws -> CIImage {
        let fontSize: CGFloat = switch scaleBucket {
        case 720: 16
        case 1080: 18
        default: 22
        }

        let font = UIFont.systemFont(ofSize: fontSize, weight: .semibold)
        let paragraph = NSMutableParagraphStyle()
        paragraph.lineBreakMode = .byTruncatingTail

        let attrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: uiColor(style.textColor),
            .paragraphStyle: paragraph
        ]
        let attributed = NSAttributedString(string: text, attributes: attrs)
        let textSize = attributed.size()

        let canvasSize = CGSize(
            width: ceil(textSize.width + style.horizontalPadding * 2),
            height: ceil(textSize.height + style.verticalPadding * 2)
        )

        let format = UIGraphicsImageRendererFormat.default()
        format.opaque = false
        let renderer = UIGraphicsImageRenderer(size: canvasSize, format: format)
        let image = renderer.image { ctx in
            let bounds = CGRect(origin: .zero, size: canvasSize)
            let path = UIBezierPath(roundedRect: bounds, cornerRadius: style.cornerRadius)

            uiColor(style.backgroundColor).setFill()
            path.fill()

            if style.borderWidth > 0 {
                path.lineWidth = style.borderWidth
                uiColor(style.borderColor).setStroke()
                path.stroke()
            }

            if let shadowColor = style.shadowColor {
                ctx.cgContext.setShadow(
                    offset: CGSize(width: 0, height: 1),
                    blur: 4,
                    color: uiColor(shadowColor).cgColor
                )
            }

            let textRect = CGRect(
                x: style.horizontalPadding,
                y: style.verticalPadding,
                width: bounds.width - style.horizontalPadding * 2,
                height: bounds.height - style.verticalPadding * 2
            )
            attributed.draw(in: textRect)
        }

        guard let cgImage = image.cgImage else {
            throw ExportThemeRendererError.noVideoComposition
        }
        return CIImage(cgImage: cgImage)
    }

    private func buildLabelCache(
        segments: [ExportTimelineSegment],
        profile: ExportThemeProfile,
        geometry: ExportRenderGeometry
    ) throws -> ClipLabelOverlayCache {
        var imagesByClipID: [UUID: CIImage] = [:]
        for segment in segments {
            imagesByClipID[segment.clipID] = try makeClipLabelImage(
                text: segment.labelText,
                style: profile.labelStyle,
                scaleBucket: geometry.scaleBucket
            )
        }
        return ClipLabelOverlayCache(imagesByClipID: imagesByClipID)
    }

    private nonisolated static func renderThemedFrame(
        sourceImage: CIImage,
        compositionTime: Double,
        geometry: ExportRenderGeometry,
        profile: ExportThemeProfile,
        segments: [ExportTimelineSegment],
        labelCache: ClipLabelOverlayCache
    ) -> CIImage {
        let extent = sourceImage.extent
        var image = sourceImage.clampedToExtent()

        image = applyBaseColorTreatment(to: image, profile: profile)
        image = applyGradientOverlayIfNeeded(to: image, extent: extent, profile: profile)
        image = applyTintOverlayIfNeeded(to: image, extent: extent, profile: profile)
        image = applyEdgeGlowIfNeeded(to: image, extent: extent, profile: profile)
        image = applyLetterboxIfNeeded(to: image, extent: extent, profile: profile)

        if let frameContext = makeFrameContext(
            at: compositionTime,
            segments: segments,
            imageExtent: extent
        ) {
            image = applyClipStartFlashIfNeeded(to: image, extent: extent, profile: profile, context: frameContext)
            image = applyLabelIfNeeded(
                to: image,
                profile: profile,
                context: frameContext,
                labelCache: labelCache
            )
        }

        return image.cropped(to: extent)
    }
}

nonisolated private func makeFrameContext(
    at compositionTime: Double,
    segments: [ExportTimelineSegment],
    imageExtent: CGRect
) -> ThemeOverlayFrameContext? {
    guard let segment = segments.first(where: { $0.contains(outputTime: compositionTime) }) else {
        return nil
    }

    return ThemeOverlayFrameContext(
        compositionTime: compositionTime,
        localClipTime: max(0, compositionTime - segment.outputStartTime),
        segment: segment,
        imageExtent: imageExtent
    )
}

nonisolated private func applyBaseColorTreatment(to image: CIImage, profile: ExportThemeProfile) -> CIImage {
    var output = image

    let colorControls = CIFilter.colorControls()
    colorControls.inputImage = output
    colorControls.saturation = Float(profile.saturation)
    colorControls.contrast = Float(profile.contrast)
    colorControls.brightness = Float(profile.brightness)
    if let next = colorControls.outputImage {
        output = next
    }

    let exposure = CIFilter.exposureAdjust()
    exposure.inputImage = output
    exposure.ev = Float(profile.exposureEV)
    if let next = exposure.outputImage {
        output = next
    }

    if profile.vignetteIntensity > 0 {
        let vignette = CIFilter.vignette()
        vignette.inputImage = output
        vignette.intensity = Float(profile.vignetteIntensity)
        vignette.radius = Float(profile.vignetteRadius)
        if let next = vignette.outputImage {
            output = next
        }
    }

    return output
}

nonisolated private func applyGradientOverlayIfNeeded(
    to image: CIImage,
    extent: CGRect,
    profile: ExportThemeProfile
) -> CIImage {
    guard let gradient = profile.gradientOverlay, gradient.opacity > 0 else { return image }

    let start = CGPoint(
        x: extent.minX + extent.width * gradient.startPoint.x,
        y: extent.minY + extent.height * gradient.startPoint.y
    )
    let end = CGPoint(
        x: extent.minX + extent.width * gradient.endPoint.x,
        y: extent.minY + extent.height * gradient.endPoint.y
    )

    let filter = CIFilter.linearGradient()
    filter.point0 = start
    filter.point1 = end
    filter.color0 = ciColor(gradient.startColor)
    filter.color1 = ciColor(gradient.endColor)

    guard var gradientImage = filter.outputImage?.cropped(to: extent) else { return image }
    gradientImage = applyingAlpha(to: gradientImage, alpha: gradient.opacity)
    return gradientImage.composited(over: image)
}

nonisolated private func applyTintOverlayIfNeeded(
    to image: CIImage,
    extent: CGRect,
    profile: ExportThemeProfile
) -> CIImage {
    guard let tint = profile.tintOverlay, profile.tintOpacity > 0 else { return image }
    let overlay = CIImage(color: ciColor(tint))
        .cropped(to: extent)
    return applyingAlpha(to: overlay, alpha: profile.tintOpacity).composited(over: image)
}

nonisolated private func applyEdgeGlowIfNeeded(
    to image: CIImage,
    extent: CGRect,
    profile: ExportThemeProfile
) -> CIImage {
    guard let style = profile.edgeGlowStyle, style.opacity > 0 else { return image }

    let scale = 0.5
    let downscale = CGAffineTransform(scaleX: scale, y: scale)
    let upscale = CGAffineTransform(scaleX: 1 / scale, y: 1 / scale)

    let small = image.transformed(by: downscale)

    let edges = CIFilter.edges()
    edges.inputImage = small
    edges.intensity = Float(style.edgeIntensity)
    guard var glow = edges.outputImage else { return image }

    let bloom = CIFilter.bloom()
    bloom.inputImage = glow
    bloom.radius = Float(style.bloomRadius * scale)
    bloom.intensity = Float(style.bloomIntensity)
    if let bloomed = bloom.outputImage {
        glow = bloomed
    }

    let falseColor = CIFilter.falseColor()
    falseColor.inputImage = glow
    falseColor.color0 = ciColor(.init(0, 0, 0, 0))
    falseColor.color1 = ciColor(style.tintColor)
    if let tinted = falseColor.outputImage {
        glow = tinted
    }

    glow = glow.transformed(by: upscale).cropped(to: extent)
    glow = applyingAlpha(to: glow, alpha: style.opacity)
    return glow.applyingFilter("CIAdditionCompositing", parameters: [kCIInputBackgroundImageKey: image]).cropped(to: extent)
}

nonisolated private func applyLetterboxIfNeeded(
    to image: CIImage,
    extent: CGRect,
    profile: ExportThemeProfile
) -> CIImage {
    guard let style = profile.letterboxStyle, style.barHeightRatio > 0 else { return image }
    let barHeight = extent.height * style.barHeightRatio
    guard barHeight > 0 else { return image }

    let color = CIImage(color: ciColor(style.color))
    let topBar = applyingAlpha(
        to: color.cropped(to: CGRect(x: extent.minX, y: extent.maxY - barHeight, width: extent.width, height: barHeight)),
        alpha: style.opacity
    )
    let bottomBar = applyingAlpha(
        to: color.cropped(to: CGRect(x: extent.minX, y: extent.minY, width: extent.width, height: barHeight)),
        alpha: style.opacity
    )

    return topBar.composited(over: bottomBar.composited(over: image))
}

nonisolated private func applyClipStartFlashIfNeeded(
    to image: CIImage,
    extent: CGRect,
    profile: ExportThemeProfile,
    context: ThemeOverlayFrameContext
) -> CIImage {
    guard let flash = profile.clipStartFlashStyle else { return image }
    guard flash.duration > 0, context.localClipTime <= flash.duration else { return image }

    let decay = 1 - (context.localClipTime / flash.duration)
    let alpha = max(0, min(1, decay)) * flash.maxOpacity
    guard alpha > 0 else { return image }

    let overlay = CIImage(color: ciColor(flash.color)).cropped(to: extent)
    return applyingAlpha(to: overlay, alpha: alpha).composited(over: image)
}

nonisolated private func applyLabelIfNeeded(
    to image: CIImage,
    profile: ExportThemeProfile,
    context: ThemeOverlayFrameContext,
    labelCache: ClipLabelOverlayCache
) -> CIImage {
    guard let labelImage = labelCache.image(for: context.segment.clipID) else { return image }

    let alpha = labelVisibilityAlpha(
        at: context.localClipTime,
        displayDuration: profile.labelStyle.displayDuration
    ) * profile.labelStyle.fixedOpacityMultiplier
    guard alpha > 0.001 else { return image }

    let extent = context.imageExtent
    let barHeight = profile.letterboxStyle.map { extent.height * $0.barHeightRatio } ?? 0
    let labelExtent = labelImage.extent

    let originX = extent.minX + profile.labelStyle.margin
    let originY: CGFloat
    if profile.labelStyle.topPlacement {
        originY = extent.maxY - barHeight - labelExtent.height - profile.labelStyle.margin
    } else {
        originY = extent.minY + profile.labelStyle.margin
    }

    let positioned = applyingAlpha(to: labelImage, alpha: alpha)
        .transformed(by: CGAffineTransform(translationX: originX, y: originY))
    return positioned.composited(over: image)
}

nonisolated private func applyingAlpha(to image: CIImage, alpha: Double) -> CIImage {
    let clampedAlpha = max(0, min(1, alpha))
    guard clampedAlpha < 0.999 else { return image }

    let matrix = CIFilter.colorMatrix()
    matrix.inputImage = image
    matrix.aVector = CIVector(x: 0, y: 0, z: 0, w: clampedAlpha)
    return matrix.outputImage ?? image
}

nonisolated private func ciColor(_ rgba: SIMD4<Double>) -> CIColor {
    CIColor(red: rgba.x, green: rgba.y, blue: rgba.z, alpha: rgba.w)
}

nonisolated private func uiColor(_ rgba: SIMD4<Double>) -> UIColor {
    UIColor(
        red: rgba.x,
        green: rgba.y,
        blue: rgba.z,
        alpha: rgba.w
    )
}
