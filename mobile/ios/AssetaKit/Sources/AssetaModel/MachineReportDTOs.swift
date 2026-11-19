import Foundation

// ADR-008: machine reports replace jobs. A supervisor accounts for every engine hour of the machines assigned to them
// (from the last approved reading to a new one, split across customers and non-productive reasons); credit invoices
// are paid in parts in the field. Shapes follow `contracts/openapi.json` and `docs/api-machine-reports.md`.

extension SyncCapability {
    /// Operation `MACHINE_REPORT`; `SyncData.machine_report_*` and `my_machine_reports`.
    public static let machineReport = "OP_MACHINE_REPORT"
    /// Operation `CREDIT_INVOICE_PAYMENT`; `SyncData.open_credit_invoices`.
    public static let creditInvoicePayment = "OP_CREDIT_INVOICE_PAYMENT"
    /// `HOURS_PURCHASE` accepts a CREDIT payment line.
    public static let hoursSaleCredit = "OP_HOURS_SALE_CREDIT"
}

extension TenantCapability {
    /// Fuel capture (`EXPENSE_CAPTURE.fuel_enabled`); listed in `/me` `disabled_capabilities` when switched off.
    public static let fuel = "FUEL"
}

/// Machine report permissions (approval is by permission, never by role).
public enum MachineReportPermission {
    public static let submit = "tenant.machine_report.submit"
    public static let read = "tenant.machine_report.read"
    public static let approve = "tenant.machine_report.approve"
    /// Record payments of credit invoices.
    public static let invoicePayment = "tenant.hours.invoice_payment"
    /// Activate hours on credit (office); holders may always record a CREDIT line.
    public static let creditActivate = "tenant.hours.credit_activate"
}

/// `ReportLineKind`.
public enum ReportLineKind: String, Codable, Sendable, CaseIterable {
    case customer = "CUSTOMER", nonProductive = "NON_PRODUCTIVE"
}

/// `MachineReportStatus`.
public enum MachineReportState: String, Codable, Sendable, CaseIterable {
    case submitted = "SUBMITTED", approved = "APPROVED", rejected = "REJECTED"
}

/// `MachineReportReasonDto`: a non-productive reason of the tenant's list.
public struct MachineReportReasonDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let code: String
    public let name: String
    public let description: String?
    public let isActive: Bool
    public let version: Int?

    public init(id: UUID, code: String, name: String, description: String? = nil, isActive: Bool = true, version: Int? = 1) {
        self.id = id
        self.code = code
        self.name = name
        self.description = description
        self.isActive = isActive
        self.version = version
    }

    enum CodingKeys: String, CodingKey {
        case id, code, name, description, version, isActive = "is_active"
    }
}

/// `MachineReportStatusDto`: one of my machines and where its next report starts.
public struct MachineReportStatusDTO: Codable, Hashable, Sendable, Identifiable {
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let meterDecimalPlaces: Int
    /// Where a new report starts (last approved reading, baseline or reset); nil: no starting reading yet.
    public let previousReading: DecimalString?
    public let previousAt: Date?
    public let previousSource: String?
    public let lastApprovedReading: DecimalString?
    public let lastApprovedAt: Date?
    public let lastReportAt: Date?
    public let daysSinceReport: Int?
    public let pendingReportID: UUID?
    public let pendingReportNumber: String?
    public let rejectedReportID: UUID?
    /// The machine's last visit: the most recent reading that belongs to any of its reports (rejected ones included),
    /// by the reading's time; nil = never visited.
    public let lastVisit: VisitPoint?

    public var id: UUID { machineID }

    public init(machineID: UUID, machineCode: String? = nil, machineName: String? = nil, meterDecimalPlaces: Int = 1,
                previousReading: Decimal?, previousAt: Date? = nil, previousSource: String? = "REPORT",
                lastApprovedReading: Decimal? = nil, lastApprovedAt: Date? = nil, lastReportAt: Date? = nil,
                daysSinceReport: Int? = nil, pendingReportID: UUID? = nil, pendingReportNumber: String? = nil,
                rejectedReportID: UUID? = nil, lastVisit: VisitPoint? = nil) {
        self.lastVisit = lastVisit
        self.machineID = machineID
        self.machineCode = machineCode
        self.machineName = machineName
        self.meterDecimalPlaces = meterDecimalPlaces
        self.previousReading = previousReading.map(DecimalString.init)
        self.previousAt = previousAt
        self.previousSource = previousSource
        self.lastApprovedReading = lastApprovedReading.map(DecimalString.init)
        self.lastApprovedAt = lastApprovedAt
        self.lastReportAt = lastReportAt
        self.daysSinceReport = daysSinceReport
        self.pendingReportID = pendingReportID
        self.pendingReportNumber = pendingReportNumber
        self.rejectedReportID = rejectedReportID
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        machineID = try c.decode(UUID.self, forKey: .machineID)
        machineCode = try c.decodeIfPresent(String.self, forKey: .machineCode)
        machineName = try c.decodeIfPresent(String.self, forKey: .machineName)
        meterDecimalPlaces = try c.decodeIfPresent(Int.self, forKey: .meterDecimalPlaces) ?? 1
        previousReading = try c.decodeIfPresent(DecimalString.self, forKey: .previousReading)
        previousAt = try c.decodeIfPresent(Date.self, forKey: .previousAt)
        previousSource = try c.decodeIfPresent(String.self, forKey: .previousSource)
        lastApprovedReading = try c.decodeIfPresent(DecimalString.self, forKey: .lastApprovedReading)
        lastApprovedAt = try c.decodeIfPresent(Date.self, forKey: .lastApprovedAt)
        lastReportAt = try c.decodeIfPresent(Date.self, forKey: .lastReportAt)
        daysSinceReport = try c.decodeIfPresent(Int.self, forKey: .daysSinceReport)
        pendingReportID = try c.decodeIfPresent(UUID.self, forKey: .pendingReportID)
        pendingReportNumber = try c.decodeIfPresent(String.self, forKey: .pendingReportNumber)
        rejectedReportID = try c.decodeIfPresent(UUID.self, forKey: .rejectedReportID)
        lastVisit = try VisitPoint.decode(c, at: .lastVisitAt, lat: .lastVisitLat, lng: .lastVisitLng,
                                          accuracy: .lastVisitAccuracyM, place: .lastVisitPlace, site: .lastVisitSiteName)
    }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(machineID, forKey: .machineID)
        try c.encodeIfPresent(machineCode, forKey: .machineCode)
        try c.encodeIfPresent(machineName, forKey: .machineName)
        try c.encode(meterDecimalPlaces, forKey: .meterDecimalPlaces)
        try c.encodeIfPresent(previousReading, forKey: .previousReading)
        try c.encodeIfPresent(previousAt, forKey: .previousAt)
        try c.encodeIfPresent(previousSource, forKey: .previousSource)
        try c.encodeIfPresent(lastApprovedReading, forKey: .lastApprovedReading)
        try c.encodeIfPresent(lastApprovedAt, forKey: .lastApprovedAt)
        try c.encodeIfPresent(lastReportAt, forKey: .lastReportAt)
        try c.encodeIfPresent(daysSinceReport, forKey: .daysSinceReport)
        try c.encodeIfPresent(pendingReportID, forKey: .pendingReportID)
        try c.encodeIfPresent(pendingReportNumber, forKey: .pendingReportNumber)
        try c.encodeIfPresent(rejectedReportID, forKey: .rejectedReportID)
        try lastVisit?.encode(&c, at: .lastVisitAt, lat: .lastVisitLat, lng: .lastVisitLng, accuracy: .lastVisitAccuracyM,
                              place: .lastVisitPlace, site: .lastVisitSiteName)
    }

    enum CodingKeys: String, CodingKey {
        case lastVisitAt = "last_visit_at", lastVisitLat = "last_visit_lat", lastVisitLng = "last_visit_lng"
        case lastVisitAccuracyM = "last_visit_accuracy_m", lastVisitPlace = "last_visit_place"
        case lastVisitSiteName = "last_visit_site_name"
        case machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name"
        case meterDecimalPlaces = "meter_decimal_places", previousReading = "previous_reading", previousAt = "previous_at"
        case previousSource = "previous_source", lastApprovedReading = "last_approved_reading"
        case lastApprovedAt = "last_approved_at", lastReportAt = "last_report_at", daysSinceReport = "days_since_report"
        case pendingReportID = "pending_report_id", pendingReportNumber = "pending_report_number"
        case rejectedReportID = "rejected_report_id"
    }
}

/// `AvailableHoursDto`: a customer's hours a new report may draw on (activated − used − reserved by other reports).
public struct AvailableHoursDTO: Codable, Hashable, Sendable {
    public let customerID: UUID
    public let customerName: String?
    /// Set when the tenant draws reports only on the machine's hours (scope MACHINE).
    public let machineID: UUID?
    public let remaining: DecimalString
    public let reserved: DecimalString
    public let available: DecimalString

    public init(customerID: UUID, customerName: String?, machineID: UUID? = nil, remaining: Decimal, reserved: Decimal = 0,
                available: Decimal) {
        self.customerID = customerID
        self.customerName = customerName
        self.machineID = machineID
        self.remaining = DecimalString(remaining)
        self.reserved = DecimalString(reserved)
        self.available = DecimalString(available)
    }

    enum CodingKeys: String, CodingKey {
        case remaining, reserved, available
        case customerID = "customer_id", customerName = "customer_name", machineID = "machine_id"
    }
}

/// `MachineReportDto`.
public struct MachineReportDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let reportNumber: String
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let captureID: UUID
    /// The machine's first reading (start == end, 0 hours, no lines, `start_source` OPENING).
    public let opening: Bool
    /// `REPORT`, `BASELINE`, `RESET` or `OPENING`.
    public let startSource: String
    public let startReading: DecimalString
    public let startAt: Date
    public let endReading: DecimalString
    public let endAt: Date
    public let hours: DecimalString
    public let customerHours: DecimalString
    public let nonProductiveHours: DecimalString
    public let status: String
    public let correctsID: UUID?
    public let correctedByID: UUID?
    public let note: String?
    public let submittedBy: UUID?
    public let submittedByName: String?
    public let submittedAt: Date
    public let decidedByName: String?
    public let decidedAt: Date?
    public let decisionNote: String?
    public let photoAttachmentID: UUID?
    public let lines: [Line]
    public let tracker: TrackerCheck?
    /// Where this report's reading was taken (time = `end_at`); nil without coordinates, place or site.
    public let visit: VisitPoint?
    /// The machine's visit before this report's reading (any report's reading, rejected ones included); nil = first.
    public let previousVisit: VisitPoint?
    /// Seconds from the previous visit to this report's reading; nil = the first visit.
    public let sincePreviousVisitSeconds: Int?

    public var state: MachineReportState? { MachineReportState(rawValue: status) }

    /// An opening report: the machine's first reading (older servers: told by `start_source` OPENING).
    public var isOpening: Bool { opening || startSource == "OPENING" }

    public struct Line: Codable, Hashable, Sendable, Identifiable {
        public let id: UUID
        public let lineNo: Int
        public let kind: String
        public let customerID: UUID?
        public let customerName: String?
        public let reasonID: UUID?
        public let reasonCode: String?
        public let reasonName: String?
        public let hours: DecimalString
        public let note: String?
        /// SUBMITTED reports, customer lines: the customer's hours available to this report now (its own reservation
        /// included).
        public let availableHours: DecimalString?

        public var lineKind: ReportLineKind? { ReportLineKind(rawValue: kind) }

        public init(id: UUID = UUID(), lineNo: Int, kind: ReportLineKind, customerID: UUID? = nil, customerName: String? = nil,
                    reasonID: UUID? = nil, reasonName: String? = nil, hours: Decimal, note: String? = nil,
                    availableHours: Decimal? = nil) {
            self.id = id
            self.lineNo = lineNo
            self.kind = kind.rawValue
            self.customerID = customerID
            self.customerName = customerName
            self.reasonID = reasonID
            reasonCode = nil
            self.reasonName = reasonName
            self.hours = DecimalString(hours)
            self.note = note
            self.availableHours = availableHours.map(DecimalString.init)
        }

        enum CodingKeys: String, CodingKey {
            case id, kind, hours, note
            case lineNo = "line_no", customerID = "customer_id", customerName = "customer_name", reasonID = "reason_id"
            case reasonCode = "reason_code", reasonName = "reason_name", availableHours = "available_hours"
        }
    }

    /// `TrackerCheckDto`: engine hours the tracker counted over the report's period, against the meter.
    public struct TrackerCheck: Codable, Hashable, Sendable {
        public let available: Bool
        public let trackerHours: DecimalString?
        public let meterHours: DecimalString
        public let difference: DecimalString?

        public init(available: Bool, trackerHours: Decimal?, meterHours: Decimal, difference: Decimal?) {
            self.available = available
            self.trackerHours = trackerHours.map(DecimalString.init)
            self.meterHours = DecimalString(meterHours)
            self.difference = difference.map(DecimalString.init)
        }

        enum CodingKeys: String, CodingKey {
            case available, difference, trackerHours = "tracker_hours", meterHours = "meter_hours"
        }
    }

    public init(id: UUID, reportNumber: String, machineID: UUID, machineCode: String? = nil, machineName: String? = nil,
                captureID: UUID = UUID(), startReading: Decimal, startAt: Date, endReading: Decimal, endAt: Date,
                status: MachineReportState, submittedBy: UUID? = nil, submittedByName: String? = nil, submittedAt: Date,
                lines: [Line], note: String? = nil, decisionNote: String? = nil, tracker: TrackerCheck? = nil,
                opening: Bool = false, visit: VisitPoint? = nil, previousVisit: VisitPoint? = nil,
                sincePreviousVisitSeconds: Int? = nil) {
        self.visit = visit
        self.previousVisit = previousVisit
        self.sincePreviousVisitSeconds = sincePreviousVisitSeconds
        self.id = id
        self.reportNumber = reportNumber
        self.machineID = machineID
        self.machineCode = machineCode
        self.machineName = machineName
        self.captureID = captureID
        self.opening = opening
        startSource = opening ? "OPENING" : "REPORT"
        self.startReading = DecimalString(startReading)
        self.startAt = startAt
        self.endReading = DecimalString(endReading)
        self.endAt = endAt
        hours = DecimalString(endReading - startReading)
        let customer = lines.filter { $0.lineKind == .customer }.reduce(Decimal(0)) { $0 + $1.hours.value }
        customerHours = DecimalString(customer)
        nonProductiveHours = DecimalString(endReading - startReading - customer)
        self.status = status.rawValue
        correctsID = nil
        correctedByID = nil
        self.note = note
        self.submittedBy = submittedBy
        self.submittedByName = submittedByName
        self.submittedAt = submittedAt
        decidedByName = nil
        decidedAt = nil
        self.decisionNote = decisionNote
        photoAttachmentID = nil
        self.lines = lines
        self.tracker = tracker
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        reportNumber = try c.decode(String.self, forKey: .reportNumber)
        machineID = try c.decode(UUID.self, forKey: .machineID)
        machineCode = try c.decodeIfPresent(String.self, forKey: .machineCode)
        machineName = try c.decodeIfPresent(String.self, forKey: .machineName)
        captureID = try c.decode(UUID.self, forKey: .captureID)
        opening = try c.decodeIfPresent(Bool.self, forKey: .opening) ?? false
        startSource = try c.decodeIfPresent(String.self, forKey: .startSource) ?? "REPORT"
        startReading = try c.decode(DecimalString.self, forKey: .startReading)
        startAt = try c.decode(Date.self, forKey: .startAt)
        endReading = try c.decode(DecimalString.self, forKey: .endReading)
        endAt = try c.decode(Date.self, forKey: .endAt)
        hours = try c.decode(DecimalString.self, forKey: .hours)
        customerHours = try c.decode(DecimalString.self, forKey: .customerHours)
        nonProductiveHours = try c.decode(DecimalString.self, forKey: .nonProductiveHours)
        status = try c.decode(String.self, forKey: .status)
        correctsID = try c.decodeIfPresent(UUID.self, forKey: .correctsID)
        correctedByID = try c.decodeIfPresent(UUID.self, forKey: .correctedByID)
        note = try c.decodeIfPresent(String.self, forKey: .note)
        submittedBy = try c.decodeIfPresent(UUID.self, forKey: .submittedBy)
        submittedByName = try c.decodeIfPresent(String.self, forKey: .submittedByName)
        submittedAt = try c.decode(Date.self, forKey: .submittedAt)
        decidedByName = try c.decodeIfPresent(String.self, forKey: .decidedByName)
        decidedAt = try c.decodeIfPresent(Date.self, forKey: .decidedAt)
        decisionNote = try c.decodeIfPresent(String.self, forKey: .decisionNote)
        photoAttachmentID = try c.decodeIfPresent(UUID.self, forKey: .photoAttachmentID)
        lines = try c.decodeIfPresent([Line].self, forKey: .lines) ?? []
        tracker = try c.decodeIfPresent(TrackerCheck.self, forKey: .tracker)
        visit = try VisitPoint.decode(c, at: nil, lat: .visitLat, lng: .visitLng, accuracy: .visitAccuracyM,
                                      place: .visitPlace, site: .visitSiteName, defaultAt: endAt)
        previousVisit = try VisitPoint.decode(c, at: .previousVisitAt, lat: .previousVisitLat, lng: .previousVisitLng,
                                              accuracy: .previousVisitAccuracyM, place: .previousVisitPlace,
                                              site: .previousVisitSiteName)
        sincePreviousVisitSeconds = try c.decodeIfPresent(Int.self, forKey: .sincePreviousVisitSeconds)
    }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(id, forKey: .id)
        try c.encode(reportNumber, forKey: .reportNumber)
        try c.encode(machineID, forKey: .machineID)
        try c.encodeIfPresent(machineCode, forKey: .machineCode)
        try c.encodeIfPresent(machineName, forKey: .machineName)
        try c.encode(captureID, forKey: .captureID)
        try c.encode(opening, forKey: .opening)
        try c.encode(startSource, forKey: .startSource)
        try c.encode(startReading, forKey: .startReading)
        try c.encode(startAt, forKey: .startAt)
        try c.encode(endReading, forKey: .endReading)
        try c.encode(endAt, forKey: .endAt)
        try c.encode(hours, forKey: .hours)
        try c.encode(customerHours, forKey: .customerHours)
        try c.encode(nonProductiveHours, forKey: .nonProductiveHours)
        try c.encode(status, forKey: .status)
        try c.encodeIfPresent(correctsID, forKey: .correctsID)
        try c.encodeIfPresent(correctedByID, forKey: .correctedByID)
        try c.encodeIfPresent(note, forKey: .note)
        try c.encodeIfPresent(submittedBy, forKey: .submittedBy)
        try c.encodeIfPresent(submittedByName, forKey: .submittedByName)
        try c.encode(submittedAt, forKey: .submittedAt)
        try c.encodeIfPresent(decidedByName, forKey: .decidedByName)
        try c.encodeIfPresent(decidedAt, forKey: .decidedAt)
        try c.encodeIfPresent(decisionNote, forKey: .decisionNote)
        try c.encodeIfPresent(photoAttachmentID, forKey: .photoAttachmentID)
        try c.encode(lines, forKey: .lines)
        try c.encodeIfPresent(tracker, forKey: .tracker)
        try visit?.encode(&c, at: nil, lat: .visitLat, lng: .visitLng, accuracy: .visitAccuracyM, place: .visitPlace,
                          site: .visitSiteName)
        try previousVisit?.encode(&c, at: .previousVisitAt, lat: .previousVisitLat, lng: .previousVisitLng,
                                  accuracy: .previousVisitAccuracyM, place: .previousVisitPlace, site: .previousVisitSiteName)
        try c.encodeIfPresent(sincePreviousVisitSeconds, forKey: .sincePreviousVisitSeconds)
    }

    enum CodingKeys: String, CodingKey {
        case visitLat = "visit_lat", visitLng = "visit_lng", visitAccuracyM = "visit_accuracy_m", visitPlace = "visit_place"
        case visitSiteName = "visit_site_name", previousVisitAt = "previous_visit_at", previousVisitLat = "previous_visit_lat"
        case previousVisitLng = "previous_visit_lng", previousVisitAccuracyM = "previous_visit_accuracy_m"
        case previousVisitPlace = "previous_visit_place", previousVisitSiteName = "previous_visit_site_name"
        case sincePreviousVisitSeconds = "since_previous_visit_seconds"
        case id, hours, status, note, lines, tracker, opening
        case reportNumber = "report_number", machineID = "machine_id", machineCode = "machine_code"
        case machineName = "machine_name", captureID = "capture_id", startSource = "start_source"
        case startReading = "start_reading", startAt = "start_at", endReading = "end_reading", endAt = "end_at"
        case customerHours = "customer_hours", nonProductiveHours = "non_productive_hours", correctsID = "corrects_id"
        case correctedByID = "corrected_by_id", submittedBy = "submitted_by", submittedByName = "submitted_by_name"
        case submittedAt = "submitted_at", decidedByName = "decided_by_name", decidedAt = "decided_at"
        case decisionNote = "decision_note", photoAttachmentID = "photo_attachment_id"
    }
}

/// `CreditInvoiceDto`: the invoice of an order's CREDIT line (paid in full or in parts).
public struct CreditInvoiceDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let invoiceNumber: String
    public let purchaseID: UUID
    public let purchaseNumber: String?
    public let customerID: UUID
    public let customerName: String?
    public let machineID: UUID?
    public let machineCode: String?
    public let currency: String
    public let hours: DecimalString
    public let amount: DecimalString
    public let paid: DecimalString
    public let balance: DecimalString
    public let issuedAt: Date?
    /// Tenant-local day (`YYYY-MM-DD`).
    public let dueDate: String?
    /// `UNPAID`, `PART_PAID`, `PAID`, `CANCELLED`.
    public let status: String
    public let overdue: Bool
    public let daysOverdue: Int
    public let payments: [Payment]

    public struct Payment: Codable, Hashable, Sendable, Identifiable {
        public let id: UUID
        public let amount: DecimalString
        public let method: String
        public let reference: String?
        public let paymentStatus: String?
        public let receivedAt: Date?
        public let recordedByName: String?
        /// Whether this payment still counts towards the invoice (not rejected or reversed).
        public let counts: Bool?

        enum CodingKeys: String, CodingKey {
            case id, amount, method, reference, counts
            case paymentStatus = "payment_status", receivedAt = "received_at", recordedByName = "recorded_by_name"
        }
    }

    public init(id: UUID, invoiceNumber: String, purchaseID: UUID = UUID(), customerID: UUID, customerName: String?,
                currency: String = "TZS", amount: Decimal, paid: Decimal, dueDate: String?, status: String = "UNPAID",
                overdue: Bool = false) {
        self.id = id
        self.invoiceNumber = invoiceNumber
        self.purchaseID = purchaseID
        purchaseNumber = nil
        self.customerID = customerID
        self.customerName = customerName
        machineID = nil
        machineCode = nil
        self.currency = currency
        hours = DecimalString(0)
        self.amount = DecimalString(amount)
        self.paid = DecimalString(paid)
        balance = DecimalString(amount - paid)
        issuedAt = nil
        self.dueDate = dueDate
        self.status = status
        self.overdue = overdue
        daysOverdue = 0
        payments = []
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        invoiceNumber = try c.decode(String.self, forKey: .invoiceNumber)
        purchaseID = try c.decode(UUID.self, forKey: .purchaseID)
        purchaseNumber = try c.decodeIfPresent(String.self, forKey: .purchaseNumber)
        customerID = try c.decode(UUID.self, forKey: .customerID)
        customerName = try c.decodeIfPresent(String.self, forKey: .customerName)
        machineID = try c.decodeIfPresent(UUID.self, forKey: .machineID)
        machineCode = try c.decodeIfPresent(String.self, forKey: .machineCode)
        currency = try c.decodeIfPresent(String.self, forKey: .currency) ?? ""
        hours = try c.decodeIfPresent(DecimalString.self, forKey: .hours) ?? DecimalString(0)
        amount = try c.decode(DecimalString.self, forKey: .amount)
        paid = try c.decodeIfPresent(DecimalString.self, forKey: .paid) ?? DecimalString(0)
        balance = try c.decode(DecimalString.self, forKey: .balance)
        issuedAt = try c.decodeIfPresent(Date.self, forKey: .issuedAt)
        dueDate = try c.decodeIfPresent(String.self, forKey: .dueDate)
        status = try c.decodeIfPresent(String.self, forKey: .status) ?? "UNPAID"
        overdue = try c.decodeIfPresent(Bool.self, forKey: .overdue) ?? false
        daysOverdue = try c.decodeIfPresent(Int.self, forKey: .daysOverdue) ?? 0
        payments = try c.decodeIfPresent([Payment].self, forKey: .payments) ?? []
    }

    enum CodingKeys: String, CodingKey {
        case id, currency, hours, amount, paid, balance, status, overdue, payments
        case invoiceNumber = "invoice_number", purchaseID = "purchase_id", purchaseNumber = "purchase_number"
        case customerID = "customer_id", customerName = "customer_name", machineID = "machine_id"
        case machineCode = "machine_code", issuedAt = "issued_at", dueDate = "due_date", daysOverdue = "days_overdue"
    }
}

/// `CreditInvoiceSummaryDto` on an order.
public struct CreditInvoiceSummaryDTO: Codable, Hashable, Sendable {
    public let id: UUID
    public let invoiceNumber: String
    public let amount: DecimalString
    public let paid: DecimalString
    public let balance: DecimalString
    public let dueDate: String?
    public let status: String
    public let overdue: Bool

    enum CodingKeys: String, CodingKey {
        case id, amount, paid, balance, status, overdue, invoiceNumber = "invoice_number", dueDate = "due_date"
    }
}

/// `CustomerHoursSummaryDto`: per customer hours bought / activated / used / left and credit owed.
public struct CustomerHoursSummaryDTO: Codable, Hashable, Sendable, Identifiable {
    public let customerID: UUID
    public let customerName: String?
    public let bought: DecimalString
    public let activated: DecimalString
    public let used: DecimalString
    public let left: DecimalString
    public let awaitingActivation: DecimalString
    public let creditOwed: DecimalString

    public var id: UUID { customerID }

    public init(customerID: UUID, customerName: String?, bought: Decimal, activated: Decimal, used: Decimal, left: Decimal,
                awaitingActivation: Decimal = 0, creditOwed: Decimal = 0) {
        self.customerID = customerID
        self.customerName = customerName
        self.bought = DecimalString(bought)
        self.activated = DecimalString(activated)
        self.used = DecimalString(used)
        self.left = DecimalString(left)
        self.awaitingActivation = DecimalString(awaitingActivation)
        self.creditOwed = DecimalString(creditOwed)
    }

    enum CodingKeys: String, CodingKey {
        case bought, activated, used, left
        case customerID = "customer_id", customerName = "customer_name", awaitingActivation = "awaiting_activation"
        case creditOwed = "credit_owed"
    }
}

// MARK: - Operation payloads

/// `MachineReportLineIn`.
public struct MachineReportLinePayload: Codable, Hashable, Sendable {
    public let kind: ReportLineKind
    public let customerID: UUID?
    public let reasonID: UUID?
    public let hours: DecimalString
    public let note: String?

    public init(kind: ReportLineKind, customerID: UUID?, reasonID: UUID?, hours: Decimal, note: String?) {
        self.kind = kind
        self.customerID = customerID
        self.reasonID = reasonID
        self.hours = DecimalString(hours)
        self.note = note
    }

    enum CodingKeys: String, CodingKey {
        case kind, hours, note, customerID = "customer_id", reasonID = "reason_id"
    }
}

/// `MACHINE_REPORT` (`MachineReportIn` without `id`: the operation id is the report id). The reading travels as its own
/// `METER_CAPTURE` operation queued first (photo, OCR, GPS, time) and is named here by `capture_id`; the report op
/// depends on it. A rejected report is final: a new report always comes with a new reading (`corrects_report_id` is never
/// sent). `opening`: the machine has no starting reading yet, so this reading only opens the count (no lines).
public struct MachineReportPayload: Codable, Hashable, Sendable {
    public let machineID: UUID
    public let captureID: UUID
    public let lines: [MachineReportLinePayload]
    public let note: String?
    public let opening: Bool?

    public init(machineID: UUID, captureID: UUID, lines: [MachineReportLinePayload], note: String?, opening: Bool? = nil) {
        self.machineID = machineID
        self.captureID = captureID
        self.lines = lines
        self.note = note
        self.opening = opening
    }

    enum CodingKeys: String, CodingKey {
        case lines, note, opening, machineID = "machine_id", captureID = "capture_id"
    }
}

/// `CREDIT_INVOICE_PAYMENT` (`CreditInvoicePaymentIn` + `invoice_id` and `evidence_upload_ids`; the operation id is the
/// payment's client id).
public struct CreditInvoicePaymentPayload: Codable, Hashable, Sendable {
    public let invoiceID: UUID
    public let amount: DecimalString
    public let method: String
    public let reference: String?
    public let receivedAt: Date
    public let staffMemberID: UUID?
    public let note: String?
    public let evidenceAttachmentIDs: [UUID]
    public let evidenceUploadIDs: [UUID]

    public init(invoiceID: UUID, amount: Decimal, method: String, reference: String?, receivedAt: Date, staffMemberID: UUID?,
                note: String?) {
        self.invoiceID = invoiceID
        self.amount = DecimalString(amount)
        self.method = method
        self.reference = reference
        self.receivedAt = receivedAt
        self.staffMemberID = staffMemberID
        self.note = note
        evidenceAttachmentIDs = []
        evidenceUploadIDs = []
    }

    enum CodingKeys: String, CodingKey {
        case amount, method, reference, note
        case invoiceID = "invoice_id", receivedAt = "received_at", staffMemberID = "staff_member_id"
        case evidenceAttachmentIDs = "evidence_attachment_ids", evidenceUploadIDs = "evidence_upload_ids"
    }
}

/// `CreditInvoicePaymentIn` (online, Owner app).
public struct CreditInvoicePaymentIn: Codable, Hashable, Sendable {
    public let clientID: UUID
    public let amount: DecimalString
    public let method: String
    public let reference: String?
    public let receivedAt: Date
    public let note: String?

    public init(clientID: UUID, amount: Decimal, method: String, reference: String?, receivedAt: Date, note: String?) {
        self.clientID = clientID
        self.amount = DecimalString(amount)
        self.method = method
        self.reference = reference
        self.receivedAt = receivedAt
        self.note = note
    }

    enum CodingKeys: String, CodingKey {
        case amount, method, reference, note, clientID = "client_id", receivedAt = "received_at"
    }
}

/// ADR-008: a visit of a machine = one meter reading of a machine report: when and where it was taken. `place` is the
/// phone's geocoder label of the reading, `siteName` the company site the coordinates fall in (server hint).
public struct VisitPoint: Hashable, Sendable {
    public let at: Date?
    public let latitude: Double?
    public let longitude: Double?
    public let accuracyM: Double?
    public let place: String?
    public let siteName: String?

    public init(at: Date?, latitude: Double? = nil, longitude: Double? = nil, accuracyM: Double? = nil, place: String? = nil,
                siteName: String? = nil) {
        self.at = at
        self.latitude = latitude
        self.longitude = longitude
        self.accuracyM = accuracyM
        self.place = place
        self.siteName = siteName
    }

    /// Both coordinates, else nil.
    public var coordinate: (latitude: Double, longitude: Double)? {
        guard let latitude, let longitude else { return nil }
        return (latitude, longitude)
    }

    /// The same visit with a display-only place (never sent or saved).
    public func with(place: String?) -> VisitPoint {
        VisitPoint(at: at, latitude: latitude, longitude: longitude, accuracyM: accuracyM, place: place, siteName: siteName)
    }

    /// Reads the six fields. With an `at` key the visit exists only when its time does; without one (this report's own
    /// reading, time `defaultAt`) it exists when any other field is present.
    static func decode<K: CodingKey>(_ c: KeyedDecodingContainer<K>, at: K?, lat: K, lng: K, accuracy: K, place: K, site: K,
                                     defaultAt: Date? = nil) throws -> VisitPoint? {
        let time = try at.flatMap { try c.decodeIfPresent(Date.self, forKey: $0) }
        let point = VisitPoint(
            at: time ?? defaultAt,
            latitude: try c.decodeIfPresent(Double.self, forKey: lat), longitude: try c.decodeIfPresent(Double.self, forKey: lng),
            accuracyM: try c.decodeIfPresent(Double.self, forKey: accuracy),
            place: try c.decodeIfPresent(String.self, forKey: place), siteName: try c.decodeIfPresent(String.self, forKey: site))
        if at != nil { return time == nil ? nil : point }
        let any = point.latitude != nil || point.longitude != nil || point.place != nil || point.siteName != nil
        return any ? point : nil
    }

    func encode<K: CodingKey>(_ c: inout KeyedEncodingContainer<K>, at: K?, lat: K, lng: K, accuracy: K, place: K,
                              site: K) throws {
        if let at { try c.encodeIfPresent(self.at, forKey: at) }
        try c.encodeIfPresent(latitude, forKey: lat)
        try c.encodeIfPresent(longitude, forKey: lng)
        try c.encodeIfPresent(accuracyM, forKey: accuracy)
        try c.encodeIfPresent(self.place, forKey: place)
        try c.encodeIfPresent(siteName, forKey: site)
    }
}
