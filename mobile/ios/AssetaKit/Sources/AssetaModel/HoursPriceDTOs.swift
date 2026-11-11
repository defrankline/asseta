import Foundation

// Hours sale prices on the Supervisor app (SYNC_HOURS_PRICES): `contracts/openapi.json` `HoursPriceDto` and
// `CustomerDiscountRateDto`; money and percent are decimal strings. Same shapes as Android `HoursPriceDtos.kt`.

extension SyncCapability {
    /// `SyncData.hours_prices` and `customer_discounts` (full snapshots): the phone shows the total of an hours sale as the
    /// hours are typed, offline, with the server's price rule.
    public static let hoursPrices = "SYNC_HOURS_PRICES"
}

/// `HoursPriceDto`: a machine's current hourly rate (its type's rate card), for pricing a sale offline.
public struct HoursPriceDTO: Codable, Hashable, Sendable {
    public let machineID: UUID
    public let rateCardID: UUID
    public let hourlyRate: DecimalString
    public let minimumHours: DecimalString
    public let currency: String
    public let effectiveFrom: Date

    enum CodingKeys: String, CodingKey {
        case machineID = "machine_id", rateCardID = "rate_card_id", hourlyRate = "hourly_rate", minimumHours = "minimum_hours"
        case currency, effectiveFrom = "effective_from"
    }
}

/// `CustomerDiscountRateDto`: a customer's approved discount in force today, percent off the hourly rate.
public struct CustomerDiscountRateDTO: Codable, Hashable, Sendable {
    public let customerID: UUID
    public let percent: DecimalString

    enum CodingKeys: String, CodingKey {
        case customerID = "customer_id", percent
    }
}
