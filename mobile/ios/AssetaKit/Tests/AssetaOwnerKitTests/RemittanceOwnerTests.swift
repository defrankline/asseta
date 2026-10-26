@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// DEC-031 D2/D3 on the Owner side: method / account / reference / slip photos of a remittance, the surplus wording of
/// a cash difference and the held-too-long overdue flags. Same as Android `HandoverText`, `DecisionMapper`, `CashRecords`.
struct RemittanceOwnerTests {
    static let accountID = UUID(uuidString: "d0000000-0000-4000-8000-000000000001")!
    static let photo1 = UUID(uuidString: "e0000000-0000-4000-8000-000000000001")!
    static let photo2 = UUID(uuidString: "e0000000-0000-4000-8000-000000000002")!
    let utc = TimeZone(identifier: "UTC")!

    static func handover(method: String?, account: String?, photos: [UUID]) -> String {
        let base = RemoteBossTests.handover()
        let extra = #","method":\#(method.map { "\"\($0)\"" } ?? "null"),"deposit_account_id":"\#(accountID.uuidString.lowercased())","deposit_account_name":\#(account.map { "\"\($0)\"" } ?? "null"),"evidence_attachment_ids":[\#(photos.map { "\"\($0.uuidString.lowercased())\"" }.joined(separator: ","))]}"#
        return String(base.dropLast(base.hasSuffix("\n") ? 2 : 1)) + extra
    }

    static func decode(_ json: String) throws -> CashHandoverDTO {
        try AssetaJSON.decoder().decode(CashHandoverDTO.self, from: Data(json.utf8))
    }

    @Test func handoverDetailsBesideAmountReceived() throws {
        let json = Self.handover(method: "BANK_DEPOSIT", account: "CRDB main", photos: [Self.photo1, Self.photo2])
        #expect(try Contract.missingRequired(schema: "CashHandoverDto", json: json) == [])
        let h = try Self.decode(json)
        #expect(HandoverText.details(h).map(\.label) == ["Method", "Paid into", "Reference"])
        #expect(HandoverText.details(h).map(\.value) == ["Bank deposit", "CRDB main", "RCPT-9"])
        #expect(h.evidence == [Self.photo1, Self.photo2] && !HandoverText.missingPhoto(h))
        #expect(OwnerAccountabilityTexts.remitPhoto(1) == "deposit slip photo 1")
        let url = OwnerAPI.remittanceEvidenceURL(handoverID: h.id, attachmentID: Self.photo2)
        #expect(url.path == "/api/v1/tenant/cash/handovers/\(h.id.uuidString.lowercased())/evidence/\(Self.photo2.uuidString.lowercased())/url")

        // Mobile money without a photo: "No deposit slip photo"; no account name: the short id.
        let mobile = try Self.decode(Self.handover(method: "MOBILE_MONEY", account: nil, photos: []))
        #expect(HandoverText.missingPhoto(mobile))
        #expect(HandoverText.details(mobile).map(\.value) == ["Mobile money", "d0000000", "RCPT-9"])
        // Cash to the office never asks for a photo.
        #expect(!HandoverText.missingPhoto(try Self.decode(Self.handover(method: "CASH_TO_OFFICE", account: "Safe", photos: []))))
    }

    @Test func olderRemittancesShowOnlyTheirReference() throws {
        let h = try Self.decode(RemoteBossTests.handover())
        #expect(h.method == nil && h.evidence.isEmpty && !HandoverText.missingPhoto(h))
        #expect(HandoverText.details(h) == [DecisionField(label: "Reference", value: "RCPT-9")])
    }

    static func variance(amount: String, kind: String?) -> String {
        let kindJSON = kind.map { #""kind":"\#($0)","# } ?? ""
        return """
        {"id":"88888888-0000-4000-8000-000000000001","source_type":"HANDOVER","source_id":"88888888-0000-4000-8000-000000000002",
         "staff_member_id":null,"counterparty_staff_id":null,"currency":"TZS","declared_amount":"50000","received_amount":"55000",
         "amount":"\(amount)",\(kindJSON)"case_id":null,"opened_at":"2026-10-24T07:00:00Z","opened_by":null,"status":"WRITE_OFF_PROPOSED",
         "reason_id":null,"proposed_by":null,"proposed_at":"2026-10-24T08:00:00Z","proposal_note":"Change from yesterday",
         "outcome":null,"resolved_by":null,"resolved_at":null,"resolution_note":null}
        """
    }

    @Test func surplusIsLabelledSurplusToExplain() throws {
        let five = OwnerFormat.money(DecimalString(5000), currency: "TZS") // "TZS 5,000.00" (locale spacing)
        for kind in ["SURPLUS", nil] {
            let item = try #require(PendingDecision.from(try JSONValue.parse(Self.variance(amount: "-5000", kind: kind)),
                                                         kind: .writeOff, timeZone: utc))
            #expect(item.headline == "Surplus to explain: \(five)")
            #expect(item.fields.first { $0.label == "Surplus to explain" }?.value == five)
            #expect(!item.fields.contains { $0.label == "Difference" })
        }
        let shortfall = try #require(PendingDecision.from(try JSONValue.parse(Self.variance(amount: "5000", kind: "SHORTFALL")),
                                                          kind: .writeOff, timeZone: utc))
        #expect(shortfall.headline == "Write off \(five)")
        #expect(shortfall.fields.first { $0.label == "Difference" }?.value == five)
    }

    @Test func heldTooLongOverdueFlags() throws {
        let json = AccountabilityGapOwnerTests.overdue.replacingOccurrences(
            of: #""policy_version":"c3"}"#,
            with: #""policy_version":"c3","reason":"HELD_TOO_LONG","held_since":"2026-10-20T09:00:00Z","max_holding_days":1}"#)
        #expect(try Contract.missingRequired(schema: "RemittanceOverdueDto", json: json) == [])
        let o = try AssetaJSON.decoder().decode(RemittanceOverdueDTO.self, from: Data(json.utf8))
        #expect(CashRecordPresentation.overdueRow(o).line == "Held longer than allowed")
        let fields = CashRecordPresentation.overdue(o, timeZone: utc)
        #expect(fields.map(\.label) == ["Cash held by", "Not remitted", "Reason", "Day", "Held since", "Allowed", "Flagged"])
        #expect(fields[4].value == "20 Oct 2026" && fields[5].value == "1 day")
        #expect(CashRecordPresentation.overdueFooter(o, timeZone: utc) == "Held since 20 Oct 2026, longer than the allowed 1 day.")
        let noSince = try AssetaJSON.decoder().decode(RemittanceOverdueDTO.self, from: Data(json
            .replacingOccurrences(of: #""held_since":"2026-10-20T09:00:00Z""#, with: #""held_since":null"#).utf8))
        #expect(CashRecordPresentation.overdueFooter(noSince) == "Held longer than allowed.")
        #expect(!CashRecordPresentation.overdue(noSince).map(\.label).contains("Held since"))
    }
}
