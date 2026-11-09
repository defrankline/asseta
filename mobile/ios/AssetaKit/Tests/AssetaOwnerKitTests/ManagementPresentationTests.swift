import AssetaModel
@testable import AssetaOwnerKit
import Foundation
import Testing

/// Strings doc "DEC-032 Phase 4 — management view": the route table, group rows, tile replacement, employee and lookup rows.
struct ManagementPresentationTests {
    typealias T = ManagementTexts
    typealias S = ManagementContractTests
    static let id = UUID(uuidString: S.uuid)!

    static let all = OwnerFeatures(permissions: [
        "tenant.accountability.read", "tenant.accountability.employee.read", "tenant.lookup.read", "tenant.fleet.read", "tenant.job.read",
        "tenant.finance.read", "tenant.hours.read", "tenant.meter.read", "tenant.approval.read", "tenant.approval.expense", "tenant.case.read",
    ])
    static let none = OwnerFeatures(permissions: ["tenant.accountability.read"])

    func target(_ route: String?, _ f: OwnerFeatures = Self.all) -> FigureTarget? { ManagementRoutes.target(route, features: f) }

    @Test func routeTable() {
        let u = S.uuid
        #expect(target(nil) == nil && target("") == nil)
        #expect(target("/tenant/hours/balances") == .screen(.customerHours))
        #expect(target("/tenant/hours/balances?customer_id=\(u)") == .screen(.hoursStatement(customer: Self.id, name: nil)))
        #expect(target("/tenant/hours/purchases/\(u)") == .screen(.hoursPurchase(Self.id)))
        #expect(target("/tenant/hours/purchases?queue=UNPAID") == .web("/tenant/hours/purchases?queue=UNPAID"))
        #expect(target("/tenant/hours/ledger") == .web("/tenant/hours/ledger"))
        #expect(target("/tenant/hours/transfers?status=PENDING") == .screen(.approvals))
        #expect(target("/tenant/hours/transfers") == .web("/tenant/hours/transfers"))
        #expect(target("/tenant/jobs?status=PENDING_APPROVAL") == .screen(.approvals))
        #expect(target("/tenant/jobs") == .web("/tenant/jobs"))
        #expect(target("/tenant/daily-reports?status=SUBMITTED") == .screen(.approvals))
        #expect(target("/tenant/daily-reports?status=RETURNED") == .web("/tenant/daily-reports?status=RETURNED"))
        #expect(target("/tenant/accountability/pending-adjustments") == .screen(.approvals))
        #expect(target("/tenant/finance/adjustments/requests/\(u)") != .screen(.approvals))
        #expect(target("/tenant/finance/adjustments/\(u)") == .web("/tenant/finance/adjustments/\(u)"))
        #expect(target("/tenant/finance/cash") == .screen(.cash))
        #expect(target("/tenant/finance/cash?tab=x") == .web("/tenant/finance/cash?tab=x"))
        #expect(target("/tenant/finance/cash/remittance-overdue") == .screen(.overdueRemittances))
        #expect(target("/tenant/finance/cash/variances?status=CLOSURE_PROPOSED") == .screen(.approvals))
        #expect(target("/tenant/finance/cash/remittances?partial_reason_pending=true") == .screen(.approvals))
        #expect(target("/tenant/exceptions") == .screen(.exceptions(jobID: nil)))
        #expect(target("/tenant/cases") == .screen(.investigations))
        #expect(target("/tenant/customer-payments/\(u)") == .web("/tenant/customer-payments/\(u)"))
        #expect(target("/tenant/staff/\(u)/accountability") == .screen(.employeeAccountability(Self.id, name: nil, from: nil, to: nil)))
    }

    @Test func aRoleWithoutTheScreenGoesToTheWebAndUnsafePathsNowhere() {
        #expect(target("/tenant/exceptions", Self.none) == .web("/tenant/exceptions"))
        #expect(target("/tenant/staff/\(S.uuid)/accountability", Self.none) == .web("/tenant/staff/\(S.uuid)/accountability"))
        #expect(target("https://evil.example/x") == nil)
        #expect(target("//tenant/x") == nil && target("/tenant//x") == nil && target("/tenant/\\x") == nil)
        #expect(target("/other/x") == nil)
    }

    @Test func excavatorPrefersTheMachineScreens() {
        let m = Self.id
        #expect(ManagementRoutes.excavatorTarget(machineID: m, route: "/tenant/x", features: Self.all) != nil)
        #expect(ManagementRoutes.excavatorTarget(machineID: m, route: "/tenant/x", features: Self.none) == .web("/tenant/x"))
    }

    @Test func deepLinkAndGating() {
        #expect(DeepLinkParser.route(path: "/tenant/staff/\(S.uuid)/accountability") == .employeeAccountability(Self.id, name: nil, from: nil, to: nil))
        #expect(Self.none.route(.employeeAccountability(Self.id, name: nil, from: nil, to: nil)) == .accountability)
        #expect(Self.all.lookup && !Self.none.lookup && Self.all.moreEntries.contains(T.lookupMore))
    }

    func summary(_ extra: String) throws -> AccountabilitySummaryDTO {
        try AssetaJSON.decoder().decode(AccountabilitySummaryDTO.self, from: Data(S.summary(extra).utf8))
    }

    static let oldTiles = #","outstanding_approvals":{"approval_requests":1,"cash_retentions":0,"custody_adjustments":0,"write_offs":0,"payments_to_verify":0,"remittances_to_verify":0,"total":3,"hours_transfers":2,"meter_resets":0},"# +
        #""cash":{"custodians":[],"transfers_awaiting_acknowledgement":[],"floats_awaiting_acknowledgement":[],"remittances_awaiting_confirmation":[],"partial_remittances_in_window":0},"payments":{"awaiting_confirmation":[]}"#

    @Test func aPresentSectionReplacesItsOldTiles() throws {
        let old = try summary(Self.oldTiles)
        let ids = AccountabilityDashboard.tiles(old).map(\.id)
        #expect(ids.contains("outstanding_approvals") && ids.contains("cash") && ids.contains("payments"))
        let approvals = try #require(AccountabilityDashboard.tiles(old).first { $0.id == "outstanding_approvals" })
        #expect(approvals.rows.contains { $0.label == "Hours transfers" && $0.value == "2" })
        #expect(!approvals.rows.contains { $0.label == "Meter resets" })

        let replaced = try summary(Self.oldTiles + #","cash_section":\#(S.cash),"exceptions_section":\#(S.exceptions)"#)
        let kept = AccountabilityDashboard.tiles(replaced).map(\.id)
        #expect(!kept.contains("outstanding_approvals") && !kept.contains("cash") && !kept.contains("payments"))
        #expect(ManagementDashboard.groups(replaced, features: Self.all).map(\.id) == ["cash_section", "exceptions_section"])
    }

    @Test func groupRowsInOrderWithFormats() throws {
        let s = try summary(#","hours_section":\#(S.hoursSection),"operations_section":\#(S.operations),"cash_section":\#(S.cash),"exceptions_section":\#(S.exceptions)"#)
        let groups = ManagementDashboard.groups(s, features: Self.all, timeZone: TimeZone(identifier: "UTC")!)
        #expect(groups.map(\.title) == [T.hoursTitle, T.opsTitle, T.cashTitle, T.excTitle])
        let hours = groups[0].blocks[0].rows
        #expect(hours.map(\.label).prefix(3) == [T.hoursPurchased, T.hoursPurchasedValue, T.hoursActivated])
        #expect(hours[0].value == "12.5 h")
        let unpaid = try #require(hours.first { $0.id == "unpaid" })
        #expect(unpaid.value == "1 · 4 h" && unpaid.caption != nil)
        #expect(groups[0].blocks[1].heading == T.hoursByCustomer && groups[0].blocks[1].footer == nil)
        let exc = groups[3].blocks
        #expect(exc.map(\.heading) == [nil, T.excApprovals(3), T.excPending(2), T.excVariances(1)])
        let attempts = try #require(exc[0].rows.first { $0.id == "attempts" })
        #expect(attempts.value == "3" && attempts.caption == "Denied 1 · Second person required 2")
        #expect(exc[0].rows.contains { $0.id == "changeover" && $0.caption == "Oldest 5 days" })
        let ops = groups[1].blocks[1].rows[0]
        #expect(ops.label == "EX-1 · Ex" && ops.caption == "Customer 6 h · Authorized 1 h · Unexplained 1 h")
        #expect(groups[2].blocks[1].heading == T.cashHeld)
    }

    static func employee(unit: String? = nil, scorecard: Bool = false) throws -> EmployeeAccountabilityDTO {
        let unitJSON = unit.map { "\"\($0)\"" } ?? "null"
        let r = #"{"record_type":"customer_payment","id":"\#(S.uuid)","occurred_at":"2026-11-01T08:00:00Z","reference":"COL-1","status":"VERIFIED","amount":"5.00","currency":"TZS","unit":\#(unitJSON),"route":"/tenant/customer-payments/\#(S.uuid)"}"#
        let json = """
        {"identity":{"staff_member_id":"\(S.uuid)","user_id":null,"full_name":"Sam","employee_code":"E1","kind":"S","phone":null,"login_email":null,"is_active":false,"roles":["Supervisor"]},
         "date_from":"2026-11-01","date_to":"2026-11-09","cash_held":[{"staff_member_id":"\(S.uuid)","currency":"TZS","outstanding":"5.00","claimed_unverified_handovers":"1.00","pending_spending":"0.00","in_transit_out":"0.00","pending_floats":"0.00","approved_retention":"0.00","as_of":"2026-11-09T08:00:00Z"}],
         "collections":[\(r),\(r)],"floats":[],"transfers_in":[],"transfers_out":[],"remittances":[],"spending":[],"retentions":[],"differences":[],
         "custody_adjustments":[],"reports_submitted":[],"approvals_made":[],"adjustments_requested":[],"adjustments_decided":[],"scorecard_items":[\(r)],"scorecard_visible":\(scorecard),"truncated":[]}
        """
        return try AssetaJSON.decoder().decode(EmployeeAccountabilityDTO.self, from: Data(json.utf8))
    }

    @Test func employeeFiguresAndLists() throws {
        let d = try Self.employee()
        let figures = EmployeePresentation.figureRows(d)
        #expect(figures.count == 13)
        #expect(figures[0].label == T.employeeListCollections && figures[0].value.hasPrefix("2 · "))
        #expect(figures[1].value == "0")
        #expect(EmployeePresentation.cashHeld(d)[0].caption?.hasPrefix("Claimed") == true)
        let lists = EmployeePresentation.recordLists(d, features: Self.all, timeZone: TimeZone(identifier: "UTC")!)
        #expect(lists.map(\.title) == [T.employeeListCollections])
        #expect(lists[0].rows[0].caption?.contains(" · Verified") == true)
        #expect(lists[0].rows[0].target == .web("/tenant/customer-payments/\(S.uuid)"))
        #expect(EmployeePresentation.figureRows(try Self.employee(scorecard: true)).count == 14)
    }

    @Test func lookupCardShowsOnlyFilledRowsAndBalanceUnit() throws {
        let json = #"{"record_type":"hours_purchase","id":"\#(S.uuid)","reference":"HP-1","route":"/tenant/hours/purchases/\#(S.uuid)","status":"ACTIVE","recorded_by_name":"Sam","recorded_at":"2026-11-01T08:00:00Z","balance_outstanding":"3.50","balance_unit":"HOURS","hours_remaining":"2"}"#
        let match = try AssetaJSON.decoder().decode(LookupMatchDTO.self, from: Data(json.utf8))
        let card = LookupPresentation.card(match, features: Self.all, timeZone: TimeZone(identifier: "UTC")!)
        #expect(card.title == "Hours purchase" && card.status == "Active")
        #expect(card.rows.map(\.label) == [T.lookupRecordedBy, T.lookupBalance, T.lookupHoursRemaining])
        #expect(card.rows[1].value == "3.5 h" && card.target == .screen(.hoursPurchase(Self.id)))
        #expect(T.lookupType("cash_handover") == "Remittance" && T.lookupType("new_thing") == OwnerFormat.humanize("new_thing"))
    }
}
