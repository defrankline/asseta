@testable import AssetaSync
import AssetaModel
import AssetaNetwork
import AssetaSecurity
import AssetaStore
import AssetaTestSupport
import Foundation
import Testing

/// Supervisor customers: rules, wording, online only, the server's refusals and saved customers reaching the pickers.
/// Same as Android `CustomerRulesTest`, `CustomerTextsTest` and `FieldCustomersTest`.
struct FieldCustomersTests {
    static let id = UUID(uuidString: "c1000000-0000-4000-8000-000000000001")!

    static func customer(name: String = "Kilimo Ltd", version: Int = 1, active: Bool = true, id: UUID = id) -> String {
        #"{"id":"\#(id.uuidString.lowercased())","code":"KIL","name":"\#(name)","kind":"REGISTERED","tax_id":null,"contact_name":"Asha","contact_phone":"0700","contact_email":null,"payment_terms_days":30,"is_active":\#(active),"deactivated_at":null,"deactivation_reason":null,"version":\#(version)}"#
    }

    static let values = CustomerValues(code: "KIL", name: "Kilimo Ltd", taxID: nil, contactName: "Asha", phone: "0700", email: nil, paymentTermsDays: 30)

    func online(_ handler: @escaping MockTransport.Handler) throws -> (SupervisorOnline, MockTransport, LocalStore) {
        let store = try LocalStore.open(at: try temporaryDirectory().appendingPathComponent("c.sqlite"),
                                        keyProvider: DatabaseKeyProvider(store: InMemorySecretStore()))
        let transport = MockTransport(handler: handler)
        let client = APIClient(baseURL: URL(string: "https://api.test")!, transport: transport,
                               tokens: StaticTokenProvider(token: "t"), tenantID: SyncFixtures.tenant)
        return (SupervisorOnline(client: client, store: store, tenantID: SyncFixtures.tenant), transport, store)
    }

    @Test func detailsOrWriteMayEditAndOnlyWriteChangesTerms() {
        #expect(CustomerRules.canEdit(["tenant.customer.details"]) && CustomerRules.canEdit(["tenant.customer.write"]))
        #expect(!CustomerRules.canEdit(["tenant.customer.read"]))
        #expect(CustomerRules.termsEditable(["tenant.customer.write"]) && !CustomerRules.termsEditable(["tenant.customer.details"]))
    }

    @Test func formChecks() {
        let kept = CustomerRules.check(CustomerDraft(code: " KIL ", name: " Kilimo ", contactName: " Asha ", termsText: "90"),
                                       termsEditable: false, currentTerms: 45)
        #expect((try? kept.get()) == CustomerValues(code: "KIL", name: "Kilimo", taxID: nil, contactName: "Asha", phone: nil, email: nil,
                                                    paymentTermsDays: 45))
        #expect((try? CustomerRules.check(CustomerDraft(code: "K", name: "N", termsText: "60"), termsEditable: true).get())?.paymentTermsDays == 60)
        func problems(_ d: CustomerDraft, _ editable: Bool = false) -> [String] {
            if case let .failure(p) = CustomerRules.check(d, termsEditable: editable) { return p.messages }
            return []
        }
        #expect(problems(CustomerDraft()) == [C.errCode, C.errName])
        #expect(problems(CustomerDraft(code: String(repeating: "x", count: 33), name: "N")) == [C.errCode])
        #expect(problems(CustomerDraft(code: "K", name: "N", email: "asha.example")) == [C.errEmail])
        #expect(problems(CustomerDraft(code: "K", name: "N", phone: String(repeating: "1", count: 41))) == [C.errLong])
        #expect(problems(CustomerDraft(code: "K", name: "N", termsText: "400"), true) == [C.errTerms])
        #expect(CustomerRules.validEmail("asha@kilimo.co.tz") && !CustomerRules.validEmail("a@b@c"))
    }

    typealias C = CustomerTexts

    @Test func wording() throws {
        let c = FieldCustomerDTO(id: Self.id, code: "KIL", name: "Kilimo Ltd", taxID: "TIN-1", contactName: "Asha", contactPhone: "0700",
                                 paymentTermsDays: 45, version: 3)
        #expect(C.rowDetail(c) == "KIL · Asha")
        #expect(C.fields(c, termsEditable: false).map { "\($0.label)=\($0.value)" }
            == ["Code=KIL", "Tax ID=TIN-1", "Contact=Asha", "Phone=0700", "Payment terms=45 days · Set by the office"])
        #expect(C.fields(c, termsEditable: true).last?.value == "45 days")
        #expect(C.draft(c) == CustomerDraft(code: "KIL", name: "Kilimo Ltd", taxID: "TIN-1", contactName: "Asha", phone: "0700", email: "",
                                            termsText: "45"))
        #expect(C.offline == "Customers need a connection. Connect to see, add or edit them.")
    }

    @Test func aSavedCustomerReachesThePickersAndTheListRefreshesThem() async throws {
        let (online, transport, store) = try online { request in
            switch (request.httpMethod, request.url?.path) {
            case ("POST", _): return (201, Data(Self.customer().utf8))
            case ("PUT", _): return (200, Data(Self.customer(name: "Kilimo Group", version: 2).utf8))
            default:
                let other = Self.customer(name: "Old", active: false, id: UUID())
                return (200, Data(#"{"items":[\#(Self.customer(name: "Kilimo Group", version: 2)),\#(other)],"total":2,"page":1,"page_size":50}"#.utf8))
            }
        }
        let directory = FieldDirectory(store: store, tenantID: SyncFixtures.tenant)
        guard case let .done(saved) = await online.saveCustomer(id: nil, values: Self.values, version: 7) else { Issue.record("not saved"); return }
        #expect(saved.id == Self.id)
        let create = try JSONValue.parse(String(decoding: try #require(transport.requests.last?.httpBody), as: UTF8.self))
        #expect(create["version"] == nil && create["payment_terms_days"] == .number(30))
        #expect(try directory.customers().map(\.name) == ["Kilimo Ltd"])

        _ = await online.saveCustomer(id: Self.id, values: Self.values, version: 1)
        let put = try #require(transport.requests.last)
        #expect(put.httpMethod == "PUT" && put.url?.path == "/api/v1/tenant/customers/\(Self.id.uuidString.lowercased())")
        #expect(try JSONValue.parse(String(decoding: try #require(put.httpBody), as: UTF8.self))["version"] == .number(1))

        guard case let .done(list) = await online.customers(query: " kil ") else { Issue.record("not listed"); return }
        #expect(list.map(\.name) == ["Kilimo Group"])
        #expect(transport.requests.last?.url?.query?.contains("q=kil") == true)
        #expect(try directory.customers().map(\.name) == ["Kilimo Group"])
    }

    @Test func refusalsKeepTheServersWordsAndAStaleVersionIsMarked() async throws {
        let (online, _, _) = try online { request in
            if request.httpMethod == "POST" {
                return (403, Data(#"{"error":{"code":"CUSTOMER_TERMS_NOT_PERMITTED","message":"Payment terms are set by the office; you can add customers and edit their details","correlation_id":"c","details":[]}}"#.utf8))
            }
            return (409, Data(#"{"error":{"code":"STALE_VERSION","message":"Customer was modified by someone else; reload and retry","correlation_id":"c","details":[]}}"#.utf8))
        }
        guard case let .refused(message, code, stale) = await online.saveCustomer(id: nil, values: Self.values, version: nil) else {
            Issue.record("expected a refusal"); return
        }
        #expect(message == "Payment terms are set by the office; you can add customers and edit their details")
        #expect(code == "CUSTOMER_TERMS_NOT_PERMITTED" && !stale)
        guard case let .refused(_, _, isStale) = await online.saveCustomer(id: Self.id, values: Self.values, version: 1) else {
            Issue.record("expected a refusal"); return
        }
        #expect(isStale)
    }

    @Test func offlineNothingIsSentOrQueued() async throws {
        let (online, _, store) = try online { _ in throw URLError(.notConnectedToInternet) }
        guard case .offline = await online.saveCustomer(id: nil, values: Self.values, version: nil) else { Issue.record("expected offline"); return }
        guard case .offline = await online.customers(query: "") else { Issue.record("expected offline"); return }
        #expect(try store.outbox.operations(tenantID: SyncFixtures.tenant, owner: nil, statuses: Set(ClientOperationStatus.allCases)).isEmpty)
    }
}
