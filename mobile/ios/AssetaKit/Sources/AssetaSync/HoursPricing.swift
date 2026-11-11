import AssetaModel
import AssetaStore
import Foundation

/// A machine's current hourly rate as the last pull delivered it (SYNC_HOURS_PRICES). `minorUnits`: the decimal places the
/// server rounds the currency to (`HoursPriceDto.minor_units`; the ISO table when an older server leaves it out).
public struct HoursPrice: Sendable, Equatable {
    public let machineID: UUID
    public let hourlyRate: Decimal
    public let minimumHours: Decimal
    public let currency: String
    public let minorUnits: Int

    public init(machineID: UUID, hourlyRate: Decimal, minimumHours: Decimal, currency: String, minorUnits: Int? = nil) {
        self.machineID = machineID
        self.hourlyRate = hourlyRate
        self.minimumHours = minimumHours
        self.currency = currency
        self.minorUnits = minorUnits ?? HoursPricing.minorUnits(currency)
    }
}

/// The prices on this phone: machine rates by machine id, approved discounts (percent) by customer id.
public struct HoursPriceBook: Sendable, Equatable {
    public var prices: [UUID: HoursPrice]
    public var discounts: [UUID: Decimal]

    public init(prices: [UUID: HoursPrice] = [:], discounts: [UUID: Decimal] = [:]) {
        self.prices = prices
        self.discounts = discounts
    }
}

/// What a sale costs: the rate card less the discount, times the hours, rounded to the currency (as the server prices it).
public struct HoursSaleQuote: Sendable, Equatable {
    public let hours: Decimal
    public let hourlyRate: Decimal
    public let discountPercent: Decimal
    public let effectiveRate: Decimal
    public let amount: Decimal
    public let currency: String
    public let minorUnits: Int
}

/// What the hours sale form shows under Hours.
public enum HoursSalePrice: Sendable, Equatable {
    /// No machine yet, or no hours (or not a valid number): nothing is shown.
    case hidden
    /// The machine has no price on this phone: the office prices the sale when it arrives.
    case unpriced
    case priced(HoursSaleQuote)

    var quote: HoursSaleQuote? { if case let .priced(q) = self { q } else { nil } }
}

/// The server's price rule for an hours sale, applied on the phone so the total shows offline (same rules as Android
/// `HoursPricing`): effective rate = hourly rate x (100 - discount) / 100, rounded to 4 decimals (half-even); total =
/// hours x effective rate, rounded half-up to the currency's minor units (the server's, sent with the price). A walk-in
/// has no discount.
public enum HoursPricing {
    /// `sync_entity.entity_type` of the two snapshots.
    public static let priceType = "hours_price"
    public static let discountType = "customer_discount"

    static let zeroDecimals: Set<String> = ["BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF", "UGX", "UYI", "VND",
                                            "VUV", "XAF", "XOF", "XPF"]
    static let threeDecimals: Set<String> = ["BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"]

    /// Fallback when the server did not send `minor_units`: ISO 4217 (TZS 2, UGX 0, KWD 3); 2 for a code not listed.
    public static func minorUnits(_ currency: String) -> Int {
        let code = currency.trimmingCharacters(in: .whitespaces).uppercased()
        if zeroDecimals.contains(code) { return 0 }
        if threeDecimals.contains(code) { return 3 }
        return 2
    }

    static func rounded(_ value: Decimal, _ scale: Int, _ mode: NSDecimalNumber.RoundingMode) -> Decimal {
        var input = value
        var output = Decimal()
        NSDecimalRound(&output, &input, scale, mode)
        return output
    }

    public static func effectiveRate(_ hourlyRate: Decimal, discountPercent: Decimal) -> Decimal {
        rounded(hourlyRate * (100 - discountPercent) / 100, 4, .bankers)
    }

    public static func quote(hours: Decimal, hourlyRate: Decimal, discountPercent: Decimal, currency: String,
                             minorUnits: Int? = nil) -> HoursSaleQuote {
        let units = min(max(minorUnits ?? Self.minorUnits(currency), 0), 6)
        let effective = effectiveRate(hourlyRate, discountPercent: discountPercent)
        let amount = rounded(hours * effective, units, .plain)
        return HoursSaleQuote(hours: hours, hourlyRate: hourlyRate, discountPercent: discountPercent, effectiveRate: effective,
                              amount: amount, currency: currency, minorUnits: units)
    }

    /// The form's price line: hidden until a machine and hours are entered; `walkIn` sales get no discount.
    public static func price(_ book: HoursPriceBook, machineID: UUID?, customerID: UUID?, walkIn: Bool, hoursText: String) -> HoursSalePrice {
        guard let machineID else { return .hidden }
        guard let hours = AccountabilityRules.saleHours(hoursText), hours > 0 else { return .hidden }
        guard let price = book.prices[machineID] else { return .unpriced }
        let discount = walkIn ? 0 : customerID.flatMap { book.discounts[$0] } ?? 0
        return .priced(quote(hours: hours, hourlyRate: price.hourlyRate, discountPercent: max(discount, 0), currency: price.currency,
                             minorUnits: price.minorUnits))
    }

    /// "TZS 570,000"; "USD 12.50" when there are cents (`minorUnits` decimals).
    public static func money(_ amount: Decimal, currency: String, minorUnits: Int? = nil) -> String {
        let digits = rounded(amount, 0, .plain) == amount ? 0 : (minorUnits ?? Self.minorUnits(currency))
        return "\(currency) \(number(rounded(amount, digits, .plain), digits...digits))"
    }

    /// An hourly rate or an amount without its currency: grouping, up to 4 decimals ("95,000", "85,500.5").
    public static func rate(_ value: Decimal) -> String { number(value, 0...4) }

    /// Hours or a percent: grouping, up to 2 decimals ("6", "12.5").
    public static func figure(_ value: Decimal) -> String { number(value, 0...2) }

    static func number(_ value: Decimal, _ fraction: ClosedRange<Int>) -> String {
        value.formatted(.number.precision(.fractionLength(fraction)).rounded(rule: .toNearestOrEven).grouping(.automatic)
            .locale(Locale(identifier: "en_US")))
    }

    static func load(store: LocalStore, tenantID: UUID) -> HoursPriceBook {
        func rows<T: Decodable>(_ type: String, _: T.Type) -> [T] {
            ((try? store.syncState.entities(type: type, tenantID: tenantID)) ?? [])
                .compactMap { try? AssetaJSON.decoder().decode(T.self, from: Data($0.json.utf8)) }
        }
        var book = HoursPriceBook()
        for p in rows(priceType, HoursPriceDTO.self) {
            book.prices[p.machineID] = HoursPrice(machineID: p.machineID, hourlyRate: p.hourlyRate.value,
                                                  minimumHours: p.minimumHours.value, currency: p.currency, minorUnits: p.minorUnits)
        }
        for d in rows(discountType, CustomerDiscountRateDTO.self) { book.discounts[d.customerID] = d.percent.value }
        return book
    }
}

extension FieldDirectory {
    /// Machine rates and customer discounts of the last pull (SYNC_HOURS_PRICES), for the hours sale total offline.
    public func hoursPrices() -> HoursPriceBook { HoursPricing.load(store: store, tenantID: tenantID) }
}

// MARK: - Payment lines

/// Where the payment lines of a sale stand against its offline total.
public enum PaymentStatus: Sendable, Equatable {
    case notPaid
    case fullyPaid
    case partPaid(balance: Decimal)
    /// The parts add up to more than the total: saving is blocked.
    case overTotal
    /// Paid something, but the total is not known on this phone (the office prices the sale).
    case noTotal
}

/// What is paid so far, the total when known, and the status.
public struct PaymentSummary: Sendable, Equatable {
    public let paid: Decimal
    public let quote: HoursSaleQuote?
    public let status: PaymentStatus
    public var balance: Decimal? { quote.map { max($0.amount - paid, 0) } }
}

/// Payment lines of an hours sale (same rules as Android `HoursPayments`).
public enum HoursPayments {
    /// `HoursPurchaseIn.payments` takes at most 10 parts.
    public static let max = 10

    /// The lines' valid amounts added up (a line without a valid amount counts as nothing yet).
    public static func paid(_ lines: [PaymentLine]) -> Decimal {
        lines.reduce(0) { $0 + (AccountabilityRules.value($1.amountText, decimals: AccountabilityRules.moneyDecimals) ?? 0) }
    }

    public static func summary(_ lines: [PaymentLine], price: HoursSalePrice) -> PaymentSummary {
        let paid = paid(lines)
        let quote = price.quote
        let status: PaymentStatus
        if paid == 0 {
            status = .notPaid
        } else if let quote {
            status = paid > quote.amount ? .overTotal : paid == quote.amount ? .fullyPaid : .partPaid(balance: quote.amount - paid)
        } else {
            status = .noTotal
        }
        return PaymentSummary(paid: paid, quote: quote, status: status)
    }

    /// A new line: `method`, with its amount set to what is still owed when the total is known (empty otherwise). The
    /// amount is filled once, when the line is added; typed values are never changed afterwards.
    public static func newLine(_ lines: [PaymentLine], price: HoursSalePrice, method: String = "CASH") -> PaymentLine {
        let balance = summary(lines, price: price).balance.flatMap { $0 > 0 ? $0 : nil }
        return PaymentLine(method: method, amountText: balance.map(AccountabilityRules.plain) ?? "", reference: "")
    }
}
