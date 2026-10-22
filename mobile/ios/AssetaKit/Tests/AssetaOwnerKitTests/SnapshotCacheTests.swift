@testable import AssetaOwnerKit
import AssetaModel
import AssetaSecurity
import AssetaStore
import Foundation
import Testing

struct SnapshotCacheTests {
    let tenantA = UUID(uuidString: "11111111-1111-4111-8111-111111111111")!
    let tenantB = UUID(uuidString: "22222222-2222-4222-8222-222222222222")!
    let t0 = Date(timeIntervalSince1970: 1_790_000_000)

    func makeCache(maxEntries: Int = SnapshotCache.maxEntriesPerTenant) throws -> (SnapshotCache, URL, InMemorySecretStore) {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("owner-cache-\(UUID().uuidString)", isDirectory: true)
            .appendingPathComponent(SnapshotCache.fileName)
        let secrets = InMemorySecretStore()
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        let key = try DatabaseKeyProvider(store: secrets, account: SnapshotCache.keyAccount).loadOrCreateKey()
        let cache = try SnapshotCache(database: try EncryptedDatabase(url: url, key: key), maxEntriesPerTenant: maxEntries)
        return (cache, url, secrets)
    }

    @Test func roundTripKeepsFetchTime() throws {
        let (cache, _, _) = try makeCache()
        try cache.put(["a": 1], key: .overview, tenantID: tenantA, fetchedAt: t0)
        let hit = try #require(try cache.get([String: Int].self, key: .overview, tenantID: tenantA, now: t0 + 60))
        #expect(hit.value == ["a": 1])
        #expect(abs(hit.fetchedAt.timeIntervalSince(t0)) < 0.001)
    }

    @Test func tenantsAreIsolated() throws {
        let (cache, _, _) = try makeCache()
        try cache.put("A", key: .fleetMap, tenantID: tenantA, fetchedAt: t0)
        #expect(try cache.get(String.self, key: .fleetMap, tenantID: tenantB, now: t0) == nil)
    }

    @Test func entriesOlderThanSevenDaysAreNeverReturnedAndArePurged() throws {
        let (cache, _, _) = try makeCache()
        try cache.put("old", key: .overview, tenantID: tenantA, fetchedAt: t0)
        try cache.put("new", key: .fleetMap, tenantID: tenantA, fetchedAt: t0 + 6 * 86_400)
        let later = t0 + 7 * 86_400 + 1
        #expect(try cache.get(String.self, key: .overview, tenantID: tenantA, now: later) == nil)
        #expect(try cache.get(String.self, key: .fleetMap, tenantID: tenantA, now: later)?.value == "new")
        #expect(try cache.purge(now: later) == 1)
        #expect(try cache.count(tenantID: tenantA) == 1)
    }

    @Test func fetchTimeInTheFutureIsTreatedAsExpired() throws {
        let (cache, _, _) = try makeCache()
        try cache.put("x", key: .overview, tenantID: tenantA, fetchedAt: t0 + 3600)
        #expect(try cache.get(String.self, key: .overview, tenantID: tenantA, now: t0) == nil)
    }

    @Test func eachTenantIsBoundedOldestDroppedFirst() throws {
        let (cache, _, _) = try makeCache(maxEntries: 3)
        for i in 0..<5 {
            try cache.put(i, key: SnapshotKey("k\(i)"), tenantID: tenantA, fetchedAt: t0 + Double(i))
        }
        #expect(try cache.count(tenantID: tenantA) == 3)
        #expect(try cache.get(Int.self, key: SnapshotKey("k0"), tenantID: tenantA, now: t0 + 10) == nil)
        #expect(try cache.get(Int.self, key: SnapshotKey("k4"), tenantID: tenantA, now: t0 + 10)?.value == 4)
    }

    @Test func olderResponseDoesNotOverwriteNewer() throws {
        let (cache, _, _) = try makeCache()
        try cache.put("new", key: .overview, tenantID: tenantA, fetchedAt: t0 + 10)
        try cache.put("late", key: .overview, tenantID: tenantA, fetchedAt: t0)
        #expect(try cache.get(String.self, key: .overview, tenantID: tenantA, now: t0 + 20)?.value == "new")
    }

    @Test func revokedTenantIsWipedAndRetainKeepsOnlyMemberships() throws {
        let (cache, _, _) = try makeCache()
        try cache.put("A", key: .overview, tenantID: tenantA, fetchedAt: t0)
        try cache.put("B", key: .overview, tenantID: tenantB, fetchedAt: t0)
        try cache.put("me", key: .profile, tenantID: nil, fetchedAt: t0)
        try cache.removeTenant(tenantA)
        #expect(try cache.count(tenantID: tenantA) == 0)
        try cache.retainTenants([])
        #expect(try cache.count(tenantID: tenantB) == 0)
        #expect(try cache.count(tenantID: nil) == 1) // the profile is user-level
    }

    @Test func undecodableEntryIsDroppedNotThrown() throws {
        let (cache, _, _) = try makeCache()
        try cache.put("text", key: .overview, tenantID: tenantA, fetchedAt: t0)
        #expect(try cache.get(TenantOverviewDTO.self, key: .overview, tenantID: tenantA, now: t0) == nil)
        #expect(try cache.count(tenantID: tenantA) == 0)
    }

    @Test func destroyRemovesFileAndKeySoNothingCanBeReopened() throws {
        let (cache, url, secrets) = try makeCache()
        try cache.put("secret-plant-data", key: .overview, tenantID: tenantA, fetchedAt: t0)
        let raw = try Data(contentsOf: url)
        #expect(raw.range(of: Data("secret-plant-data".utf8)) == nil) // encrypted at rest
        try SnapshotCache.destroy(at: url, secrets: secrets, closing: cache)
        #expect(!FileManager.default.fileExists(atPath: url.path))
        #expect(try secrets.data(for: SnapshotCache.keyAccount) == nil)
    }
}
