import Foundation

// Accountability (design A customer hours, B engine hours, C cash custody): the field operations the Supervisor
// app queues offline, the server capabilities that gate them, the online lists it reads and the tenant policy
// values that switch each capability on. Shapes follow `contracts/openapi.json`.

extension SyncCapability {
    /// `HOURS_PURCHASE` (walk-in/registered customer hours purchase with payment claim and evidence uploads).
    public static let hoursPurchase = "OP_HOURS_PURCHASE"
    public static let hoursTransferRequest = "OP_HOURS_TRANSFER_REQUEST"
    /// `CASH_TRANSFER`, `CASH_TRANSFER_ACKNOWLEDGEMENT` and `CASH_FLOAT_ACKNOWLEDGEMENT`.
    public static let cashTransfer = "OP_CASH_TRANSFER"
    /// `METER_CAPTURE` accepts kind DAILY (job_id null, machine_id set).
    public static let meterDailyReading = "METER_DAILY_READING"
    public static let meterBaseline = "OP_METER_BASELINE"
    public static let meterCorrection = "OP_METER_CORRECTION"
    /// `CASH_RETENTION_REQUEST` (ask to keep cash, queued offline; decided by another person).
    public static let cashRetentionRequest = "OP_CASH_RETENTION_REQUEST"
}

// MARK: - Operation payloads

/// `WalkInCustomerIn`: a customer known only by name (and phone); the server assigns the WALK code.
public struct WalkInCustomerPayload: Codable, Hashable, Sendable {
    /// Becomes the customer id, so an offline replay returns the same walk-in customer.
    public let clientID: UUID?
    public let name: String
    public let phone: String?

    public init(clientID: UUID?, name: String, phone: String?) {
        self.clientID = clientID
        self.name = name
        self.phone = phone
    }

    enum CodingKeys: String, CodingKey { case name, phone, clientID = "client_id" }
}

/// `PurchasePaymentIn`: the payment taken with the purchase (CLAIMED until the office verifies it).
public struct PurchasePaymentPayload: Codable, Hashable, Sendable {
    public let method: String
    public let amount: DecimalString?
    public let receivedAt: Date
    public let reference: String?
    public let note: String?
    /// The custodian who holds the cash (nil = the recorder).
    public let staffMemberID: UUID?

    public init(method: String, amount: Decimal?, receivedAt: Date, reference: String?, note: String?, staffMemberID: UUID?) {
        self.method = method
        self.amount = amount.map(DecimalString.init)
        self.receivedAt = receivedAt
        self.reference = reference
        self.note = note
        self.staffMemberID = staffMemberID
    }

    enum CodingKeys: String, CodingKey {
        case method, amount, reference, note, receivedAt = "received_at", staffMemberID = "staff_member_id"
    }
}

/// `HOURS_PURCHASE` (`HoursPurchaseIn` + `evidence_upload_ids`). The operation id is the purchase's client id;
/// evidence photos are resumable uploads (purpose PAYMENT_EVIDENCE) appended when complete.
public struct HoursPurchasePayload: Codable, Hashable, Sendable {
    public let clientID: UUID
    public let machineID: UUID
    public let hours: DecimalString
    public let customerID: UUID?
    public let walkIn: WalkInCustomerPayload?
    public let jobSiteID: UUID?
    public let note: String?
    public let payment: PurchasePaymentPayload?
    public let evidenceUploadIDs: [UUID]

    public init(clientID: UUID, machineID: UUID, hours: Decimal, customerID: UUID?, walkIn: WalkInCustomerPayload?,
                jobSiteID: UUID?, note: String?, payment: PurchasePaymentPayload?) {
        self.clientID = clientID
        self.machineID = machineID
        self.hours = DecimalString(hours)
        self.customerID = customerID
        self.walkIn = walkIn
        self.jobSiteID = jobSiteID
        self.note = note
        self.payment = payment
        evidenceUploadIDs = []
    }

    enum CodingKeys: String, CodingKey {
        case hours, note, payment, clientID = "client_id", machineID = "machine_id", customerID = "customer_id", walkIn = "walk_in"
        case jobSiteID = "job_site_id", evidenceUploadIDs = "evidence_upload_ids"
    }
}

/// `HOURS_TRANSFER_REQUEST` (`TransferIn`): move remaining hours of a purchase to another machine.
public struct HoursTransferPayload: Codable, Hashable, Sendable {
    public let clientID: UUID
    public let purchaseID: UUID
    public let fromMachineID: UUID?
    public let toMachineID: UUID
    public let hours: DecimalString
    public let reason: String
    public let reasonCodeID: UUID?

    public init(clientID: UUID, purchaseID: UUID, fromMachineID: UUID?, toMachineID: UUID, hours: Decimal, reason: String,
                reasonCodeID: UUID?) {
        self.clientID = clientID
        self.reasonCodeID = reasonCodeID
        self.purchaseID = purchaseID
        self.fromMachineID = fromMachineID
        self.toMachineID = toMachineID
        self.hours = DecimalString(hours)
        self.reason = reason
    }

    enum CodingKeys: String, CodingKey {
        case hours, reason, clientID = "client_id", purchaseID = "purchase_id", fromMachineID = "from_machine_id"
        case toMachineID = "to_machine_id", reasonCodeID = "reason_code_id"
    }
}

/// `CASH_TRANSFER` (`CashTransferIn`): field-to-field cash. When the recorder is the receiver, `amount_received`
/// is what they actually got (recording it is the acknowledgement when the tenant allows that).
public struct CashTransferPayload: Codable, Hashable, Sendable {
    public let clientID: UUID
    public let fromStaffID: UUID?
    public let toStaffID: UUID
    public let amount: DecimalString
    public let amountReceived: DecimalString?
    public let currency: String?
    public let transferredAt: Date
    public let note: String?

    public init(clientID: UUID, fromStaffID: UUID?, toStaffID: UUID, amount: Decimal, amountReceived: Decimal?,
                currency: String?, transferredAt: Date, note: String?) {
        self.clientID = clientID
        self.fromStaffID = fromStaffID
        self.toStaffID = toStaffID
        self.amount = DecimalString(amount)
        self.amountReceived = amountReceived.map(DecimalString.init)
        self.currency = currency
        self.transferredAt = transferredAt
        self.note = note
    }

    enum CodingKeys: String, CodingKey {
        case amount, currency, note, clientID = "client_id", fromStaffID = "from_staff_id", toStaffID = "to_staff_id"
        case amountReceived = "amount_received", transferredAt = "transferred_at"
    }
}

/// `CASH_TRANSFER_ACKNOWLEDGEMENT` / `CASH_FLOAT_ACKNOWLEDGEMENT` (`CashAcknowledgementIn` + the record id).
public struct CashAcknowledgementPayload: Codable, Hashable, Sendable {
    public let transferID: UUID?
    public let entryID: UUID?
    public let acknowledged: Bool
    public let amountReceived: DecimalString?
    public let note: String?

    public init(transferID: UUID? = nil, entryID: UUID? = nil, acknowledged: Bool, amountReceived: Decimal?, note: String?) {
        self.transferID = transferID
        self.entryID = entryID
        self.acknowledged = acknowledged
        self.amountReceived = amountReceived.map(DecimalString.init)
        self.note = note
    }

    enum CodingKeys: String, CodingKey {
        case acknowledged, note, transferID = "transfer_id", entryID = "entry_id", amountReceived = "amount_received"
    }
}

/// `METER_BASELINE` (`BaselineIn`; the server takes the operation id as the baseline id). The photo's attachment id
/// is written into `photo_attachment_id` when its upload completes.
public struct MeterBaselinePayload: Codable, Hashable, Sendable {
    /// The baseline id (also the operation id; a replay returns the same baseline).
    public let id: UUID
    public let machineID: UUID
    public let reading: String
    public let capturedAt: Date
    public let photoAttachmentID: UUID?
    public let gps: GpsPayload?
    public let deviceID: String
    public let note: String?

    public init(id: UUID, machineID: UUID, reading: String, capturedAt: Date, gps: GpsPayload?, deviceID: String, note: String?) {
        self.id = id
        self.machineID = machineID
        self.reading = reading
        self.capturedAt = capturedAt
        photoAttachmentID = nil
        self.gps = gps
        self.deviceID = deviceID
        self.note = note
    }

    enum CodingKeys: String, CodingKey {
        case id, reading, gps, note, machineID = "machine_id", capturedAt = "captured_at"
        case photoAttachmentID = "photo_attachment_id", deviceID = "device_id"
    }
}

/// `METER_CORRECTION` (`CorrectionIn`): a replacement reading for one of mine, proposed with a reason (10+ characters)
/// and approved by a second person. The replacement's photo id fills `replacement.photo_attachment_id`.
public struct MeterCorrectionPayload: Codable, Hashable, Sendable {
    public let supersededCaptureID: UUID
    public let reason: String
    public let replacement: MeterCapturePayload

    public init(supersededCaptureID: UUID, reason: String, replacement: MeterCapturePayload) {
        self.supersededCaptureID = supersededCaptureID
        self.reason = reason
        self.replacement = replacement
    }

    enum CodingKeys: String, CodingKey { case reason, replacement, supersededCaptureID = "superseded_capture_id" }
}

/// `CashRetentionIn`: ask to keep some cash instead of remitting it (decided by another person). Online it is a
/// `POST /cash/retentions`; offline it is the `CASH_RETENTION_REQUEST` payload, where `client_id` is required and makes
/// a replay return the same request.
public struct CashRetentionIn: Codable, Hashable, Sendable {
    public let clientID: UUID?
    public let amount: DecimalString
    public let currency: String?
    public let reason: String
    public let reasonID: UUID?
    public let staffMemberID: UUID?
    public let validUntil: Date?

    public init(amount: Decimal, currency: String?, reason: String, reasonID: UUID?, staffMemberID: UUID?, validUntil: Date?,
                clientID: UUID? = nil) {
        self.clientID = clientID
        self.reasonID = reasonID
        self.validUntil = validUntil
        self.amount = DecimalString(amount)
        self.currency = currency
        self.reason = reason
        self.staffMemberID = staffMemberID
    }

    enum CodingKeys: String, CodingKey {
        case amount, currency, reason, reasonID = "reason_id", staffMemberID = "staff_member_id", validUntil = "valid_until"
        case clientID = "client_id"
    }
}

// MARK: - Online reads

/// `CustodianDto`: any active staff member who may hold cash (with or without a login).
public struct CustodianDTO: Codable, Hashable, Sendable, Identifiable {
    public let staffMemberID: UUID
    public let fullName: String
    public let kind: String
    public let employeeCode: String?
    public let isActive: Bool
    public let hasLogin: Bool

    public var id: UUID { staffMemberID }

    public init(staffMemberID: UUID, fullName: String, kind: String, employeeCode: String?, isActive: Bool, hasLogin: Bool) {
        self.staffMemberID = staffMemberID
        self.fullName = fullName
        self.kind = kind
        self.employeeCode = employeeCode
        self.isActive = isActive
        self.hasLogin = hasLogin
    }

    enum CodingKeys: String, CodingKey {
        case kind, staffMemberID = "staff_member_id", fullName = "full_name", employeeCode = "employee_code"
        case isActive = "is_active", hasLogin = "has_login"
    }
}

/// `CashTransferDto`.
public struct CashTransferDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let clientID: UUID?
    public let fromStaffID: UUID
    public let toStaffID: UUID
    public let amountDeclared: DecimalString
    public let currency: String
    public let transferredAt: Date
    public let note: String?
    public let status: String
    public let source: String
    public let recordedBy: UUID?
    public let recordedAt: Date
    public let amountReceived: DecimalString?
    public let ackMethod: String?
    public let acknowledgedBy: UUID?
    public let acknowledgedAt: Date?
    public let ackNote: String?
    public let varianceID: UUID?
    // Display names beside the ids (nullable; show the short id only when missing).
    public let fromStaffName: String?
    public let toStaffName: String?
    public let recordedByName: String?
    public let acknowledgedByName: String?

    enum CodingKeys: String, CodingKey {
        case fromStaffName = "from_staff_name", toStaffName = "to_staff_name", recordedByName = "recorded_by_name"
        case acknowledgedByName = "acknowledged_by_name"
        case id, currency, note, status, source, clientID = "client_id", fromStaffID = "from_staff_id"
        case toStaffID = "to_staff_id", amountDeclared = "amount_declared", transferredAt = "transferred_at"
        case recordedBy = "recorded_by", recordedAt = "recorded_at", amountReceived = "amount_received"
        case ackMethod = "ack_method", acknowledgedBy = "acknowledged_by", acknowledgedAt = "acknowledged_at"
        case ackNote = "ack_note", varianceID = "variance_id"
    }
}

/// `CashCustodyEntryDto` of a float (company → custodian) with its acknowledgement state.
public struct CashFloatDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let staffMemberID: UUID
    public let entryType: String
    public let amount: DecimalString
    public let currency: String
    public let occurredAt: Date
    public let reference: String?
    public let note: String?
    public let ackRequired: Bool?
    public let ackStatus: String?
    public let amountReceived: DecimalString?
    public let acknowledgedAt: Date?
    public let staffMemberName: String?
    public let createdByName: String?
    public let acknowledgedByName: String?

    enum CodingKeys: String, CodingKey {
        case staffMemberName = "staff_member_name", createdByName = "created_by_name", acknowledgedByName = "acknowledged_by_name"
        case id, amount, currency, reference, note, staffMemberID = "staff_member_id", entryType = "entry_type"
        case occurredAt = "occurred_at", ackRequired = "ack_required", ackStatus = "ack_status"
        case amountReceived = "amount_received", acknowledgedAt = "acknowledged_at"
    }
}

/// `CashRetentionDto`.
public struct CashRetentionDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let staffMemberID: UUID
    public let amount: DecimalString
    public let currency: String
    public let reasonID: UUID?
    public let reason: String
    public let validUntil: Date?
    public let status: String
    public let createdBy: UUID?
    public let createdAt: Date
    public let decidedBy: UUID?
    public let decidedAt: Date?
    public let decisionNote: String?
    /// The device's client id when it was asked from the app (offline idempotency).
    public let clientID: UUID?
    public let staffMemberName: String?
    public let createdByName: String?
    public let decidedByName: String?

    enum CodingKeys: String, CodingKey {
        case clientID = "client_id", staffMemberName = "staff_member_name", createdByName = "created_by_name"
        case decidedByName = "decided_by_name"
        case id, amount, currency, reason, status, staffMemberID = "staff_member_id", reasonID = "reason_id"
        case validUntil = "valid_until", createdBy = "created_by", createdAt = "created_at", decidedBy = "decided_by"
        case decidedAt = "decided_at", decisionNote = "decision_note"
    }
}

/// `HoursPurchaseDto` as the apps show it (number, customer, machine, hours, amount, status, remaining).
public struct HoursPurchaseDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let purchaseNumber: String
    public let clientID: UUID?
    public let customerID: UUID
    public let customerName: String?
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let jobSiteName: String?
    public let createdByName: String?
    public let hours: DecimalString
    public let currency: String
    public let amount: DecimalString
    public let status: String
    public let createdAt: Date
    public let cancelledAt: Date?
    public let totals: Totals
    /// The purchase's hours per machine after transfers.
    public let machines: [MachineHours]?

    public struct Totals: Codable, Hashable, Sendable {
        public let purchased: DecimalString
        public let activated: DecimalString
        public let consumed: DecimalString
        public let remaining: DecimalString
        public let awaitingActivation: DecimalString
        /// Hours moved to other machines; 0 when absent.
        public let transferred: DecimalString
        public let expired: DecimalString
        /// DEC-031 Phase 4 daily drawdown: hours held by running jobs (already out of `remaining`); 0 when absent.
        public let provisional: DecimalString

        public init(from decoder: any Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            let zero = DecimalString(0)
            purchased = try c.decode(DecimalString.self, forKey: .purchased)
            activated = try c.decode(DecimalString.self, forKey: .activated)
            consumed = try c.decode(DecimalString.self, forKey: .consumed)
            remaining = try c.decode(DecimalString.self, forKey: .remaining)
            awaitingActivation = try c.decode(DecimalString.self, forKey: .awaitingActivation)
            transferred = try c.decodeIfPresent(DecimalString.self, forKey: .transferred) ?? zero
            expired = try c.decodeIfPresent(DecimalString.self, forKey: .expired) ?? zero
            provisional = try c.decodeIfPresent(DecimalString.self, forKey: .provisional) ?? zero
        }

        enum CodingKeys: String, CodingKey {
            case purchased, activated, consumed, remaining, transferred, expired, provisional
            case awaitingActivation = "awaiting_activation"
        }
    }

    public struct MachineHours: Codable, Hashable, Sendable {
        public let machineID: UUID
        public let machineCode: String?
        public let machineName: String?
        public let remaining: DecimalString
        /// Hours of this machine held by running jobs (DEC-031 Phase 4); 0 when absent.
        public let provisional: DecimalString

        public init(from decoder: any Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            machineID = try c.decode(UUID.self, forKey: .machineID)
            machineCode = try c.decodeIfPresent(String.self, forKey: .machineCode)
            machineName = try c.decodeIfPresent(String.self, forKey: .machineName)
            remaining = try c.decode(DecimalString.self, forKey: .remaining)
            provisional = try c.decodeIfPresent(DecimalString.self, forKey: .provisional) ?? DecimalString(0)
        }

        enum CodingKeys: String, CodingKey {
            case remaining, provisional, machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name"
        }
    }

    /// Hours held by running jobs on `machineID` (after transfers), else on the whole purchase.
    public func provisional(on machineID: UUID?) -> Decimal {
        machines?.first { $0.machineID == machineID }?.provisional.value ?? totals.provisional.value
    }

    /// Remaining hours on `machineID` (after transfers), else the purchase total remaining.
    public func remaining(on machineID: UUID?) -> Decimal {
        machines?.first { $0.machineID == machineID }?.remaining.value ?? totals.remaining.value
    }

    enum CodingKeys: String, CodingKey {
        case id, hours, currency, amount, status, totals, machines, purchaseNumber = "purchase_number", clientID = "client_id"
        case customerID = "customer_id", customerName = "customer_name", machineID = "machine_id", createdAt = "created_at"
        case machineCode = "machine_code", machineName = "machine_name", jobSiteName = "job_site_name"
        case createdByName = "created_by_name", cancelledAt = "cancelled_at"
    }
}

// MARK: - Tenant policy values (`GET /tenant/policies/{type}/effective`)

/// `EffectivePolicyDto` with the values of one policy type.
public struct EffectivePolicyDTO<Values: Codable & Hashable & Sendable>: Codable, Hashable, Sendable {
    public let policyType: String
    public let versionStamp: String
    public let values: Values

    enum CodingKeys: String, CodingKey { case values, policyType = "policy_type", versionStamp = "version_stamp" }
}

/// The CASH_CUSTODY switches the field app follows. Parsed strictly (a missing or mistyped switch makes the policy
/// unknown, which hides the new options), as Android `CashCustodyPolicy`.
public struct CashCustodyPolicyValues: Codable, Hashable, Sendable {
    public let recordersMayRecordForOthers: Bool
    public let transferAckRequired: Bool
    public let recorderReceiverCountsAsAck: Bool
    public let floatAckRequired: Bool
    public let remitFullBalance: Bool
    public let retentionAllowed: Bool
    /// DEC-031 D2 remittance requirements (off when absent: a server before DEC-031 never asks for them).
    /// A bank / mobile-money remittance needs its transaction reference (cash to the office never does).
    public let remittanceReferenceRequired: Bool
    /// A photo of the deposit slip or payment confirmation.
    public let remittanceEvidenceRequired: Bool
    /// The company deposit account the money was paid into.
    public let remittanceAccountRequired: Bool
    /// Days a custodian may hold unremitted cash (nil = no limit). Informational on the phone (D3).
    public let maxHoldingDays: Int?

    public init(recordersMayRecordForOthers: Bool, transferAckRequired: Bool, recorderReceiverCountsAsAck: Bool,
                floatAckRequired: Bool, remitFullBalance: Bool, retentionAllowed: Bool,
                remittanceReferenceRequired: Bool = false, remittanceEvidenceRequired: Bool = false,
                remittanceAccountRequired: Bool = false, maxHoldingDays: Int? = nil) {
        self.recordersMayRecordForOthers = recordersMayRecordForOthers
        self.transferAckRequired = transferAckRequired
        self.recorderReceiverCountsAsAck = recorderReceiverCountsAsAck
        self.floatAckRequired = floatAckRequired
        self.remitFullBalance = remitFullBalance
        self.retentionAllowed = retentionAllowed
        self.remittanceReferenceRequired = remittanceReferenceRequired
        self.remittanceEvidenceRequired = remittanceEvidenceRequired
        self.remittanceAccountRequired = remittanceAccountRequired
        self.maxHoldingDays = maxHoldingDays
    }

    /// The DEC-030 switches are strict (a missing one makes the policy unknown); the DEC-031 keys default to off.
    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        recordersMayRecordForOthers = try c.decode(Bool.self, forKey: .recordersMayRecordForOthers)
        transferAckRequired = try c.decode(Bool.self, forKey: .transferAckRequired)
        recorderReceiverCountsAsAck = try c.decode(Bool.self, forKey: .recorderReceiverCountsAsAck)
        floatAckRequired = try c.decode(Bool.self, forKey: .floatAckRequired)
        remitFullBalance = try c.decode(Bool.self, forKey: .remitFullBalance)
        retentionAllowed = try c.decode(Bool.self, forKey: .retentionAllowed)
        remittanceReferenceRequired = try c.decodeIfPresent(Bool.self, forKey: .remittanceReferenceRequired) ?? false
        remittanceEvidenceRequired = try c.decodeIfPresent(Bool.self, forKey: .remittanceEvidenceRequired) ?? false
        remittanceAccountRequired = try c.decodeIfPresent(Bool.self, forKey: .remittanceAccountRequired) ?? false
        maxHoldingDays = try c.decodeIfPresent(Int.self, forKey: .maxHoldingDays)
    }

    enum CodingKeys: String, CodingKey {
        case recordersMayRecordForOthers = "recorders_may_record_for_others", transferAckRequired = "transfer_ack_required"
        case recorderReceiverCountsAsAck = "recorder_receiver_counts_as_ack", floatAckRequired = "float_ack_required"
        case remitFullBalance = "remit_full_balance", retentionAllowed = "retention_allowed"
        case remittanceReferenceRequired = "remittance_reference_required"
        case remittanceEvidenceRequired = "remittance_evidence_required"
        case remittanceAccountRequired = "remittance_account_required", maxHoldingDays = "max_holding_days"
    }
}

/// The CUSTOMER_HOURS switches the field app follows. Parsed strictly (a missing or mistyped switch makes the
/// policy unknown, which hides the new options), as Android `CustomerHoursPolicy`.
public struct CustomerHoursPolicyValues: Codable, Hashable, Sendable {
    public let enabled: Bool
    public let walkInAllowed: Bool
    public let transferRequiresApproval: Bool
    public let reasonCodeRequired: Bool

    public init(enabled: Bool, walkInAllowed: Bool, transferRequiresApproval: Bool, reasonCodeRequired: Bool = false) {
        self.enabled = enabled
        self.walkInAllowed = walkInAllowed
        self.transferRequiresApproval = transferRequiresApproval
        self.reasonCodeRequired = reasonCodeRequired
    }

    enum CodingKeys: String, CodingKey {
        case enabled, walkInAllowed = "walk_in_allowed", transferRequiresApproval = "transfer_requires_approval"
        case reasonCodeRequired = "reason_code_required"
    }
}

/// `ReasonCodeDto`: a tenant hours reason (kind DISCOUNT, CREDIT, TRANSFER, CANCELLATION).
public struct ReasonCodeDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let kind: String
    public let code: String
    public let label: String
    public let isActive: Bool

    enum CodingKeys: String, CodingKey { case id, kind, code, label, isActive = "is_active" }
}

/// `CashReasonDto`: a tenant cash reason (kind VARIANCE, WRITE_OFF, RETENTION, ADJUSTMENT).
public struct CashReasonDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let kind: String
    public let label: String
    public let description: String?
    public let isActive: Bool

    enum CodingKeys: String, CodingKey { case id, kind, label, description, isActive = "is_active" }
}

/// A display name from the server, else a short form of the id ("3f2a9c1e"), never empty.
public enum DisplayName {
    public static func or(_ name: String?, id: UUID?) -> String {
        if let name = name?.trimmingCharacters(in: .whitespacesAndNewlines), !name.isEmpty { return name }
        return id.map(shortID) ?? "—"
    }

    /// The name, else the short id, else nil (a missing person or record is left out).
    public static func optional(_ name: String?, id: UUID?) -> String? {
        if let name = name?.trimmingCharacters(in: .whitespacesAndNewlines), !name.isEmpty { return name }
        return id.map(shortID)
    }

    /// "CODE · Name" for a machine (either part may be missing), else the short id.
    public static func machine(code: String?, name: String?, id: UUID?) -> String {
        let parts = [code, name].compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
        return parts.isEmpty ? (id.map(shortID) ?? "—") : parts.joined(separator: " · ")
    }

    /// The first 8 characters of the id, lower case.
    public static func shortID(_ id: UUID) -> String { String(id.uuidString.lowercased().prefix(8)) }
}

/// `RemittanceOverdueDto`: a custodian still holding unremitted cash after the tenant's daily cut-off (reason
/// CUTOFF) or longer than their holding allowance (reason HELD_TOO_LONG, DEC-031 D3). One per custodian per
/// tenant-local day per reason; evidence, never edited.
public struct RemittanceOverdueDTO: Codable, Hashable, Sendable, Identifiable {
    public struct Amount: Codable, Hashable, Sendable {
        public let currency: String
        public let amount: DecimalString
    }

    public let id: UUID
    public let staffMemberID: UUID
    public let staffMemberName: String?
    /// Tenant-local day (`YYYY-MM-DD`).
    public let localDay: String
    /// CUTOFF: the daily cut-off hour; HELD_TOO_LONG: the tenant-local hour it was flagged (never shown as a cut-off).
    public let cutoffHour: Int
    public let amounts: [Amount]
    public let flaggedAt: Date
    public let policyVersion: String
    /// Kept as text (nil from a server before DEC-031 = CUTOFF); see ``overdueReason``.
    public let reason: String?
    /// When the oldest unremitted cash was received.
    public let heldSince: Date?
    /// The holding allowance that applied.
    public let maxHoldingDays: Int?

    public init(id: UUID, staffMemberID: UUID, staffMemberName: String?, localDay: String, cutoffHour: Int,
                amounts: [Amount], flaggedAt: Date, policyVersion: String, reason: String? = nil, heldSince: Date? = nil,
                maxHoldingDays: Int? = nil) {
        self.id = id
        self.staffMemberID = staffMemberID
        self.staffMemberName = staffMemberName
        self.localDay = localDay
        self.cutoffHour = cutoffHour
        self.amounts = amounts
        self.flaggedAt = flaggedAt
        self.policyVersion = policyVersion
        self.reason = reason
        self.heldSince = heldSince
        self.maxHoldingDays = maxHoldingDays
    }

    /// HELD_TOO_LONG only when the server says so; anything else reads as the daily cut-off.
    public var overdueReason: OverdueReason { reason.flatMap(OverdueReason.init(rawValue:)) ?? .cutoff }
    public var heldTooLong: Bool { overdueReason == .heldTooLong }

    enum CodingKeys: String, CodingKey {
        case id, amounts, reason, staffMemberID = "staff_member_id", staffMemberName = "staff_member_name", localDay = "local_day"
        case cutoffHour = "cutoff_hour", flaggedAt = "flagged_at", policyVersion = "policy_version"
        case heldSince = "held_since", maxHoldingDays = "max_holding_days"
    }
}
