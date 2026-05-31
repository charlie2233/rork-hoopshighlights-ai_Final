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
        drawBasketballMark()
        drawBaselineSlash()
        drawMonogram()
        drawWordmark()
        drawFineBorder()
        image.unlockFocus()
        return image
    }

    private func drawBackground() {
        let rect = NSRect(x: 0, y: 0, width: size, height: size)
        color(6, 8, 10).setFill()
        rect.fill()

        let gradient = NSGradient(colors: [
            color(26, 29, 31),
            color(9, 11, 13),
            color(3, 5, 7)
        ])
        gradient?.draw(in: NSBezierPath(rect: rect), angle: -28)
    }

    private func drawBasketballMark() {
        let ballRect = NSRect(
            x: size * 0.103,
            y: size * 0.314,
            width: size * 0.430,
            height: size * 0.430
        )
        let ball = NSBezierPath(ovalIn: ballRect)
        let ballGradient = NSGradient(colors: [
            color(255, 119, 29),
            color(232, 83, 19)
        ])
        ballGradient?.draw(in: ball, angle: -24)

        color(7, 9, 12).setStroke()
        drawCurve(
            from: CGPoint(x: size * 0.332, y: size * 0.318),
            control1: CGPoint(x: size * 0.408, y: size * 0.454),
            control2: CGPoint(x: size * 0.395, y: size * 0.602),
            to: CGPoint(x: size * 0.304, y: size * 0.724),
            width: size * 0.024
        )
        drawCurve(
            from: CGPoint(x: size * 0.116, y: size * 0.458),
            control1: CGPoint(x: size * 0.244, y: size * 0.532),
            control2: CGPoint(x: size * 0.381, y: size * 0.536),
            to: CGPoint(x: size * 0.520, y: size * 0.492),
            width: size * 0.023
        )
        drawCurve(
            from: CGPoint(x: size * 0.184, y: size * 0.666),
            control1: CGPoint(x: size * 0.300, y: size * 0.644),
            control2: CGPoint(x: size * 0.414, y: size * 0.588),
            to: CGPoint(x: size * 0.518, y: size * 0.492),
            width: size * 0.020
        )
    }

    private func drawBaselineSlash() {
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.34)
        shadow.shadowBlurRadius = size * 0.014
        shadow.shadowOffset = NSSize(width: 0, height: -size * 0.006)

        NSGraphicsContext.saveGraphicsState()
        shadow.set()
        let cut = NSBezierPath()
        cut.move(to: CGPoint(x: size * 0.152, y: size * 0.266))
        cut.line(to: CGPoint(x: size * 0.792, y: size * 0.333))
        cut.line(to: CGPoint(x: size * 0.874, y: size * 0.392))
        cut.line(to: CGPoint(x: size * 0.228, y: size * 0.323))
        cut.close()
        color(249, 181, 45).setFill()
        cut.fill()
        NSGraphicsContext.restoreGraphicsState()
    }

    private func drawMonogram() {
        let font = NSFont(name: "AvenirNextCondensed-HeavyItalic", size: size * 0.510)
            ?? NSFont(name: "DINCondensed-Bold", size: size * 0.500)
            ?? NSFont.systemFont(ofSize: size * 0.490, weight: .black)
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.58)
        shadow.shadowBlurRadius = size * 0.018
        shadow.shadowOffset = NSSize(width: 0, height: -size * 0.012)

        let attributes: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: color(248, 247, 239),
            .strokeColor: color(7, 9, 12),
            .strokeWidth: -2.8,
            .shadow: shadow,
            .kern: 0
        ]
        let text = "HC"
        let textSize = text.size(withAttributes: attributes)
        let point = CGPoint(
            x: (size - textSize.width) / 2 + size * 0.058,
            y: size * 0.292
        )
        text.draw(at: point, withAttributes: attributes)
    }

    private func drawWordmark() {
        let font = NSFont(name: "AvenirNextCondensed-HeavyItalic", size: size * 0.072)
            ?? NSFont.systemFont(ofSize: size * 0.068, weight: .heavy)
        let attributes: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: color(248, 247, 239, 0.94),
            .kern: size * 0.004
        ]
        let text = "HOOPCLIPS"
        let textSize = text.size(withAttributes: attributes)
        let point = CGPoint(
            x: (size - textSize.width) / 2 + size * 0.006,
            y: size * 0.145
        )
        text.draw(at: point, withAttributes: attributes)

        let underline = NSBezierPath()
        underline.move(to: CGPoint(x: size * 0.302, y: size * 0.127))
        underline.line(to: CGPoint(x: size * 0.700, y: size * 0.127))
        underline.lineWidth = size * 0.012
        underline.lineCapStyle = .round
        color(240, 159, 32, 0.92).setStroke()
        underline.stroke()
    }

    private func drawFineBorder() {
        let rect = NSRect(x: 0, y: 0, width: size, height: size)
        let inset = size * 0.020
        let border = NSBezierPath(roundedRect: rect.insetBy(dx: inset, dy: inset), xRadius: size * 0.185, yRadius: size * 0.185)
        color(255, 255, 255, 0.060).setStroke()
        border.lineWidth = size * 0.004
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
