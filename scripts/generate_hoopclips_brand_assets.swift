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
        drawCourtPlate()
        drawBasketballPanel()
        drawMonogram()
        drawWordmark()
        drawFineBorder()
        image.unlockFocus()
        return image
    }

    private func drawBackground() {
        let rect = NSRect(x: 0, y: 0, width: size, height: size)
        color(5, 7, 9).setFill()
        rect.fill()

        let gradient = NSGradient(colors: [
            color(19, 23, 24),
            color(6, 8, 10),
            color(2, 3, 5)
        ])
        gradient?.draw(in: NSBezierPath(rect: rect), angle: -20)
    }

    private func drawCourtPlate() {
        let plate = NSBezierPath()
        plate.move(to: CGPoint(x: size * 0.075, y: size * 0.185))
        plate.line(to: CGPoint(x: size * 0.820, y: size * 0.185))
        plate.line(to: CGPoint(x: size * 0.925, y: size * 0.310))
        plate.line(to: CGPoint(x: size * 0.925, y: size * 0.825))
        plate.line(to: CGPoint(x: size * 0.165, y: size * 0.825))
        plate.line(to: CGPoint(x: size * 0.075, y: size * 0.700))
        plate.close()
        color(255, 255, 248, 0.055).setFill()
        plate.fill()
        color(255, 255, 248, 0.145).setStroke()
        plate.lineWidth = size * 0.008
        plate.stroke()

        let topSlash = NSBezierPath()
        topSlash.move(to: CGPoint(x: size * 0.120, y: size * 0.778))
        topSlash.line(to: CGPoint(x: size * 0.362, y: size * 0.778))
        topSlash.line(to: CGPoint(x: size * 0.420, y: size * 0.838))
        topSlash.line(to: CGPoint(x: size * 0.178, y: size * 0.838))
        topSlash.close()
        color(255, 107, 22).setFill()
        topSlash.fill()
    }

    private func drawBasketballPanel() {
        let ballRect = NSRect(
            x: size * 0.540,
            y: size * 0.105,
            width: size * 0.520,
            height: size * 0.520
        )
        let ball = NSBezierPath(ovalIn: ballRect)
        let ballGradient = NSGradient(colors: [
            color(255, 126, 18),
            color(238, 75, 14)
        ])
        ballGradient?.draw(in: ball, angle: -32)

        color(5, 7, 9, 0.86).setStroke()
        drawCurve(
            from: CGPoint(x: size * 0.585, y: size * 0.330),
            control1: CGPoint(x: size * 0.715, y: size * 0.385),
            control2: CGPoint(x: size * 0.875, y: size * 0.390),
            to: CGPoint(x: size * 1.015, y: size * 0.330),
            width: size * 0.021
        )
        drawCurve(
            from: CGPoint(x: size * 0.785, y: size * 0.110),
            control1: CGPoint(x: size * 0.720, y: size * 0.245),
            control2: CGPoint(x: size * 0.720, y: size * 0.470),
            to: CGPoint(x: size * 0.855, y: size * 0.625),
            width: size * 0.021
        )
        drawCurve(
            from: CGPoint(x: size * 0.602, y: size * 0.510),
            control1: CGPoint(x: size * 0.730, y: size * 0.470),
            control2: CGPoint(x: size * 0.905, y: size * 0.470),
            to: CGPoint(x: size * 1.010, y: size * 0.552),
            width: size * 0.018
        )
    }

    private func drawMonogram() {
        let font = NSFont(name: "AvenirNextCondensed-HeavyItalic", size: size * 0.585)
            ?? NSFont(name: "DINCondensed-Bold", size: size * 0.570)
            ?? NSFont.systemFont(ofSize: size * 0.560, weight: .black)
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.55)
        shadow.shadowBlurRadius = size * 0.010
        shadow.shadowOffset = NSSize(width: size * 0.010, height: -size * 0.010)

        let attributes: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: color(248, 247, 239),
            .strokeColor: color(3, 5, 7),
            .strokeWidth: -4.0,
            .shadow: shadow,
            .kern: -size * 0.018
        ]
        let text = "HC"
        let textSize = text.size(withAttributes: attributes)
        let point = CGPoint(
            x: (size - textSize.width) / 2 - size * 0.008,
            y: size * 0.252
        )
        text.draw(at: point, withAttributes: attributes)
    }

    private func drawWordmark() {
        let plate = NSBezierPath(roundedRect: NSRect(
            x: size * 0.145,
            y: size * 0.132,
            width: size * 0.710,
            height: size * 0.118
        ), xRadius: size * 0.024, yRadius: size * 0.024)
        color(255, 107, 22).setFill()
        plate.fill()

        let cut = NSBezierPath()
        cut.move(to: CGPoint(x: size * 0.145, y: size * 0.132))
        cut.line(to: CGPoint(x: size * 0.298, y: size * 0.132))
        cut.line(to: CGPoint(x: size * 0.380, y: size * 0.250))
        cut.line(to: CGPoint(x: size * 0.225, y: size * 0.250))
        cut.close()
        color(5, 7, 9, 0.22).setFill()
        cut.fill()

        let font = NSFont(name: "AvenirNextCondensed-Heavy", size: size * 0.072)
            ?? NSFont(name: "DINCondensed-Bold", size: size * 0.077)
            ?? NSFont.systemFont(ofSize: size * 0.070, weight: .black)
        let attributes: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: color(255, 252, 241),
            .kern: size * 0.003
        ]
        let text = "HOOPCLIPS"
        let textSize = text.size(withAttributes: attributes)
        text.draw(at: CGPoint(
            x: (size - textSize.width) / 2,
            y: size * 0.157
        ), withAttributes: attributes)
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
