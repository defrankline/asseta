@testable import AssetaAppShell
import AssetaAuth
import AssetaModel
import AssetaNetwork
import AssetaSecurity
import AssetaTestSupport
import Foundation
import Testing

/// Owner app hooks on the shared session: cached `/me` when offline, and the sign-out wipe hook.
@MainActor
struct OfflineProfileTests {
    let base = SessionModelTests()

    final class Box { var saved: MeResponse?; var wiped = 0 }

    func cache(_ box: Box) -> SessionModel.ProfileCache {
        SessionModel.ProfileCache(load: { box.saved }, save: { box.saved = $0 })
    }

    @Test func profileIsSavedOnlineAndUsedWhenOffline() async throws {
        let box = Box()
        let online = try base.makeModel { _ in (200, Fixtures.json(Fixtures.meJSON)) }
        online.profileCache = cache(box)
        await online.start()
        #expect(box.saved?.displayName == "Sam Supervisor" && !online.isProfileFromCache)

        let offline = try base.makeModel { _ in throw URLError(.notConnectedToInternet) }
        offline.profileCache = cache(box)
        await offline.start()
        guard case .ready = offline.phase else { Issue.record("expected cached profile"); return }
        #expect(offline.isProfileFromCache)
        #expect(offline.selectedTenant?.name == "Acme Plant Hire")
    }

    @Test func withoutCacheOfflineStaysUnavailable() async throws {
        let model = try base.makeModel { _ in throw URLError(.notConnectedToInternet) }
        await model.start()
        #expect(model.phase == .profileUnavailable)
    }

    @Test func rejectedSessionRunsSignOutHookAndIgnoresCache() async throws {
        let box = Box()
        box.saved = try AssetaJSON.decoder().decode(MeResponse.self, from: Fixtures.json(Fixtures.meJSON))
        let body = #"{"error":{"code":"FORBIDDEN","message":"No","correlation_id":"c"}}"#
        let model = try base.makeModel { _ in (403, Fixtures.json(body)) }
        model.profileCache = cache(box)
        model.onSignOut = { box.wiped += 1 }
        await model.start()
        #expect(model.phase == .profileUnavailable) // 403 is not "offline": no cached fallback
        await model.signOut()
        #expect(box.wiped == 1 && model.phase == .signedOut)
    }
}
