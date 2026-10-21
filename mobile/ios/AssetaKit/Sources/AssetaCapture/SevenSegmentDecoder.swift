import Foundation

/// Deterministic 7-segment decoder used as an independent second opinion for LCD/LED meters.
///
/// Each glyph is sampled at the seven segment positions inside a cell spanning the row's common
/// top/bottom and the row's median digit width (right-aligned, because a `1` lights only the right
/// segments). A segment is on (ink ≥ 45%), off (≤ 15%) or uncertain; any uncertain segment or an
/// unknown pattern fails the whole row, so proportional fonts simply produce no opinion.
enum SevenSegmentDecoder {
    private static let patterns: [String: Character] = [
        "abcdef": "0", "bc": "1", "abdeg": "2", "abcdg": "3", "bcfg": "4", "acdfg": "5",
        "acdefg": "6", "cdefg": "6", "abc": "7", "abcf": "7", "abcdefg": "8", "abcdfg": "9", "abcfg": "9",
    ]

    /// (segment, u-range, v-range) in cell-relative coordinates, v measured from the top.
    private static let regions: [(Character, ClosedRange<Double>, ClosedRange<Double>)] = [
        ("a", 0.3...0.7, 0.0...0.12), ("b", 0.8...1.0, 0.2...0.4), ("c", 0.8...1.0, 0.6...0.8),
        ("d", 0.3...0.7, 0.88...1.0), ("e", 0.0...0.2, 0.6...0.8), ("f", 0.0...0.2, 0.2...0.4),
        ("g", 0.3...0.7, 0.44...0.56),
    ]

    static func decode(_ row: GlyphRow, _ segmentation: Segmentation) -> [Character]? {
        let tops = row.glyphs.map(\.y0).sorted(), bottoms = row.glyphs.map(\.y1).sorted()
        let top = tops[tops.count / 2], bottom = bottoms[bottoms.count / 2]
        let cellHeight = bottom - top + 1
        let cellWidth = row.medianWidth
        guard cellHeight >= 12, cellWidth >= 4 else { return nil }
        var out: [Character] = []
        for glyph in row.glyphs {
            if glyph.width * 100 < cellWidth * 40 {
                // A narrow full-height stroke is a `1`.
                guard glyph.height * 100 >= cellHeight * 80 else { return nil }
                out.append("1")
                continue
            }
            var lit = ""
            for (segment, us, vs) in regions {
                guard let ratio = inkRatio(segmentation, x1: glyph.x1, width: cellWidth, top: top,
                                           height: cellHeight, us: us, vs: vs) else { return nil }
                if ratio >= 0.45 { lit.append(segment) } else if ratio > 0.15 { return nil }
            }
            guard let digit = patterns[lit] else { return nil }
            out.append(digit)
        }
        return out
    }

    private static func inkRatio(_ s: Segmentation, x1: Int, width: Int, top: Int, height: Int,
                                 us: ClosedRange<Double>, vs: ClosedRange<Double>) -> Double? {
        let x0 = x1 - width + 1
        let left = x0 + Int(us.lowerBound * Double(width)), right = x0 + Int(us.upperBound * Double(width)) - 1
        let upper = top + Int(vs.lowerBound * Double(height)), lower = top + Int(vs.upperBound * Double(height)) - 1
        guard left >= 0, upper >= 0, right < s.image.width, lower < s.image.height, right >= left, lower >= upper
        else { return nil }
        var ink = 0, total = 0
        for y in upper...lower {
            for x in left...right {
                total += 1
                if s.mask[y * s.image.width + x] { ink += 1 }
            }
        }
        return total == 0 ? nil : Double(ink) / Double(total)
    }
}
