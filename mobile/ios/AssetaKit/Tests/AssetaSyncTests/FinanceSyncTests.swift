import AssetaCapture
import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

enum FinanceFixtures {
    static let categoryID = UUID(uuidString: "dddddddd-0000-4000-8000-000000000004")!
    static let customerID = UUID(uuidString: "eeeeeeee-0000-4000-8000-000000000005")!
    static let staffID = UUID(uuidString: "ffffffff-0000-4000-8000-000000000006")!

    static func category(active: Bool = true, name: String = "Spare parts") -> [String: Any] {
        ["id": categoryID.lowercased, "code": "PARTS", "name": name, "is_active": active, "sync_revision": 5,
         "version": active ? 1 : 2, "deactivated_at": NSNull(), "deactivation_reason": NSNull()]
    }

    static func customer() -> [String: Any] {
        ["id": customerID.lowercased, "code": "C-1", "name": "Road Builders Ltd", "is_active": true, "version": 1]
    }

    static func custody(outstanding: String, at: Date) -> [String: Any] {
        ["staff_member_id": staffID.lowercased, "currency": "TZS", "outstanding": outstanding,
         "claimed_unverified_handovers": "0", "pending_spending": "0", "as_of": AssetaJSON.formatInstant(at)]
    }

    static func expenseSnapshot(validUntil: Date) -> [String: Any] {
        ["policy_type": "EXPENSE_CAPTURE", "scope_key": "tenant", "version_ids": [UUID().lowercased],
         "version_stamp": "e1", "valid_until": AssetaJSON.formatInstant(validUntil),
         "values": ["receipt_required_above": "50", "gps_required": true, "gps_max_accuracy_m": 100.0,
                    "auto_approve_limit": "200"]]
    }
}

extension SyncHarness {
    func withFinanceData() -> SyncHarness {
        server.mutate {
            $0.expenseCategories = [FinanceFixtures.category()]
            $0.customers = [FinanceFixtures.customer()]
            $0.cashCustody = [FinanceFixtures.custody(outstanding: "500.00", at: $0.serverTime)]
            $0.snapshots.append(FinanceFixtures.expenseSnapshot(validUntil: $0.serverTime.addingTimeInterval(86400)))
        }
        return self
    }

    /// An expense of 120.50 TZS paid from custody with one receipt photo, under the synced policy.
    func recordExpense(receiptBytes: Int = 2300) throws -> ClientOperation {
        guard case let .allowed(snapshot) = try directoryView.expenseGate() else { throw FieldRecorderError.notAllowed("gate") }
        let receipt = try evidence.store(Data((0..<receiptBytes).map { UInt8(($0 * 7) % 251) }), fileExtension: "jpg",
                                         contentType: "image/jpeg")
        var draft = ExpenseDraft()
        draft.categoryID = FinanceFixtures.categoryID
        draft.amountText = "120.50"
        draft.description = "Hydraulic hose"
        draft.currency = directoryView.baseCurrency() ?? "TZS" // the form prefills the tenant currency
        draft.jobID = SyncFixtures.jobID
        draft.jobMachineID = SyncFixtures.machineID
        draft.gps = .fix(latitude: -6.8, longitude: 39.3, accuracyM: 9, capturedAt: clock.wallNow)
        return try recorder.recordExpense(draft, receipts: [receipt], snapshot: snapshot,
                                          baseCurrency: directoryView.baseCurrency(), incurredAt: clock.wallNow)
    }
}

/// Finance operations through the real engine against the fake server.
struct FinanceSyncTests {
    @Test func bootstrapStoresFinanceDataAndDeltasDeactivate() async throws {
        let h = try SyncHarness().withFinanceData()
        let engine = h.engine()
        _ = try await engine.sync()
        #expect(try h.directoryView.expenseCategories().map(\.name) == ["Spare parts"])
        #expect(try h.directoryView.customers().map(\.id) == [FinanceFixtures.customerID])
        #expect(try h.directoryView.custodyBalances().map(\.outstanding.value) == [Decimal(string: "500")!])
        #expect(h.directoryView.baseCurrency() == "TZS")
        guard case let .allowed(snapshot) = try h.directoryView.expenseGate() else { Issue.record("gate"); return }
        #expect(snapshot.policy.receiptRequiredAbove.value == 50)
        // The meter rules are unaffected by the extra snapshot type.
        #expect(try h.directoryView.meterSnapshots().map(\.scopeKey) == ["tenant"])

        h.clock.advance(60)
        h.server.mutate {
            $0.serverTime = $0.serverTime.addingTimeInterval(60)
            $0.cursor = 101
            $0.expenseCategories = [FinanceFixtures.category(active: false)]
            $0.cashCustody = [FinanceFixtures.custody(outstanding: "350.25", at: $0.serverTime)]
        }
        _ = try await engine.sync(force: true)
        #expect(try h.directoryView.expenseCategories().isEmpty)
        #expect(try h.directoryView.custodyBalances().map(\.outstanding.value) == [Decimal(string: "350.25")!])
    }

    @Test func expenseWaitsForReceiptUploadThenAcksWithUploadID() async throws {
        let h = try SyncHarness().withFinanceData()
        let engine = h.engine()
        _ = try await engine.sync()
        let expense = try h.recordExpense()
        #expect(try h.store.outbox.readyToSend(tenantID: SyncFixtures.tenant, now: h.clock.wallNow, limit: 10).isEmpty)
        h.server.mutate { $0.offline = true }
        _ = try await engine.sync(force: true)
        #expect(try h.status(expense.id) == .pending)
        let summary = try h.directoryView.cashSummary()
        #expect(summary.pending.map(\.kind) == [.custodyExpense])
        #expect(summary.lines.first?.unverifiedNet == Decimal(string: "-120.5")!)
        #expect(summary.lines.first?.projected == Decimal(string: "379.5")!)

        h.server.mutate { $0.offline = false }
        let report = try await engine.sync(force: true)
        #expect(report.uploaded == 1)
        #expect(try h.status(expense.id) == .acked)
        let session = try #require(h.server.read { $0.blobs.keys.first })
        let applied = try #require(h.server.read { $0.appliedPayloads[expense.id] })
        #expect(applied["receipt_upload_ids"] as? [String] == [session.lowercased])
        #expect(applied["amount"] as? String == "120.5") // decimal string, never a JSON number
        #expect(applied["client_id"] as? String == expense.entityID.lowercased)
        #expect(applied["job_id"] as? String == SyncFixtures.jobID.lowercased)
        #expect(applied["paid_from"] as? String == "CASH_CUSTODY")
        #expect(try h.directoryView.cashSummary().pending.isEmpty)
    }

    @Test func deferredReceiptIsRetriedThenAcked() async throws {
        let h = try SyncHarness().withFinanceData()
        let engine = h.engine()
        _ = try await engine.sync()
        let expense = try h.recordExpense()
        h.server.mutate { $0.script[expense.id] = ["ATTACHMENT_PENDING"] }
        _ = try await engine.sync(force: true)
        let deferred = try #require(try h.store.outbox.operation(id: expense.id))
        #expect(deferred.status == .pending)
        #expect(deferred.nextAttemptAt == h.clock.wallNow.addingTimeInterval(PushOutcomeApplier.deferDelay))
        _ = try await engine.sync(force: true) // too early: not re-sent
        #expect(h.server.read { $0.pushedBatchSizes.count } == 1)
        h.clock.advance(11)
        _ = try await engine.sync(force: true)
        #expect(try h.status(expense.id) == .acked)
        #expect(h.server.read { $0.applyOrder } == [expense.id])
    }

    @Test func lostResponseReplaysAsDuplicateExactlyOnce() async throws {
        let h = try SyncHarness().withFinanceData()
        let engine = h.engine()
        _ = try await engine.sync()
        let collection = try h.recorder.recordCashCollection(
            customerID: FinanceFixtures.customerID, amountText: "250", currency: "TZS", reference: "RCPT-9", note: nil,
            jobNumber: "J-1001", receivedAt: h.clock.wallNow)
        h.server.mutate { $0.dropNextPushResponse = true }
        _ = try await engine.sync(force: true)
        #expect(try h.status(collection.id) == .pending)
        _ = try await engine.sync(force: true)
        let op = try #require(try h.store.outbox.operation(id: collection.id))
        #expect(op.status == .acked)
        #expect(op.serverResultJSON?.contains("DUPLICATE") == true)
        #expect(h.server.read { $0.applyOrder } == [collection.id])
        let applied = try #require(h.server.read { $0.appliedPayloads[collection.id] })
        #expect(applied["note"] as? String == "Job J-1001")
        #expect(applied["customer_id"] as? String == FinanceFixtures.customerID.lowercased)
    }

    @Test func missingReceiptUploadIsRejectedAndKept() async throws {
        let h = try SyncHarness().withFinanceData()
        let engine = h.engine()
        _ = try await engine.sync()
        let expense = try h.recordExpense()
        // Upload completes, then the server no longer knows the session (e.g. purged).
        let uploader = BlobUploader(api: h.api, attachments: h.store.attachments, evidence: h.evidence)
        for file in try h.store.attachments.pendingUploads(tenantID: SyncFixtures.tenant, now: h.clock.wallNow) {
            _ = try await uploader.upload(file, now: h.clock.wallNow)
        }
        h.server.mutate { $0.blobs = [:] }
        _ = try await engine.sync(force: true)
        let op = try #require(try h.store.outbox.operation(id: expense.id))
        #expect(op.status == .failed)
        #expect(op.errorCode == "RECEIPT_NOT_FOUND")
        let summary = try h.directoryView.cashSummary()
        #expect(summary.needsAttention.map(\.id) == [expense.id])
        #expect(summary.lines.first?.unverifiedNet == 0)
        #expect(try h.directoryView.overview().items.first { $0.id == expense.id }?.title == "Expense")
    }

    @Test func readOnlyTenantQuarantinesThenAppliesAfterReactivation() async throws {
        let h = try SyncHarness().withFinanceData()
        let engine = h.engine()
        _ = try await engine.sync()
        let handover = try h.recorder.recordCashHandover(amountText: "100", currency: "TZS", reference: "DEP-1",
                                                         note: "To office", handedAt: h.clock.wallNow)
        let fuel = try h.recorder.recordFuelEvent(
            type: .issue, litres: "40.5", unitPrice: "3200", currency: "TZS", machineID: SyncFixtures.machineID, jobID: nil,
            meterReading: "1500.5", supplier: nil, note: nil, occurredAt: h.clock.wallNow)
        h.server.mutate { $0.readOnly = true }
        _ = try await engine.sync(force: true)
        #expect(try h.status(handover.id) == .quarantined)
        #expect(try h.status(fuel.id) == .quarantined)
        #expect(try h.directoryView.cashSummary().pending.map(\.status) == [.quarantined])
        h.server.mutate { $0.readOnly = false }
        h.clock.advance(PushOutcomeApplier.quarantineRetry + 1)
        _ = try await engine.sync(force: true)
        #expect(try h.status(handover.id) == .acked)
        #expect(try h.status(fuel.id) == .acked)
        let applied = try #require(h.server.read { $0.appliedPayloads[fuel.id] })
        #expect(applied["litres"] as? String == "40.5")
        #expect(applied["unit_price"] as? String == "3200")
        #expect(applied["meter_reading"] as? String == "1500.5")
        #expect(applied["event_type"] as? String == "ISSUE")
    }
}
