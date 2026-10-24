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
    public private(set) var jobs: [FieldJob] = []
    public private(set) var overview: SyncOverview?
    public private(set) var isSyncing = false
    public private(set) var lastOutcome: SyncReport.Outcome?
    public private(set) var isOnline = true
    /// Every tab's records: server copies merged with this phone's (refreshed with the jobs).
    public private(set) var inbox = InboxSnapshot()
    /// Server notifications (fetched online, kept on the phone for offline reading).
    public private(set) var notifications: [NotificationDTO] = []
    /// The last notification refresh could not reach the server (the saved list is shown).
    public private(set) var notificationsOffline = false

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
        SupervisorPush.shared.attach(client: client, tenantID: tenant.tenantID, allowed: canReadNotifications)
        BackgroundSync.runner = { [weak self] in await self?.sync(force: false) }
        BackgroundSync.schedule()
        connectivity.start { [weak self] online in
            self?.isOnline = online
            if online { Task { await self?.sync(force: true) } }
        }
        await sync(force: true)
        await refreshNotifications()
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
        jobs = (try? services.directory.jobs()) ?? []
        overview = try? services.directory.overview()
        inbox = (try? services.inbox.snapshot()) ?? InboxSnapshot()
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

    /// Decrypted local evidence of an attachment (meter photo, signature, reset evidence), or nil.
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
        jobs = []
        overview = nil
        inbox = InboxSnapshot()
        notifications = []
        var message = "This device was revoked by your administrator. All Asseta data on it has been erased."
        if !failures.isEmpty { message += " Some files could not be removed; reinstall the app to be sure." }
        await session.endSession(explanation: message)
    }

    // MARK: - Queries for views

    func job(_ id: UUID) -> FieldJob? { services?.directory.job(id: id) ?? jobs.first { $0.id == id } }

    func progress(_ job: FieldJob) -> JobProgress {
        (try? services?.recorder.progress(jobID: job.id, serverStatus: job.job.status))
            ?? JobProgress(serverStatus: job.job.status, operations: [])
    }

    func gate(_ job: FieldJob) -> CaptureGate {
        (try? services?.directory.captureGate(machineID: job.job.machineID)) ?? .blocked(.noSnapshot)
    }

    func operations(for job: FieldJob) -> [ClientOperation] {
        (try? services?.store.outbox.operations(tenantID: tenant.tenantID, owner: services?.account.subject, jobID: job.id)) ?? []
    }

    func workLog(for job: FieldJob) -> [WorkLogLine] { (try? services?.recorder.workLog(jobID: job.id)) ?? [] }

    func runningEntry(for job: FieldJob) -> RunningWorkEntry? { try? services?.recorder.runningEntry(jobID: job.id) }

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
}
#endif
