@testable import AssetaSync
import AssetaModel
import AssetaStore
import AssetaTestSupport
import Foundation
import Testing

@Suite("DEC-032 Phase 4: open invoices on the Supervisor app")
struct OpenInvoicesTests {
    static let customer = UUID(uuidString: "aaaaaaaa-0000-4000-8000-0000000000c1")!
    static let other = UUID(uuidString: "aaaaaaaa-0000-4000-8000-0000000000c2")!
    static let all = CashDetailsTests.all + [SyncCapability.syncOpenInvoices]

    static func raw(_ id: UUID, number: String, customer: UUID = customer, currency: String = "TZS", balance: String = "500000.00",
                    due: String? = "2026-11-20") -> [String: Any] {
        ["id": id.uuidString.lowercased(), "invoice_number": number, "customer_id": customer.uuidString.lowercased(), "customer_name": "Acme",
         "currency": currency, "total": "900000.00", "paid": "400000.00", "balance": balance, "due_date": due as Any? ?? NSNull(),
         "issued_at": "2026-11-01T08:00:00Z"]
    }

    static func invoice(_ number: String, customer: UUID = customer, currency: String = "TZS", balance: String = "500000.00",
                        due: String? = "2026-11-20", issued: String = "2026-11-01T08:00:00Z") throws -> SyncOpenInvoiceDTO {
        let dueJSON = due.map { "\"\($0)\"" } ?? "null"
        let json = """
        {"id":"\(UUID().uuidString.lowercased())","invoice_number":"\(number)","customer_id":"\(customer.uuidString.lowercased())",
         "customer_name":"Acme","currency":"\(currency)","total":"900000.00","paid":"400000.00","balance":"\(balance)",
         "due_date":\(dueJSON),"issued_at":"\(issued)"}
        """
        return try AssetaJSON.decoder().decode(SyncOpenInvoiceDTO.self, from: Data(json.utf8))
    }

    @Test func eachPullReplacesTheLocalSet() async throws {
        let h = try SyncHarness().withFinanceData()
        let first = UUID(), second = UUID()
        h.server.mutate { $0.capabilities = Self.all; $0.openInvoices = [Self.raw(first, number: "INV-1"), Self.raw(second, number: "INV-2")] }
        let engine = h.engine()
        _ = try await engine.sync()
        #expect(Set(try h.directoryView.openInvoices().map(\.invoiceNumber)) == ["INV-1", "INV-2"])
        h.server.mutate { $0.openInvoices = [Self.raw(second, number: "INV-2", balance: "100.00")] }
        _ = try await engine.sync(force: true)
        let left = try h.directoryView.openInvoices()
        #expect(left.map(\.invoiceNumber) == ["INV-2"] && left[0].balance.value == 100)
        h.server.mutate { $0.openInvoices = [] }
        _ = try await engine.sync(force: true)
        #expect(try h.directoryView.openInvoices().isEmpty)
    }

    @Test func aServerWithoutTheCapabilityLeavesTheListAlone() async throws {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate { $0.capabilities = Self.all; $0.openInvoices = [Self.raw(UUID(), number: "INV-1")] }
        let engine = h.engine()
        _ = try await engine.sync()
        h.server.mutate { $0.capabilities = CashDetailsTests.all; $0.openInvoices = [] }
        _ = try await engine.sync(force: true)
        #expect(try h.directoryView.openInvoices().map(\.invoiceNumber) == ["INV-1"])
    }

    @Test func aServerThatDoesNotAnnounceInvoicesRefusesTheLink() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, CashDetailsTests.all)
        let invoice = try Self.invoice("INV-1")
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.serverTooOld)) {
            try h.recorder.recordCashCollection(customerID: Self.customer, amountText: "1", currency: "TZS", reference: nil, note: nil,
                                                receivedAt: h.clock.wallNow, invoice: invoice)
        }
    }

    @Test func optionsAreTheCustomersInCurrencySoonestDueFirst() throws {
        let invoices = [try Self.invoice("LATE", due: "2026-12-01"), try Self.invoice("NODUE", due: nil),
                        try Self.invoice("SOON", due: "2026-11-15"), try Self.invoice("USD", currency: "USD"),
                        try Self.invoice("OTHER", customer: Self.other)]
        #expect(OpenInvoices.options(invoices, customerID: Self.customer, currency: " tzs").map(\.invoiceNumber) == ["SOON", "LATE", "NODUE"])
        #expect(OpenInvoices.options(invoices, customerID: Self.customer, currency: "").isEmpty) // none until a currency is entered
        #expect(OpenInvoices.options(invoices + [try Self.invoice("PAID", balance: "0.00")], customerID: Self.customer, currency: "TZS").count == 3)
        #expect(OpenInvoices.options(invoices, customerID: nil, currency: "TZS").isEmpty)
    }

    @Test func allocationIsCappedAtTheOpenBalance() throws {
        let invoice = try Self.invoice("INV", balance: "1000.00")
        #expect(OpenInvoices.allocation(amount: 400, invoice: invoice) == 400)
        #expect(OpenInvoices.allocation(amount: 2500, invoice: invoice) == 1000)
    }

    @Test func payloadOmitsAllocationsUnlessAnInvoiceIsNamed() throws {
        let plain = CashCollectionPayload(clientID: UUID(), customerID: Self.customer, amount: 5, currency: "TZS", receivedAt: Date(), reference: nil, note: nil)
        let keys = try #require(try JSONSerialization.jsonObject(with: AssetaJSON.encoder().encode(plain)) as? [String: Any])
        #expect(keys["allocations"] == nil)
        let invoiceID = UUID()
        let linked = CashCollectionPayload(clientID: UUID(), customerID: Self.customer, amount: 5, currency: "TZS", receivedAt: Date(), reference: nil,
                                           note: nil, allocations: [CollectionAllocation(invoiceID: invoiceID, amount: 5)])
        let body = try #require(try JSONSerialization.jsonObject(with: AssetaJSON.encoder().encode(linked)) as? [String: Any])
        let row = try #require((body["allocations"] as? [[String: Any]])?.first)
        #expect((row["invoice_id"] as? String)?.lowercased() == invoiceID.uuidString.lowercased() && row["amount"] as? String == "5")
    }
}

@Suite("DEC-032 Phase 4: Pays for lists invoices")
struct CollectionInvoiceLinkTests {
    typealias O = OpenInvoicesTests

    @Test func optionsAddInvoicesForTheCustomerAndCurrency() throws {
        let invoices = [try O.invoice("TZS-1"), try O.invoice("USD-1", currency: "USD"), try O.invoice("X", customer: O.other)]
        let tzs = CollectionLinks.options(purchases: [], unsynced: [], customerID: O.customer, invoices: invoices, currency: "tzs")
        #expect(tzs.map(\.title) == ["TZS-1"] && tzs[0].invoice != nil)
        #expect(tzs[0].subtitle == "Invoice · 500000 TZS due")
        #expect(CollectionLinks.options(purchases: [], unsynced: [], customerID: nil, invoices: invoices, currency: "TZS").isEmpty)
    }

    @Test func conflictWordingMatchesTheStringsDoc() {
        let t = FieldAccountabilityTexts.self
        #expect(t.conflictText("INVOICE_NOT_OPEN") == "This invoice is no longer open. Record it again and choose another.")
        #expect(t.conflictText("ALLOCATION_MISMATCH") == "What you chose is for another customer or currency. Record it again and choose another.")
        #expect(t.conflictText("OVER_ALLOCATION") == "This is more than the purchase or invoice still owes. Record it again with the right amount.")
    }
}
