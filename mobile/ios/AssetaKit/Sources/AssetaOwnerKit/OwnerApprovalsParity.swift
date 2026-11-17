import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

// ADR-008 Owner Approvals as on Android (`ui/approvals/ApprovalFilters.kt`, `ApprovalsScreen.kt`): the chips and their
// counts, credit sale and expense rows, the credit approval's done and refusal messages.

/// The Approvals chips (design OwnerApprovals): All, then the three kinds the owner decides most.
public enum ApprovalFilter: String, CaseIterable, Hashable, Sendable {
    case all, machineReports, credit, expenses

    public var label: String {
        switch self {
        case .all: "All"
        case .machineReports: "Machine reports"
        case .credit: "Credit"
        case .expenses: "Expenses"
        }
    }

    /// Which kinds this chip shows: every kind under All.
    public func shows(_ kind: ApprovalKind) -> Bool {
        switch self {
        case .all: true
        case .machineReports: kind == .machineReport
        case .credit: kind == .credit
        case .expenses: kind == .expense
        }
    }
}

/// What a waiting item is; `other` = petty cash, payments, handovers, meter resets, exceptions, accountability decisions.
public enum ApprovalKind: Sendable { case machineReport, credit, expense, other }

/// Waiting items per kind; the chips show "All 5", "Machine reports 2", …, Home "5 waiting" and the menu badge.
public struct ApprovalCounts: Equatable, Sendable {
    public var reports: Int
    public var credit: Int
    public var expenses: Int
    public var other: Int

    public init(reports: Int = 0, credit: Int = 0, expenses: Int = 0, other: Int = 0) {
        self.reports = reports
        self.credit = credit
        self.expenses = expenses
        self.other = other
    }

    public var all: Int { reports + credit + expenses + other }

    public func of(_ filter: ApprovalFilter) -> Int {
        switch filter {
        case .all: all
        case .machineReports: reports
        case .credit: credit
        case .expenses: expenses
        }
    }

    /// "Machine reports 2".
    public func chip(_ filter: ApprovalFilter) -> String { "\(filter.label) \(of(filter))" }

    /// Home tile badge: "5 waiting" (nil when nothing waits).
    public var waiting: String? { all > 0 ? "\(all) waiting" : nil }

    /// Side-menu badge: the waiting count, `99+` above 99, nil when nothing waits.
    public var badge: String? { OwnerFormat.badge(all) }
}

/// Approvals wording added by ADR-008 (Android `ApprovalsTexts`).
public enum ApprovalsTexts {
    public static let creditKind = "CREDIT SALE"
    public static let expenseKind = "EXPENSE"
    public static let approveCredit = "Approve credit"
    public static let reject = "Reject"
    public static let receiptPhoto = "receipt photo"
    public static let emptyTitle = "Nothing waiting"
    public static let emptyMessage = "Nothing here needs your decision."
    public static let creditApproved = "Credit approved. The customer can use these hours."
    public static let ownSale = "You recorded this sale, so someone else must approve its credit."

    // Reject credit (owner decision): a reason is required; the seller is told it.
    public static let rejectCreditTitle = "Reject credit"
    public static func rejectCreditMessage(_ customer: String, _ amount: String) -> String {
        "\(customer): \(amount) on credit. The credit invoice is cancelled and these hours will not be usable. Parts already paid stay as they are."
    }
    public static let rejectReasonLabel = "Reason (the seller will see it)"
    public static let rejectReasonHint = "At least 3 characters."
    public static let rejectConfirm = "Reject credit"
    public static let cancel = "Cancel"
    public static let creditRejected = "Credit rejected. The invoice is cancelled and the seller is told why."
    public static let rejectReasonMin = 3

    /// Refusals of a credit approval in plain words (else `fallback`).
    public static func creditRefusal(_ code: String?, fallback: String) -> String {
        switch code {
        case "SEGREGATION_OF_DUTIES": "You recorded this sale, so you can't approve its credit. Someone else must."
        case "NO_CREDIT_ARRANGEMENT": "This customer has no approved credit limit. Set one up on the web first."
        case "CREDIT_LIMIT_EXCEEDED": "This would take the customer over their credit limit."
        case "EXCEEDS_UNACTIVATED_HOURS": "Fewer hours are waiting than this; the list has been refreshed."
        case "CREDIT_NOT_ALLOWED": "Credit is switched off for this company."
        case "PURCHASE_CANCELLED": "This order was cancelled."
        case "CANCELLATION_PENDING": "A cancellation is already waiting for this order."
        default: fallback
        }
    }

    /// The refused credit approval reloads the list for these codes (and any conflict the server says to reload on).
    public static func creditReloads(_ code: String?) -> Bool {
        code == "EXCEEDS_UNACTIVATED_HOURS" || code == "PURCHASE_CANCELLED"
    }

    /// Refusals of Reject credit in plain words (else `fallback`).
    public static func creditRejectRefusal(_ code: String?, fallback: String) -> String {
        switch code {
        case "SEGREGATION_OF_DUTIES": "You recorded this sale, so you can't reject its credit. Someone else must."
        case "CREDIT_NOT_AWAITING": "This credit is no longer waiting: it was already approved or rejected. The list has been refreshed."
        case "CREDIT_INVOICE_HAS_PAYMENTS": "Payments are already recorded on this credit invoice, so its credit can't be rejected."
        case "NO_CREDIT_PART": "This order has no credit part."
        case "PURCHASE_CANCELLED": "This order was cancelled."
        default: fallback
        }
    }

    /// The refused rejection reloads the list for these codes (the order moved on).
    public static func creditRejectReloads(_ code: String?) -> Bool {
        ["CREDIT_NOT_AWAITING", "CREDIT_INVOICE_HAS_PAYMENTS", "PURCHASE_CANCELLED", "NO_CREDIT_PART"].contains(code ?? "")
    }

    /// A rejection needs a reason of at least 3 characters (trimmed; as the server and Android).
    public static func rejectReasonValid(_ text: String) -> Bool {
        text.trimmingCharacters(in: .whitespacesAndNewlines).count >= rejectReasonMin
    }
}

/// A credit sale waiting: the order and what is left of the customer's credit limit (nil: no arrangement or unreadable).
public struct CreditSale: Codable, Hashable, Sendable, Identifiable {
    public let purchase: HoursPurchaseDTO
    public let limitLeft: DecimalString?
    public var id: UUID { purchase.id }

    public init(purchase: HoursPurchaseDTO, limitLeft: DecimalString? = nil) {
        self.purchase = purchase
        self.limitLeft = limitLeft
    }
}

/// Credit sales: orders with a CREDIT part whose hours still wait to be made usable (Android `CreditSales`).
public enum CreditSales {
    /// At most this many customers' credit limits are looked up per list.
    public static let maxExposureLookups = 25

    /// `credit_status` of a rejected credit part.
    public static let rejected = "REJECTED"

    /// Has a credit part (not rejected) and hours still waiting, not cancelled.
    public static func waiting(_ p: HoursPurchaseDTO) -> Bool {
        p.cancelledAt == nil && p.creditStatus != rejected && (p.creditAmount?.value ?? 0) > 0
            && p.totals.awaitingActivation.value > 0
    }

    /// Hours the credit part pays for: credit amount ÷ the order's effective rate (rounded down to 0.01 h), never more
    /// than the hours still waiting; the waiting hours when the rate is unknown.
    public static func creditHours(_ p: HoursPurchaseDTO) -> Decimal {
        let waiting = p.totals.awaitingActivation.value
        guard let rate = p.effectiveRate?.value, rate > 0 else { return waiting }
        var exact = (p.creditAmount?.value ?? 0) / rate
        var hours = Decimal()
        NSDecimalRound(&hours, &exact, 2, .down)
        return min(hours, waiting)
    }

    /// "Msasani Bay · 40 h on credit".
    public static func title(_ p: HoursPurchaseDTO) -> String {
        "\(p.customerName ?? p.purchaseNumber) · \(OwnerFigures.hours(creditHours(p))) on credit"
    }

    /// "Invoice INV-0042 · TZS 3,800,000 · limit left 6.2M".
    public static func detail(_ sale: CreditSale) -> String {
        let p = sale.purchase
        return [
            p.creditInvoice.map { "Invoice \($0.invoiceNumber)" },
            OwnerFigures.money(p.creditAmount?.value ?? 0, currency: p.currency).trimmingCharacters(in: .whitespaces),
            sale.limitLeft.map { "limit left \(OwnerFigures.compactMoney($0.value))" },
        ].compactMap { $0 }.joined(separator: " · ")
    }

    /// The person who recorded the sale may not approve its credit (the server refuses it too).
    public static func recordedBy(_ p: HoursPurchaseDTO, me: UUID?) -> Bool {
        guard let me, let by = p.createdBy else { return false }
        return by == me
    }
}

/// Expense rows: "Hydraulic hose · TZS 185,000" over "receipt photo · Tabata Hydraulics" (Android `ExpenseApprovals`).
public enum ExpenseApprovals {
    public static func title(_ a: ApprovalRequestDTO, _ e: ExpenseDTO?) -> String {
        "\(e?.description ?? a.reason) · \(OwnerFigures.money(a.amount.value, currency: a.currency))"
    }

    public static func detail(_ a: ApprovalRequestDTO, _ e: ExpenseDTO?) -> String {
        [
            e?.receiptAttachmentIDs.isEmpty == false ? ApprovalsTexts.receiptPhoto : nil,
            e?.supplier.flatMap { $0.trimmingCharacters(in: .whitespaces).isEmpty ? nil : $0 },
            e == nil || a.reason != e?.description ? a.reason : nil,
        ].compactMap { $0 }.joined(separator: " · ")
    }

    /// The expense behind a request (EXPENSE subjects only).
    public static func expense(_ a: ApprovalRequestDTO, in expenses: [ExpenseDTO]) -> ExpenseDTO? {
        a.subjectType == "EXPENSE" ? expenses.first { $0.id == a.subjectID } : nil
    }
}

/// `CreditExposureDto` (getCustomerCreditExposure): the customer's credit limit and what is left of it.
public struct CreditExposureDTO: Codable, Hashable, Sendable {
    public let customerID: UUID
    public let currency: String
    public let limitAmount: DecimalString?
    public let exposure: DecimalString
    public let available: DecimalString?

    enum CodingKeys: String, CodingKey {
        case currency, exposure, available, customerID = "customer_id", limitAmount = "limit_amount"
    }
}

extension OwnerAPI {
    /// `GET /customers/{id}/credit-exposure` (`tenant.hours.read`).
    public static func customerCreditExposure(_ customerID: UUID) -> APIRequest<CreditExposureDTO> {
        .get("\(tenant)/customers/\(customerID.lowercased)/credit-exposure")
    }
}

extension SnapshotKey {
    /// Credit sales waiting, with each customer's limit left.
    public static let creditSalesWaiting = SnapshotKey("credit-sales:waiting")
    /// Expenses waiting for approval (the description and supplier of expense requests).
    public static let expensesAwaitingApproval = SnapshotKey("expenses:PENDING_APPROVAL")
}

extension OwnerFeatures {
    /// Credit sales are listed (hours on and `tenant.hours.credit_activate`); Android `creditSales`.
    public var creditSales: Bool { creditActivate }
}
