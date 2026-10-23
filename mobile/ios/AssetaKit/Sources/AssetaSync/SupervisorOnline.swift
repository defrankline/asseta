import AssetaModel
import AssetaNetwork
import AssetaStore
import Foundation

/// Result of an online read: fresh from the server, the cached copy (offline or failed), or nothing.
public enum OnlineResult<T: Sendable>: Sendable {
    case fresh(T)
    case cached(T, fetchedAt: Date)
    case unavailable(String)

    public var value: T? {
        switch self {
        case let .fresh(value), let .cached(value, _): value
        case .unavailable: nil
        }
    }
}

/// The Supervisor's optional online reads: server notifications (EXPENSE_DECIDED,
/// CASH_NOT_HANDED_OVER, JOB_MISSING_READINGS, ...) cached in the encrypted store for offline viewing
/// (cleared with the tenant's state when another user signs in), today's cash reconciliation and
/// short-lived evidence URLs. Conveniences on top of sync: the app works fully without them.
/// Same behaviour as Android `SupervisorOnline`.
public struct SupervisorOnline: Sendable {
    let client: APIClient
    let store: LocalStore
    let tenantID: UUID
    let now: @Sendable () -> Date

    static let tenant = "/api/v1/tenant"

    public init(client: APIClient, store: LocalStore, tenantID: UUID, now: @escaping @Sendable () -> Date = { Date() }) {
        self.client = client
        self.store = store
        self.tenantID = tenantID
        self.now = now
    }

    private var tenantKey: String { tenantID.uuidString.lowercased() }

    /// The notifications saved on this phone (newest first) and when they were fetched.
    public func cachedNotifications() -> (items: [NotificationDTO], fetchedAt: Date)? {
        guard let text = try? store.syncState.value(SyncKey.notifications, tenant: tenantKey),
              let cache = try? AssetaJSON.decoder().decode(NotificationCache.self, from: Data(text.utf8)) else { return nil }
        return (cache.items, cache.fetchedAt)
    }

    /// Fetches the newest notifications (falls back to the cached list when offline).
    public func refreshNotifications() async -> OnlineResult<[NotificationDTO]> {
        do {
            let page = try await client.send(APIRequest<Page<NotificationDTO>>.get(
                "\(Self.tenant)/notifications",
                query: [URLQueryItem(name: "page", value: "1"), URLQueryItem(name: "page_size", value: "50")]))
            try store(page.items)
            return .fresh(page.items)
        } catch {
            if let cached = cachedNotifications() { return .cached(cached.items, fetchedAt: cached.fetchedAt) }
            return .unavailable(error.localizedDescription)
        }
    }

    /// Marks notifications read on the server, and locally right away (kept read when offline).
    public func markRead(_ ids: [UUID]) async {
        guard !ids.isEmpty else { return }
        try? update { $0.readAt == nil && ids.contains($0.id) }
        if let request = try? APIRequest<MarkReadResultDTO>.mutation(.post, "\(Self.tenant)/notifications/read",
                                                                      body: MarkReadIn(ids: ids), idempotencyKey: UUID()) {
            _ = try? await client.send(request)
        }
    }

    public func markAllRead() async {
        try? update { $0.readAt == nil }
        if let request = try? APIRequest<MarkReadResultDTO>.mutation(.post, "\(Self.tenant)/notifications/read-all",
                                                                      body: NoBody(), idempotencyKey: UUID()) {
            _ = try? await client.send(request)
        }
    }

    /// Today's reconciliation per currency from the server (online only; nil when offline or refused).
    public func todayReconciliation(currencies: [String], timeZone: TimeZone = .current) async -> [CashReconciliationDTO]? {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        let parts = calendar.dateComponents([.year, .month, .day], from: now())
        let day = String(format: "%04d-%02d-%02d", parts.year ?? 0, parts.month ?? 0, parts.day ?? 0)
        do {
            var out: [CashReconciliationDTO] = []
            for currency in currencies.isEmpty ? [nil] : currencies.map(Optional.some) {
                var query = [URLQueryItem(name: "date", value: day)]
                if let currency { query.append(URLQueryItem(name: "currency", value: currency)) }
                out += try await client.send(APIRequest<[CashReconciliationDTO]>.get(
                    "\(Self.tenant)/cash/custody/me/reconciliation", query: query))
            }
            return out
        } catch {
            return nil
        }
    }

    /// A short-lived URL of a server attachment (meter photo, signature, reset evidence), when online and allowed.
    public func attachmentURL(_ id: UUID) async -> URL? {
        try? await client.send(APIRequest<PhotoURLDTO>.get("\(Self.tenant)/attachments/\(id.lowercased)/url")).url
    }

    /// A short-lived URL of an expense receipt, when online and allowed.
    public func receiptURL(expenseID: UUID, attachmentID: UUID) async -> URL? {
        try? await client.send(APIRequest<PhotoURLDTO>.get(
            "\(Self.tenant)/expenses/\(expenseID.lowercased)/receipts/\(attachmentID.lowercased)/url")).url
    }

    private func store(_ items: [NotificationDTO]) throws {
        let json = String(decoding: try AssetaJSON.encoder().encode(NotificationCache(items: items, fetchedAt: now())), as: UTF8.self)
        try store.syncState.setValue(json, for: SyncKey.notifications, tenant: tenantKey)
    }

    private func update(_ unread: (NotificationDTO) -> Bool) throws {
        guard let cached = cachedNotifications() else { return }
        let stamp = now()
        let items = cached.items.map { n in unread(n) ? n.markedRead(at: stamp) : n }
        let json = String(decoding: try AssetaJSON.encoder().encode(NotificationCache(items: items, fetchedAt: cached.fetchedAt)),
                          as: UTF8.self)
        try store.syncState.setValue(json, for: SyncKey.notifications, tenant: tenantKey)
    }

    struct NotificationCache: Codable {
        let items: [NotificationDTO]
        let fetchedAt: Date
        enum CodingKeys: String, CodingKey { case items, fetchedAt = "fetched_at" }
    }

    struct NoBody: Encodable {}
}

extension NotificationDTO {
    /// The same notification, read at `date` (the local copy until the server confirms).
    func markedRead(at date: Date) -> NotificationDTO {
        var object = (try? JSONValue.encode(self)) ?? .null
        if case var .object(fields) = object {
            fields["read_at"] = .string(AssetaJSON.formatInstant(date))
            object = .object(fields)
        }
        return (try? object.decode(as: NotificationDTO.self)) ?? self
    }
}
