import AssetaCapture
import AssetaModel
import AssetaStore
import CryptoKit
import Foundation

/// What the field app offers from the accountability wave, from the server's sync capabilities, the user's
/// permissions and the tenant policies cached on the phone (gating table of
/// `docs/requirements/accountability-mobile-strings.md`; Android `FieldAccess`). An unknown policy hides the new
/// options, so today's screens are unchanged. The server re-checks everything on every pushed operation.
public struct FieldAccess: Sendable, Equatable {
    /// Nil when the phone never synced.
    public let capabilities: Set<String>?
    public let permissions: Set<String>
    public let cash: CashCustodyPolicyValues?
    public let hours: CustomerHoursPolicyValues?
    /// Tenant capabilities switched off by policy (`/me` `tenants[].disabled_capabilities`, e.g. CUSTOMER_HOURS).
    public let disabledCapabilities: Set<String>

    public init(capabilities: Set<String>?, permissions: Set<String>, cash: CashCustodyPolicyValues? = nil,
                hours: CustomerHoursPolicyValues? = nil, disabledCapabilities: Set<String> = []) {
        self.capabilities = capabilities
        self.permissions = permissions
        self.cash = cash
        self.hours = hours
        self.disabledCapabilities = disabledCapabilities
    }

    /// Customer hours are on: not switched off in `/me` and the cached CUSTOMER_HOURS policy enables them.
    public var customerHoursOn: Bool {
        !disabledCapabilities.contains(TenantCapability.customerHours) && hours?.enabled == true
    }

    /// Engine-hour controls are on (not switched off in `/me`): daily readings, baselines, corrections.
    public var engineHoursOn: Bool { !disabledCapabilities.contains(TenantCapability.engineHours) }

    /// The DEC-030 cash additions are on (not switched off in `/me`): transfers, acknowledgements, retentions,
    /// recording for others. Collections, remittances and floats stay either way.
    public var cashCustodyOn: Bool { !disabledCapabilities.contains(TenantCapability.cashCustody) }

    private func supports(_ capability: String) -> Bool { capabilities?.contains(capability) == true }
    private func can(_ permission: String) -> Bool { permissions.contains(permission) }

    public var sellHours: Bool { supports(SyncCapability.hoursPurchase) && can(Self.hoursPurchase) && customerHoursOn }
    public var walkIn: Bool { sellHours && hours?.walkInAllowed == true }
    public var requestHoursTransfer: Bool {
        supports(SyncCapability.hoursTransferRequest) && can(Self.hoursTransfer) && customerHoursOn
    }
    public var transferCash: Bool { supports(SyncCapability.cashTransfer) && can(Self.collectionRecord) && cashCustodyOn }
    public var acknowledgeCash: Bool { transferCash }
    /// A recorder may name another cash holder (collections, remittances, sales, transfers).
    public var recordForOthers: Bool {
        can(Self.collectionRecord) && cashCustodyOn && cash?.recordersMayRecordForOthers == true
    }
    public var askToKeepCash: Bool { can(Self.collectionRecord) && cashCustodyOn && cash?.retentionAllowed == true }
    /// "Ask to keep cash" is queued in the outbox (works offline) when the server takes `CASH_RETENTION_REQUEST`;
    /// otherwise it is sent online as before.
    public var retentionOffline: Bool { askToKeepCash && supports(SyncCapability.cashRetentionRequest) }
    /// DEC-031 D2: the hand-over form offers method, deposit account and slip photos (server REMITTANCE_DETAILS_V1).
    public var remittanceDetails: Bool { supports(SyncCapability.remittanceDetails) }
    /// The tenant's remittance requirements; all off without the capability, while CASH_CUSTODY is switched off,
    /// or while the policy is unknown.
    public var remittanceRequirements: RemittanceRequirements {
        guard remittanceDetails, cashCustodyOn, let cash else { return RemittanceRequirements() }
        return RemittanceRequirements(account: cash.remittanceAccountRequired, reference: cash.remittanceReferenceRequired,
                                      evidence: cash.remittanceEvidenceRequired)
    }
    public var dailyReading: Bool { supports(SyncCapability.meterDailyReading) && can(Self.meterCapture) && engineHoursOn }
    public var proposeBaseline: Bool { supports(SyncCapability.meterBaseline) && can(Self.meterCapture) && engineHoursOn }
    public var proposeCorrection: Bool { supports(SyncCapability.meterCorrection) && can(Self.meterCapture) && engineHoursOn }

    public static let hoursPurchase = "tenant.hours.purchase"
    public static let hoursTransfer = "tenant.hours.transfer"
    public static let hoursRead = "tenant.hours.read"
    public static let collectionRecord = "tenant.collection.record"
    public static let meterCapture = "tenant.meter.capture"
}

/// The hours-sale form as typed (validated by ``AccountabilityRules/hoursSale(_:walkInAllowed:)``).
public struct HoursSaleDraft: Sendable, Equatable {
    public var walkIn = false
    public var customerID: UUID?
    public var walkInName = ""
    public var walkInPhone = ""
    public var machineID: UUID?
    public var hoursText = ""
    public var paidNow = true
    public var method = "CASH"
    public var amountText = ""
    public var reference = ""
    public var note = ""

    public init() {}
}

public struct HoursSaleValues: Sendable, Equatable {
    public let hours: Decimal
    public let amount: Decimal?
    public let reference: String?
    public let walkInName: String?
    public let walkInPhone: String?
    public let note: String?
}

/// Offline checks of the accountability forms (wording in ``FieldAccountabilityTexts``; the server re-validates).
/// Same rules as Android `AccountabilityRules`. Each returns the values, or every problem found.
public enum AccountabilityRules {
    public static let maxNote = 1000
    public static let maxReference = 120
    public static let minReason = 3
    public static let minCorrectionReason = 10
    public static let minPhone = 3
    public static let maxName = 200
    public static let maxPhone = 40
    public static let maxEvidence = 10
    static let hoursDecimals = 2
    static let moneyDecimals = ExpenseRules.moneyDecimals

    public typealias Check<Value> = Result<Value, Problems>

    public struct Problems: Error, Equatable, Sendable {
        public let messages: [String]
        public var text: String { messages.joined(separator: "\n") }
    }

    static func value(_ text: String, decimals: Int, allowZero: Bool = false) -> Decimal? {
        if case let .success(value) = DecimalInput.parse(text, maxFractionDigits: decimals, allowZero: allowZero) { return value }
        return nil
    }

    static func trimmed(_ text: String, max: Int) -> String? {
        let value = String(text.trimmingCharacters(in: .whitespacesAndNewlines).prefix(max))
        return value.isEmpty ? nil : value
    }

    public static func hoursSale(_ d: HoursSaleDraft, walkInAllowed: Bool) -> Check<HoursSaleValues> {
        var m: [String] = []
        var name: String?, phone: String?
        if d.walkIn {
            if !walkInAllowed { m.append(FieldAccountabilityTexts.hoursErrWalkInOff) }
            name = trimmed(d.walkInName, max: maxName)
            if name == nil { m.append(FieldAccountabilityTexts.hoursErrWalkInName) }
            phone = trimmed(d.walkInPhone, max: Int.max)
            if let p = phone, p.count < minPhone || p.count > maxPhone { m.append(FieldAccountabilityTexts.hoursErrPhone) }
        } else if d.customerID == nil {
            m.append(FieldAccountabilityTexts.hoursErrCustomer)
        }
        if d.machineID == nil { m.append(FieldAccountabilityTexts.hoursErrMachine) }
        let hours = value(d.hoursText, decimals: hoursDecimals)
        if hours == nil { m.append(FieldAccountabilityTexts.hoursErrHours) }
        var amount: Decimal?, reference: String?
        if d.paidNow {
            amount = value(d.amountText, decimals: moneyDecimals)
            if amount == nil { m.append(FieldAccountabilityTexts.hoursErrAmount) }
            reference = trimmed(d.reference, max: maxReference)
            if d.method != "CASH" && reference == nil { m.append(FieldAccountabilityTexts.hoursErrReference) }
        }
        guard m.isEmpty, let hours else { return .failure(Problems(messages: m)) }
        return .success(HoursSaleValues(hours: hours, amount: amount, reference: reference, walkInName: name,
                                        walkInPhone: phone, note: trimmed(d.note, max: maxNote)))
    }

    /// `remaining`: hours left on the purchase (on `fromMachineID`), nil when unknown.
    public static func hoursTransfer(purchaseID: UUID?, fromMachineID: UUID?, toMachineID: UUID?, hoursText: String,
                                     remaining: Decimal?, reason: String, reasonCodeID: UUID?,
                                     reasonCodeRequired: Bool) -> Check<(hours: Decimal, reason: String)> {
        var m: [String] = []
        if purchaseID == nil { m.append(FieldAccountabilityTexts.transferErrPurchase) }
        if toMachineID == nil {
            m.append(FieldAccountabilityTexts.transferErrMachine)
        } else if toMachineID == fromMachineID {
            m.append(FieldAccountabilityTexts.transferErrSameMachine)
        }
        let hours = value(hoursText, decimals: hoursDecimals)
        if hours == nil {
            m.append(FieldAccountabilityTexts.transferErrHours)
        } else if let remaining, let hours, hours > remaining {
            m.append(FieldAccountabilityTexts.transferErrTooMany(plain(remaining)))
        }
        let text = reason.trimmingCharacters(in: .whitespacesAndNewlines)
        if text.count < minReason { m.append(FieldAccountabilityTexts.transferErrReason) }
        if reasonCodeRequired && reasonCodeID == nil { m.append(FieldAccountabilityTexts.transferErrCategory) }
        guard m.isEmpty, let hours else { return .failure(Problems(messages: m)) }
        return .success((hours, String(text.prefix(maxNote))))
    }

    /// `receiverIsMe` with `selfAck`: the recorder receives the cash and must say how much arrived.
    public static func cashTransfer(fromID: UUID?, toID: UUID?, amountText: String, currency: String, receiverIsMe: Bool,
                                    selfAck: Bool, receivedText: String, note: String)
        -> Check<(amount: Decimal, currency: String, received: Decimal?, note: String?)> {
        var m: [String] = []
        if toID == nil {
            m.append(FieldAccountabilityTexts.cashTransferErrTo)
        } else if toID == fromID {
            m.append(FieldAccountabilityTexts.cashTransferErrSame)
        }
        let amount = value(amountText, decimals: moneyDecimals)
        if amount == nil { m.append(FieldAccountabilityTexts.cashTransferErrAmount) }
        let code = currency.trimmingCharacters(in: .whitespaces).uppercased()
        if !CurrencyCode.isValid(code) { m.append(FieldAccountabilityTexts.currencyError) }
        var received: Decimal?
        if receiverIsMe && selfAck {
            received = value(receivedText, decimals: moneyDecimals, allowZero: true)
            if received == nil { m.append(FieldAccountabilityTexts.cashTransferErrReceived) }
        }
        guard m.isEmpty, let amount else { return .failure(Problems(messages: m)) }
        return .success((amount, code, received, trimmed(note, max: maxNote)))
    }

    /// Acknowledge: the amount received (0 or more). Dispute: a reason is required.
    public static func acknowledgement(acknowledge: Bool, receivedText: String, note: String)
        -> Check<(received: Decimal?, note: String?)> {
        let text = trimmed(note, max: maxNote)
        if !acknowledge {
            guard let text else { return .failure(Problems(messages: [FieldAccountabilityTexts.ackErrReason])) }
            return .success((nil, text))
        }
        guard let received = value(receivedText, decimals: moneyDecimals, allowZero: true) else {
            return .failure(Problems(messages: [FieldAccountabilityTexts.ackErrReceived]))
        }
        return .success((received, text))
    }

    public static func retention(amountText: String, currency: String, reason: String)
        -> Check<(amount: Decimal, currency: String, reason: String)> {
        var m: [String] = []
        let amount = value(amountText, decimals: moneyDecimals)
        if amount == nil { m.append(FieldAccountabilityTexts.retentionErrAmount) }
        let code = currency.trimmingCharacters(in: .whitespaces).uppercased()
        if !CurrencyCode.isValid(code) { m.append(FieldAccountabilityTexts.currencyError) }
        let text = reason.trimmingCharacters(in: .whitespacesAndNewlines)
        if text.count < minReason { m.append(FieldAccountabilityTexts.retentionErrReason) }
        guard m.isEmpty, let amount else { return .failure(Problems(messages: m)) }
        return .success((amount, code, String(text.prefix(maxNote))))
    }

    public static func correctionReasonValid(_ reason: String) -> Bool {
        reason.trimmingCharacters(in: .whitespacesAndNewlines).count >= minCorrectionReason
    }

    /// Provisional hours (in use by running jobs) as plain text, nil when there are none (DEC-031 Phase 4).
    public static func inUse(_ value: Decimal) -> String? { value > 0 ? hoursNumber(value) : nil }

    /// An hours figure in the phone's number format: grouping, 0–2 decimals, no trailing zeros ("12", "1,234.5"); the
    /// same rule as the Owner app and Android (strings doc "DEC-031 Phase 5", hours parity).
    public static func hoursNumber(_ value: Decimal, locale: Locale = .current) -> String {
        value.formatted(.number.precision(.fractionLength(0...2)).rounded(rule: .toNearestOrEven).locale(locale))
    }

    /// Plain decimal text without trailing zeros ("12.50" -> "12.5").
    public static func plain(_ value: Decimal) -> String {
        var v = value
        var rounded = Decimal()
        NSDecimalRound(&rounded, &v, 6, .plain)
        return DecimalString(rounded).description
    }

    /// The walk-in's client id: derived from the sale's client id (name-based UUID, as Android
    /// `UUID.nameUUIDFromBytes("walk-in:<client id>")`), so a replay of the sale returns the same customer.
    public static func walkInClientID(saleClientID: UUID) -> UUID {
        var bytes = Array(Insecure.MD5.hash(data: Data("walk-in:\(saleClientID.uuidString.lowercased())".utf8)))
        bytes[6] = (bytes[6] & 0x0F) | 0x30
        bytes[8] = (bytes[8] & 0x3F) | 0x80
        return UUID(uuid: (bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
                           bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13], bytes[14], bytes[15]))
    }
}

extension FieldRecorder {
    /// Capabilities the server advertised on the last pull (nil before the first sync).
    public func serverCapabilities() -> Set<String>? {
        guard let text = try? store.syncState.value(SyncKey.capabilities, tenant: tenantID.uuidString.lowercased()) else { return nil }
        return Set(text.split(separator: ",").map(String.init))
    }

    /// Nil when the server advertises `capability`, else why the action is unavailable.
    public func unavailable(_ capability: String) -> String? {
        guard let capabilities = serverCapabilities() else { return FieldAccountabilityTexts.needsRules }
        return capabilities.contains(capability) ? nil : FieldAccountabilityTexts.serverTooOld
    }

    func requireCapability(_ capability: String) throws {
        if let blocked = unavailable(capability) { throw FieldRecorderError.notAllowed(blocked) }
    }

    /// An operation of `type` for this record/form is already on this phone (one answer per transfer/float).
    public func alreadySaved(_ type: OperationType, clientID: UUID) throws -> Bool {
        try store.outbox.operations(tenantID: tenantID, owner: owner?.subject, statuses: Set(ClientOperationStatus.allCases))
            .contains { $0.opType == type.rawValue && $0.entityID == clientID }
    }

    static func invalid(_ problems: AccountabilityRules.Problems) -> FieldRecorderError { .invalid(problems.text) }

    // MARK: - Customer hours

    /// Queues an `HOURS_PURCHASE` (registered customer or walk-in) with the payment taken now and its evidence photos.
    /// `clientID` (one per form visit) is the purchase's idempotency key. `cashHolderID` is the cash holder when the
    /// recorder records for another custodian (cash only). The payment stays CLAIMED until someone else verifies it.
    @discardableResult
    public func recordHoursSale(_ draft: HoursSaleDraft, walkInAllowed: Bool, cashHolderID: UUID?, evidence: [StoredEvidence],
                                receivedAt: Date, clientID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.hoursPurchase)
        let values: HoursSaleValues
        switch AccountabilityRules.hoursSale(draft, walkInAllowed: walkInAllowed) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(checked): values = checked
        }
        if !draft.walkIn, let customer = draft.customerID {
            let entity = try store.syncState.entity(type: "customer", id: customer, tenantID: tenantID)
            let active = entity.flatMap { try? JSONValue.parse($0.json) }?["is_active"]?.boolValue != false
            guard entity != nil, active else { throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.customerGone) }
        }
        guard let machineID = draft.machineID, try store.syncState.entity(type: "machine", id: machineID, tenantID: tenantID) != nil else {
            throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.machineMissing)
        }
        guard evidence.count <= AccountabilityRules.maxEvidence else {
            throw FieldRecorderError.invalid(FieldAccountabilityTexts.tooManyEvidence)
        }
        if try alreadySaved(.hoursPurchase, clientID: clientID) { throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved) }
        let payment = draft.paidNow ? PurchasePaymentPayload(
            method: draft.method, amount: values.amount, receivedAt: receivedAt, reference: values.reference, note: nil,
            staffMemberID: draft.method == "CASH" ? cashHolderID : nil) : nil
        let walkIn = draft.walkIn ? WalkInCustomerPayload(clientID: AccountabilityRules.walkInClientID(saleClientID: clientID),
                                                          name: values.walkInName ?? "", phone: values.walkInPhone) : nil
        return try store.database.transaction {
            let locals = try evidence.map { try addAttachment($0, purpose: .paymentEvidence) }
            let payload = HoursPurchasePayload(clientID: clientID, machineID: machineID, hours: values.hours,
                                               customerID: draft.walkIn ? nil : draft.customerID, walkIn: walkIn,
                                               jobSiteID: nil, note: values.note, payment: payment)
            return try enqueue(.hoursPurchase, entityType: "hours_purchase", entityID: clientID, payload: payload,
                               dependsOn: [], attachments: locals.map { ($0, .evidenceUploads) }, createdAt: receivedAt)
        }
    }

    /// Queues an `HOURS_TRANSFER_REQUEST`: remaining hours of a purchase to another machine (approved per policy).
    @discardableResult
    public func requestHoursTransfer(purchaseID: UUID?, fromMachineID: UUID?, toMachineID: UUID?, hoursText: String,
                                     remaining: Decimal?, reason: String, reasonCodeID: UUID?, reasonCodeRequired: Bool,
                                     at date: Date = Date(), clientID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.hoursTransferRequest)
        let values: (hours: Decimal, reason: String)
        switch AccountabilityRules.hoursTransfer(purchaseID: purchaseID, fromMachineID: fromMachineID, toMachineID: toMachineID,
                                                 hoursText: hoursText, remaining: remaining, reason: reason,
                                                 reasonCodeID: reasonCodeID, reasonCodeRequired: reasonCodeRequired) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(checked): values = checked
        }
        guard let purchaseID, let toMachineID else { throw FieldRecorderError.invalid(FieldAccountabilityTexts.transferErrPurchase) }
        if try alreadySaved(.hoursTransferRequest, clientID: clientID) {
            throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved)
        }
        let payload = HoursTransferPayload(clientID: clientID, purchaseID: purchaseID, fromMachineID: fromMachineID,
                                           toMachineID: toMachineID, hours: values.hours, reason: values.reason,
                                           reasonCodeID: reasonCodeID)
        return try enqueue(.hoursTransferRequest, entityType: "hours_transfer", entityID: clientID, payload: payload,
                           dependsOn: [], createdAt: date)
    }

    // MARK: - Cash custody

    /// Queues a `CASH_TRANSFER` (nil `fromStaffID` = me). `selfAck`: the tenant counts recording a transfer you
    /// receive as its acknowledgement, so the amount actually received is required then.
    @discardableResult
    public func recordCashTransfer(fromStaffID: UUID?, toStaffID: UUID?, myStaffID: UUID?, amountText: String,
                                   currency: String, selfAck: Bool, receivedText: String, note: String,
                                   transferredAt: Date, clientID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.cashTransfer)
        let from = fromStaffID ?? myStaffID
        let receiverIsMe = toStaffID != nil && toStaffID == myStaffID
        let values: (amount: Decimal, currency: String, received: Decimal?, note: String?)
        switch AccountabilityRules.cashTransfer(fromID: from, toID: toStaffID, amountText: amountText, currency: currency,
                                                receiverIsMe: receiverIsMe, selfAck: selfAck, receivedText: receivedText,
                                                note: note) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(checked): values = checked
        }
        guard let toStaffID else { throw FieldRecorderError.invalid(FieldAccountabilityTexts.cashTransferErrTo) }
        if try alreadySaved(.cashTransfer, clientID: clientID) { throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved) }
        let payload = CashTransferPayload(clientID: clientID, fromStaffID: fromStaffID == myStaffID ? nil : fromStaffID,
                                          toStaffID: toStaffID, amount: values.amount, amountReceived: values.received,
                                          currency: values.currency, transferredAt: transferredAt, note: values.note)
        return try enqueue(.cashTransfer, entityType: "cash_transfer", entityID: clientID, payload: payload, dependsOn: [],
                           createdAt: transferredAt)
    }

    /// Queues the receiver's answer to a transfer (`isFloat` false) or a float: acknowledged with the amount received,
    /// or disputed with a reason. One answer per transfer/float on this phone.
    @discardableResult
    public func acknowledgeCash(targetID: UUID, isFloat: Bool, acknowledge: Bool, receivedText: String, note: String,
                                at date: Date = Date()) throws -> ClientOperation {
        try requireCapability(SyncCapability.cashTransfer)
        let values: (received: Decimal?, note: String?)
        switch AccountabilityRules.acknowledgement(acknowledge: acknowledge, receivedText: receivedText, note: note) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(checked): values = checked
        }
        let type: OperationType = isFloat ? .cashFloatAcknowledgement : .cashTransferAcknowledgement
        if try alreadySaved(type, clientID: targetID) { throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved) }
        let payload = CashAcknowledgementPayload(transferID: isFloat ? nil : targetID, entryID: isFloat ? targetID : nil,
                                                 acknowledged: acknowledge, amountReceived: values.received, note: values.note)
        return try enqueue(type, entityType: isFloat ? "cash_float" : "cash_transfer_ack", entityID: targetID,
                           payload: payload, dependsOn: [], createdAt: date)
    }

    /// Queues a `CASH_RETENTION_REQUEST` (ask to keep cash; someone else decides). `clientID` (one per form visit) is
    /// the request's idempotency key, so a replay returns the same request. `staffMemberID` nil = me.
    @discardableResult
    public func requestRetention(amountText: String, currency: String, reason: String, reasonID: UUID?,
                                 staffMemberID: UUID?, validUntil: Date?, at date: Date = Date(),
                                 clientID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.cashRetentionRequest)
        let values: (amount: Decimal, currency: String, reason: String)
        switch AccountabilityRules.retention(amountText: amountText, currency: currency, reason: reason) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(checked): values = checked
        }
        if try alreadySaved(.cashRetentionRequest, clientID: clientID) {
            throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved)
        }
        let payload = CashRetentionIn(amount: values.amount, currency: values.currency, reason: values.reason, reasonID: reasonID,
                                      staffMemberID: staffMemberID, validUntil: validUntil, clientID: clientID)
        return try enqueue(.cashRetentionRequest, entityType: "cash_retention", entityID: clientID, payload: payload,
                           dependsOn: [], createdAt: date)
    }

    // MARK: - Meter (engine hours)

    /// Queues a DAILY reading of a machine outside a job (`METER_CAPTURE` kind DAILY, job_id null, machine_id set),
    /// with the same evidence rules as a closing reading.
    @discardableResult
    public func recordDailyReading(machineID: UUID, mode: CaptureMode, reading: String, ocr: MeterOCRResult?,
                                   photo: StoredEvidence?, gps: GpsPayload, capturedAt: Date, snapshot: MeterPolicySnapshot,
                                   captureID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.meterDailyReading)
        guard try store.syncState.entity(type: "machine", id: machineID, tenantID: tenantID) != nil else {
            throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.machineMissing)
        }
        return try store.database.transaction {
            let photoLocal = try photo.map { try addAttachment($0, purpose: .meterPhoto) }
            let payload = capturePayload(id: captureID, jobID: nil, machineID: machineID, kind: .daily, mode: mode,
                                         reading: reading, ocr: ocr, gps: gps, capturedAt: capturedAt, snapshot: snapshot)
            return try enqueue(.meterCapture, entityType: "meter_capture", entityID: captureID, payload: payload,
                               dependsOn: [], attachments: photoLocal.map { [($0, .photo)] } ?? [], createdAt: capturedAt)
        }
    }

    /// Queues a `METER_BASELINE` proposal (a second person approves it). The operation id is the baseline id.
    @discardableResult
    public func proposeBaseline(machineID: UUID, reading: String, photo: StoredEvidence?, gps: GpsPayload,
                                note: String?, capturedAt: Date, baselineID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.meterBaseline)
        guard try store.syncState.entity(type: "machine", id: machineID, tenantID: tenantID) != nil else {
            throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.machineMissing)
        }
        if try alreadySaved(.meterBaseline, clientID: baselineID) { throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved) }
        return try store.database.transaction {
            let photoLocal = try photo.map { try addAttachment($0, purpose: .meterPhoto) }
            let payload = MeterBaselinePayload(id: baselineID, machineID: machineID, reading: reading, capturedAt: capturedAt,
                                               gps: gps, deviceID: deviceID,
                                               note: AccountabilityRules.trimmed(note ?? "", max: AccountabilityRules.maxNote))
            return try enqueue(.meterBaseline, entityType: "meter_baseline", entityID: baselineID, payload: payload,
                               dependsOn: [], attachments: photoLocal.map { [($0, .photo)] } ?? [], createdAt: capturedAt,
                               operationID: baselineID)
        }
    }

    /// Queues a `METER_CORRECTION`: a replacement for one of my readings the server has and still counts (same kind,
    /// job and machine), with a reason of 10+ characters; a second person approves it.
    @discardableResult
    public func proposeCorrection(of reading: ReadingItem, machineID: UUID, mode: CaptureMode, value: String,
                                  ocr: MeterOCRResult?, photo: StoredEvidence?, gps: GpsPayload, capturedAt: Date,
                                  reason: String, snapshot: MeterPolicySnapshot, replacementID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.meterCorrection)
        if let blocked = Self.correctionBlocked(reading) { throw FieldRecorderError.notAllowed(blocked) }
        guard let kind = ReadingKind(rawValue: reading.kind) else {
            throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.meterCorrectionNotLive)
        }
        guard AccountabilityRules.correctionReasonValid(reason) else {
            throw FieldRecorderError.invalid(FieldAccountabilityTexts.meterErrCorrectionReason)
        }
        let why = String(reason.trimmingCharacters(in: .whitespacesAndNewlines).prefix(2000))
        if try alreadySaved(.meterCorrection, clientID: replacementID) { throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved) }
        return try store.database.transaction {
            let photoLocal = try photo.map { try addAttachment($0, purpose: .meterPhoto) }
            let replacement = capturePayload(id: replacementID, jobID: reading.jobID, machineID: machineID, kind: kind,
                                             mode: mode, reading: value, ocr: ocr, gps: gps, capturedAt: capturedAt,
                                             snapshot: snapshot)
            let payload = MeterCorrectionPayload(supersededCaptureID: reading.id, reason: why, replacement: replacement)
            return try enqueue(.meterCorrection, entityType: "meter_correction", entityID: replacementID, payload: payload,
                               dependsOn: [], attachments: photoLocal.map { [($0, .replacementPhoto)] } ?? [],
                               createdAt: capturedAt)
        }
    }

    /// Why a reading cannot be corrected (not yet on the server, or no longer counted), else nil.
    public static func correctionBlocked(_ reading: ReadingItem) -> String? {
        guard let server = reading.server else { return FieldAccountabilityTexts.meterCorrectionNotSynced }
        guard server.state == "ACCEPTED" || server.state == "PROVISIONAL" else { return FieldAccountabilityTexts.meterCorrectionNotLive }
        return nil
    }

    func capturePayload(id: UUID, jobID: UUID?, machineID: UUID?, kind: ReadingKind, mode: CaptureMode, reading: String,
                        ocr: MeterOCRResult?, gps: GpsPayload, capturedAt: Date, snapshot: MeterPolicySnapshot) -> MeterCapturePayload {
        MeterCapturePayload(
            id: id, jobID: jobID, machineID: machineID, kind: kind, captureMode: mode, reading: reading,
            ocrRawText: ocr.map { String($0.rawText.prefix(500)) }, ocrValue: ocr?.value,
            ocrConfidence: ocr.map { ($0.confidence * 1000).rounded() / 1000 }, ocrEngine: ocr?.engine,
            photoAttachmentID: nil, gps: gps, deviceID: deviceID, capturedAt: capturedAt, policyVersionIDs: snapshot.versionIDs)
    }
}
