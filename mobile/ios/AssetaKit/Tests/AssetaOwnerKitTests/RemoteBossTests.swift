@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// The boss's decisions from the field (cash handovers, exception review, cash floats), identical to Android
/// `RemoteBossTest`.
struct RemoteBossTests {
    static let handoverID = UUID(uuidString: "26262626-0000-4000-8000-000000000001")!
    static let staffID = UUID(uuidString: "dddddddd-0000-4000-8000-00000000000d")!
    static let exceptionID = UUID(uuidString: "24242424-0000-4000-8000-000000000001")!
    let utc = TimeZone(identifier: "UTC")!
    let money: (DecimalString, String) -> String = { "\($1) \($0.description)" }

    static func handover(status: String = "CLAIMED", note: String? = "Cash from site A") -> String {
        """
        {"id":"\(handoverID.uuidString.lowercased())","client_id":null,"staff_member_id":"\(staffID.uuidString.lowercased())",
         "amount":"150000.0000","currency":"TZS","handed_at":"2026-10-22T14:05:00Z","reference":"RCPT-9",
         "note":\(note.map { "\"\($0)\"" } ?? "null"),"status":"\(status)","source":"FIELD",
         "recorded_by":"eeeeeeee-0000-4000-8000-000000000001","recorded_at":"2026-10-22T14:06:00Z",
         "verified_by":null,"verified_at":null,"decision_note":null}
        """
    }

    static let custodyEntry = """
    {"id":"27272727-0000-4000-8000-000000000001","staff_member_id":"\(staffID.uuidString.lowercased())",
     "entry_type":"FLOAT_ISSUED","amount":"50000.0000","currency":"TZS","occurred_at":"2026-10-24T08:00:00Z",
     "reference":null,"note":"Fuel for Katavi"}
    """

    static func exception(type: String = "METER_DECREASE", jobID: Bool = true) -> String {
        """
        {"id":"\(exceptionID.uuidString.lowercased())","job_id":\(jobID ? "\"abababab-0000-4000-8000-000000000001\"" : "null"),
         "machine_id":"bbbbbbbb-0000-4000-8000-000000000002","meter_capture_id":null,"exception_type":"\(type)",
         "severity":"HIGH","blocking":true,"evidence":{},"policy_version":"v2","status":"OPEN","review_note":null,
         "reviewed_at":null,"created_at":"2026-10-22T08:00:00Z"}
        """
    }

    func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T {
        try AssetaJSON.decoder().decode(T.self, from: Data(json.utf8))
    }

    func body(_ data: Data?) throws -> [String: Any] {
        try #require(data.flatMap { try JSONSerialization.jsonObject(with: $0) as? [String: Any] })
    }

    func apiError(_ code: String, status: Int = 409) -> APIError {
        .server(status: status, body: ErrorBody(code: code, message: "x", correlationID: "c"))
    }

    @Test(arguments: [("CashHandoverDto", handover()), ("CashCustodyEntryDto", custodyEntry), ("ExceptionDto", exception())])
    func samplesMatchTheContract(_ sample: (String, String)) throws {
        #expect(try Contract.missingRequired(schema: sample.0, json: sample.1) == [])
    }

    // MARK: Cash handovers

    @Test func claimedHandoversSayWhoHandedOverWhatAndWhen() throws {
        let h = try decode(CashHandoverDTO.self, Self.handover())
        #expect(HandoverText.title(h, supervisor: "Neema", money: money) == "Neema handed over TZS 150000")
        #expect(HandoverText.title(h, supervisor: nil, money: money) == "A supervisor handed over TZS 150000")
        #expect(HandoverText.claimed(h, timeZone: utc) == "Claimed 22 Oct 2026, 14:05")
        #expect(HandoverText.sectionTitle == "Cash handovers" && HandoverText.empty == "No cash handovers waiting.")
        #expect(HandoverText.confirm == "Confirm received" && HandoverText.dispute == "Dispute")
        #expect(HandoverText.confirmTitle == "Confirm this handover?" && HandoverText.disputeTitle == "Dispute this handover?")
        #expect(HandoverText.note == "Note" && HandoverText.reason == "Reason")
        #expect(HandoverText.done(confirm: true) == "Handover confirmed." && HandoverText.done(confirm: false) == "Handover disputed.")
        #expect(HandoverText.screenTitle == "Cash handover" && HandoverText.card == "Handover")
        #expect(SnapshotKey.cashHandovers(claimedOnly: true).rawValue == "cash_handovers:CLAIMED")
    }

    @Test func supervisorNamesComeFromTheCashSummary() throws {
        let summary = try decode([CashSupervisorSummaryDTO].self, """
        [{"staff_member_id":"\(Self.staffID.uuidString.lowercased())","staff_name":"Neema","currency":"TZS",
          "period_from":"2026-10-01","period_to":"2026-10-24","opening":"0","floats_issued":"0","collections":"0",
          "approved_spending":"0","verified_handovers":"0","closing_outstanding":"0",
          "claimed_unverified_handovers":"150000","pending_spending":"0","unverified_collections":"0"}]
        """)
        #expect(HandoverText.names(summary) == [Self.staffID: "Neema"])
    }

    @Test func confirmTakesAnOptionalNoteAndDisputeNeedsAReason() throws {
        #expect(HandoverText.canDecide(confirm: true, text: ""))
        #expect(!HandoverText.canDecide(confirm: false, text: "   "))
        #expect(HandoverText.canDecide(confirm: false, text: "Counted 140,000 only"))
        #expect(!HandoverText.canDecide(confirm: true, text: String(repeating: "x", count: 1001)))

        let key = UUID()
        let confirm = try OwnerAPI.decideHandover(Self.handoverID, confirm: true, note: "  ", idempotencyKey: key)
        #expect(confirm.method == .post
            && confirm.path == "/api/v1/tenant/cash/handovers/\(Self.handoverID.uuidString.lowercased())/decision")
        let confirmBody = try body(confirm.body)
        #expect(confirmBody.keys.sorted() == ["verified"] && confirmBody["verified"] as? Bool == true)

        let dispute = try OwnerAPI.decideHandover(Self.handoverID, confirm: false, note: " Short by 10,000 ", idempotencyKey: key)
        let disputeBody = try body(dispute.body)
        #expect(disputeBody["verified"] as? Bool == false && disputeBody["note"] as? String == "Short by 10,000")

        let list = OwnerAPI.cashHandovers(status: "CLAIMED")
        #expect(list.path == "/api/v1/tenant/cash/handovers" && list.queryItems.contains(URLQueryItem(name: "status", value: "CLAIMED")))
    }

    @Test func staleOrOwnHandoverDecisionsAreExplained() {
        let decided = apiError("HANDOVER_ALREADY_DECIDED")
        #expect(HandoverText.message(for: decided) == "Someone already decided this handover. Reload to see it.")
        #expect(HandoverText.needsReload(decided) && !HandoverText.needsReload(apiError("SEGREGATION_OF_DUTIES", status: 422)))
        #expect(HandoverText.message(for: apiError("SEGREGATION_OF_DUTIES", status: 422)).hasPrefix("Segregation of duties"))
    }

    // MARK: Cash floats

    @Test func issuingAFloatSendsAFloatIssuedEntry() throws {
        #expect(FloatText.action == "Issue float" && FloatText.title == "Issue a cash float")
        #expect(FloatText.amountLabel(currency: "TZS") == "Amount (TZS)" && FloatText.note == "Note (optional)")
        #expect(FloatText.submit == "Issue" && FloatText.issued == "Float issued.")
        #expect(!FloatText.canIssue(amount: "", note: "") && !FloatText.canIssue(amount: "0", note: ""))
        #expect(FloatText.canIssue(amount: "50,000", note: ""))

        let key = UUID()
        let request = try OwnerAPI.issueFloat(staffMemberID: Self.staffID, amount: Decimal(50000), currency: "TZS",
                                              note: " Fuel for Katavi ", idempotencyKey: key)
        #expect(request.method == .post && request.path == "/api/v1/tenant/cash/floats" && request.idempotencyKey == key)
        let sent = try body(request.body)
        #expect(sent["staff_member_id"] as? String == Self.staffID.uuidString.lowercased())
        #expect(sent["entry_type"] as? String == "FLOAT_ISSUED" && sent["amount"] as? String == "50000")
        #expect(sent["currency"] as? String == "TZS" && sent["note"] as? String == "Fuel for Katavi")
        let plain = try OwnerAPI.issueFloat(staffMemberID: Self.staffID, amount: Decimal(1), currency: nil, note: "",
                                            idempotencyKey: key)
        #expect(try body(plain.body).keys.sorted() == ["amount", "entry_type", "staff_member_id"])
        _ = try decode(CashCustodyEntryDTO.self, Self.custodyEntry)
    }

    @Test func floatErrorsUseTheFinanceHints() {
        #expect(FloatText.message(for: apiError("NOT_CUSTODIAN", status: 403))
            == "Only office cash staff may record custody for someone else.")
        #expect(FloatText.message(for: apiError("STAFF_INACTIVE", status: 422)) == "The staff member is inactive.")
        #expect(FloatText.message(for: apiError("CURRENCY_NOT_CONFIGURED", status: 422)) == "Choose a configured currency.")
    }

    // MARK: Exceptions

    @Test func exceptionsAreNamedByTypeAndJob() throws {
        let x = try decode(MeterExceptionDTO.self, Self.exception())
        #expect(ExceptionReviewText.title(x, jobNumber: "J-2026-105") == "Meter decrease on J-2026-105")
        #expect(ExceptionReviewText.title(x, jobNumber: nil) == "Meter decrease")
        #expect(ExceptionReviewText.reviewTitle(x) == "Review · Meter decrease")
        #expect(x.evidence == .object([:]) && ExceptionReviewText.maxJobLookups == 25)
        #expect(ExceptionReviewText.sectionTitle == "Exceptions" && ExceptionReviewText.empty == "No open exceptions.")
        #expect(ExceptionReviewText.reviewed == "Exception reviewed.")
        #expect(ExceptionReviewText.screenTitle == "Meter exception" && ExceptionReviewText.openJob == "Open job")
        #expect(ExceptionReviewText.blocksBilling == "Blocks billing until reviewed")
    }

    @Test func reviewMirrorsTheWebDialog() throws {
        #expect(ExceptionReviewOutcome.allCases.map(\.label) == [
            "Explained — a legitimate reason was found", "Discrepancy confirmed — evidence stands as recorded",
        ])
        #expect(ExceptionReviewText.outcomeLabel == "Outcome" && ExceptionReviewText.noteLabel == "Review note")
        #expect(ExceptionReviewText.submit == "Record review")
        #expect(ExceptionReviewText.noteError("  ") == "A review note is required")
        #expect(ExceptionReviewText.noteError("ok") == "At least 5 characters")
        #expect(ExceptionReviewText.noteError(String(repeating: "x", count: 2001)) == "At most 2000 characters")
        #expect(!ExceptionReviewText.canReview(outcome: nil, note: "Tracker was off"))
        #expect(ExceptionReviewText.canReview(outcome: .explained, note: "Tracker was off"))

        let key = UUID()
        let request = try OwnerAPI.reviewException(Self.exceptionID, outcome: .confirmed, note: "  Photo reused from Monday ",
                                                   idempotencyKey: key)
        #expect(request.method == .post
            && request.path == "/api/v1/tenant/exceptions/\(Self.exceptionID.uuidString.lowercased())/review")
        let sent = try body(request.body)
        #expect(sent["outcome"] as? String == "CONFIRMED" && sent["note"] as? String == "Photo reused from Monday")

        let already = apiError("ALREADY_REVIEWED")
        #expect(ExceptionReviewText.message(for: already) == "Someone else has already reviewed this exception; reload the list.")
        #expect(ExceptionReviewText.needsReload(already))
    }

    // MARK: Gating

    @Test func actionsAreGatedOnTheWebPermissions() {
        let all = OwnerFeatures(permissions: ["tenant.finance.read", "tenant.finance.verify", "tenant.finance.cash",
                                              "tenant.meter.read", "tenant.meter.review"])
        #expect(all.verifyHandovers && all.issueFloats && all.reviewExceptions)
        let readOnly = OwnerFeatures(permissions: ["tenant.finance.read", "tenant.meter.read"])
        #expect(!readOnly.verifyHandovers && !readOnly.issueFloats && !readOnly.reviewExceptions)
        #expect(all.allows(.handover(Self.handoverID)) && all.allows(.exception(Self.exceptionID)))
        #expect(OwnerRoute.handover(Self.handoverID).identifiesRecord)
    }
}
