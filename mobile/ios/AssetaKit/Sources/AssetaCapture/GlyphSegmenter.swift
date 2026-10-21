import CoreGraphics
import Foundation
import ImageIO

/// 8-bit RGBA pixels (row-major, top row first) of an image being analysed.
struct PixelImage: Sendable {
    let width: Int
    let height: Int
    var rgba: [UInt8]

    init(width: Int, height: Int, rgba: [UInt8]) {
        self.width = width
        self.height = height
        self.rgba = rgba
    }

    init?(cgImage: CGImage) {
        let w = cgImage.width, h = cgImage.height
        guard w > 0, h > 0 else { return nil }
        var buffer = [UInt8](repeating: 0, count: w * h * 4)
        let drawn: Bool = buffer.withUnsafeMutableBytes { raw in
            guard let ctx = CGContext(data: raw.baseAddress, width: w, height: h, bitsPerComponent: 8,
                                      bytesPerRow: w * 4, space: CGColorSpaceCreateDeviceRGB(),
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
            ctx.draw(cgImage, in: CGRect(x: 0, y: 0, width: w, height: h))
            return true
        }
        guard drawn else { return nil }
        self.init(width: w, height: h, rgba: buffer)
    }

    func makeCGImage() -> CGImage? {
        var copy = rgba
        return copy.withUnsafeMutableBytes { raw -> CGImage? in
            CGContext(data: raw.baseAddress, width: width, height: height, bitsPerComponent: 8, bytesPerRow: width * 4,
                      space: CGColorSpaceCreateDeviceRGB(),
                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)?.makeImage()
        }
    }

    /// Rotates around the centre by `degrees` (counter-clockwise in image space), filling with the
    /// top-left pixel colour so no artificial edges appear.
    func rotated(by degrees: Double) -> PixelImage? {
        guard let source = makeCGImage() else { return nil }
        var out = [UInt8](repeating: 0, count: width * height * 4)
        let ok: Bool = out.withUnsafeMutableBytes { raw in
            guard let ctx = CGContext(data: raw.baseAddress, width: width, height: height, bitsPerComponent: 8,
                                      bytesPerRow: width * 4, space: CGColorSpaceCreateDeviceRGB(),
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
            ctx.setFillColor(red: CGFloat(rgba[0]) / 255, green: CGFloat(rgba[1]) / 255,
                             blue: CGFloat(rgba[2]) / 255, alpha: 1)
            ctx.fill(CGRect(x: 0, y: 0, width: width, height: height))
            ctx.translateBy(x: CGFloat(width) / 2, y: CGFloat(height) / 2)
            ctx.rotate(by: CGFloat(degrees * .pi / 180))
            ctx.translateBy(x: -CGFloat(width) / 2, y: -CGFloat(height) / 2)
            ctx.interpolationQuality = .high
            ctx.draw(source, in: CGRect(x: 0, y: 0, width: width, height: height))
            return true
        }
        return ok ? PixelImage(width: width, height: height, rgba: out) : nil
    }

    /// Decodes image bytes, applies EXIF orientation and downsamples so the long side ≤ `maxSide`.
    static func decode(_ data: Data, maxSide: Int) -> CGImage? {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
        let options: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: maxSide,
        ]
        return CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary)
    }
}

/// Axis-aligned bounding box of a connected component (inclusive pixel coordinates).
struct GlyphBox: Equatable, Sendable {
    var x0: Int, y0: Int, x1: Int, y1: Int
    var area: Int

    var width: Int { x1 - x0 + 1 }
    var height: Int { y1 - y0 + 1 }
    var centerX: Double { Double(x0 + x1) / 2 }
    var centerY: Double { Double(y0 + y1) / 2 }

    mutating func merge(_ other: GlyphBox) {
        x0 = min(x0, other.x0); y0 = min(y0, other.y0)
        x1 = max(x1, other.x1); y1 = max(y1, other.y1)
        area += other.area
    }
}

/// One candidate text row of glyph-sized components, left to right.
struct GlyphRow: Sendable {
    var glyphs: [GlyphBox]
    /// Index of the glyph a geometric decimal point follows (LCD dot), if exactly one was found.
    var dotAfter: Int?
    /// More than one dot-like mark in the row: the decimal position is ambiguous.
    var ambiguousDots: Bool
    /// Index of a glyph sitting on a red cell at the right end (mechanical drum tenths wheel).
    var redTenths: Int?
    var medianHeight: Int { glyphs.map(\.height).sorted()[glyphs.count / 2] }
    var medianWidth: Int { glyphs.map(\.width).sorted()[glyphs.count / 2] }
}

struct Segmentation: Sendable {
    let image: PixelImage
    /// Foreground (ink) mask after binarization, same size as `image`.
    let mask: [Bool]
    /// Candidate rows, most prominent (tallest glyphs) first.
    let rows: [GlyphRow]
}

/// Classic document-analysis pipeline tuned for meter displays: median filter (salt-and-pepper
/// noise), global Otsu for ink polarity, local-mean adaptive threshold (glare, dim light),
/// connected components, per-column merge (7-segment pieces), row chaining, decimal-dot and
/// red-tenths-cell detection. Pure CPU code over an RGBA buffer, identical on iOS and macOS.
enum GlyphSegmenter {
    static func segment(_ image: PixelImage) -> Segmentation {
        let w = image.width, h = image.height
        let luma = medianFiltered(luminance(image), w: w, h: h)
        let fgBright = brightIsMinority(luma)
        let mask = adaptiveMask(luma, w: w, h: h, foregroundBright: fgBright)
        let components = connectedComponents(mask, w: w, h: h)
        let minHeight = max(8, h / 40)
        let glyphLike = components.filter { c in
            c.x0 > 0 && c.y0 > 0 && c.x1 < w - 1 && c.y1 < h - 1 && c.height >= minHeight && c.area >= 12
                && c.height <= h * 8 / 10 && Double(c.height) / Double(c.width) >= 0.9
                && Double(c.height) / Double(c.width) <= 12
        }
        let glyphs = mergeColumns(glyphLike)
        var rows = chainRows(glyphs).filter { $0.glyphs.count >= 3 }
        for index in rows.indices {
            locateDot(&rows[index], among: components)
            rows[index].redTenths = redTenthsIndex(rows[index], image: image, mask: mask)
        }
        rows.sort { ($0.medianHeight, $0.glyphs.count) > ($1.medianHeight, $1.glyphs.count) }
        return Segmentation(image: image, mask: mask, rows: rows)
    }

    /// Skew of a row in degrees from a least-squares fit through glyph centres.
    static func skewDegrees(_ row: GlyphRow) -> Double {
        guard row.glyphs.count >= 3 else { return 0 }
        let xs = row.glyphs.map(\.centerX), ys = row.glyphs.map(\.centerY)
        let mx = xs.reduce(0, +) / Double(xs.count), my = ys.reduce(0, +) / Double(ys.count)
        var num = 0.0, den = 0.0
        for i in xs.indices {
            num += (xs[i] - mx) * (ys[i] - my)
            den += (xs[i] - mx) * (xs[i] - mx)
        }
        return den == 0 ? 0 : atan2(num, den) * 180 / .pi
    }

    // MARK: - Binarization

    static func luminance(_ image: PixelImage) -> [Float] {
        var out = [Float](repeating: 0, count: image.width * image.height)
        image.rgba.withUnsafeBufferPointer { px in
            for i in out.indices {
                out[i] = 0.299 * Float(px[4 * i]) + 0.587 * Float(px[4 * i + 1]) + 0.114 * Float(px[4 * i + 2])
            }
        }
        return out
    }

    static func medianFiltered(_ values: [Float], w: Int, h: Int) -> [Float] {
        guard w > 2, h > 2 else { return values }
        var out = values
        var window = [Float](repeating: 0, count: 9)
        for r in 1..<(h - 1) {
            for c in 1..<(w - 1) {
                var k = 0
                for dy in -1...1 {
                    let base = (r + dy) * w + c
                    window[k] = values[base - 1]; window[k + 1] = values[base]; window[k + 2] = values[base + 1]
                    k += 3
                }
                // Insertion sort of 9 values is faster than a general sort here.
                for i in 1..<9 {
                    let v = window[i]
                    var j = i - 1
                    while j >= 0 && window[j] > v { window[j + 1] = window[j]; j -= 1 }
                    window[j + 1] = v
                }
                out[r * w + c] = window[4]
            }
        }
        return out
    }

    /// Otsu threshold; ink is the minority class (displays are mostly background).
    static func brightIsMinority(_ luma: [Float]) -> Bool {
        let threshold = otsu(luma)
        let above = luma.reduce(0) { $0 + (Int($1) > threshold ? 1 : 0) }
        return above * 2 < luma.count
    }

    static func otsu(_ values: [Float]) -> Int {
        var hist = [Double](repeating: 0, count: 256)
        for v in values { hist[min(255, max(0, Int(v)))] += 1 }
        let total = Double(values.count)
        let sumAll = (0..<256).reduce(0.0) { $0 + Double($1) * hist[$1] }
        var weightB = 0.0, sumB = 0.0, best = -1.0, threshold = 127
        for t in 0..<256 {
            weightB += hist[t]
            guard weightB > 0 else { continue }
            let weightF = total - weightB
            if weightF <= 0 { break }
            sumB += Double(t) * hist[t]
            let meanB = sumB / weightB, meanF = (sumAll - sumB) / weightF
            let between = weightB * weightF * (meanB - meanF) * (meanB - meanF)
            if between > best { best = between; threshold = t }
        }
        return threshold
    }

    static func adaptiveMask(_ luma: [Float], w: Int, h: Int, foregroundBright: Bool) -> [Bool] {
        var integral = [Double](repeating: 0, count: (w + 1) * (h + 1))
        for r in 0..<h {
            var rowSum = 0.0
            for c in 0..<w {
                rowSum += Double(luma[r * w + c])
                integral[(r + 1) * (w + 1) + c + 1] = integral[r * (w + 1) + c + 1] + rowSum
            }
        }
        let sorted = luma.sorted()
        let contrast = max(sorted[sorted.count * 19 / 20] - sorted[sorted.count / 20], 1)
        let k = 0.18 * contrast
        let radius = max(h / 6, 8)
        var mask = [Bool](repeating: false, count: w * h)
        for r in 0..<h {
            let y0 = max(0, r - radius), y1 = min(h - 1, r + radius)
            for c in 0..<w {
                let x0 = max(0, c - radius), x1 = min(w - 1, c + radius)
                let n = Double((x1 - x0 + 1) * (y1 - y0 + 1))
                let sum = integral[(y1 + 1) * (w + 1) + x1 + 1] - integral[y0 * (w + 1) + x1 + 1]
                    - integral[(y1 + 1) * (w + 1) + x0] + integral[y0 * (w + 1) + x0]
                let diff = luma[r * w + c] - Float(sum / n)
                mask[r * w + c] = foregroundBright ? diff > k : diff < -k
            }
        }
        return mask
    }

    // MARK: - Components and rows

    static func connectedComponents(_ mask: [Bool], w: Int, h: Int) -> [GlyphBox] {
        var visited = [Bool](repeating: false, count: w * h)
        var boxes: [GlyphBox] = []
        var stack: [Int] = []
        for start in 0..<(w * h) where mask[start] && !visited[start] {
            visited[start] = true
            stack.append(start)
            var box = GlyphBox(x0: start % w, y0: start / w, x1: start % w, y1: start / w, area: 0)
            while let p = stack.popLast() {
                box.area += 1
                let x = p % w, y = p / w
                box.x0 = min(box.x0, x); box.x1 = max(box.x1, x)
                box.y0 = min(box.y0, y); box.y1 = max(box.y1, y)
                if x > 0, mask[p - 1], !visited[p - 1] { visited[p - 1] = true; stack.append(p - 1) }
                if x < w - 1, mask[p + 1], !visited[p + 1] { visited[p + 1] = true; stack.append(p + 1) }
                if y > 0, mask[p - w], !visited[p - w] { visited[p - w] = true; stack.append(p - w) }
                if y < h - 1, mask[p + w], !visited[p + w] { visited[p + w] = true; stack.append(p + w) }
            }
            boxes.append(box)
        }
        return boxes
    }

    /// Merges components stacked in the same column (7-segment pieces, broken strokes).
    static func mergeColumns(_ boxes: [GlyphBox]) -> [GlyphBox] {
        var merged: [GlyphBox] = []
        for box in boxes.sorted(by: { $0.x0 < $1.x0 }) {
            if let i = merged.lastIndex(where: { m in
                let overlap = min(m.x1, box.x1) - max(m.x0, box.x0)
                return overlap > min(m.width, box.width) / 2 && abs(m.centerY - box.centerY) < Double(max(m.height, box.height))
            }) {
                merged[i].merge(box)
            } else {
                merged.append(box)
            }
        }
        return merged
    }

    /// Greedy left-to-right chaining of similar-height glyphs with small gaps (tolerates skew).
    static func chainRows(_ glyphs: [GlyphBox]) -> [GlyphRow] {
        var used = [Bool](repeating: false, count: glyphs.count)
        let order = glyphs.indices.sorted { glyphs[$0].x0 < glyphs[$1].x0 }
        var rows: [GlyphRow] = []
        for start in order where !used[start] {
            used[start] = true
            var chain = [glyphs[start]]
            var current = glyphs[start]
            for next in order where !used[next] && glyphs[next].x0 > current.x0 {
                let candidate = glyphs[next]
                let ratio = Double(candidate.height) / Double(current.height)
                let gap = candidate.x0 - current.x1
                if ratio > 0.62, ratio < 1.6, abs(candidate.centerY - current.centerY) < Double(current.height) / 2,
                   gap < current.height, gap > -current.width / 2 {
                    used[next] = true
                    chain.append(candidate)
                    current = candidate
                }
            }
            rows.append(GlyphRow(glyphs: chain, dotAfter: nil, ambiguousDots: false, redTenths: nil))
        }
        return rows
    }

    static func locateDot(_ row: inout GlyphRow, among components: [GlyphBox]) {
        let mh = row.medianHeight
        var found: [Int] = []
        for d in components {
            guard d.height >= max(3, mh / 14), d.height * 100 <= mh * 35, d.width * 100 <= mh * 35,
                  Double(d.area) >= 0.45 * Double(d.width * d.height) else { continue }
            guard let left = row.glyphs.lastIndex(where: { $0.x1 <= d.x0 + 1 }), left + 1 < row.glyphs.count,
                  row.glyphs[left + 1].x0 >= d.x1 - 1 else { continue }
            let baseline = Double(row.glyphs[left].y1 + row.glyphs[left + 1].y1) / 2
            if Double(d.y1) >= baseline - Double(mh) / 5, Double(d.y1) <= baseline + Double(mh) / 8 {
                found.append(left)
            }
        }
        let unique = Set(found)
        row.dotAfter = unique.count == 1 ? unique.first : nil
        row.ambiguousDots = unique.count > 1
    }

    /// The right-most glyph whose surrounding background is saturated red (drum tenths wheel).
    static func redTenthsIndex(_ row: GlyphRow, image: PixelImage, mask: [Bool]) -> Int? {
        guard let last = row.glyphs.indices.last, last >= 1 else { return nil }
        func isRed(_ g: GlyphBox) -> Bool {
            var r = 0.0, gr = 0.0, b = 0.0, n = 0.0
            let ex = g.width / 3, ey = g.height / 5
            for y in max(0, g.y0 - ey)...min(image.height - 1, g.y1 + ey) {
                for x in max(0, g.x0 - ex)...min(image.width - 1, g.x1 + ex) where !mask[y * image.width + x] {
                    let i = 4 * (y * image.width + x)
                    r += Double(image.rgba[i]); gr += Double(image.rgba[i + 1]); b += Double(image.rgba[i + 2]); n += 1
                }
            }
            guard n > 0 else { return false }
            r /= n; gr /= n; b /= n
            return r > 1.8 * max(gr, b) && r - max(gr, b) > 25
        }
        // Only the last wheel may be the tenths wheel, and the others must not be red.
        guard isRed(row.glyphs[last]), !isRed(row.glyphs[last - 1]) else { return nil }
        return last
    }
}
