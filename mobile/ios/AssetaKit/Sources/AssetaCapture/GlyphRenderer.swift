import CoreGraphics
import Foundation

/// Re-renders a segmented row as clean black glyphs on white with uniform spacing, a clear
/// decimal point where geometry found one, and bottom-aligned baselines. Vision reads this far
/// more reliably than the raw photo of a segmented or drum display.
enum GlyphRenderer {
    struct Rendered {
        let image: CGImage
        /// Horizontal pixel span of each glyph in `image` (same order as the row's glyphs).
        let glyphSpans: [ClosedRange<Double>]
    }

    static func render(_ row: GlyphRow, _ segmentation: Segmentation, scale: Double, gapFactor: Double) -> Rendered? {
        let source = segmentation.image
        let medianHeight = Double(row.medianHeight)
        guard medianHeight > 0 else { return nil }
        let s = scale / medianHeight
        let gap = medianHeight * gapFactor
        let margin = medianHeight * 0.6
        let dotSize = medianHeight * 0.16
        var totalWidth = margin * 2
        for (i, glyph) in row.glyphs.enumerated() {
            totalWidth += Double(glyph.width) + gap
            if row.dotAfter == i { totalWidth += dotSize + gap * 0.5 }
        }
        let tallest = Double(row.glyphs.map(\.height).max() ?? row.medianHeight)
        let width = Int((totalWidth * s).rounded(.up)), height = Int(((tallest + margin * 2) * s).rounded(.up))
        guard width > 0, height > 0, width < 8000,
              let ctx = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
                                  space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue)
        else { return nil }
        ctx.setFillColor(gray: 1, alpha: 1)
        ctx.fill(CGRect(x: 0, y: 0, width: width, height: height))
        ctx.setFillColor(gray: 0, alpha: 1)
        var x = margin
        var spans: [ClosedRange<Double>] = []
        for (i, glyph) in row.glyphs.enumerated() {
            // Bottom-align every glyph on a common baseline (CoreGraphics origin is bottom-left).
            for py in glyph.y0...glyph.y1 {
                var runStart: Int?
                for px in glyph.x0...(glyph.x1 + 1) {
                    let ink = px <= glyph.x1 && segmentation.mask[py * source.width + px]
                    if ink, runStart == nil { runStart = px }
                    if !ink, let start = runStart {
                        let ox = x + Double(start - glyph.x0)
                        let oy = margin + Double(glyph.y1 - py)
                        ctx.fill(CGRect(x: ox * s, y: oy * s, width: Double(px - start) * s + 0.5, height: s + 0.5))
                        runStart = nil
                    }
                }
            }
            spans.append((x * s)...((x + Double(glyph.width)) * s))
            x += Double(glyph.width) + gap
            if row.dotAfter == i {
                ctx.fillEllipse(in: CGRect(x: (x - gap * 0.5) * s, y: margin * s, width: dotSize * s, height: dotSize * s))
                x += dotSize + gap * 0.5
            }
        }
        guard let image = ctx.makeImage() else { return nil }
        return Rendered(image: image, glyphSpans: spans)
    }
}
