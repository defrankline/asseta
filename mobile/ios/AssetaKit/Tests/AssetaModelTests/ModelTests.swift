import AssetaModel
import Foundation
import Testing

struct DecimalStringTests {
    struct Wrapper: Codable { let amount: DecimalString }

    @Test func decodesExactDecimalFromString() throws {
        let value = try JSONDecoder().decode(Wrapper.self, from: Data(#"{"amount":"0.10"}"#.utf8))
        #expect(value.amount.value == Decimal(string: "0.1", locale: Locale(identifier: "en_US_POSIX")))
        // 0.1 + 0.2 must be exactly 0.3 (it is not with Double).
        let sum = value.amount.value + DecimalString(string: "0.2")!.value
        #expect(sum == DecimalString(string: "0.3")!.value)
    }

    @Test func largeValuesKeepPrecision() throws {
        let text = "123456789012345678.99"
        let value = try #require(DecimalString(string: text))
        #expect(value.description == text)
    }

    @Test func rejectsJSONNumbers() {
        #expect(throws: DecodingError.self) {
            try JSONDecoder().decode(Wrapper.self, from: Data(#"{"amount":12.5}"#.utf8))
        }
    }

    @Test(arguments: ["", "1e5", "1,5", " 1", "1.", ".5", "--1", "NaN", "١٢"])
    func rejectsNonCanonicalText(_ text: String) {
        #expect(DecimalString(string: text) == nil)
    }

    @Test func encodesAsString() throws {
        let data = try JSONEncoder().encode(Wrapper(amount: DecimalString(string: "-42.50")!))
        #expect(String(decoding: data, as: UTF8.self) == #"{"amount":"-42.5"}"#)
    }
}

struct IdentityDTOTests {
    static let me = """
    {"user_id":"6f1c2a1e-0b7a-4c55-9d8e-1f2a3b4c5d6e","email":"a@b.c","display_name":"A",
     "platform_permissions":["platform.tenants.read"],
     "platform_menus":[{"key":"tenants","label":"Tenants","path":"/platform/tenants","order":1}],
     "tenants":[{"tenant_id":"11111111-1111-4111-8111-111111111111","name":"Acme","status":"ACTIVE",
       "access_state":"READ_ONLY","permissions":["jobs.read"],
       "menus":[{"key":"b","label":"B","path":"/b","order":2},{"key":"a","label":"A","path":"/a","order":2},
                {"key":"z","label":"Z","path":"/z","order":1}]}]}
    """

    @Test func decodesMeContract() throws {
        let me = try AssetaJSON.decoder().decode(MeResponse.self, from: Data(Self.me.utf8))
        #expect(me.displayName == "A")
        #expect(me.platformMenus.first?.path == "/platform/tenants")
        let tenant = try #require(me.tenants.first)
        #expect(tenant.status == .active)
        #expect(tenant.accessState == .readOnly)
        #expect(tenant.accessState.allowsEntry)
        #expect(tenant.orderedMenus.map(\.key) == ["z", "a", "b"])
    }

    @Test func unknownAccessStateFailsClosed() {
        #expect(!TenantAccessState(rawValue: "SOMETHING_NEW").allowsEntry)
        #expect(!TenantAccessState.blocked.allowsEntry)
        #expect(TenantAccessState.full.allowsEntry)
    }

    @Test func roundTrips() throws {
        let me = try AssetaJSON.decoder().decode(MeResponse.self, from: Data(Self.me.utf8))
        let again = try AssetaJSON.decoder().decode(MeResponse.self, from: AssetaJSON.encoder().encode(me))
        #expect(again == me)
    }
}

struct ErrorEnvelopeTests {
    @Test func decodesEnvelopeWithNullField() throws {
        let json = #"{"error":{"code":"VALIDATION_FAILED","message":"Bad","correlation_id":"c-1","details":[{"field":null,"issue":"x"},{"field":"a.b","issue":"y"}]}}"#
        let envelope = try JSONDecoder().decode(ErrorEnvelope.self, from: Data(json.utf8))
        #expect(envelope.error.details == [ErrorDetail(field: nil, issue: "x"), ErrorDetail(field: "a.b", issue: "y")])
    }

    @Test func detailsDefaultToEmpty() throws {
        let json = #"{"error":{"code":"NOT_FOUND","message":"m","correlation_id":"c"}}"#
        #expect(try JSONDecoder().decode(ErrorEnvelope.self, from: Data(json.utf8)).error.details.isEmpty)
    }

    @Test func instantsAreUTCMillis() throws {
        let date = Date(timeIntervalSince1970: 1_700_000_000.5)
        #expect(AssetaJSON.formatInstant(date) == "2023-11-14T22:13:20.500Z")
        #expect(AssetaJSON.parseInstant("2023-11-14T22:13:20Z") == Date(timeIntervalSince1970: 1_700_000_000))
    }
}
