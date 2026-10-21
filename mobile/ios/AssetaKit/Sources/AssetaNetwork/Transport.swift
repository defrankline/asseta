import Foundation

/// Narrow, replaceable HTTP adapter so the client can be tested without a network.
public protocol HTTPTransport: Sendable {
    func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse)
}

public struct URLSessionTransport: HTTPTransport {
    private let session: URLSession

    public init(session: URLSession = URLSessionTransport.makeDefaultSession()) {
        self.session = session
    }

    /// Ephemeral session: no shared cookie jar or URL cache holding tenant data on disk.
    public static func makeDefaultSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 120
        configuration.waitsForConnectivity = false
        configuration.httpCookieAcceptPolicy = .never
        configuration.urlCache = nil
        return URLSession(configuration: configuration)
    }

    public func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        return (data, http)
    }
}

/// Supplies bearer tokens. Implemented by `AssetaAuth.AuthSession`.
public protocol AccessTokenProvider: Sendable {
    /// A currently valid access token, refreshing first if it is about to expire.
    func validAccessToken() async throws -> String
    /// Called after the server rejected `rejected` with 401; must return a different, refreshed
    /// token or throw (e.g. ``APIError/notAuthenticated``) if the session is gone.
    func refreshedAccessToken(rejected: String) async throws -> String
}
