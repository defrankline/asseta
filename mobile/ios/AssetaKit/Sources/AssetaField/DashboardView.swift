#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaSync
import SwiftUI

private typealias T = MachineReportTexts
private typealias S = SupervisorShellTexts
private typealias F = SupervisorFigures

/// Pill tone of a machine's report status.
func standingTone(_ standing: MachineReportStanding) -> ShellPill.Tone {
    switch standing {
    case .due, .opening: .due
    case .awaitingApproval: .waiting
    case .upToDate: .good
    }
}

/// Dashboard (design Dashboard): hours sold and used, productive vs non-productive, my machines (list or map) with their
/// report status, and report shortcuts.
struct DashboardView: View {
    let model: FieldModel
    let back: () -> Void
    let open: (FieldRoute) -> Void
    @State private var period: ActivityPeriod = .week
    @State private var showMap = false

    var body: some View {
        let since = period.start()
        let sold = FieldActivity.hoursSold(model.myOperations, since: since)
        let hours = FieldActivity.reportHours(model.myReports, unsent: model.unsentOperations, since: since)
        let total = hours.customers + hours.nonProductive
        VStack(spacing: 0) {
            ShellHeader(T.tileDashboard, action: back) {
                ShellSegments(ActivityPeriod.allCases.map { ($0, $0.label) }, selection: $period)
            }
            ScrollView {
                VStack(spacing: 0) {
                    HStack(spacing: 12) {
                        figure(T.dashHoursSold, "\(F.hours(sold.hours)) h",
                               [model.baseCurrency, F.compact(sold.amount)].compactMap { $0 }.joined(separator: " "))
                        figure(T.dashHoursUsed, "\(F.hours(hours.customers)) h", T.dashFromBought)
                    }
                    .padding(.top, 4)
                    VStack(alignment: .leading, spacing: 0) {
                        HStack {
                            Text(T.dashMachineHours(period.phrase))
                            Spacer()
                            Text("\(F.hours(total)) h")
                        }
                        .font(.system(size: 13)).foregroundStyle(Shell.muted)
                        SplitBar(total > 0 ? [(fraction(hours.customers, total), Shell.accent),
                                              (fraction(hours.nonProductive, total), Shell.nonProductive)] : [], height: 12)
                            .padding(.top, 10)
                        HStack(spacing: 16) {
                            legend(Shell.accent, S.productive(F.hours(hours.customers),
                                                              FieldActivity.productivePercent(customers: hours.customers,
                                                                                              nonProductive: hours.nonProductive)))
                            legend(Shell.nonProductive, T.dashNonProductive(F.hours(hours.nonProductive)))
                        }
                        .padding(.top, 8)
                    }
                    .padding(.horizontal, 16).padding(.vertical, 14)
                    .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                    .padding(.top, 12)

                    HStack {
                        SectionLabel(T.dashMyMachines)
                        if model.canSeeMachineMap {
                            ShellSegments([(false, T.dashList), (true, T.dashMap)], selection: $showMap, compact: true).fixedSize()
                        }
                    }
                    .padding(.top, 18).padding(.bottom, 8)
                    if showMap && model.canSeeMachineMap {
                        MachinesMapView(model: model).frame(height: 320).clipShape(RoundedRectangle(cornerRadius: 18))
                    } else {
                        machineList
                    }

                    SectionLabel(T.dashReports).padding(.top, 18).padding(.bottom, 8)
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible())], spacing: 10) {
                        shortcut(T.dashCustomerBalances) { open(.customerBalances) }
                        shortcut(T.dashMyReports) { open(.myReports) }
                        shortcut(T.dashMySales) { open(.mySales) }
                        shortcut(T.dashMyCash) { open(.moneyRecords) }
                    }
                }
                .padding(.horizontal, 16).padding(.bottom, 16)
            }
            .refreshable { await model.sync(force: true) }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
    }

    @ViewBuilder private var machineList: some View {
        let rows = model.machineStandings
        if rows.isEmpty {
            ShellCard { Text(T.noMachines).foregroundStyle(Shell.muted) }
        } else {
            VStack(spacing: 0) {
                ForEach(Array(rows.enumerated()), id: \.element.state.machineID) { index, row in
                    Button { open(.report(row.state.machineID)) } label: {
                        CardRow([row.state.machineCode, row.state.machineName].compactMap { $0 }.joined(separator: " · "),
                                subtitle: lastReading(row.state),
                                last: index == rows.count - 1) {
                            ShellPill(row.standing.label, tone: standingTone(row.standing))
                        }
                    }
                    .buttonStyle(.plain)
                    .contextMenu {
                        Button(MachineReportTexts.menuReadings, systemImage: "gauge.with.dots.needle.33percent") {
                            open(.machine(row.state.machineID))
                        }
                    }
                    .accessibilityIdentifier("dashboard.machine.\(row.state.machineCode ?? "")")
                }
            }
            .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
        }
    }

    /// "Last reading 1,510 h · today 07:40" (or "No reading yet"), the time of the last report, else of the reading.
    private func lastReading(_ state: MachineReportStatusDTO) -> String {
        S.lastReading(state.previousReading.map { MachineReportRules.hoursText($0.value) },
                      (state.lastReportAt ?? state.previousAt).map { F.ago($0) })
    }

    private func fraction(_ part: Decimal, _ total: Decimal) -> Double {
        total > 0 ? NSDecimalNumber(decimal: part / total).doubleValue : 0
    }

    private func figure(_ title: String, _ value: String, _ detail: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.system(size: 13)).foregroundStyle(Shell.muted)
            Text(value).font(.system(size: 22, weight: .bold)).foregroundStyle(Shell.text).padding(.top, 2)
            Text(detail).font(.system(size: 12)).foregroundStyle(Shell.muted)
        }
        .padding(14).frame(maxWidth: .infinity, alignment: .leading)
        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
    }

    private func legend(_ color: Color, _ text: String) -> some View {
        (Text("■ ").foregroundColor(color) + Text(text).foregroundColor(Shell.text)).font(.system(size: 13))
    }

    private func shortcut(_ title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title).font(.system(size: 14, weight: .semibold)).foregroundStyle(Shell.text)
                .frame(maxWidth: .infinity, minHeight: 52)
                .background(Shell.card, in: RoundedRectangle(cornerRadius: 14))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("dashboard.\(title)")
    }
}

/// "My machine reports": the server's of the last 30 days and those still on this phone. A report the server has opens
/// its read-only detail; one still on this phone opens its machine's report.
struct MyReportsView: View {
    let model: FieldModel
    let open: (FieldRoute) -> Void

    var body: some View {
        let reports = model.myReports
        let server = Set(reports.map(\.id))
        let rows = FieldActivity.reportRows(reports: reports, operations: model.myOperations, machineCode: model.machineCode)
        ScrollView {
            if rows.isEmpty {
                ShellCard { Text(T.dashNoReports).font(.system(size: 14)).foregroundStyle(Shell.muted) }.padding(16)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                        Button {
                            if server.contains(row.id) { open(.myReport(row.id)) } else if let machine = row.machineID { open(.report(machine)) }
                        } label: {
                            VStack(alignment: .leading, spacing: 0) {
                                CardRow(row.title, subtitle: F.when(row.at), last: row.extra != nil || index == rows.count - 1) {
                                    ShellPill(row.pill, tone: recentTone(row.tone))
                                }
                                if let extra = row.extra, !extra.isEmpty {
                                    Text(extra).font(.system(size: 13)).foregroundStyle(Shell.muted)
                                        .padding(.horizontal, 16).padding(.bottom, 12)
                                    if index < rows.count - 1 { Divider().overlay(Shell.border) }
                                }
                            }
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("myReports.\(index)")
                    }
                }
                .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                .padding(16)
            }
        }
        .background(Shell.background.ignoresSafeArea())
        .navigationTitle(T.dashMyReports)
        .refreshable { await model.sync(force: true) }
    }
}

/// "My sales": the hours sales recorded on this phone.
struct MySalesView: View {
    let model: FieldModel

    var body: some View {
        let rows = FieldActivity.saleRows(model.myOperations, customerName: model.customerName,
                                          money: { F.money($0, currency: model.baseCurrency) })
        ScrollView {
            if rows.isEmpty {
                ShellCard { Text(T.dashNoSales).font(.system(size: 14)).foregroundStyle(Shell.muted) }.padding(16)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                        CardRow(row.title, subtitle: [F.when(row.at), row.detail].compactMap { $0 }.joined(separator: " · "),
                                last: index == rows.count - 1) {
                            ShellPill(row.pill, tone: recentTone(row.tone))
                        }
                    }
                }
                .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                .padding(16)
            }
        }
        .background(Shell.background.ignoresSafeArea())
        .navigationTitle(T.dashMySales)
    }
}

/// "Customer balances": each customer's usable hours from the machine report snapshot, offline.
struct CustomerBalancesView: View {
    let model: FieldModel

    var body: some View {
        let rows = FieldActivity.customerBalances(model.reportHours)
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if rows.isEmpty {
                    ShellCard { Text(S.noBalances).font(.system(size: 14)).foregroundStyle(Shell.muted) }
                } else {
                    VStack(spacing: 0) {
                        ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                            CardRow(row.name, last: index == rows.count - 1) {
                                Text(S.hoursUsable(F.hours(row.hours))).font(.system(size: 15, weight: .semibold)).foregroundStyle(Shell.text)
                            }
                        }
                    }
                    .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                }
                Text(S.balancesFooter).font(.system(size: 12)).foregroundStyle(Shell.muted).padding(.horizontal, 4)
            }
            .padding(16)
        }
        .background(Shell.background.ignoresSafeArea())
        .navigationTitle(T.dashCustomerBalances)
        .refreshable { await model.sync(force: true) }
    }
}

func recentTone(_ tone: RecentActivity.Pill) -> ShellPill.Tone {
    switch tone {
    case .waiting: .waiting
    case .good: .good
    case .warning: .due
    case .bad: .bad
    case .neutral: .neutral
    }
}
#endif
