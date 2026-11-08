@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// DEC-032 Phase 2 on the Owner side: adjustment requests under Approvals, effects, withdraw, deep links, purchase and
/// statement additions, reversed payments. Strings doc "DEC-032 Phase 2 — adjustments".
struct AdjustmentOwnerTests {
    typealias T = AdjustmentTexts
    static let id = UUID(uuidString: "b1000000-0000-4000-8000-000000000001")!
    static let proposer = UUID(uuidString: "b2000000-0000-4000-8000-000000000001")!
    static let machine = UUID(uuidString: "b3000000-0000-4000-8000-000000000001")!
    static let paymentA = UUID(uuidString: "b4000000-0000-4000-8000-000000000001")!
    static let paymentB = UUID(uuidString: "b4000000-0000-4000-8000-000000000002")!
    let usd = "USD"

    static func json(type: String = "HOURS_CORRECTION", status: String = "PROPOSED", hours: String = #""2.00""#, amount: String = "null",
                     effects: String = "{}", settlement: String = "null", note: String = "null", decidedBy: String = "null") -> String {
        """
        {"id":"\(id.uuidString.lowercased())","client_id":null,"request_type":"\(type)","status":"\(status)","original_type":"hours_purchase",
         "original_id":"b5000000-0000-4000-8000-000000000001","original_reference":"P-12","customer_id":"b6000000-0000-4000-8000-000000000001",
         "customer_name":"Acme","machine_id":"\(machine.uuidString.lowercased())","machine_code":"EX-01","machine_name":"Excavator",
         "purchase_id":"b5000000-0000-4000-8000-000000000001","purchase_number":"P-12","hours":\(hours),"amount":\(amount),"currency":"USD",
         "settlement":\(settlement),"params":{},"reason":"Wrong entry","reason_code_id":null,"reason_label":"Data error",
         "evidence_attachment_ids":["b7000000-0000-4000-8000-000000000001"],"proposed_by":"\(proposer.uuidString.lowercased())","proposed_by_name":"Asha",
         "proposed_at":"2026-11-07T10:00:00Z","decided_by":\(decidedBy),"decided_by_name":null,"decided_at":null,"decision_note":\(note),"effects":\(effects)}
        """
    }

    static func decoded(_ json: String) throws -> AdjustmentRequestDTO {
        try AssetaJSON.decoder().decode(AdjustmentRequestDTO.self, from: Data(json.utf8))
    }

    static func value(_ json: String) throws -> JSONValue { try JSONValue.parse(json) }

    @Test func toleratesMissingAdditiveFieldsAndUnknownValues() throws {
        let r = try Self.decoded("""
        {"id":"\(Self.id.uuidString.lowercased())","request_type":"NEW_THING","status":"FUTURE","proposed_at":"2026-11-07T10:00:00Z"}
        """)
        #expect(r.effects == .object([:]) && r.evidenceAttachmentIDs.isEmpty && r.reason.isEmpty)
        #expect(T.type(r.requestType) == "New thing")
        #expect(AdjustmentPresentation.effects(r).isEmpty)
        #expect(!(AdjustmentPresentation.decision(r).isPending))
    }

    @Test func rowHeadlineAndSubtitle() throws {
        #expect(AdjustmentPresentation.headline(try Self.decoded(Self.json())).hasPrefix("Hours correction · +2"))
        #expect(AdjustmentPresentation.headline(try Self.decoded(Self.json(hours: #""-2.00""#))).contains("-2"))
        #expect(AdjustmentPresentation.headline(try Self.decoded(Self.json(type: "HOURS_REFUND", hours: #""3.00""#))) == "Hours refund · 3 h")
        #expect(AdjustmentPresentation.headline(try Self.decoded(Self.json(type: "INVOICE_VOID", hours: "null"))) == "Invoice void")
        let reversal = try Self.decoded(Self.json(type: "PAYMENT_REVERSAL", hours: "null", amount: #""150.00""#))
        #expect(AdjustmentPresentation.headline(reversal) == "Payment reversal · \(OwnerFormat.money(DecimalString(150), currency: usd))")
        #expect(AdjustmentPresentation.subtitle(try Self.decoded(Self.json())) == "Acme · EX-01")
    }

    @Test func requestCardRowsInOrder() throws {
        let item = try #require(PendingDecision.from(try Self.value(Self.json(status: "APPROVED", note: #""Fine""#, decidedBy: #""b2000000-0000-4000-8000-000000000002""#)),
                                                     kind: .adjustmentRequest))
        #expect(item.fields.map(\.label) == ["Type", "Reference", "Customer", "Machine", "Purchase", "Hours", "Reason category", "Proposed by", "Decided by", "Decision note"])
        #expect(item.reasonLine == "Wrong entry")
        #expect(!item.isPending)
    }

    @Test func withdrawnShowsWhyInsteadOfDecisionNote() throws {
        let item = try #require(PendingDecision.from(try Self.value(Self.json(status: "WITHDRAWN", note: #""Wrong purchase""#)), kind: .adjustmentRequest))
        #expect(item.fields.last == DecisionField(label: "Why it was withdrawn", value: "Wrong purchase"))
        #expect(!item.fields.contains { $0.label == "Decision note" })
    }

    @Test func forecastThenActualEffects() throws {
        let forecast = AdjustmentPresentation.effects(try Self.decoded(Self.json(effects: #"{"lot_hours_before":"0","lot_hours_after":"2.5"}"#)))
        #expect(forecast.title == "If approved")
        #expect(forecast.rows.map(\.label) == ["Hours on the lot now", "Hours on the lot after"])
        #expect(forecast.rows.first?.value.hasPrefix("0") == true)
        let actual = AdjustmentPresentation.effects(try Self.decoded(Self.json(status: "APPROVED",
            effects: #"{"future_key":"9","purchase_remaining":"4","lot_hours_after":"4","lot_hours_before":"2"}"#)))
        #expect(actual.title == "What it did")
        #expect(actual.rows.map(\.label) == ["Hours on the lot before", "Hours on the lot after", "Left on the purchase"])
    }

    @Test func reversalEffectsOrderMoneyAndZeroHidden() throws {
        let r = try Self.decoded(Self.json(type: "PAYMENT_REVERSAL", hours: "null", amount: #""150.00""#, effects: """
        {"unused_hours_removed":"5","used_hours":"0","money_owed":"20.00","hire_allocations_released":"0","treatment":"RECEIVABLE",
         "custody_balance_after":"-10.00","purchases":[{"purchase_id":"b5000000-0000-4000-8000-000000000001","purchase_number":"P-12","unused_hours":"5","used_hours":"1","money_owed":"20.00"}]}
        """))
        let rows = AdjustmentPresentation.effects(r).rows
        #expect(rows.map(\.label) == ["Unused hours removed", "Money owed for hours already used", "For hours already used", "Custodian's cash after", "P-12"])
        // Treatment only matters when used hours are touched.
        let untouched = try Self.decoded(Self.json(type: "PAYMENT_REVERSAL", hours: "null", amount: #""1.00""#,
                                                   effects: #"{"unused_hours_removed":"5","used_hours":"0","money_owed":"0","treatment":"CASE"}"#))
        #expect(AdjustmentPresentation.effects(untouched).rows.map(\.label) == ["Unused hours removed"])
        #expect(rows[1].value == OwnerFormat.money(DecimalString(20), currency: usd))
        #expect(rows[2] == DecisionField(label: "For hours already used", value: "Bill the customer"))
        #expect(rows[4].value == "5 h removed · 1 h used · \(OwnerFormat.money(DecimalString(20), currency: usd)) owed")
    }

    @Test func refusalWhileProposedOnly() throws {
        let known = AdjustmentPresentation.effects(try Self.decoded(Self.json(effects: #"{"refused":"PAYMENT_ALREADY_REVERSED"}"#)))
        #expect(known.refused == "This request can't be approved as it stands: This payment is already reversed.")
        #expect(known.rows.isEmpty)
        let unknown = AdjustmentPresentation.effects(try Self.decoded(Self.json(effects: #"{"refused":"SOMETHING_NEW"}"#)))
        #expect(unknown.refused == "This request can't be approved as it stands: the record has changed. Reload to see it.")
        #expect(AdjustmentPresentation.effects(try Self.decoded(Self.json(status: "REJECTED", effects: #"{"refused":"X"}"#))).isEmpty)
    }

    @Test func decideAndWithdrawRules() throws {
        #expect(DecisionRules.canDecide(.adjustmentRequest, approve: true, note: ""))
        #expect(!DecisionRules.canDecide(.adjustmentRequest, approve: false, note: " "))
        #expect(!DecisionRules.canDecide(.adjustmentRequest, approve: true, note: String(repeating: "x", count: 1001)))
        #expect(AdjustmentRules.canWithdraw(reason: "abc") && !AdjustmentRules.canWithdraw(reason: " ab "))
        let r = try Self.decoded(Self.json())
        let propose = [AdjustmentPermission.propose]
        #expect(AdjustmentRules.offersWithdraw(r, userID: Self.proposer, permissions: propose))
        #expect(!AdjustmentRules.offersWithdraw(r, userID: UUID(), permissions: propose))
        #expect(!AdjustmentRules.offersWithdraw(r, userID: Self.proposer, permissions: []))
        #expect(!AdjustmentRules.offersWithdraw(try Self.decoded(Self.json(status: "APPROVED")), userID: Self.proposer, permissions: propose))
    }

    @Test func requests() throws {
        let list = OwnerAPI.decisions(.adjustmentRequest, pendingOnly: true)
        #expect(list.path.hasSuffix("/tenant/adjustment-requests"))
        #expect(list.queryItems.contains(URLQueryItem(name: "status", value: "PROPOSED")))
        let decide = try OwnerAPI.decide(.adjustmentRequest, id: Self.id, approve: false, note: " No ", idempotencyKey: UUID())
        #expect(decide.path.hasSuffix("/adjustment-requests/\(Self.id.uuidString.lowercased())/decision"))
        let body = try #require(decide.body)
        let sent = try JSONValue.parse(String(decoding: body, as: UTF8.self))
        #expect(sent["decision"]?.stringValue == "REJECT" && sent["note"]?.stringValue == "No")
        let approve = try OwnerAPI.decide(.adjustmentRequest, id: Self.id, approve: true, note: "", idempotencyKey: UUID())
        let approveBody = try JSONValue.parse(String(decoding: try #require(approve.body), as: UTF8.self))
        #expect(approveBody["decision"]?.stringValue == "APPROVE" && approveBody["approve"] == nil)
        let withdraw = try OwnerAPI.withdrawAdjustment(Self.id, reason: " Oops ", idempotencyKey: UUID())
        #expect(withdraw.path.hasSuffix("/withdraw"))
        #expect(try JSONValue.parse(String(decoding: try #require(withdraw.body), as: UTF8.self))["reason"]?.stringValue == "Oops")
    }

    @Test func refusalWordingUsesAdjustmentTexts() {
        let error = APIError.server(status: 409, body: ErrorBody(code: "SEGREGATION_OF_DUTIES", message: "No", correlationID: "c"))
        #expect(DecisionRules.message(for: error, kind: .adjustmentRequest) == "You proposed this request, so someone else must decide it.")
        #expect(DecisionRules.message(for: error, kind: .discount) == OwnerAccountabilityTexts.decisionOwnRequest)
    }

    @Test func gatedByPermissionOnly() {
        let read = OwnerFeatures(permissions: [AdjustmentPermission.read], disabledCapabilities: [TenantCapability.customerHours, TenantCapability.cashCustody])
        #expect(read.decisionKinds == [.adjustmentRequest] && read.approvalsScreen && !read.canDecide(.adjustmentRequest))
        #expect(read.allows(.decision(.adjustmentRequest, Self.id)))
        #expect(OwnerFeatures(permissions: [AdjustmentPermission.read, AdjustmentPermission.decide]).canDecide(.adjustmentRequest))
        #expect(!OwnerFeatures(permissions: ["tenant.finance.read"]).decisionKinds.contains(.adjustmentRequest))
    }

    @Test func emptyStateOnlyForARoleWithNothingElseToShow() {
        let accountant = OwnerFeatures(permissions: [AdjustmentPermission.read, AdjustmentPermission.decide])
        #expect(accountant.approvalsScreen && !accountant.approvals)
        #expect(!accountant.nothingWaiting(waiting: [:]))
        #expect(accountant.nothingWaiting(waiting: [.adjustmentRequest: 0]))
        #expect(!accountant.nothingWaiting(waiting: [.adjustmentRequest: 1]))
        #expect(!OwnerFeatures(permissions: [AdjustmentPermission.read, "tenant.approval.read"]).nothingWaiting(waiting: [.adjustmentRequest: 0]))
        #expect(!OwnerFeatures(permissions: [AdjustmentPermission.read, "tenant.job.read"]).nothingWaiting(waiting: [.adjustmentRequest: 0]))
    }

    @Test func deepLinks() {
        let id = Self.id, text = id.uuidString.lowercased()
        #expect(DeepLinkParser.route(path: "/tenant/finance/adjustments/requests/\(text)") == .decision(.adjustmentRequest, id))
        #expect(DeepLinkParser.route(path: "/tenant/finance/adjustments") == .approvals)
        #expect(DeepLinkParser.route(path: "/tenant/finance/adjustments/\(text)") == .approvals)
        #expect(DeepLinkParser.route(entity: "adjustment_request", id: text, path: nil) == .decision(.adjustmentRequest, id))
        #expect(DeepLinkParser.parse(pushPayload: ["kind": "ADJUSTMENT_REQUEST", "record_id": text])?.route == .decision(.adjustmentRequest, id))
        // Cash custody paths are untouched by the new branch.
        #expect(DeepLinkParser.route(path: "/tenant/finance/cash/adjustments/\(text)") == .decision(.adjustment, id))
    }

    static func purchase(totals: String = "", allocations: String = "") -> String {
        """
        {"id":"b5000000-0000-4000-8000-000000000001","purchase_number":"P-12","customer_id":"b6000000-0000-4000-8000-000000000001","customer_name":"Acme",
         "machine_id":"\(machine.uuidString.lowercased())","machine_code":"EX-01","hours":"10","currency":"USD","amount":"100","status":"ACTIVE",
         "created_at":"2026-11-01T10:00:00Z","cancelled_at":null,
         "totals":{"purchased":"10","activated":"10","consumed":"2","remaining":"8","awaiting_activation":"0"\(totals)}\(allocations)}
        """
    }

    static func purchaseDTO(_ json: String) throws -> HoursPurchaseDTO {
        try AssetaJSON.decoder().decode(HoursPurchaseDTO.self, from: Data(json.utf8))
    }

    @Test func purchaseRowsGainRefundedCorrectedReversedOnlyWhenNotZero() throws {
        let plain = CustomerHoursPresentation.purchaseRows(try Self.purchaseDTO(Self.purchase()))
        #expect(!plain.contains { ["Refunded", "Corrected", "Reversed"].contains($0.label) })
        let rows = CustomerHoursPresentation.purchaseRows(try Self.purchaseDTO(Self.purchase(totals: #","refunded":"1.5","corrected":"-2","reversed":"3""#)))
        #expect(rows.first { $0.label == "Refunded" }?.value == "1.5 h")
        #expect(rows.first { $0.label == "Corrected" }?.value.contains("-2") == true)
        #expect(rows.first { $0.label == "Reversed" }?.value == "3 h")
        #expect(CustomerHoursPresentation.purchaseRows(try Self.purchaseDTO(Self.purchase(totals: #","corrected":"2""#))).first { $0.label == "Corrected" }?.value == "+2 h")
    }

    @Test func paymentRowsAndWhichPaymentsToRead() throws {
        let allocations = """
        ,"allocations":[{"id":"b8000000-0000-4000-8000-000000000001","payment_id":"\(Self.paymentA.uuidString.lowercased())","purchase_id":"b5000000-0000-4000-8000-000000000001",
         "amount":"60","payment_status":"VERIFIED","created_at":"2026-11-01T10:00:00Z","released_at":"2026-11-05T10:00:00Z","release_reason":"Ignored text"},
         {"id":"b8000000-0000-4000-8000-000000000002","payment_id":"\(Self.paymentB.uuidString.lowercased())","purchase_id":"b5000000-0000-4000-8000-000000000001",
         "amount":"40","payment_status":"CLAIMED","created_at":"2026-11-01T10:00:00Z","released_at":null,"release_reason":null}]
        """
        let p = try Self.purchaseDTO(Self.purchase(allocations: allocations))
        let utc = TimeZone(identifier: "UTC")!
        let rows = CustomerHoursPresentation.paymentLines(p, reversedAt: [:], timeZone: utc)
        #expect(rows.map(\.status) == ["No longer counted", "Claimed"])
        #expect(rows.map(\.released) == [true, false] && rows.allSatisfy { !$0.reversed })
        let at = ISO8601DateFormatter().date(from: "2026-11-06T09:00:00Z")!
        let reversed = CustomerHoursPresentation.paymentLines(p, reversedAt: [Self.paymentA: at], timeZone: utc)
        #expect(reversed[0].status.hasPrefix("Reversed ") && reversed[0].status.contains("6") && reversed[0].reversed)
        #expect(CustomerHoursPresentation.releasedPaymentIDs(p, features: OwnerFeatures(permissions: ["tenant.finance.read"])) == [Self.paymentA])
        #expect(CustomerHoursPresentation.releasedPaymentIDs(p, features: OwnerFeatures(permissions: [AdjustmentPermission.read])) == [Self.paymentA])
        #expect(CustomerHoursPresentation.releasedPaymentIDs(p, features: OwnerFeatures(permissions: ["tenant.hours.read"])).isEmpty)
        #expect(CustomerHoursPresentation.paymentLines(try Self.purchaseDTO(Self.purchase()), reversedAt: [:]).isEmpty)
    }

    static func statement(totals: String, lines: String) -> String {
        """
        {"customer_id":"b6000000-0000-4000-8000-000000000001","customer_name":"Acme","machine_id":null,"date_from":"2026-11-01","date_to":"2026-11-08",
         "timezone":"UTC","generated_at":"2026-11-08T10:00:00Z","pdf_path":"/x.pdf","purchases":[],"usage":[],"lines":[\(lines)],
         "totals":{"opening_balance":"0","bought":"10","activated":"10","used":"2","transferred_in":"0","transferred_out":"0","expired":"0","cancelled":"0",
         "closing_balance":"8","provisional_at_close":"0","awaiting_activation":"0"\(totals)}}
        """
    }

    static func line(_ type: String, hours: String, at: String, reason: String) -> String {
        """
        {"entry_id":"\(UUID().uuidString.lowercased())","day":"\(at.prefix(10))","occurred_at":"\(at)","entry_type":"\(type)","purchase_id":"b5000000-0000-4000-8000-000000000001",
         "purchase_number":"P-12","machine_id":"\(machine.uuidString.lowercased())","job_id":null,"hours":"\(hours)","balance_after":"5","reason":"\(reason)"}
        """
    }

    @Test func statementTotalsAndAdjustmentCard() throws {
        let decoder = AssetaJSON.decoder()
        let empty = try decoder.decode(HoursStatementDTO.self, from: Data(Self.statement(totals: "", lines: "").utf8))
        #expect(empty.totals.refunded.value == 0 && CustomerHoursPresentation.adjustmentLines(empty).isEmpty)
        let lines = [Self.line("CONSUMED", hours: "-1", at: "2026-11-02T08:00:00Z", reason: "Job"),
                     Self.line("CORRECTION_ADD", hours: "2", at: "2026-11-03T08:00:00Z", reason: "Fix"),
                     Self.line("REFUNDED", hours: "-1", at: "2026-11-05T08:00:00Z", reason: "Unused")].joined(separator: ",")
        let s = try decoder.decode(HoursStatementDTO.self, from: Data(Self.statement(totals: #","refunded":"1","corrected":"2""#, lines: lines).utf8))
        let total = CustomerHoursPresentation.totals(s)
        #expect(total.first { $0.label == "Refunded" }?.value == "1 h" && total.first { $0.label == "Corrected" }?.value == "+2 h")
        let adjustments = CustomerHoursPresentation.adjustmentLines(s)
        #expect(adjustments.map(\.value) == [AdjustmentPresentation.signedHours(DecimalString(-1)), "+2 h"])
        #expect(adjustments[0].label.hasSuffix("· Hours refunded") && adjustments[0].caption == "P-12 · Unused")
        #expect(adjustments[1].label.hasSuffix("· Hours added by correction"))
    }
}
