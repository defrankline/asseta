@testable import AssetaAppShell
import AssetaAuth
import AssetaModel
import AssetaNetwork
import AssetaSecurity
import AssetaTestSupport
import Foundation
import Testing

@MainActor
struct SessionModelTests {
    let secrets = InMemorySecretStore()
    nonisolated static let discovery = Fixtures.json("""
    {"issuer":"https://id.example.test/realms/asseta","authorization_endpoint":"https://id.example.test/a",
     "token_endpoint":"https://id.example.test/t"}
    """)

    func makeModel(me: @escaping @Sendable (URLRequest) throws -> (Int, Data)) throws -> SessionModel {
        try TokenStore(store: secrets).save(StoredTokens(
            accessToken: "a", accessTokenExpiresAt: Date().addingTimeInterval(3600),
            refreshToken: "r", refreshTokenExpiresAt: nil, idToken: nil))
        let oidc = OIDCConfiguration(issuer: URL(string: "https://id.example.test/realms/asseta")!,
                                     redirectURI: URL(string: "com.asseta.owner:/oauth2redirect")!,
                                     postLogoutRedirectURI: URL(string: "com.asseta.owner:/logout")!)
        let auth = AuthSession(config: oidc,
                               transport: MockTransport { _ in (200, Self.discovery) }, tokenStore: TokenStore(store: secrets))
        let api = APIClient(baseURL: URL(string: "https://api.example.test")!, transport: MockTransport(handler: me),
                            tokens: auth)
        return SessionModel(auth: auth, api: api)
    }

    @Test func restoresSessionLoadsProfileAndAutoSelectsOnlyEnterableTenant() async throws {
        let model = try makeModel { _ in (200, Fixtures.json(Fixtures.meJSON)) }
        await model.start()
        guard case let .ready(me) = model.phase else { Issue.record("not ready: \(model.phase)"); return }
        #expect(me.tenants.count == 2)
        // The BLOCKED tenant is not enterable, so the single FULL tenant is selected.
        #expect(model.selectedTenant?.name == "Acme Plant Hire")
        #expect(model.selectedTenant?.orderedMenus.map(\.key) == ["jobs", "meter"])
        #expect(model.tenantClient?.tenantID == model.selectedTenant?.tenantID)
    }

    @Test func blockedTenantCannotBeSelected() async throws {
        let model = try makeModel { _ in (200, Fixtures.json(Fixtures.meJSON)) }
        await model.start()
        guard case let .ready(me) = model.phase else { Issue.record("not ready"); return }
        model.clearTenantSelection()
        model.selectTenant(me.tenants[1])
        #expect(model.selectedTenant == nil)
    }

    @Test func serverErrorShowsCorrelationReference() async throws {
        let body = #"{"error":{"code":"DEPENDENCY_UNAVAILABLE","message":"Try later","correlation_id":"abcdef12-3456"}}"#
        let model = try makeModel { _ in (503, Fixtures.json(body)) }
        await model.start()
        #expect(model.phase == .profileUnavailable)
        #expect(model.errorMessage == "Try later (ref abcdef12)")
    }

    @Test func cancelledBrowserLeavesNoError() async throws {
        let model = try makeModel { _ in (200, Fixtures.json(Fixtures.meJSON)) }
        await model.signOut()
        var opened: URL?
        await model.signIn { url, scheme in
            opened = url
            #expect(scheme == "com.asseta.owner")
            throw AuthError.userCancelled
        }
        #expect(opened?.host == "id.example.test")
        #expect(model.phase == .signedOut)
        #expect(model.errorMessage == nil)
    }

    @Test func signOutClearsState() async throws {
        let model = try makeModel { _ in (200, Fixtures.json(Fixtures.meJSON)) }
        await model.start()
        await model.signOut()
        #expect(model.phase == .signedOut)
        #expect(model.selectedTenant == nil)
        #expect(try TokenStore(store: secrets).load() == nil)
    }

    /// Runs "Change password" with a fake browser that answers with `query` (plus the request's state).
    func changePassword(_ model: SessionModel, answering query: String?) async -> URL? {
        var opened: URL?
        await model.changePassword { url, scheme in
            opened = url
            #expect(scheme == "com.asseta.owner")
            guard let query else { throw AuthError.userCancelled }
            let state = URLComponents(url: url, resolvingAgainstBaseURL: false)?
                .queryItems?.first { $0.name == "state" }?.value ?? ""
            return URL(string: "com.asseta.owner:/oauth2redirect?state=\(state)&\(query)")!
        }
        return opened
    }

    @Test func passwordChangeOpensKeycloakActionAndConfirmsSuccess() async throws {
        let model = try makeModel { _ in (200, Fixtures.json(Fixtures.meJSON)) }
        await model.start()
        let opened = await changePassword(model, answering: "kc_action_status=success")
        let items = URLComponents(url: try #require(opened), resolvingAgainstBaseURL: false)?.queryItems ?? []
        #expect(items.first { $0.name == "kc_action" }?.value == "UPDATE_PASSWORD")
        #expect(items.first { $0.name == "redirect_uri" }?.value == "com.asseta.owner:/oauth2redirect")
        #expect(model.passwordChange == .changed)
        #expect(PasswordChangeText.changed == "Password changed.")
        model.dismissPasswordChange()
        #expect(model.passwordChange == .idle)
        #expect(try TokenStore(store: secrets).load() != nil)
    }

    @Test func passwordChangeCancelShowsNothingAndErrorExplains() async throws {
        let model = try makeModel { _ in (200, Fixtures.json(Fixtures.meJSON)) }
        await model.start()
        _ = await changePassword(model, answering: "kc_action_status=cancelled")
        #expect(model.passwordChange == .idle)
        _ = await changePassword(model, answering: nil) // browser closed
        #expect(model.passwordChange == .idle)
        _ = await changePassword(model, answering: "kc_action_status=error")
        #expect(model.passwordChange == .failed(PasswordChangeText.failed))
        model.dismissPasswordChange()
        _ = await changePassword(model, answering: "error=temporarily_unavailable")
        #expect(model.passwordChange == .failed(PasswordChangeText.failed))
        // The user stays signed in whatever the outcome.
        #expect(try TokenStore(store: secrets).load() != nil)
        guard case .ready = model.phase else { Issue.record("not ready: \(model.phase)"); return }
    }

    @Test func configurationLoadsFromInfoDictionary() throws {
        let config = try AppConfiguration.load(from: [
            "CFBundleIdentifier": "com.asseta.supervisor",
            "AssetaAPIBaseURL": "https://api.example.test",
            "AssetaOIDCIssuer": "https://id.example.test/realms/asseta",
            "AssetaOIDCRedirectURI": "com.asseta.supervisor:/oauth2redirect",
            "AssetaOIDCPostLogoutRedirectURI": "com.asseta.supervisor:/logout",
        ])
        #expect(config.oidc.clientID == "asseta-mobile")
        #expect(config.oidc.callbackScheme == "com.asseta.supervisor")
        #expect(config.oidc.postLogoutRedirectURI.absoluteString == "com.asseta.supervisor:/logout")
        #expect(throws: AppConfiguration.LoadError.self) {
            try AppConfiguration.load(from: [
                "CFBundleIdentifier": "x", "AssetaAPIBaseURL": "https://a.test", "AssetaOIDCIssuer": "https://i.test",
                "AssetaOIDCRedirectURI": "com.asseta.owner:/oauth2redirect",
                "AssetaOIDCPostLogoutRedirectURI": "com.asseta.supervisor:/logout",
            ])
        }
        #expect(throws: AppConfiguration.LoadError.missingKey("AssetaAPIBaseURL")) {
            try AppConfiguration.load(from: ["CFBundleIdentifier": "x"])
        }
    }
}
