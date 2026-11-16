import AssetaModel
@testable import AssetaOwnerKit
import Foundation
import Testing

@Suite("ADR-008 Owner figures (Android Figures.kt)")
struct OwnerFiguresTests {
    static let utc = TimeZone(identifier: "UTC")!

    @Test func compactMoneyFollowsTheDesign() {
        #expect(OwnerFigures.compactMoney(5_200_000) == "5.2M")
        #expect(OwnerFigures.compactMoney(3_850_000) == "3.85M")
        #expect(OwnerFigures.compactMoney(2_000_000) == "2.0M")
        #expect(OwnerFigures.compactMoney(3_855_000) == "3.86M")
        #expect(OwnerFigures.compactMoney(1_200_000_000) == "1.2B")
        #expect(OwnerFigures.compactMoney(850_000) == "850,000")
        #expect(OwnerFigures.compactMoney(Decimal(string: "999.5")!) == "1,000")
        #expect(OwnerFigures.compactMoney(0) == "0")
        #expect(OwnerFigures.compactMoney(-2_500_000) == "-2.5M")
    }

    @Test func moneyHoursPercentAndDays() {
        #expect(OwnerFigures.money(3_800_000, currency: "TZS") == "TZS 3,800,000")
        #expect(OwnerFigures.money(Decimal(string: "3800000.50")!, currency: "TZS").contains("3,800,000.50"))
        #expect(OwnerFigures.hours(300) == "300 h")
        #expect(OwnerFigures.hours(Decimal(string: "12.50")!) == "12.5 h")
        #expect(OwnerFigures.hours(1240) == "1,240 h")
        #expect(OwnerFigures.hoursNumber(Decimal(string: "3182.875")!) == "3,182.88")
        #expect(OwnerFigures.percent(73, of: 100) == "73%")
        #expect(OwnerFigures.percent(2, of: 3) == "67%")
        #expect(OwnerFigures.percent(5, of: 0) == nil)
        #expect(OwnerFigures.days(1) == "1 day" && OwnerFigures.days(3) == "3 days")
        #expect(OwnerFigures.dec(" 12.5 ") == Decimal(string: "12.5") && OwnerFigures.dec("x") == 0 && OwnerFigures.dec(nil) == 0)
        #expect(OwnerFigures.sum(["1.5", nil, "2"]) == Decimal(string: "3.5"))
        #expect(OwnerFigures.day("2026-11-30") == "30 Nov" && OwnerFigures.day("soon") == "soon" && OwnerFigures.day(nil) == "—")
    }

    @Test func relativeTimes() throws {
        let now = try #require(ISO8601DateFormatter().date(from: "2026-11-17T10:00:00Z"))
        func at(_ text: String) throws -> Date { try #require(ISO8601DateFormatter().date(from: text)) }
        #expect(OwnerFigures.relative(try at("2026-11-17T07:40:00Z"), now: now, timeZone: Self.utc) == "today 07:40")
        #expect(OwnerFigures.relative(try at("2026-11-16T18:10:00Z"), now: now, timeZone: Self.utc) == "yesterday 18:10")
        #expect(OwnerFigures.relative(try at("2026-11-15T09:00:00Z"), now: now, timeZone: Self.utc) == "2 days ago")
        #expect(OwnerFigures.relative(try at("2026-11-11T09:00:00Z"), now: now, timeZone: Self.utc) == "6 days ago")
        #expect(OwnerFigures.relative(try at("2026-11-10T09:00:00Z"), now: now, timeZone: Self.utc) == "10 Nov")
        #expect(OwnerFigures.relative(nil, now: now) == "—")
    }

    @Test func periodsStartOnMondayAndTheFirst() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = Self.utc
        let tuesday = try #require(ISO8601DateFormatter().date(from: "2026-11-17T10:00:00Z"))
        let day = DateFormatter()
        day.timeZone = Self.utc
        day.dateFormat = "yyyy-MM-dd"
        #expect(day.string(from: OwnerFigures.Period.week.range(today: tuesday, calendar: calendar).from) == "2026-11-16")
        #expect(day.string(from: OwnerFigures.Period.month.range(today: tuesday, calendar: calendar).from) == "2026-11-01")
        #expect(day.string(from: OwnerFigures.Period.today.range(today: tuesday, calendar: calendar).from) == "2026-11-17")
        #expect(OwnerFigures.Period.allCases.map(\.label) == ["Today", "Week", "Month"])
    }

    @Test func machineReportTextsUseTheFigures() {
        #expect(MachineReportOwnerTexts.short(3_850_000) == "3.85M")
        #expect(MachineReportOwnerTexts.h(Decimal(string: "5016.75")!) == "5,016.75")
        #expect(MachineReportOwnerTexts.attentionMissing("EX-02", 1) == "EX-02 · no report for 1 day")
    }
}
