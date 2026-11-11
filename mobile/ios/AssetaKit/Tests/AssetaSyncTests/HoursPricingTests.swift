@testable import AssetaSync
import AssetaModel
import AssetaStore
import AssetaTestSupport
import Foundation
import Testing

/// SYNC_HOURS_PRICES on the Supervisor app: the stored snapshots, the price rule and the wording (as Android
/// `HoursPricesSyncTest`, `HoursPricingTest` and `AccountabilityPresentationTest`).
@Suite("Hours sale total on the Supervisor app")
struct HoursPricingTests {
    static let ex01 = UUID(uuidString: "d0000000-0000-4000-8000-000000000001")!
    static let ex02 = UUID(uuidString: "d0000000-0000-4000-8000-000000000002")!
    static let ug01 = UUID(uuidString: "d0000000-0000-4000-8000-000000000003")!
    static let kw01 = UUID(uuidString: "d0000000-0000-4000-8000-000000000004")!
    static let acme = UUID(uuidString: "c0000000-0000-4000-8000-000000000001")!
    static let other = UUID(uuidString: "c0000000-0000-4000-8000-000000000002")!
    static let odd = UUID(uuidString: "c0000000-0000-4000-8000-000000000003")!
    static let on = [SyncCapability.supervisorInbox, SyncCapability.hoursPrices]

    static func d(_ text: String) -> Decimal { Decimal(string: text, locale: Locale(identifier: "en_US_POSIX"))! }

    static func price(_ machine: UUID, _ rate: String, currency: String = "TZS") -> [String: Any] {
        ["machine_id": machine.uuidString.lowercased(), "rate_card_id": "e0000000-0000-4000-8000-000000000001", "hourly_rate": rate,
         "minimum_hours": "0.0000", "currency": currency, "effective_from": "2026-01-01T00:00:00Z"]
    }

    static func discount(_ customer: UUID, _ percent: String) -> [String: Any] {
        ["customer_id": customer.uuidString.lowercased(), "percent": percent]
    }

    static let book = HoursPriceBook(
        prices: [ex01: HoursPrice(machineID: ex01, hourlyRate: d("95000.0000"), minimumHours: 0, currency: "TZS"),
                 ug01: HoursPrice(machineID: ug01, hourlyRate: d("33333.3333"), minimumHours: 0, currency: "UGX"),
                 kw01: HoursPrice(machineID: kw01, hourlyRate: d("12.3456"), minimumHours: 0, currency: "KWD")],
        discounts: [acme: d("10.00"), odd: d("12.5")])

    static func quote(_ machine: UUID, _ customer: UUID?, _ hours: String, walkIn: Bool = false) throws -> HoursSaleQuote {
        guard case let .priced(q) = HoursPricing.price(book, machineID: machine, customerID: customer, walkIn: walkIn, hoursText: hours) else {
            throw CancellationError()
        }
        return q
    }

    // MARK: - Storing

    @Test func pricesAreStoredReplacedAndClearedWithoutTheCapability() async throws {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate {
            $0.capabilities = Self.on
            $0.extraData = ["hours_prices": [Self.price(Self.ex01, "95000.0000"), Self.price(Self.ex02, "120000.0000")],
                            "customer_discounts": [Self.discount(Self.acme, "10.00"), Self.discount(Self.other, "5.00")]]
        }
        let engine = h.engine()
        _ = try await engine.sync()
        var book = h.directoryView.hoursPrices()
        #expect(Set(book.prices.keys) == [Self.ex01, Self.ex02])
        #expect(book.prices[Self.ex01]?.hourlyRate == 95000)
        #expect(book.discounts[Self.acme] == 10)
        guard case let .priced(q) = HoursPricing.price(book, machineID: Self.ex01, customerID: Self.acme, walkIn: false, hoursText: "6") else {
            Issue.record("not priced"); return
        }
        #expect(q.amount == 513_000)

        // The next pull replaces both sets: a rate changes, a machine and a discount leave.
        h.server.mutate {
            $0.extraData = ["hours_prices": [Self.price(Self.ex01, "100000.0000")], "customer_discounts": [Self.discount(Self.other, "7.50")]]
        }
        _ = try await engine.sync(force: true)
        book = h.directoryView.hoursPrices()
        #expect(Set(book.prices.keys) == [Self.ex01])
        #expect(book.prices[Self.ex01]?.hourlyRate == 100_000)
        #expect(book.discounts == [Self.other: Self.d("7.5")])
        #expect(HoursPricing.price(book, machineID: Self.ex02, customerID: Self.acme, walkIn: false, hoursText: "6") == .unpriced)

        // An empty snapshot leaves nothing.
        h.server.mutate { $0.extraData = [:] }
        _ = try await engine.sync(force: true)
        #expect(h.directoryView.hoursPrices() == HoursPriceBook())

        // Without the capability (switched off, or an older server) nothing is kept.
        h.server.mutate { $0.extraData = ["hours_prices": [Self.price(Self.ex01, "95000")], "customer_discounts": [Self.discount(Self.acme, "10")]] }
        _ = try await engine.sync(force: true)
        #expect(h.directoryView.hoursPrices().prices.count == 1)
        h.server.mutate { $0.capabilities = [SyncCapability.supervisorInbox] }
        _ = try await engine.sync(force: true)
        #expect(h.directoryView.hoursPrices() == HoursPriceBook())
    }

    // MARK: - Price rule

    @Test func totalIsHoursTimesTheRateRoundedToTheCurrency() throws {
        let q = try Self.quote(Self.ex01, nil, "6")
        #expect(q.effectiveRate == 95000 && q.amount == 570_000 && q.currency == "TZS" && q.discountPercent == 0)
        // Half-up to the currency's minor units: 2.25 h x 33,333.3333 = 74,999.999925 -> 75,000 (UGX has none).
        #expect(try Self.quote(Self.ug01, nil, "2.25").amount == 75000)
        // KWD keeps 3: 1.5 x 12.3456 = 18.5184 -> 18.518.
        #expect(try Self.quote(Self.kw01, nil, "1.5").amount == Self.d("18.518"))
        #expect(HoursPricing.quote(hours: Self.d("0.01"), hourlyRate: Self.d("0.5"), discountPercent: 0, currency: "KWD").amount == Self.d("0.005"))
        #expect(HoursPricing.quote(hours: 1, hourlyRate: Self.d("0.005"), discountPercent: 0, currency: "TZS").amount == Self.d("0.01"))
    }

    @Test func discountComesOffTheRateRoundedToFourDecimalsHalfEven() throws {
        let q = try Self.quote(Self.ex01, Self.acme, "6")
        #expect(q.effectiveRate == 85500 && q.amount == 513_000 && q.discountPercent == 10)
        #expect(try Self.quote(Self.ex01, Self.odd, "1").effectiveRate == 83125)
        // A tie at 4 decimals goes to the even digit (Python's default context): 1.00005 -> 1.0000, 1.00015 -> 1.0002.
        #expect(HoursPricing.effectiveRate(Self.d("1.00005"), discountPercent: 0) == 1)
        #expect(HoursPricing.effectiveRate(Self.d("1.00015"), discountPercent: 0) == Self.d("1.0002"))
        #expect(HoursPricing.effectiveRate(Self.d("2.0001"), discountPercent: 50) == 1)
        #expect(HoursPricing.effectiveRate(95000, discountPercent: 100) == 0)
    }

    @Test func walkInAndUnknownCustomersPayTheFullRate() throws {
        #expect(try Self.quote(Self.ex01, Self.acme, "6", walkIn: true).amount == 570_000)
        #expect(try Self.quote(Self.ex01, UUID(), "6").amount == 570_000)
        #expect(try Self.quote(Self.ex01, nil, "6").amount == 570_000)
    }

    @Test func nothingShowsWithoutAMachineOrHoursTheOfficePricesAMachineWithoutARate() {
        let b = Self.book
        #expect(HoursPricing.price(b, machineID: nil, customerID: Self.acme, walkIn: false, hoursText: "6") == .hidden)
        for hours in ["", "0", "1.234", "abc"] {
            #expect(HoursPricing.price(b, machineID: Self.ex01, customerID: Self.acme, walkIn: false, hoursText: hours) == .hidden)
        }
        #expect(HoursPricing.price(b, machineID: UUID(), customerID: Self.acme, walkIn: false, hoursText: "6") == .unpriced)
        #expect(HoursPricing.price(HoursPriceBook(), machineID: Self.ex01, customerID: nil, walkIn: true, hoursText: "6") == .unpriced)
    }

    @Test func minorUnitsAndFigures() {
        #expect(HoursPricing.minorUnits("TZS") == 2 && HoursPricing.minorUnits("ugx") == 0)
        #expect(HoursPricing.minorUnits("KWD") == 3 && HoursPricing.minorUnits("XYZ") == 2)
        #expect(HoursPricing.money(Self.d("570000.00"), currency: "TZS") == "TZS 570,000")
        #expect(HoursPricing.money(Self.d("1234.50"), currency: "USD") == "USD 1,234.50")
        #expect(HoursPricing.money(75000, currency: "UGX") == "UGX 75,000")
        #expect(HoursPricing.money(Self.d("18.518"), currency: "KWD") == "KWD 18.518")
        #expect(HoursPricing.rate(Self.d("95000.0000")) == "95,000")
        #expect(HoursPricing.rate(Self.d("33333.3333")) == "33,333.3333")
        #expect(HoursPricing.figure(6) == "6")
        #expect(HoursPricing.figure(Self.d("1234.50")) == "1,234.5")
        #expect(HoursPricing.figure(Self.d("12.50")) == "12.5")
    }

    // MARK: - Wording

    @Test func hoursSaleTotalWording() {
        let b = HoursPriceBook(prices: [Self.ex01: HoursPrice(machineID: Self.ex01, hourlyRate: Self.d("95000.0000"), minimumHours: 0, currency: "TZS")],
                               discounts: [Self.acme: Self.d("10.00")])
        func line(_ customer: UUID?, _ hours: String, walkIn: Bool = false, machine: UUID? = HoursPricingTests.ex01) -> String? {
            FieldAccountabilityTexts.hoursPrice(HoursPricing.price(b, machineID: machine, customerID: customer, walkIn: walkIn, hoursText: hours))
        }
        #expect(line(nil, "6") == "Total: TZS 570,000 (6 h × 95,000/h)")
        #expect(line(Self.acme, "6") == "Total: TZS 513,000 (6 h × 95,000/h less 10% discount)")
        #expect(line(Self.acme, "6", walkIn: true) == "Total: TZS 570,000 (6 h × 95,000/h)")
        #expect(line(Self.acme, "12.5") == "Total: TZS 1,068,750 (12.5 h × 95,000/h less 10% discount)")
        #expect(line(nil, "6", machine: UUID()) == "The price is set when the sale reaches the office.")
        #expect(line(nil, "") == nil)
        #expect(line(nil, "6", machine: nil) == nil)
    }
}
