@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// DEC-031 Phase 5 on the Owner side: the people scorecard, idle machines, their dashboard tile, gating, deep links
/// (console paths) and the REPEATED_PATTERN wording. Unbilled work and site check-ins are gone (ADR-008). Strings doc "DEC-031 Phase 5 — oversight".
struct OversightOwnerTests {
    static let staffID = UUID(uuidString: "5a000000-0000-4000-8000-000000000001")!
    static let otherStaff = UUID(uuidString: "5a000000-0000-4000-8000-000000000002")!
    static let reportID = UUID(uuidString: "70000000-0000-4000-8000-000000000001")!
    static let machineID = UUID(uuidString: "aaaaaaaa-0000-4000-8000-000000000001")!
    static let caseID = UUID(uuidString: "f6000000-0000-4000-8000-000000000009")!
    static let exceptionID = UUID(uuidString: "e0000000-0000-4000-8000-000000000001")!
    let utc = TimeZone(identifier: "UTC")!
    let en = Locale(identifier: "en_US")

    static func id(_ u: UUID) -> String { u.uuidString.lowercased() }

    static func row(_ staff: UUID = staffID, name: String? = "Juma", total: Int = 5, active: Bool = true) -> String {
        """
        {"staff_member_id":"\(id(staff))","staff_member_name":\(name.map { "\"\($0)\"" } ?? "null"),"staff_kind":"SUPERVISOR",
         "employee_code":"S-01","is_active":\(active),"day_from":"2026-09-27","day_to":"2026-10-26","machines":2,
         "daily_reports_missing":2,"daily_reports_late":0,"unexplained_hours":"3.5","unexplained_items":1,"alerts":3,
         "alerts_open":1,"alerts_acknowledged":2,"avg_hours_to_acknowledge":"1.5","max_hours_to_acknowledge":"4",
         "cash_held":[{"currency":"TZS","amount":"150000","held_since":"2026-10-20T08:00:00Z","held_days":6}],
         "cash_held_too_long":1,"cash_differences":1,"cash_difference_totals":[{"currency":"TZS","count":1,"amount":"20000"}],
         "cash_differences_near_threshold":1,"refused_attempts":0,"pattern_signals":0,"items_total":\(total)}
        """
    }

    static let detail = """
    {"row":\(row()),"records":[
     {"item":"MISSING_DAILY_REPORT","record_type":"engine_interval","record_id":null,"at":"2026-10-20T00:00:00Z","day":"2026-10-20",
      "machine_id":"\(id(machineID))","machine_code":"EX-01","machine_name":"Excavator",
      "amount":null,"currency":null,"hours":null,"status":null,"near_threshold":false,"detail":{}},
     {"item":"CASH_DIFFERENCE","record_type":"cash_variance","record_id":"\(id(exceptionID))","at":"2026-10-22T09:00:00Z",
      "day":"2026-10-22","amount":"20000","currency":"TZS","status":"OPEN","near_threshold":true,"detail":{"source_type":"TRANSFER"}},
     {"item":"PATTERN_SIGNAL","record_type":"risk_signal","record_id":"\(id(UUID()))","at":"2026-10-25T09:00:00Z","day":"2026-10-25",
      "detail":{"case_id":"\(id(caseID))"}},
     {"item":"UNEXPLAINED_HOURS","record_type":"meter_exception","record_id":"\(id(exceptionID))","at":"2026-10-21T09:00:00Z",
      "day":"2026-10-21","hours":"3.5","machine_code":"EX-01","detail":{}}]}
    """

    static let idle = """
    {"machine_id":"\(id(machineID))","machine_code":"EX-01","machine_name":"Excavator","category_id":null,
     "idle_since":"2026-10-12T10:00:00Z","idle_days":14,"last_machine_report_id":"\(id(reportID))",
     "last_machine_report_number":"MR-2026-00007","last_engine_activity_at":null}
    """

    static func features(_ permissions: [String], off: [String] = []) -> OwnerFeatures {
        OwnerFeatures(permissions: permissions, disabledCapabilities: off)
    }

    static let all = ["tenant.oversight.scorecard.read", "tenant.oversight.read", "tenant.fleet.read",
                      "tenant.meter.read", "tenant.case.read", "tenant.finance.read", "tenant.cash.variance.read",
                      "tenant.accountability.read"]

    // MARK: - Contract

    @Test func samplesMatchTheContractAndDecode() throws {
        #expect(try Contract.missingRequired(schema: "ScorecardRowDto", json: Self.row()) == [])
        #expect(try Contract.missingRequired(schema: "ScorecardDetailDto", json: Self.detail).allSatisfy { $0.contains("records") })
        #expect(try Contract.missingRequired(schema: "IdleMachineDto", json: Self.idle) == [])
        let d = try AssetaJSON.decoder().decode(ScorecardDetailDTO.self, from: Data(Self.detail.utf8))
        #expect(d.records.count == 4 && d.records[1].nearThreshold)
        let idle = try AssetaJSON.decoder().decode(IdleMachineDTO.self, from: Data(Self.idle.utf8))
        #expect(idle.lastMachineReportNumber == "MR-2026-00007")
        for gone in ["UnbilledJobDto", "SiteCheckinDto", "MySiteCheckinsDto"] { #expect(Contract.schemas[gone] == nil) }
        let item = try #require(Contract.schemas["ScorecardItem"] as? [String: Any])
        #expect(Set(item["enum"] as? [String] ?? []) == Set(ScorecardItem.filterable.map(\.rawValue)))
    }

    @Test func requestsUseTheContractPaths() throws {
        let paths = try #require(Contract.root()["paths"] as? [String: Any])
        for path in ["/api/v1/tenant/scorecard", "/api/v1/tenant/scorecard/{staff_member_id}", "/api/v1/tenant/idle-machines"] {
            #expect(paths[path] != nil)
        }
        for path in ["/api/v1/tenant/unbilled-work", "/api/v1/tenant/site-checkins/mine", "/api/v1/tenant/site-checkins"] {
            #expect(paths[path] == nil)
        }
        let r = OwnerAPI.scorecardPerson(Self.staffID, from: "2026-10-01", to: "2026-10-26", item: "ALERT")
        #expect(r.path == "/api/v1/tenant/scorecard/\(Self.id(Self.staffID))")
        #expect(r.queryItems.contains(URLQueryItem(name: "item", value: "ALERT")))
        #expect(OwnerAPI.idleMachines().path == "/api/v1/tenant/idle-machines")
    }

    // MARK: - Scorecard

    @Test func periodsAreLocalDays() {
        let now = ISO8601DateFormatter().date(from: "2026-10-26T12:00:00Z")!
        #expect(ScorecardPeriod.last7Days.range(now: now, timeZone: utc) == ("2026-10-20", "2026-10-26"))
        #expect(ScorecardPeriod.last30Days.range(now: now, timeZone: utc) == ("2026-09-27", "2026-10-26"))
        #expect(ScorecardPeriod.thisMonth.range(now: now, timeZone: utc) == ("2026-10-01", "2026-10-26"))
        #expect(ScorecardPeriod.lastMonth.range(now: now, timeZone: utc) == ("2026-09-01", "2026-09-30"))
        #expect(ScorecardPeriod.default == .last30Days && ScorecardPeriod.allCases.map(\.label)
            == ["Last 7 days", "Last 30 days", "This month", "Last month"])
    }

    @Test func listRowsSortMostItemsFirstAndShowThreeFigures() throws {
        let decode = { (s: String) in try AssetaJSON.decoder().decode(ScorecardRowDTO.self, from: Data(s.utf8)) }
        let a = try decode(Self.row(Self.staffID, name: "Zawadi", total: 5))
        let b = try decode(Self.row(Self.otherStaff, name: "Asha", total: 5, active: false))
        let c = try decode(Self.row(UUID(), name: nil, total: 0))
        #expect(OversightPresentation.sorted([c, a, b]).map(\.staffMemberName) == ["Asha", "Zawadi", nil])
        let row = OversightPresentation.row(b)
        #expect(row.title == "Asha" && row.subtitle == "5 items to look at · Inactive")
        #expect(row.caption == "2 missing reports · 3.5 h unexplained · 1 open alerts")
        #expect(OversightPresentation.figures(a).count == 5)
        #expect(OversightTexts.items(0) == "Nothing to look at" && OversightTexts.items(1) == "1 item to look at")
        #expect(OversightPresentation.row(c).title == "5a000000" || OversightPresentation.row(c).title.count == 8)
    }

    @Test func personFiguresInTheDocumentedOrder() throws {
        let d = try AssetaJSON.decoder().decode(ScorecardDetailDTO.self, from: Data(Self.detail.utf8))
        let rows = OversightPresentation.figureRows(d.row)
        #expect(rows.map(\.label) == ["Period", "Machines responsible for", "Daily reports missing", "Daily reports late",
                                      "Unexplained engine hours", "Alerts", "Time to acknowledge", "Cash held too long",
                                      "Cash differences", "Near the case threshold", "Refused attempts", "Repeated patterns"])
        #expect(rows[4].value == "3.5 h · 1 items" && rows[5].value == "3 · 1 open")
        #expect(rows[6].value == "average 1.5 h · longest 4 h")
        #expect(rows[8].value.hasPrefix("1 · "))
        let held = OversightPresentation.cashHeldRows(d.row, timeZone: utc)
        #expect(held.first?.value == "since 20 Oct 2026 (6 days)")
    }

    @Test func recordsOpenTheirScreenWhenAllowed() throws {
        let d = try AssetaJSON.decoder().decode(ScorecardDetailDTO.self, from: Data(Self.detail.utf8))
        let rows = OversightPresentation.records(d, features: Self.features(Self.all + ["tenant.cash.write_off.read"]), timeZone: utc)
        #expect(rows.map(\.label) == ["Repeated pattern", "Cash difference", "Unexplained engine hours", "Daily report missing"])
        #expect(rows[0].route == .investigation(Self.caseID))
        #expect(rows[1].caption.contains("Near the case threshold") && rows[1].value != nil)
        #expect(rows[2].route == .exception(Self.exceptionID) && rows[2].value == "3.5 h")
        #expect(rows[3].route == .machine(Self.machineID) && rows[3].caption == "20 Oct 2026 · EX-01 · Excavator")
        // Without the read permissions nothing opens.
        let bare = OversightPresentation.records(d, features: Self.features(["tenant.oversight.scorecard.read"]))
        #expect(bare.allSatisfy { $0.route == nil })
    }

    // MARK: - Lists and tiles

    @Test func idleRows() throws {
        let m = try AssetaJSON.decoder().decode(IdleMachineDTO.self, from: Data(Self.idle.utf8))
        let idle = OversightPresentation.idle(m, timeZone: utc)
        #expect(idle.subtitle == "Idle since 12 Oct 2026 (14 days)" && idle.caption == "Last machine report MR-2026-00007")
        #expect(OversightTexts.idleFooter == "Machines with no approved machine-report hours for a while.")
        let never = try AssetaJSON.decoder().decode(IdleMachineDTO.self, from: Data(Self.idle
            .replacingOccurrences(of: #""last_machine_report_id":"\#(Self.id(Self.reportID))""#, with: #""last_machine_report_id":null"#).utf8))
        #expect(OversightPresentation.idle(never, timeZone: utc).caption == nil)
    }

    @Test func tilesFollowTheSummaryAndTheSwitches() throws {
        let idle = try JSONValue.parse(#"{"count":1,"after_days":1,"longest_idle_days":null,"items":[]}"#)
        let tiles = OversightPresentation.tiles(idle: idle, off: [])
        #expect(tiles.map(\.id) == ["idle_machines"] && tiles[0].route == .idleMachines)
        #expect(tiles[0].rows.map(\.label) == ["Machines"] && tiles[0].footer == "Machines with no approved machine-report hours for 1 day.")
        #expect(OversightPresentation.tiles(idle: idle, off: [TenantCapability.idleMachines]).isEmpty)
        #expect(OversightPresentation.tiles(idle: .null, off: []).isEmpty)
    }

    // MARK: - Gating and links

    @Test func gatesAndFallbacks() {
        let on = Self.features(Self.all)
        #expect(on.scorecard && on.idleMachines && on.moreEntries.contains("People scorecard"))
        #expect(on.allows(.scorecard) && on.route(.idleMachines) == .idleMachines)
        let off = Self.features(Self.all, off: ["SCORECARD", "IDLE_MACHINES"])
        #expect(!off.scorecard && !off.idleMachines && !off.moreEntries.contains("People scorecard"))
        #expect(off.route(.scorecard) == .accountability && off.route(.idleMachines) == .accountability)
        let noPermission = Self.features(["tenant.accountability.read"])
        #expect(!noPermission.allows(.idleMachines) && noPermission.route(.idleMachines) == .accountability)
    }

    @Test func deepLinksAndSignalWording() {
        // Jobs are gone (ADR-008): an old UNBILLED_WORK push naming a job opens nothing in particular.
        #expect(RecordKind(rawValue: "JOB") == nil)
        let push = DeepLinkParser.parse(pushPayload: ["kind": "JOB", "record_id": Self.id(Self.reportID), "type": "UNBILLED_WORK"])
        #expect(push == nil)
        #expect(DeepLinkParser.route(path: "/tenant/scorecard") == .scorecard)
        #expect(DeepLinkParser.route(path: "/tenant/scorecard/\(Self.id(Self.staffID))")
            == .scorecardPerson(Self.staffID, name: nil, from: nil, to: nil))
        #expect(DeepLinkParser.route(path: "/tenant/unbilled-work") == nil)
        #expect(DeepLinkParser.route(path: "/tenant/idle-machines") == .idleMachines)
        #expect(CaseText.signal("REPEATED_PATTERN") == "Repeated items to look at for one person")
    }

    @Test func hoursNumbersFollowThePhoneFormat() {
        #expect(OwnerFormat.hoursNumber(DecimalString(Decimal(string: "1234.5")!), locale: en) == "1,234.5")
        #expect(OwnerFormat.hoursNumber(DecimalString(Decimal(string: "12.00")!), locale: en) == "12")
        #expect(OwnerFormat.hours(DecimalString(Decimal(string: "12.3456")!), locale: en) == "12.35 h")
        #expect(OwnerFormat.hoursNumber(DecimalString(Decimal(string: "0.125")!), locale: en) == "0.12") // half-even
    }
}
