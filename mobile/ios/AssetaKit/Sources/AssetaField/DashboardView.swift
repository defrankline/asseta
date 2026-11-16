#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaSync
import SwiftUI

private typealias T = MachineReportTexts

/// Pill tone of a machine's report status.
func standingTone(_ standing: MachineReportStanding) -> ShellPill.Tone {
    switch standing {
    case .due, .opening: .due
    case .awaitingApproval: .waiting
    case .rejected: .bad
    case .upToDate: .good
    }
}

/// Relative day of a reading ("today 07:40", "yesterday", "3 days ago").
func relativeDay(_ date: Date, now: Date = Date(), calendar: Calendar = .current) -> String {
    let days = calendar.dateComponents([.day], from: calendar.startOfDay(for: date), to: calendar.startOfDay(for: now)).day ?? 0
    switch days {
    case ..<1: return "today " + date.formatted(date: .omitted, time: .shortened)
    case 1: return "yesterday"
    default: return "\(days) days ago"
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
        let sales = FieldActivity.salesByMethod(model.myOperations, since: since)
        let hours = FieldActivity.reportHours(model.myReports, unsent: model.unsentOperations, since: since)
        let total = hours.customers + hours.nonProductive
        VStack(spacing: 0) {
            ShellHeader(T.tileDashboard, action: back) {
                ShellSegments(ActivityPeriod.allCases.map { ($0, $0.label) }, selection: $period)
            }
            ScrollView {
                VStack(spacing: 0) {
                    HStack(spacing: 12) {
                        figure(T.dashHoursSold, "\(MachineReportRules.hoursText(sales.hours)) h",
                               model.baseCurrency.map { "\($0) \(model.shortMoney(sales.total))" } ?? model.shortMoney(sales.total))
                        figure(T.dashHoursUsed, "\(MachineReportRules.hoursText(hours.customers)) h", T.dashFromBought)
                    }
                    .padding(.top, 4)
                    VStack(alignment: .leading, spacing: 0) {
                        HStack {
                            Text(T.dashMachineHours(period.phrase))
                            Spacer()
                            Text("\(MachineReportRules.hoursText(total)) h")
                        }
                        .font(.system(size: 13)).foregroundStyle(Shell.muted)
                        SplitBar(total > 0 ? [(fraction(hours.customers, total), Shell.accent),
                                              (fraction(hours.nonProductive, total), Shell.nonProductive)] : [], height: 12)
                            .padding(.top, 10)
                        HStack(spacing: 16) {
                            legend(Shell.accent, T.dashProductive(MachineReportRules.hoursText(hours.customers),
                                                                  FieldActivity.productivePercent(customers: hours.customers,
                                                                                                  nonProductive: hours.nonProductive)))
                            legend(Shell.nonProductive, T.dashNonProductive(MachineReportRules.hoursText(hours.nonProductive)))
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
                        shortcut(T.dashCustomerBalances) { open(.customers) }
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
                                subtitle: row.state.previousReading.map {
                                    T.dashLastReading(MachineReportRules.hoursText($0.value),
                                                      row.state.previousAt.map { relativeDay($0) } ?? "")
                                } ?? T.dashNoReading,
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

/// "My machine reports": my reports of the last 30 days (and any waiting), with their decision.
struct MyReportsView: View {
    let model: FieldModel

    var body: some View {
        let reports = model.myReports
        List {
            if reports.isEmpty { ContentUnavailableView(T.dashMyReports, systemImage: "gauge", description: Text(T.dashNoReports)) }
            ForEach(reports) { report in
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("\(report.machineCode ?? "") · \(report.reportNumber)").font(.headline)
                        Spacer()
                        ShellPill(report.state == .approved ? T.pillApproved : report.state == .rejected ? T.pillRejected : T.pillAwaiting,
                                   tone: report.state == .approved ? .good : report.state == .rejected ? .bad : .waiting)
                    }
                    Text(T.readingRange(MachineReportRules.hoursText(report.startReading.value),
                                        MachineReportRules.hoursText(report.endReading.value)))
                    Text("\(T.productiveHeader(MachineReportRules.hoursText(report.customerHours.value))) · "
                         + T.nonProductiveHeaderTotal(MachineReportRules.hoursText(report.nonProductiveHours.value)))
                        .font(.caption).foregroundStyle(.secondary)
                    if let note = report.decisionNote { Text(T.rejectedReason(note)).font(.caption).foregroundStyle(.secondary) }
                    Text(report.submittedAt.formatted(date: .abbreviated, time: .shortened)).font(.caption).foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle(T.dashMyReports)
        .refreshable { await model.sync(force: true) }
    }
}

/// "My sales": the sales and invoice payments recorded on this phone.
struct MySalesView: View {
    let model: FieldModel

    var body: some View {
        let rows = FieldActivity.recent(reports: [], operations: model.myOperations, machineCode: model.machineCode,
                                        customerName: model.customerName, money: { model.money($0) }, limit: 200)
            .filter { $0.machineID == nil }
        List {
            if rows.isEmpty { ContentUnavailableView(T.dashMySales, systemImage: "clock", description: Text(T.dashNoSales)) }
            ForEach(rows) { row in
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(row.title).font(.headline)
                        Text([row.at.formatted(date: .abbreviated, time: .shortened), row.detail].compactMap { $0 }.joined(separator: " · "))
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    ShellPill(row.pill, tone: recentTone(row.tone))
                }
            }
        }
        .navigationTitle(T.dashMySales)
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
