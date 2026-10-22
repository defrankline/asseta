#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import AssetaSecurity
import Foundation
import Observation
import SwiftUI
import UIKit

/// The Owner app's process-wide encrypted snapshot cache (opened lazily, destroyed on sign-out).
@MainActor
enum OwnerCacheHolder {
    private static var cache: SnapshotCache?

    static func shared(secrets: (any SecretStore)?) -> SnapshotCache? {
        if let cache { return cache }
        guard let secrets, let url = try? SnapshotCache.defaultURL() else { return nil }
        cache = try? SnapshotCache.open(at: url, secrets: secrets)
        return cache
    }

    /// Deletes the database files and their Keychain key.
    static func destroy(secrets: (any SecretStore)?) {
        guard let secrets, let url = try? SnapshotCache.defaultURL() else { return }
        try? SnapshotCache.destroy(at: url, secrets: secrets, closing: cache)
        cache = nil
    }
}

/// Wires the shared session for the Owner app: the cached `/me` for offline launches and the
/// sign-out wipe (push device deactivated best-effort, then cache database + key destroyed).
public enum OwnerApp {
    @MainActor
    public static func configure(_ session: SessionModel) {
        session.profileCache = SessionModel.ProfileCache(
            load: { [weak session] in
                let cache = OwnerCacheHolder.shared(secrets: session?.secrets)
                return (try? cache?.get(MeResponse.self, key: .profile, tenantID: nil, now: Date()))?.value
            },
            save: { [weak session] me in
                guard let cache = OwnerCacheHolder.shared(secrets: session?.secrets) else { return }
                try? cache.put(me, key: .profile, tenantID: nil, fetchedAt: Date())
                // Drop cached data of companies this user can no longer open.
                try? cache.retainTenants(Set(me.tenants.filter { $0.accessState.allowsEntry }.map(\.tenantID)))
            }
        )
        session.onSignOut = { [weak session] in
            await PushCenter.shared.unregister()
            OwnerCacheHolder.destroy(secrets: session?.secrets)
        }
    }

    /// For `AssetaAppScene(home:)`.
    public static let home: HomeBuilder = { AnyView(OwnerRootView(context: $0)) }
}

/// UI state of the Owner app for one tenant.
@MainActor
@Observable
public final class OwnerModel {
    let session: SessionModel
    let tenant: TenantMembership
    let me: MeResponse
    let features: OwnerFeatures
    let repository: OwnerRepository?

    private(set) var isOnline = true
    private(set) var unreadCount = 0
    /// Bumped (throttled) when the server reports a change; open screens reload on it.
    private(set) var changeTick = 0
    /// Bumped when a new notification arrives; the inbox reloads on it.
    private(set) var inboxTick = 0
    private(set) var accessLostMessage: String?

    private let connectivity = ConnectivityMonitor()
    private var realtime: RealtimeClient?
    private var realtimeTask: Task<Void, Never>?
    private var lastTick = Date.distantPast

    public init(session: SessionModel, me: MeResponse, tenant: TenantMembership) {
        self.session = session
        self.me = me
        self.tenant = tenant
        features = OwnerFeatures(tenant)
        let cache = OwnerCacheHolder.shared(secrets: session.secrets)
        repository = session.tenantClient.map { OwnerRepository(client: $0, cache: cache, tenantID: tenant.tenantID) }
    }

    var isReadOnlyTenant: Bool { tenant.accessState != .full }

    func start() async {
        connectivity.start { [weak self] online in
            guard let self else { return }
            self.isOnline = online
            if online { self.bump(force: true); self.startRealtime() } else { self.stopRealtime() }
        }
        startRealtime()
        await refreshUnread()
        PushCenter.shared.attach(self)
    }

    func stop() {
        connectivity.stop()
        stopRealtime()
    }

    func foreground() {
        bump(force: true)
        startRealtime()
        Task { await refreshUnread() }
    }

    func background() { stopRealtime() }

    /// Why a mutation can't be offered now (nil = allowed).
    func mutationBlock(permitted: Bool, showingCachedData: Bool) -> MutationBlock? {
        MutationGuard.check(isOnline: isOnline, showingCachedData: showingCachedData, accessState: tenant.accessState,
                            permitted: permitted)
    }

    /// Called by loaders on errors: lost tenant access sends the user back to the company picker.
    func handle(_ error: any Error) {
        guard let api = error as? APIError else { return }
        if api == .notAuthenticated {
            Task { await session.endSession(explanation: "Your session ended. Please sign in again.") }
        } else if OwnerRepository.accessLostCodes.contains(api.code) {
            accessLostMessage = "You no longer have access to \(tenant.name). Its saved data was removed from this phone."
        }
    }

    func leaveTenant() {
        stop()
        session.clearTenantSelection()
        Task { await session.loadProfile() }
    }

    func signOut() async {
        stop()
        await session.signOut()
    }

    // MARK: - Realtime and unread count

    func refreshUnread() async {
        guard features.notifications, let repository else { return }
        if let count = try? await repository.send(OwnerAPI.unreadCount()) { unreadCount = count.count }
    }

    func noteRead(remaining: Int?) {
        if let remaining { unreadCount = remaining } else { Task { await refreshUnread() } }
    }

    private func startRealtime() {
        guard realtimeTask == nil, isOnline, features.notifications,
              let base = session.configuration?.apiBaseURL else { return }
        let client = RealtimeClient(baseURL: base, tenantID: tenant.tenantID, tokens: session.accessTokens)
        realtime = client
        realtimeTask = Task { [weak self] in
            let events = await client.start()
            for await event in events {
                guard let self else { return }
                self.handle(event)
            }
        }
    }

    private func stopRealtime() {
        realtimeTask?.cancel()
        realtimeTask = nil
        let client = realtime
        realtime = nil
        Task { await client?.stop() }
    }

    private func handle(_ event: RealtimeEvent) {
        switch event {
        case let .authOK(unread, _):
            if let unread { unreadCount = unread }
            inboxTick += 1 // best-effort feed: re-read the durable inbox on every (re)connect
        case .notification:
            inboxTick += 1
        case let .unreadCount(count):
            unreadCount = count
        case .entityChanged:
            bump(force: false)
        default:
            break
        }
    }

    /// Reloads open screens, at most every 10 s for server-pushed changes (positions stream often).
    private func bump(force: Bool) {
        let now = Date()
        guard force || now.timeIntervalSince(lastTick) >= 10 else { return }
        lastTick = now
        changeTick += 1
    }

    static var appVersion: String {
        let info = Bundle.main.infoDictionary ?? [:]
        return "\(info["CFBundleShortVersionString"] as? String ?? "0") (\(info["CFBundleVersion"] as? String ?? "0"))"
    }
}
#endif
