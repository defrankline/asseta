import Foundation

/// Validates ID token claims per OIDC Core §3.1.3.7.
///
/// The token is received directly from the token endpoint over TLS, which OIDC Core §3.1.3.7(6)
/// allows in place of signature validation. Claims are checked (iss, aud, azp, exp, nonce) so a
/// replayed or mis-issued token is rejected. Claims are **not** used for authorization.
public enum IDTokenValidator {
    struct Claims: Decodable {
        let iss: String
        let aud: Audience
        let azp: String?
        let exp: TimeInterval
        let nonce: String?
    }

    enum Audience: Decodable {
        case one(String), many([String])
        init(from decoder: any Decoder) throws {
            let container = try decoder.singleValueContainer()
            if let single = try? container.decode(String.self) { self = .one(single) } else {
                self = .many(try container.decode([String].self))
            }
        }
        var values: [String] {
            switch self {
            case let .one(value): [value]
            case let .many(values): values
            }
        }
    }

    public static func validate(
        _ idToken: String,
        config: OIDCConfiguration,
        metadata: OIDCProviderMetadata,
        expectedNonce: String,
        now: Date,
        leeway: TimeInterval = 60
    ) throws {
        let segments = idToken.split(separator: ".", omittingEmptySubsequences: false)
        guard segments.count == 3, let payload = PKCE.decodeBase64URL(String(segments[1])),
              let claims = try? JSONDecoder().decode(Claims.self, from: payload)
        else { throw AuthError.invalidIDToken(reason: "malformed") }
        guard claims.iss == metadata.issuer else { throw AuthError.invalidIDToken(reason: "issuer") }
        let audiences = claims.aud.values
        guard audiences.contains(config.clientID) else { throw AuthError.invalidIDToken(reason: "audience") }
        if audiences.count > 1, claims.azp != config.clientID { throw AuthError.invalidIDToken(reason: "azp") }
        guard Date(timeIntervalSince1970: claims.exp + leeway) > now else { throw AuthError.invalidIDToken(reason: "expired") }
        guard claims.nonce == expectedNonce else { throw AuthError.invalidIDToken(reason: "nonce") }
    }
}
