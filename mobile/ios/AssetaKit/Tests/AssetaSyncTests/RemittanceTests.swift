import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// DEC-031 D2/D3 on the field side: deposit accounts from sync, the hand-over form's method / account / slip photos
/// and the tenant's requirements, the offline payload (evidence uploads with purpose REMITTANCE_EVIDENCE, DEFERRED until
/// uploaded), new conflicts and the held-too-long overdue screen. Same rules as Android `RemittanceRules`.
struct RemittanceTests {
    static let bankID = UUID(uuidString: "d0000000-0000-4000-8000-000000000001")!
    static let mobileID = UUID(uuidString: "d0000000-0000-4000-8000-000000000002")!
    static let officeID = UUID(uuidString: "d0000000-0000-4000-8000-000000000003")!
    static let usdID = UUID(uuidString: "d0000000-0000-4000-8000-000000000004")!

    static func account(_ id: UUID, _ name: String, _ type: String, currency: String = "TZS", active: Bool = true,
                        institution: Any = "CRDB", masked: Any = "•••• 4821", revision: Int = 5) -> [String: Any] {
        ["id": id.uuidString.lowercased(), "name": name, "account_type": type, "institution": institution,
         "account_number_masked": masked, "currency": currency, "note": NSNull(), "is_active": active, "version": 1,
         "created_by": NSNull(), "created_by_name": NSNull(), "created_at": "2026-10-26T08:00:00Z",
         "updated_at": "2026-10-26T08:00:00Z", "deactivated_at": NSNull(), "deactivated_by": NSNull(),
         "deactivated_by_name": NSNull(), "deactivation_reason": NSNull(), "sync_revision": revision]
    }

    nonisolated(unsafe) static let accounts: [[String: Any]] = [
        account(bankID, "CRDB main", "BANK"),
        account(mobileID, "M-Pesa till", "MOBILE_MONEY", institution: "Vodacom", masked: NSNull()),
        account(officeID, "Head office safe", "CASH_OFFICE", institution: NSNull(), masked: NSNull()),
        account(usdID, "USD account", "BANK", currency: "USD"),
    ]

    static let all = AccountabilityTests.all + [SyncCapability.remittanceDetails]

    static func decoded(_ json: [String: Any]) throws -> DepositAccountDTO {
        try AssetaJSON.decoder().decode(DepositAccountDTO.self, from: JSONSerialization.data(withJSONObject: json))
    }

    // MARK: - Access and policy

    @Test func detailsNeedTheCapabilityAndRequirementsFollowCashCustody() {
        let policy = CashCustodyPolicyValues(recordersMayRecordForOthers: false, transferAckRequired: false,
                                             recorderReceiverCountsAsAck: false, floatAckRequired: false,
                                             remitFullBalance: false, retentionAllowed: false,
                                             remittanceReferenceRequired: true, remittanceEvidenceRequired: true,
                                             remittanceAccountRequired: true)
        let old = FieldAccess(capabilities: Set(AccountabilityTests.all), permissions: AccountabilityTests.permissions, cash: policy)
        #expect(!old.remittanceDetails && old.remittanceRequirements == RemittanceRequirements())
        let on = FieldAccess(capabilities: Set(Self.all), permissions: AccountabilityTests.permissions, cash: policy)
        #expect(on.remittanceDetails)
        #expect(on.remittanceRequirements == RemittanceRequirements(account: true, reference: true, evidence: true))
        // CASH_CUSTODY switched off: the details stay, the requirements read as off.
        let off = FieldAccess(capabilities: Set(Self.all), permissions: AccountabilityTests.permissions, cash: policy,
                              disabledCapabilities: [TenantCapability.cashCustody])
        #expect(off.remittanceDetails && off.remittanceRequirements == RemittanceRequirements())
        // Unknown policy: nothing required.
        let unknown = FieldAccess(capabilities: Set(Self.all), permissions: AccountabilityTests.permissions)
        #expect(unknown.remittanceRequirements == RemittanceRequirements())
    }

    @Test func cashPolicyDecodesTheNewKeysTolerantly() throws {
        let base = #"{"recorders_may_record_for_others":true,"transfer_ack_required":false,"recorder_receiver_counts_as_ack":false,"float_ack_required":false,"remit_full_balance":false,"retention_allowed":true"#
        let old = try AssetaJSON.decoder().decode(CashCustodyPolicyValues.self, from: Data((base + "}").utf8))
        #expect(!old.remittanceAccountRequired && !old.remittanceReferenceRequired && !old.remittanceEvidenceRequired)
        #expect(old.maxHoldingDays == nil && old.recordersMayRecordForOthers)
        let new = try AssetaJSON.decoder().decode(CashCustodyPolicyValues.self, from: Data((base
            + #","remittance_reference_required":true,"remittance_evidence_required":false,"remittance_account_required":true,"max_holding_days":3}"#).utf8))
        #expect(new.remittanceReferenceRequired && !new.remittanceEvidenceRequired && new.remittanceAccountRequired)
        #expect(new.maxHoldingDays == 3)
        // The DEC-030 switches stay strict.
        #expect(throws: (any Error).self) {
            try AssetaJSON.decoder().decode(CashCustodyPolicyValues.self, from: Data(#"{"retention_allowed":true}"#.utf8))
        }
    }

    // MARK: - Rules and form

    @Test func pickerListsActiveAccountsOfTheCurrencyAndMethod() throws {
        var all = try Self.accounts.map(Self.decoded)
        all.append(try Self.decoded(Self.account(UUID(), "Closed bank", "BANK", active: false)))
        #expect(RemittanceRules.accounts(all, currency: "tzs", method: .bankDeposit).map(\.name) == ["CRDB main"])
        #expect(RemittanceRules.accounts(all, currency: "USD", method: .bankDeposit).map(\.name) == ["USD account"])
        #expect(RemittanceRules.accounts(all, currency: "TZS", method: .mobileMoney).map(\.name) == ["M-Pesa till"])
        #expect(RemittanceRules.accounts(all, currency: "TZS", method: .cashToOffice).map(\.name) == ["Head office safe"])
        #expect(RemittanceRules.subtitle(all[0]) == "CRDB · •••• 4821")
        #expect(RemittanceRules.subtitle(all[1]) == "Vodacom")
        #expect(RemittanceRules.subtitle(all[2]) == "")
    }

    @Test func choosingAnAccountSetsTheMethodAndANewMethodDropsAMismatchedAccount() throws {
        let all = try Self.accounts.map(Self.decoded)
        var draft = RemittanceDraft()
        #expect(draft.method == .cashToOffice && draft.accountID == nil)
        RemittanceForm.selectAccount(&draft, accountID: Self.mobileID, accounts: all)
        #expect(draft.method == .mobileMoney && draft.accountID == Self.mobileID)
        RemittanceForm.selectAccount(&draft, accountID: nil, accounts: all)
        #expect(draft.method == .mobileMoney && draft.accountID == nil)
        RemittanceForm.selectAccount(&draft, accountID: Self.bankID, accounts: all)
        RemittanceForm.selectMethod(&draft, method: .bankDeposit, accounts: all)
        #expect(draft.accountID == Self.bankID)
        RemittanceForm.selectMethod(&draft, method: .cashToOffice, accounts: all)
        #expect(draft.method == .cashToOffice && draft.accountID == nil)
    }

    @Test func requirementLinesAndLabels() throws {
        let all = try Self.accounts.map(Self.decoded)
        let T = FieldAccountabilityTexts.self
        let none = RemittanceRequirements(), every = RemittanceRequirements(account: true, reference: true, evidence: true)
        #expect(RemittanceRules.check(none, method: .bankDeposit, accountID: nil, account: nil, currency: "TZS", reference: "",
                                      photoCount: 0).isEmpty)
        #expect(RemittanceRules.check(every, method: .bankDeposit, accountID: nil, account: nil, currency: "TZS", reference: " ",
                                      photoCount: 0) == [T.remitErrAccount, T.remitErrReference, T.remitErrEvidence])
        // Cash to the office never needs a reference.
        #expect(RemittanceRules.check(every, method: .cashToOffice, accountID: Self.officeID, account: all[2], currency: "TZS",
                                      reference: "", photoCount: 1).isEmpty)
        // A chosen account that is gone, of another type, or of another currency.
        #expect(RemittanceRules.check(none, method: .bankDeposit, accountID: UUID(), account: nil, currency: "TZS", reference: "",
                                      photoCount: 0) == [RemittanceRules.errAccountGone])
        #expect(RemittanceRules.check(none, method: .bankDeposit, accountID: Self.mobileID, account: all[1], currency: "TZS",
                                      reference: "", photoCount: 0) == [RemittanceRules.errAccountMismatch])
        #expect(RemittanceRules.check(none, method: .bankDeposit, accountID: Self.usdID, account: all[3], currency: "TZS",
                                      reference: "", photoCount: 0) == [RemittanceRules.errAccountCurrency])
        #expect(RemittanceRules.check(none, method: .cashToOffice, accountID: nil, account: nil, currency: "TZS", reference: "",
                                      photoCount: 11) == ["At most 10 photos per handover."])
        #expect(RemittanceForm.accountLabel(none) == "Paid into (optional)" && RemittanceForm.accountLabel(every) == "Paid into")
        #expect(RemittanceForm.referenceLabel(every, method: .mobileMoney) == "Transaction reference")
        #expect(RemittanceForm.referenceLabel(every, method: .cashToOffice) == "Reference (deposit slip, transaction no.) (optional)")
        #expect(RemittanceForm.photosLabel(every) == "Deposit slip or payment confirmation")
        #expect(RemittanceForm.photosLabel(none) == "Deposit slip or payment confirmation (optional)")
        #expect(RemittanceMethod.allCases.map(T.remitMethodText) == ["Cash to the office", "Bank deposit", "Mobile money"])
    }

    // MARK: - Sync and outbox

    @Test func depositAccountsSyncAndDeactivationsLeaveThePicker() async throws {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate { $0.capabilities = Self.all; $0.depositAccounts = Self.accounts }
        let engine = h.engine()
        _ = try await engine.sync()
        #expect(try h.directoryView.depositAccounts().map(\.name) == ["CRDB main", "Head office safe", "M-Pesa till", "USD account"])
        h.server.mutate { $0.depositAccounts = [Self.account(Self.bankID, "CRDB main", "BANK", active: false, revision: 9)] }
        _ = try await engine.sync(force: true)
        #expect(try h.directoryView.depositAccounts().map(\.name) == ["Head office safe", "M-Pesa till", "USD account"])
        #expect(try h.directoryView.depositAccount(Self.bankID)?.isActive == false)
    }

    @Test func handoverWithSlipPhotoWaitsForUploadThenAcks() async throws {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate { $0.capabilities = Self.all; $0.depositAccounts = Self.accounts }
        let engine = h.engine()
        _ = try await engine.sync()
        let slip = try h.evidence.store(Data((0..<1700).map { UInt8($0 % 191) }), fileExtension: "jpg", contentType: "image/jpeg")
        let every = RemittanceRequirements(account: true, reference: true, evidence: true)
        // The recorder enforces the requirements too.
        #expect(throws: FieldRecorderError.invalid(FieldAccountabilityTexts.remitErrReference)) {
            try h.recorder.recordCashHandover(amountText: "150000", currency: "TZS", reference: "", note: nil,
                                              handedAt: h.clock.wallNow, method: .bankDeposit, depositAccountID: Self.bankID,
                                              requirements: every, evidence: [slip])
        }
        let op = try h.recorder.recordCashHandover(amountText: "150000", currency: "tzs", reference: " DS-778 ", note: nil,
                                                   handedAt: h.clock.wallNow, method: .bankDeposit, depositAccountID: Self.bankID,
                                                   requirements: every, evidence: [slip])
        let queued = try JSONValue.parse(op.payloadJSON)
        #expect(queued["method"]?.stringValue == "BANK_DEPOSIT" && queued["evidence_upload_ids"] == .array([]))
        #expect(try h.store.outbox.readyToSend(tenantID: SyncFixtures.tenant, now: h.clock.wallNow, limit: 10).isEmpty)
        #expect(try h.directoryView.overview().items.first { $0.id == op.id }?.waitingFor == "Waiting for its photos to upload")
        _ = try await engine.sync(force: true)
        #expect(try h.status(op.id) == .acked)
        let applied = try #require(h.server.read { $0.appliedPayloads[op.id] })
        let session = try #require(h.server.read { $0.blobs.keys.first })
        #expect(applied["evidence_upload_ids"] as? [String] == [session.lowercased])
        #expect(applied["deposit_account_id"] as? String == Self.bankID.lowercased)
        #expect(applied["reference"] as? String == "DS-778" && applied["currency"] as? String == "TZS")
        #expect(h.server.read { $0.blobs.values.first?.purpose } == "REMITTANCE_EVIDENCE")
    }

    @Test func withoutTheCapabilityThePayloadIsUnchanged() throws {
        let h = try SyncHarness()
        let op = try h.recorder.recordCashHandover(amountText: "5000", currency: "TZS", reference: "R-1", note: nil,
                                                   handedAt: h.clock.wallNow)
        let p = try JSONValue.parse(op.payloadJSON)
        #expect(p["method"] == nil && p["deposit_account_id"] == nil && p["evidence_upload_ids"] == nil)
        #expect(p["reference"]?.stringValue == "R-1")
        let slip = try h.evidence.store(Data(repeating: 1, count: 100), fileExtension: "jpg", contentType: "image/jpeg")
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.serverTooOld)) {
            try h.recorder.recordCashHandover(amountText: "5000", currency: "TZS", reference: nil, note: nil,
                                              handedAt: h.clock.wallNow, evidence: [slip])
        }
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.serverTooOld)) {
            try h.recorder.recordCashHandover(amountText: "5000", currency: "TZS", reference: nil, note: nil,
                                              handedAt: h.clock.wallNow, method: .cashToOffice)
        }
        // With the capability, cash to the office with no photo: method and an empty upload list.
        try AccountabilityTests.supported(h.store, Self.all)
        let cash = try h.recorder.recordCashHandover(amountText: "5000", currency: "TZS", reference: nil, note: nil,
                                                     handedAt: h.clock.wallNow, method: .cashToOffice)
        let c = try JSONValue.parse(cash.payloadJSON)
        #expect(c["method"]?.stringValue == "CASH_TO_OFFICE" && c["evidence_upload_ids"] == .array([]) && c["deposit_account_id"] == nil)
    }

    @Test func remittanceConflictsInPlainWords() {
        for code in ["REMITTANCE_REFERENCE_REQUIRED", "REMITTANCE_EVIDENCE_REQUIRED", "REMITTANCE_ACCOUNT_REQUIRED",
                     "DEPOSIT_ACCOUNT_INACTIVE"] {
            let result = OperationResultDTO(id: UUID(), status: .duplicate, error: .object(["code": .string(code)]))
            #expect(PushOutcomeApplier.classify(result) == .conflict(code: code))
            #expect(FieldAccountabilityTexts.conflictText(code) != nil)
        }
        #expect(FieldAccountabilityTexts.conflictText("DEPOSIT_ACCOUNT_INACTIVE")
            == "The account you chose is no longer in use. Record the handover again with another account.")
        #expect(FieldAccountabilityTexts.conflictText("REMITTANCE_ACCOUNT_MISMATCH")
            == "The account you chose does not match how the money was handed over. Record the handover again.")
    }

    // MARK: - Overdue: held longer than allowed (D3)

    @Test func heldTooLongRowsAndFooter() throws {
        let utc = TimeZone(identifier: "UTC")!
        let json = CapabilitySwitchTests.overdueJSON.replacingOccurrences(
            of: #""policy_version":"c3"}"#,
            with: #""policy_version":"c3","reason":"HELD_TOO_LONG","held_since":"2026-10-20T09:00:00Z","max_holding_days":3}"#)
        let o = try AssetaJSON.decoder().decode(RemittanceOverdueDTO.self, from: Data(json.utf8))
        #expect(o.heldTooLong)
        let rows = RemittanceOverduePresentation.rows(o, flagged: { _ in "24 Oct 2026, 07:05" }, timeZone: utc)
        #expect(rows.map(\.label) == ["Cash held by", "Not remitted", "Reason", "Day", "Held since", "Allowed", "Flagged"])
        #expect(rows[2].value == "Held longer than allowed" && rows[4].value == "20 Oct 2026" && rows[5].value == "3 days")
        #expect(RemittanceOverduePresentation.footer(o, timeZone: utc)
            == "Held since 20 Oct 2026, longer than the allowed 3 days. Remit this cash to the office as soon as you can.")
        let short = try AssetaJSON.decoder().decode(RemittanceOverdueDTO.self, from: Data(json
            .replacingOccurrences(of: #""max_holding_days":3"#, with: #""max_holding_days":null"#).utf8))
        #expect(!RemittanceOverduePresentation.rows(short, flagged: { _ in "x" }).map(\.label).contains("Allowed"))
        #expect(RemittanceOverduePresentation.footer(short) == "Held longer than allowed. Remit this cash to the office as soon as you can.")
        #expect(FieldAccountabilityTexts.days(1) == "1 day")
    }
}
