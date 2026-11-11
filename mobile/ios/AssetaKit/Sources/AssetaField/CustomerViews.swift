#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaSync
import SwiftUI

private typealias C = CustomerTexts

// Supervisor customers (online): list and search, one customer, add or edit its details. Same screens as Android
// `CustomersScreen`, `CustomerDetailScreen`, `CustomerFormScreen` (strings doc "Supervisor — customers").

extension FieldModel {
    var customerPermissions: Set<String> { Set(tenant.permissions) }
    /// The Customers entry: adding customers or editing their details.
    var canEditCustomers: Bool { CustomerRules.canEdit(customerPermissions) }
}

/// Money tab: the entry to Customers.
struct CustomersMoneySection: View {
    let model: FieldModel

    var body: some View {
        if model.canEditCustomers {
            Section(C.section) {
                NavigationLink(value: FieldRoute.customers) { Label(C.row, systemImage: "person.2") }
                    .accessibilityIdentifier("money.customers")
            }
        }
    }
}

/// The add / edit sheet: a new customer (`nil`) or one by id.
struct CustomerFormItem: Identifiable {
    let customerID: UUID?
    var id: String { customerID?.uuidString ?? "new" }
}

/// One online read of a screen.
private enum Loaded<T> {
    case loading, done(T), offline, failed(String)

    init(_ result: CustomerResult<T>) where T: Sendable {
        switch result {
        case let .done(value): self = .done(value)
        case .offline: self = .offline
        case let .refused(message, _, _): self = .failed(message)
        }
    }
}

struct CustomersListView: View {
    let model: FieldModel
    @State private var query = ""
    @State private var state: Loaded<[FieldCustomerDTO]> = .loading
    @State private var form: CustomerFormItem?

    var body: some View {
        List {
            Section {
                TextField(C.search, text: $query).autocorrectionDisabled()
                if model.canEditCustomers, !isOffline {
                    Button(C.add, systemImage: "plus") { form = CustomerFormItem(customerID: nil) }
                }
            }
            switch state {
            case .loading: ProgressView()
            case .offline: ContentUnavailableView(C.title, systemImage: "wifi.slash", description: Text(C.offline))
            case let .failed(message): ContentUnavailableView(C.title, systemImage: "exclamationmark.triangle", description: Text(message))
            case let .done(items):
                if items.isEmpty {
                    ContentUnavailableView(C.title, systemImage: "person.2", description: Text(C.empty))
                }
                ForEach(items) { c in
                    NavigationLink(value: FieldRoute.customer(c.id)) {
                        InboxRow(c.name, nil, C.rowDetail(c))
                    }
                }
            }
        }
        .navigationTitle(C.title)
        .task(id: query) {
            try? await Task.sleep(for: .milliseconds(300))
            await load()
        }
        .refreshable { await load() }
        .sheet(item: $form, onDismiss: { Task { await load() } }) { item in CustomerFormView(model: model, customerID: item.customerID) }
    }

    private var isOffline: Bool { if case .offline = state { true } else { false } }

    private func load() async {
        guard let online = model.services?.online else { state = .offline; return }
        state = Loaded(await online.customers(query: query))
    }
}

struct CustomerDetailView: View {
    let model: FieldModel
    let customerID: UUID
    @State private var state: Loaded<FieldCustomerDTO> = .loading
    @State private var form: CustomerFormItem?

    var body: some View {
        List {
            switch state {
            case .loading: ProgressView()
            case .offline: ContentUnavailableView(C.titleDetail, systemImage: "wifi.slash", description: Text(C.offline))
            case let .failed(message): ContentUnavailableView(C.titleDetail, systemImage: "exclamationmark.triangle", description: Text(message))
            case let .done(c):
                Section(c.name) {
                    ForEach(C.fields(c, termsEditable: CustomerRules.termsEditable(model.customerPermissions)), id: \.label) {
                        LabeledContent($0.label, value: $0.value)
                    }
                }
                if model.canEditCustomers {
                    Section { Button(C.edit, systemImage: "pencil") { form = CustomerFormItem(customerID: c.id) } }
                }
            }
        }
        .navigationTitle(C.titleDetail)
        .task { await load() }
        .refreshable { await load() }
        .sheet(item: $form, onDismiss: { Task { await load() } }) { item in CustomerFormView(model: model, customerID: item.customerID) }
    }

    private func load() async {
        guard let online = model.services?.online else { state = .offline; return }
        state = Loaded(await online.customer(customerID))
    }
}

/// Add or edit a customer's details (online; payment terms only with `tenant.customer.write`).
struct CustomerFormView: View {
    let model: FieldModel
    let customerID: UUID?
    @Environment(\.dismiss) private var dismiss
    @State private var draft = CustomerDraft()
    @State private var current: FieldCustomerDTO?
    @State private var loadProblem: String?
    @State private var saving = false
    @State private var error: String?

    private var termsEditable: Bool { CustomerRules.termsEditable(model.customerPermissions) }
    private var check: Result<CustomerValues, AccountabilityRules.Problems> {
        CustomerRules.check(draft, termsEditable: termsEditable, currentTerms: current?.paymentTermsDays ?? CustomerRules.defaultTerms)
    }

    var body: some View {
        NavigationStack {
            Form {
                if customerID != nil, current == nil {
                    if let loadProblem {
                        ContentUnavailableView(C.titleEdit, systemImage: "wifi.slash", description: Text(loadProblem))
                    } else {
                        ProgressView()
                    }
                } else {
                    Section {
                        TextField(C.code, text: $draft.code).autocorrectionDisabled()
                        TextField(C.name, text: $draft.name)
                        TextField(C.taxID, text: $draft.taxID).autocorrectionDisabled()
                        TextField(C.contactName, text: $draft.contactName)
                        TextField(C.phone, text: $draft.phone).keyboardType(.phonePad)
                        TextField(C.email, text: $draft.email).keyboardType(.emailAddress).textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                        if termsEditable {
                            TextField(C.terms, text: $draft.termsText).keyboardType(.numberPad)
                        } else {
                            LabeledContent(C.terms, value: C.termsByOffice(current?.paymentTermsDays ?? CustomerRules.defaultTerms))
                                .foregroundStyle(.secondary)
                        }
                    } footer: { Text(C.footer) }
                    if case let .failure(problems) = check, !draft.code.isEmpty || !draft.name.isEmpty {
                        Section { ForEach(problems.messages, id: \.self) { Text($0).foregroundStyle(.secondary) } }
                    }
                }
            }
            .navigationTitle(customerID == nil ? C.titleAdd : C.titleEdit)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { Task { await save() } }
                        .disabled(saving || (customerID != nil && current == nil) || !isValid)
                }
            }
            .alert("Not saved", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
                Button("OK") { error = nil }
            } message: { Text(error ?? "") }
            .task { await reload() }
        }
        .interactiveDismissDisabled(saving)
    }

    private var isValid: Bool { if case .success = check { true } else { false } }

    /// Reads the customer again: the form shows the server's current details and version.
    private func reload() async {
        guard let customerID else { return }
        guard let online = model.services?.online else { loadProblem = C.offline; return }
        switch await online.customer(customerID) {
        case let .done(c):
            current = c
            draft = C.draft(c)
        case .offline: loadProblem = C.offline
        case let .refused(message, _, _): loadProblem = message
        }
    }

    private func save() async {
        guard case let .success(values) = check else { return }
        guard let online = model.services?.online else { error = C.offline; return }
        saving = true
        defer { saving = false }
        switch await online.saveCustomer(id: customerID, values: values, version: current?.version) {
        case .done:
            UIAccessibility.post(notification: .announcement, argument: C.saved)
            dismiss()
        case .offline: error = C.offline
        case let .refused(message, _, stale):
            if stale {
                await reload()
                error = C.stale
            } else {
                error = message
            }
        }
    }
}
#endif
