import AssetaNetwork
import AssetaSecurity
import Foundation

/// Talks to the Keycloak token and logout endpoints (form-encoded, RFC 6749).
public struct TokenClient: Sendable {
    let config: OIDCConfiguration
    let transport: any HTTPTransport
    let now: @Sendable () -> Date

    public init(config: OIDCConfiguration, transport: any HTTPTransport, now: @escaping @Sendable () -> Date = { Date() }) {
        self.config = config
        self.transport = transport
        self.now = now
    }

    public func exchange(code: String, pending: PendingAuthorization) async throws -> StoredTokens {
        let tokens = try await post(pending.metadata.tokenEndpoint, [
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirectURI.absoluteString,
            "client_id": config.clientID,
            "code_verifier": pending.pkce.verifier,
        ], previous: nil)
        guard let idToken = tokens.idToken else { throw AuthError.invalidIDToken(reason: "missing id_token") }
        try IDTokenValidator.validate(idToken, config: config, metadata: pending.metadata,
                                      expectedNonce: pending.nonce, now: now())
        return tokens
    }

    public func refresh(_ current: StoredTokens, metadata: OIDCProviderMetadata) async throws -> StoredTokens {
        guard let refreshToken = current.refreshToken else { throw AuthError.notSignedIn }
        return try await post(metadata.tokenEndpoint, [
            "grant_type": "refresh_token",
            "refresh_token": refreshToken,
            "client_id": config.clientID,
        ], previous: current)
    }

    /// Ends the Keycloak user session server-side (back-channel logout with the refresh token,
    /// supported by Keycloak's end-session endpoint for public clients).
    public func endSession(_ tokens: StoredTokens, metadata: OIDCProviderMetadata) async throws {
        guard let endpoint = metadata.endSessionEndpoint, let refreshToken = tokens.refreshToken else { return }
        let (data, response) = try await transport.send(formRequest(endpoint, [
            "client_id": config.clientID,
            "refresh_token": refreshToken,
        ]))
        guard (200..<300).contains(response.statusCode) else { throw tokenError(data, response.statusCode) }
    }

    // MARK: - Private

    private struct TokenResponse: Decodable {
        let accessToken: String
        let tokenType: String
        let expiresIn: Int
        let refreshToken: String?
        let refreshExpiresIn: Int?
        let idToken: String?

        enum CodingKeys: String, CodingKey {
            case accessToken = "access_token", tokenType = "token_type", expiresIn = "expires_in"
            case refreshToken = "refresh_token", refreshExpiresIn = "refresh_expires_in", idToken = "id_token"
        }
    }

    private func post(_ endpoint: URL, _ form: [String: String], previous: StoredTokens?) async throws -> StoredTokens {
        let issuedAt = now()
        let (data, response) = try await transport.send(formRequest(endpoint, form))
        guard response.statusCode == 200 else { throw tokenError(data, response.statusCode) }
        guard let decoded = try? JSONDecoder().decode(TokenResponse.self, from: data),
              decoded.tokenType.caseInsensitiveCompare("bearer") == .orderedSame
        else { throw AuthError.invalidTokenResponse }
        // Keycloak returns refresh_expires_in = 0 for offline tokens (no fixed expiry).
        let refreshExpiry = decoded.refreshExpiresIn.flatMap { $0 > 0 ? issuedAt.addingTimeInterval(TimeInterval($0)) : nil }
        return StoredTokens(
            accessToken: decoded.accessToken,
            accessTokenExpiresAt: issuedAt.addingTimeInterval(TimeInterval(decoded.expiresIn)),
            refreshToken: decoded.refreshToken ?? previous?.refreshToken,
            refreshTokenExpiresAt: decoded.refreshToken == nil ? previous?.refreshTokenExpiresAt : refreshExpiry,
            idToken: decoded.idToken ?? previous?.idToken
        )
    }

    private func formRequest(_ endpoint: URL, _ form: [String: String]) -> URLRequest {
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = Data(Self.formEncode(form).utf8)
        return request
    }

    static func formEncode(_ form: [String: String]) -> String {
        var allowed = CharacterSet.alphanumerics
        allowed.insert(charactersIn: "-._~")
        return form.sorted { $0.key < $1.key }.map { key, value in
            let k = key.addingPercentEncoding(withAllowedCharacters: allowed) ?? key
            let v = value.addingPercentEncoding(withAllowedCharacters: allowed) ?? value
            return "\(k)=\(v)"
        }.joined(separator: "&")
    }

    private func tokenError(_ data: Data, _ status: Int) -> AuthError {
        struct OAuthError: Decodable {
            let error: String
            let errorDescription: String?
            enum CodingKeys: String, CodingKey { case error, errorDescription = "error_description" }
        }
        let body = try? JSONDecoder().decode(OAuthError.self, from: data)
        return .tokenEndpoint(status: status, code: body?.error, description: body?.errorDescription)
    }
}
