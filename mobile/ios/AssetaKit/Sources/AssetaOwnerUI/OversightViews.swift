#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

// DEC-031 Phase 5 Owner screens (strings doc "DEC-031 Phase 5 — oversight"): More → People scorecard (period chips,
// one row per person), one person (figures, cash held now, records), and the Unbilled work / Idle machines lists the
// dashboard tiles open. Read-only; reads may show the cached snapshot.

private typealias T = OversightTexts

/// People scorecard: counts of items to look at per person, most first.
struct ScorecardView: View {
    let model: OwnerModel
    @State private var period = ScorecardPeriod.default

    var body: some View {
        ScorecardBody(model: model, period: $period)
            .id(period)
            .navigationTitle(T.scoreTitle)
    }
}

private struct ScorecardBody: View {
    let model: OwnerModel
    @Binding var period: ScorecardPeriod
    @State private var loader = Loader<Page<ScorecardRowDTO>>()

    var body: some View {
        let range = period.range()
        List {
            Section {
                FilterChips(options: ScorecardPeriod.allCases.map { ($0, $0.label) }, selection: $period)
                    .listRowInsets(EdgeInsets())
                    .accessibilityIdentifier("scorecard.period")
            }
            if let page = loader.value {
                let rows = OversightPresentation.sorted(page.items)
                if rows.isEmpty { EmptyState(title: T.scoreEmpty, systemImage: "person.3") }
                Section {
                    ForEach(rows) { r in
                        let row = OversightPresentation.row(r)
                        NavigationLink(value: OwnerRoute.scorecardPerson(r.staffMemberID, name: row.title, from: range.from, to: range.to)) {
                            OversightRowView(row: row)
                        }
                    }
                } footer: { if !rows.isEmpty { Text(T.scoreFooter) } }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload(range) }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .refreshable { await reload(range) }
        .task(id: model.changeTick) { await reload(range) }
    }

    private func reload(_ range: (from: String, to: String)) async {
        await loader.load(model, .scorecard(from: range.from, to: range.to), OwnerAPI.scorecard(from: range.from, to: range.to))
    }
}

/// One person's scorecard: figures, cash held now and the records behind them (newest first).
struct ScorecardPersonView: View {
    let model: OwnerModel
    let staffID: UUID
    let name: String?
    let from: String?
    let to: String?
    @State private var loader = Loader<ScorecardDetailDTO>()

    private var range: (from: String, to: String) {
        if let from, let to { return (from, to) }
        return ScorecardPeriod.default.range()
    }

    var body: some View {
        List {
            if let d = loader.value {
                Section(T.figures) {
                    Text(OversightPresentation.name(d.row)).font(.headline)
                    OversightFieldList(fields: OversightPresentation.figureRows(d.row))
                }
                let held = OversightPresentation.cashHeldRows(d.row)
                if !held.isEmpty { Section(T.cashHeld) { OversightFieldList(fields: held) } }
                Section(T.records) {
                    let records = OversightPresentation.records(d, features: model.features)
                    if records.isEmpty { Text(T.recordsEmpty).font(.footnote).foregroundStyle(.secondary) }
                    ForEach(records, id: \.self) { record in
                        if let route = record.route {
                            NavigationLink(value: route) { ScoreRecordRowView(row: record) }
                        } else {
                            ScoreRecordRowView(row: record)
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
        .navigationTitle(loader.value.map { OversightPresentation.name($0.row) } ?? name ?? T.scoreTitle)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private func reload() async {
        let r = range
        await loader.load(model, .scorecardPerson(staffID, from: r.from, to: r.to, item: nil),
                          OwnerAPI.scorecardPerson(staffID, from: r.from, to: r.to))
    }
}

/// Completed jobs not on an issued invoice yet, longest waiting first.
struct UnbilledWorkView: View {
    let model: OwnerModel
    @State private var loader = Loader<Page<UnbilledJobDTO>>()

    var body: some View {
        List {
            if let page = loader.value {
                let items = OversightPresentation.unbilledSorted(page.items)
                if items.isEmpty { EmptyState(title: T.unbilledEmpty, systemImage: "doc.text") }
                Section {
                    ForEach(items) { u in
                        let row = OversightPresentation.unbilled(u)
                        if model.features.allows(.job(u.jobID)) {
                            NavigationLink(value: OwnerRoute.job(u.jobID)) { OversightRowView(row: row) }
                        } else {
                            OversightRowView(row: row)
                        }
                    }
                } footer: { if !items.isEmpty { Text(T.unbilledFooter) } }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(T.unbilledTitle)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private func reload() async { await loader.load(model, .unbilledWork, OwnerAPI.unbilledWork()) }
}

/// Machines with no running job and no engine hours for a while, longest idle first.
struct IdleMachinesView: View {
    let model: OwnerModel
    @State private var loader = Loader<Page<IdleMachineDTO>>()

    var body: some View {
        List {
            if let page = loader.value {
                let items = OversightPresentation.idleSorted(page.items)
                if items.isEmpty { EmptyState(title: T.idleEmpty, systemImage: "moon.zzz") }
                Section {
                    ForEach(items) { m in
                        let row = OversightPresentation.idle(m)
                        if model.features.allows(.machine(m.machineID)) {
                            NavigationLink(value: OwnerRoute.machine(m.machineID)) { OversightRowView(row: row) }
                        } else {
                            OversightRowView(row: row)
                        }
                    }
                } footer: { if !items.isEmpty { Text(T.idleFooter) } }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(T.idleTitle)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private func reload() async { await loader.load(model, .idleMachines, OwnerAPI.idleMachines()) }
}

/// Headline, subtitle, caption, and a trailing value when set.
private struct OversightRowView: View {
    let row: OversightRow

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 4) {
                Text(row.title).font(.headline)
                Text(row.subtitle).font(.subheadline).foregroundStyle(.secondary)
                if let caption = row.caption { Text(caption).font(.caption).foregroundStyle(.secondary) }
            }
            if let trailing = row.trailing {
                Spacer()
                Text(trailing).font(.subheadline).monospacedDigit()
            }
        }
        .accessibilityElement(children: .combine)
    }
}

private struct ScoreRecordRowView: View {
    let row: ScorecardRecordRow

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            if let value = row.value {
                LabeledContent(row.label) { Text(value).monospacedDigit() }
            } else {
                Text(row.label)
            }
            if !row.caption.isEmpty { Text(row.caption).font(.caption).foregroundStyle(.secondary) }
        }
        .accessibilityElement(children: .combine)
    }
}

/// Labelled values (label left, value right).
private struct OversightFieldList: View {
    let fields: [DecisionField]

    var body: some View {
        ForEach(fields, id: \.self) { field in
            LabeledContent(field.label) { Text(field.value).multilineTextAlignment(.trailing) }
        }
    }
}
#endif
