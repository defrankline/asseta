import AssetaModel
@testable import AssetaOwnerKit
import Foundation
import Testing

@Suite("ADR-008 Owner side menu, Home, Approvals and report approval as on Android")
struct OwnerShellApprovalsParityTests {
    static let me = UUID()

    // MARK: Side menu

    @Test func menuGroupsFollowTheRoleWithAMoreGroup() {
        let boss = OwnerFeatures(permissions: [
            "tenant.fleet.read", "tenant.finance.read", "tenant.approval.read", "tenant.hours.read", "tenant.machine_report.read",
            "tenant.notification.read", "tenant.setup.read", "tenant.meter.read", "tenant.expense.read", "tenant.case.read",
        ])
        let groups = boss.menuGroups
        #expect(groups.count == 2 && groups[0].header == nil && groups[1].header == "More")
        #expect(groups[0].entries.map(\.label) == ["Home", "Approvals", "Customers & hours", "Machines", "Money", "Reports", "Notifications"])
        #expect(groups[1].entries.map(\.label) == ["Go-live checklist", "Dashboard", "Fleet map", "Alerts", "Meter exceptions",
                                                    "Field spend", "Cash with supervisors", "Investigations"])
        // Machine reports alone: Approvals, Machines and Reports; no money, customers or More group.
        let reader = OwnerFeatures(permissions: [MachineReportPermission.read])
        #expect(reader.menuGroups.map(\.entries) == [[.home, .approvals, .machines, .reports]])
        // Nothing: only Home.
        #expect(OwnerFeatures(permissions: []).menuGroups.map(\.entries) == [[.home]])
        // Customer hours switched off: no Customers & hours, Money only with finance.
        let off = OwnerFeatures(permissions: ["tenant.hours.read"], disabledCapabilities: [TenantCapability.customerHours])
        #expect(!off.shows(.customers) && !off.shows(.money) && !off.shows(.reports))
        // Tracking off: no Alerts in More.
        let noTracking = OwnerFeatures(permissions: ["tenant.fleet.read"], disabledCapabilities: [TenantCapability.tracking])
        #expect(noTracking.shows(.fleet) && !noTracking.shows(.alerts))
    }

    @Test func homeFiguresShowADashWhenMissing() {
        #expect(OwnerHomePresentation.cash(nil) == "—")
        #expect(OwnerHomePresentation.hoursSold(nil) == "—")
        #expect(OwnerHomePresentation.productive(nil) == "—")
        #expect(OwnerHomePresentation.productive([]) == "—")
        #expect(OwnerHomePresentation.hoursSold([]) == "0 h")
        let report = MachineReportOwnerTests.report()
        #expect(OwnerHomePresentation.productive([report, MachineReportOwnerTests.report(status: .rejected, customer: 0, idle: 50)]) == "73%")
        #expect(OwnerHomeTexts.bell(unread: 0) == "Notifications")
        #expect(OwnerHomeTexts.bell(unread: 3) == "Notifications, 3 unread")
        #expect(OwnerHomeTexts.bell(unread: 120) == "Notifications, 99+ unread")
        #expect(MachineReportOwnerTexts.nothingNeedsYou == "Nothing needs your attention right now.")
    }

    @Test func overdueRowsSayTheLastApprovedReading() {
        let read = MachineReportStatusDTO(machineID: UUID(), machineCode: "EX-02", previousReading: 1510, lastApprovedReading: 1510,
                                          daysSinceReport: 4)
        let never = MachineReportStatusDTO(machineID: UUID(), machineCode: "GR-01", previousReading: nil)
        let rows = AttentionRow.rows(pending: [], states: [read, never], reminderDays: 3)
        #expect(rows.map(\.detail) == ["Last approved reading 1,510 h", "No approved reading yet"])
    }

    // MARK: Approvals

    @Test func countsAndChips() {
        let counts = ApprovalCounts(reports: 2, credit: 1, expenses: 1, other: 3)
        #expect(counts.all == 7 && counts.waiting == "7 waiting" && counts.badge == "7")
        #expect(ApprovalFilter.allCases.map(counts.chip) == ["All 7", "Machine reports 2", "Credit 1", "Expenses 1"])
        #expect(ApprovalCounts().waiting == nil && ApprovalCounts().badge == nil)
        #expect(ApprovalCounts(other: 120).badge == "99+")
        #expect(ApprovalFilter.all.shows(.other) && !ApprovalFilter.credit.shows(.other) && ApprovalFilter.expenses.shows(.expense))
        #expect(OwnerFeatures(permissions: [MachineReportPermission.read]).approvalsScreen)
    }

    static func order(credit: String = "3800000", rate: String? = "95000", awaiting: String = "60", createdBy: UUID? = nil,
                      cancelled: Bool = false) throws -> HoursPurchaseDTO {
        let json = """
        {"id":"\(UUID())","purchase_number":"HP-7","client_id":null,"customer_id":"\(UUID())","customer_name":"Msasani Bay",
         "machine_id":"\(UUID())","hours":"60","currency":"TZS","amount":"5700000","status":"ACTIVE",
         "created_at":"2026-11-16T08:00:00Z"\(cancelled ? ",\"cancelled_at\":\"2026-11-16T09:00:00Z\"" : ""),
         "totals":{"purchased":"60","activated":"0","consumed":"0","remaining":"0","awaiting_activation":"\(awaiting)"},
         "credit_amount":"\(credit)","credit_invoice":{"id":"\(UUID())","invoice_number":"INV-0042","amount":"\(credit)",
         "paid":"0","balance":"\(credit)","due_date":"2026-11-30","status":"UNPAID","overdue":false}
         \(rate.map { ",\"effective_rate\":\"\($0)\"" } ?? "")\(createdBy.map { ",\"created_by\":\"\($0.uuidString.lowercased())\"" } ?? "")}
        """
        return try AssetaJSON.decoder().decode(HoursPurchaseDTO.self, from: Data(json.utf8))
    }

    @Test func creditSaleRows() throws {
        let p = try Self.order()
        let cancelled = try Self.order(cancelled: true), noCredit = try Self.order(credit: "0")
        let lowerRate = try Self.order(rate: "90000"), fewWaiting = try Self.order(awaiting: "20"), noRate = try Self.order(rate: nil)
        let mine = try Self.order(createdBy: Self.me)
        #expect(CreditSales.waiting(p) && !CreditSales.waiting(cancelled) && !CreditSales.waiting(noCredit))
        #expect(CreditSales.creditHours(p) == 40)
        #expect(CreditSales.creditHours(lowerRate) == Decimal(string: "42.22"))
        #expect(CreditSales.creditHours(fewWaiting) == 20)
        #expect(CreditSales.creditHours(noRate) == 60)
        #expect(CreditSales.title(p) == "Msasani Bay · 40 h on credit")
        #expect(CreditSales.detail(CreditSale(purchase: p, limitLeft: DecimalString(6_200_000)))
            == "Invoice INV-0042 · TZS 3,800,000 · limit left 6.2M")
        #expect(CreditSales.detail(CreditSale(purchase: p)) == "Invoice INV-0042 · TZS 3,800,000")
        #expect(CreditSales.recordedBy(mine, me: Self.me) && !CreditSales.recordedBy(p, me: Self.me))
        #expect(ApprovalsTexts.creditRefusal("CREDIT_LIMIT_EXCEEDED", fallback: "x") == "This would take the customer over their credit limit.")
        #expect(ApprovalsTexts.creditRefusal("OTHER", fallback: "x") == "x")
        #expect(OwnerAPI.customerCreditExposure(Self.me).path.hasSuffix("/customers/\(Self.me.uuidString.lowercased())/credit-exposure"))
    }

    @Test func expenseRows() throws {
        let request = """
        {"id":"\(UUID())","subject_type":"EXPENSE","subject_id":"\(Self.me.uuidString.lowercased())","amount":"185000","currency":"TZS",
         "reason":"Burst hose","policy_version":"v1","status":"PENDING","requested_by":null,"requested_at":"2026-11-16T08:00:00Z",
         "decided_by":null,"decided_at":null,"decision_note":null}
        """
        let a = try AssetaJSON.decoder().decode(ApprovalRequestDTO.self, from: Data(request.utf8))
        let expense = """
        {"id":"\(Self.me.uuidString.lowercased())","amount":"185000","currency":"TZS","description":"Hydraulic hose","status":"PENDING_APPROVAL",
         "incurred_at":"2026-11-16T07:00:00Z","paid_from":"COLLECTIONS","supplier":"Tabata Hydraulics",
         "receipt_attachment_ids":["\(UUID())"],"decision_note":null,"machine_id":null,"custodian_staff_id":null,
         "receipt_required":true,"control_flags":[],"petty_cash_fund_id":null}
        """
        let e = try AssetaJSON.decoder().decode(ExpenseDTO.self, from: Data(expense.utf8))
        #expect(ExpenseApprovals.expense(a, in: [e]) == e)
        #expect(ExpenseApprovals.title(a, e) == "Hydraulic hose · TZS 185,000")
        #expect(ExpenseApprovals.detail(a, e) == "receipt photo · Tabata Hydraulics · Burst hose")
        #expect(ExpenseApprovals.title(a, nil) == "Burst hose · TZS 185,000")
        #expect(ExpenseApprovals.detail(a, nil) == "Burst hose")
    }

    // MARK: Machine report approval

    @Test func reportRowsAndDetailLines() {
        let r = MachineReportOwnerTests.report()
        #expect(ReportPresentation.rowTitle(r) == "EX-01 · 300 h · Daudi Mollel")
        #expect(ReportPresentation.split(r) == "220 h Pwani · 80 h breakdown / repair")
        #expect(ReportPresentation.readings(r) == "1,210 → 1,510 h")
        #expect(ReportPresentation.readLine(r, capture: nil) == "300 h")
        #expect(ReportPresentation.readLine(r, capture: ReportCaptureDTO(reading: 1510, ocrValue: "1510.0")) == "300 h · read by phone 1510.0 ✓")
        #expect(ReportPresentation.readLine(r, capture: ReportCaptureDTO(reading: 1500, ocrValue: "1510.0"))
            == "300 h · read by phone 1510.0 · typed 1,500")
        #expect(ReportPresentation.readLine(r, capture: ReportCaptureDTO(reading: 1510, captureMode: "MANUAL")) == "300 h · typed by hand")
        #expect(ReportPresentation.gpsLine(nil) == nil)
        #expect(ReportPresentation.gpsLine(ReportCaptureDTO(reading: 1, latitude: -6.8, accuracyM: 6.4)) == "GPS: ±6 m")
        #expect(ReportPresentation.gpsLine(ReportCaptureDTO(reading: 1, latitude: -6.8)) == "GPS: position recorded")
        #expect(ReportPresentation.gpsLine(ReportCaptureDTO(reading: 1, gpsStatus: "NO_FIX")) == "GPS: no fix")
        #expect(ReportPresentation.beforeAfter(r.lines[0]) == "· 140 → 0 h left")
        #expect(ReportPresentation.quoted("  Hose ") == "“Hose”" && ReportPresentation.quoted(" ") == nil)
        #expect(ReportPresentation.tracker(r) == "No tracker data for this period.")
        #expect(ReportPresentation.cannotDecide(.ownReport) == "You submitted this report, so someone else must approve or reject it.")
        #expect(ReportPresentation.cannotDecide(.notPermitted) == "Only people allowed to approve machine reports can decide it.")
        #expect(ReportPresentation.cannotDecide(.allowed) == nil)
        #expect(ReportTexts.refusal("REPORT_NOT_PENDING", fallback: "x") == "This report was already decided by someone else. It has been refreshed.")
        #expect(ReportTexts.refusal(nil, fallback: "x") == "x")
        #expect(MachineReportApproval.rejectReasonValid(" ok ") && !MachineReportApproval.rejectReasonValid("   "))
    }

    @Test func splitNamesCountsAndTotals() throws {
        let json = """
        {"id":"\(UUID())","report_number":"MR-2026-00009","machine_id":"\(UUID())","capture_id":"\(UUID())",
         "start_source":"REPORT","start_reading":"10","start_at":"2026-11-12T14:30:00Z","end_reading":"52","end_at":"2026-11-16T04:40:00Z",
         "hours":"42","customer_hours":"38","non_productive_hours":"4","status":"SUBMITTED","submitted_at":"2026-11-16T04:41:00Z",
         "lines":[]}
        """
        let bare = try AssetaJSON.decoder().decode(MachineReportDTO.self, from: Data(json.utf8))
        #expect(ReportPresentation.split(bare) == "38 h to customers · 4 h non-productive")
        #expect(ReportPresentation.rowTitle(bare) == "MR-2026-00009 · 42 h")
    }
}
