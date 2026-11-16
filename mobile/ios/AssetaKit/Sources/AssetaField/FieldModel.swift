#if os(iOS)
import AssetaAppShell
import AssetaCapture
import AssetaModel
import AssetaStore
import AssetaSync
import Foundation
import Observation

/// UI state of the Supervisor field app for one tenant.
@MainActor
@Observable
public final class FieldModel {
    public enum Phase: Equatable { case loading, ready, failed(String) }

    public private(set) var phase: Phase = .loading
    public private(set) var overview: SyncOverview?
    public private(set) var isSyncing = false
    public private(set) var lastOutcome: SyncReport.Outcome?
    public private(set) var isOnline = true
    /// Every screen's records: server copies merged with this phone's.
    public private(set) var inbox = InboxSnapshot()
    /// Server notifications (fetched online, kept on the phone for offline reading).
    public private(set) var notifications: [NotificationDTO] = []
    /// The last notification refresh could not reach the server (the saved list is shown).
    public private(set) var notificationsOffline = false
    /// What the accountability entries need: server capabilities, permissions and the saved tenant policies.
    public private(set) var access = FieldAccess(capabilities: nil, permissions: [])
    /// Bumped whenever the saved accountability lists change (views re-read them).
    public private(set) var accountabilityTick = 0
    /// Overdue-remittance flags read online this session (shown while the screen re-reads them).
    var savedOverdue: [UUID: RemittanceOverdueDTO] = [:]

    let session: SessionModel
    let tenant: TenantMembership
    private(set) var services: FieldServices?
    private let connectivity = ConnectivityMonitor()
    private var retryTask: Task<Void, Never>?
    let locator = LocationCapturer()
    let ocr = MeterOCR()

    public init(session: SessionModel, tenant: TenantMembership) {
        self.session = session
        self.tenant = tenant
    }

    public func start() async {
        guard services == nil else { return }
        guard let secrets = session.secrets, let client = session.tenantClient else {
            phase = .failed("This build is missing its configuration.")
            return
        }
        guard let account = session.account else {
            phase = .failed("Sign in again to open your field work.")
            return
        }
        do {
            services = try FieldServices(tenantID: tenant.tenantID, account: account, launchAccount: session.launchAccount,
                                         client: client, secrets: secrets, appVersion: FieldServices.appVersion)
        } catch {
            phase = .failed("The local data store could not be opened (\(error)).")
            return
        }
        phase = .ready
        refresh()
        installAccountDeletionHooks()
        SupervisorPush.shared.attach(client: client, tenantID: tenant.tenantID, allowed: canReadNotifications)
        BackgroundSync.runner = { [weak self] in await self?.sync(force: false) }
        BackgroundSync.schedule()
        connectivity.start { [weak self] online in
            self?.isOnline = online
            if online { Task { await self?.sync(force: true) } }
        }
        await sync(force: true)
        await refreshNotifications()
        await refreshAccountability()
    }

    public func stop() {
        connectivity.stop()
        retryTask?.cancel()
        BackgroundSync.runner = nil
    }

    /// Runs one sync cycle; `force` ignores the backoff window (foreground, reconnect, user action).
    public func sync(force: Bool) async {
        guard let services, !isSyncing else { return }
        isSyncing = true
        defer { isSyncing = false }
        do {
            let report = try await services.engine.sync(force: force)
            if report.outcome != .alreadyRunning { lastOutcome = report.outcome }
        } catch SyncError.deviceRevoked {
            await deviceRevoked()
            return
        } catch {
            lastOutcome = .serverUnavailable(String(describing: error))
        }
        refresh()
        scheduleRetry()
    }

    /// While the app is open, retry automatically when the backoff window ends.
    private func scheduleRetry() {
        retryTask?.cancel()
        guard let next = overview?.nextAttemptAt, (overview?.unsyncedCount ?? 0) > 0 || lastOutcome != .synced else { return }
        retryTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(max(1, next.timeIntervalSinceNow)))
            guard !Task.isCancelled else { return }
            await self?.sync(force: false)
        }
    }

    public func refresh() {
        guard let services else { return }
        overview = try? services.directory.overview()
        inbox = (try? services.inbox.snapshot()) ?? InboxSnapshot()
        access = services.accountability.access(permissions: tenant.permissions,
                                                disabledCapabilities: tenant.disabledCapabilities)
        accountabilityTick += 1
        if notifications.isEmpty { notifications = services.online.cachedNotifications()?.items ?? [] }
    }

    /// Fetches the newest notifications (the saved list when offline).
    public func refreshNotifications() async {
        guard let services else { return }
        let result = await services.online.refreshNotifications()
        notifications = result.value ?? notifications
        if case .fresh = result { notificationsOffline = false } else { notificationsOffline = true }
    }

    func markRead(_ notification: NotificationDTO) async {
        guard let services, notification.isUnread else { return }
        await services.online.markRead([notification.id])
        notifications = services.online.cachedNotifications()?.items ?? notifications
    }

    func markAllRead() async {
        guard let services else { return }
        await services.online.markAllRead()
        notifications = services.online.cachedNotifications()?.items ?? notifications
    }

    var online: SupervisorOnline? { services?.online }
    /// Server notifications (and push for them) need `tenant.notification.read`; the server enforces it.
    var canReadNotifications: Bool { tenant.permissions.contains("tenant.notification.read") }
    var unreadNotifications: Int { notifications.filter(\.isUnread).count }

    /// Decrypted local evidence of an attachment (meter photo, receipt, reset evidence), or nil.
    func localEvidence(_ attachment: LocalAttachment) -> Data? {
        try? services?.evidence.read(attachment.fileName)
    }

    /// The local evidence files an operation carries.
    func evidenceFiles(of operation: ClientOperation) -> [LocalAttachment] {
        (try? services?.store.attachments.attachments(operationID: operation.id)) ?? []
    }

    private func deviceRevoked() async {
        stop()
        let failures = services?.wipe() ?? []
        services = nil
        overview = nil
        inbox = InboxSnapshot()
        notifications = []
        var message = "This device was revoked by your administrator. All Asseta data on it has been erased."
        if !failures.isEmpty { message += " Some files could not be removed; reinstall the app to be sure." }
        await session.endSession(explanation: message)
    }

    // MARK: - Queries for views

    var clockStatus: ClockStatus { services?.directory.clockStatus() ?? .unknown }
    var deviceID: String? { services?.deviceID }

    // MARK: - Actions

    func storeEvidence(_ data: Data, fileExtension: String, contentType: String) throws -> StoredEvidence {
        guard let services else { throw FieldRecorderError.notAllowed("Not ready") }
        return try services.evidence.store(data, fileExtension: fileExtension, contentType: contentType)
    }

    func discardEvidence(_ evidence: StoredEvidence) {
        guard let services else { return }
        try? FileManager.default.removeItem(at: services.evidence.url(for: evidence.fileName))
    }

    func perform(_ action: (FieldRecorder) throws -> Void) throws {
        guard let services else { throw FieldRecorderError.notAllowed("Not ready") }
        try action(services.recorder)
        refresh()
        Task { await sync(force: true) }
    }

    func retry(_ operation: ClientOperation) {
        try? services?.store.outbox.requeue(id: operation.id)
        refresh()
        Task { await sync(force: true) }
    }

    public func signOut() async {
        stop()
        await session.signOut()
    }

    // MARK: - Delete my account

    /// "Delete my account" warns about this account's unsynced items (as the sign-out confirmation counts them),
    /// offers a sync first, and erases the field data once the server deleted the account.
    private func installAccountDeletionHooks() {
        session.accountDeletionHooks = AccountDeletionHooks(
            unsyncedCount: { [weak self] in
                self?.refresh()
                return self?.overview?.unsyncedCount ?? 0
            },
            syncNow: { [weak self] in await self?.sync(force: true) },
            eraseLocalData: { [weak self] in self?.eraseAfterAccountDeletion() }
        )
    }

    /// The account is gone: its unsent work can never be sent. The encrypted database, evidence files and caches are
    /// erased unless another account on this phone still has unsynced work (held for them, so it must survive); then
    /// the normal sign-out runs.
    func eraseAfterAccountDeletion() {
        stop()
        guard let services else { return }
        let othersWaiting = (try? services.store.outbox.hasUnsyncedWork(excluding: services.account.subject)) ?? true
        if !othersWaiting {
            _ = services.wipe()
            URLCache.shared.removeAllCachedResponses()
            if let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first,
               let items = try? FileManager.default.contentsOfDirectory(at: caches, includingPropertiesForKeys: nil) {
                for item in items { try? FileManager.default.removeItem(at: item) }
            }
        }
        self.services = nil
        overview = nil
        inbox = InboxSnapshot()
        notifications = []
    }
}
#endif
