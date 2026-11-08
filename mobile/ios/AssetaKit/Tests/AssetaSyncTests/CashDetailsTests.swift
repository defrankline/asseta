import AssetaCapture
import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// DEC-032 Phase 3 on the field side: the collection's "Pays for", the partial remittance reason, hours transfer evidence,
/// the new conflicts and the module switches. Strings doc "DEC-032 Phase 3 — independence and evidence".
struct CashDetailsTests {
    typealias T = FieldAccountabilityTexts
    static let all = RemittanceTests.all + [SyncCapability.cashDetailsV2]
    static let customer = UUID(uuidString: "c1000000-0000-4000-8000-000000000001")!
    static let other = UUID(uuidString: "c1000000-0000-4000-8000-000000000002")!

    static func cash(remitFull: Bool = true, linkRequired: Bool = false) -> CashCustodyPolicyValues {
        CashCustodyPolicyValues(recordersMayRecordForOthers: true, transferAckRequired: false, recorderReceiverCountsAsAck: false,
                                floatAckRequired: false, remitFullBalance: remitFull, retentionAllowed: true,
                                remittanceAccountRequired: true, collectionLinkRequired: linkRequired)
    }

    static func access(caps: [String] = all, cash: CashCustodyPolicyValues = cash(), disabled: Set<String> = []) -> FieldAccess {
        FieldAccess(capabilities: Set(caps), permissions: AccountabilityTests.permissions, cash: cash,
                    hours: AccountabilityTests.hoursOn, disabledCapabilities: disabled)
    }

    static func purchase(_ number: String, customer: UUID, status: String = "ACTIVE", clientID: UUID? = nil) throws -> HoursPurchaseDTO {
        let json = """
        {"id":"\(UUID().uuidString.lowercased())","purchase_number":"\(number)","client_id":\(clientID.map { "\"\($0.uuidString.lowercased())\"" } ?? "null"),
         "customer_id":"\(customer.uuidString.lowercased())","machine_id":"\(UUID().uuidString.lowercased())","hours":"10","currency":"TZS","amount":"1000",
         "status":"\(status)","created_at":"2026-11-01T08:00:00Z",
         "totals":{"purchased":"10","activated":"10","consumed":"2","remaining":"8","transferred":"0","expired":"0","awaiting_activation":"0","provisional":"0"}}
        """
        return try AssetaJSON.decoder().decode(HoursPurchaseDTO.self, from: Data(json.utf8))
    }

    /// A sale waiting in this phone's outbox (the recorder's own checks are covered by `AccountabilityTests`).
    static func saleOp(customer: UUID, h: SyncHarness) throws -> ClientOperation {
        let clientID = UUID()
        let json = #"{"client_id":"\#(clientID.lowercased)","machine_id":"\#(SyncFixtures.machineID.lowercased)","customer_id":"\#(customer.lowercased)","hours":"5","evidence_upload_ids":[]}"#
        return try h.store.outbox.enqueue(NewClientOperation(
            tenantID: SyncFixtures.tenant, opType: "HOURS_PURCHASE", entityType: "hours_purchase", entityID: clientID, payloadJSON: json,
            dependsOn: [], attachments: [], createdAtDevice: h.clock.wallNow, owner: nil))
    }

    // MARK: - Access

    @Test func everythingNewNeedsTheCapability() {
        let old = Self.access(caps: RemittanceTests.all, cash: Self.cash(linkRequired: true))
        #expect(!old.cashDetails && !old.collectionLinkRequired)
        #expect(PartialRemittance.need(access: old, amountText: "1", estimate: 10, otherHolder: false) == .hidden)
        let on = Self.access(cash: Self.cash(linkRequired: true))
        #expect(on.cashDetails && on.collectionLinkRequired)
    }

    @Test func depositAccountsOffDropsTheAccountRequirementOnly() {
        #expect(Self.access().remittanceRequirements.account)
        let off = Self.access(disabled: [TenantCapability.depositAccounts])
        #expect(!off.depositAccountsOn && !off.remittanceRequirements.account && off.remittanceDetails)
    }

    @Test func policiesDecodeTheNewKeysTolerantly() throws {
        let base = #"{"recorders_may_record_for_others":true,"transfer_ack_required":false,"recorder_receiver_counts_as_ack":false,"float_ack_required":false,"remit_full_balance":false,"retention_allowed":true"#
        #expect(try !AssetaJSON.decoder().decode(CashCustodyPolicyValues.self, from: Data((base + "}").utf8)).collectionLinkRequired)
        #expect(try AssetaJSON.decoder().decode(CashCustodyPolicyValues.self, from: Data((base + #","collection_link_required":true}"#).utf8)).collectionLinkRequired)
        let hours = #"{"enabled":true,"walk_in_allowed":false,"transfer_requires_approval":true,"reason_code_required":false"#
        #expect(try !AssetaJSON.decoder().decode(CustomerHoursPolicyValues.self, from: Data((hours + "}").utf8)).transferEvidenceRequired)
        #expect(try AssetaJSON.decoder().decode(CustomerHoursPolicyValues.self, from: Data((hours + #","transfer_evidence_required":true}"#).utf8)).transferEvidenceRequired)
        #expect(throws: (any Error).self) { try AssetaJSON.decoder().decode(CustomerHoursPolicyValues.self, from: Data(#"{"enabled":true}"#.utf8)) }
    }

    // MARK: - Collection link

    @Test func picksTheCustomersOpenPurchasesThenThisPhonesUnsyncedSales() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.all)
        let sale = try Self.saleOp(customer: Self.customer, h: h)
        _ = try Self.saleOp(customer: Self.other, h: h)
        let known = UUID()
        let purchases = [try Self.purchase("P-1", customer: Self.customer), try Self.purchase("P-2", customer: Self.other),
                         try Self.purchase("P-3", customer: Self.customer, status: "CANCELLED"),
                         try Self.purchase("P-4", customer: Self.customer, clientID: known)]
        let ops = try h.store.outbox.operations(tenantID: SyncFixtures.tenant, statuses: [.pending])
        let rows = CollectionLinks.options(purchases: purchases, unsynced: ops, customerID: Self.customer)
        #expect(rows.map(\.title) == ["P-1", "P-4", "Not synced yet · 5 h"])
        #expect(rows.map(\.subtitle) == ["8 h left", "8 h left", nil])
        #expect(rows.last?.operationID == sale.id && rows.first?.operationID == nil && rows.last?.id == sale.entityID)
        #expect(CollectionLinks.options(purchases: purchases, unsynced: ops, customerID: nil).isEmpty)
    }

    @Test func recordsTheLinkAndWaitsForAnUnsyncedSale() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.all)
        let sale = try Self.saleOp(customer: Self.customer, h: h)
        let op = try h.recorder.recordCashCollection(customerID: Self.customer, amountText: "500", currency: "TZS", reference: nil, note: nil,
                                                     receivedAt: h.clock.wallNow, purchaseID: sale.entityID, purchaseOperationID: sale.id)
        #expect(try JSONValue.parse(op.payloadJSON)["purchase_id"]?.stringValue == sale.entityID.lowercased)
        #expect(op.dependencies == [sale.id])
        let plain = try h.recorder.recordCashCollection(customerID: Self.customer, amountText: "1", currency: "TZS", reference: nil, note: nil,
                                                        receivedAt: h.clock.wallNow)
        #expect(try JSONValue.parse(plain.payloadJSON)["purchase_id"] == nil && plain.dependencies.isEmpty)
    }

    @Test func aRefusedSaleCannotBeLinkedAndAnAcceptedOneNeedsNoWait() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.all)
        let refused = try Self.saleOp(customer: Self.customer, h: h)
        try h.store.outbox.markSent(id: refused.id)
        try h.store.outbox.markConflict(id: refused.id, code: "X", message: "x", resultJSON: "{}")
        #expect(throws: FieldRecorderError.notAllowed(T.collectionPurchaseGone)) {
            try h.recorder.recordCashCollection(customerID: Self.customer, amountText: "1", currency: "TZS", reference: nil, note: nil,
                                                receivedAt: h.clock.wallNow, purchaseID: refused.entityID, purchaseOperationID: refused.id)
        }
    }

    @Test func aRemittanceDecisionOpensTheHandover() {
        let id = UUID()
        #expect(InboxLink.from(record: RecordRef(kind: .cashRemittance, id: id)) == .handover(id))
    }

    @Test func aRequiredLinkIsEnforcedAndAnOldServerGetsNoLink() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.all)
        #expect(throws: FieldRecorderError.invalid(T.collectionErrLink)) {
            try h.recorder.recordCashCollection(customerID: Self.customer, amountText: "1", currency: "TZS", reference: nil, note: nil,
                                                receivedAt: h.clock.wallNow, linkRequired: true)
        }
        let old = try SyncHarness()
        try AccountabilityTests.supported(old.store, RemittanceTests.all)
        #expect(throws: FieldRecorderError.notAllowed(T.serverTooOld)) {
            try old.recorder.recordCashCollection(customerID: Self.customer, amountText: "1", currency: "TZS", reference: nil, note: nil,
                                                  receivedAt: old.clock.wallNow, purchaseID: UUID())
        }
    }

    // MARK: - Partial reason

    @Test func theReasonIsRequiredOnlyBelowMyOwnEstimate() {
        let a = Self.access()
        #expect(PartialRemittance.need(access: a, amountText: "100", estimate: 150, otherHolder: false) == .required(balance: 150))
        #expect(PartialRemittance.need(access: a, amountText: "150", estimate: 150, otherHolder: false) == .hidden)
        #expect(PartialRemittance.need(access: a, amountText: "200", estimate: 150, otherHolder: false) == .hidden)
        #expect(PartialRemittance.need(access: a, amountText: "", estimate: 150, otherHolder: false) == .hidden)
        #expect(PartialRemittance.need(access: a, amountText: "100", estimate: nil, otherHolder: false) == .hidden)
        #expect(PartialRemittance.need(access: a, amountText: "100", estimate: nil, otherHolder: true) == .optional)
        let off = Self.access(cash: Self.cash(remitFull: false))
        #expect(PartialRemittance.need(access: off, amountText: "100", estimate: 150, otherHolder: false) == .hidden)
        #expect(PartialRemittance.issues(.required(balance: 1), reason: " ab ") == [T.handoverPartialError])
        #expect(PartialRemittance.issues(.required(balance: 1), reason: "abc").isEmpty)
        #expect(PartialRemittance.issues(.optional, reason: "").isEmpty && PartialRemittance.issues(.hidden, reason: "").isEmpty)
        #expect(PartialRemittance.issues(.optional, reason: "ab") == [T.handoverPartialError])
        let custodyOff = Self.access(disabled: [TenantCapability.cashCustody])
        #expect(!custodyOff.partialReason
            && PartialRemittance.need(access: custodyOff, amountText: "100", estimate: 150, otherHolder: false) == .hidden)
    }

    @Test func theEstimateMatchesTheCurrency() {
        let summary = CashSummary(lines: [CashLine(currency: "TZS", synced: nil, pendingCollections: 40)],
                                  pending: [], needsAttention: [], baseCurrency: "USD")
        #expect(PartialRemittance.estimate(summary, currency: " tzs") == 40)
        #expect(PartialRemittance.estimate(summary, currency: "EUR") == nil && PartialRemittance.estimate(nil, currency: "TZS") == nil)
    }

    @Test func handoverCarriesTheReasonOnlyWhenTheServerTakesIt() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.all)
        let reason = UUID()
        let op = try h.recorder.recordCashHandover(amountText: "5", currency: "TZS", reference: nil, note: nil, handedAt: h.clock.wallNow,
                                                   partialReason: "  Kept for fuel ", partialReasonID: reason)
        let p = try JSONValue.parse(op.payloadJSON)
        #expect(p["partial_reason"]?.stringValue == "Kept for fuel" && p["partial_reason_id"]?.stringValue == reason.lowercased)
        let plain = try JSONValue.parse(try h.recorder.recordCashHandover(amountText: "5", currency: "TZS", reference: nil, note: nil,
                                                                          handedAt: h.clock.wallNow).payloadJSON)
        #expect(plain["partial_reason"] == nil && plain["partial_reason_id"] == nil)
        #expect(throws: FieldRecorderError.invalid(T.handoverPartialError)) {
            try h.recorder.recordCashHandover(amountText: "5", currency: "TZS", reference: nil, note: nil, handedAt: h.clock.wallNow,
                                              partialReasonRequired: true)
        }
        #expect(throws: FieldRecorderError.invalid(T.handoverPartialError)) {
            try h.recorder.recordCashHandover(amountText: "5", currency: "TZS", reference: nil, note: nil, handedAt: h.clock.wallNow, partialReason: "ab")
        }
        let old = try SyncHarness()
        try AccountabilityTests.supported(old.store, RemittanceTests.all)
        #expect(throws: FieldRecorderError.notAllowed(T.serverTooOld)) {
            try old.recorder.recordCashHandover(amountText: "5", currency: "TZS", reference: nil, note: nil, handedAt: old.clock.wallNow,
                                                partialReason: "Kept for fuel")
        }
    }

    // MARK: - Transfer evidence

    private func request(_ h: SyncHarness, evidence: [StoredEvidence] = [], required: Bool = false) throws -> ClientOperation {
        try h.recorder.requestHoursTransfer(purchaseID: UUID(), fromMachineID: UUID(), toMachineID: UUID(), hoursText: "2", remaining: 8,
                                            reason: "Machine moved", reasonCodeID: nil, reasonCodeRequired: false, evidence: evidence,
                                            evidenceRequired: required, at: h.clock.wallNow)
    }

    @Test func transferPhotosUploadAsAdjustmentEvidenceAndHoldTheOp() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.all)
        let photo = try h.evidence.store(Data(repeating: 3, count: 200), fileExtension: "jpg", contentType: "image/jpeg")
        let op = try request(h, evidence: [photo], required: true)
        #expect(try JSONValue.parse(op.payloadJSON)["evidence_upload_ids"] == .array([]))
        #expect(try h.store.attachments.attachments(operationID: op.id).first?.purpose == "ADJUSTMENT_EVIDENCE")
        #expect(try h.store.outbox.readyToSend(tenantID: SyncFixtures.tenant, now: h.clock.wallNow, limit: 10).isEmpty)
        #expect(try h.directoryView.overview().items.first { $0.id == op.id }?.waitingFor == T.outboxWaitingPhotos)
    }

    @Test func aRequiredPhotoIsEnforcedAndNoPhotoKeepsTodaysPayload() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.all)
        #expect(throws: FieldRecorderError.invalid(T.transferErrEvidence)) { try request(h, required: true) }
        #expect(try JSONValue.parse(try request(h).payloadJSON)["evidence_upload_ids"] == nil)
        let old = try SyncHarness()
        try AccountabilityTests.supported(old.store, AccountabilityTests.all)
        let photo = try old.evidence.store(Data(repeating: 4, count: 200), fileExtension: "jpg", contentType: "image/jpeg")
        #expect(throws: (any Error).self) { try request(old, evidence: [photo]) }
    }

    // MARK: - Conflicts and numbers

    @Test func newConflictsAreConflictsInPlainWords() {
        let expected = [
            "COLLECTION_LINK_REQUIRED": "Your company requires every collection to name its purchase or invoice. Record it again and choose one.",
            "PARTIAL_REMITTANCE_REASON_REQUIRED": "Part of this cash is still with you and your company requires the reason. Record the handover again with the reason.",
            "EVIDENCE_REQUIRED": "Your company requires evidence for this. Record it again with a photo.",
            "PURCHASE_NOT_FOUND": "The purchase you chose is no longer on record. Record it again and choose another.",
            "PURCHASE_CANCELLED": "The purchase you chose is cancelled. Record it again and choose another.",
            "OVER_ALLOCATION": "This is more than the purchase still owes. Record it again with the right amount.",
            "ALLOCATION_MISMATCH": "The purchase you chose is for another customer or currency. Record it again and choose another.",
        ]
        for (code, text) in expected {
            let result = OperationResultDTO(id: UUID(), status: .duplicate, error: .object(["code": .string(code)]))
            #expect(PushOutcomeApplier.classify(result) == .conflict(code: code))
            #expect(T.conflictText(code) == text)
        }
    }

    @Test func blobPurposeIsOnTheWire() {
        #expect(BlobPurpose.adjustmentEvidence.rawValue == "ADJUSTMENT_EVIDENCE")
        #expect(SyncCapability.cashDetailsV2 == "CASH_DETAILS_V2")
    }
}
