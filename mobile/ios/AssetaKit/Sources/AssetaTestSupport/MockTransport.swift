import AssetaNetwork
import Foundation

/// Scripted HTTP transport for tests: records requests and replies via a handler.
public final class MockTransport: HTTPTransport, @unchecked Sendable {
    // @unchecked: mutable state is only touched while holding `lock`.
    public typealias Handler = @Sendable (URLRequest) throws -> (Int, Data)

    private let lock = NSLock()
    private var handler: Handler
    private var recorded: [URLRequest] = []

    public init(handler: @escaping Handler) {
        self.handler = handler
    }

    public var requests: [URLRequest] { lock.withLock { recorded } }

    public func setHandler(_ handler: @escaping Handler) {
        lock.withLock { self.handler = handler }
    }

    public func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let current = lock.withLock { () -> Handler in
            recorded.append(request)
            return handler
        }
        let (status, data) = try current(request)
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: nil)!
        return (data, response)
    }

    /// Decodes an `application/x-www-form-urlencoded` body.
    public static func form(_ request: URLRequest) -> [String: String] {
        guard let body = request.httpBody, let text = String(data: body, encoding: .utf8) else { return [:] }
        var result: [String: String] = [:]
        for pair in text.split(separator: "&") {
            let parts = pair.split(separator: "=", maxSplits: 1).map(String.init)
            guard parts.count == 2 else { continue }
            result[parts[0].removingPercentEncoding ?? parts[0]] = parts[1].removingPercentEncoding ?? parts[1]
        }
        return result
    }
}

/// Fixed token provider for API client tests.
public actor StaticTokenProvider: AccessTokenProvider {
    public private(set) var token: String
    private let refreshed: String?
    public private(set) var refreshCount = 0

    public init(token: String, refreshed: String? = nil) {
        self.token = token
        self.refreshed = refreshed
    }

    public func validAccessToken() async throws -> String { token }

    public func refreshedAccessToken(rejected: String) async throws -> String {
        refreshCount += 1
        guard let refreshed else { throw APIError.notAuthenticated }
        token = refreshed
        return refreshed
    }
}

public enum Fixtures {
    public static func json(_ text: String) -> Data { Data(text.utf8) }

    public static let meJSON = """
    {"user_id":"6f1c2a1e-0b7a-4c55-9d8e-1f2a3b4c5d6e","email":"sup@example.com","display_name":"Sam Supervisor",
     "platform_permissions":[],"platform_menus":[],
     "tenants":[
      {"tenant_id":"11111111-1111-4111-8111-111111111111","name":"Acme Plant Hire","status":"ACTIVE",
       "access_state":"FULL","permissions":["jobs.read","meter.capture"],
       "menus":[{"key":"meter","label":"Meter","path":"/meter","order":20},
                {"key":"jobs","label":"Jobs","path":"/jobs","order":10}]},
      {"tenant_id":"22222222-2222-4222-8222-222222222222","name":"Blocked Co","status":"SUSPENDED",
       "access_state":"BLOCKED","permissions":[],"menus":[]}
     ]}
    """
}
