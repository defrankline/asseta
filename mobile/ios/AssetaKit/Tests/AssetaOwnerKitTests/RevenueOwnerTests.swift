@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// DEC-031 Phase 1 on the Owner side: revenue differences (Approvals rows, figures, explain / decide rules), non-revenue
/// hours decisions, the dashboard tile, the daily machine sheet, gating and deep links. Strings doc "DEC-031 Phase 1".
struct RevenueOwnerTests {
    static let differenceID = UUID(uuidString: "f1000000-0000-4000-8000-000000000001")!
    static let machineID = UUID(uuidString: "aaaaaaaa-0000-4000-8000-000000000001")!
    static let explainer = UUID(uuidString: "c0000000-0000-4000-8000-000000000001")!
    static let approvalID = UUID(uuidString: "f2000000-0000-4000-8000-000000000001")!
    let utc = TimeZone(identifier: "UTC")!

    static func difference(status: String = "OPEN", inProgress: String = "0", adjusted: String? = nil,
                           explained: Bool = false, caseNumber: Bool = false, unexplained: String = "0") -> String {
        let explainedBy = explained ? "\"\(explainer.uuidString.lowercased())\"" : "null"
        return """
        {"id":"\(differenceID.uuidString.lowercased())","machine_id":"\(machineID.uuidString.lowercased())","machine_code":"EX-01",
         "machine_name":"Excavator","job_id":null,"job_number":null,"period_kind":"WEEK","period_key":"WEEK:2026-W43",
         "period_start":"2026-10-19T00:00:00Z","period_end":"2026-10-26T00:00:00Z","local_from":"2026-10-19","local_to":"2026-10-25",
         "currency":"TZS","customer_work_hours":"20.00","non_revenue_hours":"1.50","unexplained_hours":"\(unexplained)",
         "expected_amount":"1000000","unexplained_expected_amount":"\(unexplained == "0" ? "0" : "50000")",
         "attributed_amount":"800000","in_progress_amount":"\(inProgress)","difference":"200000",
         "adjusted_difference":\(adjusted.map { "\"\($0)\"" } ?? "null"),
         "adjustments":\(adjusted == nil ? "[]" : #"[{"id":"f3000000-0000-4000-8000-000000000001","amount":"-50000","cause_id":"f4000000-0000-4000-8000-000000000001","cause_type":"NON_REVENUE_APPROVAL","created_at":"2026-10-26T10:00:00Z","created_by":null,"created_by_name":null,"previous_difference":"200000","new_difference":"150000"}]"#),
         "status":"\(status)","reason_id":\(explained ? "\"f5000000-0000-4000-8000-000000000001\"" : "null"),
         "reason_name":\(explained ? "\"Customer paid late\"" : "null"),"explanation_note":\(explained ? "\"Paid next week\"" : "null"),
         "explained_by":\(explainedBy),"explained_by_name":\(explained ? "\"Asha\"" : "null"),
         "explained_at":\(explained ? "\"2026-10-26T08:00:00Z\"" : "null"),"decided_by":null,"decided_at":null,"decision_note":null,
         "case_id":\(caseNumber ? "\"f6000000-0000-4000-8000-000000000001\"" : "null"),"case_number":\(caseNumber ? "\"CASE-7\"" : "null"),
         "opened_at":"2026-10-26T01:00:00Z","computed_at":"2026-10-26T01:00:00Z","policy_version":"r1",
         "detail":{"jobs":[{"job_id":"bbbbbbbb-0000-4000-8000-000000000001","job_number":"J-12","currency":"TZS","expected":"1000000.0000",
         "in_progress":"0.0000","attributed":"800000.0000","completed":true},{"job_id":"bbbbbbbb-0000-4000-8000-000000000002",
         "job_number":"J-13","currency":"USD","expected":"10","in_progress":"0","attributed":"0","completed":true}],"money_sources":[]}}
        """
    }

    static func decode(_ json: String) throws -> RevenueDifferenceDTO {
        try AssetaJSON.decoder().decode(RevenueDifferenceDTO.self, from: Data(json.utf8))
    }

    func money(_ amount: Decimal) -> String { OwnerFormat.money(amount, currency: "TZS") }

    @Test func differenceDecodesAgainstTheContract() throws {
        let json = Self.difference(adjusted: "150000", explained: true, caseNumber: true)
        #expect(try Contract.missingRequired(schema: "RevenueDifferenceDto", json: json) == [])
        let d = try Self.decode(json)
        #expect(d.adjustments.count == 1 && d.detailJobs.map(\.jobNumber) == ["J-12"])
        #expect(d.isPending)
    }

    @Test func approvalsRowAndFiguresFollowTheStringsDoc() throws {
        let d = try Self.decode(Self.difference())
        let row = RevenuePresentation.row(d, timeZone: utc)
        #expect(row.headline == "\(money(200_000)) to explain · EX-01")
        #expect(row.subtitle == "19 Oct 2026 – 25 Oct 2026 · To explain")
        #expect(row.footnote == nil)
        // Once explained: "Proposed {time} by {explainer}"; the headline shows the adjusted difference when present.
        let explainedRow = RevenuePresentation.row(try Self.decode(Self.difference(status: "EXPLANATION_PROPOSED", adjusted: "150000",
                                                                                   explained: true)), timeZone: utc)
        #expect(explainedRow.headline == "\(money(150_000)) to explain · EX-01")
        #expect(explainedRow.subtitle == "19 Oct 2026 – 25 Oct 2026 · Explanation waiting for a decision")
        #expect(explainedRow.footnote == "Proposed 26 Oct 2026, 08:00 by Asha")
        #expect(RevenuePresentation.statusTone("CONFIRMED") == .critical && RevenuePresentation.statusTone("CLEARED") == .live)
        // Zero-only rows (in progress, unexplained, adjusted, investigation) are left out; the status pill follows.
        #expect(RevenuePresentation.figures(d).map(\.label) == [
            "Machine", "Period", "Expected revenue", "Money attributed", "Difference", "Customer-work hours",
            "Non-revenue hours",
        ])
        let full = try Self.decode(Self.difference(inProgress: "1000", adjusted: "150000", caseNumber: true, unexplained: "2.00"))
        #expect(RevenuePresentation.figures(full).map(\.label) == [
            "Machine", "Period", "Expected revenue", "Work still in progress", "Money attributed", "Difference",
            "Difference after adjustments", "Customer-work hours", "Non-revenue hours", "Unexplained hours",
            "Unexplained hours expected as revenue", "Investigation",
        ])
        #expect(RevenuePresentation.figures(full).last?.value == "CASE-7")
        #expect(RevenuePresentation.jobs(d) == [DecisionField(
            label: "J-12", value: "Expected \(money(1_000_000)) · Attributed \(money(800_000))")])
        #expect(RevenuePresentation.adjustments(full, timeZone: utc) == ["26 Oct 2026: \(money(200_000)) → \(money(150_000))"])
        #expect(RevenuePresentation.explanation(d).isEmpty)
        let explained = try Self.decode(Self.difference(status: "EXPLANATION_PROPOSED", explained: true))
        #expect(RevenuePresentation.explanation(explained, timeZone: utc).map(\.value) == [
            "Customer paid late", "Paid next week", "Asha", "26 Oct 2026, 08:00",
        ])
        #expect(RevenuePresentation.period(from: "2026-10-26", to: "2026-10-26") == "26 Oct 2026")
    }

    @Test func explainAndDecideRules() throws {
        let all = [RevenuePermission.read, RevenuePermission.explain, RevenuePermission.decide]
        let open = try Self.decode(Self.difference())
        #expect(RevenueRules.canExplain(open, permissions: all))
        #expect(!RevenueRules.canExplain(open, permissions: [RevenuePermission.read, RevenuePermission.decide]))
        #expect(RevenueRules.decisions(open, permissions: all) == [.confirm])
        let proposed = try Self.decode(Self.difference(status: "EXPLANATION_PROPOSED", explained: true))
        #expect(!RevenueRules.canExplain(proposed, permissions: all))
        #expect(RevenueRules.decisions(proposed, permissions: all) == [.approve, .reject, .confirm])
        #expect(RevenueRules.decisions(proposed, permissions: [RevenuePermission.read, RevenuePermission.explain]).isEmpty)
        #expect(RevenueRules.decisions(try Self.decode(Self.difference(status: "EXPLAINED")), permissions: all).isEmpty)
        #expect(RevenueRules.isOwnExplanation(proposed, userID: Self.explainer))
        #expect(!RevenueRules.isOwnExplanation(proposed, userID: UUID()))
        #expect(RevenueRules.listsOpen(permissions: [RevenuePermission.read, RevenuePermission.explain]))
        #expect(!RevenueRules.listsOpen(permissions: [RevenuePermission.read]))
        #expect(!RevenueRules.noteOK("ok  ") && RevenueRules.noteOK("Paid late"))
        #expect(RevenueTexts.status("CLEARED") == "Cleared (money arrived)")
        #expect(RevenueTexts.status("NEW_STATE") == "New state")
        let reasons = [RevenueReasonDTO(id: UUID(), code: "B", name: "beta"), RevenueReasonDTO(id: UUID(), code: "A", name: "Alpha"),
                       RevenueReasonDTO(id: UUID(), code: "X", name: "Old", isActive: false)]
        #expect(RevenueRules.pickable(reasons).map(\.name) == ["Alpha", "beta"])
    }

    @Test func requestsHitTheContractPaths() throws {
        let explain = try OwnerAPI.explainRevenueDifference(Self.differenceID, reasonID: Self.explainer, note: " Paid late ",
                                                            idempotencyKey: UUID())
        #expect(explain.path == "/api/v1/tenant/revenue-differences/\(Self.differenceID.uuidString.lowercased())/explanation")
        let body = try JSONValue.parse(String(decoding: try #require(explain.body), as: UTF8.self))
        #expect(body["note"]?.stringValue == "Paid late" && body["reason_id"]?.stringValue.flatMap(UUID.init(uuidString:)) == Self.explainer)
        let decide = try OwnerAPI.decideRevenueDifference(Self.differenceID, decision: .confirm, note: "Recover it", idempotencyKey: UUID())
        #expect(decide.path.hasSuffix("/decision"))
        #expect(try JSONValue.parse(String(decoding: try #require(decide.body), as: UTF8.self))["decision"]?.stringValue == "CONFIRM")
        let list = OwnerAPI.revenueDifferences(status: "OPEN")
        #expect(list.path == "/api/v1/tenant/revenue-differences" && list.queryItems.contains(URLQueryItem(name: "status", value: "OPEN")))
        let sheet = OwnerAPI.dailySheet(machineID: Self.machineID, dayFrom: "2026-10-13", dayTo: "2026-10-26")
        #expect(sheet.queryItems.contains(URLQueryItem(name: "day_from", value: "2026-10-13")))
        #expect(OwnerAPI.dailySheetDay(machineID: Self.machineID, day: "2026-10-26").path
            == "/api/v1/tenant/daily-machine-sheet/\(Self.machineID.uuidString.lowercased())/2026-10-26")
        // Non-revenue decisions: the generic decision with a required note.
        let nonRevenue = try OwnerAPI.decide(.nonRevenue, id: Self.approvalID, approve: false, note: "Not movement", idempotencyKey: UUID())
        #expect(nonRevenue.path == "/api/v1/tenant/non-revenue-approvals/\(Self.approvalID.uuidString.lowercased())/decision")
        #expect(try JSONValue.parse(String(decoding: try #require(nonRevenue.body), as: UTF8.self))["decision"]?.stringValue == "REJECT")
        #expect(!DecisionRules.canDecide(.nonRevenue, approve: true, note: "ok"))
    }

    static let nonRevenueApproval = """
    {"id":"\(approvalID.uuidString.lowercased())","activity_id":"f7000000-0000-4000-8000-000000000001","activity_type":"MOBILIZATION",
     "job_id":"bbbbbbbb-0000-4000-8000-000000000001","job_number":"J-12","machine_id":"\(machineID.uuidString.lowercased())",
     "machine_code":"EX-01","machine_name":"Excavator","started_at":"2026-10-26T06:00:00Z","ended_at":"2026-10-26T07:30:00Z",
     "hours":"1.50","reason_id":"f5000000-0000-4000-8000-000000000001","reason_name":"Move to site","note":"Moved to site B",
     "status":"PROPOSED","proposed_by":"\(explainer.uuidString.lowercased())","proposed_by_name":"Asha",
     "proposed_at":"2026-10-26T08:00:00Z","decided_by":null,"decided_by_name":null,"decided_at":null,"decision_note":null,
     "policy_version":"r1"}
    """

    @Test func nonRevenueDecisionFields() throws {
        #expect(try Contract.missingRequired(schema: "NonRevenueApprovalDto", json: Self.nonRevenueApproval) == [])
        let item = try #require(PendingDecision.from(try JSONValue.parse(Self.nonRevenueApproval), kind: .nonRevenue, timeZone: utc))
        #expect(item.headline == "1.5 h Mobilization · EX-01")
        #expect(item.reason == "Move to site" && item.proposedByName == "Asha")
        #expect(item.isPending && item.isOwn(userID: Self.explainer))
        #expect(item.fields.map(\.label) == ["Machine", "Job", "Type", "Time", "Hours", "Reason", "Note", "Proposed by"])
        #expect(item.fields[3].value == "26 Oct 2026, 06:00 – 26 Oct 2026, 07:30")
        #expect(DecisionKind.nonRevenue.sectionTitle == "Non-revenue hours")
        #expect(DecisionKind(entity: "non_revenue_approval") == .nonRevenue)
    }

    @Test func gatingFollowsCapabilityAndPermissions() {
        let perms = [RevenuePermission.read, RevenuePermission.explain, RevenuePermission.decide, "tenant.fleet.read"]
        let off = OwnerFeatures(permissions: perms, disabledCapabilities: [TenantCapability.revenueReconciliation])
        #expect(!off.revenueRead && !off.decisionKinds.contains(.nonRevenue))
        #expect(!off.allows(.revenueDifference(Self.differenceID)) && !off.allows(.dailySheet(Self.machineID)))
        #expect(off.route(.revenueDifference(Self.differenceID)) == .approvals)
        #expect(off.route(.decision(.nonRevenue, Self.approvalID)) == .approvals)
        #expect(off.route(.dailySheet(Self.machineID)) == .machine(Self.machineID))
        #expect(off.route(.dailySheetDay(Self.machineID, "2026-10-26")) == .machine(Self.machineID))
        let on = OwnerFeatures(permissions: perms)
        #expect(on.revenueRead && on.revenueExplain && on.revenueDecide && on.approvalsScreen)
        #expect(on.decisionKinds.last == .nonRevenue && on.canDecide(.nonRevenue))
        #expect(on.allows(.dailySheetDay(Self.machineID, "2026-10-26")))
        // An older server never grants the revenue permissions: nothing changes.
        let older = OwnerFeatures(permissions: ["tenant.fleet.read"])
        #expect(!older.revenueRead && !older.allows(.dailySheet(Self.machineID)) && !older.decisionKinds.contains(.nonRevenue))
    }

    @Test func deepLinksOpenTheRecords() throws {
        let id = Self.differenceID.uuidString.lowercased()
        #expect(DeepLinkParser.route(record: RecordRef(kind: .revenueDifference, id: Self.differenceID)) == .revenueDifference(Self.differenceID))
        #expect(DeepLinkParser.route(record: RecordRef(kind: .nonRevenueApproval, id: Self.approvalID)) == .decision(.nonRevenue, Self.approvalID))
        #expect(DeepLinkParser.route(entity: "revenue_difference", id: id, path: nil) == .revenueDifference(Self.differenceID))
        #expect(DeepLinkParser.route(path: "/tenant/revenue-differences/\(id)") == .revenueDifference(Self.differenceID))
        #expect(DeepLinkParser.route(path: "/tenant/non-revenue-approvals/\(Self.approvalID.uuidString.lowercased())")
            == .decision(.nonRevenue, Self.approvalID))
        #expect(DeepLinkParser.route(path: "/tenant/revenue-differences") == .approvals)
        #expect(DeepLinkParser.route(path: "/tenant/non-revenue-approvals") == .approvals)
        #expect(DeepLinkParser.route(path: "/tenant/engine-hours/daily-sheet") == .fleet)
        let push = DeepLinkParser.parse(pushPayload: ["kind": "REVENUE_DIFFERENCE", "record_id": id, "type": "REVENUE_DIFFERENCE"])
        #expect(push?.route == .revenueDifference(Self.differenceID))
        #expect(OwnerRoute.revenueDifference(Self.differenceID).identifiesRecord && !OwnerRoute.dailySheet(Self.machineID).identifiesRecord)
    }

    static let summaryJSON = """
    {"as_of":"2026-10-26T09:00:00Z","policy_version":"o1","hidden_tiles":[],"unavailable_tiles":[],"disabled_capabilities":[],
     "revenue_differences":{"open":2,"awaiting_decision":1,"amounts":[{"currency":"TZS","count":3,"amount":"450000"}],
     "oldest_open_days":4,"window_days":30,"explained_in_window":5,"confirmed_in_window":1,"cleared_in_window":2,
     "items":[{"id":"\(differenceID.uuidString.lowercased())","machine_id":"\(machineID.uuidString.lowercased())","machine_code":"EX-01",
     "period_key":"WEEK:2026-W43","local_from":"2026-10-19","local_to":"2026-10-25","currency":"TZS","difference":"200000","status":"OPEN"}]}}
    """

    @Test func dashboardTile() throws {
        let summary = try AssetaJSON.decoder().decode(AccountabilitySummaryDTO.self, from: Data(Self.summaryJSON.utf8))
        let tile = try #require(AccountabilityDashboard.tiles(summary).first { $0.id == "revenue_differences" })
        #expect(tile.title == "Revenue differences" && tile.route == .approvals && tile.footer == "Last 30 days")
        #expect(tile.rows.map(\.label) == ["To explain", "Awaiting a decision", "Amount", "Oldest open", "Explained", "Confirmed",
                                           "Cleared", "EX-01 · 19 Oct 2026 – 25 Oct 2026"])
        #expect(tile.rows[2].value == "3 · \(money(450_000))" && tile.rows[3].value == "4 days")
        #expect(tile.rows.last?.value == money(200_000))
        #expect(!AccountabilityDashboard.tiles(summary, disabled: [TenantCapability.revenueReconciliation])
            .contains { $0.id == "revenue_differences" })
        #expect(!AccountabilityDashboard.tiles(summary, revenueRead: false).contains { $0.id == "revenue_differences" })
        // Oldest open null → the row is hidden; no amounts → "None".
        let quiet = try AssetaJSON.decoder().decode(AccountabilitySummaryDTO.self, from: Data(Self.summaryJSON
            .replacingOccurrences(of: #""oldest_open_days":4"#, with: #""oldest_open_days":null"#)
            .replacingOccurrences(of: #"[{"currency":"TZS","count":3,"amount":"450000"}]"#, with: "[]").utf8))
        let rows = try #require(AccountabilityDashboard.tiles(quiet).first { $0.id == "revenue_differences" }).rows
        #expect(!rows.map(\.label).contains("Oldest open") && rows[2].value == "None")
    }

    static let sheetDay = """
    {"machine_id":"\(machineID.uuidString.lowercased())","machine_code":"EX-01","machine_name":"Excavator","day":"2026-10-26",
     "first_reading":"1200.0","last_reading":"1210.5","reading_count":2,"engine_hours":"10.50","customer_work_hours":"8.00",
     "non_revenue_hours":"1.50","non_revenue_by_type":{"MOBILIZATION":"1.50"},"non_revenue_pending_hours":"0",
     "revenue_hours":"8.00","approved_non_customer_hours":"0","identified_variance_hours":"0","unexplained_hours":"1.00",
     "pending_review_hours":"0","fuel_litres":"42.5",
     "jobs":[{"job_id":"bbbbbbbb-0000-4000-8000-000000000001","job_number":"J-12","status":"COMPLETED","billing_mode":"INVOICE",
     "customer_id":null,"customer_name":"Mjenzi Ltd","job_site_id":null,"job_site_name":null,"customer_work_hours":"8.00","revenue_hours":"8.00"}],
     "money":[{"currency":"TZS","expected":"400000","in_progress":"0","attributed":"300000","difference":"100000",
     "unexplained_hours":"1.00","unexplained_expected":"50000"}],"flags":["UNEXPLAINED_HOURS","SOMETHING_NEW"],
     "readings":[{"id":"f8000000-0000-4000-8000-000000000002","kind":"CLOSING","reading":"1210.5","captured_at":"2026-10-26T15:00:00Z",
     "state":"ACCEPTED","job_id":null,"job_number":null},{"id":"f8000000-0000-4000-8000-000000000001","kind":"OPENING",
     "reading":"1200.0","captured_at":"2026-10-26T05:00:00Z","state":"ACCEPTED","job_id":null,"job_number":null}],
     "segments":[],"money_sources":[],"flag_records":[],"fuel_events":[]}
    """

    @Test func dailySheet() throws {
        #expect(try Contract.missingRequired(schema: "DailyMachineSheetDetailDto", json: Self.sheetDay) == [])
        let s = try AssetaJSON.decoder().decode(DailyMachineSheetDTO.self, from: Data(Self.sheetDay.utf8))
        let row = RevenuePresentation.sheetRow(s)
        #expect(row.title == "26 Oct 2026" && row.hours == "Engine 10.5 h · Revenue 8 h")
        #expect(row.differences == ["Difference \(money(100_000))"])
        #expect(row.flags == "Unexplained hours · Something new")
        #expect(RevenuePresentation.sheetHours(s).map(\.label) == [
            "Engine hours", "Customer work", "Non-revenue", "Non-revenue · Mobilization", "Revenue hours", "Unexplained",
        ])
        let readings = RevenuePresentation.sheetReadings(s, timeZone: utc)
        #expect(readings.map(\.label) == ["First reading", "Last reading", "Readings taken", "05:00 · 1200", "15:00 · 1210.5"])
        #expect(readings.map(\.value) == ["1200", "1210.5", "2", "Opening", "Closing"])
        #expect(RevenuePresentation.sheetJobs(s) == [DecisionField(label: "J-12 · Mjenzi Ltd", value: OwnerFormat.hours(DecimalString(8)))])
        let money = RevenuePresentation.sheetMoney(s)
        #expect(money.first?.title == "Money (TZS)")
        #expect(money.first?.fields.map(\.label) == ["Expected revenue", "Money attributed", "Difference",
                                                    "Unexplained hours expected as revenue"])
        #expect(RevenuePresentation.sheetFuel(s) == "42.5 L")
        #expect(RevenuePresentation.sheetRange(now: Date(timeIntervalSince1970: 1_793_000_000), timeZone: utc)
            == (from: "2026-10-13", to: "2026-10-26"))
        #expect(RevenuePresentation.sheetRows([s, try AssetaJSON.decoder().decode(DailyMachineSheetDTO.self, from: Data(Self.sheetDay
            .replacingOccurrences(of: #""day":"2026-10-26""#, with: #""day":"2026-10-27""#).utf8))]).map(\.day) == ["2026-10-27", "2026-10-26"])
    }
}
