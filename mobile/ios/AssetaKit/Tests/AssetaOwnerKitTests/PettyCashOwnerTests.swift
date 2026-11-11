@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// DEC-033 in the Owner app: petty cash fundings, top-ups and adjustments to approve. Same as Android `PettyCashReviewOwnerTest`.
struct PettyCashOwnerTests {
    typealias T = PettyCashReviewText
    static let id = UUID(uuidString: "44444444-4444-4444-8444-444444444444")!
    static let proposer = UUID(uuidString: "55555555-5555-4555-8555-555555555555")!
    let money: (DecimalString, String) -> String = { "\($1) \($0.description)" }

    static func movement(kind: String = "TOP_UP", status: String = "PROPOSED", aboveCap: String? = nil) throws -> PettyCashMovementDTO {
        let reason = aboveCap.map { "\"\($0)\"" } ?? "null"
        let json = """
        {"id":"\(id.uuidString.lowercased())","number":"PC-2026-00011","fund_id":"\(id.uuidString.lowercased())","petty_cash_fund_name":"Site A box",
         "kind":"\(kind)","status":"\(status)","client_id":null,"holder_staff_id":"\(proposer.uuidString.lowercased())","holder_staff_name":"Juma",
         "amount":"50000.00","currency":"TZS","deposit_account_id":null,"method":null,"reference":null,"note":"Fuel and water",
         "suggested_amount":"40000.00","cap_amount":"45000.00","above_cap_reason":\(reason),"basis_from":null,"evidence_attachment_ids":[],
         "source":"API","created_by":"\(proposer.uuidString.lowercased())","created_by_name":"Asha","created_at":"2026-11-11T07:00:00Z",
         "client_created_at":null,"decided_by":null,"decided_at":null,"decision_note":null,"issued_by":null,"issued_at":null,
         "received_by":null,"received_at":null,"amount_received":null,"receipt_method":null,"receipt_note":null}
        """
        return try AssetaJSON.decoder().decode(PettyCashMovementDTO.self, from: Data(json.utf8))
    }

    static func adjustment(amount: String = "-2500.00", status: String = "PENDING") throws -> PettyCashAdjustmentDTO {
        let json = """
        {"id":"\(UUID().uuidString.lowercased())","number":"PC-2026-00012","fund_id":"\(id.uuidString.lowercased())","petty_cash_fund_name":"Site A box",
         "amount":"\(amount)","currency":"TZS","reason_id":null,"reason":"Count difference","evidence_attachment_ids":[],"status":"\(status)",
         "created_by":"\(proposer.uuidString.lowercased())","created_by_name":"Asha","created_at":"2026-11-11T07:00:00Z",
         "decided_by":null,"decided_at":null,"decision_note":null}
        """
        return try AssetaJSON.decoder().decode(PettyCashAdjustmentDTO.self, from: Data(json.utf8))
    }

    @Test func listsAskOnlyForWhatWaits() {
        let movements = OwnerAPI.pettyCashMovementsToApprove()
        #expect(movements.path.hasSuffix("/petty-cash/movements"))
        #expect(movements.queryItems.contains(URLQueryItem(name: "status", value: "PROPOSED")))
        let adjustments = OwnerAPI.pettyCashAdjustmentsToApprove()
        #expect(adjustments.path.hasSuffix("/petty-cash/adjustments"))
        #expect(adjustments.queryItems.contains(URLQueryItem(name: "status", value: "PENDING")))
    }

    @Test func rowsNameTheRequestAndSignAdjustments() throws {
        let rows = T.rows(movements: [try Self.movement(), try Self.movement(status: "APPROVED")],
                          adjustments: [try Self.adjustment(), try Self.adjustment(amount: "5000.00", status: "APPROVED")])
        #expect(rows.count == 2)
        #expect(T.headline(rows[0], money: money) == "Top-up TZS 50000 · Site A box")
        #expect(T.summary(rows[0]) == "PC-2026-00011 · Proposed by Asha")
        #expect(T.reasonLine(rows[0]) == "Fuel and water")
        #expect(T.headline(rows[1], money: money) == "Fund adjustment -TZS 2500 · Site A box")
        #expect(T.amount(.adjustment(try Self.adjustment(amount: "5000")), money: money) == "+TZS 5000")
        #expect(T.reasonLine(rows[1]) == "Count difference")
        #expect(T.reasonLine(.movement(try Self.movement(aboveCap: "Long trip"))) == "Long trip")
    }

    @Test func factsInScreenOrder() throws {
        let fields = T.fields(try Self.movement(), timeZone: TimeZone(identifier: "UTC")!, money: money)
        #expect(fields.map(\.label) == ["Fund", "Holder", "Kind", "Number", "Amount", "Suggested", "Brings the fund to its limit", "Note",
                                        "Proposed by", "Proposed"])
        let adjustment = T.fields(try Self.adjustment(), timeZone: TimeZone(identifier: "UTC")!, money: money)
        #expect(adjustment.map(\.label) == ["Fund", "Kind", "Number", "Amount", "Reason", "Proposed by", "Proposed"])
        #expect(adjustment.first { $0.label == "Kind" }?.value == "Fund adjustment")
    }

    @Test func aReaderOpensTheRecordButOnlyAnApproverSeesTheSection() {
        let reader = OwnerFeatures(permissions: ["tenant.pettycash.read"], disabledCapabilities: [])
        #expect(reader.allows(.pettyCashAdjustment(Self.id)) && !reader.pettyCashApprove)
        #expect(!OwnerFeatures(permissions: ["tenant.pettycash.read"], disabledCapabilities: ["PETTY_CASH"]).allows(.pettyCashMovement(Self.id)))
    }

    @Test func decisionRules() throws {
        #expect(T.canDecide(approve: true, note: ""))
        #expect(!T.canDecide(approve: false, note: "no"))
        #expect(T.canDecide(approve: false, note: "Not needed"))
        #expect(T.isOwn(createdBy: Self.proposer, userID: Self.proposer))
        #expect(!T.isOwn(createdBy: Self.proposer, userID: UUID()))
        #expect(T.decidable("PROPOSED") && T.decidable("PENDING") && !T.decidable("APPROVED"))
        #expect(T.status("PROPOSED") == "Waiting for approval" && T.kind("FUNDING") == "Funding")
    }

    @Test func refusalsAreTheServersOwnWordsExceptAlreadyDecided() {
        let holder = APIError.server(status: 422, body: ErrorBody(code: "SEGREGATION_OF_DUTIES",
                                                                 message: "The holder cannot approve their own fund", correlationID: "c"))
        #expect(T.message(for: holder) == "The holder cannot approve their own fund")
        let decided = APIError.server(status: 409, body: ErrorBody(code: "PETTY_CASH_ALREADY_DECIDED", message: "Already APPROVED",
                                                                  correlationID: "c"))
        #expect(T.message(for: decided) == T.alreadyDecided && T.needsReload(decided))
    }

    @Test func gatingNeedsReadApproveAndTheSwitch() {
        let on = OwnerFeatures(permissions: ["tenant.pettycash.read", "tenant.pettycash.approve"], disabledCapabilities: [])
        #expect(on.pettyCashApprove && on.approvalsScreen && on.allows(.pettyCashMovement(Self.id)))
        #expect(!OwnerFeatures(permissions: ["tenant.pettycash.read"], disabledCapabilities: []).pettyCashApprove)
        #expect(!OwnerFeatures(permissions: ["tenant.pettycash.read", "tenant.pettycash.approve"],
                               disabledCapabilities: ["PETTY_CASH"]).pettyCashApprove)
    }

    @Test func deepLinksOpenTheRecord() {
        let id = Self.id
        #expect(DeepLinkParser.route(entity: "petty_cash_movement", id: id.uuidString, path: nil) == .pettyCashMovement(id))
        #expect(DeepLinkParser.route(entity: "petty_cash_adjustment", id: id.uuidString, path: nil) == .pettyCashAdjustment(id))
        #expect(DeepLinkParser.route(entity: "petty_cash_fund", id: id.uuidString, path: nil) == .approvals)
        #expect(DeepLinkParser.route(path: "/tenant/finance/petty-cash/movements/\(id.uuidString.lowercased())") == .pettyCashMovement(id))
        #expect(DeepLinkParser.route(path: "/tenant/finance/petty-cash/adjustments/\(id.uuidString.lowercased())") == .pettyCashAdjustment(id))
        #expect(DeepLinkParser.route(path: "/tenant/finance/petty-cash/funds") == .approvals)
        #expect(OwnerRoute.pettyCashMovement(id).identifiesRecord)
    }

    @Test func expenseFlagsShowNeutrally() throws {
        let json = """
        {"id":"\(UUID().uuidString)","amount":"10.00","currency":"TZS","description":"Water","status":"PENDING_APPROVAL",
         "incurred_at":"2026-11-11T07:00:00Z","paid_from":"PETTY_CASH","control_flags":["OVERSPEND","ABOVE_PETTY_CASH_MAXIMUM"]}
        """
        let e = try AssetaJSON.decoder().decode(ExpenseDTO.self, from: Data(json.utf8))
        #expect(SpendText.expenseChecks(e) == "To check: Recorded above what the fund had available; Above the petty cash maximum per expense")
        #expect(SpendText.expenseRow(e).checks == SpendText.expenseChecks(e))
        #expect(OwnerFormat.humanize(e.paidFrom) == "Petty cash")
    }
}
