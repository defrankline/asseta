import Foundation

/// A server enum carried as its raw string. Unknown future values decode instead of failing,
/// so an older app build keeps working when the server adds a state; the UI treats unknown values
/// neutrally (never as the "best" state).
public protocol OpenStringEnum: RawRepresentable, Codable, Hashable, Sendable, CustomStringConvertible
where RawValue == String {
    init(rawValue: String)
}

extension OpenStringEnum {
    public init(from decoder: any Decoder) throws {
        self.init(rawValue: try decoder.singleValueContainer().decode(String.self))
    }

    public func encode(to encoder: any Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }

    public var description: String { rawValue }

    /// `"NEVER_REPORTED"` → `"Never reported"`, for values without a dedicated label.
    public var humanized: String {
        let words = rawValue.split(separator: "_").map { $0.lowercased() }
        guard let first = words.first else { return rawValue }
        return ([first.prefix(1).uppercased() + first.dropFirst()] + words.dropFirst()).joined(separator: " ")
    }
}

/// `{"items","total","page","page_size"}` list envelope used by every paginated endpoint.
public struct Page<Item: Codable & Hashable & Sendable>: Codable, Hashable, Sendable {
    public let items: [Item]
    public let total: Int
    public let page: Int
    public let pageSize: Int

    public init(items: [Item], total: Int, page: Int, pageSize: Int) {
        self.items = items
        self.total = total
        self.page = page
        self.pageSize = pageSize
    }

    enum CodingKeys: String, CodingKey { case items, total, page, pageSize = "page_size" }
}
