#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

// DEC-032 Phase 4 Owner screens (strings doc "management view"): the Accountability groups' rows, Employee accountability and
// Find a reference.

private typealias T = ManagementTexts

/// A label, value and caption; opens its screen or the web when it has a target.
struct ManagementRowView: View {
    let model: OwnerModel
    let row: ManagementRow
    @Environment(\.openURL) private var openURL

    var body: some View {
        switch row.target {
        case let .screen(route)?:
            NavigationLink(value: route) { content }
        case let .web(path)?:
            Button { if let url = model.session.configuration?.webURL(for: path) { openURL(url) } } label: {
                VStack(alignment: .leading, spacing: 2) {
                    content
                    Text(T.openWeb).font(.footnote).foregroundStyle(Color.accentColor)
                }
            }
            .buttonStyle(.plain)
        case nil:
            content
        }
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 2) {
            LabeledContent(row.label) { Text(row.value).multilineTextAlignment(.trailing) }
            if let caption = row.caption { Text(caption).font(.footnote).foregroundStyle(.secondary) }
        }
    }
}

/// The four group cards of the Accountability dashboard.
struct ManagementGroupsView: View {
    let model: OwnerModel
    let summary: AccountabilitySummaryDTO

    var body: some View {
        ForEach(ManagementDashboard.groups(summary, features: model.features.without(summary.disabledCapabilities))) { group in
            ForEach(Array(group.blocks.enumerated()), id: \.element.id) { index, block in
                Section {
                    if let target = block.headingTarget, let heading = block.heading {
                        ManagementRowView(model: model, row: ManagementRow(id: "heading", label: heading, value: "", target: target)).fontWeight(.semibold)
                    }
                    ForEach(block.rows) { ManagementRowView(model: model, row: $0) }
                } header: {
                    Text(block.headingTarget != nil ? "" : block.heading ?? (index == 0 ? group.title : ""))
                } footer: {
                    if let footer = block.footer { Text(footer) }
                }
            }
        }
    }
}

/// One employee's accountability (`tenant.accountability.employee.read`): identity, figures, cash held now and records.
struct EmployeeAccountabilityView: View {
    let model: OwnerModel
    let staffID: UUID
    let name: String?
    let from: String?
    let to: String?
    /// Nil: the period handed over by the scorecard, when no chip covers it.
    @State private var period: ScorecardPeriod?
    @State private var loader = Loader<EmployeeAccountabilityDTO>()

    init(model: OwnerModel, staffID: UUID, name: String?, from: String?, to: String?) {
        self.model = model
        self.staffID = staffID
        self.name = name
        self.from = from
        self.to = to
        _period = State(initialValue: EmployeePresentation.initialPeriod(from: from, to: to))
    }

    private var range: (from: String, to: String) {
        if let period { return period.range() }
        if let from, let to { return (from, to) }
        return ScorecardPeriod.default.range()
    }

    var body: some View {
        List {
            Section {
                FilterChips(options: ScorecardPeriod.allCases.map { (Optional($0), $0.label) }, selection: $period)
                    .listRowInsets(EdgeInsets()).accessibilityIdentifier("employee.period")
            }
            if let d = loader.value {
                identity(d.identity)
                Section(T.employeeFigures) { ForEach(EmployeePresentation.figureRows(d)) { ManagementRowView(model: model, row: $0) } }
                let held = EmployeePresentation.cashHeld(d)
                if !held.isEmpty { Section(T.employeeCashHeld) { ForEach(held) { ManagementRowView(model: model, row: $0) } } }
                ForEach(EmployeePresentation.recordLists(d, features: model.features)) { list in
                    Section(list.title) { ForEach(list.rows) { ManagementRowView(model: model, row: $0) } }
                }
                if !d.truncated.isEmpty { Text(T.employeeTruncated).font(.footnote).foregroundStyle(.secondary) }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(T.employeeTitle)
        .refreshable { await reload() }
        .task(id: "\(model.changeTick)\(String(describing: period))") { await reload() }
    }

    @ViewBuilder private func identity(_ i: EmployeeIdentityDTO) -> some View {
        Section {
            HStack {
                Text(i.fullName).font(.headline)
                if !i.isActive { Spacer(); Pill(text: T.employeeInactive, color: Palette.warning) }
            }
            if let code = i.employeeCode { LabeledContent(T.employeeCode, value: code) }
            if !i.roles.isEmpty { LabeledContent(T.employeeRoles, value: i.roles.joined(separator: ", ")) }
            if let phone = i.phone { LabeledContent(T.employeePhone, value: phone) }
        }
    }

    private func reload() async {
        let r = range
        await loader.load(model, .employeeAccountability(staffID, from: r.from, to: r.to),
                          OwnerAPI.employeeAccountability(staffID, from: r.from, to: r.to))
    }
}

/// Find a reference: online only, one card per match.
struct FindReferenceView: View {
    let model: OwnerModel
    @State private var text = ""
    @State private var result: LookupResultDTO?
    @State private var error: String?
    @State private var working = false

    private var trimmed: String { text.trimmingCharacters(in: .whitespacesAndNewlines) }

    var body: some View {
        List {
            Section {
                TextField(T.lookupHint, text: Binding(get: { text }, set: { text = String($0.prefix(100)) }))
                    .autocorrectionDisabled().textInputAutocapitalization(.characters)
                    .accessibilityIdentifier("lookup.reference").onSubmit { Task { await search() } }
                Button(T.lookupSearch) { Task { await search() } }
                    .disabled(trimmed.isEmpty || working).accessibilityIdentifier("lookup.search")
            }
            if let error { Text(error).foregroundStyle(Palette.offline) }
            if working { ProgressView().frame(maxWidth: .infinity) }
            if let result, !working {
                if result.matches.isEmpty { EmptyState(title: T.lookupEmpty, systemImage: "magnifyingglass") }
                ForEach(result.matches) { match in card(LookupPresentation.card(match, features: model.features)) }
            }
        }
        .navigationTitle(T.lookupTitle)
    }

    @ViewBuilder private func card(_ card: LookupPresentation.Card) -> some View {
        Section(card.title) {
            ManagementRowView(model: model, row: ManagementRow(id: "head", label: card.subtitle, value: "", target: card.target))
            ForEach(card.rows) { LabeledContent($0.label, value: $0.value) }
        }
    }

    private func search() async {
        guard !trimmed.isEmpty, let repository = model.repository else { return }
        working = true
        defer { working = false }
        do {
            result = try await repository.send(OwnerAPI.lookup(reference: trimmed))
            error = nil
        } catch {
            result = nil
            self.error = LookupPresentation.failureMessage(error)
            model.handle(error)
        }
    }
}
#endif
