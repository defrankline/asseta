import AssetaModel
@testable import AssetaSync
import Foundation
import Testing

/// DEC-031 Phase 4 in the Supervisor app: the hours-transfer purchase picker and the From machine caption show hours in
/// use by running jobs beside the hours left (as Android `purchaseOptions` / `inUseOn`). Strings doc "DEC-031 Phases 2
/// and 4" (field.hours.*).
struct HoursInUseTests {
    static func purchase(provisional: String, m1: String, m2: String = "0") -> String {
        """
        {"id":"a7000000-0000-4000-8000-000000000001","purchase_number":"HP-2026-00001","client_id":null,
         "customer_id":"c7000000-0000-4000-8000-000000000001","customer_name":"Joe",
         "machine_id":"aaaaaaaa-0000-4000-8000-000000000001","machine_code":"EX-01","machine_name":null,"job_site_name":null,
         "created_by_name":null,"hours":"20","currency":"TZS","amount":"1","status":"ACTIVE","created_at":"2026-10-01T07:00:00Z",
         "totals":{"purchased":"20","activated":"20","consumed":"4","remaining":"12.00","awaiting_activation":"0","provisional":"\(provisional)"},
         "machines":[{"machine_id":"aaaaaaaa-0000-4000-8000-000000000001","remaining":"8","provisional":"\(m1)"},
                     {"machine_id":"aaaaaaaa-0000-4000-8000-000000000002","remaining":"4","provisional":"\(m2)"}]}
        """
    }

    static let m1 = UUID(uuidString: "aaaaaaaa-0000-4000-8000-000000000001")!
    static let m2 = UUID(uuidString: "aaaaaaaa-0000-4000-8000-000000000002")!

    @Test func purchasesShowHoursInUseBesideHoursLeft() throws {
        let p = try AssetaJSON.decoder().decode(HoursPurchaseDTO.self, from: Data(Self.purchase(provisional: "4.00", m1: "4.00").utf8))
        let title = FieldAccountabilityTexts.transferPurchaseOption(number: p.purchaseNumber, hours: AccountabilityRules.plain(p.totals.remaining.value),
                                                                    provisional: AccountabilityRules.inUse(p.totals.provisional.value))
        #expect(title == "HP-2026-00001 · 12 h left · 4 h in use by running jobs")
        #expect(AccountabilityRules.inUse(p.provisional(on: Self.m1)) == "4")
        #expect(AccountabilityRules.inUse(p.provisional(on: Self.m2)) == nil)
        #expect(AccountabilityRules.inUse(p.provisional(on: nil)) == "4")
        #expect(FieldAccountabilityTexts.hoursInUse("4") == "4 h in use by running jobs")

        let none = try AssetaJSON.decoder().decode(HoursPurchaseDTO.self, from: Data(Self.purchase(provisional: "0", m1: "0").utf8))
        #expect(FieldAccountabilityTexts.transferPurchaseOption(number: none.purchaseNumber, hours: "12",
                                                                provisional: AccountabilityRules.inUse(none.totals.provisional.value))
            == "HP-2026-00001 · 12 h left")
        #expect(AccountabilityRules.inUse(none.provisional(on: Self.m1)) == nil)
    }
}
