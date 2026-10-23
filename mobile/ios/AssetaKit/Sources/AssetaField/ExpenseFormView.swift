#if os(iOS)
import AssetaAppShell
import AssetaCapture
import AssetaModel
import AssetaSync
import AVFoundation
import SwiftUI
import UIKit

/// Record expense (`EXPENSE`). The owner's `EXPENSE_CAPTURE` snapshot is enforced offline: receipt
/// photo above the threshold, GPS fix and accuracy when required, and a clear note when the amount
/// needs a manager's approval. Receipts are taken with the in-app camera only.
struct ExpenseFormView: View {
    let model: FieldModel
    @State private var form: ExpenseFormModel
    @State private var showCamera = false
    @State private var cameraDenied = false
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    init(model: FieldModel, snapshot: ExpensePolicySnapshot) {
        self.model = model
        _form = State(initialValue: ExpenseFormModel(snapshot: snapshot, baseCurrency: model.baseCurrency))
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    SearchablePickerField(label: "Category", options: model.categoryOptions, selection: $form.draft.categoryID,
                                          emptyMessage: "No expense categories have been synced yet. Connect and sync.",
                                          identifier: "expense.category")
                    TextField("Amount", text: $form.draft.amountText)
                        .keyboardType(.decimalPad).font(.title3.monospacedDigit())
                        .accessibilityIdentifier("expense.amount")
                    TextField("Currency", text: $form.draft.currency)
                        .textInputAutocapitalization(.characters).autocorrectionDisabled()
                    TextField("What was it for?", text: $form.draft.description, axis: .vertical)
                        .accessibilityIdentifier("expense.description")
                    TextField("Supplier (optional)", text: $form.draft.supplier)
                } footer: { Text(form.rulesSummary) }
                Section("Paid from") {
                    Picker("Paid from", selection: $form.draft.paidFrom) {
                        Text("My cash").tag(ExpensePaidFrom.cashCustody)
                        Text("Company").tag(ExpensePaidFrom.company)
                    }
                    .pickerStyle(.segmented)
                }
                Section {
                    SearchablePickerField(label: "Job", options: model.jobOptions,
                                          selection: Binding(get: { form.draft.jobID },
                                                             set: { form.selectJob($0, model: model) }),
                                          noneTitle: "No job", identifier: "expense.job")
                    SearchablePickerField(label: "Machine", options: model.machineOptions, selection: $form.draft.machineID,
                                          noneTitle: "No machine", identifier: "expense.machine")
                        .disabled(form.draft.jobID != nil)
                } header: { Text("Charge to") } footer: {
                    Text(form.draft.jobID != nil ? "The cost is charged to the job's machine." : "Optional.")
                }
                receiptSection
                gpsSection
                outcomeSection
            }
            .navigationTitle("Record expense")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { form.cancel(model: model); dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { if form.save(model: model) { dismiss() } }
                        .disabled(!form.assessment.canSave)
                        .accessibilityIdentifier("expense.save")
                }
            }
            .task { await form.locate(using: model.locator) }
            .onAppear { if form.draft.currency.isEmpty { form.draft.currency = form.baseCurrency ?? "" } }
            .fullScreenCover(isPresented: $showCamera) {
                CameraCaptureView { data in
                    showCamera = false
                    if let data { form.receiptTaken(data, model: model) }
                }
                .ignoresSafeArea()
            }
            .alert("Camera access needed", isPresented: $cameraDenied) {
                Button("Open Settings") { if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) } }
                Button("Cancel", role: .cancel) {}
            } message: { Text("Allow camera access in Settings to photograph the receipt.") }
            .alert("Not saved", isPresented: Binding(get: { form.errorMessage != nil },
                                                     set: { if !$0 { form.errorMessage = nil } })) {
                Button("OK") { form.errorMessage = nil }
            } message: { Text(form.errorMessage ?? "") }
        }
        .interactiveDismissDisabled()
    }

    @ViewBuilder private var receiptSection: some View {
        Section {
            ForEach(Array(form.receiptImages.enumerated()), id: \.offset) { index, data in
                HStack {
                    if let image = UIImage(data: data) {
                        Image(uiImage: image).resizable().scaledToFit().frame(height: 120)
                    }
                    Spacer()
                    Button("Remove", role: .destructive) { form.removeReceipt(at: index, model: model) }
                        .buttonStyle(.borderless)
                }
            }
            if form.receipts.count < FieldRecorder.maxReceipts {
                Button(form.receipts.isEmpty ? "Photograph receipt" : "Add another receipt photo", systemImage: "camera") {
                    Task { if await CameraAccess.request() { showCamera = true } else { cameraDenied = true } }
                }
                .accessibilityIdentifier("expense.receipt")
            }
        } header: {
            Text(form.assessment.receiptRequired ? "Receipt (required)" : "Receipt (optional)")
        } footer: {
            Text("Stored encrypted on this phone and uploaded before the expense is sent.")
        }
    }

    @ViewBuilder private var gpsSection: some View {
        Section {
            switch form.gpsState {
            case .locating:
                ProgressView("Getting a fresh location fix…")
            case let .done(result):
                if result.status == .fix, let lat = result.latitude, let lon = result.longitude {
                    LabeledContent("Location", value: String(format: "%.5f, %.5f", lat, lon))
                    LabeledContent("Accuracy", value: String(format: "± %.0f m", result.accuracyM ?? 0))
                } else {
                    Label(MeterCaptureView.describe(result.status), systemImage: "location.slash").foregroundStyle(Palette.warning)
                }
                Button("Try location again", systemImage: "location") { Task { await form.locate(using: model.locator) } }
            }
        } header: { Text(form.policy.gpsRequired ? "GPS (required)" : "GPS") }
    }

    @ViewBuilder private var outcomeSection: some View {
        let assessment = form.assessment
        let visible = assessment.issues.filter { issue in
            switch issue {
            case .categoryMissing, .descriptionMissing, .gpsPending: false
            case let .amount(failure): failure != .empty
            default: true
            }
        }
        if !visible.isEmpty {
            Section { ForEach(visible, id: \.description) { Text($0.description).foregroundStyle(Palette.warning) } }
        }
        if assessment.amount != nil {
            Section {
                if let note = form.approvalNote {
                    Label(note, systemImage: "person.badge.clock").font(.footnote)
                        .accessibilityIdentifier("expense.approvalNote")
                } else {
                    Label("Within the auto-approval limit: approved automatically once synced.", systemImage: "checkmark.seal")
                        .font(.footnote).accessibilityIdentifier("expense.autoApproved")
                }
            }
        }
    }
}

enum CameraAccess {
    /// Asks for camera access just in time; true when the camera may be used.
    @MainActor static func request() async -> Bool {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: true
        case .notDetermined: await AVCaptureDevice.requestAccess(for: .video)
        default: false
        }
    }
}
#endif
