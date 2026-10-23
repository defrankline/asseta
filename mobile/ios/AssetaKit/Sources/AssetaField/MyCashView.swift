#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaStore
import AssetaSync
import SwiftUI

/// Custody of one currency (Money tab): the server's balance as of the last sync kept apart from what
/// this phone has recorded but the server has not confirmed yet, which is clearly marked unverified.
struct CustodyLineSection: View {
    let line: CashLine
    let base: String?

    var body: some View { lineSection(line, base: base) }

    @ViewBuilder private func lineSection(_ line: CashLine, base: String?) -> some View {
        Section {
            if let synced = line.synced {
                LabeledContent("Synced balance") {
                    Text(MyCashView.money(synced.outstanding.value, line.currency)).font(.title3.monospacedDigit().bold())
                }
                .accessibilityIdentifier("cash.synced.\(line.currency)")
                if synced.claimedUnverifiedHandovers.value != 0 {
                    LabeledContent("Handed over, awaiting verification",
                                   value: MyCashView.money(synced.claimedUnverifiedHandovers.value, line.currency))
                }
                if synced.pendingSpending.value != 0 {
                    LabeledContent("Expenses awaiting approval", value: MyCashView.money(synced.pendingSpending.value, line.currency))
                }
            } else {
                LabeledContent("Synced balance", value: "Not yet received")
            }
            unsyncedRow("Collections not yet synced", "+", line.pendingCollections, line.currency)
            unsyncedRow("Handovers not yet synced", "−", line.pendingHandovers, line.currency)
            unsyncedRow("Cash expenses not yet synced", "−", line.pendingCashExpenses, line.currency)
            LabeledContent("Estimated cash in hand (unverified)") {
                Text(MyCashView.money(line.estimatedInHand, line.currency)).foregroundStyle(Palette.warning).monospacedDigit()
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
                Text(sign + MyCashView.money(amount, currency)).foregroundStyle(Palette.warning).monospacedDigit()
            }
        }
    }
}

/// Shared money formatting of the field finance screens.
enum MyCashView {
    static func money(_ value: Decimal, _ currency: String) -> String {
        let text = DecimalInput.format(value)
        return currency.isEmpty ? text : "\(text) \(currency)"
    }
}
#endif
