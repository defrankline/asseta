import AssetaCapture
import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// Offline enforcement of the `EXPENSE_CAPTURE` snapshot and the other finance form rules.
struct FinanceRulesTests {
    static let policy = ExpenseCapturePolicy(receiptRequiredAbove: 50, gpsRequired: true, gpsMaxAccuracyM: 100,
                                             autoApproveLimit: 200)
    static let fix = GpsPayload.fix(latitude: -6.8, longitude: 39.3, accuracyM: 12, capturedAt: Date())

    static func draft(amount: String, receipts: Int = 0, gps: GpsPayload? = fix, currency: String = "") -> ExpenseDraft {
        var draft = ExpenseDraft()
        draft.categoryID = UUID()
        draft.amountText = amount
        draft.description = "Hydraulic hose"
        draft.receiptCount = receipts
        draft.gps = gps
        draft.currency = currency
        return draft
    }

    @Test func receiptRequiredOnlyAboveThreshold() {
        let atThreshold = ExpenseRules.assess(Self.draft(amount: "50"), policy: Self.policy, baseCurrency: "TZS")
        #expect(atThreshold.canSave)
        #expect(!atThreshold.receiptRequired)
        let above = ExpenseRules.assess(Self.draft(amount: "50.01"), policy: Self.policy, baseCurrency: "TZS")
        #expect(above.receiptRequired)
        #expect(above.issues == [.receiptRequired(reason: "above 50 TZS")])
        #expect(ExpenseRules.assess(Self.draft(amount: "50.01", receipts: 1), policy: Self.policy, baseCurrency: "TZS").canSave)
        let zero = ExpenseCapturePolicy(receiptRequiredAbove: 0, gpsRequired: false, gpsMaxAccuracyM: 100, autoApproveLimit: 0)
        #expect(ExpenseRules.assess(Self.draft(amount: "1"), policy: zero, baseCurrency: nil).issues
            == [.receiptRequired(reason: "for every expense")])
    }

    @Test func gpsRequiredAndAccuracyEnforced() {
        #expect(ExpenseRules.assess(Self.draft(amount: "10", gps: nil), policy: Self.policy, baseCurrency: nil).issues == [.gpsPending])
        #expect(ExpenseRules.assess(Self.draft(amount: "10", gps: .failed(.timeout)), policy: Self.policy, baseCurrency: nil).issues
            == [.gpsRequired(status: .timeout)])
        let coarse = GpsPayload.fix(latitude: 1, longitude: 1, accuracyM: 150, capturedAt: Date())
        #expect(ExpenseRules.assess(Self.draft(amount: "10", gps: coarse), policy: Self.policy, baseCurrency: nil).issues
            == [.gpsTooInaccurate(accuracyM: 150, maxM: 100)])
        let lenient = ExpenseCapturePolicy(receiptRequiredAbove: 50, gpsRequired: false, gpsMaxAccuracyM: 100, autoApproveLimit: 0)
        #expect(ExpenseRules.assess(Self.draft(amount: "10", gps: .failed(.permissionDenied)), policy: lenient, baseCurrency: nil).canSave)
    }

    @Test func approvalNeededAboveAutoApproveLimitOrForeignCurrency() {
        let small = ExpenseRules.assess(Self.draft(amount: "200", receipts: 1), policy: Self.policy, baseCurrency: "TZS")
        #expect(!small.needsApproval)
        #expect(ExpenseRules.approvalNote(small, policy: Self.policy, baseCurrency: "TZS") == nil)
        let big = ExpenseRules.assess(Self.draft(amount: "200.01", receipts: 1), policy: Self.policy, baseCurrency: "TZS")
        #expect(big.needsApproval)
        #expect(ExpenseRules.approvalNote(big, policy: Self.policy, baseCurrency: "TZS")?.contains("auto-approval limit of 200 TZS") == true)
        let foreign = ExpenseRules.assess(Self.draft(amount: "5", currency: "usd"), policy: Self.policy, baseCurrency: "TZS")
        #expect(foreign.isForeignCurrency && foreign.needsApproval && foreign.receiptRequired)
        #expect(foreign.currency == "USD")
        #expect(ExpenseRules.assess(Self.draft(amount: "5", currency: "TZS"), policy: Self.policy, baseCurrency: "TZS").canSave)
        #expect(ExpenseRules.assess(Self.draft(amount: "5", currency: "US"), policy: Self.policy, baseCurrency: "TZS").issues
            .contains(.currencyInvalid))
    }

    @Test func moneyIsParsedStrictlyAsDecimal() {
        #expect(DecimalInput.parse("1250.50", maxFractionDigits: 2) == .success(Decimal(string: "1250.5")!))
        #expect(DecimalInput.parse("0,1", maxFractionDigits: 2) == .success(Decimal(string: "0.1")!))
        #expect(DecimalInput.parse("1.005", maxFractionDigits: 2) == .failure(.tooManyDecimals(2)))
        #expect(DecimalInput.parse("1e3", maxFractionDigits: 2) == .failure(.notANumber))
        #expect(DecimalInput.parse("1,000.00", maxFractionDigits: 2) == .failure(.notANumber))
        #expect(DecimalInput.parse("-4", maxFractionDigits: 2) == .failure(.negative))
        #expect(DecimalInput.parse("0", maxFractionDigits: 2) == .failure(.notPositive))
        #expect(DecimalInput.parse("0", maxFractionDigits: 2, allowZero: true) == .success(0))
        // 0.1 + 0.2 is exact in Decimal (it would not be in Double).
        let sum = (try? DecimalInput.parse("0.1", maxFractionDigits: 2).get())! + (try? DecimalInput.parse("0.2", maxFractionDigits: 2).get())!
        #expect(DecimalInput.format(sum) == "0.3")
    }

    @Test func fuelShapeRules() {
        #expect(FinanceRules.fuelIssues(type: .issue, litres: "40", unitPrice: "3.25", meterReading: "", machineID: nil, jobID: nil)
            == ["Choose the machine or job the fuel went to."])
        #expect(FinanceRules.fuelIssues(type: .purchase, litres: "40", unitPrice: "", meterReading: "", machineID: nil, jobID: nil)
            == ["Enter the unit price."])
        #expect(FinanceRules.fuelIssues(type: .usage, litres: "12.345", unitPrice: "", meterReading: "1500.25",
                                        machineID: UUID(), jobID: nil).isEmpty)
        #expect(FinanceRules.fuelIssues(type: .usage, litres: "1.2345", unitPrice: "", meterReading: "", machineID: UUID(), jobID: nil)
            == ["Litres may have at most 3 decimals."])
    }

    @Test func gateBlocksWithoutFreshRules() {
        let now = Date(timeIntervalSince1970: 1_800_000_000)
        let snapshot = ExpensePolicySnapshot(versionIDs: [], versionStamp: "e1", policy: Self.policy, validUntil: now)
        #expect(ExpenseGate.evaluate(snapshot: nil, offlineGrantUntil: nil, now: now) == .blocked(.noSnapshot))
        #expect(ExpenseGate.evaluate(snapshot: snapshot, offlineGrantUntil: nil, now: now) == .allowed(snapshot))
        #expect(ExpenseGate.evaluate(snapshot: snapshot, offlineGrantUntil: nil, now: now.addingTimeInterval(1))
            == .blocked(.snapshotExpired(validUntil: now)))
        #expect(ExpenseGate.evaluate(snapshot: snapshot, offlineGrantUntil: now.addingTimeInterval(-1), now: now)
            == .blocked(.offlineGrantExpired(until: now.addingTimeInterval(-1))))
        // A threshold sent as a JSON number (not a decimal string) fails closed.
        let stored = StoredPolicySnapshot(policyType: "EXPENSE_CAPTURE", scopeKey: "tenant", versionIDsJSON: "[]", versionStamp: "x",
                                          valuesJSON: #"{"receipt_required_above":50,"gps_required":true,"gps_max_accuracy_m":100,"auto_approve_limit":"0"}"#,
                                          validUntil: now, receivedAt: now)
        #expect(ExpensePolicySnapshot(stored) == nil)
    }

    @Test func recorderRefusesPolicyViolationsAndWritesNothing() throws {
        let h = try SyncHarness()
        let snapshot = ExpensePolicySnapshot(versionIDs: [], versionStamp: "e1", policy: Self.policy,
                                             validUntil: Date().addingTimeInterval(3600))
        #expect(throws: FieldRecorderError.invalid("A receipt photo is required above 50 TZS.")) {
            try h.recorder.recordExpense(Self.draft(amount: "75"), receipts: [], snapshot: snapshot, baseCurrency: "TZS",
                                         incurredAt: Date())
        }
        #expect(throws: FieldRecorderError.self) {
            try h.recorder.recordCashCollection(customerID: UUID(), amountText: "12.345", currency: "", reference: nil,
                                                note: nil, receivedAt: Date())
        }
        #expect(throws: FieldRecorderError.self) {
            try h.recorder.recordCashHandover(amountText: "10", currency: "tz", reference: nil, note: nil, handedAt: Date())
        }
        #expect(try h.store.outbox.statusCounts(tenantID: SyncFixtures.tenant).values.reduce(0, +) == 0)
    }
}
