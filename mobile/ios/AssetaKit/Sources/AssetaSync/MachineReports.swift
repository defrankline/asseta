import AssetaCapture
import AssetaModel
import AssetaStore
import CryptoKit
import Foundation

// ADR-008 machine reports on the Supervisor app: the synced snapshots (reasons, my machines' status, customers'
// available hours, my reports), the offline rules of the 3-step form (reading → account for hours → review & submit)
// and the `MACHINE_REPORT` operation. The phone checks the sum and its cached available hours; the server decides.

public enum MachineReports {
    /// `sync_entity.entity_type` of each snapshot.
    public static let reasonType = "machine_report_reason"
    public static let stateType = "machine_report_state"
    public static let hoursType = "machine_report_hours"
    public static let reportType = "machine_report"
    public static let invoiceType = "open_credit_invoice"

    /// The stored key of a snapshot row: states by machine, available hours by customer (and machine under the MACHINE
    /// scope), everything else by `id`.
    static func key(type: String, _ object: JSONValue) -> UUID? {
        func uuid(_ field: String) -> UUID? { object[field]?.stringValue.flatMap(UUID.init(uuidString:)) }
        switch type {
        case stateType: return uuid("machine_id")
        case hoursType:
            guard let customer = uuid("customer_id") else { return nil }
            guard let machine = uuid("machine_id") else { return customer }
            return nameUUID("\(customer.uuidString.lowercased()):\(machine.uuidString.lowercased())")
        default: return uuid("id")
        }
    }

    static func nameUUID(_ text: String) -> UUID {
        var bytes = Array(Insecure.MD5.hash(data: Data(text.utf8)))
        bytes[6] = (bytes[6] & 0x0F) | 0x30
        bytes[8] = (bytes[8] & 0x3F) | 0x80
        return UUID(uuid: (bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
                           bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13], bytes[14], bytes[15]))
    }
}

// MARK: - Per-machine status

extension MachineReportStanding {
    public var label: String {
        switch self {
        case .opening: MachineReportTexts.pillOpening
        case .due: MachineReportTexts.pillDue
        case .awaitingApproval: MachineReportTexts.pillAwaiting
        case .upToDate: MachineReportTexts.pillUpToDate
        }
    }
}

// MARK: - The form as typed

/// One line of the split as typed: a customer (hours from what they bought) or a non-productive reason (note required).
public struct ReportLineDraft: Sendable, Equatable, Identifiable {
    public var id = UUID()
    public var kind: ReportLineKind
    public var customerID: UUID?
    public var customerName: String
    public var reasonID: UUID?
    public var reasonName: String
    public var hoursText: String
    public var note: String

    public init(kind: ReportLineKind, customerID: UUID? = nil, customerName: String = "", reasonID: UUID? = nil,
                reasonName: String = "", hoursText: String = "", note: String = "") {
        self.kind = kind
        self.customerID = customerID
        self.customerName = customerName
        self.reasonID = reasonID
        self.reasonName = reasonName
        self.hoursText = hoursText
        self.note = note
    }
}

/// The checked split, ready to queue.
public struct CheckedReport: Sendable, Equatable {
    public let difference: Decimal
    public let lines: [MachineReportLinePayload]
    public let note: String?
}

/// Offline rules of the machine report (same as Android `MachineReportRules`; the server re-checks everything).
public enum MachineReportRules {
    public static let maxNote = 1000

    /// The new reading as typed ("1510", "1,510.0" → 1510.0), with the machine's meter precision; nil when invalid.
    public static func reading(_ text: String, decimalPlaces: Int) -> Decimal? {
        let plain = text.trimmingCharacters(in: .whitespaces)
        // A grouping comma ("1,510.0") is not a decimal comma when a dot follows.
        let cleaned = plain.contains(".") ? plain.replacingOccurrences(of: ",", with: "") : plain
        guard case let .success(normalized) = CaptureValidator.normalizeReading(cleaned, decimalPlaces: decimalPlaces) else {
            return nil
        }
        return Decimal(string: normalized, locale: Locale(identifier: "en_US_POSIX"))
    }

    /// Hours to account for: new − previous (0 or less means nothing to report).
    public static func difference(previous: Decimal, reading: Decimal) -> Decimal { reading - previous }

    /// Line hours have at most 2 decimals (steps of 0.01), whatever the meter's precision.
    public static let lineDecimals = 2

    /// A line's hours as typed: more than 0, at most 2 decimals; nil otherwise (an invalid line).
    public static func hours(_ text: String) -> Decimal? {
        if case let .success(value) = DecimalInput.parse(text, maxFractionDigits: lineDecimals) { return value }
        return nil
    }

    /// Whether a line's hours are valid (shown on the line's hours field when not).
    public static func lineValid(_ line: ReportLineDraft) -> Bool { hours(line.hoursText) != nil }

    /// The hours accounted for by the valid lines (an invalid line counts for nothing).
    public static func accounted(_ lines: [ReportLineDraft]) -> Decimal {
        lines.reduce(Decimal(0)) { $0 + (hours($1.hoursText) ?? 0) }
    }

    /// "All hours accounted for": there are lines, every line's hours are valid and they add up to `difference`.
    public static func allAccounted(_ lines: [ReportLineDraft], difference: Decimal) -> Bool {
        !lines.isEmpty && lines.allSatisfy(lineValid) && accounted(lines) == difference
    }

    /// Hours a new line starts with: the hours still to account for, and for a customer line no more than the
    /// customer's `available` hours (min of the two). Empty when nothing is left. Same as Android `startHours`.
    public static func startHours(difference: Decimal, lines: [ReportLineDraft], available: Decimal? = nil) -> String {
        let left = difference - accounted(lines)
        let start = available.map { min($0, left) } ?? left
        return start > 0 ? AccountabilityRules.plain(start) : ""
    }

    /// What a customer has left after this report's valid lines for it ("after this").
    public static func customerAfter(_ lines: [ReportLineDraft], customerID: UUID?, available: Decimal) -> Decimal {
        available - accounted(lines.filter { $0.kind == .customer && $0.customerID == customerID })
    }

    /// Each customer's hours a report on `machineID` may draw on: the synced available hours (customer-wide, or of this
    /// machine under the MACHINE scope) less what this phone's unsent reports already hold for that customer.
    public static func available(_ rows: [AvailableHoursDTO], machineID: UUID,
                                 heldByUnsent: [UUID: Decimal] = [:]) -> [UUID: (name: String, hours: Decimal)] {
        var result: [UUID: (name: String, hours: Decimal)] = [:]
        for row in rows where row.machineID == nil || row.machineID == machineID {
            let current = result[row.customerID]?.hours ?? 0
            result[row.customerID] = (row.customerName ?? "", current + row.available.value)
        }
        for (customer, held) in heldByUnsent {
            if let row = result[customer] { result[customer] = (row.name, max(0, row.hours - held)) }
        }
        return result
    }

    /// Every problem with the split, in the order the form shows them (Android `MachineReportRules.check`); empty =
    /// Review may open. Every line has hours > 0 with at most 2 decimals; a customer appears once and gets no more than its
    /// `available` hours (``available(_:machineID:heldByUnsent:)``); a non-productive line has a note; the lines add up
    /// to `difference` exactly.
    public static func problems(_ lines: [ReportLineDraft], difference: Decimal,
                                available: [UUID: (name: String, hours: Decimal)]) -> [String] {
        typealias T = MachineReportTexts
        var m: [String] = []
        func add(_ s: String) { if !m.contains(s) { m.append(s) } }
        if lines.isEmpty { add(T.errNoLines) }
        if lines.count > maxLines { add(T.errTooManyLines) }
        let customers = lines.filter { $0.kind == .customer }.compactMap(\.customerID)
        if Set(customers).count != customers.count { add(T.errDuplicateCustomer) }
        for line in lines {
            let value = hours(line.hoursText)
            if value == nil { add(T.errLineHours) }
            switch line.kind {
            case .customer:
                let cap = line.customerID.flatMap { available[$0]?.hours } ?? 0
                if let value, value > cap { add(T.errOverCap(line.customerName, hoursText(cap))) }
            case .nonProductive:
                if line.note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { add(T.errNote(line.reasonName)) }
            }
        }
        let left = difference - accounted(lines)
        if left != 0 { add(T.leftToAccount(left)) }
        return m
    }

    /// The split when it is complete (sum == difference, every line valid and within its customer's cap).
    public static func check(_ lines: [ReportLineDraft], difference: Decimal,
                             available: [UUID: (name: String, hours: Decimal)], note: String) -> Result<CheckedReport, AccountabilityRules.Problems> {
        let problems = problems(lines, difference: difference, available: available)
        guard problems.isEmpty else { return .failure(AccountabilityRules.Problems(messages: problems)) }
        let payload = lines.map { line in
            MachineReportLinePayload(
                kind: line.kind, customerID: line.kind == .customer ? line.customerID : nil,
                reasonID: line.kind == .nonProductive ? line.reasonID : nil,
                hours: hours(line.hoursText) ?? 0,
                note: line.kind == .nonProductive ? AccountabilityRules.trimmed(line.note, max: maxNote) : nil)
        }
        return .success(CheckedReport(difference: difference, lines: payload, note: AccountabilityRules.trimmed(note, max: maxNote)))
    }

    /// Hours for display: grouping, 0–2 decimals, no trailing zeros ("300", "1,210.5", "1.15").
    public static func hoursText(_ value: Decimal) -> String { AccountabilityRules.hoursNumber(value, locale: Locale(identifier: "en_US")) }

    /// A reading for display with the meter's precision ("1,210.0").
    public static func readingText(_ value: Decimal, decimalPlaces: Int = 1, locale: Locale = Locale(identifier: "en_US")) -> String {
        value.formatted(.number.precision(.fractionLength(decimalPlaces)).locale(locale))
    }

    /// The split of a report into productive (customers) and non-productive hours.
    public static func productive(_ lines: [ReportLineDraft]) -> (customers: Decimal, nonProductive: Decimal) {
        lines.reduce((Decimal(0), Decimal(0))) { sum, line in
            let h = hours(line.hoursText) ?? 0
            return line.kind == .customer ? (sum.0 + h, sum.1) : (sum.0, sum.1 + h)
        }
    }
}

// MARK: - Reading the snapshots

extension FieldDirectory {
    private func rows<T: Decodable>(_ type: String, as: T.Type) -> [T] {
        ((try? store.syncState.entities(type: type, tenantID: tenantID)) ?? [])
            .compactMap { try? AssetaJSON.decoder().decode(T.self, from: Data($0.json.utf8)) }
    }

    /// Active non-productive reasons, by name.
    public func machineReportReasons() -> [MachineReportReasonDTO] {
        rows(MachineReports.reasonType, as: MachineReportReasonDTO.self).filter(\.isActive)
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    /// My machines' report status (open SUPERVISOR assignment), by machine code.
    public func machineReportStates() -> [MachineReportStatusDTO] {
        rows(MachineReports.stateType, as: MachineReportStatusDTO.self)
            .sorted { ($0.machineCode ?? "") < ($1.machineCode ?? "") }
    }

    /// Customers' hours a report may draw on (available > 0).
    public func machineReportHours() -> [AvailableHoursDTO] { rows(MachineReports.hoursType, as: AvailableHoursDTO.self) }

    /// My reports of the last 30 days and any still waiting, newest first.
    public func myMachineReports() -> [MachineReportDTO] {
        rows(MachineReports.reportType, as: MachineReportDTO.self).sorted { $0.submittedAt > $1.submittedAt }
    }

    /// Credit invoices with a balance, oldest due first; each balance less this phone's unsent payments of it.
    public func openCreditInvoices() -> [OpenCreditInvoice] {
        let unsent = unsentOperations(.creditInvoicePayment)
        var paidHere: [UUID: Decimal] = [:]
        for op in unsent {
            guard let payload = try? AssetaJSON.decoder().decode(CreditInvoicePaymentPayload.self, from: Data(op.payloadJSON.utf8))
            else { continue }
            paidHere[payload.invoiceID, default: 0] += payload.amount.value
        }
        return rows(MachineReports.invoiceType, as: CreditInvoiceDTO.self)
            .sorted { ($0.dueDate ?? "9999") < ($1.dueDate ?? "9999") }
            .map { OpenCreditInvoice(invoice: $0, unsentPaid: paidHere[$0.id] ?? 0) }
    }

    /// This user's operations of `type` not yet acknowledged by the server.
    public func unsentOperations(_ type: OperationType) -> [ClientOperation] {
        ((try? store.outbox.operations(tenantID: tenantID, owner: owner?.subject,
                                       statuses: [.pending, .sent, .quarantined])) ?? [])
            .filter { $0.opType == type.rawValue }
    }

    /// My unsent machine reports by machine.
    public func unsentMachineReports() -> [UUID: MachineReportPayload] {
        var result: [UUID: MachineReportPayload] = [:]
        for op in unsentOperations(.machineReport) {
            if let payload = try? AssetaJSON.decoder().decode(MachineReportPayload.self, from: Data(op.payloadJSON.utf8)) {
                result[payload.machineID] = payload
            }
        }
        return result
    }

    /// Customer hours my unsent reports hold (the server reserves them once they arrive).
    public func hoursHeldByUnsentReports(excluding machineID: UUID? = nil) -> [UUID: Decimal] {
        var held: [UUID: Decimal] = [:]
        for (machine, payload) in unsentMachineReports() where machine != machineID {
            for line in payload.lines where line.kind == .customer {
                if let customer = line.customerID { held[customer, default: 0] += line.hours.value }
            }
        }
        return held
    }
}

/// A credit invoice the phone may take a payment for.
public struct OpenCreditInvoice: Sendable, Equatable, Identifiable {
    public let invoice: CreditInvoiceDTO
    /// Payments recorded on this phone that the server has not received yet.
    public let unsentPaid: Decimal
    public var id: UUID { invoice.id }
    /// What is still owed after this phone's unsent payments.
    public var balance: Decimal { max(0, invoice.balance.value - unsentPaid) }
}

// MARK: - Queueing a report

extension FieldRecorder {
    /// Queues a machine report: the new reading as a DAILY `METER_CAPTURE` (photo, OCR, GPS, time, area name; the photo
    /// uploads first) and the `MACHINE_REPORT` naming it, which waits for it. Every report has its own new reading (a
    /// rejected report is final and never corrected). `opening`: the machine has no starting reading, so only the reading
    /// is submitted (no lines). The operation id is the report id.
    @discardableResult
    public func recordMachineReport(machineID: UUID, reading: NewReportReading?, report: CheckedReport?, opening: Bool = false,
                                    reportID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.machineReport)
        guard try store.syncState.entity(type: "machine", id: machineID, tenantID: tenantID) != nil
            || store.syncState.entity(type: MachineReports.stateType, id: machineID, tenantID: tenantID) != nil else {
            throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.machineMissing)
        }
        guard let reading else { throw FieldRecorderError.invalid(MachineReportTexts.errReading) }
        if !opening && (report?.lines.isEmpty ?? true) { throw FieldRecorderError.invalid(MachineReportTexts.errNothingToReport) }
        if try alreadySaved(.machineReport, clientID: reportID) { throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved) }
        return try store.database.transaction {
            let photoLocal = try reading.photo.map { try addAttachment($0, purpose: .meterPhoto) }
            let capturePayload = capturePayload(id: reading.captureID, machineID: machineID, kind: .daily, mode: reading.mode,
                                                reading: reading.reading, ocr: reading.ocr, gps: reading.gps,
                                                capturedAt: reading.capturedAt, snapshot: reading.snapshot,
                                                placeName: reading.placeName)
            let capture = try enqueue(.meterCapture, entityType: "meter_capture", entityID: reading.captureID,
                                      payload: capturePayload, dependsOn: [], attachments: photoLocal.map { [($0, .photo)] } ?? [],
                                      createdAt: reading.capturedAt)
            let payload = MachineReportPayload(machineID: machineID, captureID: reading.captureID,
                                               lines: opening ? [] : report?.lines ?? [], note: report?.note,
                                               opening: opening ? true : nil)
            return try enqueue(.machineReport, entityType: "machine_report", entityID: reportID, payload: payload,
                               dependsOn: [capture.id], createdAt: reading.capturedAt, operationID: reportID)
        }
    }
}

/// The meter capture taken for a report (step 1).
public struct NewReportReading: Sendable {
    public let captureID: UUID
    public let mode: CaptureMode
    /// Normalized decimal text with the meter's precision.
    public let reading: String
    public let ocr: MeterOCRResult?
    public let photo: StoredEvidence?
    public let gps: GpsPayload
    public let capturedAt: Date
    public let snapshot: MeterPolicySnapshot
    /// The phone's area label of the reading (reverse geocoded while online; nil otherwise), sent as `place_name`.
    public let placeName: String?

    public init(captureID: UUID, mode: CaptureMode, reading: String, ocr: MeterOCRResult?, photo: StoredEvidence?, gps: GpsPayload,
                capturedAt: Date, snapshot: MeterPolicySnapshot, placeName: String? = nil) {
        self.placeName = placeName
        self.captureID = captureID
        self.mode = mode
        self.reading = reading
        self.ocr = ocr
        self.photo = photo
        self.gps = gps
        self.capturedAt = capturedAt
        self.snapshot = snapshot
    }
}

// MARK: - Credit invoice payments

/// Offline checks of a credit invoice payment (the server re-checks balance and custody).
public enum CreditPaymentRules {
    /// Amount > 0 and at most the balance; bank and mobile money need a reference and the tenant's
    /// `field_noncash_payments`.
    public static func check(amountText: String, balance: Decimal, method: String, reference: String,
                             noncashAllowed: Bool) -> Result<(amount: Decimal, reference: String?), AccountabilityRules.Problems> {
        typealias T = MachineReportTexts
        var m: [String] = []
        let amount = AccountabilityRules.value(amountText, decimals: AccountabilityRules.moneyDecimals)
        if amount == nil { m.append(T.payErrAmount) }
        if let amount, amount > balance { m.append(T.payErrOverBalance(AccountabilityRules.plain(balance))) }
        let ref = AccountabilityRules.trimmed(reference, max: AccountabilityRules.maxReference)
        if method != "CASH" {
            if !noncashAllowed { m.append(FieldAccountabilityTexts.hoursErrNoncashOff) }
            if ref == nil { m.append(FieldAccountabilityTexts.hoursErrReference) }
        }
        guard m.isEmpty, let amount else { return .failure(AccountabilityRules.Problems(messages: m)) }
        return .success((amount, method == "CASH" ? nil : ref))
    }
}

extension FieldRecorder {
    /// Queues a `CREDIT_INVOICE_PAYMENT` (part or full payment). Cash goes into the recorder's custody (or
    /// `cashHolderID`'s); bank / mobile money stay claimed until verified. The operation id is the payment's client id.
    @discardableResult
    public func recordCreditInvoicePayment(_ invoice: OpenCreditInvoice, amountText: String, method: String, reference: String,
                                           note: String, evidence: [StoredEvidence], noncashAllowed: Bool, cashHolderID: UUID?,
                                           receivedAt: Date, clientID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.creditInvoicePayment)
        let checked: (amount: Decimal, reference: String?)
        switch CreditPaymentRules.check(amountText: amountText, balance: invoice.balance, method: method, reference: reference,
                                        noncashAllowed: noncashAllowed) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(value): checked = value
        }
        guard evidence.count <= AccountabilityRules.maxEvidence else {
            throw FieldRecorderError.invalid(FieldAccountabilityTexts.tooManyEvidence)
        }
        if try alreadySaved(.creditInvoicePayment, clientID: clientID) {
            throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved)
        }
        return try store.database.transaction {
            let locals = try evidence.map { try addAttachment($0, purpose: .paymentEvidence) }
            let payload = CreditInvoicePaymentPayload(
                invoiceID: invoice.invoice.id, amount: checked.amount, method: method, reference: checked.reference,
                receivedAt: receivedAt, staffMemberID: method == "CASH" ? cashHolderID : nil,
                note: AccountabilityRules.trimmed(note, max: AccountabilityRules.maxNote))
            return try enqueue(.creditInvoicePayment, entityType: "credit_invoice_payment", entityID: clientID, payload: payload,
                               dependsOn: [], attachments: locals.map { ($0, .evidenceUploads) }, createdAt: receivedAt,
                               operationID: clientID)
        }
    }
}
