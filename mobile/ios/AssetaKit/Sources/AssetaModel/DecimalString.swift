import Foundation

/// A monetary or fixed-point quantity transported as a JSON **string** (e.g. `"1250.50"`).
///
/// The Asseta API never sends money as a JSON number, and the client never parses money
/// through `Double`. Decoding rejects JSON numbers and any non-canonical decimal text.
public struct DecimalString: Codable, Hashable, Sendable, CustomStringConvertible {
    public let value: Decimal

    public init(_ value: Decimal) {
        self.value = value
    }

    /// Strictly parses `-?digits(.digits)?` using a locale-independent parser.
    public init?(string text: String) {
        guard DecimalString.isCanonical(text),
              let parsed = Decimal(string: text, locale: Locale(identifier: "en_US_POSIX"))
        else { return nil }
        self.value = parsed
    }

    public init(from decoder: any Decoder) throws {
        let container = try decoder.singleValueContainer()
        // Decoding as String fails for JSON numbers, which is intentional: no float path.
        let text = try container.decode(String.self)
        guard let parsed = DecimalString(string: text) else {
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Invalid decimal string: \(text)"
            )
        }
        self = parsed
    }

    public func encode(to encoder: any Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(description)
    }

    public var description: String {
        var copy = value
        return NSDecimalString(&copy, Locale(identifier: "en_US_POSIX"))
    }

    static func isCanonical(_ text: String) -> Bool {
        var scalars = Substring(text)
        if scalars.first == "-" { scalars = scalars.dropFirst() }
        let parts = scalars.split(separator: ".", omittingEmptySubsequences: false)
        guard (1...2).contains(parts.count) else { return false }
        return parts.allSatisfy { part in
            !part.isEmpty && part.allSatisfy { $0.isASCII && $0.isNumber }
        }
    }
}
