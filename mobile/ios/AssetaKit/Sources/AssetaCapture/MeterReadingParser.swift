import Foundation

/// Hour-meter OCR text parsing rules, spec v2 — a faithful port of the reference implementation
/// `backend/src/asseta/modules/meter/ocr_parse.py`. Android and iOS must both pass every case in
/// `contracts/fixtures/ocr/parse_cases.json`, so do not "improve" the rules here: change the spec,
/// the reference and the shared cases together.
///
/// Rules: ignore clock times and unit words; map common letter/digit confusions inside numeric
/// tokens; a token with an explicit `.`/`,` separator is decimal; a long integer token immediately
/// followed by a single-digit token is a tenths drum (mechanical counters); exactly one candidate
/// must remain, else ambiguous. v2: when several remain, the single candidate written with an hours
/// unit and exactly the meter's decimal places wins (dashboards that also show trip/idle counters and
/// fuel); two or more such candidates stay ambiguous. A failure returns no value and the app falls back to manual entry
/// (policy permitting), keeping the original photo and raw text.
public enum MeterReadingParser {
    public static let specVersion = "2"

    public enum Reason: String, Sendable, Equatable {
        case ok = "OK"
        case noNumber = "NO_NUMBER"
        case ambiguous = "AMBIGUOUS"
        case precisionExceedsMeter = "PRECISION_EXCEEDS_METER"
    }

    public struct Result: Sendable, Equatable {
        /// Canonical decimal string with exactly `decimalPlaces` fraction digits, or nil (manual fallback).
        public let value: String?
        public let reason: Reason
        /// The normalized candidate token(s) the decision was based on (diagnostics / OCR consistency).
        public let candidates: [String]
    }

    private static let clock = try! NSRegularExpression(pattern: #"\b\d{1,2}:\d{2}(:\d{2})?\b"#)
    // An hours unit written right after a number tags that number (v2); "#" marks it for the tokenizer.
    private static let unitAfterNumber = try! NSRegularExpression(pattern: #"(?<=\d)\s*(?:HOURS?|HRS?|H)(?![A-Z])"#)
    private static let units = try! NSRegularExpression(pattern: #"\b(HRS?|HOURS?|H)\b"#)
    private static let token = try! NSRegularExpression(pattern: #"[0-9OQDILSBZG|]+(?:[.,][0-9OQDILSBZG|]+)?|#"#)
    private static let confusable: [Character: Character] = [
        "O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "|": "1", "S": "5", "B": "8", "Z": "2", "G": "6",
    ]

    public static func parse(_ text: String, decimalPlaces: Int) -> Result {
        var upper = replace(clock, in: text.uppercased())
        upper = unitAfterNumber.stringByReplacingMatches(
            in: upper, range: NSRange(upper.startIndex..., in: upper), withTemplate: " # ")
        upper = replace(units, in: upper)
        let range = NSRange(upper.startIndex..., in: upper)
        let raw = token.matches(in: upper, range: range).compactMap { match in
            Range(match.range, in: upper).map { String(upper[$0]) }
        }
        let tokens = raw
            .filter { $0 == "#" || $0.contains(where: { $0.isASCII && $0.isNumber }) }
            .map { String($0.map { confusable[$0] ?? ($0 == "," ? "." : $0) }) }

        var candidates: [(text: String, unit: Bool)] = []
        func unit(at index: Int) -> Bool { index < tokens.count && tokens[index] == "#" }
        var index = 0
        while index < tokens.count {
            let current = tokens[index]
            let next = index + 1 < tokens.count ? tokens[index + 1] : nil
            if current == "#" {
                index += 1
                continue
            }
            if !current.contains("."), let next, next != "#", next.count == 1, current.count >= 3, decimalPlaces >= 1 {
                index += 2
                candidates.append(("\(current).\(next)", unit(at: index))) // drum counter: last wheel is tenths
                continue
            }
            index += 1
            if current.replacingOccurrences(of: ".", with: "").count >= 3 {
                candidates.append((current, unit(at: index)))
            }
        }
        guard !candidates.isEmpty else { return Result(value: nil, reason: .noNumber, candidates: []) }
        if candidates.count > 1 {
            let preferred = candidates.filter {
                $0.unit && ($0.text.split(separator: ".", omittingEmptySubsequences: false).dropFirst().first?.count ?? 0) == decimalPlaces
            }
            guard preferred.count == 1 else { return Result(value: nil, reason: .ambiguous, candidates: candidates.map(\.text)) }
            candidates = preferred
        }
        let texts = candidates.map(\.text)
        let parts = texts[0].split(separator: ".", omittingEmptySubsequences: false)
        let fraction = parts.count > 1 ? String(parts[1]) : ""
        guard fraction.count <= decimalPlaces else {
            return Result(value: nil, reason: .precisionExceedsMeter, candidates: texts)
        }
        var integer = String(parts[0].drop(while: { $0 == "0" }))
        if integer.isEmpty { integer = "0" }
        let padded = fraction + String(repeating: "0", count: max(decimalPlaces - fraction.count, 0))
        let value = decimalPlaces > 0 ? "\(integer).\(padded)" : integer
        return Result(value: value, reason: .ok, candidates: texts)
    }

    private static func replace(_ regex: NSRegularExpression, in text: String) -> String {
        regex.stringByReplacingMatches(in: text, range: NSRange(text.startIndex..., in: text), withTemplate: " ")
    }
}
