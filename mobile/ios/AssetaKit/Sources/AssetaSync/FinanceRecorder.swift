import AssetaCapture
import AssetaModel
import AssetaStore
import Foundation

/// Gate 5 field finance: expenses (with receipt photos), cash collections, cash handovers and fuel
/// events as durable outbox operations. Each carries a device-generated `client_id` (the server's
/// exactly-once key, besides the operation id). An expense with receipts is never sent before every
/// receipt upload has completed; the upload session ids are then written into `receipt_upload_ids`.
extension FieldRecorder {
    public static let maxReceipts = 10

    /// Records an expense under `snapshot` (the policy the screen enforced). Re-checks the policy so
    /// nothing that breaks it reaches the outbox. `receipts` must already be in the evidence store.
    @discardableResult
    public func recordExpense(_ draft: ExpenseDraft, receipts: [StoredEvidence], snapshot: ExpensePolicySnapshot,
                              baseCurrency: String?, incurredAt: Date, clientID: UUID = UUID()) throws -> ClientOperation {
        guard receipts.count <= Self.maxReceipts else {
            throw FieldRecorderError.invalid("At most \(Self.maxReceipts) receipt photos per expense")
        }
        var checked = draft
        checked.receiptCount = receipts.count
        let assessment = ExpenseRules.assess(checked, policy: snapshot.policy, baseCurrency: baseCurrency)
        if let issue = assessment.issues.first { throw FieldRecorderError.invalid(issue.description) }
        guard let categoryID = draft.categoryID, let amount = assessment.amount, let gps = draft.gps else {
            throw FieldRecorderError.invalid("The expense is incomplete")
        }
        return try store.database.transaction {
            let locals = try receipts.map { try addAttachment($0, purpose: .expenseReceipt) }
            let payload = ExpensePayload(
                clientID: clientID, categoryID: categoryID,
                description: FinanceRules.clean(draft.description, max: 2000) ?? "",
                amount: amount, currency: assessment.currency, incurredAt: incurredAt, paidFrom: draft.paidFrom,
                supplier: FinanceRules.clean(draft.supplier, max: 200), machineID: draft.jobID == nil ? draft.machineID : nil,
                jobID: draft.jobID, gps: gps, deviceID: deviceID)
            return try enqueue(.expense, entityType: "expense", entityID: clientID, payload: payload, dependsOn: [],
                               attachments: locals.map { ($0, .receiptUploads) }, createdAt: incurredAt)
        }
    }

    /// Cash received from a customer into the supervisor's custody (or, when the tenant lets recorders record for
    /// others, into `custodianID`'s custody). A job, when chosen, only helps
    /// pick the customer and is noted for the office (the collection itself has no job field); it must
    /// belong to the chosen customer (`jobCustomerID`, when the job's contract is known).
    @discardableResult
    public func recordCashCollection(customerID: UUID?, amountText: String, currency: String, reference: String?,
                                     note: String?, jobNumber: String? = nil, jobCustomerID: UUID? = nil,
                                     custodianID: UUID? = nil, receivedAt: Date,
                                     clientID: UUID = UUID()) throws -> ClientOperation {
        guard let customerID else { throw FieldRecorderError.invalid("Choose the customer who paid.") }
        if let jobNumber, let jobCustomerID, jobCustomerID != customerID {
            throw FieldRecorderError.invalid("Job \(jobNumber) belongs to another customer.")
        }
        let amount = try FinanceRules.amount(amountText)
        let jobNote = jobNumber.map { "Job \($0)" }
        let combined = [jobNote, FinanceRules.clean(note, max: 1000)].compactMap { $0 }.joined(separator: ". ")
        let payload = CashCollectionPayload(
            clientID: clientID, customerID: customerID, amount: amount, currency: try FinanceRules.currency(currency),
            receivedAt: receivedAt, reference: FinanceRules.clean(reference, max: 120),
            note: FinanceRules.clean(combined, max: 1000), staffMemberID: custodianID)
        return try enqueue(.cashCollection, entityType: "cash_collection", entityID: clientID, payload: payload,
                           dependsOn: [], createdAt: receivedAt)
    }

    /// Cash handed to the office; CLAIMED until finance verifies it. `method` (only when the server announces
    /// REMITTANCE_DETAILS_V1) adds how the money reached the company, the company account and the slip photos,
    /// checked against the tenant's `requirements`; the photos upload with purpose REMITTANCE_EVIDENCE and the op
    /// waits for them.
    @discardableResult
    public func recordCashHandover(amountText: String, currency: String, reference: String?, note: String?,
                                   custodianID: UUID? = nil, handedAt: Date, method: RemittanceMethod? = nil,
                                   depositAccountID: UUID? = nil,
                                   requirements: RemittanceRequirements = RemittanceRequirements(),
                                   evidence: [StoredEvidence] = [], clientID: UUID = UUID()) throws -> ClientOperation {
        let amount = try FinanceRules.amount(amountText)
        let code = try FinanceRules.currency(currency)
        if let method {
            // Details need a server that takes them (Android: SERVER_TOO_OLD).
            guard serverCapabilities()?.contains(SyncCapability.remittanceDetails) == true else {
                throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.serverTooOld)
            }
            let account = try depositAccountID.flatMap { try RemittanceRules.depositAccount($0, store: store, tenantID: tenantID) }
            let problems = RemittanceRules.check(requirements, method: method, accountID: depositAccountID, account: account,
                                                 currency: code, reference: reference ?? "", photoCount: evidence.count)
            if let problem = problems.first { throw FieldRecorderError.invalid(problem) }
        } else if depositAccountID != nil || !evidence.isEmpty {
            throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.serverTooOld)
        }
        if !evidence.isEmpty, try alreadySaved(.cashHandover, clientID: clientID) {
            throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved)
        }
        return try store.database.transaction {
            let locals = try evidence.map { try addAttachment($0, purpose: .remittanceEvidence) }
            let payload = CashHandoverPayload(
                clientID: clientID, amount: amount, currency: code, handedAt: handedAt,
                reference: FinanceRules.clean(reference, max: 120), note: FinanceRules.clean(note, max: 1000),
                staffMemberID: custodianID, method: method, depositAccountID: depositAccountID,
                // With details the key is always sent (empty, filled as each photo upload completes), as Android.
                evidenceUploadIDs: method == nil ? nil : [])
            return try enqueue(.cashHandover, entityType: "cash_handover", entityID: clientID, payload: payload,
                               dependsOn: [], attachments: locals.map { ($0, .evidenceUploads) }, createdAt: handedAt)
        }
    }

    @discardableResult
    public func recordFuelEvent(type: FuelEventType, litres: String, unitPrice: String, currency: String,
                                machineID: UUID?, jobID: UUID?, meterReading: String, supplier: String?, note: String?,
                                occurredAt: Date, clientID: UUID = UUID()) throws -> ClientOperation {
        let issues = FinanceRules.fuelIssues(type: type, litres: litres, unitPrice: unitPrice, meterReading: meterReading,
                                             machineID: machineID, jobID: jobID)
        if let issue = issues.first { throw FieldRecorderError.invalid(issue) }
        let litresValue = try FinanceRules.amount(litres, what: "Litres", decimals: FinanceRules.litresDecimals)
        var price: Decimal?
        var currencyCode: String?
        if type != .usage {
            price = try FinanceRules.amount(unitPrice, what: "Unit price", decimals: FinanceRules.unitPriceDecimals,
                                            allowZero: true)
            currencyCode = try FinanceRules.currency(currency)
        }
        var meter: Decimal?
        if !meterReading.trimmingCharacters(in: .whitespaces).isEmpty {
            meter = try FinanceRules.amount(meterReading, what: "Meter reading", decimals: FinanceRules.meterDecimals,
                                            allowZero: true)
        }
        let payload = FuelEventPayload(
            clientID: clientID, eventType: type, litres: litresValue, unitPrice: price,
            currency: currencyCode,
            machineID: jobID == nil ? machineID : nil, jobID: jobID, meterReading: meter,
            supplier: FinanceRules.clean(supplier, max: 200), occurredAt: occurredAt, note: FinanceRules.clean(note, max: 1000))
        return try enqueue(.fuelEvent, entityType: "fuel_event", entityID: clientID, payload: payload, dependsOn: [],
                           createdAt: occurredAt)
    }
}
