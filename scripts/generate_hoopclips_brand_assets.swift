#!/usr/bin/env swift
import AppKit
import Foundation
import ImageIO

private let repoRoot = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)

private let appIconPaths = [
    "ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png",
    "ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png"
]

private let appIconContentsPaths = [
    "ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/Contents.json",
    "ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/Contents.json"
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
        drawFineBorder()
        image.unlockFocus()
        return image
    }

    private func drawBackground() {
        let rect = NSRect(x: 0, y: 0, width: size, height: size)
        color(4, 6, 8).setFill()
        rect.fill()

        let gradient = NSGradient(colors: [
            color(27, 31, 32),
            color(7, 10, 12),
            color(2, 3, 5)
        ])
        gradient?.draw(in: NSBezierPath(rect: rect), angle: -35)

        let spotlight = NSBezierPath(ovalIn: NSRect(
            x: -size * 0.10,
            y: size * 0.55,
            width: size * 0.54,
            height: size * 0.54
        ))
        color(255, 122, 28, 0.12).setFill()
        spotlight.fill()
    }

    private func drawBasketballMark() {
        let ballRect = NSRect(
            x: size * 0.085,
            y: size * 0.205,
            width: size * 0.430,
            height: size * 0.430
        )
        let ball = NSBezierPath(ovalIn: ballRect)
        let ballGradient = NSGradient(colors: [
            color(255, 129, 27),
            color(235, 73, 16)
        ])
        ballGradient?.draw(in: ball, angle: -24)

        color(5, 7, 9).setStroke()
        drawCurve(
            from: CGPoint(x: size * 0.313, y: size * 0.205),
            control1: CGPoint(x: size * 0.390, y: size * 0.340),
            control2: CGPoint(x: size * 0.375, y: size * 0.490),
            to: CGPoint(x: size * 0.287, y: size * 0.615),
            width: size * 0.024
        )
        drawCurve(
            from: CGPoint(x: size * 0.100, y: size * 0.352),
            control1: CGPoint(x: size * 0.228, y: size * 0.424),
            control2: CGPoint(x: size * 0.362, y: size * 0.429),
            to: CGPoint(x: size * 0.503, y: size * 0.383),
            width: size * 0.023
        )
        drawCurve(
            from: CGPoint(x: size * 0.168, y: size * 0.558),
            control1: CGPoint(x: size * 0.286, y: size * 0.536),
            control2: CGPoint(x: size * 0.400, y: size * 0.480),
            to: CGPoint(x: size * 0.503, y: size * 0.383),
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
        cut.move(to: CGPoint(x: size * 0.095, y: size * 0.225))
        cut.line(to: CGPoint(x: size * 0.820, y: size * 0.313))
        cut.line(to: CGPoint(x: size * 0.915, y: size * 0.386))
        cut.line(to: CGPoint(x: size * 0.185, y: size * 0.292))
        cut.close()
        color(247, 181, 42).setFill()
        cut.fill()
        NSGraphicsContext.restoreGraphicsState()
    }

    private func drawMonogram() {
        let font = NSFont(name: "AvenirNextCondensed-HeavyItalic", size: size * 0.650)
            ?? NSFont(name: "DINCondensed-Bold", size: size * 0.635)
            ?? NSFont.systemFont(ofSize: size * 0.620, weight: .black)
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.64)
        shadow.shadowBlurRadius = size * 0.016
        shadow.shadowOffset = NSSize(width: 0, height: -size * 0.011)

        let attributes: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: color(248, 247, 239),
            .strokeColor: color(3, 5, 7),
            .strokeWidth: -3.2,
            .shadow: shadow,
            .kern: -size * 0.010
        ]
        let text = "HC"
        let textSize = text.size(withAttributes: attributes)
        let point = CGPoint(
            x: (size - textSize.width) / 2 + size * 0.050,
            y: size * 0.220
        )
        text.draw(at: point, withAttributes: attributes)
    }

    private func drawFineBorder() {
        let rect = NSRect(x: 0, y: 0, width: size, height: size)
        let inset = size * 0.026
        let border = NSBezierPath(roundedRect: rect.insetBy(dx: inset, dy: inset), xRadius: size * 0.160, yRadius: size * 0.160)
        color(255, 255, 255, 0.045).setStroke()
        border.lineWidth = size * 0.0035
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

private func saveAppIconContents(to relativePath: String) throws {
    let outputURL = repoRoot.appendingPathComponent(relativePath)
    try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
    let contents = """
    {
      "images" : [
        {
          "filename" : "icon.png",
          "idiom" : "universal",
          "platform" : "ios",
          "size" : "1024x1024"
        }
      ],
      "info" : {
        "author" : "xcode",
        "version" : 1
      }
    }
    """
    try (contents + "\n").write(to: outputURL, atomically: true, encoding: .utf8)
}

let appIcon = HoopClipsBrandRenderer(size: 1024).image()
let brandMark = HoopClipsBrandRenderer(size: 512).image()

for path in appIconPaths {
    try savePNG(appIcon, to: path)
}
for path in appIconContentsPaths {
    try saveAppIconContents(to: path)
}
for path in brandMarkPaths {
    try savePNG(brandMark, to: path)
}

print("Generated HoopClips app icon and in-app brand mark assets.")
