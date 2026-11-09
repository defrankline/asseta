import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

// DEC-032 Phase 2 in the Owner app (strings doc "DEC-032 Phase 2 — adjustments"): proposed hours corrections, refunds,
// reversals and invoice voids under Approvals, decided on the generic decision screen (`DecisionKind.adjustmentRequest`),
// withdrawn by their proposer. Actions are online only; reads may come from the encrypted snapshot cache.

/// `tenant.adjustment.*`: approvals by permission, never by role.
public enum AdjustmentPermission {
    public static let read = "tenant.adjustment.read"
    public static let propose = "tenant.adjustment.propose"
    public static let decide = "tenant.adjustment.decide"
}

/// Wording copied exactly from `docs/requirements/accountability-mobile-strings.md` (owner.adjust.*).
public enum AdjustmentTexts {
    public static let section = "Adjustments"
    public static let empty = "No adjustments waiting."
    public static let title = "Adjustment request"
    public static let fieldType = "Type"
    public static let reference = "Reference"
    public static let customer = "Customer"
    public static let machine = "Machine"
    public static let purchase = "Purchase"
    public static let hours = "Hours"
    public static let amount = "Amount"
    public static let settlementLabel = "Settlement"
    public static let reasonCategory = "Reason category"
    public static let withdrawnReason = "Why it was withdrawn"
    public static let evidence = "Evidence"
    public static let effectsForecast = "If approved"
    public static let effectsActual = "What it did"
    public static func refused(_ reason: String) -> String { "This request can't be approved as it stands: \(reason)" }
    /// A `refused` code without its own wording.
    public static let refusedUnknown = "the record has changed. Reload to see it."

    public static let effectLotBeforeForecast = "Hours on the lot now"
    public static let effectLotBeforeActual = "Hours on the lot before"
    public static let effectLotAfter = "Hours on the lot after"
    public static let effectPurchaseRemaining = "Left on the purchase"
    public static let effectHoursRefunded = "Hours refunded"
    public static let effectValue = "Value of the hours"
    public static let effectSettlement = "Settlement"
    public static let effectPaymentAmount = "Payment amount"
    public static let effectUnusedRemoved = "Unused hours removed"
    public static let effectUsedHours = "Hours already used"
    public static let effectUsedKept = "Used hours kept"
    public static let effectMoneyOwed = "Money owed for hours already used"
    public static let effectTreatment = "For hours already used"
    public static let effectRecoveryInvoice = "Recovery invoice"
    public static let effectReleased = "Released from invoices"
    public static let effectMoneyReleased = "Released to credit"
    public static let effectCustomerBalance = "Customer balance"
    public static let effectCustodyAfter = "Custodian's cash after"
    public static func effectPurchaseLine(unused: String, used: String, owed: String) -> String {
        "\(unused) h removed · \(used) h used · \(owed) owed"
    }

    public static let withdraw = "Withdraw"
    public static let withdrawTitle = "Withdraw this request"
    public static let withdrawFooter = "Only the person who proposed a request can withdraw it."
    public static let withdrawLabel = "Why are you withdrawing it? (at least 3 characters)"
    public static let withdrawConfirm = "Withdraw this request?"
    public static let withdrawn = "Withdrawn."

    public static func type(_ wire: String) -> String {
        switch wire {
        case AdjustmentRequestTypes.hoursCorrection: "Hours correction"
        case AdjustmentRequestTypes.hoursRefund: "Hours refund"
        case AdjustmentRequestTypes.paymentReversal: "Payment reversal"
        case AdjustmentRequestTypes.collectionReversal: "Collection reversal"
        case AdjustmentRequestTypes.purchaseReversal: "Purchase reversal"
        case AdjustmentRequestTypes.invoiceVoid: "Invoice void"
        case AdjustmentRequestTypes.zeroAmountActivation: "Purchase with nothing to pay"
        default: OwnerFormat.humanize(wire)
        }
    }

    public static func settlement(_ wire: String) -> String {
        switch wire {
        case RefundSettlements.credit: "Credit to the customer"
        case RefundSettlements.payOut: "Paid out"
        default: OwnerFormat.humanize(wire)
        }
    }

    public static func treatment(_ wire: String) -> String {
        switch wire {
        case "RECEIVABLE": "Bill the customer"
        case "CASE": "Open an investigation case"
        default: OwnerFormat.humanize(wire)
        }
    }

    /// owner.adjust.error.*: nil for a code without its own wording.
    public static func error(_ code: String?) -> String? {
        switch code {
        case "SEGREGATION_OF_DUTIES": "You proposed this request, so someone else must decide it."
        case "ALREADY_DECIDED": "This request was already decided or withdrawn. Reload to see it."
        case "NOT_PROPOSER": "Only the person who proposed this request can withdraw it."
        case "REVERSAL_EXISTS": "A reversal of this record is already waiting or done."
        case "REVERSAL_TYPE_MISMATCH": "This record can't be reversed this way."
        case "NOTHING_TO_REVERSE": "There is nothing left to reverse on this record."
        case "PURCHASE_CANCELLED": "This purchase is cancelled."
        case "HOURS_CORRECTION_INVALID": "The hours of this correction are not valid."
        case "HOURS_CORRECTION_NEGATIVE": "This correction would take the hours below zero."
        case "HOURS_CORRECTION_EXCEEDS_LOT": "This correction would lift the purchase above its activated hours."
        case "HOURS_CORRECTION_EXCEEDS_ENTRY": "This correction is more than the entry it corrects."
        case "CONSUMED_ENTRY_NOT_FOUND": "The usage entry this correction names is no longer on the purchase."
        case "REFUND_NOT_ALLOWED": "Your company has switched refunds off."
        case "HOURS_REFUND_INVALID": "The hours of this refund are not valid."
        case "EXCEEDS_REMAINING_HOURS": "This refund is more than the unused hours left on the machine."
        case "REFUND_EXCEEDS_PAID": "This refund is more than the verified money on the purchase."
        case "STAFF_NOT_FOUND": "The person named to pay out this refund is no longer on record."
        case "PAYMENT_NOT_VERIFIED": "Only a verified payment can be reversed."
        case "PAYMENT_ALREADY_REVERSED": "This payment is already reversed."
        case "PAYMENT_REVERSED": "This payment has been reversed."
        case "INVOICE_NOT_ISSUED": "Only an issued invoice can be voided."
        case "PURCHASE_NOT_ZERO_AMOUNT": "This purchase has an amount to pay."
        case "ALREADY_ACTIVATED": "This purchase is already activated."
        case "ZERO_AMOUNT_PENDING": "A request for this purchase already waits for a decision."
        default: nil
        }
    }
}

/// What approving a request would do (while PROPOSED) or did (once decided). Empty hides the card.
public struct AdjustmentEffects: Hashable, Sendable {
    public let title: String
    public let rows: [DecisionField]
    /// Why the request can't be approved as it stands. Approve stays available: the server decides when it is pressed.
    public let refused: String?

    public var isEmpty: Bool { rows.isEmpty && refused == nil }
}

/// Input rules of a withdrawal and who is offered it.
public enum AdjustmentRules {
    public static let withdrawMin = 3, withdrawMax = 1000

    public static func canWithdraw(reason: String) -> Bool {
        let n = reason.trimmingCharacters(in: .whitespacesAndNewlines).count
        return n >= withdrawMin && n <= withdrawMax
    }

    /// Only the proposer, with `tenant.adjustment.propose`, while the request still waits.
    public static func offersWithdraw(_ r: AdjustmentRequestDTO, userID: UUID?, permissions: [String]) -> Bool {
        r.status == AdjustmentRequestStatuses.proposed && userID != nil && r.proposedBy == userID
            && permissions.contains(AdjustmentPermission.propose)
    }

    public static func message(for error: any Error) -> String {
        AdjustmentTexts.error((error as? APIError)?.code) ?? DecisionErrorText.message(for: error)
    }
}

/// One adjustment request on the decision list and screen.
public enum AdjustmentPresentation {
    typealias T = AdjustmentTexts
    typealias O = OwnerAccountabilityTexts

    private static func money(_ value: Decimal, _ currency: String?) -> String {
        OwnerFormat.money(value, currency: currency ?? "").trimmingCharacters(in: .whitespaces)
    }

    /// "+2 h" / "-2 h".
    static func signedHours(_ value: DecimalString) -> String {
        (value.value > 0 ? "+" : "") + OwnerFormat.hours(value)
    }

    /// The figure of a request: signed hours (correction), hours (refund), money (reversals), nothing (invoice void).
    static func figure(_ r: AdjustmentRequestDTO) -> String? {
        switch r.requestType {
        case AdjustmentRequestTypes.hoursCorrection: r.hours.map(signedHours)
        case AdjustmentRequestTypes.hoursRefund: r.hours.map { OwnerFormat.hours($0) }
        case AdjustmentRequestTypes.invoiceVoid: nil
        case AdjustmentRequestTypes.zeroAmountActivation: r.hours.map { OwnerFormat.hours($0) }
        default: r.amount.map { money($0.value, r.currency) }
        }
    }

    /// "{type} · {amount}".
    public static func headline(_ r: AdjustmentRequestDTO) -> String {
        [T.type(r.requestType), figure(r)].compactMap { $0 }.joined(separator: " · ")
    }

    /// "{customer} · {machine}", each only when present; nil when neither is.
    public static func subtitle(_ r: AdjustmentRequestDTO) -> String? {
        let parts = [DisplayName.optional(r.customerName, id: r.customerID),
                     r.machineCode ?? r.machineName ?? r.machineID.map(DisplayName.shortID)].compactMap { $0 }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    private static func machine(_ r: AdjustmentRequestDTO) -> String? {
        guard let id = r.machineID else { return r.machineCode ?? r.machineName }
        return DisplayName.machine(code: r.machineCode, name: r.machineName, id: id)
    }

    static func decision(_ r: AdjustmentRequestDTO) -> PendingDecision {
        let proposer = DisplayName.optional(r.proposedByName, id: r.proposedBy)
        let hours: String? = r.requestType == AdjustmentRequestTypes.hoursCorrection
            ? r.hours.map(signedHours) : r.hours.map { OwnerFormat.hours($0) }
        let rows: [(String, String?)] = [
            (VarianceTexts.number, r.requestNumber), (T.fieldType, T.type(r.requestType)), (T.reference, r.originalReference),
            (T.customer, DisplayName.optional(r.customerName, id: r.customerID)), (T.machine, machine(r)),
            (T.purchase, r.purchaseNumber), (T.hours, hours),
            (T.amount, r.amount.map { money($0.value, r.currency) }), (T.settlementLabel, r.settlement.map(T.settlement)),
            (T.reasonCategory, r.reasonLabel), (O.fieldProposedBy, proposer),
            (O.fieldDecidedBy, DisplayName.optional(r.decidedByName, id: r.decidedBy)),
            (r.status == AdjustmentRequestStatuses.withdrawn ? T.withdrawnReason : O.fieldDecisionNote, r.decisionNote),
        ]
        var item = PendingDecision(kind: .adjustmentRequest, recordID: r.id, headline: headline(r), status: r.status,
                                   proposedBy: r.proposedBy, proposedByName: proposer, proposedAt: r.proposedAt, reason: r.reason,
                                   fields: PendingDecision.fields(rows), machineID: r.machineID, photoAttachmentID: nil)
        item.subtitle = subtitle(r)
        return item
    }

    /// `effects` as rows: known keys only, in the documented order; zero rows hidden except the two lot rows.
    public static func effects(_ r: AdjustmentRequestDTO) -> AdjustmentEffects {
        let proposed = r.status == AdjustmentRequestStatuses.proposed
        let title = proposed ? T.effectsForecast : T.effectsActual
        if proposed, let code = r.effects["refused"]?.stringValue {
            return AdjustmentEffects(title: title, rows: [], refused: T.refused(T.error(code) ?? T.refusedUnknown))
        }
        let e = r.effects
        func number(_ key: String) -> Decimal? { e[key]?.decimalValue }
        func hours(_ key: String, _ label: String, keepZero: Bool = false) -> DecisionField? {
            guard let n = number(key), keepZero || n != 0 else { return nil }
            return DecisionField(label: label, value: OwnerFormat.hours(DecimalString(n)))
        }
        func cash(_ key: String, _ label: String) -> DecisionField? {
            guard let n = number(key), n != 0 else { return nil }
            return DecisionField(label: label, value: money(n, r.currency))
        }
        func text(_ key: String, _ label: String, _ map: (String) -> String = { $0 }) -> DecisionField? {
            guard let s = e[key]?.stringValue, !s.isEmpty else { return nil }
            return DecisionField(label: label, value: map(s))
        }
        // How used hours are treated only matters when a reversal actually touches some.
        let touchesUsed = (number("used_hours") ?? 0) != 0 || (number("money_owed") ?? 0) != 0
        var rows: [DecisionField?] = [
            hours("lot_hours_before", proposed ? T.effectLotBeforeForecast : T.effectLotBeforeActual, keepZero: true),
            hours("lot_hours_after", T.effectLotAfter, keepZero: true),
            hours("purchase_remaining", T.effectPurchaseRemaining), hours("hours_refunded", T.effectHoursRefunded),
            cash("value", T.effectValue), text("settlement", T.effectSettlement, T.settlement),
            cash("payment_amount", T.effectPaymentAmount), hours("unused_hours_removed", T.effectUnusedRemoved),
            hours("used_hours", T.effectUsedHours), hours("used_hours_kept", T.effectUsedKept), cash("money_owed", T.effectMoneyOwed),
            touchesUsed ? text("treatment", T.effectTreatment, T.treatment) : nil, text("recovery_invoice_number", T.effectRecoveryInvoice),
            cash("hire_allocations_released", T.effectReleased), cash("money_released_to_credit", T.effectMoneyReleased),
            cash("customer_balance", T.effectCustomerBalance), cash("custody_balance_after", T.effectCustodyAfter),
        ]
        if case let .array(purchases)? = e["purchases"] {
            rows += purchases.map { p in
                let unused = p["unused_hours"]?.decimalValue ?? 0, used = p["used_hours"]?.decimalValue ?? 0
                let label = p["purchase_number"]?.stringValue ?? p["purchase_id"]?.stringValue.flatMap(UUID.init(uuidString:)).map(DisplayName.shortID)
                return DecisionField(label: label ?? T.purchase,
                                     value: T.effectPurchaseLine(unused: OwnerFormat.hoursNumber(DecimalString(unused)),
                                                                 used: OwnerFormat.hoursNumber(DecimalString(used)),
                                                                 owed: money(p["money_owed"]?.decimalValue ?? 0, r.currency)))
            }
        }
        return AdjustmentEffects(title: title, rows: rows.compactMap { $0 }, refused: nil)
    }
}

extension OwnerFeatures {
    /// Approvals has nothing at all to show a role without expense requests or other sections, once every decision kind
    /// has loaded with nothing waiting ("Reaching Approvals" in the strings doc).
    public func nothingWaiting(waiting: [DecisionKind: Int], revenueWaiting: Int? = 0) -> Bool {
        !approvals && !jobs && !finance && !meterEvidence && decisionKinds.allSatisfy { waiting[$0] == 0 }
            && (!revenueRead || revenueWaiting == 0)
    }
}

extension SnapshotKey {
    public static func customerPayment(_ id: UUID) -> SnapshotKey { SnapshotKey("hours.payment.\(id.lowercased)") }
}

extension OwnerAPI {
    /// The proposer takes the request back (`reason` 3..1000 characters).
    public static func withdrawAdjustment(_ id: UUID, reason: String, idempotencyKey: UUID) throws -> APIRequest<JSONValue> {
        try .mutation(.post, "\(tenant)/adjustment-requests/\(id.lowercased)/withdraw",
                      body: AdjustmentWithdrawIn(reason: reason.trimmingCharacters(in: .whitespacesAndNewlines)),
                      idempotencyKey: idempotencyKey)
    }

    /// One customer payment (`tenant.finance.read` or `tenant.adjustment.read`): is it reversed?
    public static func customerPayment(_ id: UUID) -> APIRequest<CustomerPaymentDTO> {
        .get("\(tenant)/customer-payments/\(id.lowercased)")
    }
}
