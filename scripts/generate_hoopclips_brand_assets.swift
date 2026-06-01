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
        drawBadgeSurface()
        drawCourtDetail()
        drawBasketballSignal()
        drawSpeedCut()
        drawMonogram()
        drawClipFrame()
        drawFineBorder()
        image.unlockFocus()
        return image
    }

    private func drawBackground() {
        let rect = NSRect(x: 0, y: 0, width: size, height: size)
        color(4, 6, 7).setFill()
        rect.fill()

        let gradient = NSGradient(colors: [
            color(17, 20, 21),
            color(8, 10, 11),
            color(3, 4, 5)
        ])
        gradient?.draw(in: NSBezierPath(rect: rect), angle: -18)
    }

    private func drawBadgeSurface() {
        let rect = NSRect(x: 0, y: 0, width: size, height: size)
        let badge = NSBezierPath(roundedRect: rect.insetBy(dx: size * 0.045, dy: size * 0.045), xRadius: size * 0.155, yRadius: size * 0.155)
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.50)
        shadow.shadowBlurRadius = size * 0.024
        shadow.shadowOffset = NSSize(width: 0, height: -size * 0.012)
        shadow.set()
        color(9, 12, 13).setFill()
        badge.fill()
        NSShadow().set()

        let insetBadge = NSBezierPath(roundedRect: rect.insetBy(dx: size * 0.070, dy: size * 0.070), xRadius: size * 0.130, yRadius: size * 0.130)
        NSGradient(colors: [
            color(18, 22, 24),
            color(7, 10, 11),
            color(2, 3, 4)
        ])?.draw(in: insetBadge, angle: -35)

    }

    private func drawCourtDetail() {
        color(255, 249, 235, 0.070).setStroke()

        let baseline = NSBezierPath()
        baseline.move(to: CGPoint(x: size * 0.110, y: size * 0.275))
        baseline.line(to: CGPoint(x: size * 0.890, y: size * 0.275))
        baseline.lineWidth = size * 0.004
        baseline.stroke()

        let arc = NSBezierPath(ovalIn: NSRect(
            x: size * 0.285,
            y: size * 0.255,
            width: size * 0.430,
            height: size * 0.430
        ))
        arc.lineWidth = size * 0.003
        arc.stroke()

        let halfCourt = NSBezierPath()
        halfCourt.move(to: CGPoint(x: size * 0.500, y: size * 0.140))
        halfCourt.line(to: CGPoint(x: size * 0.500, y: size * 0.735))
        halfCourt.lineWidth = size * 0.0025
        halfCourt.stroke()
    }

    private func drawBasketballSignal() {
        let ballRect = NSRect(x: size * 0.605, y: size * 0.245, width: size * 0.250, height: size * 0.250)
        color(255, 119, 17).setFill()
        NSBezierPath(ovalIn: ballRect).fill()

        color(7, 9, 10, 0.64).setStroke()
        let lineWidth = size * 0.009

        let middleSeam = NSBezierPath()
        middleSeam.move(to: CGPoint(x: ballRect.midX, y: ballRect.minY + size * 0.012))
        middleSeam.line(to: CGPoint(x: ballRect.midX, y: ballRect.maxY - size * 0.012))
        middleSeam.lineWidth = lineWidth
        middleSeam.stroke()

        let curveA = NSBezierPath()
        curveA.move(to: CGPoint(x: ballRect.minX + size * 0.030, y: ballRect.minY + size * 0.035))
        curveA.curve(
            to: CGPoint(x: ballRect.maxX - size * 0.032, y: ballRect.maxY - size * 0.035),
            controlPoint1: CGPoint(x: ballRect.midX - size * 0.085, y: ballRect.midY - size * 0.025),
            controlPoint2: CGPoint(x: ballRect.midX - size * 0.020, y: ballRect.midY + size * 0.080)
        )
        curveA.lineWidth = lineWidth
        curveA.stroke()

        let curveB = NSBezierPath()
        curveB.move(to: CGPoint(x: ballRect.maxX - size * 0.032, y: ballRect.minY + size * 0.035))
        curveB.curve(
            to: CGPoint(x: ballRect.minX + size * 0.030, y: ballRect.maxY - size * 0.035),
            controlPoint1: CGPoint(x: ballRect.midX + size * 0.085, y: ballRect.midY - size * 0.025),
            controlPoint2: CGPoint(x: ballRect.midX + size * 0.020, y: ballRect.midY + size * 0.080)
        )
        curveB.lineWidth = lineWidth
        curveB.stroke()
    }

    private func drawSpeedCut() {
        let cut = NSBezierPath()
        cut.move(to: CGPoint(x: size * 0.130, y: size * 0.375))
        cut.line(to: CGPoint(x: size * 0.720, y: size * 0.375))
        cut.line(to: CGPoint(x: size * 0.675, y: size * 0.438))
        cut.line(to: CGPoint(x: size * 0.158, y: size * 0.438))
        cut.close()
        color(255, 119, 17).setFill()
        cut.fill()

        let blackCut = NSBezierPath()
        blackCut.move(to: CGPoint(x: size * 0.235, y: size * 0.345))
        blackCut.line(to: CGPoint(x: size * 0.750, y: size * 0.345))
        blackCut.line(to: CGPoint(x: size * 0.730, y: size * 0.366))
        blackCut.line(to: CGPoint(x: size * 0.248, y: size * 0.366))
        blackCut.close()
        color(2, 3, 4).setFill()
        blackCut.fill()
    }

    private func drawMonogram() {
        let paragraph = NSMutableParagraphStyle()
        paragraph.alignment = .center
        let font = brandFont(size: size * 0.530)
        let attrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: color(249, 246, 235),
            .strokeColor: color(2, 3, 4),
            .strokeWidth: -3.2,
            .paragraphStyle: paragraph
        ]
        let text = NSAttributedString(string: "HC", attributes: attrs)
        let textSize = text.size()
        let drawPoint = CGPoint(
            x: (size - textSize.width) / 2 - size * 0.006,
            y: size * 0.300
        )

        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.70)
        shadow.shadowBlurRadius = size * 0.010
        shadow.shadowOffset = NSSize(width: size * 0.012, height: -size * 0.014)
        shadow.set()
        text.draw(at: drawPoint)
        NSShadow().set()
    }

    private func drawClipFrame() {
        color(255, 119, 17, 0.92).setStroke()
        let lineWidth = size * 0.012
        let cornerLength = size * 0.105
        let inset = size * 0.128

        let topLeft = NSBezierPath()
        topLeft.move(to: CGPoint(x: inset, y: size - inset - cornerLength))
        topLeft.line(to: CGPoint(x: inset, y: size - inset))
        topLeft.line(to: CGPoint(x: inset + cornerLength, y: size - inset))
        topLeft.lineWidth = lineWidth
        topLeft.lineCapStyle = .square
        topLeft.lineJoinStyle = .miter
        topLeft.stroke()

        let bottomRight = NSBezierPath()
        bottomRight.move(to: CGPoint(x: size - inset - cornerLength, y: inset))
        bottomRight.line(to: CGPoint(x: size - inset, y: inset))
        bottomRight.line(to: CGPoint(x: size - inset, y: inset + cornerLength))
        bottomRight.lineWidth = lineWidth
        bottomRight.lineCapStyle = .square
        bottomRight.lineJoinStyle = .miter
        bottomRight.stroke()
    }

    private func drawWordmark() {
        let paragraph = NSMutableParagraphStyle()
        paragraph.alignment = .center
        let attrs: [NSAttributedString.Key: Any] = [
            .font: brandFont(size: size * 0.060),
            .foregroundColor: color(255, 119, 17),
            .paragraphStyle: paragraph,
            .kern: size * 0.006
        ]
        let wordmark = NSAttributedString(string: "HOOPCLIPS", attributes: attrs)
        let rect = NSRect(x: size * 0.165, y: size * 0.105, width: size * 0.670, height: size * 0.085)
        wordmark.draw(in: rect)
    }

    private func drawFineBorder() {
        let rect = NSRect(x: 0, y: 0, width: size, height: size)
        let inset = size * 0.026
        let border = NSBezierPath(roundedRect: rect.insetBy(dx: inset, dy: inset), xRadius: size * 0.160, yRadius: size * 0.160)
        color(255, 249, 235, 0.070).setStroke()
        border.lineWidth = size * 0.004
        border.stroke()
    }

    private func brandFont(size: CGFloat) -> NSFont {
        for name in [
            "AvenirNextCondensed-HeavyItalic",
            "AvenirNext-HeavyItalic",
            "DINCondensed-Bold",
            "HelveticaNeue-CondensedBlack"
        ] {
            if let font = NSFont(name: name, size: size) {
                return font
            }
        }
        return NSFont.systemFont(ofSize: size, weight: .heavy)
    }

    private func slabPath(x: CGFloat, y: CGFloat, width: CGFloat, height: CGFloat, slant: CGFloat) -> NSBezierPath {
        let path = NSBezierPath()
        path.move(to: CGPoint(x: x + slant, y: y + height))
        path.line(to: CGPoint(x: x + width + slant, y: y + height))
        path.line(to: CGPoint(x: x + width - slant, y: y))
        path.line(to: CGPoint(x: x - slant, y: y))
        path.close()
        return path
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
