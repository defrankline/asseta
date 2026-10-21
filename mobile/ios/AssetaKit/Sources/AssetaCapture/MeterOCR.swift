import CoreGraphics
import Foundation
import Vision

/// Outcome of on-device OCR of one meter photo. OCR output is evidence, not proof: the user always
/// confirms or corrects it, and the original photo and raw text are kept.
public struct MeterOCRResult: Sendable, Equatable {
    /// Parsed reading (canonical decimal string) or nil when nothing trustworthy was read.
    public let value: String?
    /// Heuristic agreement score in [0, 1] (see ``MeterOCR``); not a calibrated probability.
    public let confidence: Double
    /// Raw recognized text (what the engine saw), stored as `ocr_raw_text`.
    public let rawText: String
    public let engine: String
    /// Short diagnostic of how the value was obtained or why it was not.
    public let note: String

    public init(value: String?, confidence: Double, rawText: String, engine: String, note: String) {
        self.value = value
        self.confidence = confidence
        self.rawText = rawText
        self.engine = engine
        self.note = note
    }
}

/// Hour-meter OCR with Apple Vision (`VNRecognizeTextRequest`, accurate, on-device only).
///
/// Vision's own per-string confidence is ~1.0 even for wrong reads of segmented displays, so it is
/// not used as the confidence. Instead the photo is segmented into glyphs (``GlyphSegmenter``), the
/// reading row is re-rendered as clean black-on-white glyphs in three layouts, each layout is read
/// by Vision, characters are mapped back to glyphs, and the confidence reflects how many
/// independent layouts agree glyph-for-glyph, plus plausibility checks:
/// - a decimal point is taken from geometry (LCD dot) or a red tenths wheel (mechanical drum) —
///   so `20264.1` is not merged into `202641`;
/// - every glyph must map to exactly one character, and the digit run must be contiguous;
/// - a `1` as wide as the other digits is suspicious (blurred 7-segment `7`);
/// - a full-frame Vision read with the same digit count but different digits caps confidence;
/// - on 7-segment displays a deterministic segment decoder (``SevenSegmentDecoder``) is a second,
///   independent opinion: agreement with the Vision majority counts as unanimous, and it resolves a
///   too-wide `1` only when at least one Vision layout read the same digit.
///
/// Scores: unanimous 0.92 (+0.05 when the full-frame read agrees), 2 of 3 layouts 0.70, else 0.50;
/// capped at 0.60 for a suspicious `1`, a segment-decoder conflict or a full-frame conflict, and at
/// 0.50 for an ambiguous decimal point or another same-size row with a different number. Vision
/// alone, without geometric confirmation, never exceeds 0.40. These are heuristic agreement
/// scores (no calibration data exists yet), chosen so that below `min_ocr_confidence` the app asks
/// for a recapture rather than trusting a doubtful read.
public struct MeterOCR: Sendable {
    public static let engineName = "apple-vision+asseta-geometry/1"
    static let layouts: [(scale: Double, gap: Double)] = [(64, 0.3), (100, 0.5), (80, 0.4)]

    public init() {}

    /// Recognizes the reading in `imageData` (JPEG/PNG bytes, EXIF orientation honoured).
    public func recognize(imageData: Data, decimalPlaces: Int) -> MeterOCRResult {
        guard let cgImage = PixelImage.decode(imageData, maxSide: 1280) else {
            return MeterOCRResult(value: nil, confidence: 0, rawText: "", engine: Self.engineName, note: "UNREADABLE_IMAGE")
        }
        return recognize(cgImage: cgImage, decimalPlaces: decimalPlaces)
    }

    public func recognize(cgImage: CGImage, decimalPlaces: Int) -> MeterOCRResult {
        let fullFrame = Self.visionText(cgImage)
        let fullParse = MeterReadingParser.parse(fullFrame.joined(separator: " "), decimalPlaces: decimalPlaces)
        guard var image = PixelImage(cgImage: cgImage) else {
            return fallback(fullFrame, fullParse, note: "UNREADABLE_IMAGE")
        }
        var segmentation = GlyphSegmenter.segment(image)
        if let best = segmentation.rows.first {
            let skew = GlyphSegmenter.skewDegrees(best)
            if abs(skew) > 1.5, let straightened = image.rotated(by: skew) {
                image = straightened
                segmentation = GlyphSegmenter.segment(image)
            }
        }
        var readings: [RowReading] = []
        for row in segmentation.rows.prefix(3) {
            if let reading = read(row, segmentation, decimalPlaces: decimalPlaces) { readings.append(reading) }
        }
        let parsed = readings.filter { $0.value != nil }
        guard let primary = parsed.first else { return fallback(fullFrame, fullParse, note: "NO_GEOMETRIC_READ") }

        var confidence = primary.agreement >= 1 ? 0.92 : (primary.agreement >= 0.6 ? 0.7 : 0.5)
        var notes = ["layouts=\(primary.agreeing)/\(Self.layouts.count)"]
        if primary.suspiciousOne { confidence = min(confidence, 0.6); notes.append("WIDE_ONE") }
        if primary.ambiguousDots { confidence = min(confidence, 0.5); notes.append("AMBIGUOUS_DOT") }
        if primary.segments != .absent { notes.append("SEGMENTS_\(primary.segments)".uppercased()) }
        if primary.segments == .conflict { confidence = min(confidence, 0.6) }
        // Another row of similar-size text with a different number makes the reading ambiguous;
        // smaller rows (clock, odometer, labels) are ordinary distractors.
        let peers = parsed.filter { $0.medianHeight * 4 >= primary.medianHeight * 3 }
        if Set(peers.compactMap(\.value)).count > 1 { confidence = min(confidence, 0.5); notes.append("ROWS_DISAGREE") }
        let ours = Self.digits(primary.value ?? "")
        if let other = fullParse.candidates.first.map(Self.digits), fullParse.reason == .ok {
            if other == ours {
                confidence = min(confidence + 0.05, 0.98); notes.append("FULL_FRAME_AGREES")
            } else if other.count == ours.count {
                confidence = min(confidence, 0.6); notes.append("FULL_FRAME_CONFLICT")
            }
        }
        let raw = ([primary.text] + fullFrame).joined(separator: " | ")
        return MeterOCRResult(value: primary.value, confidence: confidence, rawText: String(raw.prefix(500)),
                              engine: Self.engineName, note: notes.joined(separator: ","))
    }

    // MARK: - Row reading

    enum SegmentOpinion: String { case absent, agree, resolved, conflict }

    struct RowReading {
        let value: String?
        let text: String
        let agreement: Double
        let agreeing: Int
        let suspiciousOne: Bool
        let ambiguousDots: Bool
        let segments: SegmentOpinion
        let medianHeight: Int
    }

    private func read(_ row: GlyphRow, _ segmentation: Segmentation, decimalPlaces: Int) -> RowReading? {
        var votes: [[Character]] = []
        for layout in Self.layouts {
            guard let rendered = GlyphRenderer.render(row, segmentation, scale: layout.scale, gapFactor: layout.gap),
                  let chars = Self.assign(rendered) else { continue }
            votes.append(chars)
        }
        guard !votes.isEmpty else { return nil }
        let tally = Dictionary(grouping: votes, by: { String($0) })
        guard let (winner, group) = tally.max(by: { $0.value.count < $1.value.count }) else { return nil }
        var chars = Array(winner)
        var agreeing = group.count
        var wideOne = Self.hasWideOne(chars, row: row)
        var segments = SegmentOpinion.absent
        if let decoded = SevenSegmentDecoder.decode(row, segmentation) {
            if decoded == chars {
                segments = .agree
                // Two independent recognizers (a Vision majority and the deterministic segment
                // decoder) agree on every glyph: as strong as unanimous Vision layouts.
                if agreeing * 3 >= Self.layouts.count * 2 { agreeing = Self.layouts.count }
            } else if wideOne, votes.contains(decoded), Self.differsOnlyAtWideOnes(chars, decoded, row: row) {
                // Vision called a full-width glyph `1`; the segment decoder (confirmed by at least
                // one Vision layout) shows which digit it is (typically a 7-segment `7`).
                chars = decoded
                agreeing = Self.layouts.count
                wideOne = false
                segments = .resolved
            } else {
                segments = .conflict
            }
        }
        guard let text = Self.compose(chars, row: row) else { return nil }
        let parse = MeterReadingParser.parse(text, decimalPlaces: decimalPlaces)
        return RowReading(
            value: parse.value, text: text,
            agreement: Double(agreeing) / Double(Self.layouts.count), agreeing: agreeing,
            suspiciousOne: wideOne, ambiguousDots: row.ambiguousDots, segments: segments,
            medianHeight: row.medianHeight
        )
    }

    /// Maps Vision's characters to glyph slots by order. Vision's accurate recognizer reports the
    /// line box for every character, so the correspondence is by count instead: after dropping
    /// whitespace and punctuation (the decimal point comes from geometry), there must be exactly
    /// one character per rendered glyph, else the layout is discarded.
    static func assign(_ rendered: GlyphRenderer.Rendered) -> [Character]? {
        let text = Self.observations(rendered.image).compactMap { $0.topCandidates(1).first?.string }.joined()
        let chars = text.filter { !$0.isWhitespace && !".,·:'`".contains($0) }
        guard chars.count == rendered.glyphSpans.count else { return nil }
        return chars.map { Character($0.uppercased()) }
    }

    /// Builds parser input from per-glyph characters: geometric decimal point, drum tenths split,
    /// unit letters separated. Rejects symbols and non-contiguous digit runs.
    static func compose(_ chars: [Character], row: GlyphRow) -> String? {
        let digitLike = Set("0123456789OQDILSBZG|")
        var isDigit: [Bool] = []
        for c in chars {
            if digitLike.contains(c) { isDigit.append(true) } else if c.isLetter { isDigit.append(false) } else { return nil }
        }
        guard let first = isDigit.firstIndex(of: true), let last = isDigit.lastIndex(of: true),
              isDigit[first...last].allSatisfy({ $0 }) else { return nil }
        var text = ""
        for (i, c) in chars.enumerated() {
            if i == last + 1 || (i == first && i > 0) { text.append(" ") }
            if let red = row.redTenths, row.dotAfter == nil, i == red, i == last { text.append(" ") }
            text.append(c)
            if let dot = row.dotAfter, dot == i, i < last { text.append(".") }
        }
        return text
    }

    /// True when `a` and `b` differ only at glyphs `a` reads as a too-wide `1`.
    static func differsOnlyAtWideOnes(_ a: [Character], _ b: [Character], row: GlyphRow) -> Bool {
        guard a.count == b.count, a.count == row.glyphs.count else { return false }
        let widths = row.glyphs.map(\.width).sorted()
        let median = Double(widths[widths.count / 2])
        for i in a.indices where a[i] != b[i] {
            guard "1IL|".contains(a[i]), Double(row.glyphs[i].width) > 0.7 * median else { return false }
        }
        return true
    }

    /// A recognized `1` whose glyph is nearly as wide as the other digits.
    static func hasWideOne(_ chars: [Character], row: GlyphRow) -> Bool {
        let ones: Set<Character> = ["1", "I", "L", "|"]
        let others = zip(chars, row.glyphs).filter { !ones.contains($0.0) && $0.0.isNumber }.map(\.1.width).sorted()
        guard !others.isEmpty else { return false }
        let median = Double(others[others.count / 2])
        return zip(chars, row.glyphs).contains { ones.contains($0.0) && Double($0.1.width) > 0.7 * median }
    }

    // MARK: - Vision

    static func observations(_ image: CGImage) -> [VNRecognizedTextObservation] {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        request.recognitionLanguages = ["en-US"]
        let handler = VNImageRequestHandler(cgImage: image, options: [:])
        do { try handler.perform([request]) } catch { return [] }
        return (request.results ?? []).sorted { $0.boundingBox.minX < $1.boundingBox.minX }
    }

    static func visionText(_ image: CGImage) -> [String] {
        observations(image)
            .sorted { ($0.boundingBox.maxY, -$0.boundingBox.minX) > ($1.boundingBox.maxY, -$1.boundingBox.minX) }
            .compactMap { $0.topCandidates(1).first?.string }
    }

    private func fallback(_ fullFrame: [String], _ parse: MeterReadingParser.Result, note: String) -> MeterOCRResult {
        // Vision alone (no geometric confirmation) is never trusted enough to skip a recapture.
        MeterOCRResult(value: parse.value, confidence: parse.value == nil ? 0 : 0.4,
                       rawText: String(fullFrame.joined(separator: " | ").prefix(500)), engine: Self.engineName,
                       note: "\(note),\(parse.reason.rawValue)")
    }

    /// Digits without leading zeros (so `03190.6` and `3190.6` compare equal).
    static func digits(_ text: String) -> String {
        String(text.filter { $0.isASCII && $0.isNumber }.drop(while: { $0 == "0" }))
    }
}
