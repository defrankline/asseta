import AssetaModel
@testable import AssetaOwnerKit
import Foundation
import Testing

/// Phase 4 DTOs against `contracts/openapi.json`, and leniency of the dashboard when a section is missing or unreadable.
struct ManagementContractTests {
    static let uuid = "aaaaaaaa-0000-4000-8000-000000000001"
    static let hoursFig = #"{"hours":"12.50","count":2,"route":"/tenant/hours/ledger"}"#
    static let moneyFig = #"{"lines":[{"currency":"TZS","count":2,"amount":"1500.00"}],"count":2,"route":"/tenant/cash"}"#
    static let countFig = #"{"count":3,"route":"/tenant/daily-reports"}"#
    static let queue = """
    {"count":1,"hours":"4.00","amounts":[{"currency":"TZS","count":1,"amount":"400.00"}],"route":"/tenant/hours/purchases?queue=UNPAID",
     "items":[{"purchase_id":"\(uuid)","purchase_number":"HP-1","customer_id":"\(uuid)","customer_name":"Acme","hours_awaiting":"4.00",
               "amount_open":"400.00","currency":"TZS","created_at":"2026-11-01T08:00:00Z","route":"/tenant/hours/purchases/\(uuid)"}]}
    """
    static let hoursSection = """
    {"purchased":\(hoursFig),"purchased_value":\(moneyFig),"activated":\(hoursFig),"consumed":\(hoursFig),"remaining":\(hoursFig),
     "remaining_by_customer":[{"customer_id":"\(uuid)","customer_name":"Acme","remaining":"3.00","activated":"5.00","consumed":"2.00",
                               "route":"/tenant/hours/statement/\(uuid)"}],
     "remaining_customers_total":1,"unpaid_purchases":\(queue),"unconfirmed_purchases":\(queue),"awaiting_activation":\(queue)}
    """
    static let operations = """
    {"operating_hours":\(hoursFig),"customer_hours":\(hoursFig),"authorized_non_customer_hours":\(hoursFig),"unexplained_hours":\(hoursFig),
     "by_excavator":[{"machine_id":"\(uuid)","machine_code":"EX-1","machine_name":"Ex","operating_hours":"8.00","customer_hours":"6.00",
                      "authorized_hours":"1.00","unexplained_hours":"1.00","route":"/tenant/work-allocations"}],
     "meter_discrepancies":{"count":1,"by_type":[{"type":"ROLLBACK","count":1,"route":"/tenant/exceptions"}],"route":"/tenant/exceptions"},
     "pending_reports":\(countFig),"returned_reports":\(countFig)}
    """
    static let cash = """
    {"collected":\(moneyFig),"held_by_employee":[{"staff_member_id":"\(uuid)","staff_member_name":"Sam","currency":"TZS","outstanding":"10.00",
       "in_transit_out":"0.00","claimed_unverified_handovers":"0.00","pending_floats":"0.00","approved_retention":"0.00",
       "route":"/tenant/staff/\(uuid)/accountability"}],
     "transferred":\(moneyFig),"in_transit":\(moneyFig),"declared_for_remittance":\(moneyFig),"confirmed_by_company":\(moneyFig),
     "outstanding":\(moneyFig),"unconfirmed_remittances":\(moneyFig),"disputed_remittances":\(moneyFig),"disputed_transfers":\(moneyFig)}
    """
    static let pendingItem = """
    {"kind":"ADJUSTMENT","record_type":"ADJUSTMENT_REQUEST","id":"\(uuid)","reference":"ARQ-1","status":"PROPOSED","requested_by":null,
     "requested_by_name":null,"requested_at":"2026-11-01T08:00:00Z","amount":"5.00","unit":"HOURS","currency":null,"customer_id":null,
     "customer_name":null,"machine_id":null,"machine_code":null,"machine_name":null,"staff_member_id":null,"staff_member_name":null,
     "route":"/tenant/finance/adjustments/requests/\(uuid)"}
    """
    static let kind = #"{"kind":"HOURS_CORRECTION","count":2,"oldest_at":"2026-11-01T08:00:00Z","route":"/tenant/approvals"}"#
    static let exceptions = """
    {"unexplained_engine_hours":\(hoursFig),"shortages":\(moneyFig),"overages":\(moneyFig),"shortages_opened_in_period":\(moneyFig),
     "overages_opened_in_period":\(moneyFig),"pending_adjustments":{"total":2,"by_kind":[\(kind)],"oldest":[\(pendingItem)],"route":"/tenant/accountability/pending-adjustments"},
     "unauthorized_attempts":{"permission_denied":1,"segregation_of_duties":2,"since":"2026-11-01T00:00:00Z","route":"/tenant/audit"},
     "unconfirmed_payments":\(moneyFig),"outstanding_approvals":{"total":3,"by_kind":[\(kind)]},
     "overdue_reports":{"total":4,"missing_daily_reports":\(countFig),"remittances_overdue_today":\(countFig)},
     "unresolved_variances":{"total":1,"by_source":[{"source":"HANDOVER","unit":"MONEY","count":1,"amounts":[{"currency":"TZS","count":1,"amount":"5.00"}],"route":"/tenant/cash/variances"}]},
     "changeover_jobs_awaiting_approval":{"count":1,"oldest_days":5,"items":[{"job_id":"\(uuid)","job_number":"J-1","machine_id":"\(uuid)","machine_code":"EX-1",
        "machine_name":"Ex","customer_id":"\(uuid)","customer_name":"Acme","changed_over_at":"2026-11-01T08:00:00Z","days_waiting":5,"route":"/tenant/jobs/\(uuid)"}]}}
    """
    static func summary(_ extra: String) -> String {
        #"{"as_of":"2026-11-09T08:00:00Z","policy_version":"v1","hidden_tiles":[],"unavailable_tiles":[]\#(extra)}"#
    }

    @Test func sectionsMatchTheContractAndDecode() throws {
        for (schema, json) in [("CustomerHoursSectionDto", Self.hoursSection), ("ExcavatorOperationsSectionDto", Self.operations),
                               ("CashSectionDto", Self.cash), ("ExceptionsSectionDto", Self.exceptions)] {
            #expect(try Contract.missingRequired(schema: schema, json: json) == [], "\(schema)")
        }
        let body = Self.summary(#","period":{"date_from":"2026-11-01","date_to":"2026-11-09"},"hours_section":\#(Self.hoursSection),"operations_section":\#(Self.operations),"cash_section":\#(Self.cash),"exceptions_section":\#(Self.exceptions)"#)
        let s = try AssetaJSON.decoder().decode(AccountabilitySummaryDTO.self, from: Data(body.utf8))
        #expect(s.period?.dateFrom == "2026-11-01")
        #expect(s.hoursSection?.remaining.hours.value == Decimal(string: "12.5"))
        #expect(s.operationsSection?.byExcavator.first?.machineCode == "EX-1")
        #expect(s.cashSection?.heldByEmployee.first?.staffMemberName == "Sam")
        #expect(s.exceptionsSection?.changeoverJobsAwaitingApproval.oldestDays == 5)
        #expect(s.exceptionsSection?.pendingAdjustments.oldest.first?.reference == "ARQ-1")
    }

    @Test func aBadSectionNeverFailsTheDashboard() throws {
        let s = try AssetaJSON.decoder().decode(AccountabilitySummaryDTO.self, from: Data(Self.summary(#","cash_section":{"nope":1},"hours_section":null"#).utf8))
        #expect(s.cashSection == nil && s.hoursSection == nil && s.period == nil)
    }

    @Test func employeeAccountabilityAndLookupDecode() throws {
        let record = #"{"record_type":"COLLECTION","id":"\#(Self.uuid)","occurred_at":"2026-11-01T08:00:00Z","reference":"COL-1","amount":"5.00","currency":"TZS","route":"/tenant/customer-payments/\#(Self.uuid)"}"#
        let noID = #"{"record_type":"CASE_ITEM","id":null,"occurred_at":"2026-11-01T08:00:00Z"}"#
        let employee = """
        {"identity":{"staff_member_id":"\(Self.uuid)","user_id":null,"full_name":"Sam","employee_code":"E1","kind":"SUPERVISOR","phone":null,"login_email":null,"is_active":true,"roles":["Supervisor"]},
         "date_from":"2026-11-01","date_to":"2026-11-09","cash_held":[{"staff_member_id":"\(Self.uuid)","currency":"TZS","outstanding":"5.00","claimed_unverified_handovers":"0.00","pending_spending":"0.00","as_of":"2026-11-09T08:00:00Z"}],
         "collections":[\(record)],"floats":[],"transfers_in":[],"transfers_out":[],"remittances":[],"spending":[],"retentions":[],"differences":[\(noID)],
         "custody_adjustments":[],"reports_submitted":[],"approvals_made":[],"adjustments_requested":[],"adjustments_decided":[],"scorecard_items":[],"scorecard_visible":false,"truncated":["collections"]}
        """
        #expect(try Contract.missingRequired(schema: "EmployeeAccountabilityDto", json: employee) == [])
        let dto = try AssetaJSON.decoder().decode(EmployeeAccountabilityDTO.self, from: Data(employee.utf8))
        #expect(dto.identity.fullName == "Sam" && dto.collections.first?.reference == "COL-1" && dto.differences.first?.id == nil)
        #expect(dto.truncated == ["collections"] && !dto.scorecardVisible)

        let lookup = """
        {"reference":"COL-1","matches":[{"record_type":"COLLECTION","id":"\(Self.uuid)","reference":"COL-1","route":"/tenant/customer-payments/\(Self.uuid)","status":"VERIFIED",
          "recorded_by_name":"Sam","recorded_at":"2026-11-01T08:00:00Z","amount":"5.00","currency":"TZS","balance_outstanding":"1.00","balance_unit":"MONEY","hours_remaining":null}]}
        """
        #expect(try Contract.missingRequired(schema: "LookupResultDto", json: lookup) == [])
        let found = try AssetaJSON.decoder().decode(LookupResultDTO.self, from: Data(lookup.utf8))
        #expect(found.matches.first?.balanceOutstanding?.value == 1)
    }

    @Test func requestsCarryTheirFilters() {
        let id = UUID(uuidString: Self.uuid)!
        let lookup = OwnerAPI.lookup(reference: " COL-1 ")
        #expect(lookup.path == "/api/v1/tenant/lookup" && lookup.queryItems == [URLQueryItem(name: "reference", value: "COL-1")])
        let employee = OwnerAPI.employeeAccountability(id, from: "2026-11-01", to: "2026-11-09")
        #expect(employee.path == "/api/v1/tenant/employees/\(Self.uuid)/accountability")
        #expect(employee.queryItems == [URLQueryItem(name: "date_from", value: "2026-11-01"), URLQueryItem(name: "date_to", value: "2026-11-09")])
        #expect(OwnerAPI.accountabilitySummary().path == "/api/v1/tenant/accountability/summary" && OwnerAPI.accountabilitySummary().queryItems.isEmpty)
        #expect(SnapshotKey.accountabilityPeriod(from: nil, to: nil) == SnapshotKey.accountability)
    }
}
