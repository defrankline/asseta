@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// Go-live fix: the boss confirms or rejects customer payments from the phone. Same as Android `PaymentReviewOwnerTest`.
struct PaymentReviewOwnerTests {
    typealias T = PaymentReviewText
    static let id = UUID(uuidString: "11111111-1111-4111-8111-111111111111")!
    static let recorder = UUID(uuidString: "22222222-2222-4222-8222-222222222222")!
    static let invoice = UUID(uuidString: "33333333-3333-4333-8333-333333333333")!
    static let readAndVerify = ["tenant.finance.read", "tenant.finance.verify"]
    let utc = TimeZone(identifier: "UTC")!
    let money: (DecimalString, String) -> String = { "\($1) \($0.description)" }

    static func json(status: String = "CLAIMED", recordedBy: String? = recorder.uuidString.lowercased(), recordedByName: String? = "Asha Mwita",
                     customerName: String? = "Kilimo Ltd", released: String = "null") -> String {
        func q(_ s: String?) -> String { s.map { "\"\($0)\"" } ?? "null" }
        let inv = invoice.uuidString.lowercased()
        return """
        {"id":"\(id.uuidString.lowercased())","customer_id":"\(recorder.uuidString.lowercased())","customer_name":\(q(customerName)),"client_id":null,"amount":"50000.00","currency":"TZS",
        "method":"MOBILE_MONEY","reference":"MP-77","received_at":"2026-11-01T07:00:00Z","received_by_staff_id":"\(recorder.uuidString.lowercased())","received_by_staff_name":"Juma",
        "status":"\(status)","note":"Paid at site","source":"FIELD","recorded_by":\(q(recordedBy)),"recorded_by_name":\(q(recordedByName)),"recorded_at":"2026-11-01T08:00:00Z",
        "verified_by":null,"verified_at":null,"decision_note":null,"collection_number":"COL-12",
        "allocations":[{"id":"\(inv)","invoice_id":"\(inv)","amount":"30000.00","created_at":"2026-11-01T08:00:00Z","released_at":\(released),"release_reason":null}],
        "purchase_links":[{"purchase_id":"\(inv)","purchase_number":"HP-9","amount":"20000.00"}]}
        """
    }

    static func payment(_ json: String = json()) throws -> CustomerPaymentRecordDTO {
        try AssetaJSON.decoder().decode(CustomerPaymentRecordDTO.self, from: Data(json.utf8))
    }

    @Test func listAsksOnlyForClaimedPayments() throws {
        let request = OwnerAPI.paymentsToConfirm()
        #expect(request.path.hasSuffix("/customer-payments"))
        #expect(request.queryItems.contains(URLQueryItem(name: "status", value: "CLAIMED")))
        #expect(request.queryItems.contains(URLQueryItem(name: "page_size", value: "100")))
    }

    @Test func decodesTheContractAndNamesTheRow() throws {
        #expect(try Contract.missingRequired(schema: "CustomerPaymentDto", json: Self.json()) == [])
        let p = try Self.payment()
        #expect(T.headline(p, money: money) == "Kilimo Ltd paid TZS 50000")
        #expect(T.summary(p) == "Mobile money · COL-12")
        #expect(T.recordedBy(p) == "Recorded by Asha Mwita")
        #expect(T.headline(try Self.payment(Self.json(customerName: nil)), money: money) == "A customer paid TZS 50000")
    }

    @Test func factsAreNamedInScreenOrder() throws {
        let fields = T.fields(try Self.payment(), timeZone: utc)
        #expect(fields.map(\.label) == ["Customer", "Amount", "Method", "Reference", "Collection number", "Received", "Received by", "Recorded by", "Recorded", "Note"])
        #expect(fields.first { $0.label == "Recorded by" }?.value == "Asha Mwita")
        #expect(T.fields(try Self.payment(Self.json(customerName: nil)), timeZone: utc).first?.value == "22222222")
    }

    @Test func linksNameThePurchaseAndInvoice() throws {
        let p = try Self.payment()
        #expect(T.purchases(p, money: money).map(\.text) == ["HP-9 · TZS 20000"])
        #expect(T.invoices(p, numbers: [Self.invoice: "INV-4"], money: money) == ["INV-4 · TZS 30000"])
        #expect(T.invoices(p, numbers: [:], money: money) == ["33333333 · TZS 30000"])
        #expect(T.invoices(try Self.payment(Self.json(released: #""2026-11-02T08:00:00Z""#)), numbers: [:], money: money).isEmpty)
    }

    @Test func methodsAndStatusesInPlainWords() {
        #expect(T.method("CASH") == "Cash")
        #expect(T.method("BANK") == "Bank transfer")
        #expect(T.status("CLAIMED") == "Waiting to be confirmed")
        #expect(T.status("VERIFIED") == "Confirmed")
        #expect(T.status("REJECTED") == "Rejected")
    }

    @Test func rejectionNeedsAReasonOfThreeCharacters() {
        #expect(T.canDecide(confirm: true, note: ""))
        #expect(!T.canDecide(confirm: false, note: ""))
        #expect(!T.canDecide(confirm: false, note: " ab "))
        #expect(T.canDecide(confirm: false, note: "abc"))
        #expect(!T.canDecide(confirm: true, note: String(repeating: "x", count: 1001)))
    }

    @Test func decisionIsSentWithoutAmountAndWithATrimmedNote() throws {
        let confirm = try OwnerAPI.decidePayment(Self.id, confirm: true, note: "  ", idempotencyKey: UUID())
        #expect(confirm.path.hasSuffix("/customer-payments/\(Self.id.uuidString.lowercased())/decision"))
        #expect(try JSONSerialization.jsonObject(with: #require(confirm.body)) as? [String: Bool] == ["verified": true])
        let reject = try OwnerAPI.decidePayment(Self.id, confirm: false, note: "  Not received ", idempotencyKey: UUID())
        let body = try JSONSerialization.jsonObject(with: #require(reject.body)) as? [String: Any]
        #expect(body?["verified"] as? Bool == false)
        #expect(body?["note"] as? String == "Not received")
    }

    @Test func recorderCannotDecideAndOnlyAWaitingPaymentIsDecidable() throws {
        let p = try Self.payment()
        #expect(T.isOwn(p, userID: Self.recorder))
        #expect(!T.isOwn(p, userID: Self.id))
        #expect(!T.isOwn(p, userID: nil))
        #expect(!T.isOwn(try Self.payment(Self.json(recordedBy: nil)), userID: Self.id))
        #expect(T.decidable(p))
        #expect(!T.decidable(try Self.payment(Self.json(status: "VERIFIED"))))
    }

    @Test func refusalsAreInPlainWordsAndAlreadyDecidedReloads() {
        let own = APIError.server(status: 422, body: ErrorBody(code: "SEGREGATION_OF_DUTIES", message: "x", correlationID: "c"))
        #expect(T.message(for: own) == "You recorded this payment, so someone else must confirm or reject it.")
        let decided = APIError.server(status: 409, body: ErrorBody(code: "PAYMENT_ALREADY_DECIDED", message: "x", correlationID: "c"))
        #expect(T.message(for: decided) == "Someone already decided this payment. Reload to see it.")
        #expect(T.needsReload(decided))
        #expect(!T.needsReload(own))
    }

    @Test func sectionNeedsReadAndVerifyAndOpensApprovals() {
        #expect(OwnerFeatures(permissions: Self.readAndVerify).confirmPayments)
        #expect(OwnerFeatures(permissions: Self.readAndVerify).approvalsScreen)
        #expect(!OwnerFeatures(permissions: ["tenant.finance.read"]).confirmPayments)
        #expect(!OwnerFeatures(permissions: ["tenant.finance.verify"]).confirmPayments)
        #expect(OwnerFeatures(permissions: Self.readAndVerify).allows(.customerPayment(Self.id)))
        #expect(!OwnerFeatures(permissions: ["tenant.finance.verify"]).allows(.customerPayment(Self.id)))
    }

    @Test func notificationOpensThePayment() {
        let text = Self.id.uuidString.lowercased()
        #expect(DeepLinkParser.route(entity: "customer_payment", id: text, path: "/tenant/customer-payments") == .customerPayment(Self.id))
        #expect(DeepLinkParser.route(entity: "customer_payment", id: nil, path: "/tenant/customer-payments") == .approvals)
        #expect(DeepLinkParser.route(path: "/tenant/customer-payments/\(text)") == .customerPayment(Self.id))
        #expect(DeepLinkParser.route(path: "/tenant/customer-payments?status=CLAIMED") == .approvals)
        let push = DeepLinkParser.parse(pushPayload: ["notification_id": text, "type": "CUSTOMER_PAYMENT_TO_VERIFY", "link": "/tenant/customer-payments",
                                                      "entity": "customer_payment", "entity_id": text])
        #expect(push?.route == .customerPayment(Self.id))
        #expect(OwnerRoute.customerPayment(Self.id).identifiesRecord)
        #expect(DeepLinkParser.parse(pushPayload: ["link": "/tenant/customer-payments", "entity": "customer_payment", "entity_id": "../x"])?.route == .approvals)
    }

    @Test func dashboardRoutesOpenThePhoneScreens() {
        let f = OwnerFeatures(permissions: Self.readAndVerify)
        let text = Self.id.uuidString.lowercased()
        #expect(ManagementRoutes.target("/tenant/customer-payments/\(text)", features: f) == .screen(.customerPayment(Self.id)))
        #expect(ManagementRoutes.target("/tenant/customer-payments?status=CLAIMED", features: f) == .screen(.approvals))
        #expect(ManagementRoutes.target("/tenant/customer-payments?method=CASH", features: f) == .web("/tenant/customer-payments?method=CASH"))
        let readOnly = OwnerFeatures(permissions: ["tenant.finance.read"])
        #expect(ManagementRoutes.target("/tenant/customer-payments?status=CLAIMED", features: readOnly) == .web("/tenant/customer-payments?status=CLAIMED"))
    }
}
