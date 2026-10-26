@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// DEC-031 Phase 5 on the Owner side: the people scorecard, unbilled work, idle machines, their dashboard tiles, gating,
/// deep links (kind JOB, console paths) and the REPEATED_PATTERN wording. Strings doc "DEC-031 Phase 5 — oversight".
struct OversightOwnerTests {
    static let staffID = UUID(uuidString: "5a000000-0000-4000-8000-000000000001")!
    static let otherStaff = UUID(uuidString: "5a000000-0000-4000-8000-000000000002")!
    static let jobID = UUID(uuidString: "70000000-0000-4000-8000-000000000001")!
    static let machineID = UUID(uuidString: "aaaaaaaa-0000-4000-8000-000000000001")!
    static let caseID = UUID(uuidString: "f6000000-0000-4000-8000-000000000009")!
    static let exceptionID = UUID(uuidString: "e0000000-0000-4000-8000-000000000001")!
    let utc = TimeZone(identifier: "UTC")!
    let en = Locale(identifier: "en_US")

    static func id(_ u: UUID) -> String { u.uuidString.lowercased() }

    static func row(_ staff: UUID = staffID, name: String? = "Juma", total: Int = 5, active: Bool = true,
                    missed: String = "1") -> String {
        """
        {"staff_member_id":"\(id(staff))","staff_member_name":\(name.map { "\"\($0)\"" } ?? "null"),"staff_kind":"SUPERVISOR",
         "employee_code":"S-01","is_active":\(active),"day_from":"2026-09-27","day_to":"2026-10-26","machines":2,
         "daily_reports_missing":2,"daily_reports_late":0,"unexplained_hours":"3.5","unexplained_items":1,"alerts":3,
         "alerts_open":1,"alerts_acknowledged":2,"avg_hours_to_acknowledge":"1.5","max_hours_to_acknowledge":"4",
         "cash_held":[{"currency":"TZS","amount":"150000","held_since":"2026-10-20T08:00:00Z","held_days":6}],
         "cash_held_too_long":1,"cash_differences":1,"cash_difference_totals":[{"currency":"TZS","count":1,"amount":"20000"}],
         "cash_differences_near_threshold":1,"revenue_differences":0,"revenue_difference_totals":[],"refused_attempts":0,
         "checkins_missed":\(missed),"checkins_made":4,"pattern_signals":0,"items_total":\(total)}
        """
    }

    static let detail = """
    {"row":\(row()),"records":[
     {"item":"MISSING_DAILY_REPORT","record_type":"engine_interval","record_id":null,"at":"2026-10-20T00:00:00Z","day":"2026-10-20",
      "machine_id":"\(id(machineID))","machine_code":"EX-01","machine_name":"Excavator","job_id":null,"job_number":null,
      "amount":null,"currency":null,"hours":null,"status":null,"near_threshold":false,"detail":{}},
     {"item":"CASH_DIFFERENCE","record_type":"cash_variance","record_id":"\(id(exceptionID))","at":"2026-10-22T09:00:00Z",
      "day":"2026-10-22","amount":"20000","currency":"TZS","status":"OPEN","near_threshold":true,"detail":{"source_type":"TRANSFER"}},
     {"item":"MISSED_CHECKIN","record_type":"site_checkin_slot","record_id":null,"at":"2026-10-24T05:00:00Z","day":"2026-10-24",
      "status":"MISSED","detail":{"scheduled_at":"2026-10-24T05:00:00+00:00","window_minutes":60}},
     {"item":"PATTERN_SIGNAL","record_type":"risk_signal","record_id":"\(id(UUID()))","at":"2026-10-25T09:00:00Z","day":"2026-10-25",
      "detail":{"case_id":"\(id(caseID))"}},
     {"item":"UNEXPLAINED_HOURS","record_type":"job_exception","record_id":"\(id(exceptionID))","at":"2026-10-21T09:00:00Z",
      "day":"2026-10-21","hours":"3.5","machine_code":"EX-01","detail":{}}]}
    """

    static let unbilled = """
    {"job_id":"\(id(jobID))","job_number":"J-2026-7","machine_id":"\(id(machineID))","machine_code":"EX-01","machine_name":"Excavator",
     "customer_id":"\(id(UUID()))","customer_name":"Mjenzi Ltd","job_site_id":null,"job_site_name":"North pit",
     "supervisor_staff_id":null,"supervisor_staff_name":null,"completed_at":"2026-10-10T15:00:00Z","days_unbilled":16,
     "billable_hours":"40","currency":"TZS","total":"4000000","draft_invoice_id":"\(id(UUID()))"}
    """

    static let idle = """
    {"machine_id":"\(id(machineID))","machine_code":"EX-01","machine_name":"Excavator","category_id":null,
     "idle_since":"2026-10-12T10:00:00Z","idle_days":14,"last_job_id":"\(id(jobID))","last_job_number":"J-2026-7",
     "last_job_completed_at":"2026-10-12T10:00:00Z","last_engine_activity_at":null,"planned_job_id":null}
    """

    static let checkin = """
    {"id":"\(id(UUID()))","client_id":"\(id(UUID()))","staff_member_id":"\(id(staffID))","recorded_by":"\(id(UUID()))",
     "captured_at":"2026-10-26T05:10:00Z","received_at":"2026-10-26T05:11:00Z","gps_status":"NO_FIX","latitude":null,
     "longitude":null,"accuracy_m":null,"job_site_id":null,"job_id":null,"distance_m":null,"source":"SYNC"}
    """

    static let mine = """
    {"required":true,"times":["08:00"],"window_minutes":60,"max_distance_m":null,"timezone":"Africa/Dar_es_Salaam",
     "day_from":"2026-10-20","day_to":"2026-10-26","slots":[{"scheduled_at":"2026-10-26T05:00:00Z","window_minutes":60,"status":"DUE"}],
     "checkins":[\(checkin)]}
    """

    static func features(_ permissions: [String], off: [String] = []) -> OwnerFeatures {
        OwnerFeatures(permissions: permissions, disabledCapabilities: off)
    }

    static let all = ["tenant.oversight.scorecard.read", "tenant.oversight.read", "tenant.job.read", "tenant.fleet.read",
                      "tenant.meter.read", "tenant.case.read", "tenant.finance.read", "tenant.cash.variance.read",
                      "tenant.accountability.read"]

    // MARK: - Contract

    @Test func samplesMatchTheContractAndDecode() throws {
        #expect(try Contract.missingRequired(schema: "ScorecardRowDto", json: Self.row()) == [])
        #expect(try Contract.missingRequired(schema: "ScorecardDetailDto", json: Self.detail).allSatisfy { $0.contains("records") })
        #expect(try Contract.missingRequired(schema: "UnbilledJobDto", json: Self.unbilled) == [])
        #expect(try Contract.missingRequired(schema: "IdleMachineDto", json: Self.idle) == [])
        #expect(try Contract.missingRequired(schema: "SiteCheckinDto", json: Self.checkin) == [])
        #expect(try Contract.missingRequired(schema: "MySiteCheckinsDto", json: Self.mine) == [])
        let d = try AssetaJSON.decoder().decode(ScorecardDetailDTO.self, from: Data(Self.detail.utf8))
        #expect(d.records.count == 5 && d.row.checkinsMissed == 1 && d.records[1].nearThreshold)
        let row = try AssetaJSON.decoder().decode(ScorecardRowDTO.self, from: Data(Self.row(missed: "null").utf8))
        #expect(row.checkinsMissed == nil)
        _ = try AssetaJSON.decoder().decode(UnbilledJobDTO.self, from: Data(Self.unbilled.utf8))
        _ = try AssetaJSON.decoder().decode(IdleMachineDTO.self, from: Data(Self.idle.utf8))
        let mine = try AssetaJSON.decoder().decode(MySiteCheckinsDTO.self, from: Data(Self.mine.utf8))
        #expect(mine.slots.first?.status == .due && mine.checkins.first?.withinDistance == nil)
    }

    @Test func requestsUseTheContractPaths() throws {
        let paths = try #require(Contract.root()["paths"] as? [String: Any])
        for path in ["/api/v1/tenant/scorecard", "/api/v1/tenant/scorecard/{staff_member_id}", "/api/v1/tenant/unbilled-work",
                     "/api/v1/tenant/idle-machines", "/api/v1/tenant/site-checkins/mine"] {
            #expect(paths[path] != nil)
        }
        let r = OwnerAPI.scorecardPerson(Self.staffID, from: "2026-10-01", to: "2026-10-26", item: "ALERT")
        #expect(r.path == "/api/v1/tenant/scorecard/\(Self.id(Self.staffID))")
        #expect(r.queryItems.contains(URLQueryItem(name: "item", value: "ALERT")))
        #expect(OwnerAPI.unbilledWork().path == "/api/v1/tenant/unbilled-work")
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
        #expect(OversightPresentation.figures(a).count == 6)
        #expect(OversightTexts.items(0) == "Nothing to look at" && OversightTexts.items(1) == "1 item to look at")
        #expect(OversightPresentation.row(c).title == "5a000000" || OversightPresentation.row(c).title.count == 8)
    }

    @Test func personFiguresInTheDocumentedOrder() throws {
        let d = try AssetaJSON.decoder().decode(ScorecardDetailDTO.self, from: Data(Self.detail.utf8))
        let rows = OversightPresentation.figureRows(d.row)
        #expect(rows.map(\.label) == ["Period", "Machines responsible for", "Daily reports missing", "Daily reports late",
                                      "Unexplained engine hours", "Alerts", "Time to acknowledge", "Cash held too long",
                                      "Cash differences", "Near the case threshold", "Revenue differences", "Refused attempts",
                                      "Site check-ins", "Repeated patterns"])
        #expect(rows[4].value == "3.5 h · 1 items" && rows[5].value == "3 · 1 open")
        #expect(rows[6].value == "average 1.5 h · longest 4 h" && rows[12].value == "4 made · 1 missed")
        #expect(rows[8].value.hasPrefix("1 · "))
        let held = OversightPresentation.cashHeldRows(d.row, timeZone: utc)
        #expect(held.first?.value == "since 20 Oct 2026 (6 days)")
        let noCheckins = try AssetaJSON.decoder().decode(ScorecardRowDTO.self, from: Data(Self.row(missed: "null").utf8))
        #expect(!OversightPresentation.figureRows(noCheckins).contains { $0.label == "Site check-ins" })
    }

    @Test func recordsOpenTheirScreenWhenAllowed() throws {
        let d = try AssetaJSON.decoder().decode(ScorecardDetailDTO.self, from: Data(Self.detail.utf8))
        let rows = OversightPresentation.records(d, features: Self.features(Self.all + ["tenant.cash.write_off.read"]), timeZone: utc)
        #expect(rows.map(\.label) == ["Repeated pattern", "Missed site check-in", "Cash difference", "Unexplained engine hours",
                                      "Daily report missing"])
        #expect(rows[0].route == .investigation(Self.caseID))
        #expect(rows[1].route == nil && rows[1].caption.contains("Scheduled 05:00") && rows[1].caption.hasPrefix("24 Oct 2026"))
        #expect(rows[2].caption.contains("Near the case threshold") && rows[2].value != nil)
        #expect(rows[3].route == .exception(Self.exceptionID) && rows[3].value == "3.5 h")
        #expect(rows[4].route == .machine(Self.machineID) && rows[4].caption == "20 Oct 2026 · EX-01 · Excavator")
        // Without the read permissions nothing opens.
        let bare = OversightPresentation.records(d, features: Self.features(["tenant.oversight.scorecard.read"]))
        #expect(bare.allSatisfy { $0.route == nil })
    }

    // MARK: - Lists and tiles

    @Test func unbilledAndIdleRows() throws {
        let u = try AssetaJSON.decoder().decode(UnbilledJobDTO.self, from: Data(Self.unbilled.utf8))
        let row = OversightPresentation.unbilled(u, timeZone: utc)
        #expect(row.title == "J-2026-7 · Mjenzi Ltd" && row.subtitle == "EX-01 · Excavator · North pit")
        #expect(row.caption == "Completed 10 Oct 2026 · 16 days unbilled · On a draft invoice" && row.trailing != nil)
        let m = try AssetaJSON.decoder().decode(IdleMachineDTO.self, from: Data(Self.idle.utf8))
        let idle = OversightPresentation.idle(m, timeZone: utc)
        #expect(idle.subtitle == "Idle since 12 Oct 2026 (14 days)" && idle.caption == "Last job J-2026-7 completed 12 Oct 2026")
    }

    @Test func tilesFollowTheSummaryAndTheSwitches() throws {
        let unbilled = try JSONValue.parse(#"{"count":2,"after_days":7,"amounts":[{"currency":"TZS","count":2,"amount":"500"}],"oldest_days":16,"items":[]}"#)
        let idle = try JSONValue.parse(#"{"count":1,"after_days":1,"longest_idle_days":null,"items":[]}"#)
        let tiles = OversightPresentation.tiles(unbilled: unbilled, idle: idle, off: [])
        #expect(tiles.map(\.id) == ["unbilled_work", "idle_machines"])
        #expect(tiles[0].rows.map(\.label) == ["Jobs", "Value", "Oldest"] && tiles[0].rows[2].value == "16 days")
        #expect(tiles[0].footer == "Completed jobs not on an issued invoice after 7 days." && tiles[0].route == .unbilledWork)
        #expect(tiles[1].rows.map(\.label) == ["Machines"] && tiles[1].footer == "Machines with no running job and no engine hours for 1 day.")
        #expect(OversightPresentation.tiles(unbilled: unbilled, idle: idle, off: [TenantCapability.unbilledWork, TenantCapability.idleMachines]).isEmpty)
        #expect(OversightPresentation.tiles(unbilled: nil, idle: .null, off: []).isEmpty)
    }

    // MARK: - Gating and links

    @Test func gatesAndFallbacks() {
        let on = Self.features(Self.all)
        #expect(on.scorecard && on.unbilledWork && on.idleMachines && on.moreEntries.contains("People scorecard"))
        #expect(on.allows(.scorecard) && on.route(.unbilledWork) == .unbilledWork)
        let off = Self.features(Self.all, off: ["SCORECARD", "UNBILLED_WORK", "IDLE_MACHINES"])
        #expect(!off.scorecard && !off.unbilledWork && !off.idleMachines && !off.moreEntries.contains("People scorecard"))
        #expect(off.route(.scorecard) == .accountability && off.route(.idleMachines) == .accountability)
        let noPermission = Self.features(["tenant.accountability.read"])
        #expect(!noPermission.allows(.unbilledWork) && noPermission.route(.unbilledWork) == .accountability)
    }

    @Test func deepLinksAndSignalWording() {
        #expect(DeepLinkParser.route(record: RecordRef(kind: .job, id: Self.jobID)) == .job(Self.jobID))
        let push = DeepLinkParser.parse(pushPayload: ["kind": "JOB", "record_id": Self.id(Self.jobID), "type": "UNBILLED_WORK"])
        #expect(push?.route == .job(Self.jobID))
        #expect(DeepLinkParser.route(path: "/tenant/scorecard") == .scorecard)
        #expect(DeepLinkParser.route(path: "/tenant/scorecard/\(Self.id(Self.staffID))")
            == .scorecardPerson(Self.staffID, name: nil, from: nil, to: nil))
        #expect(DeepLinkParser.route(path: "/tenant/unbilled-work") == .unbilledWork)
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
