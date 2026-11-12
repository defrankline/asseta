@testable import AssetaAppShell
import AssetaAuth
import AssetaModel
import AssetaNetwork
import AssetaSecurity
import AssetaTestSupport
import Foundation
import Testing

/// "Delete my account", a deleted or disabled account (USER_INACTIVE) and the access banner (same cases as Android).
@MainActor
struct AccountDeletionTests {
    let secrets = InMemorySecretStore()

    nonisolated static let deleted = #"{"user_id":"6f1c2a1e-0b7a-4c55-9d8e-1f2a3b4c5d6e","display_name":"Former user 6f1c2a1e","#
        + #""deleted_at":"2026-11-12T08:00:00Z","companies":["Acme Plant Hire"]}"#

    nonisolated static func error(_ code: String, _ message: String) -> Data {
        Fixtures.json(#"{"error":{"code":"\#(code)","message":"\#(message)","correlation_id":"c1"}}"#)
    }

    /// A signed-in session whose API answers `/me` with the fixture and other paths with `other`.
    func makeModel(other: @escaping @Sendable (URLRequest) throws -> (Int, Data))
        throws -> (SessionModel, MockTransport) {
        try TokenStore(store: secrets).save(StoredTokens(
            accessToken: "a", accessTokenExpiresAt: Date().addingTimeInterval(3600),
            refreshToken: "r", refreshTokenExpiresAt: nil, idToken: nil))
        let oidc = OIDCConfiguration(issuer: URL(string: "https://id.example.test/realms/asseta")!,
                                     redirectURI: URL(string: "com.asseta.owner:/oauth2redirect")!,
                                     postLogoutRedirectURI: URL(string: "com.asseta.owner:/logout")!)
        let auth = AuthSession(config: oidc, transport: MockTransport { _ in (200, SessionModelTests.discovery) },
                               tokenStore: TokenStore(store: secrets))
        let transport = MockTransport { request in
            if request.url?.path == "/api/v1/me" { return (200, Fixtures.json(Fixtures.meJSON)) }
            return try other(request)
        }
        let api = APIClient(baseURL: URL(string: "https://api.example.test")!, transport: transport, tokens: auth,
                            userInactive: UserInactiveSignal())
        return (SessionModel(auth: auth, api: api), transport)
    }

    @Test func successErasesLocalDataSignsOutAndSaysTheAccountWasDeleted() async throws {
        let (model, transport) = try makeModel { _ in (200, Fixtures.json(Self.deleted)) }
        await model.start()
        var erased = false
        var signedOut = false
        model.onSignOut = { signedOut = true }
        model.accountDeletionHooks = AccountDeletionHooks(unsyncedCount: { 0 }, syncNow: {}, eraseLocalData: { erased = true })
        let flow = model.makeAccountDeletionFlow(isOnline: true)
        flow.reason = "  Leaving the company  "
        flow.typed = "nope"
        #expect(!flow.canSubmit)
        flow.typed = " DELETE "
        #expect(flow.canSubmit)
        await flow.submit()
        #expect(flow.step == .confirm)
        #expect(await flow.confirm())

        let request = try #require(transport.requests.last { $0.url?.path == "/api/v1/me/account-deletion" })
        #expect(request.httpMethod == "POST")
        #expect(request.value(forHTTPHeaderField: "X-Tenant-ID") == nil)
        #expect(request.value(forHTTPHeaderField: "Idempotency-Key") != nil)
        let body = try #require(try JSONSerialization.jsonObject(with: request.httpBody ?? Data()) as? [String: Any])
        #expect(body["confirm"] as? Bool == true)
        #expect(body["reason"] as? String == "Leaving the company")
        #expect(erased && signedOut)
        #expect(model.phase == .signedOut)
        #expect(model.selectedTenant == nil)
        #expect(model.errorMessage == "Your account was deleted.")
        #expect(try TokenStore(store: secrets).load() == nil)
    }

    @Test func lastOwnerShowsTheServerMessageAndStaysSignedIn() async throws {
        let message = "You are the last owner of Acme Plant Hire. Give someone else the owner role, or close the company."
        let (model, _) = try makeModel { _ in (422, Self.error("LAST_OWNER", message)) }
        await model.start()
        let flow = model.makeAccountDeletionFlow(isOnline: true)
        flow.typed = "DELETE"
        await flow.submit()
        #expect(!(await flow.confirm()))
        #expect(flow.error == message)
        #expect(flow.step == .form)
        guard case .ready = model.phase else { Issue.record("signed out: \(model.phase)"); return }
        #expect(try TokenStore(store: secrets).load() != nil)
    }

    @Test func platformAccountIsExplained() async throws {
        let (model, _) = try makeModel { _ in (422, Self.error("PLATFORM_ACCOUNT", "Platform accounts are closed elsewhere")) }
        await model.start()
        let flow = model.makeAccountDeletionFlow(isOnline: true)
        flow.typed = "DELETE"
        await flow.submit()
        await flow.confirm()
        #expect(flow.error == "Platform accounts are removed by the platform owner.")
        #expect(AccountDeletionText.message(for: APIError.transport(code: -1009, message: "offline", correlationID: "c"))
            == "Cannot reach Asseta. Check your connection and try again.")
    }

    @Test func offlineSendsNothing() async throws {
        let (model, transport) = try makeModel { _ in (200, Fixtures.json(Self.deleted)) }
        await model.start()
        let flow = model.makeAccountDeletionFlow(isOnline: false)
        flow.typed = "DELETE"
        #expect(!flow.canSubmit)
        await flow.submit()
        #expect(flow.error == "Connect to the internet to delete your account.")
        #expect(flow.step == .form)
        #expect(!(await flow.confirm()))
        #expect(!transport.requests.contains { $0.url?.path == "/api/v1/me/account-deletion" })
    }

    @Test func unsyncedWorkIsWarnedAboutAndSyncFirstChecksAgain() async throws {
        var waiting = 3
        var syncs = 0
        let hooks = AccountDeletionHooks(unsyncedCount: { waiting }, syncNow: { syncs += 1; waiting -= 2 },
                                         eraseLocalData: {})
        var deleted = 0
        let flow = AccountDeletionFlow(isOnline: true, hooks: hooks) { _ in deleted += 1 }
        flow.typed = "DELETE"
        await flow.submit()
        #expect(flow.step == .unsynced(3))
        #expect(AccountDeletionText.unsyncedTitle == "Records not yet sent will be lost")
        #expect(AccountDeletionText.unsyncedMessage(3)
            == "3 item(s) on this phone are not synced yet. If you delete your account now they are lost. Sync first to send them.")
        await flow.syncFirst()
        #expect(flow.step == .unsynced(1))
        await flow.syncFirst()
        #expect(flow.step == .confirm)
        #expect(syncs == 2)
        flow.cancel()
        waiting = 4
        await flow.submit()
        flow.deleteAnyway()
        #expect(flow.step == .confirm)
        #expect(await flow.confirm())
        #expect(deleted == 1)
    }

    @Test func userInactiveAnywhereSignsOutWithAnExplanation() async throws {
        let (model, _) = try makeModel { _ in (403, Self.error("USER_INACTIVE", "User is deactivated")) }
        await model.start()
        guard case .ready = model.phase else { Issue.record("not ready"); return }
        // Any call (here a tenant-scoped one) answering 403 USER_INACTIVE ends the session.
        await #expect(throws: APIError.self) {
            _ = try await model.tenantClient?.send(APIRequest<EmptyResponse>.get("/api/v1/tenant/jobs"))
        }
        for _ in 0..<20 where model.phase != .signedOut { await Task.yield() }
        #expect(model.phase == .signedOut)
        #expect(model.errorMessage == "This account was deleted or disabled.")
        #expect(try TokenStore(store: secrets).load() == nil)
    }

    @Test func userInactiveOnProfileSignsOut() async throws {
        try TokenStore(store: secrets).save(StoredTokens(
            accessToken: "a", accessTokenExpiresAt: Date().addingTimeInterval(3600),
            refreshToken: "r", refreshTokenExpiresAt: nil, idToken: nil))
        let oidc = OIDCConfiguration(issuer: URL(string: "https://id.example.test/realms/asseta")!,
                                     redirectURI: URL(string: "com.asseta.owner:/oauth2redirect")!,
                                     postLogoutRedirectURI: URL(string: "com.asseta.owner:/logout")!)
        let auth = AuthSession(config: oidc, transport: MockTransport { _ in (200, SessionModelTests.discovery) },
                               tokenStore: TokenStore(store: secrets))
        let api = APIClient(baseURL: URL(string: "https://api.example.test")!,
                            transport: MockTransport { _ in (403, Self.error("USER_INACTIVE", "User is deactivated")) },
                            tokens: auth)
        let model = SessionModel(auth: auth, api: api)
        await model.start()
        #expect(model.phase == .signedOut)
        #expect(model.errorMessage == "This account was deleted or disabled.")
    }

    @Test func bannerShowsTheAccessReason() throws {
        let json = #"{"tenant_id":"11111111-1111-4111-8111-111111111111","name":"Acme","status":"ACTIVE","#
            + #""access_state":"READ_ONLY","permissions":[],"menus":[],"#
            + #""access_state_reason":"Company closure requested: all its data will be deleted on 2026-12-12"}"#
        let tenant = try AssetaJSON.decoder().decode(TenantMembership.self, from: Fixtures.json(json))
        #expect(AccessBanner.text(tenant) == "Company closure requested: all its data will be deleted on 2026-12-12")
        let me = try AssetaJSON.decoder().decode(MeResponse.self, from: Fixtures.json(Fixtures.meJSON))
        #expect(me.tenants[0].accessStateReason == nil)
        #expect(AccessBanner.text(me.tenants[0]) == nil)
        let blank = TenantMembership(tenantID: UUID(), name: "B", status: tenant.status, accessState: tenant.accessState,
                                     permissions: [], menus: [], accessStateReason: "  ")
        #expect(AccessBanner.text(blank) == nil)
    }
}
