@testable import AssetaSync
import AssetaModel
import AssetaStore
import AssetaTestSupport
import Foundation
import Testing

/// DEC-033 petty cash on the Supervisor app: snapshots, gating, offline operations, rules and wording (as Android).
@Suite("DEC-033: petty cash on the Supervisor app")
struct PettyCashTests {
    static let fundID = UUID(uuidString: "f0000000-0000-4000-8000-000000000001")!
    static let otherFundID = UUID(uuidString: "f0000000-0000-4000-8000-000000000002")!
    static let movementID = UUID(uuidString: "f1000000-0000-4000-8000-000000000001")!
    static let changeID = UUID(uuidString: "f2000000-0000-4000-8000-000000000001")!
    static let advanceID = UUID(uuidString: "f3000000-0000-4000-8000-000000000001")!
    static let myAdvanceID = UUID(uuidString: "f3000000-0000-4000-8000-000000000002")!
    static let me = UUID(uuidString: "e0000000-0000-4000-8000-000000000001")!
    static let colleague = UUID(uuidString: "e0000000-0000-4000-8000-000000000002")!
    static let caps = [SyncCapability.supervisorInbox, SyncCapability.pettyCash]
    static let permissions: Set<String> = ["tenant.pettycash.read", "tenant.pettycash.count", "tenant.expense.write"]

    static func fund(id: UUID = fundID, balance: String = "300.00", available: String = "250.00",
                     limit: String = "500.00") -> [String: Any] {
        ["id": id.uuidString.lowercased(), "code": "PC-01", "name": "Site box", "holder_staff_id": me.uuidString.lowercased(),
         "holder_staff_name": "Me", "currency": "TZS", "approved_limit": limit, "is_active": true,
         "balance": ["balance": balance, "available_to_spend": available, "approved_limit": limit, "pending_spending": "50.00",
                     "awaiting_acknowledgement": "0", "returns_claimed": "0", "below_low_balance": false,
                     "as_of": "2026-11-11T08:00:00Z"]]
    }

    static func movement(kind: String = "TOP_UP") -> [String: Any] {
        ["id": movementID.uuidString.lowercased(), "number": "PC-2026-00007", "fund_id": fundID.uuidString.lowercased(),
         "petty_cash_fund_name": "Site box", "kind": kind, "status": "ISSUED", "amount": "200.00", "currency": "TZS",
         "issued_at": "2026-11-11T07:00:00Z", "issued_by_name": "Office"]
    }

    static func change() -> [String: Any] {
        ["id": changeID.uuidString.lowercased(), "fund_id": otherFundID.uuidString.lowercased(), "petty_cash_fund_name": "Yard box",
         "from_staff_id": colleague.uuidString.lowercased(), "from_staff_name": "Asha", "to_staff_id": me.uuidString.lowercased(),
         "status": "PENDING", "requested_at": "2026-11-10T07:00:00Z"]
    }

    static func advance(id: UUID, fund: UUID, recipient: UUID) -> [String: Any] {
        ["id": id.uuidString.lowercased(), "number": "PC-2026-0009\(id == advanceID ? 1 : 2)", "fund_id": fund.uuidString.lowercased(),
         "petty_cash_fund_name": "Other box", "recipient_staff_id": recipient.uuidString.lowercased(), "recipient_staff_name": "Asha",
         "amount": "100.00", "currency": "TZS", "status": "OUTSTANDING", "due_at": "2026-11-15T07:00:00Z",
         "approved_spending": "20.00", "pending_spending": "0", "remaining": "80.00"]
    }

    static func policy(_ values: [String: Any], at: Date) -> [String: Any] {
        ["policy_type": "PETTY_CASH", "scope_key": "tenant", "version_ids": [UUID().uuidString.lowercased()], "version_stamp": "v1",
         "values": values, "valid_until": ISO8601DateFormatter().string(from: at.addingTimeInterval(86400))]
    }

    /// A synced phone with my fund, a top-up to acknowledge, a fund handed to me and two advances.
    static func synced(advances: Bool = true) async throws -> SyncHarness {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate {
            $0.capabilities = Self.caps
            $0.extraData = ["petty_cash_funds": [Self.fund()], "petty_cash_awaiting": [Self.movement()],
                            "petty_cash_holder_changes": [Self.change()],
                            "petty_cash_advances": [Self.advance(id: Self.advanceID, fund: Self.fundID, recipient: Self.colleague),
                                                    Self.advance(id: Self.myAdvanceID, fund: Self.otherFundID, recipient: Self.me)]]
            $0.snapshots.append(Self.policy(["count_witness_required": true, "return_evidence_required": true,
                                             "advances_enabled": advances, "max_expense_amount": "150.00"], at: $0.serverTime))
        }
        _ = try await h.engine().sync()
        return h
    }

    // MARK: - Snapshot

    @Test func everyPullReplacesTheSnapshotAndNoCapabilityClearsIt() async throws {
        let h = try await Self.synced()
        let view = h.directoryView.pettyCash()
        #expect(view.funds.map(\.code) == ["PC-01"] && view.funds[0].balance?.availableToSpend.value == 250)
        #expect(view.waiting.count == 2 && view.advances.count == 2)
        #expect(view.policy == PettyCashPolicyValues(countWitnessRequired: true, returnEvidenceRequired: true, advancesEnabled: true,
                                                     maxExpenseAmount: 150))
        h.server.mutate { $0.extraData = ["petty_cash_funds": [Self.fund(balance: "100.00", available: "90.00")]] }
        _ = try await h.engine().sync(force: true)
        let next = h.directoryView.pettyCash()
        #expect(next.funds.first?.balance?.balance.value == 100 && next.waiting.isEmpty && next.advances.isEmpty)
        h.server.mutate { $0.capabilities = [SyncCapability.supervisorInbox] }
        _ = try await h.engine().sync(force: true)
        #expect(h.directoryView.pettyCash().funds.isEmpty)
    }

    @Test func advancesAreHiddenWhileTheTenantDoesNotUseThem() async throws {
        let h = try await Self.synced(advances: false)
        let view = h.directoryView.pettyCash()
        #expect(view.advances.isEmpty && view.expenseFunds.map(\.id) == [Self.fundID])
    }

    // MARK: - Gating

    @Test func gatingNeedsCapabilityPermissionAndTheSwitch() {
        let on = FieldAccess(capabilities: Set(Self.caps), permissions: Self.permissions)
        #expect(on.pettyCash && on.pettyCashCount)
        #expect(!FieldAccess(capabilities: [SyncCapability.supervisorInbox], permissions: Self.permissions).pettyCash)
        #expect(!FieldAccess(capabilities: Set(Self.caps), permissions: ["tenant.expense.write"]).pettyCash)
        #expect(!FieldAccess(capabilities: Set(Self.caps), permissions: Self.permissions, disabledCapabilities: ["PETTY_CASH"]).pettyCash)
        let noCount = FieldAccess(capabilities: Set(Self.caps), permissions: ["tenant.pettycash.read"])
        #expect(noCount.pettyCash && !noCount.pettyCashCount)
    }

    // MARK: - Operations

    private func payload(_ op: ClientOperation) throws -> [String: Any] {
        try #require(try JSONSerialization.jsonObject(with: Data(op.payloadJSON.utf8)) as? [String: Any])
    }

    @Test func acknowledgementIsQueuedOnceAndLeavesWaiting() async throws {
        let h = try await Self.synced()
        let op = try h.recorder.acknowledgePettyCash(movementID: Self.movementID, acknowledge: true, receivedText: "190", note: " short ")
        let body = try payload(op)
        #expect(op.opType == "PETTY_CASH_ACKNOWLEDGEMENT" && op.entityID == Self.movementID)
        #expect(body["movement_id"] as? String == Self.movementID.lowercased && body["acknowledged"] as? Bool == true)
        #expect(body["amount_received"] as? String == "190" && body["note"] as? String == "short")
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved)) {
            try h.recorder.acknowledgePettyCash(movementID: Self.movementID, acknowledge: true, receivedText: "190", note: "")
        }
        let view = h.directoryView.pettyCash()
        #expect(!view.waiting.contains { $0.id == Self.movementID } && view.onPhone.map(\.id) == [op.id])
        // A synced answer stays listed under "Recorded on this phone" with its state (as Android).
        try h.store.database.execute("UPDATE client_operation SET status = 'ACKED', server_result_json = '{}' WHERE id = ?", [.text(op.id.lowercased)])
        #expect(h.directoryView.pettyCash().onPhone.map(\.status) == [.acked])
    }

    @Test func aDisputeNeedsAReasonAndCarriesNoAmount() async throws {
        let h = try await Self.synced()
        #expect(throws: FieldRecorderError.invalid(FieldAccountabilityTexts.ackErrReason)) {
            try h.recorder.acknowledgePettyCash(movementID: Self.movementID, acknowledge: false, receivedText: "200", note: " ")
        }
        let op = try h.recorder.acknowledgePettyCash(movementID: Self.movementID, acknowledge: false, receivedText: "200",
                                                     note: "Nothing arrived")
        let body = try payload(op)
        #expect(body["acknowledged"] as? Bool == false && body["amount_received"] == nil)
    }

    @Test func topUpWithoutAmountAsksForTheSuggestionAndAboveTheCapNeedsAReason() async throws {
        let h = try await Self.synced()
        let plain = try h.recorder.requestPettyCashTopUp(fundID: Self.fundID, amountText: "", note: "", aboveReason: "")
        let body = try payload(plain)
        #expect(plain.opType == "PETTY_CASH_TOP_UP_REQUEST" && body["amount"] == nil)
        #expect(body["client_id"] as? String == plain.entityID.lowercased && body["fund_id"] as? String == Self.fundID.lowercased)
        // limit 500 - balance 300 = 200: 250 is above it.
        #expect(throws: FieldRecorderError.invalid(PettyCashTexts.errAboveReason)) {
            try h.recorder.requestPettyCashTopUp(fundID: Self.fundID, amountText: "250", note: "", aboveReason: "x")
        }
        let above = try h.recorder.requestPettyCashTopUp(fundID: Self.fundID, amountText: "250", note: "", aboveReason: "Fuel run")
        #expect(try payload(above)["above_cap_reason"] as? String == "Fuel run")
        #expect(try payload(above)["amount"] as? String == "250")
    }

    @Test func returnNeedsItsPhotoAndWaitsForTheUpload() async throws {
        let h = try await Self.synced()
        #expect(throws: FieldRecorderError.invalid(PettyCashTexts.errEvidence)) {
            try h.recorder.returnPettyCash(fundID: Self.fundID, amountText: "50", method: "CASH_TO_OFFICE", depositAccountID: nil,
                                           reference: "", note: "", evidence: [], evidenceRequired: true)
        }
        let photo = try h.evidence.store(Data((0..<1700).map { UInt8($0 % 113) }), fileExtension: "jpg", contentType: "image/jpeg")
        let op = try h.recorder.returnPettyCash(fundID: Self.fundID, amountText: "50", method: "CASH_TO_OFFICE", depositAccountID: nil,
                                                reference: "", note: "", evidence: [photo], evidenceRequired: true)
        let attachments = try h.store.attachments.attachments(operationID: op.id)
        #expect(attachments.map(\.purpose) == ["PETTY_CASH_EVIDENCE"])
        _ = try await h.engine().sync(force: true)
        let session = try #require(h.server.read { $0.blobs.keys.first })
        let applied = try #require(h.server.read { $0.appliedPayloads[op.id] })
        #expect(applied["evidence_upload_ids"] as? [String] == [session.lowercased])
        #expect(applied["amount"] as? String == "50" && applied["method"] as? String == "CASH_TO_OFFICE")
    }

    @Test func countTakesTheWitnessAndZero() async throws {
        let h = try await Self.synced()
        #expect(throws: FieldRecorderError.invalid(PettyCashTexts.errCounted)) {
            try h.recorder.countPettyCash(fundID: Self.fundID, countedText: "", witnessUserID: nil, note: "", evidence: [])
        }
        let witness = UUID()
        let op = try h.recorder.countPettyCash(fundID: Self.fundID, countedText: "0", witnessUserID: witness, note: "", evidence: [])
        let body = try payload(op)
        #expect(op.opType == "PETTY_CASH_COUNT" && body["counted_amount"] as? String == "0")
        #expect(body["witness_user_id"] as? String == witness.lowercased && body["evidence_upload_ids"] as? [String] == [])
    }

    @Test func holderChangeDeclineNeedsAReason() async throws {
        let h = try await Self.synced()
        #expect(throws: FieldRecorderError.invalid(PettyCashTexts.errReason)) {
            try h.recorder.answerPettyCashHolderChange(changeID: Self.changeID, accept: false, note: "no")
        }
        let op = try h.recorder.answerPettyCashHolderChange(changeID: Self.changeID, accept: true, note: "")
        let body = try payload(op)
        #expect(op.opType == "PETTY_CASH_HOLDER_CHANGE_ACKNOWLEDGEMENT" && body["accept"] as? Bool == true)
        #expect(body["holder_change_id"] as? String == Self.changeID.lowercased)
        #expect(!h.directoryView.pettyCash().waiting.contains { $0.id == Self.changeID })
    }

    @Test func advanceFromMyFundIsClearedWithTheChange() async throws {
        let h = try await Self.synced()
        let view = h.directoryView.pettyCash()
        #expect(view.advances.first { $0.id == Self.advanceID }?.fromMyFund == true)
        #expect(view.advances.first { $0.id == Self.myAdvanceID }?.fromMyFund == false)
        let op = try h.recorder.clearPettyCashAdvance(advanceID: Self.advanceID, changeText: "80", note: "")
        let body = try payload(op)
        #expect(op.opType == "PETTY_CASH_ADVANCE_CLEARANCE" && body["change_returned"] as? String == "80")
        #expect(!h.directoryView.pettyCash().advances.contains { $0.id == Self.advanceID })
    }

    @Test func refusedAnswersComeBackToWaiting() async throws {
        let h = try await Self.synced()
        let op = try h.recorder.acknowledgePettyCash(movementID: Self.movementID, acknowledge: true, receivedText: "200", note: "")
        try h.store.database.execute("UPDATE client_operation SET status = 'CONFLICT' WHERE id = ?", [.text(op.id.lowercased)])
        let view = h.directoryView.pettyCash()
        #expect(view.waiting.contains { $0.id == Self.movementID } && view.onPhone.map(\.id) == [op.id])
    }

    // MARK: - Expense paid from petty cash

    @Test func expenseFromAFundCarriesItAndChecksCurrencyAndAdvance() async throws {
        let h = try await Self.synced()
        guard case let .allowed(snapshot) = try h.directoryView.expenseGate() else { Issue.record("gate"); return }
        var draft = ExpenseDraft()
        draft.categoryID = FinanceFixtures.categoryID
        draft.amountText = "40"
        draft.description = "Water"
        draft.currency = "USD"
        draft.paidFrom = .pettyCash
        draft.gps = .fix(latitude: -6.8, longitude: 39.3, accuracyM: 9, capturedAt: h.clock.wallNow)
        let receipt = try h.evidence.store(Data((0..<900).map { UInt8($0 % 101) }), fileExtension: "jpg", contentType: "image/jpeg")
        #expect(throws: FieldRecorderError.invalid(PettyCashTexts.expenseFundRequired)) {
            try h.recorder.recordExpense(draft, receipts: [receipt], snapshot: snapshot, baseCurrency: "TZS", incurredAt: h.clock.wallNow)
        }
        draft.pettyCashFundID = Self.fundID
        #expect(throws: FieldRecorderError.invalid(PettyCashTexts.expenseCurrency("TZS"))) {
            try h.recorder.recordExpense(draft, receipts: [receipt], snapshot: snapshot, baseCurrency: "TZS", incurredAt: h.clock.wallNow)
        }
        draft.currency = "TZS"
        let op = try h.recorder.recordExpense(draft, receipts: [receipt], snapshot: snapshot, baseCurrency: "TZS", incurredAt: h.clock.wallNow)
        let body = try payload(op)
        #expect(body["paid_from"] as? String == "PETTY_CASH" && body["petty_cash_fund_id"] as? String == Self.fundID.lowercased)
        #expect(body["petty_cash_advance_id"] == nil)
        // A fund I do not hold: only through the advance given to me.
        draft.pettyCashFundID = Self.otherFundID
        #expect(throws: FieldRecorderError.invalid(PettyCashTexts.expenseAdvanceRequired)) {
            try h.recorder.recordExpense(draft, receipts: [receipt], snapshot: snapshot, baseCurrency: "TZS", incurredAt: h.clock.wallNow,
                                         clientID: UUID())
        }
    }

    @Test func expenseNotesWarnAboveAvailableAndTheMaximum() async throws {
        let h = try await Self.synced()
        let view = h.directoryView.pettyCash()
        #expect(PettyCashRules.expenseNotes(amount: 100, fundID: Self.fundID, advanceID: nil, view: view, baseCurrency: "TZS").isEmpty)
        let notes = PettyCashRules.expenseNotes(amount: 260, fundID: Self.fundID, advanceID: nil, view: view, baseCurrency: "TZS")
        #expect(notes == [PettyCashTexts.expenseOverspend("250 TZS"), PettyCashTexts.expenseAboveMaximum("150 TZS")])
        // The advance's remaining is what counts when spending from it.
        #expect(PettyCashRules.expenseNotes(amount: 90, fundID: Self.otherFundID, advanceID: Self.myAdvanceID, view: view,
                                            baseCurrency: "TZS") == [PettyCashTexts.expenseOverspend("80 TZS")])
        // Another currency than the base: the maximum does not apply.
        #expect(PettyCashRules.expenseNotes(amount: 200, fundID: Self.fundID, advanceID: nil, view: view, baseCurrency: "USD").isEmpty)
    }

    // MARK: - Wording and links

    @Test func wordingMatchesTheStringsDoc() {
        #expect(PettyCashTexts.expenseOverspend("250 TZS")
                == "Above what the fund has available (250 TZS): it is kept for approval and marked for the approver to check.")
        #expect(PettyCashTexts.rowWaiting(2) == "2 waiting for you")
        #expect(PettyCashTexts.waitingHolderChange(fund: "Yard box", name: "Asha") == "Take over Yard box from Asha")
        #expect(FieldAccountabilityTexts.conflictText("PETTY_CASH_INSUFFICIENT")
                == "The fund did not have enough available. Check the fund and record the expense again if needed.")
        #expect(FieldAccountabilityTexts.operationTitle(.pettyCashCount, payload: nil) == "Petty cash count")
        #expect(ExpenseFlags.label("OVERSPEND") == "Recorded above what the fund had available")
        #expect(ExpenseFlags.label("SPENT_FROM_COLLECTIONS") == "Paid from collected cash")
        #expect(ExpenseFlags.label("ABOVE_PETTY_CASH_MAXIMUM") == "Above the petty cash maximum per expense")
        #expect(ExpenseFlags.label("NEW_FLAG") == "New flag")
        #expect(InboxTexts.paidFrom("PETTY_CASH") == "Petty cash")
    }

    @Test func notificationsOpenTheRecordOrMyPettyCash() {
        let id = UUID()
        #expect(InboxLink.from(entity: "petty_cash_movement", id: id.uuidString) == .pettyCashMovement(id))
        #expect(InboxLink.from(entity: "petty_cash_holder_change", id: id.uuidString) == .pettyCashHolderChange(id))
        #expect(InboxLink.from(entity: "petty_cash_count", id: id.uuidString) == .pettyCash)
    }

    @Test func syncedExpenseCarriesItsFlags() throws {
        let json = """
        {"id":"\(UUID().uuidString)","category_id":"\(UUID().uuidString)","description":"x","amount":"1","currency":"TZS",
         "paid_from":"PETTY_CASH","status":"PENDING_APPROVAL","incurred_at":"2026-11-11T08:00:00Z","submitted_at":"2026-11-11T08:00:00Z",
         "policy_version":"v","receipt_required":false,"source":"SYNC","sync_revision":3,"petty_cash_fund_id":"\(Self.fundID.uuidString)",
         "control_flags":["OVERSPEND"]}
        """
        let dto = try AssetaJSON.decoder().decode(SyncExpenseDTO.self, from: Data(json.utf8))
        #expect(dto.controlFlags == ["OVERSPEND"] && dto.pettyCashFundID == Self.fundID)
    }
}
