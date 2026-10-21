#if os(iOS)
import AssetaCapture
import AssetaModel
import AssetaSync
import Foundation
import Observation

/// State of one expense being recorded. The client id is generated once, here, so a retried save
/// or a re-sent operation is the same expense on the server. The GPS attempt starts when the screen
/// opens; receipt photos go straight into the encrypted evidence store (original JPEG bytes).
@MainActor
@Observable
final class ExpenseFormModel {
    enum GpsState: Equatable { case locating, done(GpsPayload) }

    let snapshot: ExpensePolicySnapshot
    let baseCurrency: String?
    let clientID = UUID()
    var draft = ExpenseDraft()
    private(set) var receipts: [StoredEvidence] = []
    private(set) var receiptImages: [Data] = []
    private(set) var gpsState: GpsState = .locating
    private(set) var incurredAt = Date()
    var errorMessage: String?

    init(snapshot: ExpensePolicySnapshot, baseCurrency: String?) {
        self.snapshot = snapshot
        self.baseCurrency = baseCurrency
    }

    var policy: ExpenseCapturePolicy { snapshot.policy }

    var assessment: ExpenseAssessment {
        var checked = draft
        checked.receiptCount = receipts.count
        return ExpenseRules.assess(checked, policy: policy, baseCurrency: baseCurrency)
    }

    var approvalNote: String? { ExpenseRules.approvalNote(assessment, policy: policy, baseCurrency: baseCurrency) }

    /// Plain-language summary of the owner's rules, shown on the form.
    var rulesSummary: String {
        let currency = baseCurrency.map { " \($0)" } ?? ""
        let threshold = policy.receiptRequiredAbove.value
        let receipt = threshold == 0 ? "Receipt photo required for every expense."
            : "Receipt photo required above \(DecimalInput.format(threshold))\(currency)."
        let gps = policy.gpsRequired ? " GPS fix within ±\(Int(policy.gpsMaxAccuracyM)) m required." : ""
        let limit = policy.autoApproveLimit.value
        let approval = limit == 0 ? " Every expense needs a manager's approval."
            : " Up to \(DecimalInput.format(limit))\(currency) is approved automatically."
        return receipt + gps + approval + " (Rules \(snapshot.versionStamp).)"
    }

    func selectJob(_ id: UUID?, model: FieldModel) {
        draft.jobID = id
        let machine = id.flatMap { model.job($0)?.job.machineID }
        draft.jobMachineID = machine
        if let machine { draft.machineID = machine }
    }

    /// A fresh fix for every expense (never a cached location).
    func locate(using locator: LocationCapturer) async {
        gpsState = .locating
        draft.gps = nil
        let result = await locator.captureFix(timeout: 20)
        draft.gps = result
        gpsState = .done(result)
    }

    func receiptTaken(_ data: Data, model: FieldModel) {
        guard receipts.count < FieldRecorder.maxReceipts else {
            errorMessage = "At most \(FieldRecorder.maxReceipts) receipt photos per expense."
            return
        }
        do {
            receipts.append(try model.storeEvidence(data, fileExtension: "jpg", contentType: "image/jpeg"))
            receiptImages.append(data)
        } catch {
            errorMessage = "The receipt photo could not be saved: \(error)"
        }
    }

    func removeReceipt(at index: Int, model: FieldModel) {
        guard receipts.indices.contains(index) else { return }
        model.discardEvidence(receipts.remove(at: index))
        receiptImages.remove(at: index)
    }

    func save(model: FieldModel) -> Bool {
        guard assessment.canSave else { return false }
        if case let .blocked(reason) = model.expenseGate() { // the rules may have expired meanwhile
            errorMessage = reason.expenseMessage
            return false
        }
        do {
            try model.perform {
                try $0.recordExpense(draft, receipts: receipts, snapshot: snapshot, baseCurrency: baseCurrency,
                                     incurredAt: incurredAt, clientID: clientID)
            }
            return true
        } catch {
            errorMessage = JobDetailView.describe(error)
            return false
        }
    }

    func cancel(model: FieldModel) {
        for receipt in receipts { model.discardEvidence(receipt) }
        receipts = []
        receiptImages = []
    }
}
#endif
