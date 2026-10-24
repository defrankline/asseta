import AssetaModel
import AssetaNetwork
import AssetaSecurity
import AssetaStore
@testable import AssetaSync
import AssetaTestSupport
import Foundation
import Testing

/// Offline "Today" in the Money tab, identical to Android `CashTodayTest`.
struct CashTodayTests {
    static let utc = TimeZone(identifier: "UTC")!
    // 2026-10-24 09:05:00 UTC
    let fetchedAt = Date(timeIntervalSince1970: 1_792_832_700)

    static func rowsJSON(currency: String = "TZS", day: String = "2026-10-24", outstanding: String = "150000.00") -> String {
        """
        [{"staff_member_id":"aaaaaaaa-0000-4000-8000-0000000000aa","currency":"\(currency)","timezone":"UTC",
          "days":[{"day":"\(day)","opening":"100000.00","floats_issued":"0.00","collections":"50000.00",
                   "approved_spending":"0.00","verified_handovers":"0.00","outstanding":"\(outstanding)",
                   "claimed_unverified_handovers":"0.00","pending_spending":"0.00","unverified_collections":"0.00",
                   "outstanding_if_claims_verified":"\(outstanding)"}]}]
        """
    }

    static func rows(currency: String = "TZS", day: String = "2026-10-24", outstanding: String = "150000.00") throws
        -> [CashReconciliationDTO] {
        try AssetaJSON.decoder().decode([CashReconciliationDTO].self,
                                        from: Data(rowsJSON(currency: currency, day: day, outstanding: outstanding).utf8))
    }

    @Test func liveFiguresWinWheneverTheFetchSucceeded() throws {
        let day = try #require(Self.rows().first?.days.last)
        let snapshot = CashTodaySnapshot(rows: try Self.rows(), fetchedAt: fetchedAt, day: "2026-10-24")
        let live = CashToday.select(live: ["TZS": day], snapshot: snapshot, currency: "TZS", today: "2026-10-24")
        #expect(live == .live(day) && live.header() == "Today" && live.footer == InboxTexts.reconciliationFooter)
        // Online but no row for this currency: the estimate, as before (the snapshot is for offline only).
        #expect(CashToday.select(live: [:], snapshot: snapshot, currency: "TZS", today: "2026-10-24") == .estimate)
    }

    @Test func offlineSameDaySnapshotShowsFullFiguresAsOfFetchTime() throws {
        let day = try #require(Self.rows().first?.days.last)
        let snapshot = CashTodaySnapshot(rows: try Self.rows(), fetchedAt: fetchedAt, day: "2026-10-24")
        let state = CashToday.select(live: nil, snapshot: snapshot, currency: "TZS", today: "2026-10-24")
        #expect(state == .savedToday(day, asOf: fetchedAt))
        #expect(state.header(timeZone: Self.utc) == "Today (as of 09:05)")
        #expect(state.footer == "Office figures from the last time this phone was online. Not updated while offline.")
        #expect(CashToday.unsyncedHeader == "Recorded on this phone, not yet synced")
    }

    @Test func offlineEarlierSnapshotShowsLastOfficeFigures() throws {
        let snapshot = CashTodaySnapshot(rows: try Self.rows(day: "2026-10-22", outstanding: "90000.00"), fetchedAt: fetchedAt,
                                         day: "2026-10-22")
        let state = CashToday.select(live: nil, snapshot: snapshot, currency: "TZS", today: "2026-10-24")
        guard case let .savedEarlier(day, date) = state else { Issue.record("\(state)"); return }
        #expect(day.outstanding == "90000.00" && date == "2026-10-22")
        #expect(state.header() == "Last office figures (22 Oct 2026)")
        #expect(state.footer == InboxTexts.estimateFooter)
    }

    @Test func noSnapshotOrOtherCurrencyKeepsTheEstimate() throws {
        let snapshot = CashTodaySnapshot(rows: try Self.rows(currency: "USD"), fetchedAt: fetchedAt, day: "2026-10-24")
        let none = CashToday.select(live: nil, snapshot: nil, currency: "TZS", today: "2026-10-24")
        #expect(none == .estimate && none.header() == "Today (estimate)" && none.footer == InboxTexts.estimateFooter)
        #expect(CashToday.select(live: nil, snapshot: snapshot, currency: "TZS", today: "2026-10-24") == .estimate)
    }

    @Test func localDayAndUnsyncedCash() {
        #expect(CashToday.localDay(fetchedAt, timeZone: Self.utc) == "2026-10-24")
        #expect(CashToday.localDay(fetchedAt, timeZone: TimeZone(secondsFromGMT: -10 * 3600)!) == "2026-10-23")
        #expect(!CashLine(currency: "TZS", synced: nil).hasUnsyncedCash)
        #expect(CashLine(currency: "TZS", synced: nil, pendingHandovers: 5).hasUnsyncedCash)
    }

    @Test func everyFetchIsSavedAndReadBackOffline() async throws {
        let store = try LocalStore.open(at: try temporaryDirectory().appendingPathComponent("c.sqlite"),
                                        keyProvider: DatabaseKeyProvider(store: InMemorySecretStore()))
        let json = Self.rowsJSON()
        let transport = MockTransport { _ in (200, Data(json.utf8)) }
        let client = APIClient(baseURL: URL(string: "https://api.test")!, transport: transport,
                               tokens: StaticTokenProvider(token: "t"), tenantID: SyncFixtures.tenant)
        let stamp = fetchedAt
        let online = SupervisorOnline(client: client, store: store, tenantID: SyncFixtures.tenant, now: { stamp })
        #expect(online.cachedCashToday() == nil)
        let rows = await online.todayReconciliation(currencies: ["TZS"], timeZone: Self.utc)
        #expect(rows?.count == 1)
        let saved = try #require(online.cachedCashToday())
        #expect(saved.day == "2026-10-24" && saved.fetchedAt == stamp && saved.day(currency: "TZS")?.outstanding == "150000.00")

        // Offline: the fetch fails and the saved figures stay.
        transport.setHandler { _ in throw URLError(.notConnectedToInternet) }
        #expect(await online.todayReconciliation(currencies: ["TZS"], timeZone: Self.utc) == nil)
        #expect(online.cachedCashToday() == saved)

        // Another user signing in on this phone clears it with the rest of the tenant's state.
        try store.syncState.claim(tenantID: SyncFixtures.tenant, owner: "someone-else")
        #expect(online.cachedCashToday() == nil)
    }
}
