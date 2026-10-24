#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaSync
import SwiftUI

extension FieldModel {
    var requestContractOptions: [PickerOption] {
        (services?.directory.requestContracts() ?? []).map { contract in
            PickerOption(id: contract.id, title: contract.customerName ?? contract.contractNumber,
                         subtitle: [contract.contractNumber, contract.siteName].compactMap { $0 }.joined(separator: " · "))
        }
    }

    var requestMachineOptions: [PickerOption] {
        (services?.directory.requestMachines() ?? []).map {
            PickerOption(id: $0.id, title: InboxTexts.machine($0.assetCode, $0.name), subtitle: nil)
        }
    }

    var requestSiteOptions: [PickerOption] {
        var sites = (services?.directory.requestSites() ?? []).map { PickerOption(id: $0.id, title: $0.name, subtitle: nil) }
        // A contract's own site may not be synced yet: offer it from the saved contracts.
        for contract in services?.directory.requestContracts() ?? [] {
            if let id = contract.jobSiteID, let name = contract.siteName, !sites.contains(where: { $0.id == id }) {
                sites.append(PickerOption(id: id, title: name, subtitle: nil))
            }
        }
        return sites.sorted { $0.title < $1.title }
    }

    func requestContract(_ id: UUID?) -> FieldContractDTO? {
        id.flatMap { id in services?.directory.requestContracts().first { $0.id == id } }
    }

    /// Why job requests can't be recorded now (never synced, or the server lacks OP_JOB_REQUEST), else nil.
    var jobRequestUnavailable: String? { services?.recorder.jobRequestUnavailable() }

    /// Fetches the form's lookups while online (the saved lists are used offline).
    func refreshRequestLookups() async {
        guard let services, isOnline else { return }
        await services.online.refreshRequestLookups()
    }
}

/// Request a job from the field (`JOB_REQUEST`, works offline): customer contract, machine, optional site
/// (defaults to the contract's), planned start/end and what the customer asked for. The owner prices and
/// approves it; the job then appears as ready to start. Same form as Android `JobRequestScreen`.
struct JobRequestFormView: View {
    let model: FieldModel
    @Environment(\.dismiss) private var dismiss
    @State private var clientID = UUID()
    @State private var contractID: UUID?
    @State private var machineID: UUID?
    @State private var siteID: UUID?
    @State private var plannedStart = Date()
    @State private var plannedEnd: Date?
    @State private var note = ""
    @State private var error: String?
    @State private var tick = 0 // re-reads the lookups after a refresh

    var body: some View {
        NavigationStack {
            if let blocked = model.jobRequestUnavailable {
                ContentUnavailableView(JobRequestText.unavailableTitle, systemImage: "lock", description: Text(blocked))
                    .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
            } else {
                form
            }
        }
    }

    private var form: some View {
            Form {
                Section {
                    SearchablePickerField(label: JobRequestText.contract, options: model.requestContractOptions,
                                          selection: $contractID, emptyMessage: JobRequestText.noContracts,
                                          identifier: "request.contract")
                        .onChange(of: contractID) { _, id in
                            if let site = model.requestContract(id)?.jobSiteID { siteID = site }
                        }
                    SearchablePickerField(label: JobRequestText.machine, options: model.requestMachineOptions,
                                          selection: $machineID, emptyMessage: JobRequestText.noMachines,
                                          identifier: "request.machine")
                    SearchablePickerField(label: JobRequestText.site, options: model.requestSiteOptions,
                                          selection: $siteID, noneTitle: JobRequestText.notSet,
                                          identifier: "request.site")
                }
                .id(tick)
                Section {
                    DatePicker(JobRequestText.plannedStart, selection: $plannedStart)
                        .onChange(of: plannedStart) { _, start in if let end = plannedEnd, end < start { plannedEnd = start } }
                    if let end = plannedEnd {
                        DatePicker(JobRequestText.plannedEnd, selection: Binding(get: { end }, set: { plannedEnd = $0 }),
                                   in: plannedStart...)
                        Button(JobRequestText.clear, role: .destructive) { plannedEnd = nil }
                    } else {
                        Button { plannedEnd = plannedStart } label: {
                            LabeledContent(JobRequestText.plannedEnd) { Text(JobRequestText.notSet).foregroundStyle(.secondary) }
                        }
                        .accessibilityIdentifier("request.plannedEnd")
                    }
                    TextField(JobRequestText.note, text: $note, axis: .vertical)
                        .lineLimit(3...6)
                        .onChange(of: note) { _, text in
                            if text.count > JobRequestText.noteLimit { note = String(text.prefix(JobRequestText.noteLimit)) }
                        }
                        .accessibilityIdentifier("request.note")
                } footer: {
                    Text(JobRequestText.footer)
                }
                if let error { Text(error).foregroundStyle(Palette.offline) }
            }
            .navigationTitle(JobRequestText.formTitle)
            .navigationBarTitleDisplayMode(.inline)
            .task {
                await model.refreshRequestLookups()
                tick += 1
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(JobRequestText.submit, action: save).disabled(contractID == nil || machineID == nil)
                        .accessibilityIdentifier("request.save")
                }
            }
    }

    private func save() {
        do {
            try model.perform {
                try $0.requestJob(contractID: contractID, machineID: machineID, jobSiteID: siteID, plannedStart: plannedStart,
                                  plannedEnd: plannedEnd, note: note, clientID: clientID)
            }
            dismiss()
        } catch {
            self.error = JobDetailView.describe(error)
        }
    }
}
#endif
