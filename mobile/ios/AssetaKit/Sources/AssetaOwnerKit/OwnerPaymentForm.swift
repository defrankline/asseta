import AssetaModel
import Foundation

// ADR-008 Owner "Record payment" of a credit invoice: the same rules and wording as Android `ui/money/PaymentForm.kt`
// (strings doc "ADR-008 apps › Owner › Record payment"). The server re-checks everything.

private typealias F = OwnerFiguresB

/// Record payment wording.
public enum OwnerPaymentTexts {
    public static let title = "Record payment"
    public static let invoice = "INVOICE"
    public static let amount = "Amount"
    public static let method = "METHOD"
    public static let reference = "Reference"
    public static let referenceHint = "Bank or mobile money transaction reference"
    public static let received = "RECEIVED"
    public static let today = "Today"
    public static let yesterday = "Yesterday"
    public static let note = "Note (optional)"
    public static let save = "Record payment"
    public static let noOpen = "No open credit invoices."
    public static let chooseInvoice = "Choose the invoice being paid."
    public static let amountNeeded = "Enter the amount received (more than 0)."
    public static let referenceNeeded = "Enter the transaction reference for a bank or mobile money payment."
    public static let cashNote = "Cash goes into your cash with you until you hand it over."
    public static let claimedNote = "Bank and mobile money stay unconfirmed until the office checks them."

    /// "Amount (TZS)" (the bare label until an invoice is chosen).
    public static func amountLabel(_ currency: String?) -> String { amount + (currency.map { " (\($0))" } ?? "") }
    public static func overBalance(_ balance: Decimal) -> String { "At most the balance, \(F.money(balance, currency: ""))." }
    public static func left(_ i: CreditInvoiceDTO) -> String {
        "\(F.money(i.balance.value, currency: i.currency)) left · due \(F.day(i.dueDate))"
    }
    public static func done(_ i: CreditInvoiceDTO) -> String {
        "Payment recorded. \(i.invoiceNumber): \(F.money(i.balance.value, currency: i.currency)) left."
    }

    /// Refusals of a credit-invoice payment in plain words (else `fallback`, the server's message).
    public static func refusal(_ code: String?, fallback: String) -> String {
        switch code {
        case "INVOICE_OVERPAYMENT": "That is more than the invoice still owes. The invoice has been refreshed."
        case "INVOICE_PAID": "This invoice is already paid in full."
        case "INVOICE_CANCELLED": "This invoice was cancelled with its order."
        case "INVOICE_NOT_FOUND": "This invoice no longer exists."
        case "PAYMENT_NOT_PERMITTED": "You may not record bank or mobile money payments here. Record cash, or ask the office."
        case "STAFF_NOT_LINKED": "Your login is not linked to a staff record, so cash can't be put in your custody. Ask the office."
        case "NOT_CUSTODIAN": "Only office cash staff may record cash for someone else."
        default: fallback
        }
    }
}

/// A payment method of a credit-invoice payment (no CREDIT: an invoice is paid with money).
public enum OwnerPayMethod: String, CaseIterable, Sendable, Hashable {
    case cash = "CASH", bank = "BANK", mobileMoney = "MOBILE_MONEY"

    public var label: String {
        switch self {
        case .cash: "Cash"
        case .bank: "Bank"
        case .mobileMoney: "Mobile money"
        }
    }

    public var needsReference: Bool { self != .cash }
}

/// The form as typed. `key` is the visit's Idempotency-Key and the payment's `client_id`.
public struct OwnerPaymentDraft: Equatable, Sendable {
    public var invoiceID: UUID?
    public var amount = ""
    public var method = OwnerPayMethod.cash
    public var reference = ""
    public var yesterday = false
    public var note = ""
    public var key = UUID()

    public init(invoiceID: UUID? = nil) { self.invoiceID = invoiceID }
}

/// Pure payment rules (the server re-checks everything).
public enum OwnerPaymentRules {
    /// Invoices that can still be paid: balance left, not cancelled or paid; overdue first, then by due date.
    public static func open(_ invoices: [CreditInvoiceDTO]) -> [CreditInvoiceDTO] {
        invoices.filter { $0.status != "CANCELLED" && $0.status != "PAID" && $0.balance.value > 0 }
            .sorted { a, b in a.overdue != b.overdue ? a.overdue : (a.dueDate ?? "") < (b.dueDate ?? "") }
    }

    /// A positive amount with at most 2 decimals ("170000", "170,000" and "170000.50" read).
    public static func amount(_ text: String) -> Decimal? {
        let raw = text.replacingOccurrences(of: ",", with: "").trimmingCharacters(in: .whitespaces)
        guard raw.range(of: #"^(\d+\.?\d*|\.\d+)$"#, options: .regularExpression) != nil,
              let value = Decimal(string: raw, locale: Locale(identifier: "en_US_POSIX")), value > 0 else { return nil }
        let decimals = raw.split(separator: ".", omittingEmptySubsequences: false).dropFirst().first
            .map { String($0).replacingOccurrences(of: "0+$", with: "", options: .regularExpression).count } ?? 0
        return decimals <= 2 ? value : nil
    }

    /// The first problem of the draft, or nil when it can be sent.
    public static func problem(_ d: OwnerPaymentDraft, invoice: CreditInvoiceDTO?) -> String? {
        guard let invoice else { return OwnerPaymentTexts.chooseInvoice }
        guard let amount = amount(d.amount) else { return OwnerPaymentTexts.amountNeeded }
        if amount > invoice.balance.value { return OwnerPaymentTexts.overBalance(invoice.balance.value) }
        if d.method.needsReference && d.reference.trimmingCharacters(in: .whitespaces).isEmpty {
            return OwnerPaymentTexts.referenceNeeded
        }
        return nil
    }

    /// When the money was received: now today, or noon yesterday (local time).
    public static func receivedAt(yesterday: Bool, now: Date = Date(), calendar: Calendar = .current) -> Date {
        guard yesterday, let day = calendar.date(byAdding: .day, value: -1, to: calendar.startOfDay(for: now)) else { return now }
        return calendar.date(bySettingHour: 12, minute: 0, second: 0, of: day) ?? now
    }

    /// The request body (call only when ``problem(_:invoice:)`` is nil).
    public static func body(_ d: OwnerPaymentDraft, now: Date = Date(), calendar: Calendar = .current) -> CreditInvoicePaymentIn {
        let reference = d.reference.trimmingCharacters(in: .whitespaces)
        let note = d.note.trimmingCharacters(in: .whitespacesAndNewlines)
        return CreditInvoicePaymentIn(clientID: d.key, amount: amount(d.amount) ?? 0, method: d.method.rawValue,
                                      reference: d.method.needsReference && !reference.isEmpty ? reference : nil,
                                      receivedAt: receivedAt(yesterday: d.yesterday, now: now, calendar: calendar),
                                      note: note.isEmpty ? nil : note)
    }
}
