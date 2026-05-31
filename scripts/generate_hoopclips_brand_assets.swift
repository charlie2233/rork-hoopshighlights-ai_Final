#!/usr/bin/env swift
import AppKit
import Foundation
import ImageIO

private let repoRoot = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)

private let appIconPaths = [
    "ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png",
    "ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png"
]

private let brandMarkPaths = [
    "ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png",
    "ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png"
]

private func color(_ red: CGFloat, _ green: CGFloat, _ blue: CGFloat, _ alpha: CGFloat = 1) -> NSColor {
    NSColor(calibratedRed: red / 255, green: green / 255, blue: blue / 255, alpha: alpha)
}

private struct HoopClipsBrandRenderer {
    let size: CGFloat

    func image() -> NSImage {
        let image = NSImage(size: NSSize(width: size, height: size))
        image.lockFocus()
        NSGraphicsContext.current?.imageInterpolation = .high
        drawBackground()
        drawBasketballAccent()
        drawSpeedCut()
        drawMonogram()
        drawFineBorder()
        image.unlockFocus()
        return image
    }

    private func drawBackground() {
        let rect = NSRect(x: 0, y: 0, width: size, height: size)
        color(5, 7, 10).setFill()
        rect.fill()

        let gradient = NSGradient(colors: [
            color(35, 39, 43),
            color(12, 14, 17),
            color(5, 7, 10)
        ])
        gradient?.draw(in: NSBezierPath(rect: rect), angle: -18)
    }

    private func drawBasketballAccent() {
        let ballRect = NSRect(
            x: size * 0.128,
            y: size * 0.285,
            width: size * 0.39,
            height: size * 0.43
        )
        let ball = NSBezierPath(ovalIn: ballRect)
        color(242, 92, 28).setFill()
        ball.fill()

        color(7, 9, 12).setStroke()
        drawCurve(
            from: CGPoint(x: size * 0.318, y: size * 0.290),
            control1: CGPoint(x: size * 0.376, y: size * 0.420),
            control2: CGPoint(x: size * 0.374, y: size * 0.566),
            to: CGPoint(x: size * 0.304, y: size * 0.708),
            width: size * 0.022
        )
        drawCurve(
            from: CGPoint(x: size * 0.137, y: size * 0.442),
            control1: CGPoint(x: size * 0.250, y: size * 0.516),
            control2: CGPoint(x: size * 0.378, y: size * 0.518),
            to: CGPoint(x: size * 0.506, y: size * 0.472),
            width: size * 0.022
        )
        drawCurve(
            from: CGPoint(x: size * 0.190, y: size * 0.658),
            control1: CGPoint(x: size * 0.302, y: size * 0.632),
            control2: CGPoint(x: size * 0.404, y: size * 0.572),
            to: CGPoint(x: size * 0.504, y: size * 0.476),
            width: size * 0.019
        )
    }

    private func drawSpeedCut() {
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.42)
        shadow.shadowBlurRadius = size * 0.018
        shadow.shadowOffset = NSSize(width: 0, height: -size * 0.008)

        NSGraphicsContext.saveGraphicsState()
        shadow.set()
        let cut = NSBezierPath()
        cut.move(to: CGPoint(x: size * 0.228, y: size * 0.247))
        cut.line(to: CGPoint(x: size * 0.782, y: size * 0.322))
        cut.line(to: CGPoint(x: size * 0.838, y: size * 0.367))
        cut.line(to: CGPoint(x: size * 0.278, y: size * 0.295))
        cut.close()
        color(244, 166, 35).setFill()
        cut.fill()
        NSGraphicsContext.restoreGraphicsState()
    }

    private func drawMonogram() {
        let font = NSFont(name: "AvenirNextCondensed-HeavyItalic", size: size * 0.435)
            ?? NSFont(name: "DINCondensed-Bold", size: size * 0.43)
            ?? NSFont.systemFont(ofSize: size * 0.42, weight: .black)
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.62)
        shadow.shadowBlurRadius = size * 0.024
        shadow.shadowOffset = NSSize(width: 0, height: -size * 0.010)

        let attributes: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: color(248, 247, 239),
            .strokeColor: color(7, 9, 12),
            .strokeWidth: -2.4,
            .shadow: shadow,
            .kern: 0
        ]
        let text = "HC"
        let textSize = text.size(withAttributes: attributes)
        let point = CGPoint(
            x: (size - textSize.width) / 2 + size * 0.055,
            y: size * 0.304
        )
        text.draw(at: point, withAttributes: attributes)
    }

    private func drawFineBorder() {
        let rect = NSRect(x: 0, y: 0, width: size, height: size)
        let inset = size * 0.018
        let border = NSBezierPath(roundedRect: rect.insetBy(dx: inset, dy: inset), xRadius: size * 0.20, yRadius: size * 0.20)
        color(255, 255, 255, 0.045).setStroke()
        border.lineWidth = size * 0.003
        border.stroke()
    }

    private func drawCurve(from: CGPoint, control1: CGPoint, control2: CGPoint, to: CGPoint, width: CGFloat) {
        let path = NSBezierPath()
        path.move(to: from)
        path.curve(to: to, controlPoint1: control1, controlPoint2: control2)
        path.lineWidth = width
        path.lineCapStyle = .round
        path.stroke()
    }
}

private func savePNG(_ image: NSImage, to relativePath: String) throws {
    let outputURL = repoRoot.appendingPathComponent(relativePath)
    try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
    guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        throw NSError(domain: "HoopClipsLogo", code: 1, userInfo: [NSLocalizedDescriptionKey: "Could not read generated image for \(relativePath)"])
    }
    let width = Int(image.size.width)
    let height = Int(image.size.height)
    guard let context = CGContext(
        data: nil,
        width: width,
        height: height,
        bitsPerComponent: 8,
        bytesPerRow: width * 4,
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue | CGBitmapInfo.byteOrder32Big.rawValue
    ) else {
        throw NSError(domain: "HoopClipsLogo", code: 1, userInfo: [NSLocalizedDescriptionKey: "Could not create RGB context for \(relativePath)"])
    }
    context.setFillColor(CGColor(red: 5 / 255, green: 7 / 255, blue: 10 / 255, alpha: 1))
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))
    context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
    guard let flattened = context.makeImage(),
          let destination = CGImageDestinationCreateWithURL(outputURL as CFURL, "public.png" as CFString, 1, nil) else {
        throw NSError(domain: "HoopClipsLogo", code: 1, userInfo: [NSLocalizedDescriptionKey: "Could not prepare PNG destination for \(relativePath)"])
    }
    CGImageDestinationAddImage(destination, flattened, nil)
    if !CGImageDestinationFinalize(destination) {
        throw NSError(domain: "HoopClipsLogo", code: 1, userInfo: [NSLocalizedDescriptionKey: "Could not encode PNG for \(relativePath)"])
    }
}

let appIcon = HoopClipsBrandRenderer(size: 1024).image()
let brandMark = HoopClipsBrandRenderer(size: 512).image()

for path in appIconPaths {
    try savePNG(appIcon, to: path)
}
for path in brandMarkPaths {
    try savePNG(brandMark, to: path)
}

print("Generated HoopClips app icon and in-app brand mark assets.")
