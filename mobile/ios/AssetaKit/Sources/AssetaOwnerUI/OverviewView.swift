#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import SwiftUI

/// Home dashboard: fleet, work, money and risk KPIs with per-section freshness.
struct OverviewView: View {
    let model: OwnerModel
    let open: (OwnerRoute) -> Void
    @State private var loader = Loader<TenantOverviewDTO>()
    private let columns = [GridItem(.adaptive(minimum: 150), spacing: 12)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if loader.isFromCache {
                    StaleBanner(fetchedAt: loader.snapshot?.fetchedAt, isOnline: model.isOnline)
                }
                if let overview = loader.value {
                    if let fleet = overview.fleet { fleetSection(fleet) }
                    if let work = overview.work { workSection(work) }
                    if let money = overview.money { moneySection(money) }
                    if let risk = overview.risk { riskSection(risk) }
                    Text("Computed \(overview.asOf.shortStamp) · \(overview.timezone)")
                        .font(.caption).foregroundStyle(.secondary)
                } else if let error = loader.error {
                    LoadFailure(message: error) { await reload() }
                } else {
                    ProgressView("Loading overview…").frame(maxWidth: .infinity, minHeight: 200)
                }
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle(model.tenant.name)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
        .toolbar {
            if model.features.notifications {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { open(.notifications) } label: {
                        Image(systemName: model.unreadCount > 0 ? "bell.badge" : "bell")
                    }
                    .accessibilityLabel(model.unreadCount > 0 ? "Notifications, \(model.unreadCount) unread" : "Notifications")
                }
            }
        }
    }

    private func reload() async { await loader.load(model, .overview, OwnerAPI.overview()) }

    private func header(_ title: String, _ latest: Date?) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.title3.bold())
            Text(OwnerFormat.sourceFreshness(latest)).font(.caption).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isHeader)
    }

    @ViewBuilder private func fleetSection(_ fleet: OverviewFleetSection) -> some View {
        header("Fleet", fleet.latestSourceAt)
        LazyVGrid(columns: columns, spacing: 12) {
            KPITile(title: "Machines", value: "\(fleet.machines)", systemImage: "truck.box")
            // Live counts describe the moment the server computed them; offline they are history.
            KPITile(title: loader.isFromCache ? "Live when saved" : "Live now", value: "\(fleet.connectivity.live)",
                    tint: loader.isFromCache ? .secondary : .green, systemImage: "dot.radiowaves.left.and.right")
            KPITile(title: "Stale / offline", value: "\(fleet.connectivity.stale + fleet.connectivity.offline)",
                    tint: Brand.amber, systemImage: "wifi.exclamationmark")
            KPITile(title: "Engine on (verified)", value: "\(fleet.engineOnVerified)", systemImage: "engine.combustion")
            Button { open(.alerts) } label: {
                KPITile(title: "Open alerts", value: "\(fleet.openAlerts.total)",
                        tint: fleet.openAlerts.critical > 0 ? .red : .primary, systemImage: "exclamationmark.triangle")
            }
            .buttonStyle(.plain)
            .accessibilityHint("\(fleet.openAlerts.critical) critical. Opens alerts.")
            KPITile(title: "No tracker / never", value: "\(fleet.connectivity.noTracker + fleet.connectivity.never)",
                    tint: .secondary, systemImage: "antenna.radiowaves.left.and.right.slash")
        }
    }

    @ViewBuilder private func workSection(_ work: OverviewWorkSection) -> some View {
        header("Work", work.latestSourceAt)
        LazyVGrid(columns: columns, spacing: 12) {
            KPITile(title: "In progress", value: "\(work.jobsByStatus["IN_PROGRESS"] ?? 0)", tint: .blue,
                    systemImage: "play.circle")
            KPITile(title: "Approved, not started", value: "\(work.jobsByStatus["APPROVED"] ?? 0)",
                    systemImage: "checkmark.circle")
            if let approvals = work.pendingApprovals {
                Button { open(.approvals) } label: {
                    KPITile(title: "Pending approvals", value: "\(approvals)", tint: approvals > 0 ? .orange : .primary,
                            systemImage: "checkmark.seal")
                }
                .buttonStyle(.plain)
                .accessibilityHint("Opens approvals.")
            }
            if let review = work.readingsNeedingReview {
                KPITile(title: "Readings to review", value: "\(review)", systemImage: "gauge.with.needle")
            }
            if let exceptions = work.openExceptions {
                KPITile(title: "Open exceptions", value: "\(exceptions)", systemImage: "exclamationmark.bubble")
            }
        }
    }

    @ViewBuilder private func moneySection(_ money: OverviewMoneySection) -> some View {
        header("Money (since \(money.monthStart))", money.latestSourceAt)
        if money.currencies.isEmpty {
            Text("No financial activity this month.").foregroundStyle(.secondary)
        }
        ForEach(money.currencies) { row in
            VStack(alignment: .leading, spacing: 8) {
                Text(row.currency).font(.headline)
                LazyVGrid(columns: columns, spacing: 12) {
                    KPITile(title: "Receivables", value: OwnerFormat.money(row.receivablesOutstanding, currency: row.currency))
                    KPITile(title: "Overdue (\(row.overdueInvoices))",
                            value: OwnerFormat.money(row.receivablesOverdue, currency: row.currency),
                            tint: row.overdueInvoices > 0 ? .red : .primary)
                    KPITile(title: "Receipts (verified)",
                            value: OwnerFormat.money(row.verifiedReceiptsMTD, currency: row.currency), tint: .green)
                    KPITile(title: "Expenses (approved)",
                            value: OwnerFormat.money(row.approvedExpensesMTD, currency: row.currency))
                    KPITile(title: "Cash with supervisors",
                            value: OwnerFormat.money(row.cashWithSupervisors, currency: row.currency))
                }
            }
        }
    }

    @ViewBuilder private func riskSection(_ risk: OverviewRiskSection) -> some View {
        header("Risk", risk.latestSourceAt)
        LazyVGrid(columns: columns, spacing: 12) {
            if let cases = risk.openCases {
                KPITile(title: "Open investigations", value: "\(cases.total)", tint: cases.critical > 0 ? .red : .primary,
                        systemImage: "doc.text.magnifyingglass")
            }
            if let signals = risk.signalsLast7Days {
                KPITile(title: "Signals (7 days)", value: "\(signals.total)", systemImage: "waveform.path.ecg")
            }
        }
    }
}
#endif
