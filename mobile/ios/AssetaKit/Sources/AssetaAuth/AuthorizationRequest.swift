import Foundation

/// An in-flight authorization attempt. Holds the secrets (verifier, state, nonce) that must
/// match the redirect; it lives only in memory for the duration of the browser session.
public struct PendingAuthorization: Sendable, Equatable {
    public let url: URL
    public let state: String
    public let nonce: String
    public let pkce: PKCE
    public let metadata: OIDCProviderMetadata

    public static func make(config: OIDCConfiguration, metadata: OIDCProviderMetadata) throws -> PendingAuthorization {
        let pkce = try PKCE.generate()
        let state = try PKCE.randomToken()
        let nonce = try PKCE.randomToken()
        guard var components = URLComponents(url: metadata.authorizationEndpoint, resolvingAgainstBaseURL: false) else {
            throw URLError(.badURL)
        }
        components.queryItems = (components.queryItems ?? []) + [
            URLQueryItem(name: "response_type", value: "code"),
            URLQueryItem(name: "client_id", value: config.clientID),
            URLQueryItem(name: "redirect_uri", value: config.redirectURI.absoluteString),
            URLQueryItem(name: "scope", value: config.scopes.joined(separator: " ")),
            URLQueryItem(name: "state", value: state),
            URLQueryItem(name: "nonce", value: nonce),
            URLQueryItem(name: "code_challenge", value: pkce.challenge),
            URLQueryItem(name: "code_challenge_method", value: pkce.method),
        ]
        guard let url = components.url else { throw URLError(.badURL) }
        return PendingAuthorization(url: url, state: state, nonce: nonce, pkce: pkce, metadata: metadata)
    }

    /// Validates the redirect and extracts the authorization code.
    public func authorizationCode(from callback: URL, config: OIDCConfiguration) throws -> String {
        guard let components = URLComponents(url: callback, resolvingAgainstBaseURL: false),
              callback.scheme?.lowercased() == config.redirectURI.scheme?.lowercased(),
              components.path == (URLComponents(url: config.redirectURI, resolvingAgainstBaseURL: false)?.path ?? "")
        else { throw AuthError.missingAuthorizationCode }
        let items = Dictionary(
            (components.queryItems ?? []).map { ($0.name, $0.value ?? "") },
            uniquingKeysWith: { first, _ in first }
        )
        // Check state before anything else, including error responses (RFC 6749 §10.12).
        guard items["state"] == state else { throw AuthError.stateMismatch }
        if let error = items["error"] {
            throw AuthError.authorizationDenied(code: error, description: items["error_description"])
        }
        guard let code = items["code"], !code.isEmpty else { throw AuthError.missingAuthorizationCode }
        return code
    }
}
