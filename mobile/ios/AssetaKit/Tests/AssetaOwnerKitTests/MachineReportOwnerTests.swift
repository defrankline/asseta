import AssetaModel
import AssetaNetwork
@testable import AssetaOwnerKit
import Foundation
import Testing

@Suite("ADR-008: machine reports, credit and money on the Owner app")
struct MachineReportOwnerTests {
    static let me = UUID(), other = UUID(), machine = UUID(), pwani = UUID()

    static func report(by submitter: UUID = other, status: MachineReportState = .submitted, customer: Decimal = 220,
                       idle: Decimal = 80, machineID: UUID = machine, code: String = "EX-01",
                       at: Date = Date(timeIntervalSince1970: 1_792_000_000)) -> MachineReportDTO {
        MachineReportDTO(id: UUID(), reportNumber: "MR-2026-00001", machineID: machineID, machineCode: code, machineName: "CAT 320D2",
                         startReading: 1210, startAt: at.addingTimeInterval(-86400), endReading: 1210 + customer + idle, endAt: at,
                         status: status, submittedBy: submitter, submittedByName: "Daudi Mollel", submittedAt: at,
                         lines: [.init(lineNo: 1, kind: .customer, customerID: pwani, customerName: "Pwani", hours: customer,
                                       availableHours: 140),
                                 .init(lineNo: 2, kind: .nonProductive, reasonID: UUID(), reasonName: "Breakdown / repair", hours: idle,
                                       note: "Hose")])
    }

    @Test func onlyApproversDecideAndNeverTheirOwnReport() {
        let approver: Set<String> = [MachineReportPermission.read, MachineReportPermission.approve]
        #expect(MachineReportApproval.decision(Self.report(), me: Self.me, permissions: approver) == .allowed)
        #expect(MachineReportApproval.decision(Self.report(by: Self.me), me: Self.me, permissions: approver) == .ownReport)
        #expect(MachineReportApproval.decision(Self.report(), me: Self.me, permissions: [MachineReportPermission.read]) == .notPermitted)
        #expect(MachineReportApproval.decision(Self.report(status: .approved), me: Self.me, permissions: approver) == .decided)
        #expect(!MachineReportApproval.rejectReasonValid("   "))
        #expect(MachineReportApproval.rejectReasonValid("Idle hours too high"))
        let features = OwnerFeatures(permissions: Array(approver))
        #expect(features.machineReports && features.reportsApprove)
    }

    @Test func customerLinesShowHoursBeforeAndAfter() throws {
        let line = try #require(Self.report().lines.first)
        let ba = try #require(MachineReportApproval.beforeAfter(line))
        #expect(ba.before == 140 && ba.after == -80)
        #expect(MachineReportApproval.beforeAfter(Self.report().lines[1]) == nil)
    }

    @Test func machineHoursSummaryLeavesRejectedOut() {
        let second = UUID()
        let summary = MachineHoursSummary.of([Self.report(), Self.report(status: .rejected),
                                              Self.report(status: .approved, customer: 38, idle: 4, machineID: second, code: "WL-01")])
        #expect(summary.productive == 258 && summary.nonProductive == 84)
        #expect(summary.machines.map(\.code) == ["EX-01", "WL-01"])
        #expect(summary.machines[0].lastPending && !summary.machines[1].lastPending)
        #expect(summary.byReason.first?.name == MachineReportOwnerTexts.customers && summary.byReason[1].hours == 84)
        #expect(summary.productivePercent == 75)
        #expect(MachineHoursSummary.of([]).productivePercent == 0)
    }

    @Test func soldByMethodIncludesCredit() throws {
        let json = """
        [{"id":"\(UUID())","purchase_number":"HP-1","client_id":null,"customer_id":"\(UUID())","machine_id":"\(UUID())",
          "hours":"20","currency":"TZS","amount":"1900000","status":"ACTIVE","created_at":"2026-11-16T08:00:00Z",
          "totals":{"purchased":"20","activated":"10","consumed":"0","remaining":"10","awaiting_activation":"10"},
          "credit_amount":"900000","credit_invoice":{"id":"\(UUID())","invoice_number":"CI-2026-00001","amount":"900000",
          "paid":"0","balance":"900000","due_date":"2026-11-30","status":"UNPAID","overdue":false},
          "payments":[{"id":"\(UUID())","amount":"600000","method":"CASH","status":"CLAIMED"},
                      {"id":"\(UUID())","amount":"400000","method":"MOBILE_MONEY","status":"CLAIMED"}]}]
        """
        let orders = try AssetaJSON.decoder().decode([HoursPurchaseDTO].self, from: Data(json.utf8))
        let sold = SoldByMethod.of(orders)
        #expect(sold.cash == 600_000 && sold.mobileMoney == 400_000 && sold.credit == 900_000 && sold.total == 1_900_000)
        #expect(sold.hours == 20 && orders[0].creditInvoice?.invoiceNumber == "CI-2026-00001")
    }

    @Test func attentionListsWaitingReportsAndSilentMachines() {
        let now = Date(timeIntervalSince1970: 1_792_000_000)
        let quiet = MachineReportStatusDTO(machineID: UUID(), machineCode: "EX-02", machineName: "Komatsu", previousReading: 3182.8,
                                           daysSinceReport: 3)
        let fresh = MachineReportStatusDTO(machineID: UUID(), machineCode: "WL-01", previousReading: 5016.8, daysSinceReport: 1)
        let rows = AttentionRow.rows(pending: [Self.report(at: now)], states: [quiet, fresh], reminderDays: 3, now: now)
        #expect(rows.map(\.title) == ["EX-01 report · 80 h non-productive", "EX-02 · no report for 3 days"])
        #expect(rows[0].pill == MachineReportOwnerTexts.review && rows[1].pill == MachineReportOwnerTexts.overdue)
    }

    @Test func overdueFollowsTheTenantsReminderDays() {
        let now = Date(timeIntervalSince1970: 1_792_000_000)
        let five = MachineReportStatusDTO(machineID: UUID(), machineCode: "EX-02", previousReading: 3182.8, daysSinceReport: 5)
        let two = MachineReportStatusDTO(machineID: UUID(), machineCode: "WL-01", previousReading: 5016.8, daysSinceReport: 2)
        let never = MachineReportStatusDTO(machineID: UUID(), machineCode: "GR-01", previousReading: 900, daysSinceReport: nil)
        let opening = MachineReportStatusDTO(machineID: UUID(), machineCode: "DZ-01", previousReading: nil)
        let rejected = MachineReportStatusDTO(machineID: UUID(), machineCode: "EX-03", previousReading: 100, daysSinceReport: 1,
                                              rejectedReportID: UUID())
        let waiting = MachineReportStatusDTO(machineID: UUID(), machineCode: "EX-04", previousReading: 100, daysSinceReport: 9,
                                             pendingReportID: UUID(), rejectedReportID: UUID())
        let all = [five, two, never, opening, rejected, waiting]
        func titles(_ days: Int?) -> [String] {
            AttentionRow.rows(pending: [], states: all, reminderDays: days, now: now).map(\.title)
        }
        #expect(titles(3) == ["EX-02 · no report for 5 days", "EX-03 · report rejected, not yet redone",
                              "GR-01 · no report yet", "DZ-01 · no report yet"])
        #expect(titles(2) == ["EX-02 · no report for 5 days", "WL-01 · no report for 2 days",
                              "EX-03 · report rejected, not yet redone", "GR-01 · no report yet", "DZ-01 · no report yet"])
        #expect(titles(7) == ["EX-03 · report rejected, not yet redone", "GR-01 · no report yet", "DZ-01 · no report yet"])
        // Reminders off: only never reported, no first reading and rejected machines.
        #expect(titles(nil) == titles(7))
        // A machine with a report waiting is never overdue.
        #expect(OverdueMachine.of(waiting, reminderDays: 1) == nil)
        #expect(OverdueMachine.of(five, reminderDays: 3)?.pill == "No report 5 days")
        #expect(OverdueMachine.of(never, reminderDays: 3)?.pill == "No report yet")
        #expect(OverdueMachine.of(opening, reminderDays: nil)?.pill == "No report yet")
        #expect(OverdueMachine.of(rejected, reminderDays: 3)?.pill == "Rejected")
    }

    @Test func reminderDaysDefaultToThreeAndNullSwitchesThemOff() throws {
        func policy(_ extra: String) throws -> CustomerHoursPolicyValues {
            let json = """
            {"policy_type":"CUSTOMER_HOURS","version_stamp":"v1","values":{"enabled":true,"walk_in_allowed":true,
             "transfer_requires_approval":true,"reason_code_required":false\(extra)}}
            """
            return try AssetaJSON.decoder().decode(EffectivePolicyDTO<CustomerHoursPolicyValues>.self, from: Data(json.utf8)).values
        }
        #expect(MachineReportStanding.reminderDays(nil) == 3)
        #expect(MachineReportStanding.reminderDays(try policy("")) == 3)
        #expect(MachineReportStanding.reminderDays(try policy(",\"machine_report_reminder_days\":5")) == 5)
        #expect(MachineReportStanding.reminderDays(try policy(",\"machine_report_reminder_days\":null")) == nil)
        #expect(MachineReportStanding.reminderDays(try policy(",\"machine_report_reminder_days\":\"x\"")) == 3)
        #expect(OwnerAPI.customerHoursPolicy().path.hasSuffix("/policies/CUSTOMER_HOURS/effective"))
    }

    @Test func decisionRequestsAndContractShapes() throws {
        let id = UUID()
        let approve = try OwnerAPI.approveMachineReport(id, note: "  ", idempotencyKey: UUID())
        #expect(approve.path.hasSuffix("/machine-reports/\(id.uuidString.lowercased())/approve"))
        let reject = try OwnerAPI.rejectMachineReport(id, reason: " Too idle ", idempotencyKey: UUID())
        let body = try JSONSerialization.jsonObject(with: try #require(reject.body)) as? [String: Any]
        #expect(body?["reason"] as? String == "Too idle")
        let queue = OwnerAPI.machineReports(pending: true)
        #expect(queue.queryItems.contains(URLQueryItem(name: "queue", value: "PENDING")))
        let credit = try OwnerAPI.activateCredit(id, hours: 40, reason: MachineReportOwnerTexts.creditApprovedReason,
                                                 idempotencyKey: UUID())
        #expect(credit.path.hasSuffix("/credit-activations"))
    }

    @Test func reportAndInvoiceDecodeFromTheServer() throws {
        let report = """
        {"id":"\(UUID())","report_number":"MR-2026-00007","machine_id":"\(UUID())","machine_code":"EX-01","capture_id":"\(UUID())",
         "start_source":"REPORT","start_ref":"\(UUID())","start_reading":"1210.0","start_at":"2026-11-12T14:30:00Z",
         "end_reading":"1510.0","end_at":"2026-11-16T04:40:00Z","hours":"300.0","customer_hours":"220.0",
         "non_productive_hours":"80.0","status":"SUBMITTED","corrects_id":null,"note":"Hose","source":"SYNC",
         "submitted_by":"\(UUID())","submitted_at":"2026-11-16T04:41:00Z","client_created_at":null,"decided_by":null,
         "decided_at":null,"decision_note":null,"policy_version":"v1","findings":[],
         "tracker":{"available":true,"tracker_hours":"296.0","meter_hours":"300.0","difference":"4.0"},
         "lines":[{"id":"\(UUID())","line_no":1,"kind":"CUSTOMER","customer_id":"\(UUID())","customer_name":"Pwani",
                   "reason_id":null,"hours":"120.0","note":null,"available_hours":"140.0","lots":[]}]}
        """
        let dto = try AssetaJSON.decoder().decode(MachineReportDTO.self, from: Data(report.utf8))
        #expect(dto.state == .submitted && dto.tracker?.trackerHours?.value == 296 && dto.lines[0].availableHours?.value == 140)
    }
}
