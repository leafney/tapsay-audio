// SPDX-License-Identifier: GPL-3.0-only
// An original two-channel waveform icon; no upstream artwork is used.
import AppKit
import Foundation

let directory = URL(fileURLWithPath: CommandLine.arguments[1])
try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
for points in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let size = points * scale
        let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size,
            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
            colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
        let extent = CGFloat(size)
        NSColor(calibratedRed: 0.12, green: 0.35, blue: 0.43, alpha: 1).setFill()
        NSBezierPath(roundedRect: NSRect(x: 0, y: 0, width: extent, height: extent),
            xRadius: extent * 0.21, yRadius: extent * 0.21).fill()
        NSColor.white.setFill()
        let heights: [CGFloat] = [0.25, 0.5, 0.72, 0.72, 0.5, 0.25]
        for (index, height) in heights.enumerated() {
            NSBezierPath(roundedRect: NSRect(x: extent * (0.18 + CGFloat(index) * 0.11),
                y: extent * (1 - height) / 2, width: extent * 0.075, height: extent * height),
                xRadius: extent * 0.035, yRadius: extent * 0.035).fill()
        }
        NSGraphicsContext.restoreGraphicsState()
        let name = "icon_\(points)x\(points)" + (scale == 2 ? "@2x" : "") + ".png"
        try bitmap.representation(using: .png, properties: [:])!.write(to: directory.appendingPathComponent(name))
    }
}
