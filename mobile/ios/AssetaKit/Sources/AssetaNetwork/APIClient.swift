import AssetaModel
import Foundation

public enum HTTPMethod: String, Sendable {
    case get = "GET", post = "POST", put = "PUT", patch = "PATCH", delete = "DELETE"

    public var isMutation: Bool { self != .get }
}

/// A typed API request. Mutations can only be constructed with an idempotency key, which the
/// caller must persist and reuse on retry (for outbox operations it is the operation UUID).
public struct APIRequest<Response: Decodable & Sendable>: Sendable {
    public let method: HTTPMethod
    public let path: String
    public let queryItems: [URLQueryItem]
    public let body: Data?
    public let idempotencyKey: UUID?
    public let tenantScoped: Bool
    /// Extra request headers (e.g. `X-Device-Id` on sync calls). Cannot override the auth,
    /// tenant, correlation or idempotency headers the client sets itself.
    public let headers: [String: String]
    public let contentType: String

    private init(method: HTTPMethod, path: String, queryItems: [URLQueryItem], body: Data?,
                 idempotencyKey: UUID?, tenantScoped: Bool, headers: [String: String] = [:],
                 contentType: String = "application/json") {
        self.method = method
        self.path = path
        self.queryItems = queryItems
        self.body = body
        self.idempotencyKey = idempotencyKey
        self.tenantScoped = tenantScoped
        self.headers = headers
        self.contentType = contentType
    }

    /// Returns a copy with additional headers.
    public func adding(headers extra: [String: String]) -> Self {
        Self(method: method, path: path, queryItems: queryItems, body: body, idempotencyKey: idempotencyKey,
             tenantScoped: tenantScoped, headers: headers.merging(extra) { _, new in new }, contentType: contentType)
    }

    /// A mutation whose body is sent as raw bytes (e.g. a blob chunk), not JSON-encoded.
    public static func rawMutation(
        _ method: HTTPMethod,
        _ path: String,
        data: Data,
        contentType: String = "application/octet-stream",
        idempotencyKey: UUID,
        tenantScoped: Bool = true
    ) -> Self {
        precondition(method.isMutation, "Use .get for reads")
        return Self(method: method, path: path, queryItems: [], body: data, idempotencyKey: idempotencyKey,
                    tenantScoped: tenantScoped, contentType: contentType)
    }

    public static func get(_ path: String, query: [URLQueryItem] = [], tenantScoped: Bool = true) -> Self {
        Self(method: .get, path: path, queryItems: query, body: nil, idempotencyKey: nil, tenantScoped: tenantScoped)
    }

    public static func mutation<Body: Encodable>(
        _ method: HTTPMethod,
        _ path: String,
        body: Body,
        idempotencyKey: UUID,
        tenantScoped: Bool = true
    ) throws -> Self {
        precondition(method.isMutation, "Use .get for reads")
        return Self(method: method, path: path, queryItems: [], body: try AssetaJSON.encoder().encode(body),
                    idempotencyKey: idempotencyKey, tenantScoped: tenantScoped)
    }
}

/// Placeholder response type for endpoints returning no body (204).
public struct EmptyResponse: Decodable, Sendable, Equatable {
    public init() {}
}

/// Asseta REST client. Adds bearer auth, tenant, correlation and idempotency headers and maps
/// failures to ``APIError``. It never makes authorization decisions — it reports the server's.
public struct APIClient: Sendable {
    public let baseURL: URL
    public let tenantID: UUID?
    private let transport: any HTTPTransport
    private let tokens: any AccessTokenProvider
    private let makeCorrelationID: @Sendable () -> UUID

    public init(
        baseURL: URL,
        transport: any HTTPTransport = URLSessionTransport(),
        tokens: any AccessTokenProvider,
        tenantID: UUID? = nil,
        makeCorrelationID: @escaping @Sendable () -> UUID = { UUID() }
    ) {
        self.baseURL = baseURL
        self.transport = transport
        self.tokens = tokens
        self.tenantID = tenantID
        self.makeCorrelationID = makeCorrelationID
    }

    /// Returns a client bound to `tenantID` (sent as `X-Tenant-ID`).
    public func withTenant(_ tenantID: UUID?) -> APIClient {
        APIClient(baseURL: baseURL, transport: transport, tokens: tokens, tenantID: tenantID,
                  makeCorrelationID: makeCorrelationID)
    }

    public func send<Response>(_ request: APIRequest<Response>) async throws -> Response {
        if request.tenantScoped && tenantID == nil { throw APIError.tenantRequired }
        let token = try await tokens.validAccessToken()
        let (data, response, correlationID) = try await perform(request, token: token)
        if response.statusCode == 401 {
            // One refresh-and-retry. Safe for mutations because the idempotency key is reused.
            let fresh = try await tokens.refreshedAccessToken(rejected: token)
            let retry = try await perform(request, token: fresh)
            return try decode(retry.0, retry.1, retry.2)
        }
        return try decode(data, response, correlationID)
    }

    func buildURLRequest<Response>(_ request: APIRequest<Response>, token: String, correlationID: UUID) throws -> URLRequest {
        let relative = request.path.hasPrefix("/") ? String(request.path.dropFirst()) : request.path
        guard var components = URLComponents(url: baseURL.appendingPathComponent(relative), resolvingAgainstBaseURL: false)
        else { throw URLError(.badURL) }
        if !request.queryItems.isEmpty { components.queryItems = request.queryItems }
        guard let url = components.url else { throw URLError(.badURL) }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = request.method.rawValue
        for (name, value) in request.headers.sorted(by: { $0.key < $1.key }) {
            urlRequest.setValue(value, forHTTPHeaderField: name)
        }
        urlRequest.setValue("application/json", forHTTPHeaderField: "Accept")
        urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(correlationID.uuidString.lowercased(), forHTTPHeaderField: "X-Correlation-ID")
        if let tenantID {
            urlRequest.setValue(tenantID.uuidString.lowercased(), forHTTPHeaderField: "X-Tenant-ID")
        }
        if let key = request.idempotencyKey {
            urlRequest.setValue(key.uuidString.lowercased(), forHTTPHeaderField: "Idempotency-Key")
        }
        if let body = request.body {
            urlRequest.httpBody = body
            urlRequest.setValue(request.contentType, forHTTPHeaderField: "Content-Type")
        }
        return urlRequest
    }

    private func perform<Response>(
        _ request: APIRequest<Response>,
        token: String
    ) async throws -> (Data, HTTPURLResponse, String) {
        let correlationID = makeCorrelationID()
        let urlRequest = try buildURLRequest(request, token: token, correlationID: correlationID)
        let cid = correlationID.uuidString.lowercased()
        do {
            let (data, response) = try await transport.send(urlRequest)
            return (data, response, cid)
        } catch let error as URLError {
            throw APIError.transport(code: error.errorCode, message: error.localizedDescription, correlationID: cid)
        }
    }

    private func decode<Response: Decodable>(_ data: Data, _ response: HTTPURLResponse, _ cid: String) throws -> Response {
        guard (200..<300).contains(response.statusCode) else {
            if let envelope = try? AssetaJSON.decoder().decode(ErrorEnvelope.self, from: data) {
                throw APIError.server(status: response.statusCode, body: envelope.error)
            }
            throw APIError.unexpectedStatus(status: response.statusCode, correlationID: cid)
        }
        if Response.self == EmptyResponse.self, let empty = EmptyResponse() as? Response {
            return empty
        }
        do {
            return try AssetaJSON.decoder().decode(Response.self, from: data)
        } catch {
            throw APIError.decoding(message: String(describing: error), correlationID: cid)
        }
    }
}

extension APIClient {
    /// `GET /api/v1/me` — identity plus server-computed tenant memberships, permissions and menus.
    public func me() async throws -> MeResponse {
        try await send(APIRequest<MeResponse>.get("/api/v1/me", tenantScoped: false))
    }
}
