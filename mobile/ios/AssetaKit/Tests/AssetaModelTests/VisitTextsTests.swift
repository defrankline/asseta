import AssetaModel
import Foundation
import Testing

/// ADR-008 "time since last visit, and where": the same wording as Android and web.
@Suite("Machine visits: duration, Where line, maps link, place label")
struct VisitTextsTests {
    @Test func durationFormat() {
        #expect(VisitTexts.duration(seconds: nil) == "First visit")
        #expect(VisitTexts.duration(seconds: 0) == "0 min")
        #expect(VisitTexts.duration(seconds: 59) == "0 min")
        #expect(VisitTexts.duration(seconds: 45 * 60 + 59) == "45 min")
        #expect(VisitTexts.duration(seconds: 3600) == "1 h")
        #expect(VisitTexts.duration(seconds: 5 * 3600 + 20 * 60) == "5 h 20 min")
        #expect(VisitTexts.duration(seconds: 5 * 3600) == "5 h")
        #expect(VisitTexts.duration(seconds: 86399) == "23 h 59 min")
        #expect(VisitTexts.duration(seconds: 86400) == "1 day")
        #expect(VisitTexts.duration(seconds: 86400 + 3 * 3600 + 59 * 60) == "1 day 3 h")
        #expect(VisitTexts.duration(seconds: 2 * 86400 + 59 * 60) == "2 days")
        #expect(VisitTexts.sinceLastVisit(seconds: nil) == "Since last visit: First visit")
        #expect(VisitTexts.sinceLastVisit(seconds: 86400 + 3 * 3600) == "Since last visit: 1 day 3 h")
    }

    @Test func timeSinceLastVisitOnTheReportForm() {
        let utc = TimeZone(identifier: "UTC")!
        let last = Date(timeIntervalSince1970: 1_794_929_160) // 2026-11-17 15:26 UTC
        let now = last.addingTimeInterval(86400 + 3 * 3600 + 10 * 60)
        #expect(VisitTexts.dayTime(last, timeZone: utc) == "17 Nov, 15:26")
        #expect(VisitTexts.timeSinceLastVisit(last, now: now, timeZone: utc)
            == "Time since last visit: 1 day 3 h (last visit 17 Nov, 15:26)")
        #expect(VisitTexts.timeSinceLastVisit(nil, now: now) == "Time since last visit: First visit")
        let visit = VisitPoint(at: last, latitude: -6.79241, longitude: 39.20834, accuracyM: 5.4)
        #expect(VisitTexts.lastVisitLine(visit, timeZone: utc) == "Last visit: 17 Nov, 15:26 · Where: -6.7924, 39.2083 (±5 m)")
        #expect(VisitTexts.lastVisitLine(VisitPoint(at: last), timeZone: utc) == "Last visit: 17 Nov, 15:26")
        #expect(VisitTexts.lastVisitLine(nil) == nil)
    }

    @Test func whereLineLeavesOutMissingParts() {
        let full = VisitPoint(at: nil, latitude: -6.7924, longitude: 39.2083, accuracyM: 5, place: "Mbezi Beach, Kinondoni",
                              siteName: "Yard A")
        #expect(VisitTexts.whereLine(full) == "Where: Mbezi Beach, Kinondoni (at Yard A) · -6.7924, 39.2083 (±5 m)")
        #expect(VisitTexts.whereLine(VisitPoint(at: nil, latitude: -6.7924, longitude: 39.2083, accuracyM: 5, siteName: "Yard A"))
            == "Where: at Yard A · -6.7924, 39.2083 (±5 m)")
        #expect(VisitTexts.whereLine(VisitPoint(at: nil, latitude: -6.7924, longitude: 39.2083, accuracyM: 5))
            == "Where: -6.7924, 39.2083 (±5 m)")
        #expect(VisitTexts.whereLine(VisitPoint(at: nil, latitude: -6.7924, longitude: 39.2083, place: "Mbezi"))
            == "Where: Mbezi · -6.7924, 39.2083")
        #expect(VisitTexts.whereLine(VisitPoint(at: nil, place: "Mbezi", siteName: "Yard A")) == nil)
        #expect(VisitTexts.whereLine(nil) == nil)
    }

    @Test func appleMapsLink() throws {
        let url = try #require(VisitTexts.mapsURL(VisitPoint(at: nil, latitude: -6.7924, longitude: 39.2083, place: "Mbezi Beach")))
        #expect(url.absoluteString == "http://maps.apple.com/?ll=-6.7924,39.2083&q=Mbezi%20Beach")
        #expect(VisitTexts.mapsURL(VisitPoint(at: nil, latitude: -6.7924, longitude: 39.2083))?.absoluteString
            == "http://maps.apple.com/?ll=-6.7924,39.2083&q=-6.7924,39.2083")
        #expect(VisitTexts.mapsURL(VisitPoint(at: nil, place: "Mbezi")) == nil)
    }

    @Test func placeLabelIsAnAreaNeverAStreet() {
        #expect(VisitTexts.placeLabel(subLocality: "Mbezi Beach", district: "Kinondoni", locality: "Dar es Salaam")
            == "Mbezi Beach, Kinondoni, Dar es Salaam")
        #expect(VisitTexts.placeLabel(subLocality: nil, district: "Kinondoni", locality: "Dar es Salaam") == "Kinondoni, Dar es Salaam")
        #expect(VisitTexts.placeLabel(subLocality: "Kinondoni", district: "kinondoni", locality: " ") == "Kinondoni")
        #expect(VisitTexts.placeLabel(subLocality: nil, district: nil, locality: nil) == nil)
        #expect(VisitTexts.placeLabel(subLocality: String(repeating: "a", count: 300), district: nil, locality: nil)?.count == 200)
    }

    @Test func visitGapFlag() {
        #expect(MachineReportStanding.visitGapFlagged(seconds: 24 * 3600 + 1, warningHours: 24))
        #expect(!MachineReportStanding.visitGapFlagged(seconds: 24 * 3600, warningHours: 24))
        #expect(!MachineReportStanding.visitGapFlagged(seconds: 99 * 3600, warningHours: nil))
        #expect(!MachineReportStanding.visitGapFlagged(seconds: nil, warningHours: 24))
        #expect(MachineReportStanding.visitGapWarningHours(nil) == 24)
        let off = CustomerHoursPolicyValues(enabled: true, walkInAllowed: true, transferRequiresApproval: true, visitGapWarningHours: nil)
        #expect(MachineReportStanding.visitGapWarningHours(off) == nil)
    }
}
