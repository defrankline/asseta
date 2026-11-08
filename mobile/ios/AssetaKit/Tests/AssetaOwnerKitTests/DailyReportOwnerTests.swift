@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// DEC-032 Phase 1 on the Owner side: daily reports to review, work allocation corrections on the decision screen, a
/// machine day's allocations, value at risk, gating and deep links. Strings doc "DEC-032 Phase 1".
struct DailyReportOwnerTests {
    typealias T = DailyReportOwnerTexts
    static let reportID = UUID(uuidString: "a1000000-0000-4000-8000-000000000001")!
    static let groupID = UUID(uuidString: "a2000000-0000-4000-8000-000000000001")!
    static let originalID = UUID(uuidString: "a3000000-0000-4000-8000-000000000001")!
    static let machineID = UUID(uuidString: "a4000000-0000-4000-8000-000000000001")!
    static let sender = UUID(uuidString: "a5000000-0000-4000-8000-000000000001")!
    let utc = TimeZone(identifier: "UTC")!

    static func report(status: String = "SUBMITTED", late: Bool = false, duplicate: Bool = false, difference: String = "0.00",
                       supersedes: Bool = false) -> String {
        """
        {"id":"\(reportID.uuidString.lowercased())","machine_id":"\(machineID.uuidString.lowercased())","machine_code":"EX-01","machine_name":"Excavator",
         "report_date":"2026-11-07","opening_ref":"a6000000-0000-4000-8000-000000000001","closing_ref":"a6000000-0000-4000-8000-000000000002",
         "opening_reading":"100.0","closing_reading":"110.5","total_hours":"10.50","billable_hours":"8.00","unbillable_hours":"2.50",
         "difference_hours":"\(difference)","unbillable":[{"reason_id":"a7000000-0000-4000-8000-000000000001","reason_name":"Rain","hours":"2.50"}],
         "allocations":[{"allocation_id":"a8000000-0000-4000-8000-000000000001","kind":"CUSTOMER_WORK","customer_id":"a9000000-0000-4000-8000-000000000001",
         "customer_name":"Acme","job_id":null,"job_number":"J-12","activity_type":null,"start_reading":"100.0","end_reading":"108.0","hours":"8.00"},
         {"allocation_id":"a8000000-0000-4000-8000-000000000002","kind":"UNEXPLAINED","customer_id":null,"customer_name":null,"job_id":null,
         "job_number":null,"activity_type":null,"start_reading":"108.0","end_reading":"110.5","hours":"2.50"}],
         "note":"Long day","evidence_attachment_ids":["aa000000-0000-4000-8000-000000000001"],"status":"\(status)","source":"SYNC","policy_version":"v1",
         "is_duplicate":\(duplicate),"duplicate_of_id":null,"is_late":\(late),"supersedes_id":\(supersedes ? "\"\(originalID.uuidString.lowercased())\"" : "null"),
         "submitted_at":"2026-11-07T18:00:00Z","submitted_by":"\(sender.uuidString.lowercased())","submitted_by_name":"Asha",
         "client_created_at":"2026-11-07T17:59:00Z","reviewed_at":null,"reviewed_by":null,"review_note":null}
        """
    }

    static func decoded(_ json: String) throws -> DailyReportDTO { try AssetaJSON.decoder().decode(DailyReportDTO.self, from: Data(json.utf8)) }

    static func entry(id: UUID = UUID(), kind: String = "CUSTOMER_WORK", hours: String = "3.00", customer: String = #""Acme""#, job: String = #""J-12""#,
                      reason: String = "null", activity: String = "null", status: String = "PROPOSED", group: UUID? = groupID) -> String {
        """
        {"id":"\(id.uuidString.lowercased())","machine_id":"\(machineID.uuidString.lowercased())","machine_code":"EX-01","machine_name":"Excavator",
         "work_date":"2026-11-07","kind":"\(kind)","status":"\(status)","source":"CORRECTION","hours":"\(hours)",
         "start_ref":"a6000000-0000-4000-8000-000000000001","start_reading":"100.0","start_at":"2026-11-07T06:00:00Z",
         "end_ref":"a6000000-0000-4000-8000-000000000002","end_reading":"103.0","end_at":"2026-11-07T09:00:00Z",
         "customer_id":null,"customer_name":\(customer),"job_id":null,"job_number":\(job),"activity_type":\(activity),"reason_id":null,"reason_name":\(reason),
         "lots":[{"purchase_id":"ab000000-0000-4000-8000-000000000001","purchase_number":"P-9","hours":"3.00"}],"evidence_attachment_ids":[],
         "changeover_id":null,"classification_id":null,"correction_group_id":\(group.map { "\"\($0.uuidString.lowercased())\"" } ?? "null"),
         "correction_reason":"Wrong customer","supersedes_id":"\(originalID.uuidString.lowercased())","superseded_at":null,
         "recorded_by":"\(sender.uuidString.lowercased())","recorded_by_name":"Asha","decided_at":null,"decided_by":null,"decision_note":null,
         "meter_epoch":1,"policy_version":"v1","reading_review":"NONE","created_at":"2026-11-08T07:00:00Z"}
        """
    }

    static func page(_ items: [String]) throws -> Page<JSONValue> {
        try AssetaJSON.decoder().decode(Page<JSONValue>.self, from: Data(#"{"items":[\#(items.joined(separator: ","))],"total":\#(items.count),"page":1,"page_size":100}"#.utf8))
    }

    @Test func reportRowsAndFigures() throws {
        let r = try Self.decoded(Self.report(difference: "0.50"))
        #expect(AllocationPresentation.rowHeadline(r) == "EX-01 · 7 Nov 2026")
        #expect(AllocationPresentation.rowLine(r) == "10.5 h in total · 8 h billable · 2.5 h unbillable")
        let figures = Dictionary(uniqueKeysWithValues: AllocationPresentation.figures(r, timeZone: utc).map { ($0.label, $0.value) })
        #expect(figures[T.machine] == "EX-01 · Excavator" && figures[T.total] == "10.5 h" && figures[T.notAccounted] == "0.5 h")
        #expect(figures[T.submittedBy] == "Asha" && figures[T.submitted] == "7 Nov 2026, 18:00" && figures[T.note] == nil)
        #expect(AllocationPresentation.reasons(r) == [DecisionField(label: "Rain", value: "2.5 h")])
        #expect(AllocationPresentation.allocations(r) == [DecisionField(label: "Customer work", value: "8 h · Acme · J-12"),
                                                          DecisionField(label: "Unexplained", value: "2.5 h")])
        let none = try Self.decoded(Self.report())
        #expect(!AllocationPresentation.figures(none, timeZone: utc).contains { $0.label == T.notAccounted })
    }

    @Test func flagsAndStatusWords() throws {
        let r = try Self.decoded(Self.report(late: true, duplicate: true, supersedes: true))
        #expect(AllocationPresentation.flags(r) == [T.flagLate, T.flagRepeat, T.replaces])
        #expect(AllocationPresentation.flags(try Self.decoded(Self.report())).isEmpty)
        #expect(["SUBMITTED", "REVIEWED", "RETURNED", "SUPERSEDED", "OTHER_ONE"].map(T.status) == ["To review", "Reviewed", "Sent back", "Replaced", "Other one"])
    }

    @Test func theSenderNeverReviewsAndANoteIsNeeded() throws {
        let r = try Self.decoded(Self.report())
        #expect(DailyReportReview.isOwn(r, userID: Self.sender) && !DailyReportReview.isOwn(r, userID: UUID()) && !DailyReportReview.isOwn(r, userID: nil))
        #expect(!DailyReportReview.noteOK("  ok  ") && DailyReportReview.noteOK("Looks fine"))
    }

    @Test func gatingFollowsPermissionsAndEngineHours() {
        let reader = OwnerFeatures(permissions: ["tenant.meter.read"])
        #expect(reader.allocationsRead && !reader.reviewDailyReports && reader.decisionKinds.contains(.allocationCorrection))
        #expect(!reader.canDecide(.allocationCorrection) && reader.allows(.dailyReport(Self.reportID)))
        let reviewer = OwnerFeatures(permissions: ["tenant.meter.read", "tenant.meter.review", "tenant.meter.approve"])
        #expect(reviewer.reviewDailyReports && reviewer.canDecide(.allocationCorrection))
        let off = OwnerFeatures(permissions: ["tenant.meter.read", "tenant.meter.review"], disabledCapabilities: [TenantCapability.engineHours])
        #expect(!off.allocationsRead && !off.reviewDailyReports && !off.decisionKinds.contains(.allocationCorrection))
        #expect(off.route(.dailyReport(Self.reportID)) == .approvals)
        #expect(off.route(.decision(.allocationCorrection, Self.groupID)) == .approvals)
    }

    @Test func correctionsListOneRowPerGroup() throws {
        let other = UUID()
        let page = try Self.page([Self.entry(hours: "3.00"), Self.entry(kind: "UNEXPLAINED", hours: "1.25", customer: "null", job: "null"),
                                  Self.entry(hours: "2.00", group: other)])
        let rows = PendingDecision.list(page, kind: .allocationCorrection)
        #expect(rows.map(\.recordID) == [Self.groupID, other])
        #expect(rows[0].headline == "EX-01 · 7 Nov 2026 · 4.25 h" && rows[0].isPending && rows[0].reason == "Wrong customer")
        #expect(rows[0].proposedBy == Self.sender && rows[0].isOwn(userID: Self.sender))
    }

    @Test func aCorrectionShowsItsParts() throws {
        let json = """
        {"group_id":"\(Self.groupID.uuidString.lowercased())","status":"PROPOSED","supersedes_id":"\(Self.originalID.uuidString.lowercased())",
         "entries":[\(Self.entry()),\(Self.entry(kind: "AUTHORIZED_ACTIVITY", hours: "1.00", customer: "null", job: "null", activity: #""MOBILIZATION""#)),
         \(Self.entry(kind: "UNEXPLAINED", hours: "0.50", customer: "null", job: "null"))]}
        """
        let value = try JSONValue.parse(json)
        let item = try #require(PendingDecision.from(value, kind: .allocationCorrection, timeZone: utc))
        #expect(item.recordID == Self.groupID && item.status == "PROPOSED" && item.machineID == Self.machineID)
        let parts = item.fields.filter { $0.label.hasPrefix("Proposed: ") }
        #expect(parts == [DecisionField(label: "Proposed: Customer work", value: "3 h · Acme · J-12"),
                          DecisionField(label: "Proposed: Authorized activity", value: "1 h · Mobilization"),
                          DecisionField(label: "Proposed: Unexplained", value: "0.5 h")])
        #expect(item.reasonLine == "Wrong customer")
    }

    @Test func correctionRequestsUseTheGroupPaths() throws {
        let list = OwnerAPI.decisions(.allocationCorrection, pendingOnly: true)
        #expect(list.path == "/api/v1/tenant/work-allocations" && list.queryItems.contains(URLQueryItem(name: "status", value: "PROPOSED")))
        let id = Self.groupID.uuidString.lowercased()
        #expect(OwnerAPI.decision(.allocationCorrection, id: Self.groupID).path == "/api/v1/tenant/work-allocations/corrections/\(id)")
        #expect(try OwnerAPI.decide(.allocationCorrection, id: Self.groupID, approve: true, note: "Agreed", idempotencyKey: UUID()).path
            == "/api/v1/tenant/work-allocations/corrections/\(id)/decision")
        #expect(DecisionKind.allocationCorrection.usesMeterDecision)
        #expect(!DecisionRules.canDecide(.allocationCorrection, approve: true, note: "ok"))
    }

    @Test func refusalsAreInPlainWords() {
        func api(_ code: String) -> APIError {
            .server(status: 409, body: ErrorBody(code: code, message: "x", correlationID: "c"))
        }
        #expect(DecisionRules.message(for: api("ALLOCATION_NOT_ACTIVE")) == T.errNotActive)
        #expect(DecisionRules.message(for: api("ALLOCATION_CORRECTION_PENDING")) == T.errPending)
        #expect(DecisionRules.needsReload(api("ALLOCATION_NOT_ACTIVE")))
        #expect(DailyReportReview.message(for: api("REPORT_ALREADY_REVIEWED")) == T.errAlreadyReviewed)
        #expect(DailyReportReview.message(for: api("SEGREGATION_OF_DUTIES")) == T.own)
        #expect(DailyReportReview.needsReload(api("REPORT_ALREADY_REVIEWED")))
    }

    @Test func allocationEntriesAndDay() throws {
        let a = try AssetaJSON.decoder().decode(WorkAllocationDTO.self, from: Data(Self.entry().utf8))
        #expect(AllocationPresentation.entryLine(a) == "100 → 103 · 3 h" && AllocationPresentation.lots(a) == ["From P-9: 3 h"])
        #expect(AllocationPresentation.who(a) == "Acme · J-12")
        let authorized = try AssetaJSON.decoder().decode(WorkAllocationDTO.self, from: Data(
            Self.entry(kind: "AUTHORIZED_ACTIVITY", customer: "null", job: "null", reason: #""Road repair""#, activity: #""WORK""#).utf8))
        #expect(AllocationPresentation.who(authorized) == "Road repair")
        let day = try AssetaJSON.decoder().decode(AllocationDayDTO.self, from: Data("""
        {"machine_id":"\(Self.machineID.uuidString.lowercased())","day":"2026-11-07","total_engine_hours":"10.00","customer_hours":"6.00","authorized_hours":"3.00",
         "unexplained_hours":"1.00","allocated_hours":"10.00","difference_hours":"0.00","reconciled":true}
        """.utf8))
        #expect(AllocationPresentation.dayFields(day).map(\.label) == [T.dayTotal, T.dayCustomer, T.dayAuthorized, T.dayUnexplained, T.dayAllocated, T.dayDifference])
        #expect(AllocationPresentation.dayFields(day)[0].value == "10 h" && day.reconciled)
    }

    @Test func valueAtRiskIsItsOwnRowPerCurrency() throws {
        let tile = try JSONValue.parse(#"{"value_at_risk":[{"currency":"TZS","amount":"50000"},{"currency":"USD","amount":"20"}]}"#)
        let rows = AllocationPresentation.valueAtRiskRows(tile)
        #expect(rows.map(\.label) == ["Value at risk", "Value at risk"] && rows.count == 2)
        #expect(AllocationPresentation.valueAtRiskRows(try JSONValue.parse(#"{"value_at_risk":[]}"#)).isEmpty)
        #expect(AllocationPresentation.valueAtRiskRows(nil).isEmpty)
    }

    @Test func deepLinks() throws {
        let report = Self.reportID, group = Self.groupID
        #expect(DeepLinkParser.route(record: RecordRef(kind: .dailyReport, id: report)) == .dailyReport(report))
        #expect(DeepLinkParser.route(record: RecordRef(kind: .workAllocationCorrection, id: group)) == .decision(.allocationCorrection, group))
        #expect(DeepLinkParser.route(entity: "daily_report", id: report.uuidString, path: nil) == .dailyReport(report))
        #expect(DeepLinkParser.route(entity: "work_allocation_correction", id: group.uuidString, path: nil) == .decision(.allocationCorrection, group))
        #expect(DeepLinkParser.route(path: "/tenant/daily-reports/\(report.uuidString)") == .dailyReport(report))
        #expect(DeepLinkParser.route(path: "/tenant/daily-reports") == .approvals)
        #expect(DeepLinkParser.route(path: "/tenant/work-allocations/corrections/\(group.uuidString)") == .decision(.allocationCorrection, group))
        #expect(DeepLinkParser.route(path: "/tenant/work-allocations") == .approvals)
        #expect(OwnerRoute.dailyReport(report).identifiesRecord)
    }

    @Test func machineDaysOpenWithMeterReadWhenRevenueChecksAreOff() throws {
        let m = Self.machineID, day = OwnerRoute.dailySheetDay(m, "2026-11-07")
        let meterOnly = OwnerFeatures(permissions: ["tenant.meter.read", "tenant.fleet.read"],
                                      disabledCapabilities: [TenantCapability.revenueReconciliation])
        #expect(!meterOnly.revenueRead && meterOnly.machineDays)
        #expect(meterOnly.allows(.dailySheet(m)) && meterOnly.allows(day) && meterOnly.route(day) == day)
        let off = OwnerFeatures(permissions: ["tenant.meter.read", "tenant.fleet.read"],
                                disabledCapabilities: [TenantCapability.revenueReconciliation, TenantCapability.engineHours])
        #expect(!off.machineDays && !off.allows(day) && off.route(day) == .machine(m))
        #expect(!OwnerFeatures(permissions: ["tenant.fleet.read"]).machineDays)
        let request = OwnerAPI.allocationDays(machineID: m, from: "2026-10-25", to: "2026-11-07")
        #expect(request.path == "/api/v1/tenant/work-allocations/reconciliation")
        #expect(request.queryItems.contains(URLQueryItem(name: "from", value: "2026-10-25")))
        let d = try AssetaJSON.decoder().decode(AllocationDayDTO.self, from: Data("""
        {"machine_id":"\(m.uuidString.lowercased())","day":"2026-11-07","total_engine_hours":"10.00","customer_hours":"6.00","authorized_hours":"2.50",
         "unexplained_hours":"1.50","allocated_hours":"10.00","difference_hours":"0.00","reconciled":true}
        """.utf8))
        #expect(AllocationPresentation.dayLine(d) == "10 h engine · 10 h allocated" && AllocationPresentation.dayUnexplained(d) == "1.5 h unexplained")
    }
}
