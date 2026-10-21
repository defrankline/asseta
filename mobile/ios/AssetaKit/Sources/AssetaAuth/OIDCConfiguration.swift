import AssetaNetwork
import Foundation

/// Static OIDC client configuration. Keycloak is authoritative for authentication and
/// authorization; the app is a public client using Authorization Code + PKCE (S256).
public struct OIDCConfiguration: Sendable, Equatable {
    /// Realm issuer, e.g. `https://id.example.com/realms/asseta`.
    public let issuer: URL
    public let clientID: String
    /// Per-app redirect, supplied by the app target's configuration
    /// (e.g. `com.asseta.supervisor:/oauth2redirect`). Never defaulted in AssetaKit.
    public let redirectURI: URL
    /// Per-app post-logout redirect (e.g. `com.asseta.supervisor:/logout`), registered in Keycloak
    /// for browser-based RP-initiated logout.
    public let postLogoutRedirectURI: URL
    public let scopes: [String]

    public init(
        issuer: URL,
        clientID: String = "asseta-mobile",
        redirectURI: URL,
        postLogoutRedirectURI: URL,
        scopes: [String] = ["openid", "profile", "email"]
    ) {
        self.issuer = issuer
        self.clientID = clientID
        self.redirectURI = redirectURI
        self.postLogoutRedirectURI = postLogoutRedirectURI
        self.scopes = scopes
    }

    /// Custom URL scheme the browser session listens for (the app's own scheme).
    public var callbackScheme: String { redirectURI.scheme ?? "" }

    /// Checks the redirects are private-use custom-scheme URIs (RFC 8252 §7.1) sharing one scheme.
    public func validateRedirects() throws {
        for uri in [redirectURI, postLogoutRedirectURI] {
            guard let scheme = uri.scheme?.lowercased(), scheme.contains("."),
                  !["http", "https"].contains(scheme)
            else { throw AuthError.invalidRedirectURI(uri.absoluteString) }
        }
        guard redirectURI.scheme?.lowercased() == postLogoutRedirectURI.scheme?.lowercased() else {
            throw AuthError.invalidRedirectURI(postLogoutRedirectURI.absoluteString)
        }
    }
}

/// Subset of the OpenID Provider metadata the app needs.
public struct OIDCProviderMetadata: Codable, Sendable, Equatable {
    public let issuer: String
    public let authorizationEndpoint: URL
    public let tokenEndpoint: URL
    public let endSessionEndpoint: URL?
    public let revocationEndpoint: URL?

    public init(issuer: String, authorizationEndpoint: URL, tokenEndpoint: URL,
                endSessionEndpoint: URL?, revocationEndpoint: URL?) {
        self.issuer = issuer
        self.authorizationEndpoint = authorizationEndpoint
        self.tokenEndpoint = tokenEndpoint
        self.endSessionEndpoint = endSessionEndpoint
        self.revocationEndpoint = revocationEndpoint
    }

    enum CodingKeys: String, CodingKey {
        case issuer
        case authorizationEndpoint = "authorization_endpoint"
        case tokenEndpoint = "token_endpoint"
        case endSessionEndpoint = "end_session_endpoint"
        case revocationEndpoint = "revocation_endpoint"
    }

    /// Fetches `/.well-known/openid-configuration` and verifies the issuer matches exactly
    /// (OIDC Discovery §4.3) to prevent endpoint substitution.
    public static func discover(_ config: OIDCConfiguration, transport: any HTTPTransport) async throws -> OIDCProviderMetadata {
        let url = config.issuer.appendingPathComponent(".well-known/openid-configuration")
        var request = URLRequest(url: url)
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await transport.send(request)
        guard response.statusCode == 200 else { throw AuthError.discoveryFailed(status: response.statusCode) }
        let metadata = try JSONDecoder().decode(OIDCProviderMetadata.self, from: data)
        guard metadata.issuer == config.issuer.absoluteString else {
            throw AuthError.issuerMismatch(expected: config.issuer.absoluteString, actual: metadata.issuer)
        }
        return metadata
    }
}

public enum AuthError: Error, Equatable, Sendable {
    case discoveryFailed(status: Int)
    case issuerMismatch(expected: String, actual: String)
    case stateMismatch
    case missingAuthorizationCode
    /// The authorization server returned `error=` on the redirect (e.g. `access_denied`).
    case authorizationDenied(code: String, description: String?)
    case userCancelled
    /// Token endpoint rejected the request (e.g. `invalid_grant` for an expired refresh token).
    case tokenEndpoint(status: Int, code: String?, description: String?)
    case invalidTokenResponse
    case invalidIDToken(reason: String)
    case notSignedIn
    case invalidRedirectURI(String)
}
