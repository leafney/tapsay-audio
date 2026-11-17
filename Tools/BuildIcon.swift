// SPDX-License-Identifier: GPL-3.0-only
// Original five-channel waveform icon aligned with the TapSay brand; no upstream artwork is used.
import AppKit
import Foundation

let directory = URL(fileURLWithPath: CommandLine.arguments[1])
try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
let style = CommandLine.arguments.count > 3 ? CommandLine.arguments[3] : "driver"
guard style == "driver" || style == "uninstaller" else {
    throw NSError(domain: "TapSayAudioIcon", code: 2,
                  userInfo: [NSLocalizedDescriptionKey: "Unsupported icon style: \(style)"])
}
let teal = NSColor(srgbRed: 80.0 / 255.0, green: 166.0 / 255.0, blue: 190.0 / 255.0, alpha: 1.0)
let offWhite = NSColor(srgbRed: 251.0 / 255.0, green: 252.0 / 255.0, blue: 255.0 / 255.0, alpha: 1.0)
let coral = NSColor(srgbRed: 239.0 / 255.0, green: 83.0 / 255.0, blue: 109.0 / 255.0, alpha: 1.0)
let bars: [(x: CGFloat, y: CGFloat, width: CGFloat, height: CGFloat)] = [
    (65.0 / 256.0, 111.0 / 256.0, 18.0 / 256.0, 34.0 / 256.0),
    (92.0 / 256.0, 89.0 / 256.0, 18.0 / 256.0, 78.0 / 256.0),
    (119.0 / 256.0, 62.0 / 256.0, 18.0 / 256.0, 132.0 / 256.0),
    (146.0 / 256.0, 89.0 / 256.0, 18.0 / 256.0, 78.0 / 256.0),
    (173.0 / 256.0, 111.0 / 256.0, 18.0 / 256.0, 34.0 / 256.0),
]
var pngBySize: [Int: Data] = [:]
for points in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let size = points * scale
        let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size,
            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
            colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
        let extent = CGFloat(size)
        teal.setFill()
        NSBezierPath(roundedRect: NSRect(x: extent * 0.0625, y: extent * 0.0625,
            width: extent * 0.875, height: extent * 0.875),
            xRadius: extent * 0.199, yRadius: extent * 0.199).fill()
        offWhite.setFill()
        for bar in bars {
            let width = extent * bar.width
            NSBezierPath(roundedRect: NSRect(x: extent * bar.x, y: extent * bar.y,
                width: width, height: extent * bar.height),
                xRadius: width / 2, yRadius: width / 2).fill()
        }
        if style == "uninstaller" {
            let badgeCenter = NSPoint(x: extent * 0.76, y: extent * 0.24)
            let badgeRadius = extent * 0.118
            teal.setStroke()
            let badgeRing = NSBezierPath(ovalIn: NSRect(
                x: badgeCenter.x - badgeRadius - extent * 0.018,
                y: badgeCenter.y - badgeRadius - extent * 0.018,
                width: (badgeRadius + extent * 0.018) * 2,
                height: (badgeRadius + extent * 0.018) * 2))
            badgeRing.lineWidth = extent * 0.036
            badgeRing.stroke()
            coral.setFill()
            NSBezierPath(ovalIn: NSRect(
                x: badgeCenter.x - badgeRadius,
                y: badgeCenter.y - badgeRadius,
                width: badgeRadius * 2,
                height: badgeRadius * 2)).fill()

            let bodyHeight = extent * 0.084
            let lidHeight = extent * 0.019
            let handleHeight = extent * 0.012
            let glyphHeight = bodyHeight + extent * 0.008 + lidHeight + handleHeight
            let glyphBottom = badgeCenter.y - glyphHeight / 2
            let bodyTop = glyphBottom + bodyHeight
            let lidBottom = bodyTop + extent * 0.008
            let handleBottom = lidBottom + lidHeight
            let bodyTopHalfWidth = extent * 0.046
            let bodyBottomHalfWidth = extent * 0.039
            let bodyCorner = extent * 0.010

            offWhite.setFill()
            let body = NSBezierPath()
            body.move(to: NSPoint(
                x: badgeCenter.x - bodyTopHalfWidth + bodyCorner,
                y: bodyTop))
            body.line(to: NSPoint(
                x: badgeCenter.x + bodyTopHalfWidth - bodyCorner,
                y: bodyTop))
            body.curve(
                to: NSPoint(
                    x: badgeCenter.x + bodyTopHalfWidth,
                    y: bodyTop - bodyCorner),
                controlPoint1: NSPoint(
                    x: badgeCenter.x + bodyTopHalfWidth,
                    y: bodyTop),
                controlPoint2: NSPoint(
                    x: badgeCenter.x + bodyTopHalfWidth,
                    y: bodyTop - bodyCorner))
            body.line(to: NSPoint(
                x: badgeCenter.x + bodyBottomHalfWidth,
                y: glyphBottom + bodyCorner))
            body.curve(
                to: NSPoint(
                    x: badgeCenter.x + bodyBottomHalfWidth - bodyCorner,
                    y: glyphBottom),
                controlPoint1: NSPoint(
                    x: badgeCenter.x + bodyBottomHalfWidth,
                    y: glyphBottom),
                controlPoint2: NSPoint(
                    x: badgeCenter.x + bodyBottomHalfWidth,
                    y: glyphBottom))
            body.line(to: NSPoint(
                x: badgeCenter.x - bodyBottomHalfWidth + bodyCorner,
                y: glyphBottom))
            body.curve(
                to: NSPoint(
                    x: badgeCenter.x - bodyBottomHalfWidth,
                    y: glyphBottom + bodyCorner),
                controlPoint1: NSPoint(
                    x: badgeCenter.x - bodyBottomHalfWidth,
                    y: glyphBottom),
                controlPoint2: NSPoint(
                    x: badgeCenter.x - bodyBottomHalfWidth,
                    y: glyphBottom))
            body.line(to: NSPoint(
                x: badgeCenter.x - bodyTopHalfWidth,
                y: bodyTop - bodyCorner))
            body.curve(
                to: NSPoint(
                    x: badgeCenter.x - bodyTopHalfWidth + bodyCorner,
                    y: bodyTop),
                controlPoint1: NSPoint(
                    x: badgeCenter.x - bodyTopHalfWidth,
                    y: bodyTop),
                controlPoint2: NSPoint(
                    x: badgeCenter.x - bodyTopHalfWidth,
                    y: bodyTop))
            body.close()
            body.fill()

            NSBezierPath(roundedRect: NSRect(
                x: badgeCenter.x - extent * 0.062,
                y: lidBottom,
                width: extent * 0.124, height: lidHeight),
                xRadius: lidHeight / 2, yRadius: lidHeight / 2).fill()
            NSBezierPath(roundedRect: NSRect(
                x: badgeCenter.x - extent * 0.024,
                y: handleBottom,
                width: extent * 0.048, height: handleHeight),
                xRadius: handleHeight / 2, yRadius: handleHeight / 2).fill()
        }
        NSGraphicsContext.restoreGraphicsState()
        let name = "icon_\(points)x\(points)" + (scale == 2 ? "@2x" : "") + ".png"
        let png = bitmap.representation(using: .png, properties: [:])!
        try png.write(to: directory.appendingPathComponent(name))
        pngBySize[size] = png
    }
}

if CommandLine.arguments.count > 2 {
    func appendBigEndian(_ value: UInt32, to data: inout Data) {
        data.append(UInt8((value >> 24) & 0xff))
        data.append(UInt8((value >> 16) & 0xff))
        data.append(UInt8((value >> 8) & 0xff))
        data.append(UInt8(value & 0xff))
    }

    let iconTypes: [(size: Int, type: String)] = [
        (16, "icp4"), (32, "icp5"), (64, "icp6"), (128, "ic07"),
        (256, "ic08"), (512, "ic09"), (1024, "ic10")
    ]
    var icns = Data("icns".utf8)
    var totalSize = UInt32(8)
    for (size, _) in iconTypes {
        guard let png = pngBySize[size] else {
            throw NSError(domain: "TapSayAudioIcon", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "缺少 \(size)x\(size) 图标"])
        }
        totalSize += UInt32(8 + png.count)
    }
    appendBigEndian(totalSize, to: &icns)
    for (size, type) in iconTypes {
        icns.append(contentsOf: type.utf8)
        appendBigEndian(UInt32(8 + pngBySize[size]!.count), to: &icns)
        icns.append(pngBySize[size]!)
    }
    try icns.write(to: URL(fileURLWithPath: CommandLine.arguments[2]))
}
