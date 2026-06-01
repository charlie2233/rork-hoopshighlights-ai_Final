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
        drawHoopArc()
        drawSlabMonogram()
        drawClipCorners()
        drawFineBorder()
        image.unlockFocus()
        return image
    }

    private func drawBackground() {
        let rect = NSRect(x: 0, y: 0, width: size, height: size)
        color(5, 7, 9).setFill()
        rect.fill()

        let gradient = NSGradient(colors: [
            color(18, 21, 22),
            color(7, 9, 10),
            color(2, 3, 4)
        ])
        gradient?.draw(in: NSBezierPath(rect: rect), angle: -20)
    }

    private func drawBadgeSurface() {
        let rect = NSRect(x: 0, y: 0, width: size, height: size)
        let badge = NSBezierPath(roundedRect: rect.insetBy(dx: size * 0.040, dy: size * 0.040), xRadius: size * 0.170, yRadius: size * 0.170)
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.55)
        shadow.shadowBlurRadius = size * 0.030
        shadow.shadowOffset = NSSize(width: 0, height: -size * 0.010)
        shadow.set()
        color(11, 14, 16).setFill()
        badge.fill()
        NSShadow().set()

        let insetBadge = NSBezierPath(roundedRect: rect.insetBy(dx: size * 0.064, dy: size * 0.064), xRadius: size * 0.145, yRadius: size * 0.145)
        NSGradient(colors: [
            color(22, 26, 28),
            color(9, 12, 14),
            color(2, 4, 5)
        ])?.draw(in: insetBadge, angle: -35)
    }

    private func drawCourtDetail() {
        color(255, 255, 248, 0.055).setStroke()

        let baseline = NSBezierPath()
        baseline.move(to: CGPoint(x: size * 0.145, y: size * 0.260))
        baseline.line(to: CGPoint(x: size * 0.855, y: size * 0.260))
        baseline.lineWidth = size * 0.005
        baseline.stroke()

        let arc = NSBezierPath(ovalIn: NSRect(
            x: size * 0.270,
            y: size * 0.230,
            width: size * 0.460,
            height: size * 0.460
        ))
        arc.lineWidth = size * 0.004
        arc.stroke()

        let halfCourt = NSBezierPath()
        halfCourt.move(to: CGPoint(x: size * 0.500, y: size * 0.140))
        halfCourt.line(to: CGPoint(x: size * 0.500, y: size * 0.860))
        halfCourt.lineWidth = size * 0.003
        halfCourt.stroke()
    }

    private func drawHoopArc() {
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.42)
        shadow.shadowBlurRadius = size * 0.018
        shadow.shadowOffset = NSSize(width: size * 0.012, height: -size * 0.010)
        shadow.set()

        let arc = NSBezierPath()
        arc.appendArc(
            withCenter: CGPoint(x: size * 0.610, y: size * 0.520),
            radius: size * 0.285,
            startAngle: 38,
            endAngle: 322,
            clockwise: false
        )
        arc.lineWidth = size * 0.108
        arc.lineCapStyle = .round
        color(255, 128, 20).setFill()
        color(255, 128, 20).setStroke()
        arc.stroke()

        color(58, 25, 9, 0.54).setStroke()
        drawCurve(
            from: CGPoint(x: size * 0.665, y: size * 0.295),
            control1: CGPoint(x: size * 0.750, y: size * 0.410),
            control2: CGPoint(x: size * 0.755, y: size * 0.600),
            to: CGPoint(x: size * 0.670, y: size * 0.755),
            width: size * 0.010
        )
        drawCurve(
            from: CGPoint(x: size * 0.820, y: size * 0.405),
            control1: CGPoint(x: size * 0.720, y: size * 0.480),
            control2: CGPoint(x: size * 0.720, y: size * 0.575),
            to: CGPoint(x: size * 0.820, y: size * 0.640),
            width: size * 0.010
        )

        NSShadow().set()
    }

    private func drawSlabMonogram() {
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.66)
        shadow.shadowBlurRadius = size * 0.014
        shadow.shadowOffset = NSSize(width: size * 0.018, height: -size * 0.018)
        shadow.set()

        let left = slabPath(x: size * 0.255, y: size * 0.215, width: size * 0.150, height: size * 0.570, slant: size * 0.060)
        let right = slabPath(x: size * 0.520, y: size * 0.215, width: size * 0.150, height: size * 0.570, slant: size * 0.060)
        let cross = slabPath(x: size * 0.335, y: size * 0.455, width: size * 0.270, height: size * 0.118, slant: size * 0.030)

        color(4, 6, 7).setStroke()
        color(247, 246, 238).setFill()
        for slab in [left, right] {
            slab.lineJoinStyle = .round
            slab.fill()
            slab.lineWidth = size * 0.020
            slab.stroke()
        }

        color(255, 128, 20).setFill()
        cross.fill()
        color(4, 6, 7).setStroke()
        cross.lineWidth = size * 0.014
        cross.stroke()

        NSShadow().set()
    }

    private func drawClipCorners() {
        color(255, 126, 19).setStroke()
        let lineWidth = size * 0.018
        let cornerLength = size * 0.120
        let inset = size * 0.145

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

    private func drawFineBorder() {
        let rect = NSRect(x: 0, y: 0, width: size, height: size)
        let inset = size * 0.026
        let border = NSBezierPath(roundedRect: rect.insetBy(dx: inset, dy: inset), xRadius: size * 0.160, yRadius: size * 0.160)
        color(255, 255, 255, 0.045).setStroke()
        border.lineWidth = size * 0.0035
        border.stroke()
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
