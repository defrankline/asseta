import Foundation

/// Structured error envelope returned by every Asseta API error response:
/// `{"error":{"code","message","correlation_id","details":[{"field","issue"}]}}`.
public struct ErrorEnvelope: Codable, Hashable, Sendable {
    public let error: ErrorBody

    public init(error: ErrorBody) {
        self.error = error
    }
}

public struct ErrorBody: Codable, Hashable, Sendable {
    public let code: String
    public let message: String
    public let correlationID: String
    public let details: [ErrorDetail]

    public init(code: String, message: String, correlationID: String, details: [ErrorDetail] = []) {
        self.code = code
        self.message = message
        self.correlationID = correlationID
        self.details = details
    }

    enum CodingKeys: String, CodingKey {
        case code, message
        case correlationID = "correlation_id"
        case details
    }

    public init(from decoder: any Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        code = try container.decode(String.self, forKey: .code)
        message = try container.decode(String.self, forKey: .message)
        correlationID = try container.decode(String.self, forKey: .correlationID)
        details = try container.decodeIfPresent([ErrorDetail].self, forKey: .details) ?? []
    }
}

public struct ErrorDetail: Codable, Hashable, Sendable {
    /// Dotted field path, or nil when the issue is not tied to one field.
    public let field: String?
    public let issue: String

    public init(field: String?, issue: String) {
        self.field = field
        self.issue = issue
    }
}
