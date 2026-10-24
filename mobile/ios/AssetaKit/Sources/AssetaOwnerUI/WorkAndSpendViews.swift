#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import SwiftUI

/// Meter exceptions (read-only), optionally of one job; reviewing them happens in the web console.
struct ExceptionsView: View {
    let model: OwnerModel
    let jobID: UUID?
    @State private var openOnly = ExceptionText.defaultOpenOnly
    @State private var loader = Loader<Page<MeterExceptionDTO>>()

    var body: some View {
        List {
            SegmentedFilter(options: ExceptionText.filters, selection: $openOnly)
            if let page = loader.value {
                if page.items.isEmpty {
                    EmptyState(title: ExceptionText.empty(openOnly: openOnly), systemImage: "exclamationmark.triangle")
                }
                ForEach(page.items) { RecordLink(model: model, row: ExceptionText.row($0)) }
                FootNote(ExceptionText.footer)
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(ExceptionText.title)
        .refreshable { await reload() }
        .task(id: ReloadKey(tick: model.changeTick, filter: openOnly ? "OPEN" : "ALL")) { await reload() }
    }

    private func reload() async {
        await loader.load(model, .exceptions(openOnly: openOnly, jobID: jobID),
                          OwnerAPI.exceptions(status: openOnly ? "OPEN" : nil, jobID: jobID, pageSize: 100))
    }
}

/// Expenses and fuel recorded in the field (read-only); a row with a job opens it.
struct FieldSpendView: View {
    let model: OwnerModel
    @State private var showFuel = false
    @State private var pendingOnly = SpendText.defaultPendingOnly
    @State private var expenses = Loader<Page<ExpenseDTO>>()
    @State private var fuel = Loader<Page<FuelEventDTO>>()

    var body: some View {
        List {
            SegmentedFilter(options: SpendText.kinds, selection: $showFuel)
            if showFuel {
                if let page = fuel.value {
                    if page.items.isEmpty { EmptyState(title: SpendText.fuelEmpty, systemImage: "fuelpump") }
                    ForEach(page.items) { RecordLink(model: model, row: SpendText.fuelRow($0)) }
                } else if let error = fuel.error {
                    LoadFailure(message: error) { await reload() }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            } else {
                FilterChips(options: SpendText.expenseFilters, selection: $pendingOnly)
                    .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                if let page = expenses.value {
                    if page.items.isEmpty { EmptyState(title: SpendText.expensesEmpty, systemImage: "doc.text") }
                    ForEach(page.items) { RecordLink(model: model, row: SpendText.expenseRow($0)) }
                } else if let error = expenses.error {
                    LoadFailure(message: error) { await reload() }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            }
        }
        .modifier(SpendStaleBanner(loader: showFuel ? nil : expenses, fuel: showFuel ? fuel : nil, model: model))
        .navigationTitle(SpendText.title)
        .refreshable { await reload() }
        .task(id: ReloadKey(tick: model.changeTick, filter: showFuel ? "FUEL" : (pendingOnly ? "PENDING" : "ALL"))) {
            await reload()
        }
    }

    private func reload() async {
        if showFuel {
            await fuel.load(model, .fuel, OwnerAPI.fuelEvents(pageSize: 100))
        } else {
            await expenses.load(model, .expenses(pendingOnly: pendingOnly),
                                OwnerAPI.expenses(status: pendingOnly ? SpendText.pendingStatus : nil, pageSize: 100))
        }
    }
}

/// The stale banner of whichever half of Field spend is showing.
private struct SpendStaleBanner: ViewModifier {
    let loader: Loader<Page<ExpenseDTO>>?
    let fuel: Loader<Page<FuelEventDTO>>?
    let model: OwnerModel

    func body(content: Content) -> some View {
        if let loader {
            content.staleBanner(loader, model: model)
        } else if let fuel {
            content.staleBanner(fuel, model: model)
        } else {
            content
        }
    }
}

/// Cash held by each supervisor over a period (read-only), largest holding first.
struct CashView: View {
    let model: OwnerModel
    @State private var period = CashText.defaultPeriod
    @State private var loader = Loader<[CashSupervisorSummaryDTO]>()

    var body: some View {
        List {
            FilterChips(options: CashPeriod.allCases.map { ($0, $0.label) }, selection: $period)
                .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
            if let items = loader.value {
                let cards = CashText.cards(items)
                if cards.isEmpty { EmptyState(title: CashText.empty, systemImage: "banknote") }
                ForEach(cards, id: \.id) { card in
                    Section {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(CashText.holdingLabel).font(.caption).foregroundStyle(.secondary)
                            Text(card.holding).font(.title2.bold()).monospacedDigit()
                        }
                        .accessibilityElement(children: .combine)
                        ForEach(card.lines, id: \.label) { line in
                            LabeledContent(line.label) {
                                Text(line.value).monospacedDigit().foregroundStyle(line.tone == .warning ? Palette.warning : .secondary)
                            }
                        }
                    } header: {
                        Text(card.title)
                    }
                }
                Section { FootNote(CashText.footer) }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(CashText.title)
        .refreshable { await reload() }
        .task(id: ReloadKey(tick: model.changeTick, filter: period.rawValue)) { await reload() }
    }

    private func reload() async {
        let range = CashText.range(period)
        await loader.load(model, .cash(period), OwnerAPI.cashSupervisorSummary(from: range.from, to: range.to))
    }
}

/// Two-way segmented control as a list row (Android `SegmentedButton` row).
struct SegmentedFilter<Value: Hashable>: View {
    let options: [(Value, String)]
    @Binding var selection: Value

    var body: some View {
        Picker("Filter", selection: $selection) {
            ForEach(Array(options.enumerated()), id: \.offset) { _, option in Text(option.1).tag(option.0) }
        }
        .pickerStyle(.segmented)
        .listRowBackground(Color.clear)
    }
}
#endif
