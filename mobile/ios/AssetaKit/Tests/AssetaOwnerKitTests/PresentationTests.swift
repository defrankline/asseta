@testable import AssetaOwnerKit
import AssetaModel
import Foundation
import Testing

struct FleetPresentationTests {
    let now = AssetaJSON.parseInstant("2026-10-22T08:00:00Z")!

    func machine(_ connectivity: String, isLive: Bool = true, lastMessage: String? = "2026-10-22T07:58:00Z",
                 alerts: Int = 1) throws -> MachineMapDTO {
        try AssetaJSON.decoder().decode(MachineMapDTO.self, from: Data(Samples.machineJSON(
            connectivity: connectivity, isLive: isLive, lastMessage: lastMessage, alerts: alerts).utf8))
    }

    @Test func liveOnlyWhenServerSaysLiveAndDataIsFresh() throws {
        let style = FleetPresentation.style(for: try machine("LIVE"), dataIsCached: false, now: now)
        #expect(style.claimsLive && style.tone == .live && style.label == "Live")
        #expect(style.accessibilityLabel == "EX-01, Excavator 1. Live. 1 open alert.")
    }

    @Test func cachedLiveMachineIsNeverCalledLive() throws {
        let style = FleetPresentation.style(for: try machine("LIVE"), dataIsCached: true, now: now + 3 * 3600)
        #expect(!style.claimsLive && style.tone == .stale)
        #expect(style.label == "Last seen 3 h ago") // keeps ageing from last_message_at
    }

    @Test func liveConnectivityWithoutIsLiveFlagIsNotLive() throws {
        let style = FleetPresentation.style(for: try machine("LIVE", isLive: false), dataIsCached: false, now: now)
        #expect(!style.claimsLive && style.tone == .recent)
    }

    @Test func staleOfflineAndTrackerlessStyles() throws {
        #expect(FleetPresentation.style(for: try machine("STALE"), dataIsCached: false, now: now).tone == .stale)
        let offline = FleetPresentation.style(for: try machine("OFFLINE"), dataIsCached: false, now: now)
        #expect(offline.tone == .offline && offline.label == "Offline · last seen 2 min ago")
        let none = FleetPresentation.style(for: try machine("NO_TRACKER", lastMessage: nil, alerts: 0), dataIsCached: false,
                                           now: now)
        #expect(none.tone == .unknown && none.label == "No tracker" && !none.accessibilityLabel.contains("alert"))
    }

    @Test func listOrderPutsAlertsFirstThenRecency() throws {
        let quiet = try machine("LIVE", alerts: 0)
        let alarmed = try machine("OFFLINE", lastMessage: "2026-10-01T00:00:00Z", alerts: 2)
        #expect(FleetPresentation.sorted([quiet, alarmed]).first?.openAlerts == 2)
    }
}

struct FormatTests {
    let enUS = Locale(identifier: "en_US")
    var utc: Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC")!
        return calendar
    }

    @Test func moneyUsesDecimalAndCurrencyMinorUnits() {
        #expect(OwnerFormat.money(DecimalString(string: "1250.5000")!, currency: "USD", locale: enUS) == "$1,250.50")
        #expect(OwnerFormat.money(DecimalString(string: "0.1")!.value + DecimalString(string: "0.2")!.value,
                                  currency: "USD", locale: enUS) == "$0.30")
        #expect(OwnerFormat.money(Decimal(5), currency: "points", locale: enUS) == "5 points")
    }

    @Test func agesAndHours() {
        #expect([0, 59, 60, 3599, 3600, 86_399, 86_400, -5].map(OwnerFormat.age(seconds:))
            == ["just now", "just now", "1 min ago", "59 min ago", "1 h ago", "23 h ago", "1 d ago", "just now"])
        #expect(OwnerFormat.hours(DecimalString(string: "12.50"), locale: enUS) == "12.5 h")
        #expect(OwnerFormat.hours(nil) == "—")
        #expect(OwnerFormat.kilometres(12.44, locale: enUS) == "12.4 km")
    }

    @Test func staleBannerNamesTheSnapshotTime() {
        let fetched = AssetaJSON.parseInstant("2026-10-22T14:05:00Z")!
        let sameDay = AssetaJSON.parseInstant("2026-10-22T18:00:00Z")!
        let banner = OwnerFormat.staleBanner(fetchedAt: fetched, isOnline: false, now: sameDay, calendar: utc,
                                             locale: Locale(identifier: "en_GB"))
        #expect(banner == "Offline — data from 14:05 (stale)")
        let later = AssetaJSON.parseInstant("2026-10-30T09:00:00Z")!
        let old = OwnerFormat.staleBanner(fetchedAt: fetched, isOnline: true, now: later, calendar: utc,
                                          locale: Locale(identifier: "en_GB"))
        #expect(old.hasPrefix("Can't reach Asseta — data from 22 Oct"))
    }

    @Test func sectionFreshness() {
        let now = Date(timeIntervalSince1970: 10_000)
        #expect(OwnerFormat.sourceFreshness(nil, now: now) == "No data yet")
        #expect(OwnerFormat.sourceFreshness(now - 300, now: now) == "Latest data 5 min ago")
    }
}
