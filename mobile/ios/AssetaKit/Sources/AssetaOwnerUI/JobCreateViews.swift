#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

/// "New job": the boss creates a job and assigns it to a supervisor, as the web dialog. With "Approve now" (only with
/// `tenant.job.approve`) the job is created, submitted and approved in sequence, so the supervisor is notified at once;
/// otherwise it is created and sent for approval. Same wording and rules as the Android Owner app.
struct NewJobSheet: View {
    let model: OwnerModel
    let showingCachedData: Bool
    let finished: (JobCreateOutcome) async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var form = JobCreateForm()
    @State private var approveNow = true
    @State private var progress = JobCreateProgress()
    @State private var attempted = false
    @State private var working = false
    @State private var error: String?

    private var canApprove: Bool { model.features.approveJobs }
    private var block: MutationBlock? {
        model.mutationBlock(permitted: model.features.createJobs, showingCachedData: showingCachedData)
    }

    var body: some View {
        NavigationStack {
            Form {
                if let block { Section { BlockedNote(block: block) } }
                Section {
                    LookupField(title: JobCreateText.contract, selection: $form.contract, label: \.label,
                                error: shown(.contract), identifier: "newjob.contract") { q in
                        try await send(OwnerAPI.contractOptions(query: q)).items
                    }
                    LookupField(title: JobCreateText.machine, selection: $form.machine, label: \.label,
                                error: shown(.machine), identifier: "newjob.machine") { q in
                        try await send(OwnerAPI.machineOptions(query: q)).items
                    }
                    LookupField(title: JobCreateText.supervisor, selection: $form.supervisor, label: \.fullName,
                                error: shown(.supervisor), identifier: "newjob.supervisor") { q in
                        try await send(OwnerAPI.supervisorOptions(query: q)).items
                    }
                    if model.features.pickJobSites {
                        LookupField(title: JobCreateText.site, selection: $form.site, label: \.label,
                                    allowsNone: true, identifier: "newjob.site") { q in
                            try await send(OwnerAPI.jobSiteOptions(query: q))
                        }
                    }
                    TextField(JobCreateText.jobNumber, text: $form.jobNumber)
                        .textInputAutocapitalization(.characters)
                        .autocorrectionDisabled()
                        .accessibilityIdentifier("newjob.number")
                    FieldError(text: shown(.jobNumber))
                }
                Section {
                    DatePicker(JobCreateText.plannedStart, selection: $form.plannedStart)
                        .accessibilityIdentifier("newjob.start")
                    Toggle(JobCreateText.plannedEnd, isOn: Binding(
                        get: { form.plannedEnd != nil },
                        set: { form.plannedEnd = $0 ? (form.plannedEnd ?? form.plannedStart.addingTimeInterval(8 * 3600)) : nil }
                    ))
                    .accessibilityIdentifier("newjob.end.toggle")
                    if let end = form.plannedEnd {
                        DatePicker(JobCreateText.plannedEnd, selection: Binding(get: { end }, set: { form.plannedEnd = $0 }))
                            .labelsHidden()
                            .accessibilityIdentifier("newjob.end")
                    }
                    FieldError(text: form.error(.plannedEnd))
                }
                Section(JobCreateText.price) {
                    Picker(JobCreateText.price, selection: $form.priceMode) {
                        ForEach(JobPriceMode.allCases, id: \.self) { Text($0.label).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .accessibilityIdentifier("newjob.price")
                    if form.priceMode == .negotiated {
                        TextField(JobCreateText.hourlyRateLabel(currency: form.contract?.currency), text: $form.hourlyRate)
                            .keyboardType(.decimalPad)
                            .accessibilityIdentifier("newjob.rate")
                        FieldError(text: shown(.hourlyRate))
                    }
                    TextField(JobCreateText.minimumHours, text: $form.minimumHours)
                        .keyboardType(.decimalPad)
                        .accessibilityIdentifier("newjob.minimum")
                    FieldError(text: shown(.minimumHours))
                }
                Section {
                    if canApprove {
                        Toggle(JobCreateText.approveNow, isOn: $approveNow).accessibilityIdentifier("newjob.approveNow")
                    }
                } footer: {
                    if !(canApprove && approveNow) { Text(JobCreateText.sendForApproval) }
                }
                if let error {
                    Text(error).font(.footnote).foregroundStyle(Palette.offline).accessibilityIdentifier("newjob.error")
                }
            }
            .navigationTitle(JobCreateText.title)
            .navigationBarTitleDisplayMode(.inline)
            .interactiveDismissDisabled(working)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button(JobCreateText.cancel) { dismiss() }.disabled(working) }
                ToolbarItem(placement: .confirmationAction) {
                    Button(JobCreateText.submitLabel(approveNow: approveNow, canApprove: canApprove)) { Task { await submit() } }
                        .disabled(working || block != nil)
                        .accessibilityIdentifier("newjob.submit")
                }
            }
        }
    }

    /// Field errors appear once the user tried to create (the end-before-start one at once).
    private func shown(_ field: JobCreateForm.Field) -> String? { attempted ? form.error(field) : nil }

    private func send<Value: Decodable & Sendable>(_ request: APIRequest<Value>) async throws -> Value {
        guard let repository = model.repository else { throw APIError.tenantRequired }
        do {
            return try await repository.send(request)
        } catch {
            model.handle(error)
            throw error
        }
    }

    private func submit() async {
        attempted = true
        guard block == nil else { return }
        if let first = form.errors().first {
            error = first.1
            return
        }
        working = true
        defer { working = false }
        error = nil
        var current = progress
        let outcome = await JobCreateFlow.run(form: form, approveNow: approveNow && canApprove, progress: &current) {
            try await send($0)
        }
        progress = current
        switch outcome {
        case let .notCreated(message):
            error = message
        case .done, .partly:
            dismiss()
            await finished(outcome)
        }
    }
}

private struct FieldError: View {
    let text: String?

    var body: some View {
        if let text { Text(text).font(.footnote).foregroundStyle(Palette.offline) }
    }
}

/// A form row that opens a searchable list fed by the server (`q` on every change, debounced), as the web's async
/// autocompletes. Lookups need a connection; nothing is cached.
struct LookupField<Item: Identifiable & Hashable & Sendable>: View {
    let title: String
    @Binding var selection: Item?
    let label: (Item) -> String
    var allowsNone = false
    var error: String?
    var identifier: String
    let search: @MainActor (String) async throws -> [Item]
    @State private var open = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Button { open = true } label: {
                LabeledContent(title) {
                    Text(selection.map(label) ?? JobCreateText.choose)
                        .foregroundStyle(selection == nil ? .secondary : .primary)
                        .multilineTextAlignment(.trailing)
                }
            }
            .foregroundStyle(.primary)
            .accessibilityIdentifier(identifier)
            FieldError(text: error)
        }
        .sheet(isPresented: $open) {
            LookupSheet(title: title, selection: $selection, label: label, allowsNone: allowsNone, search: search)
        }
    }
}

private struct LookupSheet<Item: Identifiable & Hashable & Sendable>: View {
    let title: String
    @Binding var selection: Item?
    let label: (Item) -> String
    let allowsNone: Bool
    let search: @MainActor (String) async throws -> [Item]
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""
    @State private var items: [Item]?
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List {
                if allowsNone {
                    Button(JobCreateText.noSite) { selection = nil; dismiss() }
                }
                if let items {
                    if items.isEmpty { Text(JobCreateText.noMatches).foregroundStyle(.secondary) }
                    ForEach(items) { item in
                        Button { selection = item; dismiss() } label: {
                            HStack {
                                Text(label(item)).foregroundStyle(.primary)
                                Spacer()
                                if item.id == selection?.id { Image(systemName: "checkmark").foregroundStyle(Brand.amber) }
                            }
                        }
                    }
                } else if let error {
                    Text(error).foregroundStyle(Palette.offline)
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            }
            .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: JobCreateText.search)
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button(JobCreateText.cancel) { dismiss() } } }
            .task(id: query) {
                if !query.isEmpty { try? await Task.sleep(for: .milliseconds(300)) }
                guard !Task.isCancelled else { return }
                do {
                    let found = try await search(query)
                    guard !Task.isCancelled else { return }
                    items = found
                    error = nil
                } catch {
                    guard !Task.isCancelled else { return }
                    items = nil
                    self.error = DecisionErrorText.message(for: error)
                }
            }
        }
    }
}

/// Opens a job after "New job" when it was created but a later step failed (the notice says what).
struct CreatedJob: Hashable {
    let id: UUID
    let notice: String
}
#endif
