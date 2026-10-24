#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaSync
import SwiftUI

/// Record cash collection (`CASH_COLLECTION`): cash a customer paid the supervisor, entering their
/// custody. Customer and job come from synced data (searchable). The client id is fixed per form.
struct CashCollectionFormView: View {
    let model: FieldModel
    @Environment(\.dismiss) private var dismiss
    @State private var clientID = UUID()
    @State private var customerID: UUID?
    @State private var jobID: UUID?
    @State private var amount = ""
    @State private var currency = ""
    @State private var reference = ""
    @State private var note = ""
    @State private var receivedAt = Date()
    @State private var holderID: UUID?
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    SearchablePickerField(label: "Job (optional)", options: model.jobOptions,
                                          selection: $jobID, noneTitle: "No job",
                                          identifier: "collection.job")
                        .onChange(of: jobID) { _, id in selectJob(id) }
                    SearchablePickerField(label: "Customer", options: model.customerOptions, selection: $customerID,
                                          emptyMessage: "Customers of your jobs appear here after a sync.",
                                          identifier: "collection.customer")
                    holderPicker
                }
                Section {
                    TextField("Amount", text: $amount).keyboardType(.decimalPad).font(.title3.monospacedDigit())
                        .accessibilityIdentifier("collection.amount")
                    TextField("Currency", text: $currency)
                        .textInputAutocapitalization(.characters).autocorrectionDisabled()
                    TextField("Receipt / reference number (optional)", text: $reference)
                    DatePicker("Received", selection: $receivedAt, in: ...Date())
                    TextField("Note (optional)", text: $note, axis: .vertical)
                } footer: {
                    Text("The cash is added to your custody once the server accepts it. The office verifies it later.")
                }
                if let error { Text(error).foregroundStyle(Palette.offline) }
            }
            .navigationTitle("Cash collection")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear { if currency.isEmpty { currency = model.baseCurrency ?? "" } }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save", action: save).disabled(customerID == nil || amount.isEmpty)
                        .accessibilityIdentifier("collection.save")
                }
            }
        }
    }

    /// Recorders may record for another cash holder when the company allows it (operators hold cash without a login).
    @ViewBuilder private var holderPicker: some View {
        if model.access.recordForOthers {
            SearchablePickerField(label: FieldAccountabilityTexts.cashHolder, options: model.custodianOptions(),
                                  selection: Binding(get: { holderID ?? model.myStaffID }, set: { holderID = $0 }),
                                  emptyMessage: FieldAccountabilityTexts.cashTransferCustodiansEmpty, identifier: "cash.holder")
        }
    }

    private var holder: UUID? { holderID.flatMap { model.access.recordForOthers && $0 != model.myStaffID ? $0 : nil } }

    /// A job pre-selects its customer (via its contract).
    private func selectJob(_ id: UUID?) {
        if let customer = id.flatMap({ model.job($0)?.customer?.id }) { customerID = customer }
    }

    private func save() {
        do {
            try model.perform {
                try $0.recordCashCollection(customerID: customerID, amountText: amount, currency: currency,
                                            reference: reference, note: note,
                                            jobNumber: jobID.flatMap { model.job($0)?.job.jobNumber },
                                            jobCustomerID: jobID.flatMap { model.job($0)?.customer?.id },
                                            custodianID: holder, receivedAt: receivedAt, clientID: clientID)
            }
            dismiss()
        } catch {
            self.error = JobDetailView.describe(error)
        }
    }
}

/// Hand over cash (`CASH_HANDOVER`) to the office; it stays "claimed" until finance verifies it.
struct CashHandoverFormView: View {
    let model: FieldModel
    @Environment(\.dismiss) private var dismiss
    @State private var clientID = UUID()
    @State private var amount = ""
    @State private var currency = ""
    @State private var reference = ""
    @State private var note = ""
    @State private var handedAt = Date()
    @State private var holderID: UUID?
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                if let summary = model.cashSummary(), !summary.lines.isEmpty {
                    Section("Your cash") {
                        ForEach(summary.lines) { line in
                            LabeledContent(line.currency.isEmpty ? "Company currency" : line.currency,
                                           value: DecimalInput.format(line.estimatedInHand))
                        }
                    }
                }
                Section {
                    holderPicker
                    TextField("Amount handed over", text: $amount).keyboardType(.decimalPad)
                        .font(.title3.monospacedDigit()).accessibilityIdentifier("handover.amount")
                    TextField("Currency", text: $currency)
                        .textInputAutocapitalization(.characters).autocorrectionDisabled()
                    TextField("Reference (deposit slip, receipt no.)", text: $reference)
                    DatePicker("Handed over", selection: $handedAt, in: ...Date())
                    TextField("Note (who received it…)", text: $note, axis: .vertical)
                } footer: {
                    Text("Your custody goes down only when finance verifies the handover.")
                }
                if let error { Text(error).foregroundStyle(Palette.offline) }
            }
            .navigationTitle("Hand over cash")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear { if currency.isEmpty { currency = model.baseCurrency ?? "" } }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save", action: save).disabled(amount.isEmpty).accessibilityIdentifier("handover.save")
                }
            }
        }
    }

    private func save() {
        do {
            try model.perform {
                try $0.recordCashHandover(amountText: amount, currency: currency, reference: reference, note: note,
                                          custodianID: holder, handedAt: handedAt, clientID: clientID)
            }
            dismiss()
        } catch {
            self.error = JobDetailView.describe(error)
        }
    }

    /// Recorders may record for another cash holder when the company allows it (operators hold cash without a login).
    @ViewBuilder private var holderPicker: some View {
        if model.access.recordForOthers {
            SearchablePickerField(label: FieldAccountabilityTexts.cashHolder, options: model.custodianOptions(),
                                  selection: Binding(get: { holderID ?? model.myStaffID }, set: { holderID = $0 }),
                                  emptyMessage: FieldAccountabilityTexts.cashTransferCustodiansEmpty, identifier: "cash.holder")
        }
    }

    private var holder: UUID? { holderID.flatMap { model.access.recordForOthers && $0 != model.myStaffID ? $0 : nil } }
}

/// Fuel event (`FUEL_EVENT`): PURCHASE (bought, priced), ISSUE (given to a machine, priced) or
/// USAGE (consumed by a machine, no price), with an optional meter reading.
struct FuelFormView: View {
    let model: FieldModel
    @Environment(\.dismiss) private var dismiss
    @State private var clientID = UUID()
    @State private var type: FuelEventType = .issue
    @State private var litres = ""
    @State private var unitPrice = ""
    @State private var currency = ""
    @State private var jobID: UUID?
    @State private var machineID: UUID?
    @State private var meterReading = ""
    @State private var supplier = ""
    @State private var note = ""
    @State private var occurredAt = Date()
    @State private var error: String?

    private var issues: [String] {
        FinanceRules.fuelIssues(type: type, litres: litres, unitPrice: unitPrice, meterReading: meterReading,
                                machineID: machineID, jobID: jobID)
    }

    var body: some View {
        NavigationStack {
            Form {
                Picker("Type", selection: $type) {
                    Text("Purchase").tag(FuelEventType.purchase)
                    Text("Issue").tag(FuelEventType.issue)
                    Text("Usage").tag(FuelEventType.usage)
                }
                .pickerStyle(.segmented)
                Section {
                    TextField("Litres", text: $litres).keyboardType(.decimalPad).font(.title3.monospacedDigit())
                        .accessibilityIdentifier("fuel.litres")
                    if type != .usage {
                        TextField("Price per litre", text: $unitPrice).keyboardType(.decimalPad)
                        TextField("Currency", text: $currency)
                            .textInputAutocapitalization(.characters).autocorrectionDisabled()
                    }
                    if let cost { Text("Cost: \(cost)").accessibilityIdentifier("fuel.cost") }
                    if type == .purchase { TextField("Supplier (optional)", text: $supplier) }
                    DatePicker("When", selection: $occurredAt, in: ...Date())
                } footer: { Text(Self.explain(type)) }
                Section("Machine") {
                    SearchablePickerField(label: "Job", options: model.jobOptions,
                                          selection: $jobID, noneTitle: "No job",
                                          identifier: "fuel.job")
                        .onChange(of: jobID) { _, id in selectJob(id) }
                    SearchablePickerField(label: "Machine", options: model.machineOptions, selection: $machineID,
                                          noneTitle: type == .purchase ? "No machine (stock)" : nil, identifier: "fuel.machine")
                        .disabled(jobID != nil)
                    TextField("Meter reading (optional)", text: $meterReading).keyboardType(.decimalPad)
                }
                Section { TextField("Note (optional)", text: $note, axis: .vertical) }
                let visible = issues.filter { !$0.hasPrefix("Enter the") }
                if !visible.isEmpty {
                    Section { ForEach(visible, id: \.self) { Text($0).foregroundStyle(Palette.warning) } }
                }
                if let error { Text(error).foregroundStyle(Palette.offline) }
            }
            .navigationTitle("Fuel event")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear { if currency.isEmpty { currency = model.baseCurrency ?? "" } }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save", action: save).disabled(!issues.isEmpty).accessibilityIdentifier("fuel.save")
                }
            }
        }
    }

    /// Litres × price per litre, exact (shown before saving; the server computes the attributed cost itself).
    private var cost: String? {
        guard type != .usage,
              case let .success(l) = DecimalInput.parse(litres, maxFractionDigits: FinanceRules.litresDecimals),
              case let .success(p) = DecimalInput.parse(unitPrice, maxFractionDigits: FinanceRules.unitPriceDecimals,
                                                        allowZero: true)
        else { return nil }
        let code = currency.trimmingCharacters(in: .whitespaces).uppercased()
        return MyCashView.money(l * p, code.isEmpty ? (model.baseCurrency ?? "") : code)
    }

    static func explain(_ type: FuelEventType) -> String {
        switch type {
        case .purchase: "Fuel bought into stock. Record the money spent as an expense too."
        case .issue: "Fuel given to a machine from stock."
        case .usage: "Fuel a machine consumed (no price)."
        }
    }

    private func selectJob(_ id: UUID?) {
        if let machine = id.flatMap({ model.job($0)?.job.machineID }) { machineID = machine }
    }

    private func save() {
        do {
            try model.perform {
                try $0.recordFuelEvent(type: type, litres: litres, unitPrice: unitPrice, currency: currency,
                                       machineID: machineID, jobID: jobID, meterReading: meterReading,
                                       supplier: type == .purchase ? supplier : nil, note: note,
                                       occurredAt: occurredAt, clientID: clientID)
            }
            dismiss()
        } catch {
            self.error = JobDetailView.describe(error)
        }
    }
}
#endif
