import AssetaModel
import AssetaStore
import Foundation

/// A machine's current hourly rate as the last pull delivered it (SYNC_HOURS_PRICES).
public struct HoursPrice: Sendable, Equatable {
    public let machineID: UUID
    public let hourlyRate: Decimal
    public let minimumHours: Decimal
    public let currency: String

    public init(machineID: UUID, hourlyRate: Decimal, minimumHours: Decimal, currency: String) {
        self.machineID = machineID
        self.hourlyRate = hourlyRate
        self.minimumHours = minimumHours
        self.currency = currency
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
}

/// What the hours sale form shows under Hours.
public enum HoursSalePrice: Sendable, Equatable {
    /// No machine yet, or no hours (or not a valid number): nothing is shown.
    case hidden
    /// The machine has no price on this phone: the office prices the sale when it arrives.
    case unpriced
    case priced(HoursSaleQuote)
}

/// The server's price rule for an hours sale, applied on the phone so the total shows offline (same rules as Android
/// `HoursPricing`): effective rate = hourly rate x (100 - discount) / 100, rounded to 4 decimals (half-even); total =
/// hours x effective rate, rounded half-up to the currency's minor units. A walk-in has no discount.
public enum HoursPricing {
    /// `sync_entity.entity_type` of the two snapshots.
    public static let priceType = "hours_price"
    public static let discountType = "customer_discount"

    static let zeroDecimals: Set<String> = ["BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF", "UGX", "UYI", "VND",
                                            "VUV", "XAF", "XOF", "XPF"]
    static let threeDecimals: Set<String> = ["BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"]

    /// ISO 4217 minor units (TZS 2, UGX 0, KWD 3); 2 for a code not listed, as the server's default.
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

    public static func quote(hours: Decimal, hourlyRate: Decimal, discountPercent: Decimal, currency: String) -> HoursSaleQuote {
        let effective = effectiveRate(hourlyRate, discountPercent: discountPercent)
        let amount = rounded(hours * effective, minorUnits(currency), .plain)
        return HoursSaleQuote(hours: hours, hourlyRate: hourlyRate, discountPercent: discountPercent, effectiveRate: effective,
                              amount: amount, currency: currency)
    }

    /// The form's price line: hidden until a machine and hours are entered; `walkIn` sales get no discount.
    public static func price(_ book: HoursPriceBook, machineID: UUID?, customerID: UUID?, walkIn: Bool, hoursText: String) -> HoursSalePrice {
        guard let machineID else { return .hidden }
        guard let hours = AccountabilityRules.saleHours(hoursText), hours > 0 else { return .hidden }
        guard let price = book.prices[machineID] else { return .unpriced }
        let discount = walkIn ? 0 : customerID.flatMap { book.discounts[$0] } ?? 0
        return .priced(quote(hours: hours, hourlyRate: price.hourlyRate, discountPercent: max(discount, 0), currency: price.currency))
    }

    /// "TZS 570,000"; "USD 12.50" when there are cents (the currency's minor units).
    public static func money(_ amount: Decimal, currency: String) -> String {
        let digits = rounded(amount, 0, .plain) == amount ? 0 : minorUnits(currency)
        return "\(currency) \(number(rounded(amount, digits, .plain), digits...digits))"
    }

    /// An hourly rate: grouping, up to 4 decimals ("95,000", "85,500.5").
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
                                                  minimumHours: p.minimumHours.value, currency: p.currency)
        }
        for d in rows(discountType, CustomerDiscountRateDTO.self) { book.discounts[d.customerID] = d.percent.value }
        return book
    }
}

extension FieldDirectory {
    /// Machine rates and customer discounts of the last pull (SYNC_HOURS_PRICES), for the hours sale total offline.
    public func hoursPrices() -> HoursPriceBook { HoursPricing.load(store: store, tenantID: tenantID) }
}
