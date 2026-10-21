import AssetaModel
import Foundation

/// Typed failure of an Asseta API call. Every case carries the request's correlation ID so
/// support can trace it through server logs and audit.
public enum APIError: Error, Equatable, Sendable {
    /// Server returned the structured `{"error":{...}}` envelope.
    case server(status: Int, body: ErrorBody)
    /// Non-2xx response without a decodable envelope (e.g. proxy error page).
    case unexpectedStatus(status: Int, correlationID: String)
    /// 2xx response whose body did not match the expected DTO.
    case decoding(message: String, correlationID: String)
    /// Network-level failure (offline, timeout, TLS).
    case transport(code: Int, message: String, correlationID: String)
    /// No authenticated session is available; user must sign in.
    case notAuthenticated
    /// A tenant-scoped request was sent without a selected tenant.
    case tenantRequired

    public var correlationID: String? {
        switch self {
        case let .server(_, body): body.correlationID
        case let .unexpectedStatus(_, id), let .decoding(_, id), let .transport(_, _, id): id
        case .notAuthenticated, .tenantRequired: nil
        }
    }

    public var httpStatus: Int? {
        switch self {
        case let .server(status, _), let .unexpectedStatus(status, _): status
        default: nil
        }
    }

    /// Stable machine-readable code (server code when available).
    public var code: String {
        switch self {
        case let .server(_, body): body.code
        case .unexpectedStatus: "UNEXPECTED_STATUS"
        case .decoding: "DECODING_FAILED"
        case .transport: "TRANSPORT_FAILED"
        case .notAuthenticated: "NOT_AUTHENTICATED"
        case .tenantRequired: "TENANT_REQUIRED"
        }
    }

    /// Whether repeating the same request (same idempotency key) may succeed later.
    public var isRetryable: Bool {
        switch self {
        case .transport: true
        case let .server(status, _), let .unexpectedStatus(status, _): status == 429 || status >= 500
        default: false
        }
    }
}

extension APIError: LocalizedError {
    public var errorDescription: String? {
        switch self {
        case let .server(_, body): body.message
        case let .unexpectedStatus(status, _): "The server returned an unexpected response (\(status))."
        case .decoding: "The server response could not be read."
        case let .transport(_, message, _): message
        case .notAuthenticated: "Please sign in again."
        case .tenantRequired: "Select a company first."
        }
    }
}
