import Foundation

/// Shared JSON coders so every module agrees on date and key handling.
/// DTOs declare explicit snake_case `CodingKeys`; no automatic key conversion is applied,
/// which keeps wire names greppable and reviewable.
public enum AssetaJSON {
    public static func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let text = try container.decode(String.self)
            if let date = parseInstant(text) { return date }
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Invalid ISO-8601 instant: \(text)")
        }
        return decoder
    }

    public static func encoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .custom { date, encoder in
            var container = encoder.singleValueContainer()
            try container.encode(formatInstant(date))
        }
        encoder.outputFormatting = [.sortedKeys]
        return encoder
    }

    /// Formats a UTC instant with millisecond precision, e.g. `2026-10-21T08:15:30.123Z`.
    public static func formatInstant(_ date: Date) -> String {
        date.formatted(
            Date.ISO8601FormatStyle(includingFractionalSeconds: true, timeZone: TimeZone(identifier: "UTC")!)
        )
    }

    public static func parseInstant(_ text: String) -> Date? {
        let withFraction = Date.ISO8601FormatStyle(includingFractionalSeconds: true)
        let plain = Date.ISO8601FormatStyle()
        return (try? withFraction.parse(text)) ?? (try? plain.parse(text))
    }
}
