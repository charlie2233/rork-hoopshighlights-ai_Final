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
        drawCourtLines()
        drawEnergyBand()
        drawHoopRing()
        drawMonogram()
        drawCornerTab()
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

    private func drawCourtLines() {
        color(255, 255, 248, 0.075).setStroke()

        let baseline = NSBezierPath()
        baseline.move(to: CGPoint(x: size * 0.090, y: size * 0.220))
        baseline.line(to: CGPoint(x: size * 0.910, y: size * 0.220))
        baseline.lineWidth = size * 0.010
        baseline.stroke()

        let lane = NSBezierPath()
        lane.move(to: CGPoint(x: size * 0.145, y: size * 0.220))
        lane.line(to: CGPoint(x: size * 0.145, y: size * 0.760))
        lane.line(to: CGPoint(x: size * 0.430, y: size * 0.760))
        lane.line(to: CGPoint(x: size * 0.430, y: size * 0.220))
        lane.lineWidth = size * 0.008
        lane.stroke()

        let arc = NSBezierPath(ovalIn: NSRect(
            x: size * 0.255,
            y: size * 0.225,
            width: size * 0.510,
            height: size * 0.510
        ))
        arc.lineWidth = size * 0.006
        arc.stroke()
    }

    private func drawEnergyBand() {
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.35)
        shadow.shadowBlurRadius = size * 0.022
        shadow.shadowOffset = NSSize(width: size * 0.012, height: -size * 0.016)
        shadow.set()

        let topBand = NSBezierPath()
        topBand.move(to: CGPoint(x: size * 0.060, y: size * 0.690))
        topBand.line(to: CGPoint(x: size * 0.770, y: size * 0.690))
        topBand.line(to: CGPoint(x: size * 0.860, y: size * 0.820))
        topBand.line(to: CGPoint(x: size * 0.150, y: size * 0.820))
        topBand.close()
        color(255, 126, 19).setFill()
        topBand.fill()

        let bottomBand = NSBezierPath()
        bottomBand.move(to: CGPoint(x: size * 0.135, y: size * 0.125))
        bottomBand.line(to: CGPoint(x: size * 0.920, y: size * 0.125))
        bottomBand.line(to: CGPoint(x: size * 0.825, y: size * 0.235))
        bottomBand.line(to: CGPoint(x: size * 0.235, y: size * 0.235))
        bottomBand.close()
        color(255, 126, 19).setFill()
        bottomBand.fill()

        NSShadow().set()
    }

    private func drawHoopRing() {
        let outer = NSBezierPath(ovalIn: NSRect(
            x: size * 0.595,
            y: size * 0.290,
            width: size * 0.335,
            height: size * 0.335
        ))
        color(255, 126, 19).setFill()
        outer.fill()

        let inner = NSBezierPath(ovalIn: NSRect(
            x: size * 0.650,
            y: size * 0.345,
            width: size * 0.225,
            height: size * 0.225
        ))
        color(6, 8, 9).setFill()
        inner.fill()

        color(255, 246, 226, 0.22).setStroke()
        outer.lineWidth = size * 0.012
        outer.stroke()
    }

    private func drawMonogram() {
        let font = NSFont(name: "AvenirNextCondensed-HeavyItalic", size: size * 0.580)
            ?? NSFont(name: "DINCondensed-Bold", size: size * 0.560)
            ?? NSFont.systemFont(ofSize: size * 0.550, weight: .black)
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.58)
        shadow.shadowBlurRadius = size * 0.018
        shadow.shadowOffset = NSSize(width: size * 0.018, height: -size * 0.014)

        let attributes: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: color(248, 247, 239),
            .strokeColor: color(3, 5, 7),
            .strokeWidth: -5.5,
            .shadow: shadow,
            .kern: 0
        ]
        let text = "HC"
        let textSize = text.size(withAttributes: attributes)
        let point = CGPoint(
            x: (size - textSize.width) / 2 - size * 0.018,
            y: size * 0.265
        )
        text.draw(at: point, withAttributes: attributes)
    }

    private func drawCornerTab() {
        let tab = NSBezierPath()
        tab.move(to: CGPoint(x: size * 0.070, y: size * 0.070))
        tab.line(to: CGPoint(x: size * 0.295, y: size * 0.070))
        tab.line(to: CGPoint(x: size * 0.220, y: size * 0.152))
        tab.line(to: CGPoint(x: size * 0.070, y: size * 0.152))
        tab.close()
        color(255, 126, 19).setFill()
        tab.fill()

        let notch = NSBezierPath()
        notch.move(to: CGPoint(x: size * 0.315, y: size * 0.070))
        notch.line(to: CGPoint(x: size * 0.445, y: size * 0.070))
        notch.line(to: CGPoint(x: size * 0.370, y: size * 0.152))
        notch.line(to: CGPoint(x: size * 0.240, y: size * 0.152))
        notch.close()
        color(255, 172, 61, 0.48).setFill()
        notch.fill()
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
