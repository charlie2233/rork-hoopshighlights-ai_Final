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
        drawBasketballField()
        drawClipFrame()
        drawWordTabs()
        drawMonogram()
        drawPlayCut()
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
        color(255, 255, 248, 0.065).setStroke()

        let baseline = NSBezierPath()
        baseline.move(to: CGPoint(x: size * 0.075, y: size * 0.265))
        baseline.line(to: CGPoint(x: size * 0.925, y: size * 0.265))
        baseline.lineWidth = size * 0.007
        baseline.stroke()

        let arc = NSBezierPath(ovalIn: NSRect(
            x: size * 0.250,
            y: size * 0.205,
            width: size * 0.500,
            height: size * 0.500
        ))
        arc.lineWidth = size * 0.005
        arc.stroke()

        let halfCourt = NSBezierPath()
        halfCourt.move(to: CGPoint(x: size * 0.500, y: size * 0.080))
        halfCourt.line(to: CGPoint(x: size * 0.500, y: size * 0.920))
        halfCourt.lineWidth = size * 0.004
        halfCourt.stroke()
    }

    private func drawBasketballField() {
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.35)
        shadow.shadowBlurRadius = size * 0.018
        shadow.shadowOffset = NSSize(width: size * 0.010, height: -size * 0.012)
        shadow.set()

        let ball = NSBezierPath(ovalIn: NSRect(
            x: size * 0.570,
            y: size * 0.240,
            width: size * 0.365,
            height: size * 0.365
        ))
        color(255, 128, 20).setFill()
        ball.fill()

        color(47, 20, 8, 0.72).setStroke()
        drawCurve(
            from: CGPoint(x: size * 0.618, y: size * 0.310),
            control1: CGPoint(x: size * 0.720, y: size * 0.410),
            control2: CGPoint(x: size * 0.745, y: size * 0.495),
            to: CGPoint(x: size * 0.910, y: size * 0.520),
            width: size * 0.012
        )
        drawCurve(
            from: CGPoint(x: size * 0.730, y: size * 0.250),
            control1: CGPoint(x: size * 0.695, y: size * 0.350),
            control2: CGPoint(x: size * 0.705, y: size * 0.505),
            to: CGPoint(x: size * 0.765, y: size * 0.595),
            width: size * 0.010
        )
        let seam = NSBezierPath()
        seam.move(to: CGPoint(x: size * 0.735, y: size * 0.423))
        seam.line(to: CGPoint(x: size * 0.925, y: size * 0.423))
        seam.lineWidth = size * 0.010
        seam.stroke()

        NSShadow().set()
    }

    private func drawClipFrame() {
        let topBar = NSBezierPath()
        topBar.move(to: CGPoint(x: size * 0.090, y: size * 0.755))
        topBar.line(to: CGPoint(x: size * 0.785, y: size * 0.755))
        topBar.line(to: CGPoint(x: size * 0.865, y: size * 0.855))
        topBar.line(to: CGPoint(x: size * 0.165, y: size * 0.855))
        topBar.close()
        color(255, 126, 19).setFill()
        topBar.fill()

        let leftRail = NSBezierPath()
        leftRail.move(to: CGPoint(x: size * 0.075, y: size * 0.210))
        leftRail.line(to: CGPoint(x: size * 0.230, y: size * 0.210))
        leftRail.line(to: CGPoint(x: size * 0.165, y: size * 0.330))
        leftRail.line(to: CGPoint(x: size * 0.075, y: size * 0.330))
        leftRail.close()
        color(255, 126, 19).setFill()
        leftRail.fill()

        let bottomBar = NSBezierPath()
        bottomBar.move(to: CGPoint(x: size * 0.145, y: size * 0.105))
        bottomBar.line(to: CGPoint(x: size * 0.880, y: size * 0.105))
        bottomBar.line(to: CGPoint(x: size * 0.805, y: size * 0.215))
        bottomBar.line(to: CGPoint(x: size * 0.205, y: size * 0.215))
        bottomBar.close()
        color(255, 126, 19).setFill()
        bottomBar.fill()
    }

    private func drawWordTabs() {
        let topFont = NSFont(name: "AvenirNextCondensed-Heavy", size: size * 0.055)
            ?? NSFont.systemFont(ofSize: size * 0.052, weight: .black)
        let topAttributes: [NSAttributedString.Key: Any] = [
            .font: topFont,
            .foregroundColor: color(5, 7, 9),
            .kern: size * 0.006
        ]
        "HOOP".draw(
            at: CGPoint(x: size * 0.190, y: size * 0.785),
            withAttributes: topAttributes
        )

        let bottomFont = NSFont(name: "AvenirNextCondensed-Heavy", size: size * 0.070)
            ?? NSFont.systemFont(ofSize: size * 0.066, weight: .black)
        let bottomAttributes: [NSAttributedString.Key: Any] = [
            .font: bottomFont,
            .foregroundColor: color(5, 7, 9),
            .kern: size * 0.005
        ]
        "CLIPS".draw(
            at: CGPoint(x: size * 0.480, y: size * 0.127),
            withAttributes: bottomAttributes
        )
    }

    private func drawMonogram() {
        let font = NSFont(name: "AvenirNextCondensed-HeavyItalic", size: size * 0.560)
            ?? NSFont(name: "DINCondensed-Bold", size: size * 0.545)
            ?? NSFont.systemFont(ofSize: size * 0.540, weight: .black)
        let shadow = NSShadow()
        shadow.shadowColor = color(0, 0, 0, 0.66)
        shadow.shadowBlurRadius = size * 0.012
        shadow.shadowOffset = NSSize(width: size * 0.018, height: -size * 0.018)

        let attributes: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: color(248, 247, 239),
            .strokeColor: color(3, 5, 7),
            .strokeWidth: -6.8,
            .shadow: shadow,
            .kern: 0
        ]
        let text = "HC"
        let textSize = text.size(withAttributes: attributes)
        let point = CGPoint(
            x: (size - textSize.width) / 2 - size * 0.030,
            y: size * 0.288
        )
        text.draw(at: point, withAttributes: attributes)
    }

    private func drawPlayCut() {
        let triangle = NSBezierPath()
        triangle.move(to: CGPoint(x: size * 0.720, y: size * 0.375))
        triangle.line(to: CGPoint(x: size * 0.720, y: size * 0.555))
        triangle.line(to: CGPoint(x: size * 0.875, y: size * 0.465))
        triangle.close()
        color(255, 255, 248).setFill()
        triangle.fill()

        color(3, 5, 7).setStroke()
        triangle.lineWidth = size * 0.018
        triangle.stroke()

        color(255, 126, 19).setStroke()
        let cut = NSBezierPath()
        cut.move(to: CGPoint(x: size * 0.265, y: size * 0.250))
        cut.line(to: CGPoint(x: size * 0.855, y: size * 0.780))
        cut.lineWidth = size * 0.014
        cut.lineCapStyle = .round
        cut.stroke()
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
