import AssetaCapture
import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// ADR-008 on the Supervisor app: machine reports (sum == difference, per-customer caps, opening report, status),
/// credit on a sale, credit invoice payments, the FUEL switch and the snapshots/payloads (same rules as Android).
@Suite("ADR-008: machine reports and credit on the Supervisor app")
struct MachineReportTests {
    static let pwani = UUID(uuidString: "aaaaaaaa-0000-4000-8000-0000000000a1")!
    static let msasani = UUID(uuidString: "aaaaaaaa-0000-4000-8000-0000000000a2")!
    static let breakdown = UUID(uuidString: "aaaaaaaa-0000-4000-8000-0000000000b1")!
    static let caps: [UUID: (name: String, hours: Decimal)] = [pwani: ("Pwani Road Contractors", 140), msasani: ("Msasani Bay", 100)]
    static let all = AccountabilityTests.all + [SyncCapability.machineReport, SyncCapability.creditInvoicePayment,
                                                SyncCapability.hoursSaleCredit]

    static func customer(_ id: UUID, _ hours: String) -> ReportLineDraft {
        ReportLineDraft(kind: .customer, customerID: id, customerName: "C", hoursText: hours)
    }

    static func idle(_ hours: String, note: String = "Hydraulic hose replaced on site") -> ReportLineDraft {
        ReportLineDraft(kind: .nonProductive, reasonID: breakdown, reasonName: "Breakdown / repair", hoursText: hours, note: note)
    }

    // MARK: - Rules

    @Test func readingDifferenceAndParsing() {
        #expect(MachineReportRules.reading("1,510.0", decimalPlaces: 1) == Decimal(string: "1510.0"))
        #expect(MachineReportRules.reading("1510", decimalPlaces: 1) == 1510)
        #expect(MachineReportRules.reading("1510.05", decimalPlaces: 1) == nil)
        #expect(MachineReportRules.reading("", decimalPlaces: 1) == nil)
        #expect(MachineReportRules.difference(previous: 1210, reading: 1510) == 300)
    }

    @Test func reviewOnlyWhenTheSumEqualsTheDifference() {
        var lines = [Self.customer(Self.pwani, "120"), Self.customer(Self.msasani, "100"), Self.idle("40"), Self.idle("25")]
        lines[3].reasonID = UUID() // another reason
        let short = MachineReportRules.problems(lines, difference: 300, available: Self.caps)
        #expect(short == [MachineReportTexts.stillToAccount("15")])
        #expect(MachineReportRules.accounted(lines) == 285)
        lines.append(Self.idle("15"))
        #expect(MachineReportRules.problems(lines, difference: 300, available: Self.caps).isEmpty)
        lines.append(Self.idle("1"))
        #expect(MachineReportRules.problems(lines, difference: 300, available: Self.caps)
            == [MachineReportTexts.overAccounted("1")])
        guard case let .success(checked) = MachineReportRules.check(Array(lines.dropLast()), difference: 300,
                                                                    available: Self.caps, note: "  Hose failure  ") else {
            Issue.record("valid split refused"); return
        }
        #expect(checked.lines.count == 5 && checked.note == "Hose failure")
        #expect(checked.lines[0].kind == .customer && checked.lines[0].reasonID == nil && checked.lines[0].note == nil)
        #expect(checked.lines[2].kind == .nonProductive && checked.lines[2].customerID == nil)
    }

    @Test func eachCustomerIsCappedByTheirAvailableHours() {
        let lines = [Self.customer(Self.pwani, "150"), Self.idle("150")]
        let problems = MachineReportRules.problems(lines, difference: 300, available: Self.caps)
        #expect(problems == [MachineReportTexts.errOverCap("C", "140")])
        // Unknown customer (no usable hours) is capped at 0.
        let stranger = MachineReportRules.problems([Self.customer(UUID(), "10")], difference: 10, available: Self.caps)
        #expect(stranger.count == 1 && stranger[0].contains("0 h available"))
        // A customer twice is refused.
        let twice = MachineReportRules.problems([Self.customer(Self.pwani, "5"), Self.customer(Self.pwani, "5")], difference: 10,
                                                available: Self.caps)
        #expect(twice.contains(MachineReportTexts.errDuplicateCustomer))
    }

    @Test func linesTakeHundredthsAndNonProductiveNeedsANote() {
        let line = Self.idle("2.555", note: "  ")
        let problems = MachineReportRules.problems([line], difference: Decimal(string: "2.5")!, available: [:])
        #expect(problems == ["Enter the hours (more than 0, at most 2 decimals).", "Say what happened for “Breakdown / repair”.",
                             "2.5 h still to account for"])
        #expect(MachineReportTexts.errLineHours == "Enter the hours (more than 0, at most 2 decimals).")
        #expect(MachineReportRules.problems([], difference: 10, available: [:])
            == ["Add a customer or a non-productive line.", "10 h still to account for"])
        let many = Array(repeating: Self.idle("1"), count: 51)
        #expect(MachineReportRules.problems(many, difference: 51, available: [:]) == ["At most 50 lines per report."])
    }

    /// Line hours take up to 2 decimals whatever the meter shows (a 1-decimal meter's 9.0 h split 7.85 + 1.15).
    @Test func lineHoursAcceptTwoDecimalsWhateverTheMeter() {
        #expect(MachineReportRules.hours("1.15") == Decimal(string: "1.15"))
        #expect(MachineReportRules.hours("1,15") == Decimal(string: "1.15"))
        #expect(MachineReportRules.hours("0.01") == Decimal(string: "0.01"))
        #expect(MachineReportRules.hours("1.155") == nil)
        #expect(MachineReportRules.hours("0") == nil && MachineReportRules.hours("0.00") == nil)
        #expect(MachineReportRules.hours("-1") == nil && MachineReportRules.hours("abc") == nil && MachineReportRules.hours("") == nil)
        let lines = [Self.customer(Self.pwani, "7.85"), Self.idle("1.15")]
        #expect(MachineReportRules.problems(lines, difference: 9, available: Self.caps).isEmpty)
        #expect(MachineReportRules.allAccounted(lines, difference: 9))
        guard case let .success(checked) = MachineReportRules.check(lines, difference: 9, available: Self.caps, note: "") else {
            Issue.record("hundredths refused"); return
        }
        #expect(checked.lines.map(\.hours.value) == [Decimal(string: "7.85")!, Decimal(string: "1.15")!])
        #expect(MachineReportRules.hoursText(Decimal(string: "1.15")!) == "1.15")
        // The sum must still be exact.
        #expect(MachineReportRules.problems([Self.customer(Self.pwani, "7.84"), Self.idle("1.15")], difference: 9,
                                            available: Self.caps) == ["0.01 h still to account for"])
    }

    /// The Android bug: an invalid line was counted as 0 and the header still said "All hours accounted for".
    @Test func anInvalidLineNeverCountsTowardsAccountedFor() {
        let bad = Self.idle("1.155")
        let lines = [Self.customer(Self.pwani, "9"), bad]
        #expect(!MachineReportRules.lineValid(bad) && MachineReportRules.lineValid(lines[0]))
        #expect(MachineReportRules.accounted(lines) == 9)
        // The valid lines add up to 9 h, but one line is invalid: not "All hours accounted for".
        #expect(!MachineReportRules.allAccounted(lines, difference: 9))
        #expect(MachineReportRules.problems(lines, difference: 9, available: Self.caps)
            == [MachineReportTexts.errLineHours])
        #expect(MachineReportRules.allAccounted([Self.customer(Self.pwani, "9")], difference: 9))
        #expect(!MachineReportRules.allAccounted([], difference: 0))
        // The customer's "after this" ignores an invalid line of theirs.
        let customerLines = [Self.customer(Self.pwani, "7.85"), Self.customer(Self.pwani, "1.155")]
        #expect(MachineReportRules.customerAfter(customerLines, customerID: Self.pwani, available: 9) == Decimal(string: "1.15"))
        #expect(MachineReportRules.customerAfter(customerLines, customerID: Self.msasani, available: 5) == 5)
    }

    @Test func availableHoursFollowTheScopeAndUnsentReports() {
        let machine = UUID(), other = UUID()
        let rows = [AvailableHoursDTO(customerID: Self.pwani, customerName: "Pwani", remaining: 200, available: 140),
                    AvailableHoursDTO(customerID: Self.msasani, customerName: "Msasani", machineID: machine, remaining: 100, available: 100),
                    AvailableHoursDTO(customerID: Self.msasani, customerName: "Msasani", machineID: other, remaining: 50, available: 50)]
        let caps = MachineReportRules.available(rows, machineID: machine, heldByUnsent: [Self.pwani: 40])
        #expect(caps[Self.pwani]?.hours == 100)
        #expect(caps[Self.msasani]?.hours == 100) // only this machine's hours under the MACHINE scope
    }

    @Test func machineStatusFromTheSnapshot() {
        let id = UUID()
        func state(previous: Decimal? = 1210, days: Int? = 1, pending: UUID? = nil, rejected: UUID? = nil) -> MachineReportStatusDTO {
            MachineReportStatusDTO(machineID: id, previousReading: previous, daysSinceReport: days, pendingReportID: pending,
                                   rejectedReportID: rejected)
        }
        #expect(MachineReportStanding.of(state(), unsentReport: false, reminderDays: 3) == .upToDate)
        #expect(MachineReportStanding.of(state(days: 3), unsentReport: false, reminderDays: 3) == .due)
        #expect(MachineReportStanding.of(state(days: 30), unsentReport: false, reminderDays: nil) == .upToDate)
        #expect(MachineReportStanding.of(state(days: nil), unsentReport: false, reminderDays: 3) == .due)
        #expect(MachineReportStanding.of(state(previous: nil), unsentReport: false, reminderDays: 3) == .opening)
        #expect(MachineReportStanding.of(state(pending: UUID()), unsentReport: false, reminderDays: 3) == .awaitingApproval(notSent: false))
        #expect(MachineReportStanding.of(state(), unsentReport: true, reminderDays: 3) == .awaitingApproval(notSent: true))
        // A rejected report is final: the machine is due again (even when reported yesterday), or needs its first
        // reading when the rejected report was the opening one.
        #expect(MachineReportStanding.of(state(rejected: UUID()), unsentReport: false, reminderDays: 3) == .due)
        #expect(MachineReportStanding.of(state(days: 0, rejected: UUID()), unsentReport: false, reminderDays: nil) == .due)
        #expect(MachineReportStanding.of(state(previous: nil, rejected: UUID()), unsentReport: false, reminderDays: 3) == .opening)
        // A new report already waiting wins over the rejection.
        #expect(MachineReportStanding.of(state(pending: UUID(), rejected: UUID()), unsentReport: false, reminderDays: 3)
            == .awaitingApproval(notSent: false))
        #expect(MachineReportStanding.due.needsReport && MachineReportStanding.opening.needsReport)
        #expect(!MachineReportStanding.upToDate.needsReport)
        // The Supervisor's reminder days: a policy that failed to load counts as 3; an explicit null switches them off.
        #expect(MachineReportStanding.reminderDays(nil) == 3)
        let off = CustomerHoursPolicyValues(enabled: true, walkInAllowed: true, transferRequiresApproval: true,
                                            machineReportReminderDays: nil)
        #expect(MachineReportStanding.reminderDays(off) == nil)
        #expect(MachineReportStanding.of(state(days: 30), unsentReport: false,
                                         reminderDays: MachineReportStanding.reminderDays(off)) == .upToDate)
        #expect(MachineReportStanding.of(state(days: 3), unsentReport: false,
                                         reminderDays: MachineReportStanding.reminderDays(nil)) == .due)
    }

    @Test func aRejectedReportIsFinal() {
        #expect(MachineReportTexts.rejected("Wrong customer") == "Rejected: Wrong customer. Send a new report for this machine.")
        #expect(MachineReportTexts.rejected("  ") == "Rejected. Send a new report for this machine.")
        #expect(MachineReportTexts.rejected(nil) == "Rejected. Send a new report for this machine.")
        #expect(MachineReportTexts.conflict("CORRECTION_NOT_ALLOWED")
            == "A rejected report can't be corrected; send a new report with a new reading.")
        #expect(MachineReportTexts.conflict("CAPTURE_ALREADY_USED") == "This reading was already used in another report. Take a new reading.")
        #expect(MachineReportTexts.conflict("HOURS_PRECISION") == "The hours have more than 2 decimals.")
    }

    // MARK: - Gating

    @Test func creditIsOfferedOnlyWithCapabilityPolicyOrPermissionAndNeverToWalkIns() {
        let policyOn = CustomerHoursPolicyValues(enabled: true, walkInAllowed: true, transferRequiresApproval: true,
                                                 fieldNoncashPayments: true, fieldCreditSales: true)
        let policyOff = CustomerHoursPolicyValues(enabled: true, walkInAllowed: true, transferRequiresApproval: true,
                                                  fieldNoncashPayments: true)
        let caps = Set(Self.all)
        let field = FieldAccess(capabilities: caps, permissions: AccountabilityTests.permissions, hours: policyOn)
        #expect(field.creditSales)
        #expect(field.saleMethods(walkIn: false) == ["CASH", "BANK", "MOBILE_MONEY", "CREDIT"])
        #expect(field.saleMethods(walkIn: true) == ["CASH", "BANK", "MOBILE_MONEY"])
        #expect(!FieldAccess(capabilities: caps, permissions: AccountabilityTests.permissions, hours: policyOff).creditSales)
        let office = AccountabilityTests.permissions.union([MachineReportPermission.creditActivate])
        #expect(FieldAccess(capabilities: caps, permissions: office, hours: policyOff).creditSales)
        let oldServer = Set(AccountabilityTests.all)
        #expect(!FieldAccess(capabilities: oldServer, permissions: office, hours: policyOn).creditSales)
    }

    @Test func fuelIsHiddenWhenSwitchedOffAndReportsNeedTheirPermission() {
        let on = FieldAccess(capabilities: Set(Self.all), permissions: [MachineReportPermission.submit])
        let off = FieldAccess(capabilities: Set(Self.all), permissions: [], disabledCapabilities: [TenantCapability.fuel])
        #expect(on.fuelOn && !off.fuelOn)
        #expect(on.machineReport && !off.machineReport)
        #expect(!FieldAccess(capabilities: Set(AccountabilityTests.all), permissions: [MachineReportPermission.submit]).machineReport)
        let payer = FieldAccess(capabilities: Set(Self.all), permissions: [MachineReportPermission.invoicePayment],
                                hours: AccountabilityTests.hoursOn)
        #expect(payer.invoicePayment)
        let hoursOff = FieldAccess(capabilities: Set(Self.all), permissions: [MachineReportPermission.invoicePayment],
                                   hours: AccountabilityTests.hoursOn, disabledCapabilities: [TenantCapability.customerHours])
        #expect(!hoursOff.invoicePayment)
    }

    @Test func policyKeysDecodeWithDefaults() throws {
        let json = #"{"enabled":true,"walk_in_allowed":false,"transfer_requires_approval":true,"reason_code_required":false,"field_credit_sales":true,"machine_report_reminder_days":null}"#
        let values = try AssetaJSON.decoder().decode(CustomerHoursPolicyValues.self, from: Data(json.utf8))
        #expect(values.fieldCreditSales && values.machineReportReminderDays == nil)
        let older = #"{"enabled":true,"walk_in_allowed":false,"transfer_requires_approval":true,"reason_code_required":false}"#
        let old = try AssetaJSON.decoder().decode(CustomerHoursPolicyValues.self, from: Data(older.utf8))
        #expect(!old.fieldCreditSales && old.machineReportReminderDays == 3)
        // visit_gap_warning_hours: absent = 24, null = never flag, a number as set.
        #expect(old.visitGapWarningHours == 24 && values.visitGapWarningHours == 24)
        let gap = #"{"enabled":true,"walk_in_allowed":false,"transfer_requires_approval":true,"reason_code_required":false,"visit_gap_warning_hours":48}"#
        #expect(try AssetaJSON.decoder().decode(CustomerHoursPolicyValues.self, from: Data(gap.utf8)).visitGapWarningHours == 48)
        let noFlag = #"{"enabled":true,"walk_in_allowed":false,"transfer_requires_approval":true,"reason_code_required":false,"visit_gap_warning_hours":null}"#
        #expect(try AssetaJSON.decoder().decode(CustomerHoursPolicyValues.self, from: Data(noFlag.utf8)).visitGapWarningHours == nil)
    }

    // MARK: - Sale with a CREDIT line

    @Test func creditLineRules() {
        var d = HoursSaleDraft()
        d.customerID = Self.pwani
        d.machineID = UUID()
        d.hoursText = "20"
        d.payments = [PaymentLine(method: "CASH", amountText: "1000000"), PaymentLine(method: "CREDIT", amountText: "900000")]
        guard case let .success(v) = AccountabilityRules.hoursSale(d, walkInAllowed: true, creditAllowed: true) else {
            Issue.record("credit refused"); return
        }
        #expect(v.payments.map(\.method) == ["CASH", "CREDIT"] && v.payments[1].reference == nil)
        guard case let .failure(off) = AccountabilityRules.hoursSale(d, walkInAllowed: true, creditAllowed: false) else {
            Issue.record("credit accepted while off"); return
        }
        #expect(off.messages.contains(MachineReportTexts.saleErrCreditOff))
        var walkIn = d
        walkIn.walkIn = true
        walkIn.walkInName = "Asha"
        guard case let .failure(w) = AccountabilityRules.hoursSale(walkIn, walkInAllowed: true, creditAllowed: true) else {
            Issue.record("walk-in credit accepted"); return
        }
        #expect(w.messages.contains(MachineReportTexts.saleErrCreditWalkIn))
        var twice = d
        twice.payments.append(PaymentLine(method: "CREDIT", amountText: "1"))
        guard case let .failure(t) = AccountabilityRules.hoursSale(twice, walkInAllowed: true, creditAllowed: true) else {
            Issue.record("two credit lines accepted"); return
        }
        #expect(t.messages.contains(MachineReportTexts.saleErrCreditTwice))
        #expect(!AccountabilityRules.referenceMissing(PaymentLine(method: "CREDIT")))
    }

    @Test func creditSaleQueuesAmountOnlyLine() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.all)
        try h.store.syncState.upsert([StoredEntity(entityType: "customer", id: Self.pwani, revision: 1, version: 1,
                                                   json: #"{"id":"\#(Self.pwani.uuidString.lowercased())","name":"Pwani","code":"C1","is_active":true}"#)],
                                     tenantID: SyncFixtures.tenant)
        var d = HoursSaleDraft()
        d.customerID = Self.pwani
        d.machineID = SyncFixtures.machineID
        d.hoursText = "10"
        d.payments = [PaymentLine(method: "CASH", amountText: "500"), PaymentLine(method: "CREDIT", amountText: "300")]
        try h.store.syncState.upsert([StoredEntity(entityType: "machine", id: SyncFixtures.machineID, revision: 1, version: 1,
                                                   json: try JSONValue.encode(["id": SyncFixtures.machineID.uuidString.lowercased(),
                                                                               "asset_code": "EX-07", "name": "Excavator"]).jsonString())],
                                     tenantID: SyncFixtures.tenant)
        let op = try h.recorder.recordHoursSale(d, walkInAllowed: true, cashHolderID: nil, evidence: [], receivedAt: h.clock.wallNow,
                                                creditAllowed: true)
        let payload = try JSONValue.parse(op.payloadJSON)
        guard case let .array(parts)? = payload["payments"] else { Issue.record("no payments"); return }
        #expect(parts[1]["method"]?.stringValue == "CREDIT" && parts[1]["amount"]?.stringValue == "300")
        #expect(parts[1]["received_at"] == nil && parts[0]["received_at"] != nil)
        #expect(payload["job"] == nil)
    }

    // MARK: - Offline report

    static func reading(_ h: SyncHarness, _ value: String = "1510.0", place: String? = nil) throws -> NewReportReading {
        let photo = try h.evidence.store(Data((0..<2000).map { UInt8($0 % 251) }), fileExtension: "jpg", contentType: "image/jpeg")
        return NewReportReading(captureID: UUID(), mode: .automatic, reading: value,
                                ocr: MeterOCRResult(value: value, confidence: 0.97, rawText: value, engine: "test", note: ""),
                                photo: photo, gps: .fix(latitude: -6.8, longitude: 39.28, accuracyM: 6, capturedAt: h.clock.wallNow),
                                capturedAt: h.clock.wallNow, snapshot: SyncFixtures.meterSnapshot, placeName: place)
    }

    @Test func reportQueuesTheReadingThenTheReportDependingOnIt() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.all)
        try h.store.syncState.upsert([StoredEntity(entityType: "machine", id: SyncFixtures.machineID, revision: 1, version: 1,
                                                   json: try JSONValue.encode(["id": SyncFixtures.machineID.uuidString.lowercased(),
                                                                               "asset_code": "EX-07", "name": "Excavator"]).jsonString())],
                                     tenantID: SyncFixtures.tenant)
        let lines = [Self.customer(Self.pwani, "120"), Self.customer(Self.msasani, "100"), Self.idle("80")]
        guard case let .success(checked) = MachineReportRules.check(lines, difference: 300, available: Self.caps,
                                                                    note: "") else { Issue.record("invalid"); return }
        let reading = try Self.reading(h, place: "  Mbezi Beach, Kinondoni, Dar es Salaam ")
        let reportID = UUID()
        let op = try h.recorder.recordMachineReport(machineID: SyncFixtures.machineID, reading: reading, report: checked,
                                                    reportID: reportID)
        #expect(op.id == reportID && op.opType == "MACHINE_REPORT")
        let all = try h.store.outbox.operations(tenantID: SyncFixtures.tenant, statuses: Set(ClientOperationStatus.allCases))
        let capture = try #require(all.first { $0.opType == "METER_CAPTURE" })
        #expect(op.dependencies == [capture.id])
        let capturePayload = try JSONValue.parse(capture.payloadJSON)
        #expect(capturePayload["kind"]?.stringValue == "DAILY" && capturePayload["job_id"] == nil)
        #expect(capturePayload["place_name"]?.stringValue == "Mbezi Beach, Kinondoni, Dar es Salaam")
        #expect(try h.store.attachments.attachments(operationID: capture.id).count == 1)
        let payload = try JSONValue.parse(op.payloadJSON)
        #expect(payload["capture_id"]?.stringValue == reading.captureID.uuidString.lowercased())
        #expect(payload["machine_id"]?.stringValue == SyncFixtures.machineID.uuidString.lowercased())
        #expect(payload["opening"] == nil && payload["corrects_report_id"] == nil && payload["note"] == nil)
        guard case let .array(sent)? = payload["lines"] else { Issue.record("no lines"); return }
        #expect(sent.count == 3 && sent[0]["kind"]?.stringValue == "CUSTOMER" && sent[0]["hours"]?.stringValue == "120")
        #expect(sent[2]["reason_id"]?.stringValue == Self.breakdown.uuidString.lowercased() && sent[2]["note"] != nil)
        // The unsent report holds the customers' hours and marks the machine as waiting.
        let directory = h.directoryView
        #expect(directory.unsentMachineReports()[SyncFixtures.machineID] != nil)
        #expect(directory.hoursHeldByUnsentReports()[Self.pwani] == 120)
        #expect(directory.hoursHeldByUnsentReports(excluding: SyncFixtures.machineID).isEmpty)
        // A second save of the same visit is refused.
        #expect(throws: FieldRecorderError.self) {
            try h.recorder.recordMachineReport(machineID: SyncFixtures.machineID, reading: reading, report: checked, reportID: reportID)
        }
    }

    @Test func openingReportSubmitsTheReadingOnly() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.all)
        try h.store.syncState.upsert([StoredEntity(entityType: "machine", id: SyncFixtures.machineID, revision: 1, version: 1,
                                                   json: try JSONValue.encode(["id": SyncFixtures.machineID.uuidString.lowercased(),
                                                                               "asset_code": "EX-07", "name": "Excavator"]).jsonString())],
                                     tenantID: SyncFixtures.tenant)
        let op = try h.recorder.recordMachineReport(machineID: SyncFixtures.machineID, reading: try Self.reading(h), report: nil,
                                                    opening: true)
        let payload = try JSONValue.parse(op.payloadJSON)
        #expect(payload["opening"]?.boolValue == true)
        guard case let .array(lines)? = payload["lines"] else { Issue.record("no lines key"); return }
        #expect(lines.isEmpty)
        // Without the opening flag a report needs its lines.
        #expect(throws: FieldRecorderError.self) {
            try h.recorder.recordMachineReport(machineID: SyncFixtures.machineID, reading: try Self.reading(h), report: nil)
        }
    }

    @Test func aReportAlwaysNeedsItsOwnNewReadingAndAPlaceIsOptional() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.all)
        try h.store.syncState.upsert([StoredEntity(entityType: "machine", id: SyncFixtures.machineID, revision: 1, version: 1,
                                                   json: try JSONValue.encode(["id": SyncFixtures.machineID.uuidString.lowercased(),
                                                                               "asset_code": "EX-07", "name": "Excavator"]).jsonString())],
                                     tenantID: SyncFixtures.tenant)
        guard case let .success(checked) = MachineReportRules.check([Self.idle("10")], difference: 10,
                                                                    available: [:], note: "") else { Issue.record("invalid"); return }
        // No reading: refused (a rejected report's reading is never reused).
        #expect(throws: FieldRecorderError.self) {
            try h.recorder.recordMachineReport(machineID: SyncFixtures.machineID, reading: nil, report: checked)
        }
        // Offline / no geocoder result: the capture goes without a place, never delayed.
        let op = try h.recorder.recordMachineReport(machineID: SyncFixtures.machineID, reading: try Self.reading(h), report: checked)
        let all = try h.store.outbox.operations(tenantID: SyncFixtures.tenant, statuses: Set(ClientOperationStatus.allCases))
        let capture = try #require(all.first { $0.opType == "METER_CAPTURE" })
        #expect(op.dependencies == [capture.id])
        #expect(try JSONValue.parse(capture.payloadJSON)["place_name"] == nil)
        #expect(try JSONValue.parse(op.payloadJSON)["corrects_report_id"] == nil)
    }

    @Test func aServerWithoutReportsRefusesTheReport() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, AccountabilityTests.all)
        #expect(throws: FieldRecorderError.self) {
            try h.recorder.recordMachineReport(machineID: SyncFixtures.machineID, reading: try Self.reading(h), report: nil, opening: true)
        }
    }

    // MARK: - Snapshots

    static func state(_ machine: UUID) -> [String: Any] {
        ["machine_id": machine.uuidString.lowercased(), "machine_code": "EX-01", "machine_name": "CAT 320D2",
         "meter_decimal_places": 1, "previous_reading": "1210.0", "previous_at": "2026-11-12T14:30:00Z", "previous_source": "REPORT",
         "last_approved_reading": "1210.0", "last_approved_at": "2026-11-12T14:30:00Z", "last_report_at": "2026-11-12T14:30:00Z",
         "days_since_report": 4, "pending_report_id": NSNull(), "pending_report_number": NSNull(), "rejected_report_id": NSNull()]
    }

    @Test func snapshotsReplaceTheLocalSetsAndClearWithoutTheCapability() async throws {
        let h = try SyncHarness()
        let machine = UUID(), invoice = UUID()
        h.server.mutate {
            $0.capabilities = Self.all
            $0.extraData = [
                "machine_report_reasons": [["id": Self.breakdown.uuidString.lowercased(), "code": "BREAKDOWN", "name": "Breakdown / repair",
                                            "description": NSNull(), "is_active": true, "version": 1]],
                "machine_report_states": [Self.state(machine)],
                "machine_report_hours": [["customer_id": Self.pwani.uuidString.lowercased(), "customer_name": "Pwani",
                                          "machine_id": NSNull(), "remaining": "140", "reserved": "0", "available": "140"],
                                         ["customer_id": Self.msasani.uuidString.lowercased(), "customer_name": "Msasani",
                                          "machine_id": machine.uuidString.lowercased(), "remaining": "100", "reserved": "0",
                                          "available": "100"]],
                "open_credit_invoices": [["id": invoice.uuidString.lowercased(), "invoice_number": "CI-2026-00042",
                                          "purchase_id": UUID().uuidString.lowercased(), "customer_id": Self.msasani.uuidString.lowercased(),
                                          "customer_name": "Msasani", "machine_id": machine.uuidString.lowercased(), "currency": "TZS",
                                          "hours": "40", "unit_price": "95000", "amount": "3800000", "paid": "1800000",
                                          "paid_verified": "0", "balance": "2000000", "payment_terms_days": 14,
                                          "issued_at": "2026-11-15T12:00:00Z", "due_date": "2026-11-30", "status": "PART_PAID",
                                          "overdue": false, "days_overdue": 0, "created_by": NSNull()]],
            ]
        }
        let engine = h.engine()
        _ = try await engine.sync()
        let d = h.directoryView
        #expect(d.machineReportReasons().map(\.name) == ["Breakdown / repair"])
        #expect(d.machineReportStates().first?.previousReading?.value == 1210 && d.machineReportStates().first?.daysSinceReport == 4)
        #expect(d.machineReportHours().count == 2)
        let open = d.openCreditInvoices()
        #expect(open.count == 1 && open[0].balance == 2_000_000 && open[0].invoice.dueDate == "2026-11-30")
        h.server.mutate { $0.capabilities = AccountabilityTests.all }
        _ = try await engine.sync(force: true)
        #expect(d.machineReportStates().isEmpty && d.openCreditInvoices().isEmpty && d.machineReportReasons().isEmpty)
    }

    // MARK: - Credit invoice payments

    static func openInvoice(balance: Decimal = 2_000_000) -> OpenCreditInvoice {
        OpenCreditInvoice(invoice: CreditInvoiceDTO(id: UUID(), invoiceNumber: "CI-2026-00042", customerID: msasani,
                                                    customerName: "Msasani", amount: 3_800_000, paid: 3_800_000 - balance,
                                                    dueDate: "2026-11-30", status: "PART_PAID"), unsentPaid: 0)
    }

    @Test func invoicePaymentRules() {
        guard case let .success(cash) = CreditPaymentRules.check(amountText: "850000", balance: 2_000_000, method: "CASH",
                                                                 reference: "x", noncashAllowed: false) else {
            Issue.record("refused"); return
        }
        #expect(cash.amount == 850_000 && cash.reference == nil)
        guard case let .failure(over) = CreditPaymentRules.check(amountText: "2000001", balance: 2_000_000, method: "CASH",
                                                                 reference: "", noncashAllowed: true) else {
            Issue.record("overpayment accepted"); return
        }
        #expect(over.messages == [MachineReportTexts.payErrOverBalance("2000000")])
        guard case let .failure(bank) = CreditPaymentRules.check(amountText: "10", balance: 100, method: "BANK", reference: " ",
                                                                 noncashAllowed: false) else {
            Issue.record("bank accepted"); return
        }
        #expect(bank.messages.count == 2)
    }

    @Test func invoicePaymentQueuesTheOperationAndLowersTheBalance() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.all)
        let invoice = Self.openInvoice()
        let clientID = UUID()
        let op = try h.recorder.recordCreditInvoicePayment(invoice, amountText: "850000", method: "MOBILE_MONEY", reference: "QK7H2LX9",
                                                           note: "", evidence: [], noncashAllowed: true, cashHolderID: UUID(),
                                                           receivedAt: h.clock.wallNow, clientID: clientID)
        #expect(op.id == clientID && op.opType == "CREDIT_INVOICE_PAYMENT")
        let payload = try JSONValue.parse(op.payloadJSON)
        #expect(payload["invoice_id"]?.stringValue == invoice.invoice.id.uuidString.lowercased())
        #expect(payload["amount"]?.stringValue == "850000" && payload["method"]?.stringValue == "MOBILE_MONEY")
        #expect(payload["reference"]?.stringValue == "QK7H2LX9" && payload["staff_member_id"] == nil)
        guard case let .array(uploads)? = payload["evidence_upload_ids"] else { Issue.record("no uploads list"); return }
        #expect(uploads.isEmpty)
        // The same payment twice is refused.
        #expect(throws: FieldRecorderError.self) {
            try h.recorder.recordCreditInvoicePayment(invoice, amountText: "1", method: "CASH", reference: "", note: "", evidence: [],
                                                      noncashAllowed: true, cashHolderID: nil, receivedAt: h.clock.wallNow,
                                                      clientID: clientID)
        }
    }

    // MARK: - Figures

    @Test func salesByMethodAndRecentRows() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.all)
        _ = try h.recorder.recordCreditInvoicePayment(Self.openInvoice(), amountText: "100", method: "CASH", reference: "", note: "",
                                                      evidence: [], noncashAllowed: true, cashHolderID: nil,
                                                      receivedAt: h.clock.wallNow)
        let ops = try h.store.outbox.operations(tenantID: SyncFixtures.tenant, statuses: Set(ClientOperationStatus.allCases))
        let figures = FieldActivity.salesByMethod(ops, since: h.clock.wallNow.addingTimeInterval(-60))
        #expect(figures.cash == 100 && figures.total == 100)
        #expect(FieldActivity.salesByMethod(ops, since: h.clock.wallNow.addingTimeInterval(60)).total == 0)
        #expect(FieldActivity.productivePercent(customers: 220, nonProductive: 80) == 73)
        #expect(FieldActivity.productivePercent(customers: 0, nonProductive: 0) == nil)
        let report = MachineReportDTO(id: UUID(), reportNumber: "MR-1", machineID: UUID(), machineCode: "EX-01", startReading: 1210,
                                      startAt: Date(), endReading: 1510, endAt: Date(), status: .submitted, submittedAt: Date(),
                                      lines: [.init(lineNo: 1, kind: .customer, customerID: Self.pwani, hours: 220)])
        let hours = FieldActivity.reportHours([report], unsent: [], since: .distantPast)
        #expect(hours.customers == 220 && hours.nonProductive == 80)
        let recent = FieldActivity.recent(reports: [report], operations: ops, machineCode: { _ in "?" }, customerName: { _ in nil },
                                          money: { "\($0)" })
        #expect(recent.first?.title == MachineReportTexts.recentReport("EX-01", "300"))
        #expect(recent.first?.pill == MachineReportTexts.pillAwaiting)
    }
}
