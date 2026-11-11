@testable import AssetaSync
import AssetaCapture
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

    @Test func theServersMinorUnitsWinOverTheISOTable() async throws {
        // A tenant whose TZS has no cents: 2.5 h x 33,333.3333 = 83,333.33325 -> 83,333.
        let noCents = HoursPriceBook(prices: [Self.ex01: HoursPrice(machineID: Self.ex01, hourlyRate: Self.d("33333.3333"), minimumHours: 0,
                                                                    currency: "TZS", minorUnits: 0)])
        guard case let .priced(q) = HoursPricing.price(noCents, machineID: Self.ex01, customerID: nil, walkIn: false, hoursText: "2.5") else {
            Issue.record("not priced"); return
        }
        #expect(q.amount == 83333 && q.minorUnits == 0)
        // Without the field (an older server) the ISO table applies: 83,333.33.
        let iso = HoursPriceBook(prices: [Self.ex01: HoursPrice(machineID: Self.ex01, hourlyRate: Self.d("33333.3333"), minimumHours: 0,
                                                                currency: "TZS")])
        #expect(HoursPricing.price(iso, machineID: Self.ex01, customerID: nil, walkIn: false, hoursText: "2.5").quote?.amount
                == Self.d("83333.33"))
        #expect(HoursPricing.money(Self.d("1234.567"), currency: "TZS", minorUnits: 3) == "TZS 1,234.567")
        // Stored from sync: the server's value, else the table.
        let h = try SyncHarness().withFinanceData()
        h.server.mutate {
            $0.capabilities = Self.on
            var withUnits = Self.price(Self.ex01, "33333.3333")
            withUnits["minor_units"] = 0
            $0.extraData = ["hours_prices": [withUnits, Self.price(Self.ex02, "33333.3333", currency: "UGX")]]
        }
        _ = try await h.engine().sync()
        let book = h.directoryView.hoursPrices()
        #expect(book.prices[Self.ex01]?.minorUnits == 0 && book.prices[Self.ex02]?.minorUnits == 0)
    }

    // MARK: - Payment lines

    static func lines(_ amounts: String...) -> [PaymentLine] { amounts.map { PaymentLine(amountText: $0) } }

    @Test func paymentLinesAgainstTheTotal() {
        let price = HoursPricing.price(Self.book, machineID: Self.ex01, customerID: nil, walkIn: false, hoursText: "6") // 570,000
        func s(_ amounts: String...) -> PaymentSummary { HoursPayments.summary(amounts.map { PaymentLine(amountText: $0) }, price: price) }
        #expect(s().status == .notPaid && s().balance == 570_000)
        #expect(s("300000", "270000").status == .fullyPaid)
        #expect(s("300000").status == .partPaid(balance: 270_000))
        #expect(s("300000", "270000.01").status == .overTotal)
        #expect(s("600000").balance == 0)
        #expect(s("300000", "abc", "").paid == 300_000) // a line without a valid amount counts as nothing yet
        #expect(HoursPayments.summary(Self.lines("5"), price: .unpriced).status == .noTotal)
        // A new line takes what is still owed, once; without a total it starts empty.
        #expect(HoursPayments.newLine([], price: price) == PaymentLine(method: "CASH", amountText: "570000"))
        #expect(HoursPayments.newLine(Self.lines("300000"), price: price).amountText == "270000")
        #expect(HoursPayments.newLine(Self.lines("570000"), price: price).amountText == "")
        #expect(HoursPayments.newLine([], price: .unpriced).amountText == "")
    }

    @Test func theOpeningCashLineFollowsTheTotalUntilTypedInto() {
        func p(_ hours: String, _ customer: UUID? = nil, machine: UUID? = nil) -> HoursSalePrice {
            HoursPricing.price(Self.book, machineID: machine ?? Self.ex01, customerID: customer, walkIn: false, hoursText: hours)
        }
        let opened = HoursSaleDraft.newSale()
        #expect(opened.payments == [PaymentLine(method: "CASH", amountText: "", followsTotal: true)])
        #expect(HoursSaleDraft().payments.isEmpty)
        // Total unknown: stays empty (and still needs an amount to save).
        #expect(HoursPayments.follow(opened.payments, price: .hidden).first?.amountText == "")
        #expect(HoursPayments.follow(opened.payments, price: .unpriced).first?.amountText == "")
        let six = HoursPayments.follow(opened.payments, price: p("6"))
        #expect(six.first?.amountText == "570000")
        #expect(HoursPayments.summary(six, price: p("6")).status == .fullyPaid)
        // Hours, customer (discount) and machine change the total: the line follows.
        let four = HoursPayments.follow(six, price: p("4"))
        #expect(four.first?.amountText == "380000")
        #expect(HoursPayments.follow(four, price: p("4", Self.acme)).first?.amountText == "342000")
        #expect(HoursPayments.follow(four, price: p("4", machine: UUID())).first?.amountText == "")
        // Typed: never changed again.
        var typed = four
        typed[0].typedAmount = "100000"
        #expect(typed == [PaymentLine(method: "CASH", amountText: "100000")])
        #expect(HoursPayments.follow(typed, price: p("6")) == typed)
        // A method change keeps it following; a later line is filled once and never follows.
        var bank = six
        bank[0].method = "BANK"
        #expect(HoursPayments.follow(bank, price: p("4")) == [PaymentLine(method: "BANK", amountText: "380000", followsTotal: true)])
        #expect(!HoursPayments.newLine(Self.lines("300000"), price: p("6")).followsTotal)
        // Removed: no lines, not paid yet.
        #expect(HoursPayments.summary([], price: p("6")).status == .notPaid)
    }

    @Test func saveBlockersSayWhySaveIsOff() {
        let price = HoursPricing.price(Self.book, machineID: Self.ex01, customerID: nil, walkIn: false, hoursText: "6")
        func draft(_ lines: [PaymentLine], machine: Bool = true, hours: String = "6", customer: Bool = true) -> HoursSaleDraft {
            var d = HoursSaleDraft()
            d.customerID = customer ? Self.acme : nil
            d.machineID = machine ? Self.ex01 : nil
            d.hoursText = hours
            d.payments = lines
            return d
        }
        func blockers(_ d: HoursSaleDraft, noncash: Bool = true, p: HoursSalePrice? = nil) -> String? {
            AccountabilityRules.hoursSaleBlockers(d, walkInAllowed: false, noncashAllowed: noncash, price: p ?? price)
        }
        let cash = PaymentLine(method: "CASH", amountText: "300000")
        let bank = PaymentLine(method: "BANK", amountText: "100000")
        let mobile = PaymentLine(method: "MOBILE_MONEY", amountText: "170000")
        // Fully paid but the references are missing: Save is off and the line says why.
        #expect(blockers(draft([cash, bank, mobile])) == "To save: enter the reference for payments 2 and 3.")
        #expect(AccountabilityRules.referenceMissing(bank) && !AccountabilityRules.referenceMissing(cash))
        #expect(!AccountabilityRules.referenceMissing(PaymentLine(method: "BANK", amountText: "1", reference: "CRDB")))
        #expect(FieldAccountabilityTexts.hoursReferenceLine == "Enter the reference for this payment")
        var withRefs = [cash, bank, mobile]
        withRefs[1].reference = "R1"
        withRefs[2].reference = "R2"
        #expect(blockers(draft(withRefs)) == nil)
        #expect(blockers(draft([PaymentLine(method: "CASH")])) == "To save: enter the amount for payment 1.")
        #expect(blockers(draft([PaymentLine(amountText: "abc"), PaymentLine(amountText: "0")])) == "To save: enter the amount for payments 1 and 2.")
        #expect(blockers(draft([cash, cash])) == "To save: lower the payments to the total of TZS 570,000.")
        #expect(blockers(draft([PaymentLine(amountText: "5")], machine: false, hours: ""), p: .hidden)
                == "To save: choose the machine and enter the hours (more than 0).")
        #expect(blockers(draft([], customer: false)) == "To save: choose the customer.")
        #expect(blockers(draft([cash, bank]), noncash: false) == "To save: change payment 2 to cash and enter the reference for payment 2.")
        #expect(blockers(draft([])) == nil) // not paid yet
        var walkIn = draft([])
        walkIn.walkIn = true
        walkIn.walkInName = "Juma"
        #expect(AccountabilityRules.hoursSaleBlockers(walkIn, walkInAllowed: false) == "To save: choose a registered customer.")
        #expect(FieldAccountabilityTexts.hoursPayments([1, 2, 3]) == "payments 1, 2 and 3")
    }

    @Test func splitRules() {
        let price = HoursPricing.price(Self.book, machineID: Self.ex01, customerID: nil, walkIn: false, hoursText: "6")
        func draft(_ lines: [PaymentLine]) -> HoursSaleDraft {
            var d = HoursSaleDraft()
            d.customerID = Self.acme
            d.machineID = Self.ex01
            d.hoursText = "6"
            d.payments = lines
            return d
        }
        func problems(_ d: HoursSaleDraft, noncash: Bool = true, price p: HoursSalePrice = .hidden) -> [String] {
            if case let .failure(found) = AccountabilityRules.hoursSale(d, walkInAllowed: false, noncashAllowed: noncash, price: p) {
                return found.messages
            }
            return []
        }
        let cash = PaymentLine(method: "CASH", amountText: "300000")
        let bank = PaymentLine(method: "BANK", amountText: "270000")
        #expect(problems(draft([cash, bank]), price: price) == [FieldAccountabilityTexts.hoursErrReference])
        #expect(problems(draft([cash, bank]), noncash: false, price: price)
                == [FieldAccountabilityTexts.hoursErrNoncashOff, FieldAccountabilityTexts.hoursErrReference])
        var withRef = bank
        withRef.reference = "CRDB"
        guard case let .success(ok) = AccountabilityRules.hoursSale(draft([cash, withRef]), walkInAllowed: false, noncashAllowed: true,
                                                                    price: price) else { Issue.record("invalid"); return }
        #expect(ok.payments.map(\.method) == ["CASH", "BANK"])
        #expect(problems(draft([cash, cash]), price: price) == [FieldAccountabilityTexts.hoursErrPaymentsExceed("TZS 570,000")])
        #expect(problems(draft([cash, cash]), price: .unpriced).isEmpty) // without a known total the server checks it
        #expect(problems(draft(Array(repeating: PaymentLine(amountText: "1"), count: 11))) == [FieldAccountabilityTexts.hoursErrTooManyPayments])
        #expect(problems(draft([cash])).isEmpty)
    }

    @Test func methodsFollowTheTenantPolicy() throws {
        func access(_ extra: String) throws -> FieldAccess {
            let json = #"{"enabled":true,"walk_in_allowed":false,"transfer_requires_approval":true,"reason_code_required":false"# + extra + "}"
            let hours = try AssetaJSON.decoder().decode(CustomerHoursPolicyValues.self, from: Data(json.utf8))
            return FieldAccess(capabilities: [SyncCapability.hoursPurchase], permissions: ["tenant.hours.purchase"], hours: hours)
        }
        #expect(try access("").saleMethods == ["CASH"])
        #expect(try access(#","field_noncash_payments":true"#).saleMethods == ["CASH", "BANK", "MOBILE_MONEY"])
        #expect(try access(#","field_noncash_payments":false"#).saleMethods == ["CASH"])
    }

    @Test func cashActivationFollowsTheTenantPolicyAndMissingMeansVerify() throws {
        func access(_ extra: String) throws -> FieldAccess {
            let json = #"{"enabled":true,"walk_in_allowed":false,"transfer_requires_approval":true,"reason_code_required":false"# + extra + "}"
            let hours = try AssetaJSON.decoder().decode(CustomerHoursPolicyValues.self, from: Data(json.utf8))
            return FieldAccess(capabilities: [SyncCapability.hoursPurchase], permissions: ["tenant.hours.purchase"], hours: hours)
        }
        #expect(try access("").cashActivation == .verify)
        #expect(try access(#","cash_activation":"VERIFY""#).cashActivation == .verify)
        #expect(try access(#","cash_activation":"ON_HANDOVER""#).cashActivation == .onHandover)
        #expect(try access(#","cash_activation":"ON_RECORDING""#).cashActivation == .onRecording)
        #expect(try access(#","cash_activation":"SOMETHING_NEW""#).cashActivation == .verify)
        #expect(try access(#","cash_activation":null"#).cashActivation == .verify)
        #expect(try access(#","cash_activation":"ON_RECORDING""#).sellHours)
        #expect(FieldAccess(capabilities: nil, permissions: []).cashActivation == .verify) // policy unknown
    }

    @Test func paymentFooterFollowsTheLinesAndTheCashActivationPolicy() {
        typealias T = FieldAccountabilityTexts
        func footer(_ a: HoursCashActivation, _ m: String...) -> String { T.hoursPaymentFooter(methods: m, activation: a) }
        let verified = "Hours become available only after someone else verifies this payment."
        let withCashParts = verified + " Cash parts: hand them over; the office confirms the handover."
        let onSync = "The hours are available once this sale syncs. You hold this cash until you hand it over."
        let onHandover = "The hours become available when the office confirms your handover of this cash."
        // VERIFY: unchanged for every mix.
        #expect(footer(.verify, "CASH") == verified)
        #expect(footer(.verify, "CASH", "CASH") == verified)
        #expect(footer(.verify, "CASH", "BANK") == verified)
        #expect(footer(.verify, "MOBILE_MONEY") == verified)
        // Only cash.
        #expect(footer(.onRecording, "CASH") == onSync)
        #expect(footer(.onRecording, "CASH", "CASH") == onSync)
        #expect(footer(.onHandover, "CASH") == onHandover)
        #expect(footer(.onHandover, "CASH", "CASH") == onHandover)
        // Cash with bank or mobile money.
        #expect(footer(.onRecording, "CASH", "BANK") == withCashParts)
        #expect(footer(.onHandover, "MOBILE_MONEY", "CASH") == withCashParts)
        // No cash: bank and mobile money always wait for verification.
        #expect(footer(.onRecording, "BANK") == verified)
        #expect(footer(.onHandover, "BANK", "MOBILE_MONEY") == verified)
    }

    @Test func splitSaleIsQueuedWithItsPartsInOrderAndRetriesStayExactlyOnce() async throws {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate {
            $0.capabilities = AccountabilityTests.all + [SyncCapability.hoursPrices]
            $0.extraData = ["hours_prices": [Self.price(SyncFixtures.machineID, "95000.0000")]]
        }
        let engine = h.engine()
        _ = try await engine.sync()
        var draft = HoursSaleDraft()
        draft.customerID = FinanceFixtures.customerID
        draft.machineID = SyncFixtures.machineID
        draft.hoursText = "6"
        draft.payments = [PaymentLine(method: "CASH", amountText: "300000", reference: "ignored for cash"),
                          PaymentLine(method: "BANK", amountText: "200000", reference: " CRDB-77 "),
                          PaymentLine(method: "MOBILE_MONEY", amountText: "70000", reference: "MP-1")]
        let holder = UUID(), clientID = UUID()
        let op = try h.recorder.recordHoursSale(draft, walkInAllowed: false, cashHolderID: holder, evidence: [], receivedAt: h.clock.wallNow,
                                                clientID: clientID, noncashAllowed: true)
        let p = try JSONValue.parse(op.payloadJSON)
        #expect(p["client_id"]?.stringValue == clientID.lowercased && p["payment"] == nil)
        guard case let .array(parts)? = p["payments"] else { Issue.record("no payments"); return }
        #expect(parts.map { $0["method"]?.stringValue } == ["CASH", "BANK", "MOBILE_MONEY"])
        #expect(parts.map { $0["amount"]?.stringValue } == ["300000", "200000", "70000"])
        #expect(parts.map { $0["reference"]?.stringValue } == [nil, "CRDB-77", "MP-1"])
        // Cash goes to the named holder's custody; bank and mobile money name no holder.
        #expect(parts.map { $0["staff_member_id"]?.stringValue } == [holder.lowercased, nil, nil])
        // The same form saved again is the same sale (the server keys the parts uuid5(client_id, "payment"/"payment-n")).
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved)) {
            try h.recorder.recordHoursSale(draft, walkInAllowed: false, cashHolderID: holder, evidence: [], receivedAt: h.clock.wallNow,
                                           clientID: clientID, noncashAllowed: true)
        }
        _ = try await engine.sync(force: true)
        #expect(try h.status(op.id) == .acked)
        #expect((h.server.read { $0.appliedPayloads[op.id] }?["payments"] as? [Any])?.count == 3)

        // One part travels as `payment`; none as not paid yet.
        draft.payments = [PaymentLine(amountText: "570000")]
        let one = try JSONValue.parse(try h.recorder.recordHoursSale(draft, walkInAllowed: false, cashHolderID: nil, evidence: [],
                                                                    receivedAt: h.clock.wallNow).payloadJSON)
        #expect(one["payment"]?["amount"]?.stringValue == "570000" && one["payments"] == nil)
        draft.payments = []
        let none = try JSONValue.parse(try h.recorder.recordHoursSale(draft, walkInAllowed: false, cashHolderID: nil, evidence: [],
                                                                     receivedAt: h.clock.wallNow).payloadJSON)
        #expect(none["payment"] == nil && none["payments"] == nil)
        // The opening Cash line, followed to the total, travels as one cash `payment`.
        let quote = HoursPricing.quote(hours: 6, hourlyRate: 95000, discountPercent: 0, currency: "TZS", minorUnits: 2)
        draft.payments = HoursPayments.follow(HoursSaleDraft.newSale().payments, price: .priced(quote))
        let opening = try JSONValue.parse(try h.recorder.recordHoursSale(draft, walkInAllowed: false, cashHolderID: nil, evidence: [],
                                                                        receivedAt: h.clock.wallNow).payloadJSON)
        #expect(opening["payment"]?["method"]?.stringValue == "CASH" && opening["payment"]?["amount"]?.stringValue == "570000")
        #expect(opening["payments"] == nil)

        // Above the total (6 h x 95,000 = 570,000) and bank without the policy are refused.
        draft.payments = [PaymentLine(amountText: "300000"), PaymentLine(amountText: "270000.01")]
        #expect(throws: FieldRecorderError.invalid(FieldAccountabilityTexts.hoursErrPaymentsExceed("TZS 570,000"))) {
            try h.recorder.recordHoursSale(draft, walkInAllowed: false, cashHolderID: nil, evidence: [], receivedAt: h.clock.wallNow)
        }
        draft.payments = [PaymentLine(method: "BANK", amountText: "100", reference: "REF")]
        #expect(throws: FieldRecorderError.invalid(FieldAccountabilityTexts.hoursErrNoncashOff)) {
            try h.recorder.recordHoursSale(draft, walkInAllowed: false, cashHolderID: nil, evidence: [], receivedAt: h.clock.wallNow)
        }
    }

    @Test func eachSplitPartCarriesItsOwnEvidenceAndTheOpWaitsForEveryUpload() async throws {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate { $0.capabilities = AccountabilityTests.all }
        let engine = h.engine()
        _ = try await engine.sync()
        func photo(_ seed: Int) throws -> StoredEvidence {
            try h.evidence.store(Data((0..<1500).map { UInt8(($0 + seed) % 251) }), fileExtension: "jpg", contentType: "image/jpeg")
        }
        var draft = HoursSaleDraft()
        draft.customerID = FinanceFixtures.customerID
        draft.machineID = SyncFixtures.machineID
        draft.hoursText = "6"
        draft.payments = [PaymentLine(method: "CASH", amountText: "300000"), PaymentLine(method: "BANK", amountText: "200000", reference: "CRDB-77"),
                          PaymentLine(method: "MOBILE_MONEY", amountText: "70000", reference: "MP-1")]
        let op = try h.recorder.recordHoursSale(draft, walkInAllowed: false, cashHolderID: nil,
                                                evidence: [[], [try photo(1), try photo(2)], [try photo(3)]],
                                                receivedAt: h.clock.wallNow, noncashAllowed: true)
        // Queued: each part names its photos by local id; the op-level list stays empty; not sendable before the uploads.
        let queued = try JSONValue.parse(op.payloadJSON)
        guard case let .array(before)? = queued["payments"] else { Issue.record("no payments"); return }
        func ids(_ part: JSONValue) -> [String] {
            if case let .array(list)? = part["evidence_upload_ids"] { return list.compactMap(\.stringValue) }
            return []
        }
        #expect(part0Empty(before[0]) && ids(before[1]).count == 2 && ids(before[2]).count == 1)
        #expect(queued["evidence_upload_ids"] == JSONValue.array([]))
        #expect(try h.store.outbox.readyToSend(tenantID: SyncFixtures.tenant, now: h.clock.wallNow, limit: 10).isEmpty)
        _ = try await engine.sync(force: true)
        #expect(try h.status(op.id) == .acked)
        let applied = try #require(h.server.read { $0.appliedPayloads[op.id] })
        let parts = try #require(applied["payments"] as? [[String: Any]])
        let uploads = Set(h.server.read { $0.blobs.keys.map { "\($0)".lowercased() } })
        #expect(uploads.count == 3)
        #expect(parts[0]["evidence_upload_ids"] == nil)
        let named = ((parts[1]["evidence_upload_ids"] as? [String]) ?? []) + ((parts[2]["evidence_upload_ids"] as? [String]) ?? [])
        #expect(Set(named.map { $0.lowercased() }) == uploads)
        #expect((applied["evidence_upload_ids"] as? [Any])?.isEmpty == true)
    }

    private func part0Empty(_ part: JSONValue) -> Bool { part["evidence_upload_ids"] == nil }

    // MARK: - Wording

    @Test func hoursSalePaymentWording() {
        let b = HoursPriceBook(prices: [Self.ex01: HoursPrice(machineID: Self.ex01, hourlyRate: 95000, minimumHours: 0, currency: "TZS", minorUnits: 2)])
        let price = HoursPricing.price(b, machineID: Self.ex01, customerID: nil, walkIn: false, hoursText: "6")
        func lines(_ amounts: String..., p: HoursSalePrice? = nil) -> [String] {
            FieldAccountabilityTexts.hoursPaymentSummary(HoursPayments.summary(amounts.map { PaymentLine(amountText: $0) }, price: p ?? price))
        }
        #expect(lines() == ["Paid TZS 0 of TZS 570,000 · Balance TZS 570,000", "Not paid yet"])
        #expect(lines("300000") == ["Paid TZS 300,000 of TZS 570,000 · Balance TZS 270,000", "Part paid (balance TZS 270,000)"])
        #expect(lines("300000", "270000") == ["Paid TZS 570,000 of TZS 570,000 · Balance TZS 0", "Fully paid"])
        #expect(lines("300000", "270000.50")
                == ["Paid TZS 570,000.50 of TZS 570,000 · Balance TZS 0", "The payments add up to more than the total of TZS 570,000."])
        #expect(lines("300000", p: .unpriced) == ["Paid 300,000"])
        #expect(lines(p: .unpriced) == ["Not paid yet"])
        #expect(FieldAccountabilityTexts.hoursNoncashByOffice == "Bank and mobile-money payments are recorded by the office.")
        #expect(FieldAccountabilityTexts.hoursAddPayment == "Add payment")
        #expect(FieldAccountabilityTexts.hoursPaymentNumber(2) == "Payment 2")
        #expect(FieldAccountabilityTexts.hoursLinePhoto == "Photo of the slip or message (optional)")
    }

    @Test func hoursSaleOnTheSyncScreenListsItsPayments() throws {
        func title(_ json: String?) throws -> String? {
            FieldAccountabilityTexts.operationTitle(.hoursPurchase, payload: try json.map { try JSONValue.parse($0) })
        }
        #expect(try title(nil) == "Hours sale")
        #expect(try title(#"{"hours":"6"}"#) == "Hours sale · Not paid yet")
        #expect(try title(#"{"payment":{"method":"CASH","amount":"570000"}}"#) == "Hours sale · Cash 570,000")
        #expect(try title(#"{"payments":[{"method":"CASH","amount":"300000"},{"method":"BANK","amount":"200000"},{"method":"MOBILE_MONEY","amount":"70000.50"}]}"#)
                == "Hours sale · Cash 300,000 + Bank 200,000 + Mobile money 70,000.5")
    }

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
