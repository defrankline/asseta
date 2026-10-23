import AssetaCapture
import AssetaModel
import AssetaNetwork
import AssetaSecurity
import AssetaStore
import AssetaSync
import AssetaTestSupport
import Foundation
import Testing

/// Gate 5 live E2E (same opt-in suite): an expense with a receipt photo, a cash collection and a cash handover are
/// recorded while the backend is unreachable, then synced to ACKED and verified through the tenant API.
extension AssetaSyncLiveTests {
    @Test func offlineExpenseCollectionAndHandoverReachAckedAgainstTheLiveBackend() async throws {
        let fixture = try LiveFixture.load()
        let categoryID = try #require(fixture.expenseCategoryID, "fixture has no finance data: update field_e2e_setup.py")
        let customerID = try #require(fixture.customerID)
        let float = try #require(fixture.cashFloat.flatMap { Decimal(string: $0) })

        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = try LocalStore.open(at: directory.appendingPathComponent("db.sqlite"),
                                        keyProvider: DatabaseKeyProvider(store: InMemorySecretStore()))
        let evidence = EvidenceStore(directory: directory.appendingPathComponent("evidence"))
        let deviceID = try DeviceIdentity.loadOrCreate(store: InMemorySecretStore())
        func engine(_ base: URL) -> (SyncEngine, APIClient) {
            let client = APIClient(baseURL: base, transport: URLSessionTransport(),
                                   tokens: StaticTokenProvider(token: fixture.accessToken), tenantID: fixture.tenantID)
            return (SyncEngine(store: store, evidence: evidence, api: SyncAPI(client: client, deviceID: deviceID),
                               tenantID: fixture.tenantID, configuration: SyncConfiguration(appVersion: "live-e2e (ios)")),
                    client)
        }
        let (live, client) = engine(fixture.apiBase)
        let fieldDirectory = FieldDirectory(store: store, tenantID: fixture.tenantID)
        let recorder = FieldRecorder(store: store, tenantID: fixture.tenantID, deviceID: deviceID)

        // 1. Bootstrap brings categories, the job's customer, the custody float and the expense rules.
        let first = try await live.sync(force: true)
        #expect(first.outcome == .synced, "first sync: \(first.outcome)")
        #expect(try fieldDirectory.expenseCategories().map(\.id).contains(categoryID))
        #expect(try fieldDirectory.customers().map(\.id).contains(customerID))
        #expect(try fieldDirectory.custodyBalances().first?.outstanding.value == float)
        guard case let .allowed(snapshot) = try fieldDirectory.expenseGate() else {
            Issue.record("expense blocked by the synced policy gate")
            return
        }

        // 2. Offline: record all three; a sync attempt against an unreachable host leaves them pending.
        let receipt = try evidence.store(Self.jpeg(bytes: 120_000), fileExtension: "jpg", contentType: "image/jpeg")
        var draft = ExpenseDraft()
        draft.categoryID = categoryID
        draft.amountText = "120.50"
        draft.description = "Live E2E hydraulic hose"
        draft.currency = "TZS"
        draft.supplier = "Hose Centre"
        draft.jobID = fixture.jobID
        draft.jobMachineID = fixture.machineID
        draft.paidFrom = .cashCustody
        draft.gps = .fix(latitude: -6.8, longitude: 39.28, accuracyM: 8, capturedAt: Date().addingTimeInterval(-2))
        let base = fieldDirectory.baseCurrency()
        let assessment = ExpenseRules.assess({ var d = draft; d.receiptCount = 1; return d }(), policy: snapshot.policy,
                                             baseCurrency: base)
        #expect(assessment.canSave, "\(assessment.issues)")
        let expense = try recorder.recordExpense(draft, receipts: [receipt], snapshot: snapshot, baseCurrency: base,
                                                 incurredAt: Date())
        let collection = try recorder.recordCashCollection(
            customerID: customerID, amountText: "250000", currency: "TZS", reference: "RCPT-\(UUID().uuidString.prefix(8))",
            note: nil, jobNumber: fieldDirectory.job(id: fixture.jobID)?.job.jobNumber, receivedAt: Date())
        let handover = try recorder.recordCashHandover(amountText: "100000", currency: "TZS", reference: "DEP-E2E",
                                                       note: "Live E2E", handedAt: Date())
        let (offline, _) = engine(URL(string: "http://127.0.0.1:9")!)
        let failed = try await offline.sync(force: true)
        guard case .offline = failed.outcome else { Issue.record("expected offline, got \(failed.outcome)"); return }
        for op in [expense, collection, handover] { #expect(try store.outbox.operation(id: op.id)?.status == .pending) }
        let pending = try fieldDirectory.cashSummary()
        #expect(pending.pending.count == 3)
        #expect(pending.lines.first?.unverifiedNet == Decimal(string: "250000")! - Decimal(string: "100000")! - Decimal(string: "120.5")!)

        // 3. Back online: the receipt uploads first, then all three are ACKED.
        let online = try await live.sync(force: true)
        #expect(online.outcome == .synced, "online sync: \(online.outcome)")
        #expect(online.uploaded == 1)
        for op in [expense, collection, handover] {
            let stored = try #require(try store.outbox.operation(id: op.id))
            #expect(stored.status == .acked, "\(op.opType) \(stored.status) \(stored.errorCode ?? "") \(stored.lastError ?? "")")
        }
        let receiptFile = try #require(try store.attachments.attachments(tenantID: fixture.tenantID, statuses: [.complete]).first)

        // 4. Replaying the expense op id is a DUPLICATE with no second expense.
        let acked = try #require(try store.outbox.operation(id: expense.id))
        let replay = try await SyncAPI(client: client, deviceID: deviceID).push(PushIn(deviceNow: Date(), operations: [
            OperationIn(id: acked.id, opType: acked.opType, createdAtDevice: acked.createdAtDevice,
                        dependsOn: acked.dependencies, payload: try JSONValue.parse(acked.payloadJSON)),
        ]))
        #expect(replay.results.map(\.status) == [.duplicate])

        // 5. Server side: exactly one expense (with the uploaded receipt), and custody moved as expected.
        let page = try await client.send(APIRequest<JSONValue>.get(
            "/api/v1/tenant/expenses", query: [URLQueryItem(name: "job_id", value: fixture.jobID.lowercased)]))
        var expenses: [JSONValue] = []
        if case let .array(items)? = page["items"] { expenses = items }
        #expect(expenses.count == 1)
        let row = try #require(expenses.first)
        #expect(row["client_id"]?.stringValue == expense.entityID.lowercased)
        #expect(row["amount"]?.stringValue.flatMap { Decimal(string: $0) } == Decimal(string: "120.5"))
        #expect(row["paid_from"]?.stringValue == "CASH_CUSTODY")
        #expect(row["status"]?.stringValue == "PENDING_APPROVAL") // default policy: every expense needs approval
        #expect(row["receipt_attachment_ids"] == .array([.string(try #require(receiptFile.attachmentID).lowercased)]))
        #expect(row["gps_status"]?.stringValue == "FIX")
        let custody = try await client.send(APIRequest<[CashCustodyBalanceDTO]>.get("/api/v1/tenant/cash/custody/me"))
        let balance = try #require(custody.first)
        #expect(balance.outstanding.value == float + Decimal(250000)) // collection in; claimed handover not yet out
        #expect(balance.claimedUnverifiedHandovers.value == Decimal(100000))
        #expect(balance.pendingSpending.value == Decimal(string: "120.5"))
        // The device's synced copy matches, and nothing is left unverified locally.
        #expect(try fieldDirectory.custodyBalances().first?.outstanding.value == balance.outstanding.value)
        #expect(try fieldDirectory.cashSummary().pending.isEmpty)
    }
}
