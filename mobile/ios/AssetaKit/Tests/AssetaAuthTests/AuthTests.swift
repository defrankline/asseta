@testable import AssetaAuth
import AssetaNetwork
import AssetaSecurity
import AssetaTestSupport
import Foundation
import Testing

struct PKCETests {
    @Test func matchesRFC7636AppendixB() {
        let pkce = PKCE(verifier: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
        #expect(pkce.challenge == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
        #expect(pkce.method == "S256")
    }

    @Test func generatedVerifiersAreUniqueAndValidLength() throws {
        let a = try PKCE.generate(), b = try PKCE.generate()
        #expect(a.verifier != b.verifier)
        #expect((43...128).contains(a.verifier.count))
        #expect(a.verifier.allSatisfy { $0.isLetter || $0.isNumber || "-._~".contains($0) })
    }
}

struct AuthorizationRequestTests {
    let keycloak = FakeKeycloak()

    @Test func buildsKeycloakAuthorizationURL() async throws {
        let metadata = try await OIDCProviderMetadata.discover(keycloak.config, transport: keycloak.transport)
        let pending = try PendingAuthorization.make(config: keycloak.config, metadata: metadata)
        let components = try #require(URLComponents(url: pending.url, resolvingAgainstBaseURL: false))
        let items = Dictionary(uniqueKeysWithValues: (components.queryItems ?? []).map { ($0.name, $0.value ?? "") })
        #expect(components.path == "/realms/asseta/protocol/openid-connect/auth")
        #expect(items["client_id"] == "asseta-mobile")
        #expect(items["redirect_uri"] == "com.asseta.supervisor:/oauth2redirect")
        #expect(items["response_type"] == "code")
        #expect(items["code_challenge_method"] == "S256")
        #expect(items["code_challenge"] == pending.pkce.challenge)
        #expect(items["state"] == pending.state)
        #expect(items["scope"]?.split(separator: " ").contains("openid") == true)
    }

    @Test func callbackValidation() async throws {
        let metadata = try await OIDCProviderMetadata.discover(keycloak.config, transport: keycloak.transport)
        let pending = try PendingAuthorization.make(config: keycloak.config, metadata: metadata)
        let base = FakeKeycloak.redirect
        #expect(try pending.authorizationCode(from: URL(string: "\(base)?code=abc&state=\(pending.state)")!,
                                              config: keycloak.config) == "abc")
        #expect(throws: AuthError.stateMismatch) {
            try pending.authorizationCode(from: URL(string: "\(base)?code=abc&state=forged")!, config: keycloak.config)
        }
        #expect(throws: AuthError.authorizationDenied(code: "access_denied", description: nil)) {
            try pending.authorizationCode(from: URL(string: "\(base)?error=access_denied&state=\(pending.state)")!,
                                          config: keycloak.config)
        }
        // Another app's scheme (e.g. the Owner app) or another path must not be accepted.
        #expect(throws: AuthError.missingAuthorizationCode) {
            try pending.authorizationCode(from: URL(string: "com.asseta.owner:/oauth2redirect?code=abc&state=\(pending.state)")!,
                                          config: keycloak.config)
        }
        #expect(throws: AuthError.missingAuthorizationCode) {
            try pending.authorizationCode(from: URL(string: "com.asseta.supervisor:/logout?code=abc&state=\(pending.state)")!,
                                          config: keycloak.config)
        }
    }

    @Test func changePasswordRequestAddsKcActionAndKeepsSignInParameters() async throws {
        let metadata = try await OIDCProviderMetadata.discover(keycloak.config, transport: keycloak.transport)
        func items(_ pending: PendingAuthorization) throws -> [String: String] {
            let components = try #require(URLComponents(url: pending.url, resolvingAgainstBaseURL: false))
            return Dictionary(uniqueKeysWithValues: (components.queryItems ?? []).map { ($0.name, $0.value ?? "") })
        }
        let login = try items(PendingAuthorization.make(config: keycloak.config, metadata: metadata))
        let pending = try PendingAuthorization.make(config: keycloak.config, metadata: metadata,
                                                    kcAction: KeycloakAction.updatePassword)
        let change = try items(pending)
        #expect(change["kc_action"] == "UPDATE_PASSWORD")
        #expect(login["kc_action"] == nil)
        #expect(change["client_id"] == "asseta-mobile")
        #expect(change["redirect_uri"] == "com.asseta.supervisor:/oauth2redirect")
        #expect(change["response_type"] == "code")
        #expect(change["code_challenge_method"] == "S256")
        #expect(change["code_challenge"] == pending.pkce.challenge)
        #expect(change["state"] == pending.state)
        #expect(change["scope"] == login["scope"])
        // Exactly the sign-in parameters plus kc_action.
        #expect(Set(change.keys) == Set(login.keys).union(["kc_action"]))
    }

    @Test func passwordChangeCallbackStatus() async throws {
        let metadata = try await OIDCProviderMetadata.discover(keycloak.config, transport: keycloak.transport)
        let pending = try PendingAuthorization.make(config: keycloak.config, metadata: metadata,
                                                    kcAction: KeycloakAction.updatePassword)
        let base = "\(FakeKeycloak.redirect)?state=\(pending.state)"
        func status(_ query: String) throws -> PasswordChangeOutcome {
            PasswordChangeOutcome(status: try pending.actionCallback(from: URL(string: "\(base)&\(query)")!,
                                                                     config: keycloak.config).status)
        }
        #expect(try status("code=abc&kc_action_status=success") == .changed)
        #expect(try status("code=abc&kc_action_status=cancelled") == .cancelled)
        #expect(try status("code=abc&kc_action_status=error") == .failed)
        #expect(try status("code=abc") == .failed)
        #expect(try pending.actionCallback(from: URL(string: "\(base)&code=abc&kc_action_status=success")!,
                                           config: keycloak.config).code == "abc")
        #expect(throws: AuthError.stateMismatch) {
            try pending.actionCallback(from: URL(string: "\(FakeKeycloak.redirect)?state=forged&kc_action_status=success")!,
                                       config: keycloak.config)
        }
        #expect(throws: AuthError.authorizationDenied(code: "access_denied", description: nil)) {
            try pending.actionCallback(from: URL(string: "\(base)&error=access_denied")!, config: keycloak.config)
        }
    }

    @Test func discoveryRejectsIssuerMismatch() async {
        let other = OIDCConfiguration(issuer: URL(string: "https://id.example.test/realms/other")!,
                                      redirectURI: keycloak.config.redirectURI,
                                      postLogoutRedirectURI: keycloak.config.postLogoutRedirectURI)
        await #expect(throws: AuthError.self) {
            try await OIDCProviderMetadata.discover(other, transport: keycloak.transport)
        }
    }

    @Test func idTokenClaimsAreChecked() throws {
        let metadata = OIDCProviderMetadata(issuer: FakeKeycloak.issuer, authorizationEndpoint: URL(string: "https://x/a")!,
                                            tokenEndpoint: URL(string: "https://x/t")!, endSessionEndpoint: nil,
                                            revocationEndpoint: nil)
        let now = Date()
        func token(_ overrides: [String: Any]) -> String {
            var claims: [String: Any] = ["iss": FakeKeycloak.issuer, "aud": "asseta-mobile",
                                         "exp": now.timeIntervalSince1970 + 60, "nonce": "n1"]
            claims.merge(overrides) { _, new in new }
            return FakeKeycloak.idToken(claims)
        }
        let config = keycloak.config
        try IDTokenValidator.validate(token([:]), config: config, metadata: metadata, expectedNonce: "n1", now: now)
        for (override, reason) in [(["nonce": "n2"], "nonce"), (["aud": "other"], "audience"),
                                   (["iss": "https://evil"], "issuer"),
                                   (["exp": now.timeIntervalSince1970 - 3600], "expired")] as [([String: Any], String)] {
            #expect(throws: AuthError.invalidIDToken(reason: reason)) {
                try IDTokenValidator.validate(token(override), config: config, metadata: metadata,
                                              expectedNonce: "n1", now: now)
            }
        }
    }
}

struct RedirectConfigurationTests {
    func config(_ redirect: String, _ logout: String) -> OIDCConfiguration {
        OIDCConfiguration(issuer: URL(string: FakeKeycloak.issuer)!, redirectURI: URL(string: redirect)!,
                          postLogoutRedirectURI: URL(string: logout)!)
    }

    @Test func acceptsPerAppCustomSchemes() throws {
        try config("com.asseta.supervisor:/oauth2redirect", "com.asseta.supervisor:/logout").validateRedirects()
        try config("com.asseta.owner:/oauth2redirect", "com.asseta.owner:/logout").validateRedirects()
        #expect(config("com.asseta.owner:/oauth2redirect", "com.asseta.owner:/logout").callbackScheme == "com.asseta.owner")
    }

    @Test(arguments: [
        ("https://example.com/cb", "com.asseta.owner:/logout"),
        ("myapp:/cb", "myapp:/logout"),
        ("com.asseta.owner:/oauth2redirect", "com.asseta.supervisor:/logout"),
    ])
    func rejectsUnsafeOrMismatchedRedirects(_ redirect: String, _ logout: String) {
        #expect(throws: AuthError.self) { try config(redirect, logout).validateRedirects() }
    }
}

struct AuthSessionTests {
    let keycloak = FakeKeycloak()
    let secrets = InMemorySecretStore()

    func makeSession(margin: TimeInterval = 60) -> AuthSession {
        AuthSession(config: keycloak.config, transport: keycloak.transport,
                    tokenStore: TokenStore(store: secrets), refreshMargin: margin)
    }

    func signIn(_ session: AuthSession, code: String = "good-code") async throws {
        let pending = try await session.beginSignIn()
        keycloak.remember(pending)
        try await session.completeSignIn(
            callbackURL: URL(string: "\(FakeKeycloak.redirect)?code=\(code)&state=\(pending.state)")!,
            pending: pending)
    }

    @Test func signInExchangesCodeWithPKCEAndPersistsTokens() async throws {
        let session = makeSession()
        #expect(await session.state == .signedOut)
        try await signIn(session)
        #expect(await session.state == .signedIn)
        #expect(try await session.validAccessToken() == "access-1")
        // Persisted in the secret store: a new session instance restores it.
        #expect(try await makeSession().validAccessToken() == "access-1")
    }

    @Test func wrongCodeFailsAndStaysSignedOut() async {
        let session = makeSession()
        await #expect(throws: AuthError.self) { try await signIn(session, code: "bad") }
        #expect(await session.state == .signedOut)
    }

    @Test func refreshesWhenTokenIsAboutToExpire() async throws {
        keycloak.accessTTL = 30 // below the 60 s margin -> refresh on next use
        let session = makeSession()
        try await signIn(session)
        #expect(try await session.validAccessToken() == "access-2")
    }

    @Test func concurrentCallersShareOneRefresh() async throws {
        keycloak.accessTTL = 30
        let session = makeSession()
        try await signIn(session)
        keycloak.accessTTL = 300
        async let a = session.validAccessToken()
        async let b = session.validAccessToken()
        async let c = session.validAccessToken()
        let tokens = try await [a, b, c]
        #expect(Set(tokens) == ["access-2"])
        #expect(keycloak.issued == 2)
    }

    @Test func rejectedTokenTriggersRefresh() async throws {
        let session = makeSession()
        try await signIn(session)
        #expect(try await session.refreshedAccessToken(rejected: "access-1") == "access-2")
        // A stale rejection after someone else refreshed returns the current token without a new call.
        #expect(try await session.refreshedAccessToken(rejected: "access-1") == "access-2")
        #expect(keycloak.issued == 2)
    }

    @Test func revokedRefreshTokenSignsOut() async throws {
        let session = makeSession()
        try await signIn(session)
        keycloak.refreshAllowed = false
        await #expect(throws: APIError.notAuthenticated) {
            try await session.refreshedAccessToken(rejected: "access-1")
        }
        #expect(await session.state == .signedOut)
        #expect(try TokenStore(store: secrets).load() == nil)
    }

    @Test func offlineRefreshKeepsSession() async throws {
        keycloak.accessTTL = 30
        let session = makeSession()
        try await signIn(session)
        keycloak.transport.setHandler { _ in throw URLError(.notConnectedToInternet) }
        await #expect(throws: URLError.self) { try await session.validAccessToken() }
        #expect(await session.state == .signedIn)
    }

    @Test func signOutEndsServerSessionAndClearsTokens() async throws {
        let session = makeSession()
        try await signIn(session)
        #expect(await session.signOut())
        #expect(await session.state == .signedOut)
        #expect(try TokenStore(store: secrets).load() == nil)
        #expect(keycloak.endSessionCalls.first?["refresh_token"] == "refresh-1")
        #expect(keycloak.endSessionCalls.first?["client_id"] == "asseta-mobile")
        await #expect(throws: APIError.notAuthenticated) { try await session.validAccessToken() }
    }

    @Test func passwordChangeExchangesCodeAndReplacesTokens() async throws {
        let session = makeSession()
        try await signIn(session)
        let pending = try await session.beginPasswordChange()
        keycloak.remember(pending)
        let outcome = try await session.completePasswordChange(
            callbackURL: URL(string: "\(FakeKeycloak.redirect)?code=good-code&state=\(pending.state)&kc_action_status=success")!,
            pending: pending)
        #expect(outcome == .changed)
        #expect(await session.state == .signedIn)
        #expect(try await session.validAccessToken() == "access-2")
        #expect(try TokenStore(store: secrets).load()?.refreshToken == "refresh-2")
    }

    @Test func cancelledPasswordChangeKeepsSession() async throws {
        let session = makeSession()
        try await signIn(session)
        let pending = try await session.beginPasswordChange()
        keycloak.remember(pending)
        let outcome = try await session.completePasswordChange(
            callbackURL: URL(string: "\(FakeKeycloak.redirect)?code=good-code&state=\(pending.state)&kc_action_status=cancelled")!,
            pending: pending)
        #expect(outcome == .cancelled)
        #expect(await session.state == .signedIn)
    }

    @Test func failedPasswordChangeCodeExchangeKeepsOldTokens() async throws {
        let session = makeSession()
        try await signIn(session)
        let pending = try await session.beginPasswordChange()
        keycloak.remember(pending)
        await #expect(throws: AuthError.self) {
            try await session.completePasswordChange(
                callbackURL: URL(string: "\(FakeKeycloak.redirect)?code=bad&state=\(pending.state)&kc_action_status=success")!,
                pending: pending)
        }
        #expect(await session.state == .signedIn)
        #expect(try await session.validAccessToken() == "access-1")
    }

    @Test func signOutOfflineStillClearsLocalTokens() async throws {
        let session = makeSession()
        try await signIn(session)
        keycloak.transport.setHandler { _ in throw URLError(.notConnectedToInternet) }
        #expect(await session.signOut() == false)
        #expect(try TokenStore(store: secrets).load() == nil)
    }
}
