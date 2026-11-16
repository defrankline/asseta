#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

private typealias T = MachineReportOwnerTexts

/// The ADR-008 Owner screens pushed on the shell's stack.
enum OwnerScreen: Hashable { case approvals, customers, machines, money, reports, settings }

/// Local days (`YYYY-MM-DD`) of a period for the server's date filters.
enum OwnerPeriod: String, CaseIterable, Hashable {
    case today, week, month

    var label: String {
        switch self {
        case .today: "Today"
        case .week: "Week"
        case .month: "Month"
        }
    }

    /// "this week", "November" (headers).
    var phrase: String {
        switch self {
        case .today: "today"
        case .week: "this week"
        case .month: Date().formatted(.dateTime.month(.wide))
        }
    }

    var range: (from: String, to: String) {
        let calendar = Calendar.current
        let now = Date()
        let start: Date = switch self {
        case .today: calendar.startOfDay(for: now)
        case .week: calendar.dateInterval(of: .weekOfYear, for: now)?.start ?? now
        case .month: calendar.dateInterval(of: .month, for: now)?.start ?? now
        }
        return (Self.day(start), Self.day(now))
    }

    static func day(_ date: Date) -> String {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: date)
    }

    /// "2026-11-30" → "30 Nov".
    static func short(_ text: String?) -> String? {
        guard let text else { return nil }
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f.date(from: text).map { $0.formatted(.dateTime.day().month(.abbreviated)) } ?? text
    }
}

func greeting(_ name: String) -> String {
    let hour = Calendar.current.component(.hour, from: Date())
    let part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"
    let first = name.split(separator: " ").first.map(String.init) ?? ""
    return first.isEmpty ? part : "\(part), \(first)"
}

/// Owner Home (design OwnerHome): menu and notifications, greeting, summary strip, the tiles the role may open and
/// "Needs your attention" (Android `OwnerHomeScreen`).
struct OwnerHomeView: View {
    let model: OwnerModel
    let queues: ApprovalQueues
    let openMenu: () -> Void
    let push: (AnyHashable) -> Void
    @State private var overview = Loader<TenantOverviewDTO>()
    @State private var states = Loader<[MachineReportStatusDTO]>()
    @State private var policy = Loader<EffectivePolicyDTO<CustomerHoursPolicyValues>>()
    @State private var week = Loader<Page<MachineReportDTO>>()
    @State private var sold = Loader<Page<HoursPurchaseDTO>>()

    var body: some View {
        let f = model.features
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    SquareButton("line.3.horizontal", label: "Open menu", action: openMenu).accessibilityIdentifier("menu.open")
                    Spacer()
                    if f.notifications {
                        Button { push(OwnerRoute.notifications) } label: {
                            Image(systemName: "bell").font(.system(size: 18, weight: .semibold)).foregroundStyle(Shell.text)
                                .frame(width: 44, height: 44).background(Shell.card, in: RoundedRectangle(cornerRadius: 12))
                                .overlay(alignment: .topTrailing) {
                                    if let badge = OwnerFormat.badge(model.unreadCount) { CountBadge(badge, red: true).offset(x: 6, y: -6) }
                                }
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel(OwnerHomeTexts.bell(unread: model.unreadCount))
                    }
                }
                .padding(.top, 8)
                VStack(alignment: .leading, spacing: 2) {
                    Text(greeting(model.me.displayName)).font(.system(size: 14)).foregroundStyle(Shell.muted)
                    Text(model.tenant.name).font(.system(size: 26, weight: .bold)).tracking(-0.4).foregroundStyle(Shell.text)
                }
                .padding(.top, 8).padding(.bottom, 18)
                if f.finance || f.hoursRead || f.machineReports { summary }
                if f.approvalsScreen || f.customersScreen || f.machinesScreen || f.moneyScreen {
                    SectionLabel(T.yourBusiness).padding(.top, 22).padding(.bottom, 10)
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible())], spacing: 12) {
                        if f.approvalsScreen {
                            HomeTile(T.tileApprovals, subtitle: T.tileApprovalsSub, systemImage: "checkmark.seal", primary: true,
                                     badge: queues.counts.waiting) { push(OwnerScreen.approvals) }
                        }
                        if f.customersScreen {
                            HomeTile(T.tileCustomers, subtitle: T.tileCustomersSub, systemImage: "person.2") { push(OwnerScreen.customers) }
                        }
                        if f.machinesScreen {
                            HomeTile(T.tileMachines, subtitle: T.tileMachinesSub, systemImage: "map") { push(OwnerScreen.machines) }
                        }
                        if f.moneyScreen {
                            HomeTile(T.tileMoney, subtitle: T.tileMoneySub, systemImage: "banknote") { push(OwnerScreen.money) }
                        }
                    }
                }
                if f.machineReports {
                    SectionLabel(T.needsAttention).padding(.top, 22).padding(.bottom, 10)
                    attention
                }
            }
            .padding(.horizontal, 20).padding(.bottom, 24)
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private var summary: some View {
        HStack(alignment: .top, spacing: 8) {
            if model.features.finance { stat(T.cashWithSupervisors, OwnerHomePresentation.cash(overview.value)) }
            if model.features.hoursRead { stat(T.hoursSoldWeek, OwnerHomePresentation.hoursSold(sold.value?.items)) }
            if model.features.machineReports {
                stat(T.productive, OwnerHomePresentation.productive(week.value?.items), accent: true)
            }
        }
        .padding(16)
        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
    }

    private func stat(_ title: String, _ value: String, accent: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.system(size: 12)).foregroundStyle(Shell.muted)
            Text(value).font(.system(size: 17, weight: .bold)).foregroundStyle(accent ? Shell.accent : Shell.text)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder private var attention: some View {
        let rows = AttentionRow.rows(pending: queues.reports.value?.items ?? [], states: states.value ?? [],
                                     reminderDays: policy.reminderDays)
        if rows.isEmpty {
            Text(T.nothingNeedsYou).font(.system(size: 14)).foregroundStyle(Shell.muted)
        } else {
            VStack(spacing: 0) {
                ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                    Button {
                        switch row.kind {
                        case let .report(id): push(OwnerRoute.machineReport(id))
                        case let .missing(id): if model.features.fleet { push(OwnerRoute.machine(id)) }
                        }
                    } label: {
                        CardRow(row.title, subtitle: row.detail, last: index == rows.count - 1) {
                            if case .report = row.kind {
                                ShellPill(row.pill, tone: .due)
                            } else {
                                ShellPill(row.pill, tone: .bad)
                            }
                        }
                    }
                    .buttonStyle(.plain)
                }
            }
            .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
        }
    }

    private func reload() async {
        let f = model.features
        let week = OwnerPeriod.week.range
        if f.finance { await overview.load(model, .overview, OwnerAPI.overview()) }
        if f.machineReports {
            await states.load(model, .machineReportStatus, OwnerAPI.machineReportStatus())
            await policy.load(model, .customerHoursPolicy, OwnerAPI.customerHoursPolicy())
            await self.week.load(model, .machineReports(from: week.from, to: week.to), OwnerAPI.machineReports(from: week.from, to: week.to))
        }
        if f.hoursRead {
            await sold.load(model, .hoursPurchases(from: week.from, to: week.to), OwnerAPI.hoursPurchases(from: week.from, to: week.to))
        }
        await queues.reload(model)
        await model.refreshUnread()
    }
}

/// The Owner side menu (design OwnerSideNav, Android `OwnerDrawerSheet`): who is signed in, the business screens, the
/// "MORE" group, then Switch company, Settings and Sign out.
struct OwnerMenu: View {
    let model: OwnerModel
    let queues: ApprovalQueues
    let current: OwnerMenuEntry?
    let go: (OwnerMenuEntry) -> Void
    let switchCompany: (() -> Void)?
    let settings: () -> Void
    let signOut: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            DrawerHeader(name: model.me.displayName, detail: model.tenant.name)
            Divider().overlay(Shell.border)
            ScrollView {
                VStack(spacing: 4) {
                    ForEach(model.features.menuGroups, id: \.header) { group in
                        if let header = group.header {
                            Text(header.uppercased()).font(.system(size: 12, weight: .semibold)).tracking(0.6).foregroundStyle(Shell.muted)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.leading, 12).padding(.top, 16).padding(.bottom, 4)
                                .accessibilityAddTraits(.isHeader)
                        }
                        ForEach(group.entries, id: \.self) { entry in
                            DrawerRow(entry.label, systemImage: Self.icon(entry), selected: current == entry, badge: badge(entry),
                                      redBadge: entry == .notifications, small: group.header != nil) { go(entry) }
                        }
                    }
                }
                .padding(.top, 14)
            }
            Divider().overlay(Shell.border)
            VStack(spacing: 4) {
                if let switchCompany {
                    DrawerRow(OwnerMenuTexts.switchCompany, systemImage: "arrow.left.arrow.right.square", small: true, action: switchCompany)
                }
                DrawerRow(OwnerMenuTexts.settings, systemImage: "gearshape", small: true, action: settings)
                DrawerRow(OwnerMenuTexts.signOut, systemImage: "rectangle.portrait.and.arrow.right", small: true, action: signOut)
                if model.isReadOnlyTenant {
                    Text(OwnerMenuTexts.readOnly).font(.system(size: 12)).foregroundStyle(Shell.faint).padding(.horizontal, 12).padding(.top, 6)
                }
            }
            .padding(.top, 12)
        }
        .padding(.horizontal, 16).padding(.top, 56).padding(.bottom, 24)
    }

    private func badge(_ entry: OwnerMenuEntry) -> String? {
        switch entry {
        case .approvals: queues.counts.badge
        case .notifications: OwnerFormat.badge(model.unreadCount)
        default: nil
        }
    }

    static func icon(_ entry: OwnerMenuEntry) -> String {
        switch entry {
        case .home: "house"
        case .approvals: "checkmark.seal"
        case .customers: "person.2"
        case .machines: "map"
        case .money: "banknote"
        case .reports: "chart.bar"
        case .notifications: "bell"
        case .setup: "checklist"
        case .dashboard: "square.grid.2x2"
        case .accountability: "checkmark.shield"
        case .lookup: "magnifyingglass"
        case .scorecard: "person.text.rectangle"
        case .fleet: "map.circle"
        case .alerts: "exclamationmark.bubble"
        case .exceptions: "exclamationmark.triangle"
        case .fieldSpend: "receipt"
        case .cash: "banknote"
        case .investigations: "doc.text.magnifyingglass"
        }
    }
}

#endif
