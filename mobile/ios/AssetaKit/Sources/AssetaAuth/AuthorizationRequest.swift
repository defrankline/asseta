import Foundation

/// An in-flight authorization attempt. Holds the secrets (verifier, state, nonce) that must
/// match the redirect; it lives only in memory for the duration of the browser session.
public struct PendingAuthorization: Sendable, Equatable {
    public let url: URL
    public let state: String
    public let nonce: String
    public let pkce: PKCE
    public let metadata: OIDCProviderMetadata

    /// Builds the sign-in request. `kcAction` adds a Keycloak application-initiated action
    /// (e.g. ``KeycloakAction/updatePassword``) and changes nothing else.
    public static func make(config: OIDCConfiguration, metadata: OIDCProviderMetadata,
                            kcAction: String? = nil) throws -> PendingAuthorization {
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
        ] + (kcAction.map { [URLQueryItem(name: KeycloakAction.parameter, value: $0)] } ?? [])
        guard let url = components.url else { throw URLError(.badURL) }
        return PendingAuthorization(url: url, state: state, nonce: nonce, pkce: pkce, metadata: metadata)
    }

    /// Validates the redirect and extracts the authorization code.
    public func authorizationCode(from callback: URL, config: OIDCConfiguration) throws -> String {
        let items = try callbackParameters(from: callback, config: config)
        guard let code = items["code"], !code.isEmpty else { throw AuthError.missingAuthorizationCode }
        return code
    }

    /// Validates the redirect of a Keycloak application-initiated action: the code (if Keycloak
    /// issued one) and `kc_action_status`.
    public func actionCallback(from callback: URL, config: OIDCConfiguration) throws -> (code: String?, status: String?) {
        let items = try callbackParameters(from: callback, config: config)
        let code = items["code"].flatMap { $0.isEmpty ? nil : $0 }
        return (code, items[KeycloakAction.statusParameter])
    }

    /// Checks scheme, path and state, then surfaces `error=` responses.
    private func callbackParameters(from callback: URL, config: OIDCConfiguration) throws -> [String: String] {
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
        return items
    }
}

/// Keycloak application-initiated actions (`kc_action`): Keycloak shows its own page for the
/// action and reports the result as `kc_action_status` on the redirect.
public enum KeycloakAction {
    public static let parameter = "kc_action"
    public static let statusParameter = "kc_action_status"
    public static let updatePassword = "UPDATE_PASSWORD"
}

/// Result of "Change password" (`kc_action=UPDATE_PASSWORD`), from `kc_action_status`.
public enum PasswordChangeOutcome: Sendable, Equatable {
    case changed
    /// The user backed out; nothing is shown.
    case cancelled
    case failed

    public init(status: String?) {
        switch status {
        case "success": self = .changed
        case "cancelled": self = .cancelled
        default: self = .failed
        }
    }
}
