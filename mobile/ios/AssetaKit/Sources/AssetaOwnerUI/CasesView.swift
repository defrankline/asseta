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
            FilterChips(options: CaseText.filters, selection: $status)
                .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
            if let page = loader.value {
                FootNote(CaseText.intro)
                if page.items.isEmpty {
                    EmptyState(title: CaseText.emptyTitle, message: CaseText.emptyMessage, systemImage: "doc.text.magnifyingglass")
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
            Text(CaseText.summary(item)).font(.caption).foregroundStyle(.secondary)
            if let outcome = item.latestOutcome {
                Text("Outcome: \(OwnerFormat.humanize(outcome))").font(.caption).foregroundStyle(.secondary)
            }
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
                    LabeledContent("Case", value: item.caseNumber)
                    LabeledContent("Status", value: item.status.humanized)
                    LabeledContent("Severity") { Pill(text: item.severity.label, color: item.severity.color) }
                    LabeledContent("Subject", value: OwnerFormat.humanize(item.subjectType))
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
                    Text(CaseText.detailFooter)
                }
                Section("Signals (\(detail.signals.count))") {
                    ForEach(detail.signals) { signal in
                        VStack(alignment: .leading, spacing: 2) {
                            HStack {
                                Text(OwnerFormat.humanize(signal.code))
                                    .font(.subheadline.bold())
                                Spacer()
                                Pill(text: signal.severity.label, color: signal.severity.color)
                            }
                            Text("Observed \(signal.observedAt.shortStamp)").font(.caption).foregroundStyle(.secondary)
                            if case let .object(fields) = signal.evidence {
                                ForEach(fields.keys.sorted(), id: \.self) { key in
                                    Text("\(OwnerFormat.humanize(key)): \(AlertText.evidence(fields[key] ?? .null))")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
                if !detail.outcomes.isEmpty {
                    Section("Outcomes") {
                        ForEach(detail.outcomes.sorted { $0.sequence < $1.sequence }) { outcome in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(OwnerFormat.humanize(outcome.outcome))
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
        .navigationTitle("Investigation")
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private func reload() async { await loader.load(model, .caseDetail(caseID), OwnerAPI.caseDetail(caseID)) }
}
#endif
