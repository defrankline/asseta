import AssetaCapture
import AssetaModel
import AssetaNetwork
import AssetaStore
import Foundation

// DEC-033 petty cash on the Supervisor app (strings doc "DEC-033 — petty cash funds"; Android `PettyCashTexts`,
// `PettyCashRules`, `PettyCashRepository`, `PettyCashCapture`). The server's snapshot gives every figure; the phone
// queues the holder's answers and requests offline. The server re-checks every rule.

// MARK: - Gating and policy

extension FieldAccess {
    public static let pettyCashRead = "tenant.pettycash.read"
    public static let pettyCashCountPermission = "tenant.pettycash.count"

    /// Petty cash is on for this user: the server announces OP_PETTY_CASH, the role reads petty cash and the tenant has
    /// not switched PETTY_CASH off.
    public var pettyCash: Bool {
        supports(SyncCapability.pettyCash) && can(Self.pettyCashRead) && !disabledCapabilities.contains(TenantCapability.pettyCash)
    }

    /// Give an advance from a fund I hold (the screen also needs the policy's advances_enabled).
    public var pettyCashGiveAdvance: Bool { pettyCash && supports(SyncCapability.pettyCashAdvance) }

    /// Record a count of a fund I hold.
    public var pettyCashCount: Bool { pettyCash && can(Self.pettyCashCountPermission) }
}

/// The part of the tenant `PETTY_CASH` policy the field app needs (missing keys read as off / none).
public struct PettyCashPolicyValues: Sendable, Equatable {
    public static let policyType = "PETTY_CASH"
    public var countWitnessRequired = false
    public var returnEvidenceRequired = false
    public var advancesEnabled = false
    public var maxExpenseAmount: Decimal?
    /// An advance or expense above what the fund has is still recorded at sync (missing = on, the platform default).
    public var overspendAllowedOffline = true

    public init(countWitnessRequired: Bool = false, returnEvidenceRequired: Bool = false, advancesEnabled: Bool = false,
                maxExpenseAmount: Decimal? = nil, overspendAllowedOffline: Bool = true) {
        self.countWitnessRequired = countWitnessRequired
        self.returnEvidenceRequired = returnEvidenceRequired
        self.advancesEnabled = advancesEnabled
        self.maxExpenseAmount = maxExpenseAmount
        self.overspendAllowedOffline = overspendAllowedOffline
    }

    public init(values: JSONValue) {
        countWitnessRequired = values["count_witness_required"]?.boolValue ?? false
        returnEvidenceRequired = values["return_evidence_required"]?.boolValue ?? false
        advancesEnabled = values["advances_enabled"]?.boolValue ?? false
        maxExpenseAmount = values["max_expense_amount"]?.stringValue.flatMap(DecimalString.init(string:))?.value
        overspendAllowedOffline = values["overspend_allowed_offline"]?.boolValue ?? true
    }
}

// MARK: - Wording

/// Supervisor wording of petty cash, word for word as Android and the strings doc.
public enum PettyCashTexts {
    public static let section = "Petty cash"
    public static let row = "My petty cash"
    public static func rowWaiting(_ n: Int) -> String { "\(n) waiting for you" }
    public static let title = "My petty cash"
    public static let emptyTitle = "No petty cash fund"
    public static let emptyMessage = "Petty cash funds you hold appear here after a sync."
    public static func fundHeader(code: String, name: String) -> String { "\(code) · \(name)" }
    public static let balance = "Balance"
    public static let available = "Available to spend"
    public static let pendingSpending = "Expenses awaiting approval"
    public static let awaitingAck = "Money on its way to you"
    public static let returnsClaimed = "Returns awaiting confirmation"
    public static let limit = "Approved limit"
    public static let low = "Below the low-balance level"
    public static let lastCount = "Last count"
    public static let notCounted = "Not counted yet"
    public static let nextCount = "Next count due"
    public static func asOf(_ date: String) -> String { "As of \(date). Figures from the last sync." }
    public static let actionTopUp = "Request a top-up"
    public static let actionReturn = "Return money to the office"
    public static let actionCount = "Record a count"
    public static let actionGiveAdvance = "Give an advance"
    public static let waiting = "Waiting for you"
    public static func waitingFunding(number: String, amount: String) -> String { "Funding \(number) · \(amount)" }
    public static func waitingTopUp(number: String, amount: String) -> String { "Top-up \(number) · \(amount)" }
    public static func waitingHolderChange(fund: String, name: String) -> String { "Take over \(fund) from \(name)" }
    public static let someone = "someone"
    public static let advances = "Advances"
    public static func advanceRow(number: String, amount: String) -> String { "\(number) · \(amount)" }
    public static func advanceDetail(amount: String, date: String) -> String { "Remaining \(amount) · due \(date)" }
    public static let advanceOverdue = "Overdue"
    public static let advanceToMe = "Given to you"
    public static func advanceFromMe(_ name: String) -> String { "Given to \(name)" }
    public static let onPhone = "Recorded on this phone"
    public static let outboxAck = "Petty cash acknowledgement"
    public static let outboxTopUp = "Petty cash top-up request"
    public static let outboxReturn = "Petty cash return"
    public static let outboxCount = "Petty cash count"
    public static let outboxHolderChange = "Petty cash fund take-over"
    public static let outboxAdvance = "Petty cash advance cleared"
    public static let outboxGiveAdvance = "Petty cash advance given"
    public static let titleAck = "Acknowledge petty cash"
    public static let titleTopUp = "Request a top-up"
    public static let titleReturn = "Return money"
    public static let titleCount = "Record a count"
    public static let titleHolderChange = "Take over a fund"
    public static let titleAdvance = "Clear an advance"
    public static let titleGiveAdvance = "Give an advance"
    public static let giveRecipient = "Given to"
    public static let giveRecipientEmpty = "No colleague is saved on this phone yet. Connect, then open this form again."
    public static let giveAmount = "Amount"
    public static let givePurpose = "Purpose"
    public static let giveFooter = "The advance leaves the fund now. The colleague clears it with receipts and the change."
    public static let giveSave = "Give advance"
    public static let errRecipient = "Choose who receives the advance."
    public static let errPurpose = "Enter the purpose (at least 3 characters)."
    public static func giveOverspend(_ amount: String) -> String {
        "Above what the fund has available (\(amount)): it is recorded when the phone syncs and marked for the office to check."
    }
    public static func giveOverspendBlocked(_ amount: String) -> String {
        "Above what the fund has available (\(amount)). Your company does not allow this offline."
    }
    public static let notFound = "This is no longer waiting on this phone. Pull to sync."
    public static let unavailable = "Petty cash is not available on this phone. Sync, or ask your office."
    public static let fund = "Fund"
    public static let ackFunding = "Funding from the office"
    public static let ackTopUp = "Top-up from the office"
    public static let ackNumber = "Number"
    public static let ackIssued = "Issued"
    public static let ackIssuedAt = "Issued at"
    public static let ackIssuedBy = "Issued by"
    public static let ackReference = "Reference"
    public static let ackAmount = "Amount received"
    public static let ackFooter = "Count the money before you acknowledge. A different amount is recorded as a difference for the office to review."
    public static let ackAcknowledge = "Acknowledge"
    public static let ackDispute = "Dispute"
    public static let ackDisputeReason = "To dispute, write in the note why."
    public static let ackWaiting = "You already answered on this phone. It is sent when the phone syncs."
    public static let note = "Note (optional)"
    public static let topUpAmount = "Amount (optional)"
    public static let topUpAmountFooter = "Leave it empty to ask for the approved spending since the last top-up."
    public static let topUpAboveReason = "Reason for going above the limit"
    public static func topUpAboveFooter(_ amount: String) -> String {
        "This is more than brings the fund to its limit (\(amount)); say why."
    }
    public static let topUpFooter = "Someone else approves the top-up. The money counts in your fund only after you acknowledge it."
    public static let topUpSend = "Send request"
    public static let returnAmount = "Amount returned"
    public static let returnMethod = "How"
    public static func returnMethodLabel(_ method: String) -> String {
        switch method {
        case "CASH_TO_OFFICE": "Cash to office"
        case "BANK_DEPOSIT": "Bank deposit"
        case "MOBILE_MONEY": "Mobile money"
        default: method
        }
    }
    public static let returnMethods = ["CASH_TO_OFFICE", "BANK_DEPOSIT", "MOBILE_MONEY"]
    public static let returnAccount = "Deposit account (optional)"
    public static let returnNoAccount = "No account"
    public static let returnReference = "Reference (optional)"
    public static let returnFooter = "The fund goes down only when the office confirms what it received."
    public static let returnEvidenceRequired = "Your company requires a photo of the slip or the cash."
    public static let countAmount = "Cash counted"
    public static let countFooter = "Count every note and coin in the fund. A difference from the expected amount goes to the office to review."
    public static let countWitness = "Witness"
    public static let countWitnessSearch = "Search a colleague by name"
    public static let countWitnessNone = "No witness"
    public static let countWitnessFooter = "Your company asks for a witness: someone else who can count petty cash watches the count."
    public static let countWitnessOffline = "Connect to choose a witness."
    public static let countWitnessNoResults = "No one found."
    public static let countNoWitness = "Without a witness this count is recorded as counted by you alone."
    public static let countWitnessEmpty = "No colleague who can witness a count is on this phone. Sync first."
    public static let countRecordedSelf = "Recorded as counted by you alone."
    public static let countWitnessDropped = "The witness could no longer witness counts, so this count was recorded without a witness."

    /// (self-count, witness dropped): a witness was chosen but the server recorded none, or the server marked a self-count.
    public static func countOutcome(sentWitness: String?, recordedWitness: String?, selfCount: Bool) -> (selfCount: Bool, witnessDropped: Bool) {
        let dropped = sentWitness != nil && recordedWitness == nil
        return (selfCount && !dropped, dropped)
    }

    /// The line under a synced count: the witness was dropped, else a self-count; nil otherwise (and for other ops).
    public static func countOutcome(_ op: ClientOperation) -> String? {
        guard op.opType == OperationType.pettyCashCount.rawValue, op.status == .acked,
              let result = op.serverResultJSON.flatMap({ try? JSONValue.parse($0) }), let entity = result["entity"] else { return nil }
        let sent = (try? JSONValue.parse(op.payloadJSON))?["witness_user_id"]?.stringValue
        let outcome = countOutcome(sentWitness: sent, recordedWitness: entity["witness_user_id"]?.stringValue,
                                   selfCount: entity["self_count"]?.boolValue ?? false)
        return outcome.witnessDropped ? countWitnessDropped : outcome.selfCount ? countRecordedSelf : nil
    }
    public static let holderFrom = "From"
    public static let holderRequestedBy = "Requested by"
    public static let holderRequestedAt = "Requested"
    public static func holderFooter(_ name: String) -> String {
        "Until you accept, \(name) stays accountable for the fund. Count the cash before you accept."
    }
    public static let holderAccept = "Take over the fund"
    public static let holderDecline = "Decline"
    public static let holderDeclineReason = "To decline, write in the note why."
    public static let advanceRecipient = "Given to"
    public static let advanceAmount = "Advance"
    public static let advancePurpose = "Purpose"
    public static let advanceApproved = "Approved spending"
    public static let advancePending = "Spending awaiting approval"
    public static let advanceRemaining = "Remaining"
    public static let advanceDue = "Due"
    public static let advanceChange = "Change handed back"
    public static let advanceFooter = "Count the change you take back. A difference is recorded for the office to review."
    public static let advancePendingWarning = "Expenses of this advance are still waiting for approval. It can be cleared once they are decided."
    public static let advanceClear = "Clear advance"
    public static let errAmount = "Enter the amount (more than 0)."
    public static let errCounted = "Enter the cash counted (0 or more)."
    public static let errChange = "Enter the change handed back (0 or more)."
    public static let errAboveReason = "Enter the reason for going above the limit (at least 3 characters)."
    public static let errEvidence = "Photograph the slip or the cash."
    public static let errReason = "Enter a reason (at least 3 characters)."
    public static let expenseSection = "Petty cash fund"
    public static let expenseFund = "Fund"
    public static let expenseFundEmpty = "No petty cash fund on this phone. Sync first."
    public static func expenseFundOption(_ amount: String) -> String { "Available \(amount)" }
    public static let expenseAdvance = "Advance (optional)"
    public static let expenseAdvanceRequiredLabel = "Advance"
    public static let expenseNoAdvance = "Not from an advance"
    public static func expenseAdvanceOption(_ amount: String) -> String { "Remaining \(amount)" }
    public static func expenseFooter(_ amount: String) -> String { "Available to spend: \(amount). The currency is the fund's." }
    public static let expenseFundRequired = "Choose the petty cash fund."
    public static let expenseAdvanceRequired = "Choose the advance this was paid from."
    public static func expenseCurrency(_ currency: String) -> String { "The fund holds \(currency)." }
    public static func expenseOverspend(_ amount: String) -> String {
        "Above what the fund has available (\(amount)): it is kept for approval and marked for the approver to check."
    }
    public static func expenseAboveMaximum(_ amount: String) -> String {
        "Above the petty cash maximum per expense (\(amount)): a manager must approve it."
    }

    /// Plain words for a petty cash conflict (nil: keep the server's message).
    public static func conflict(_ code: String) -> String? {
        switch code {
        case "PETTY_CASH_INSUFFICIENT": "The fund did not have enough available. Check the fund and record the expense again if needed."
        case "PETTY_CASH_FUND_INACTIVE": "This petty cash fund is no longer active."
        case "PETTY_CASH_DISABLED": "Petty cash is switched off for your company."
        case "PETTY_CASH_ALREADY_ACKNOWLEDGED": "This was already answered."
        case "PETTY_CASH_ALREADY_DECIDED": "This was already decided."
        case "PETTY_CASH_NOTHING_TO_TOP_UP": "Nothing to top up: no approved spending since the last top-up, or the fund is at its limit."
        case "PETTY_CASH_ABOVE_CAP_REASON_REQUIRED": "The amount is above the fund's limit; send the request again with a reason."
        case "PETTY_CASH_ADVANCE_EXPENSES_PENDING": "Expenses of this advance are still waiting for approval."
        case "PETTY_CASH_ADVANCE_CLEARED": "This advance is already cleared."
        case "PETTY_CASH_ADVANCES_DISABLED": "Advances are switched off for your company."
        case "PETTY_CASH_ADVANCE_TO_HOLDER": "An advance goes to someone other than the fund's holder."
        default: nil
        }
    }

    /// Title of a petty cash operation recorded on this phone (the sync status wording).
    public static func operationTitle(_ op: ClientOperation) -> String {
        OperationType(rawValue: op.opType).flatMap { FieldAccountabilityTexts.operationTitle($0, payload: nil) } ?? op.opType
    }

    /// The amount a recorded operation names: received (acknowledgement), counted (count), change (advance), the amount
    /// otherwise; none for a holder-change answer.
    public static func recordAmount(_ op: ClientOperation) -> String? {
        guard let p = try? JSONValue.parse(op.payloadJSON) else { return nil }
        switch OperationType(rawValue: op.opType) {
        case .pettyCashAcknowledgement: return p["amount_received"]?.stringValue
        case .pettyCashCount: return p["counted_amount"]?.stringValue
        case .pettyCashAdvanceClearance: return p["change_returned"]?.stringValue
        case .pettyCashHolderChangeAcknowledgement: return nil
        default: return p["amount"]?.stringValue
        }
    }

    /// The fund a recorded operation names (top-up, return, count), for its currency.
    public static func recordFundID(_ op: ClientOperation) -> UUID? {
        (try? JSONValue.parse(op.payloadJSON))?["fund_id"]?.stringValue.flatMap(UUID.init(uuidString:))
    }

    /// A record line: "Petty cash return · 50000 TZS".
    public static func recordTitle(_ op: ClientOperation, currency: String?) -> String {
        operationTitle(op) + (recordAmount(op).map { " · " + InboxTexts.money($0, currency) } ?? "")
    }

    /// The refusal line of a record: the plain words for the code, else the server's message.
    public static func refusal(_ op: ClientOperation) -> String { op.errorCode.flatMap(conflict) ?? op.lastError ?? "" }

    /// "500 TZS": the Supervisor app's money format.
    public static func money(_ amount: DecimalString?, _ currency: String) -> String {
        InboxTexts.money((amount ?? DecimalString(0)).description, currency)
    }
}

// MARK: - Rules

/// Offline checks of the petty cash forms (the server re-validates every one).
public enum PettyCashRules {
    public typealias Problems = AccountabilityRules.Problems
    static let money = ExpenseRules.moneyDecimals
    public static let minReason = AccountabilityRules.minReason
    public static let maxNote = AccountabilityRules.maxNote
    public static let maxReference = AccountabilityRules.maxReference

    static func trimmed(_ text: String, max: Int = maxNote) -> String? { AccountabilityRules.trimmed(text, max: max) }

    /// What brings the fund to its limit as far as the phone knows (limit − balance), never below zero.
    public static func capEstimate(_ fund: PettyCashFundDTO) -> Decimal? {
        guard let balance = fund.balance?.balance.value else { return nil }
        return max(0, fund.approvedLimit.value - balance)
    }

    /// Whether the typed top-up amount is above the cap estimate (the reason is then required).
    public static func topUpAboveCap(amountText: String, fund: PettyCashFundDTO) -> Bool {
        guard let amount = AccountabilityRules.value(amountText, decimals: money), let cap = capEstimate(fund) else { return false }
        return amount > cap
    }

    /// Top-up: amount optional (more than 0 when given); above the cap a reason of 3+ characters.
    public static func topUp(amountText: String, aboveReason: String, fund: PettyCashFundDTO)
        -> Result<(amount: Decimal?, aboveReason: String?), Problems> {
        var m: [String] = []
        var amount: Decimal?
        if !amountText.trimmingCharacters(in: .whitespaces).isEmpty {
            amount = AccountabilityRules.value(amountText, decimals: money)
            if amount == nil { m.append(PettyCashTexts.errAmount) }
        }
        var reason: String?
        if amount != nil && topUpAboveCap(amountText: amountText, fund: fund) {
            reason = trimmed(aboveReason)
            if (reason?.count ?? 0) < minReason { m.append(PettyCashTexts.errAboveReason) }
        }
        return m.isEmpty ? .success((amount, reason)) : .failure(Problems(messages: m))
    }

    /// Return: amount more than 0; a photo when the tenant requires one.
    public static func returnFund(amountText: String, photoCount: Int, evidenceRequired: Bool) -> Result<Decimal, Problems> {
        var m: [String] = []
        let amount = AccountabilityRules.value(amountText, decimals: money)
        if amount == nil { m.append(PettyCashTexts.errAmount) }
        if evidenceRequired && photoCount == 0 { m.append(PettyCashTexts.errEvidence) }
        guard m.isEmpty, let amount else { return .failure(Problems(messages: m)) }
        return .success(amount)
    }

    /// Count: the cash counted, 0 or more.
    public static func count(countedText: String) -> Result<Decimal, Problems> {
        guard let value = AccountabilityRules.value(countedText, decimals: money, allowZero: true) else {
            return .failure(Problems(messages: [PettyCashTexts.errCounted]))
        }
        return .success(value)
    }

    /// Clear an advance: the change handed back, 0 or more.
    public static func clearAdvance(changeText: String) -> Result<Decimal, Problems> {
        guard let value = AccountabilityRules.value(changeText, decimals: money, allowZero: true) else {
            return .failure(Problems(messages: [PettyCashTexts.errChange]))
        }
        return .success(value)
    }

    /// Give an advance: a recipient other than the holder, an amount, a purpose (3+ characters); above what the fund has
    /// available it is refused when the tenant does not allow overspending offline.
    public static func giveAdvance(recipientID: UUID?, holderID: UUID, amountText: String, purpose: String, available: Decimal?,
                                   currency: String, policy: PettyCashPolicyValues)
        -> Result<(recipient: UUID, amount: Decimal, purpose: String), Problems> {
        var m: [String] = []
        if recipientID == nil || recipientID == holderID { m.append(PettyCashTexts.errRecipient) }
        let amount = AccountabilityRules.value(amountText, decimals: money)
        if amount == nil { m.append(PettyCashTexts.errAmount) }
        let text = trimmed(purpose) ?? ""
        if text.count < minReason { m.append(PettyCashTexts.errPurpose) }
        if !policy.overspendAllowedOffline, let note = giveNote(amount: amount, available: available, currency: currency, policy: policy) {
            m.append(note)
        }
        guard m.isEmpty, let recipientID, let amount else { return .failure(Problems(messages: m)) }
        return .success((recipientID, amount, text))
    }

    /// A typed money amount (more than 0), nil when not valid.
    public static func amount(_ text: String) -> Decimal? { AccountabilityRules.value(text, decimals: money) }

    /// The note when an advance is above what the fund has available (allowed offline, or why it is blocked).
    public static func giveNote(amount: Decimal?, available: Decimal?, currency: String, policy: PettyCashPolicyValues) -> String? {
        guard let amount, let available, amount > available else { return nil }
        let text = InboxTexts.money(DecimalString(max(available, 0)).description, currency)
        return policy.overspendAllowedOffline ? PettyCashTexts.giveOverspend(text) : PettyCashTexts.giveOverspendBlocked(text)
    }

    /// Recipients of an advance: the saved cash holders, active, without the fund's holder and me (by name).
    public static func advanceRecipients(_ custodians: [CustodianDTO], holderID: UUID, me: UUID?) -> [CustodianDTO] {
        custodians.filter { $0.isActive && $0.staffMemberID != holderID && $0.staffMemberID != me }
            .sorted { $0.fullName.lowercased() < $1.fullName.lowercased() }
    }

    /// Take over a fund: accept, or decline with a reason of 3+ characters.
    public static func holderChange(accept: Bool, note: String) -> Result<String?, Problems> {
        let text = trimmed(note)
        if !accept && (text?.count ?? 0) < minReason { return .failure(Problems(messages: [PettyCashTexts.errReason])) }
        return .success(text)
    }

    /// Paid from petty cash: the fund is required; a fund I do not hold needs the advance; the currency is the fund's.
    public static func expenseIssues(fundID: UUID?, advanceID: UUID?, currency: String, view: PettyCashView) -> [String] {
        guard let fundID, let option = view.expenseFunds.first(where: { $0.id == fundID }) else {
            return [PettyCashTexts.expenseFundRequired]
        }
        var m: [String] = []
        if !option.held && advanceID == nil { m.append(PettyCashTexts.expenseAdvanceRequired) }
        if currency.trimmingCharacters(in: .whitespaces).uppercased() != option.currency {
            m.append(PettyCashTexts.expenseCurrency(option.currency))
        }
        return m
    }

    /// The approval notes of a petty cash expense: above what is available (fund, or the advance's remaining) and above
    /// the tenant's maximum per expense (fund currency = base currency only).
    public static func expenseNotes(amount: Decimal?, fundID: UUID?, advanceID: UUID?, view: PettyCashView,
                                    baseCurrency: String?) -> [String] {
        guard let amount, let fundID, let option = view.expenseFunds.first(where: { $0.id == fundID }) else { return [] }
        var notes: [String] = []
        let advance = advanceID.flatMap { id in view.advances.first { $0.advance.id == id } }?.advance
        let available = advance.map { $0.remaining?.value ?? 0 } ?? option.available
        if let available, amount > available {
            notes.append(PettyCashTexts.expenseOverspend(InboxTexts.money(DecimalString(available).description, option.currency)))
        }
        if let maximum = view.policy.maxExpenseAmount, option.currency == baseCurrency, amount > maximum {
            notes.append(PettyCashTexts.expenseAboveMaximum(InboxTexts.money(DecimalString(maximum).description, option.currency)))
        }
        return notes
    }
}

// MARK: - Read side

/// One thing waiting for my answer.
public enum PettyCashWaiting: Sendable, Equatable, Identifiable {
    case movement(PettyCashMovementDTO)
    case holderChange(PettyCashHolderChangeDTO)

    public var id: UUID {
        switch self {
        case let .movement(m): m.id
        case let .holderChange(c): c.id
        }
    }

    public var title: String {
        switch self {
        case let .movement(m):
            let amount = PettyCashTexts.money(m.amount, m.currency)
            return m.kind == PettyCashMovementDTO.funding ? PettyCashTexts.waitingFunding(number: m.number, amount: amount)
                : PettyCashTexts.waitingTopUp(number: m.number, amount: amount)
        case let .holderChange(c):
            return PettyCashTexts.waitingHolderChange(fund: c.pettyCashFundName ?? PettyCashTexts.fund,
                                                      name: c.fromStaffName ?? PettyCashTexts.someone)
        }
    }
}

/// An advance with whether it came out of a fund I hold (I clear it) or was given to me (I spend from it).
public struct PettyCashAdvanceRow: Sendable, Equatable, Identifiable {
    public let advance: PettyCashAdvanceDTO
    public let fromMyFund: Bool
    public var id: UUID { advance.id }

    public var who: String {
        fromMyFund ? PettyCashTexts.advanceFromMe(advance.recipientStaffName ?? PettyCashTexts.someone) : PettyCashTexts.advanceToMe
    }
}

/// A fund the expense form may name: one I hold, or the fund of an advance given to me.
public struct PettyCashFundOption: Sendable, Equatable, Identifiable {
    public let id: UUID
    public let title: String
    public let currency: String
    /// Available to spend (nil for a fund I do not hold).
    public let available: Decimal?
    public let held: Bool
}

/// My petty cash as this phone knows it: the server's snapshot with this phone's answers taken out of "Waiting for you".
public struct PettyCashView: Sendable, Equatable {
    public var funds: [PettyCashFundDTO] = []
    public var waiting: [PettyCashWaiting] = []
    public var advances: [PettyCashAdvanceRow] = []
    /// Petty cash operations recorded on this phone, newest first, with their sync state.
    public var onPhone: [ClientOperation] = []
    public var policy = PettyCashPolicyValues()

    public init(funds: [PettyCashFundDTO] = [], waiting: [PettyCashWaiting] = [], advances: [PettyCashAdvanceRow] = [],
                onPhone: [ClientOperation] = [], policy: PettyCashPolicyValues = PettyCashPolicyValues()) {
        self.funds = funds
        self.waiting = waiting
        self.advances = advances
        self.onPhone = onPhone
        self.policy = policy
    }

    /// Advances given to me (I spend from them).
    public var myAdvances: [PettyCashAdvanceDTO] { advances.filter { !$0.fromMyFund }.map(\.advance) }

    /// Funds the expense form offers: mine, then the funds of advances given to me.
    public var expenseFunds: [PettyCashFundOption] {
        var options = funds.map {
            PettyCashFundOption(id: $0.id, title: PettyCashTexts.fundHeader(code: $0.code, name: $0.name), currency: $0.currency,
                                available: $0.balance?.availableToSpend.value, held: true)
        }
        for advance in myAdvances where !options.contains(where: { $0.id == advance.fundID }) {
            options.append(PettyCashFundOption(id: advance.fundID, title: advance.pettyCashFundName ?? PettyCashTexts.fund,
                                               currency: advance.currency, available: nil, held: false))
        }
        return options
    }

    /// Advances given to me from `fundID`.
    public func advances(of fundID: UUID?) -> [PettyCashAdvanceDTO] { myAdvances.filter { $0.fundID == fundID } }

    /// "Petty cash" is offered as paid-from.
    public var offersExpense: Bool { !expenseFunds.isEmpty }
}

public enum PettyCash {
    /// `sync_entity.entity_type` of each snapshot.
    public static let fundType = "petty_cash_fund"
    public static let awaitingType = "petty_cash_awaiting"
    public static let holderChangeType = "petty_cash_holder_change"
    public static let advanceType = "petty_cash_advance"
    public static let witnessType = "petty_cash_witness"

    static let operationTypes: Set<String> = [
        OperationType.pettyCashAcknowledgement.rawValue, OperationType.pettyCashTopUpRequest.rawValue,
        OperationType.pettyCashReturn.rawValue, OperationType.pettyCashCount.rawValue,
        OperationType.pettyCashHolderChangeAcknowledgement.rawValue, OperationType.pettyCashAdvanceClearance.rawValue,
        OperationType.pettyCashAdvance.rawValue,
    ]

    /// Builds the view: answered items (an op on this phone that was not refused) leave "Waiting for you" / "Advances";
    /// advances show only when the tenant uses them.
    public static func view(funds: [PettyCashFundDTO], awaiting: [PettyCashMovementDTO], changes: [PettyCashHolderChangeDTO],
                            advances: [PettyCashAdvanceDTO], operations: [ClientOperation],
                            policy: PettyCashPolicyValues) -> PettyCashView {
        let petty = operations.filter { operationTypes.contains($0.opType) }
        let answered = Set(petty.filter { $0.status != .failed && $0.status != .conflict }.map(\.entityID))
        let mine = Set(funds.map(\.id))
        let waiting = awaiting.filter { !answered.contains($0.id) }.map(PettyCashWaiting.movement)
            + changes.filter { !answered.contains($0.id) }.map(PettyCashWaiting.holderChange)
        let rows = policy.advancesEnabled
            ? advances.filter { !answered.contains($0.id) }.map { PettyCashAdvanceRow(advance: $0, fromMyFund: mine.contains($0.fundID)) }
            : []
        return PettyCashView(funds: funds.filter { $0.isActive != false }, waiting: waiting, advances: rows,
                             onPhone: petty.sorted { $0.createdAtDevice > $1.createdAtDevice },
                             policy: policy)
    }
}

extension FieldDirectory {
    func pettyRows<T: Decodable>(_ type: String, as: T.Type) -> [T] {
        ((try? store.syncState.entities(type: type, tenantID: tenantID)) ?? [])
            .compactMap { try? AssetaJSON.decoder().decode(T.self, from: Data($0.json.utf8)) }
    }

    /// The tenant's PETTY_CASH policy snapshot (defaults when none was sent).
    public func pettyCashPolicy() -> PettyCashPolicyValues {
        let stored = (try? store.syncState.policySnapshots(policyType: PettyCashPolicyValues.policyType, tenantID: tenantID)) ?? []
        guard let snapshot = stored.first(where: { $0.scopeKey == "tenant" }),
              let values = try? JSONValue.parse(snapshot.valuesJSON) else { return PettyCashPolicyValues() }
        return PettyCashPolicyValues(values: values)
    }

    /// Colleagues who may witness a count, by name, as the last pull delivered them (offline picker).
    public func pettyCashWitnesses() -> [PettyCashWitnessDTO] {
        pettyRows(PettyCash.witnessType, as: PettyCashWitnessDTO.self)
            .sorted { ($0.name.lowercased(), $0.userID.uuidString) < ($1.name.lowercased(), $1.userID.uuidString) }
    }

    /// The server sends the witness list (SYNC_PETTY_CASH_WITNESSES): the count form picks offline, else searches online.
    public func pettyCashWitnessesOffline() -> Bool {
        let text = (try? store.syncState.value(SyncKey.capabilities, tenant: tenantID.uuidString.lowercased())) ?? nil
        return (text ?? "").split(separator: ",").contains { $0 == SyncCapability.pettyCashWitnesses }
    }

    /// My petty cash: the last snapshot with this phone's answers.
    public func pettyCash() -> PettyCashView {
        let ops = (try? store.outbox.operations(tenantID: tenantID, owner: owner?.subject,
                                                statuses: Set(ClientOperationStatus.allCases))) ?? []
        return PettyCash.view(
            funds: pettyRows(PettyCash.fundType, as: PettyCashFundDTO.self).sorted { $0.code < $1.code },
            awaiting: pettyRows(PettyCash.awaitingType, as: PettyCashMovementDTO.self).sorted { ($0.issuedAt ?? .distantPast) < ($1.issuedAt ?? .distantPast) },
            changes: pettyRows(PettyCash.holderChangeType, as: PettyCashHolderChangeDTO.self),
            advances: pettyRows(PettyCash.advanceType, as: PettyCashAdvanceDTO.self).sorted { $0.number < $1.number },
            operations: ops, policy: pettyCashPolicy())
    }
}

// MARK: - Recorder

extension FieldRecorder {
    private func pettyFund(_ fundID: UUID) throws -> PettyCashFundDTO {
        guard let entity = try store.syncState.entity(type: PettyCash.fundType, id: fundID, tenantID: tenantID),
              let fund = try? AssetaJSON.decoder().decode(PettyCashFundDTO.self, from: Data(entity.json.utf8)) else {
            throw FieldRecorderError.notAllowed(PettyCashTexts.notFound)
        }
        return fund
    }

    private func once(_ type: OperationType, _ id: UUID) throws {
        if try alreadySaved(type, clientID: id) { throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved) }
    }

    /// `PETTY_CASH_ACKNOWLEDGEMENT`: the amount received (0 or more) or a dispute with a reason. One answer per movement.
    @discardableResult
    public func acknowledgePettyCash(movementID: UUID, acknowledge: Bool, receivedText: String, note: String,
                                     at date: Date = Date()) throws -> ClientOperation {
        try requireCapability(SyncCapability.pettyCash)
        let values: (received: Decimal?, note: String?)
        switch AccountabilityRules.acknowledgement(acknowledge: acknowledge, receivedText: receivedText, note: note) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(checked): values = checked
        }
        try once(.pettyCashAcknowledgement, movementID)
        let payload = PettyCashAckPayload(movementID: movementID, acknowledged: acknowledge, amountReceived: values.received,
                                          note: values.note)
        return try enqueue(.pettyCashAcknowledgement, entityType: "petty_cash_ack", entityID: movementID, payload: payload,
                           dependsOn: [], createdAt: date)
    }

    /// `PETTY_CASH_TOP_UP_REQUEST` of a fund I hold (someone else approves it).
    @discardableResult
    public func requestPettyCashTopUp(fundID: UUID, amountText: String, note: String, aboveReason: String,
                                      at date: Date = Date(), clientID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.pettyCash)
        let fund = try pettyFund(fundID)
        let values: (amount: Decimal?, aboveReason: String?)
        switch PettyCashRules.topUp(amountText: amountText, aboveReason: aboveReason, fund: fund) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(checked): values = checked
        }
        try once(.pettyCashTopUpRequest, clientID)
        let payload = PettyCashTopUpPayload(clientID: clientID, fundID: fundID, amount: values.amount,
                                            note: PettyCashRules.trimmed(note), aboveCapReason: values.aboveReason)
        return try enqueue(.pettyCashTopUpRequest, entityType: "petty_cash_top_up", entityID: clientID, payload: payload,
                           dependsOn: [], createdAt: date)
    }

    /// `PETTY_CASH_RETURN` with its photos (purpose PETTY_CASH_EVIDENCE; the op waits for every upload).
    @discardableResult
    public func returnPettyCash(fundID: UUID, amountText: String, method: String?, depositAccountID: UUID?, reference: String,
                                note: String, evidence: [StoredEvidence], evidenceRequired: Bool, at date: Date = Date(),
                                clientID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.pettyCash)
        _ = try pettyFund(fundID)
        guard evidence.count <= AccountabilityRules.maxEvidence else { throw FieldRecorderError.invalid(FieldAccountabilityTexts.tooManyEvidence) }
        let amount: Decimal
        switch PettyCashRules.returnFund(amountText: amountText, photoCount: evidence.count, evidenceRequired: evidenceRequired) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(value): amount = value
        }
        try once(.pettyCashReturn, clientID)
        return try store.database.transaction {
            let locals = try evidence.map { try addAttachment($0, purpose: .pettyCashEvidence) }
            let payload = PettyCashReturnPayload(clientID: clientID, fundID: fundID, amount: amount, depositAccountID: depositAccountID,
                                                 method: method, reference: PettyCashRules.trimmed(reference, max: PettyCashRules.maxReference),
                                                 note: PettyCashRules.trimmed(note))
            return try enqueue(.pettyCashReturn, entityType: "petty_cash_return", entityID: clientID, payload: payload,
                               dependsOn: [], attachments: locals.map { ($0, .evidenceUploads) }, createdAt: date)
        }
    }

    /// `PETTY_CASH_COUNT` with an optional witness (a colleague's user id) and photos.
    @discardableResult
    public func countPettyCash(fundID: UUID, countedText: String, witnessUserID: UUID?, note: String, evidence: [StoredEvidence],
                               at date: Date = Date(), clientID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.pettyCash)
        _ = try pettyFund(fundID)
        guard evidence.count <= AccountabilityRules.maxEvidence else { throw FieldRecorderError.invalid(FieldAccountabilityTexts.tooManyEvidence) }
        let counted: Decimal
        switch PettyCashRules.count(countedText: countedText) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(value): counted = value
        }
        try once(.pettyCashCount, clientID)
        return try store.database.transaction {
            let locals = try evidence.map { try addAttachment($0, purpose: .pettyCashEvidence) }
            let payload = PettyCashCountPayload(clientID: clientID, fundID: fundID, countedAmount: counted, witnessUserID: witnessUserID,
                                                note: PettyCashRules.trimmed(note))
            return try enqueue(.pettyCashCount, entityType: "petty_cash_count", entityID: clientID, payload: payload,
                               dependsOn: [], attachments: locals.map { ($0, .evidenceUploads) }, createdAt: date)
        }
    }

    /// `PETTY_CASH_HOLDER_CHANGE_ACKNOWLEDGEMENT`: take over the fund, or decline with a reason.
    @discardableResult
    public func answerPettyCashHolderChange(changeID: UUID, accept: Bool, note: String, at date: Date = Date()) throws -> ClientOperation {
        try requireCapability(SyncCapability.pettyCash)
        let text: String?
        switch PettyCashRules.holderChange(accept: accept, note: note) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(value): text = value
        }
        try once(.pettyCashHolderChangeAcknowledgement, changeID)
        return try enqueue(.pettyCashHolderChangeAcknowledgement, entityType: "petty_cash_holder_change", entityID: changeID,
                           payload: PettyCashHolderChangePayload(holderChangeID: changeID, accept: accept, note: text),
                           dependsOn: [], createdAt: date)
    }

    /// `PETTY_CASH_ADVANCE` from a fund I hold to someone else (OP_PETTY_CASH_ADVANCE); queued once per form visit.
    @discardableResult
    public func givePettyCashAdvance(fundID: UUID, recipientID: UUID?, amountText: String, purpose: String,
                                     policy: PettyCashPolicyValues, at date: Date = Date(), clientID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.pettyCash)
        try requireCapability(SyncCapability.pettyCashAdvance)
        let fund = try pettyFund(fundID)
        let values: (recipient: UUID, amount: Decimal, purpose: String)
        switch PettyCashRules.giveAdvance(recipientID: recipientID, holderID: fund.holderStaffID, amountText: amountText, purpose: purpose,
                                          available: fund.balance?.availableToSpend.value, currency: fund.currency, policy: policy) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(checked): values = checked
        }
        try once(.pettyCashAdvance, clientID)
        return try enqueue(.pettyCashAdvance, entityType: "petty_cash_advance_give", entityID: clientID,
                           payload: PettyCashAdvancePayload(clientID: clientID, fundID: fundID, recipientStaffID: values.recipient,
                                                            amount: values.amount, purpose: values.purpose),
                           dependsOn: [], createdAt: date)
    }

    /// `PETTY_CASH_ADVANCE_CLEARANCE` of an advance handed out from my fund (the change I take back).
    @discardableResult
    public func clearPettyCashAdvance(advanceID: UUID, changeText: String, note: String, at date: Date = Date()) throws -> ClientOperation {
        try requireCapability(SyncCapability.pettyCash)
        let change: Decimal
        switch PettyCashRules.clearAdvance(changeText: changeText) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(value): change = value
        }
        try once(.pettyCashAdvanceClearance, advanceID)
        return try enqueue(.pettyCashAdvanceClearance, entityType: "petty_cash_advance", entityID: advanceID,
                           payload: PettyCashAdvanceClearPayload(advanceID: advanceID, changeReturned: change,
                                                                 note: PettyCashRules.trimmed(note)),
                           dependsOn: [], createdAt: date)
    }
}

// MARK: - Online

extension SupervisorOnline {
    /// Colleagues by name for the count witness (`GET /tenant/people?q=`, at least 2 characters; online only).
    public func searchPeople(_ query: String) async throws -> [PersonDTO] {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard q.count >= PettyCashRules.minWitnessQuery else { return [] }
        return try await client.send(APIRequest<[PersonDTO]>.get("\(Self.tenant)/people", query: [URLQueryItem(name: "q", value: q)]))
    }
}

extension PettyCashRules {
    /// Characters typed before the witness search runs.
    public static let minWitnessQuery = 2
}
