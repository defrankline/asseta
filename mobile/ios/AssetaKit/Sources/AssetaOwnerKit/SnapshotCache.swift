import AssetaModel
import AssetaSecurity
import AssetaStore
import Foundation

/// Identifies one cached read (a screen's server response) within a tenant.
public struct SnapshotKey: Hashable, Sendable, CustomStringConvertible {
    public let rawValue: String
    public init(_ rawValue: String) { self.rawValue = rawValue }
    public var description: String { rawValue }

    public static let profile = SnapshotKey("me")
    public static let overview = SnapshotKey("overview")
    public static let fleetMap = SnapshotKey("fleet.map")
    public static let notifications = SnapshotKey("notifications")
    public static let routing = SnapshotKey("notification.routing")
    public static func machine(_ id: UUID) -> SnapshotKey { SnapshotKey("machine.\(id.lowercased)") }
    public static func machineTrack(_ id: UUID) -> SnapshotKey { SnapshotKey("machine.\(id.lowercased).track") }
    public static func machineAlerts(_ id: UUID) -> SnapshotKey { SnapshotKey("machine.\(id.lowercased).alerts") }
    public static func machineReadings(_ id: UUID) -> SnapshotKey { SnapshotKey("machine.\(id.lowercased).readings") }
    public static func machineJobs(_ id: UUID) -> SnapshotKey { SnapshotKey("machine.\(id.lowercased).jobs") }
    public static func jobs(_ status: JobStatus?) -> SnapshotKey { SnapshotKey("jobs.\(status?.rawValue ?? "ALL")") }
    public static func job(_ id: UUID) -> SnapshotKey { SnapshotKey("job.\(id.lowercased)") }
    public static func alerts(_ status: AlertStatus?) -> SnapshotKey { SnapshotKey("alerts.\(status?.rawValue ?? "ALL")") }
    public static func approvals(_ status: ApprovalStatus?) -> SnapshotKey {
        SnapshotKey("approvals.\(status?.rawValue ?? "ALL")")
    }
    public static func cases(_ status: CaseStatus?) -> SnapshotKey { SnapshotKey("cases.\(status?.rawValue ?? "ALL")") }
    public static func caseDetail(_ id: UUID) -> SnapshotKey { SnapshotKey("case.\(id.lowercased)") }
    public static func machineInfo(_ id: UUID) -> SnapshotKey { SnapshotKey("machine.\(id.lowercased).info") }
    public static func jobCaptures(_ id: UUID) -> SnapshotKey { SnapshotKey("job.\(id.lowercased).captures") }
    public static func jobAcknowledgements(_ id: UUID) -> SnapshotKey { SnapshotKey("job.\(id.lowercased).acknowledgements") }
    public static func jobActivities(_ id: UUID) -> SnapshotKey { SnapshotKey("job.\(id.lowercased).activities") }
    public static func jobExpenses(_ id: UUID) -> SnapshotKey { SnapshotKey("job.\(id.lowercased).expenses") }
    public static func jobFuel(_ id: UUID) -> SnapshotKey { SnapshotKey("job.\(id.lowercased).fuel") }
    /// Same keys as the Android Owner app: `exceptions:OPEN:ALL`, `expenses:PENDING`, `fuel:ALL`, `cash:TODAY`.
    public static func exceptions(openOnly: Bool, jobID: UUID?) -> SnapshotKey {
        SnapshotKey("exceptions:\(openOnly ? "OPEN" : "ALL"):\(jobID?.lowercased ?? "ALL")")
    }
    public static func expenses(pendingOnly: Bool) -> SnapshotKey { SnapshotKey("expenses:\(pendingOnly ? "PENDING" : "ALL")") }
    public static let fuel = SnapshotKey("fuel:ALL")
    public static func cash(_ period: CashPeriod) -> SnapshotKey { SnapshotKey("cash:\(period.rawValue)") }
    public static func meterResets(pendingOnly: Bool) -> SnapshotKey {
        SnapshotKey("meter_resets:\(pendingOnly ? "PENDING" : "ALL")")
    }
    /// The latest 200 alerts / requests of any status (detail screens look a record up here).
    public static let recentAlerts = SnapshotKey("alerts.recent")
    public static let recentApprovals = SnapshotKey("approvals.recent")
}

/// A cached value with the time it was fetched from the server.
public struct CachedSnapshot<Value: Sendable>: Sendable {
    public let value: Value
    public let fetchedAt: Date
}

/// Bounded, encrypted, **read-only** snapshot cache of the Owner app.
///
/// Server responses are stored as the server's JSON in a SQLCipher database (own file, own
/// Keychain key) so the last known state can be shown offline, clearly marked stale. Nothing in
/// it is ever edited locally or sent back. Entries older than ``maxAge`` are never returned and
/// are purged; each tenant keeps at most ``maxEntriesPerTenant`` entries (oldest dropped first).
/// Sign-out, revocation and lost tenant access wipe it.
public final class SnapshotCache: Sendable {
    public static let maxAge: TimeInterval = 7 * 24 * 3600
    public static let maxEntriesPerTenant = 300
    public static let keyAccount = "asseta.owner.cache.key.v1"
    public static let fileName = "asseta-owner-cache.sqlite"
    /// Row key for user-level entries (the `/me` profile).
    static let userScope = "user"

    public static let schema = Migrator(migrations: [
        Migration(version: 1, name: "owner_snapshot", statements: [
            """
            CREATE TABLE owner_snapshot (
                scope TEXT NOT NULL,
                key TEXT NOT NULL,
                json TEXT NOT NULL,
                fetched_at INTEGER NOT NULL,
                PRIMARY KEY (scope, key)
            )
            """,
            "CREATE INDEX owner_snapshot_fetched_at ON owner_snapshot (fetched_at)",
        ]),
    ])

    public let database: EncryptedDatabase
    private let maxAge: TimeInterval
    private let maxEntries: Int

    public init(database: EncryptedDatabase, maxAge: TimeInterval = SnapshotCache.maxAge,
                maxEntriesPerTenant: Int = SnapshotCache.maxEntriesPerTenant) throws {
        self.database = database
        self.maxAge = maxAge
        self.maxEntries = maxEntriesPerTenant
        try Self.schema.migrate(database)
    }

    /// Opens (or creates) the cache with a Keychain-held random key and purges expired entries.
    public static func open(at url: URL, secrets: any SecretStore, now: Date = Date()) throws -> SnapshotCache {
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        let key = try DatabaseKeyProvider(store: secrets, account: keyAccount).loadOrCreateKey()
        let cache = try SnapshotCache(database: try EncryptedDatabase(url: url, key: key))
        try cache.purge(now: now)
        return cache
    }

    /// Deletes the database files and the Keychain key (the cache can never be opened again).
    public static func destroy(at url: URL, secrets: any SecretStore, closing cache: SnapshotCache? = nil) throws {
        try LocalStore.destroy(at: url, keyProvider: DatabaseKeyProvider(store: secrets, account: keyAccount),
                               closing: cache?.database)
    }

    public static func defaultURL() throws -> URL { try LocalStore.defaultURL(fileName: fileName) }

    // MARK: - Read / write

    public func put(_ value: some Encodable, key: SnapshotKey, tenantID: UUID?, fetchedAt: Date) throws {
        let json = String(decoding: try AssetaJSON.encoder().encode(value), as: UTF8.self)
        let scope = Self.scope(tenantID)
        try database.transaction {
            try database.execute(
                """
                INSERT INTO owner_snapshot (scope, key, json, fetched_at) VALUES (?, ?, ?, ?)
                ON CONFLICT (scope, key) DO UPDATE SET json = excluded.json, fetched_at = excluded.fetched_at
                WHERE excluded.fetched_at >= owner_snapshot.fetched_at
                """,
                [.text(scope), .text(key.rawValue), .text(json), .integer(fetchedAt.millisecondsSince1970)]
            )
            try trim(scope: scope)
        }
    }

    /// The cached value, or `nil` when absent, expired (older than the bound) or unreadable.
    public func get<Value: Decodable & Sendable>(_ type: Value.Type, key: SnapshotKey, tenantID: UUID?,
                                                 now: Date) throws -> CachedSnapshot<Value>? {
        let rows = try database.query(
            "SELECT json, fetched_at FROM owner_snapshot WHERE scope = ? AND key = ?",
            [.text(Self.scope(tenantID)), .text(key.rawValue)]
        ) { ($0.string(0) ?? "", Date(millisecondsSince1970: $0.int(1))) }
        guard let (json, fetchedAt) = rows.first, isWithinBound(fetchedAt, now: now) else { return nil }
        guard let value = try? AssetaJSON.decoder().decode(Value.self, from: Data(json.utf8)) else {
            try remove(key: key, tenantID: tenantID) // written by an older build with another shape
            return nil
        }
        return CachedSnapshot(value: value, fetchedAt: fetchedAt)
    }

    /// Whether a snapshot fetched at `fetchedAt` may still be shown at `now`. A fetch time in the
    /// future (clock moved back) is treated as expired rather than "fresh forever".
    public func isWithinBound(_ fetchedAt: Date, now: Date) -> Bool {
        let age = now.timeIntervalSince(fetchedAt)
        return age <= maxAge && age >= -300
    }

    public func remove(key: SnapshotKey, tenantID: UUID?) throws {
        try database.execute("DELETE FROM owner_snapshot WHERE scope = ? AND key = ?",
                             [.text(Self.scope(tenantID)), .text(key.rawValue)])
    }

    /// Drops everything cached for a tenant (access lost or revoked).
    public func removeTenant(_ tenantID: UUID) throws {
        try database.execute("DELETE FROM owner_snapshot WHERE scope = ?", [.text(Self.scope(tenantID))])
    }

    /// Keeps only the given tenants (plus user-level entries); used after `/me` changes.
    public func retainTenants(_ tenantIDs: Set<UUID>) throws {
        let keep = tenantIDs.map { Self.scope($0) } + [Self.userScope]
        let placeholders = Array(repeating: "?", count: keep.count).joined(separator: ",")
        try database.execute("DELETE FROM owner_snapshot WHERE scope NOT IN (\(placeholders))", keep.map(SQLValue.text))
    }

    public func removeAll() throws {
        try database.execute("DELETE FROM owner_snapshot")
    }

    /// Deletes expired entries and trims every tenant to the entry bound. Returns rows removed.
    @discardableResult
    public func purge(now: Date) throws -> Int {
        try database.transaction {
            let oldest = now.addingTimeInterval(-maxAge).millisecondsSince1970
            let future = now.addingTimeInterval(300).millisecondsSince1970
            try database.execute("DELETE FROM owner_snapshot WHERE fetched_at < ? OR fetched_at > ?",
                                 [.integer(oldest), .integer(future)])
            var removed = database.changes
            for scope in try database.query("SELECT DISTINCT scope FROM owner_snapshot", map: { $0.string(0) ?? "" }) {
                try trim(scope: scope)
                removed += database.changes
            }
            return removed
        }
    }

    public func count(tenantID: UUID?) throws -> Int {
        Int(try database.query("SELECT count(*) FROM owner_snapshot WHERE scope = ?",
                               [.text(Self.scope(tenantID))]) { $0.int(0) }.first ?? 0)
    }

    private func trim(scope: String) throws {
        try database.execute(
            """
            DELETE FROM owner_snapshot WHERE scope = ? AND key NOT IN (
                SELECT key FROM owner_snapshot WHERE scope = ? ORDER BY fetched_at DESC, key LIMIT ?
            )
            """,
            [.text(scope), .text(scope), .integer(Int64(maxEntries))]
        )
    }

    static func scope(_ tenantID: UUID?) -> String { tenantID.map { "tenant:\($0.lowercased)" } ?? userScope }
}
