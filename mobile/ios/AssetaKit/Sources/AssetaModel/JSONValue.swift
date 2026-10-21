import Foundation

/// An arbitrary JSON value, for protocol fields the contract declares as free-form objects
/// (`payload`, `result`, `error`, policy `values`). Numbers keep their decimal text so no money
/// or meter value passes through `Double` on the way through.
public enum JSONValue: Codable, Hashable, Sendable {
    case null
    case bool(Bool)
    case number(Decimal)
    case string(String)
    case array([JSONValue])
    case object([String: JSONValue])

    public init(from decoder: any Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Decimal.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            self = .object(try container.decode([String: JSONValue].self))
        }
    }

    public func encode(to encoder: any Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .null: try container.encodeNil()
        case let .bool(value): try container.encode(value)
        case let .number(value): try container.encode(value)
        case let .string(value): try container.encode(value)
        case let .array(value): try container.encode(value)
        case let .object(value): try container.encode(value)
        }
    }

    public subscript(key: String) -> JSONValue? {
        if case let .object(object) = self { return object[key] }
        return nil
    }

    public var stringValue: String? {
        if case let .string(value) = self { return value }
        return nil
    }

    public var boolValue: Bool? {
        if case let .bool(value) = self { return value }
        return nil
    }

    public var decimalValue: Decimal? {
        switch self {
        case let .number(value): value
        case let .string(text): Decimal(string: text, locale: Locale(identifier: "en_US_POSIX"))
        default: nil
        }
    }

    public var doubleValue: Double? { decimalValue.map { NSDecimalNumber(decimal: $0).doubleValue } }

    public var intValue: Int? { decimalValue.map { NSDecimalNumber(decimal: $0).intValue } }

    public var isNull: Bool { self == .null }

    /// Rewrites every string that is a UUID into canonical lowercase (`JSONEncoder` writes UUIDs in
    /// uppercase); keeps ids byte-identical across the outbox, payload patches and the server.
    public func lowercasingUUIDs() -> JSONValue {
        switch self {
        case let .string(text) where text.count == 36 && UUID(uuidString: text) != nil: .string(text.lowercased())
        case let .array(items): .array(items.map { $0.lowercasingUUIDs() })
        case let .object(object): .object(object.mapValues { $0.lowercasingUUIDs() })
        default: self
        }
    }

    /// Compact JSON text with sorted keys (stable for storage and payload hashing).
    public func jsonString() throws -> String {
        String(decoding: try AssetaJSON.encoder().encode(self), as: UTF8.self)
    }

    public static func parse(_ text: String) throws -> JSONValue {
        try AssetaJSON.decoder().decode(JSONValue.self, from: Data(text.utf8))
    }

    /// Re-encodes any `Encodable` value as a `JSONValue` using the shared Asseta coders.
    public static func encode(_ value: some Encodable) throws -> JSONValue {
        try AssetaJSON.decoder().decode(JSONValue.self, from: try AssetaJSON.encoder().encode(value))
    }

    /// Decodes this value into a typed DTO using the shared Asseta coders.
    public func decode<T: Decodable>(as type: T.Type = T.self) throws -> T {
        try AssetaJSON.decoder().decode(T.self, from: try AssetaJSON.encoder().encode(self))
    }
}
