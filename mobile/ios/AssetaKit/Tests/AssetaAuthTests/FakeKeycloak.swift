@testable import AssetaAuth
import AssetaTestSupport
import Foundation

/// In-memory stand-in for the Keycloak endpoints the app uses. Verifies PKCE like the server would.
final class FakeKeycloak: @unchecked Sendable {
    // @unchecked: mutable state guarded by `lock`.
    static let issuer = "https://id.example.test/realms/asseta"
    let lock = NSLock()
    var challenge: String?
    var nonce: String?
    var refreshAllowed = true
    var issued = 0
    var endSessionCalls: [[String: String]] = []
    var accessTTL = 300
    var idTokenAudience: Any = "asseta-mobile"

    static let redirect = "com.asseta.supervisor:/oauth2redirect"
    var config: OIDCConfiguration {
        OIDCConfiguration(issuer: URL(string: Self.issuer)!, redirectURI: URL(string: Self.redirect)!,
                          postLogoutRedirectURI: URL(string: "com.asseta.supervisor:/logout")!)
    }

    lazy var transport = MockTransport { [unowned self] request in try self.handle(request) }

    static func idToken(_ claims: [String: Any]) -> String {
        let header = PKCE.base64URL(Data(#"{"alg":"RS256","typ":"JWT"}"#.utf8))
        let payload = PKCE.base64URL(try! JSONSerialization.data(withJSONObject: claims))
        return "\(header).\(payload).c2ln"
    }

    func remember(_ pending: PendingAuthorization) {
        let items = URLComponents(url: pending.url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        lock.withLock {
            challenge = items.first { $0.name == "code_challenge" }?.value
            nonce = items.first { $0.name == "nonce" }?.value
        }
    }

    private func handle(_ request: URLRequest) throws -> (Int, Data) {
        let path = request.url!.path
        if path.hasSuffix("/.well-known/openid-configuration") {
            let base = Self.issuer + "/protocol/openid-connect"
            return (200, Data("""
            {"issuer":"\(Self.issuer)","authorization_endpoint":"\(base)/auth","token_endpoint":"\(base)/token",
             "end_session_endpoint":"\(base)/logout","revocation_endpoint":"\(base)/revoke"}
            """.utf8))
        }
        let form = MockTransport.form(request)
        return lock.withLock {
            if path.hasSuffix("/logout") {
                endSessionCalls.append(form)
                return (204, Data())
            }
            switch form["grant_type"] {
            case "authorization_code":
                guard form["code"] == "good-code", form["client_id"] == "asseta-mobile",
                      let verifier = form["code_verifier"], PKCE(verifier: verifier).challenge == challenge
                else { return (400, Data(#"{"error":"invalid_grant"}"#.utf8)) }
                return (200, tokenResponse(includeID: true))
            case "refresh_token":
                guard refreshAllowed, form["refresh_token"]?.hasPrefix("refresh-") == true else {
                    return (400, Data(#"{"error":"invalid_grant","error_description":"Token is not active"}"#.utf8))
                }
                return (200, tokenResponse(includeID: false))
            default:
                return (400, Data(#"{"error":"unsupported_grant_type"}"#.utf8))
            }
        }
    }

    private func tokenResponse(includeID: Bool) -> Data {
        issued += 1
        var body: [String: Any] = [
            "access_token": "access-\(issued)", "token_type": "Bearer", "expires_in": accessTTL,
            "refresh_token": "refresh-\(issued)", "refresh_expires_in": 1800,
        ]
        if includeID {
            body["id_token"] = Self.idToken([
                "iss": Self.issuer, "aud": idTokenAudience, "exp": Date().timeIntervalSince1970 + 300,
                "nonce": nonce ?? "", "sub": "user-1",
            ])
        }
        return try! JSONSerialization.data(withJSONObject: body)
    }
}
