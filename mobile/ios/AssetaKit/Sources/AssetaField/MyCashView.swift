#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaStore
import AssetaSync
import SwiftUI

/// My cash: the server's custody balance (as of the last sync) kept apart from what this phone has
/// recorded but the server has not confirmed yet, which is clearly marked unverified.
struct MyCashView: View {
    let model: FieldModel

    var body: some View {
        let summary = model.cashSummary()
        List {
            if let summary, !summary.lines.isEmpty {
                ForEach(summary.lines) { line in lineSection(line, base: summary.baseCurrency) }
            } else {
                ContentUnavailableView("No cash balance yet", systemImage: "banknote",
                                       description: Text("Your cash custody appears here after a sync."))
            }
            if let summary, !summary.pending.isEmpty {
                Section {
                    ForEach(summary.pending) { item in ItemRow(item: item, base: summary.baseCurrency) }
                } header: { Text("Not yet confirmed (\(summary.pending.count))") } footer: {
                    Text("Recorded on this phone. Not verified: the server has not accepted these yet, so they are not in the synced balance.")
                }
            }
            if let summary, !summary.needsAttention.isEmpty {
                Section {
                    ForEach(summary.needsAttention) { item in ItemRow(item: item, base: summary.baseCurrency) }
                } header: { Text("Needs attention") } footer: {
                    Text("Refused by the server or in conflict. Not counted. See Sync status for details.")
                }
            }
        }
        .navigationTitle("My cash")
        .refreshable { await model.sync(force: true) }
        .accessibilityIdentifier("cash.my")
    }

    @ViewBuilder private func lineSection(_ line: CashLine, base: String?) -> some View {
        Section {
            if let synced = line.synced {
                LabeledContent("Synced balance") {
                    Text(Self.money(synced.outstanding.value, line.currency)).font(.title3.monospacedDigit().bold())
                }
                .accessibilityIdentifier("cash.synced.\(line.currency)")
                if synced.claimedUnverifiedHandovers.value != 0 {
                    LabeledContent("Handed over, awaiting verification",
                                   value: Self.money(synced.claimedUnverifiedHandovers.value, line.currency))
                }
                if synced.pendingSpending.value != 0 {
                    LabeledContent("Expenses awaiting approval", value: Self.money(synced.pendingSpending.value, line.currency))
                }
            } else {
                LabeledContent("Synced balance", value: "Not yet received")
            }
            unsyncedRow("Collections not yet synced", "+", line.pendingCollections, line.currency)
            unsyncedRow("Handovers not yet synced", "−", line.pendingHandovers, line.currency)
            unsyncedRow("Cash expenses not yet synced", "−", line.pendingCashExpenses, line.currency)
            LabeledContent("Estimated cash in hand (unverified)") {
                Text(Self.money(line.estimatedInHand, line.currency)).foregroundStyle(Palette.warning).monospacedDigit()
            }
            .accessibilityIdentifier("cash.estimated.\(line.currency)")
        } header: {
            Text(line.currency.isEmpty ? (base ?? "Company currency") : line.currency)
        } footer: {
            if let asOf = line.synced?.asOf {
                Text("Synced balance as of \(asOf.formatted(date: .abbreviated, time: .shortened)): cash floats and collections minus approved expenses and verified handovers.")
            }
        }
    }

    /// One unsynced (unverified) part of the estimate; hidden when zero.
    @ViewBuilder private func unsyncedRow(_ title: String, _ sign: String, _ amount: Decimal, _ currency: String) -> some View {
        if amount != 0 {
            LabeledContent(title) {
                Text(sign + Self.money(amount, currency)).foregroundStyle(Palette.warning).monospacedDigit()
            }
        }
    }

    static func money(_ value: Decimal, _ currency: String) -> String {
        let text = DecimalInput.format(value)
        return currency.isEmpty ? text : "\(text) \(currency)"
    }

    struct ItemRow: View {
        let item: LocalCashItem
        let base: String?

        var body: some View {
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(item.title).font(.subheadline)
                    Spacer()
                    Text((item.sign > 0 ? "+" : "−") + MyCashView.money(item.amount, item.currency ?? base ?? ""))
                        .monospacedDigit()
                }
                HStack {
                    Text(item.at.formatted(date: .abbreviated, time: .shortened))
                    Spacer()
                    Text(Self.label(item)).foregroundStyle(item.status == .failed || item.status == .conflict ? Palette.offline : Palette.warning)
                }
                .font(.caption).foregroundStyle(.secondary)
            }
        }

        static func label(_ item: LocalCashItem) -> String {
            switch item.status {
            case .failed: "Rejected\(item.errorCode.map { ": \($0)" } ?? "")"
            case .conflict: "Conflict"
            case .quarantined: "Held (read-only subscription) · unverified"
            default: "Waiting to sync · unverified"
            }
        }
    }
}

/// Home-screen entry points for field finance, shown according to `/me` permissions.
struct FinanceSection: View {
    let model: FieldModel
    @State private var sheet: Sheet?
    @State private var blockedMessage: String?

    enum Sheet: String, Identifiable {
        case expense, collection, handover, fuel
        var id: String { rawValue }
    }

    var body: some View {
        if model.canRecordExpenses || model.canRecordCash {
            Section("Money & fuel") {
                if model.canRecordExpenses {
                    Button("Record expense", systemImage: "doc.text.viewfinder") { openExpense() }
                        .accessibilityIdentifier("finance.expense")
                }
                if model.canRecordCash {
                    Button("Record cash collection", systemImage: "banknote") { sheet = .collection }
                        .accessibilityIdentifier("finance.collection")
                    Button("Hand over cash", systemImage: "arrow.up.forward.circle") { sheet = .handover }
                        .accessibilityIdentifier("finance.handover")
                }
                if model.canRecordExpenses {
                    Button("Fuel event", systemImage: "fuelpump") { sheet = .fuel }
                        .accessibilityIdentifier("finance.fuel")
                }
                if model.canRecordCash {
                    NavigationLink { MyCashView(model: model).navigationBarTitleDisplayMode(.inline) } label: { Label("My cash", systemImage: "wallet.pass") }
                        .accessibilityIdentifier("finance.mycash")
                }
            }
            .sheet(item: $sheet) { kind in
                switch kind {
                case .expense:
                    if case let .allowed(snapshot) = model.expenseGate() { ExpenseFormView(model: model, snapshot: snapshot) }
                case .collection: CashCollectionFormView(model: model)
                case .handover: CashHandoverFormView(model: model)
                case .fuel: FuelFormView(model: model)
                }
            }
            .alert("Can't record an expense now", isPresented: Binding(get: { blockedMessage != nil },
                                                                     set: { if !$0 { blockedMessage = nil } })) {
                Button("OK") { blockedMessage = nil }
            } message: { Text(blockedMessage ?? "") }
        }
    }

    private func openExpense() {
        switch model.expenseGate() {
        case .allowed: sheet = .expense
        case let .blocked(reason): blockedMessage = reason.expenseMessage
        }
    }
}
#endif
