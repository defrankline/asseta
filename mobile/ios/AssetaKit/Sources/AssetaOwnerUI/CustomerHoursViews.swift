#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import QuickLook
import SwiftUI

// DEC-031 Phase 4 Owner screens (strings doc "DEC-031 Phases 2 and 4"): More → Customer hours (open purchases), one
// purchase (hours, hours in use by running jobs, machines) and the customer's hours statement with its PDF.
// Read-only; reads may show the cached snapshot.

private typealias T = CustomerHoursTexts

/// Open prepaid-hours purchases with hours left or in use by running jobs, newest first.
struct CustomerHoursView: View {
    let model: OwnerModel
    @State private var loader = Loader<Page<HoursPurchaseDTO>>()

    var body: some View {
        List {
            if let page = loader.value {
                let rows = CustomerHoursPresentation.open(page.items)
                if rows.isEmpty { EmptyState(title: T.empty, systemImage: "hourglass") }
                Section {
                    ForEach(rows) { p in
                        let row = CustomerHoursPresentation.row(p)
                        NavigationLink(value: OwnerRoute.hoursPurchase(p.id)) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(row.title).font(.headline)
                                Text(row.machine).font(.subheadline).foregroundStyle(.secondary)
                                Text(row.left).font(.caption).foregroundStyle(.secondary)
                            }
                            .accessibilityElement(children: .combine)
                        }
                    }
                } footer: { if !rows.isEmpty { Text(T.listFooter) } }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(T.listTitle)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private func reload() async {
        await loader.load(model, .hoursPurchases, OwnerAPI.hoursPurchases())
    }
}

/// One prepaid-hours purchase, read by id.
struct HoursPurchaseView: View {
    let model: OwnerModel
    let purchaseID: UUID
    @State private var loader = Loader<HoursPurchaseDTO>()

    var body: some View {
        Form {
            if let p = loader.value {
                Section {
                    Text(p.purchaseNumber).font(.headline)
                    HoursFieldList(fields: CustomerHoursPresentation.purchaseRows(p))
                } header: { Text(T.hours) } footer: { Text(T.provisionalFooter) }
                let machines = CustomerHoursPresentation.machineRows(p)
                if !machines.isEmpty { Section(T.machines) { HoursFieldList(fields: machines) } }
                Section {
                    NavigationLink(value: OwnerRoute.hoursStatement(customer: p.customerID, name: p.customerName)) {
                        Text(T.openStatement)
                    }
                    .accessibilityIdentifier("hours.statement")
                }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView()
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(T.purchaseTitle)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private func reload() async {
        await loader.load(model, .hoursPurchase(purchaseID), OwnerAPI.hoursPurchase(purchaseID))
    }
}

/// A customer's hours statement for a period chip, with the PDF (online only).
struct HoursStatementView: View {
    let model: OwnerModel
    let customerID: UUID
    let customerName: String?
    @State private var period: StatementPeriod = .thisMonth

    var body: some View {
        StatementBody(model: model, customerID: customerID, customerName: customerName, period: $period)
            .id(period)
            .navigationTitle(T.statementTitle)
    }
}

private struct StatementBody: View {
    let model: OwnerModel
    let customerID: UUID
    let customerName: String?
    @Binding var period: StatementPeriod
    @State private var loader = Loader<HoursStatementDTO>()
    @State private var pdfBusy = false
    @State private var pdfError: String?
    @State private var pdfURL: URL?

    var body: some View {
        let range = period.range()
        List {
            Section {
                FilterChips(options: StatementPeriod.allCases.map { ($0, $0.label) }, selection: $period)
                    .listRowInsets(EdgeInsets())
                    .accessibilityIdentifier("statement.period")
            }
            if let s = loader.value {
                Section(T.totals) {
                    Text(CustomerHoursPresentation.header(s, fallbackName: customerName)).font(.headline)
                    HoursFieldList(fields: CustomerHoursPresentation.totals(s))
                }
                Section(T.usage) {
                    let lines = CustomerHoursPresentation.usage(s)
                    if lines.isEmpty { Text(T.usageEmpty).font(.footnote).foregroundStyle(.secondary) }
                    ForEach(lines, id: \.self) { u in
                        VStack(alignment: .leading, spacing: 2) {
                            LabeledContent(u.label) { Text(u.value).monospacedDigit() }
                            Text(u.caption).font(.caption).foregroundStyle(.secondary)
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
                Section {
                    Button(T.openPDF) { Task { await openPDF(range) } }
                        .buttonStyle(.borderedProminent)
                        .frame(maxWidth: .infinity)
                        .disabled(!model.isOnline || pdfBusy)
                        .accessibilityIdentifier("statement.pdf")
                    if let pdfError { Text(pdfError).font(.caption).foregroundStyle(Palette.offline) }
                } footer: { Text(CustomerHoursPresentation.footer(s)) }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload(range) }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .refreshable { await reload(range) }
        .task(id: model.changeTick) { await reload(range) }
        .quickLookPreview($pdfURL)
    }

    private func reload(_ range: (from: String, to: String)) async {
        await loader.load(model, .hoursStatement(customerID: customerID, from: range.from, to: range.to),
                          OwnerAPI.hoursStatement(customerID: customerID, from: range.from, to: range.to))
    }

    /// Downloads the PDF into the app's temporary folder (one file, overwritten) and previews it.
    private func openPDF(_ range: (from: String, to: String)) async {
        guard let repository = model.repository, !pdfBusy else { return }
        pdfBusy = true
        pdfError = nil
        defer { pdfBusy = false }
        do {
            let raw = try await repository.send(OwnerAPI.hoursStatementPDF(customerID: customerID, from: range.from, to: range.to))
            let dir = FileManager.default.temporaryDirectory.appendingPathComponent("statements", isDirectory: true)
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            let file = dir.appendingPathComponent("hours-statement.pdf")
            try raw.data.write(to: file, options: [.atomic, .completeFileProtection])
            pdfURL = file
        } catch {
            // A refusal from the server says why in its own words; anything else (connection, file) is the generic message.
            if case .server? = error as? APIError { pdfError = DecisionErrorText.message(for: error) } else { pdfError = T.pdfFailed }
            model.handle(error)
        }
    }
}

/// Labelled values (label left, value right).
private struct HoursFieldList: View {
    let fields: [DecisionField]

    var body: some View {
        ForEach(fields, id: \.self) { field in
            LabeledContent(field.label) { Text(field.value).multilineTextAlignment(.trailing) }
        }
    }
}
#endif
