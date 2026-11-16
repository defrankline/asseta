#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaSync
import SwiftUI

private typealias T = MachineReportTexts

/// Supervisor Home (design Main): sync pill, greeting, summary strip (cash in hand, hours to report, awaiting approval),
/// the four tiles and Recent.
struct SupervisorHomeView: View {
    let model: FieldModel
    let userName: String
    let openMenu: () -> Void
    let open: (FieldRoute) -> Void

    var body: some View {
        let a = model.access
        let due = model.reportsDue
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    SquareButton("line.3.horizontal", label: "Open menu", action: openMenu).accessibilityIdentifier("menu.open")
                    Spacer()
                    Button { open(.syncStatus) } label: { syncPill }.buttonStyle(.plain).accessibilityIdentifier("sync.status")
                }
                .padding(.top, 8)
                VStack(alignment: .leading, spacing: 2) {
                    Text(T.greeting(userName, hour: Calendar.current.component(.hour, from: Date())))
                        .font(.system(size: 14)).foregroundStyle(Shell.muted)
                    Text(model.tenant.name).font(.system(size: 26, weight: .bold)).tracking(-0.4).foregroundStyle(Shell.text)
                }
                .padding(.top, 8).padding(.bottom, 18)
                VStack(alignment: .leading, spacing: 8) {
                    if let reason = AccessBanner.text(model.tenant) { AccessReasonBanner(text: reason) }
                    FieldBanners(model: model)
                }
                .padding(.bottom, 4)
                summary(due: due)
                SectionLabel(T.whatToDo).padding(.top, 22).padding(.bottom, 10)
                LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible())], spacing: 12) {
                    if a.sellHours {
                        HomeTile(T.tileSellHours, subtitle: T.tileSellHoursSub, systemImage: "clock", primary: true) { open(.sellHours) }
                    }
                    if a.machineReport {
                        HomeTile(T.tileReport, subtitle: T.tileReportSub, systemImage: "gauge.with.needle",
                                 badge: due > 0 ? T.dueBadge(due) : nil) { open(.report(nil)) }
                    }
                    HomeTile(T.tileMoney, subtitle: T.tileMoneySub, systemImage: "banknote") { open(.money) }
                    HomeTile(T.tileDashboard, subtitle: T.tileDashboardSub, systemImage: "chart.bar") { open(.dashboard) }
                }
                SectionLabel(T.recent).padding(.top, 22).padding(.bottom, 10)
                recent
            }
            .padding(.horizontal, 20).padding(.bottom, 24)
        }
        .refreshable { await model.sync(force: true); await model.refreshAccountability() }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
    }

    private var syncPill: some View {
        let unsynced = model.overview?.unsyncedCount ?? 0
        let attention = (model.overview?.counts[.failed] ?? 0) + (model.overview?.counts[.conflict] ?? 0)
        return HStack(spacing: 8) {
            if model.isSyncing {
                ProgressView().controlSize(.small)
            } else {
                Image(systemName: attention > 0 ? "exclamationmark.triangle" : unsynced > 0 ? "arrow.triangle.2.circlepath" : "checkmark")
                    .foregroundStyle(attention > 0 ? Shell.badText : unsynced > 0 ? Shell.warnText : Shell.check)
            }
            Text(model.isSyncing ? T.syncing : unsynced > 0 ? T.notSynced(unsynced) : T.allSynced)
        }
        .font(.system(size: 13)).foregroundStyle(Shell.muted)
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(Shell.card, in: Capsule())
    }

    private func summary(due: Int) -> some View {
        let summary = model.cashSummary()
        let base = summary?.baseCurrency ?? model.baseCurrency
        let line = summary?.lines.first { $0.currency == base } ?? summary?.lines.first
        return HStack(alignment: .top, spacing: 8) {
            stat(T.cashInHand, model.shortMoney(line?.estimatedInHand ?? 0))
            if model.access.machineReport {
                stat(T.hoursToReport, T.machinesCount(due), highlight: due > 0)
                stat(T.awaitingApproval, "\(model.reportsAwaiting)")
            }
        }
        .padding(16)
        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
    }

    private func stat(_ title: String, _ value: String, highlight: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.system(size: 12)).foregroundStyle(Shell.muted)
            Text(value).font(.system(size: 17, weight: .bold)).foregroundStyle(highlight ? Shell.accent : Shell.text)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder private var recent: some View {
        let rows = FieldActivity.recent(reports: model.myReports, operations: model.myOperations, machineCode: model.machineCode,
                                        customerName: model.customerName, money: { model.money($0) })
        if rows.isEmpty {
            ShellCard { Text(T.recentEmpty).font(.system(size: 14)).foregroundStyle(Shell.muted) }
        } else {
            VStack(spacing: 0) {
                ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                    Button {
                        if row.machineID != nil { open(.myReports) } else { open(.mySales) }
                    } label: {
                        CardRow(row.title, subtitle: [timeText(row.at), row.detail].compactMap { $0 }.joined(separator: " · "),
                                last: index == rows.count - 1) {
                            ShellPill(row.pill, tone: recentTone(row.tone))
                        }
                    }
                    .buttonStyle(.plain)
                }
            }
            .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
        }
    }

    /// "Today 07:40", "Yesterday 16:05", else the date and time.
    private func timeText(_ date: Date) -> String {
        let time = date.formatted(date: .omitted, time: .shortened)
        if Calendar.current.isDateInToday(date) { return "Today \(time)" }
        if Calendar.current.isDateInYesterday(date) { return "Yesterday \(time)" }
        return date.formatted(.dateTime.day().month(.abbreviated).hour().minute())
    }
}
#endif
