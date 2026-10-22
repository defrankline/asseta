#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import SwiftUI

/// Investigations, read-only. Wording stays neutral: a case is a set of signals that needs
/// review, not an accusation; outcomes are shown as recorded.
struct CasesView: View {
    let model: OwnerModel
    @State private var status: CaseStatus? = nil
    @State private var loader = Loader<Page<AnomalyCaseDTO>>()

    var body: some View {
        List {
            Picker("Status", selection: $status) {
                Text("All").tag(CaseStatus?.none)
                Text("Open").tag(CaseStatus?.some(.open))
                Text("In review").tag(CaseStatus?.some(.inReview))
                Text("Resolved").tag(CaseStatus?.some(.resolved))
            }
            .pickerStyle(.segmented)
            .listRowBackground(Color.clear)
            if let page = loader.value {
                if page.items.isEmpty {
                    ContentUnavailableView("No investigations", systemImage: "doc.text.magnifyingglass",
                                           description: Text("Nothing needs review."))
                }
                ForEach(page.items) { item in
                    NavigationLink(value: OwnerRoute.investigation(item.id)) { CaseRow(item: item) }
                }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle("Investigations")
        .refreshable { await reload() }
        .task(id: ReloadKey(tick: model.changeTick, filter: status?.rawValue)) { await reload() }
    }

    private func reload() async {
        await loader.load(model, .cases(status), OwnerAPI.cases(status: status, pageSize: 100))
    }
}

struct CaseRow: View {
    let item: AnomalyCaseDTO

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(item.caseNumber).font(.headline)
                Pill(text: item.severity.label, color: item.severity.color)
                Spacer()
                Text(item.status.humanized).font(.caption).foregroundStyle(.secondary)
            }
            Text(item.title).font(.subheadline)
            Text("Last signal \(item.lastSignalAt.shortStamp)").font(.caption).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
    }
}

struct CaseDetailView: View {
    let model: OwnerModel
    let caseID: UUID
    @State private var loader = Loader<AnomalyCaseDetailDTO>()

    var body: some View {
        List {
            if let detail = loader.value {
                let item = detail.case
                Section {
                    LabeledContent("Status", value: item.status.humanized)
                    LabeledContent("Severity") { Pill(text: item.severity.label, color: item.severity.color) }
                    LabeledContent("Subject", value: item.subjectType.capitalized)
                    LabeledContent("Opened", value: item.openedAt.shortStamp)
                    LabeledContent("Assigned to", value: item.assigneeName ?? "Unassigned")
                    if let machine = item.machineID, model.features.fleet {
                        NavigationLink(value: OwnerRoute.machine(machine)) { Text("Open machine") }
                    }
                    if let job = item.jobID, model.features.jobs {
                        NavigationLink(value: OwnerRoute.job(job)) { Text("Open job") }
                    }
                } header: {
                    Text(item.title)
                } footer: {
                    Text("Signals are indicators that need review; they are not conclusions. Review and outcomes are recorded in the web console.")
                }
                Section("Signals (\(detail.signals.count))") {
                    ForEach(detail.signals) { signal in
                        VStack(alignment: .leading, spacing: 2) {
                            HStack {
                                Text(signal.code.split(separator: "_").joined(separator: " ").lowercased().capitalizedFirst)
                                    .font(.subheadline.bold())
                                Spacer()
                                Pill(text: signal.severity.label, color: signal.severity.color)
                            }
                            Text("Observed \(signal.observedAt.shortStamp)").font(.caption).foregroundStyle(.secondary)
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
                if !detail.outcomes.isEmpty {
                    Section("Outcomes") {
                        ForEach(detail.outcomes) { outcome in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(outcome.outcome.split(separator: "_").joined(separator: " ").lowercased().capitalizedFirst)
                                    .font(.subheadline.bold())
                                Text(outcome.explanation).font(.subheadline)
                                Text("\(outcome.decidedByName ?? "Reviewer") · \(outcome.decidedAt.shortStamp)")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
                if !detail.notes.isEmpty {
                    Section("Notes") {
                        ForEach(detail.notes) { note in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(note.body)
                                Text("\(note.authorName ?? "Team") · \(note.createdAt.shortStamp)")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(loader.value?.case.caseNumber ?? "Investigation")
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private func reload() async { await loader.load(model, .caseDetail(caseID), OwnerAPI.caseDetail(caseID)) }
}
#endif
