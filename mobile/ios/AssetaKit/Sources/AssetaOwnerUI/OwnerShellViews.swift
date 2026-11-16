#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

private typealias T = MachineReportOwnerTexts

/// The ADR-008 Owner screens pushed on the shell's stack.
enum OwnerScreen: Hashable { case approvals, customers, machines, money, reports, more, settings }

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

/// Owner Home (design OwnerHome): menu and notifications, greeting, summary strip, the four tiles and "Needs your
/// attention".
struct OwnerHomeView: View {
    let model: OwnerModel
    let openMenu: () -> Void
    let push: (AnyHashable) -> Void
    @State private var pending = Loader<Page<MachineReportDTO>>()
    @State private var states = Loader<[MachineReportStatusDTO]>()
    @State private var policy = Loader<EffectivePolicyDTO<CustomerHoursPolicyValues>>()
    @State private var week = Loader<Page<MachineReportDTO>>()
    @State private var sold = Loader<Page<HoursPurchaseDTO>>()
    @State private var cash = Loader<[CashSupervisorSummaryDTO]>()
    @State private var credit = Loader<Page<HoursPurchaseDTO>>()
    @State private var approvals = Loader<Page<ApprovalRequestDTO>>()

    var body: some View {
        let f = model.features
        let waiting = (pending.value?.items.count ?? 0) + (credit.value?.items.count ?? 0) + (approvals.value?.items.count ?? 0)
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
                        .accessibilityLabel("Notifications, \(model.unreadCount) unread")
                    }
                }
                .padding(.top, 8)
                VStack(alignment: .leading, spacing: 2) {
                    Text(greeting(model.me.displayName)).font(.system(size: 14)).foregroundStyle(Shell.muted)
                    Text(model.tenant.name).font(.system(size: 26, weight: .bold)).tracking(-0.4).foregroundStyle(Shell.text)
                }
                .padding(.top, 8).padding(.bottom, 18)
                summary
                SectionLabel(T.yourBusiness).padding(.top, 22).padding(.bottom, 10)
                LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible())], spacing: 12) {
                    HomeTile(T.tileApprovals, subtitle: T.tileApprovalsSub, systemImage: "checkmark.seal", primary: true,
                             badge: waiting > 0 ? T.waiting(waiting) : nil) { push(OwnerScreen.approvals) }
                    if f.hoursRead {
                        HomeTile(T.tileCustomers, subtitle: T.tileCustomersSub, systemImage: "person.2") { push(OwnerScreen.customers) }
                    }
                    HomeTile(T.tileMachines, subtitle: T.tileMachinesSub, systemImage: "map") { push(OwnerScreen.machines) }
                    HomeTile(T.tileMoney, subtitle: T.tileMoneySub, systemImage: "banknote") { push(OwnerScreen.money) }
                }
                SectionLabel(T.needsAttention).padding(.top, 22).padding(.bottom, 10)
                attention
            }
            .padding(.horizontal, 20).padding(.bottom, 24)
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private var summary: some View {
        let cashTotal = (cash.value ?? []).reduce(Decimal(0)) { $0 + $1.closingOutstanding.value }
        let hours = SoldByMethod.of(sold.value?.items ?? []).hours
        let productive = MachineHoursSummary.of(week.value?.items ?? []).productivePercent
        return HStack(alignment: .top, spacing: 8) {
            if model.features.finance { stat(T.cashWithSupervisors, T.short(cashTotal)) }
            if model.features.hoursRead { stat(T.hoursSoldWeek, "\(T.h(hours)) h") }
            if model.features.machineReports { stat(T.productive, "\(productive)%", accent: true) }
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
        let rows = AttentionRow.rows(pending: pending.value?.items ?? [], states: states.value ?? [],
                                     reminderDays: policy.reminderDays)
        if rows.isEmpty {
            ShellCard { Text(T.nothingNeedsYou).font(.system(size: 14)).foregroundStyle(Shell.muted) }
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
        let today = OwnerPeriod.today.range
        if f.machineReports {
            await pending.load(model, .machineReportQueue, OwnerAPI.machineReports(pending: true))
            await states.load(model, .machineReportStatus, OwnerAPI.machineReportStatus())
            await policy.load(model, .customerHoursPolicy, OwnerAPI.customerHoursPolicy())
            await self.week.load(model, .machineReports(from: week.from, to: week.to), OwnerAPI.machineReports(from: week.from, to: week.to))
        }
        if f.hoursRead {
            await sold.load(model, .hoursPurchases(from: week.from, to: week.to), OwnerAPI.hoursPurchases(from: week.from, to: week.to))
        }
        if f.creditActivate { await credit.load(model, .creditToApprove, OwnerAPI.creditToApprove()) }
        if f.approvals { await approvals.load(model, .approvals(.pending), OwnerAPI.approvals(status: .pending)) }
        if f.finance {
            await cash.load(model, SnapshotKey("cash.supervisors.\(today.from)"), OwnerAPI.cashSupervisorSummary(from: today.from, to: today.to))
        }
        await model.refreshUnread()
    }
}

/// The Owner side menu (design OwnerSideNav).
struct OwnerMenu: View {
    let model: OwnerModel
    let current: AnyHashable?
    let go: (AnyHashable?) -> Void
    let switchCompany: (() -> Void)?
    let signOut: () -> Void

    var body: some View {
        let f = model.features
        VStack(alignment: .leading, spacing: 0) {
            DrawerHeader(name: model.me.displayName, detail: "\(T.roleOwner) · \(model.tenant.name)")
            Divider().overlay(Shell.border)
            ScrollView {
                VStack(spacing: 4) {
                    DrawerRow(T.menuHome, systemImage: "house", selected: current == nil) { go(nil) }
                    DrawerRow(T.tileApprovals, systemImage: "checkmark.seal", selected: current == AnyHashable(OwnerScreen.approvals)) {
                        go(OwnerScreen.approvals)
                    }
                    if f.hoursRead {
                        DrawerRow(T.menuCustomers, systemImage: "person.2", selected: current == AnyHashable(OwnerScreen.customers)) {
                            go(OwnerScreen.customers)
                        }
                    }
                    DrawerRow(T.tileMachines, systemImage: "map", selected: current == AnyHashable(OwnerScreen.machines)) {
                        go(OwnerScreen.machines)
                    }
                    DrawerRow(T.tileMoney, systemImage: "banknote", selected: current == AnyHashable(OwnerScreen.money)) {
                        go(OwnerScreen.money)
                    }
                    DrawerRow(T.menuReports, systemImage: "chart.bar", selected: current == AnyHashable(OwnerScreen.reports)) {
                        go(OwnerScreen.reports)
                    }
                    if f.notifications {
                        DrawerRow(T.menuNotifications, systemImage: "bell", selected: current == AnyHashable(OwnerRoute.notifications),
                                  badge: OwnerFormat.badge(model.unreadCount), redBadge: true) { go(OwnerRoute.notifications) }
                    }
                    DrawerRow(T.menuMore, systemImage: "ellipsis.circle", selected: current == AnyHashable(OwnerScreen.more)) {
                        go(OwnerScreen.more)
                    }
                }
                .padding(.top, 14)
            }
            Divider().overlay(Shell.border)
            VStack(spacing: 4) {
                if let switchCompany {
                    DrawerRow(T.menuSwitchCompany, systemImage: "arrow.left.arrow.right.square", small: true, action: switchCompany)
                }
                DrawerRow(T.menuSettings, systemImage: "gearshape", small: true) { go(OwnerScreen.settings) }
                DrawerRow(T.menuSignOut, systemImage: "rectangle.portrait.and.arrow.right", small: true, action: signOut)
                Text("Asseta Owner \(OwnerModel.appVersion) · Delete my account in Settings")
                    .font(.system(size: 12)).foregroundStyle(Shell.faint).padding(.horizontal, 12).padding(.top, 6)
            }
            .padding(.top, 12)
        }
        .padding(.horizontal, 16).padding(.top, 56).padding(.bottom, 24)
    }
}

// MARK: - Approvals

/// Approvals (design OwnerApprovals): machine reports, credit sales (approve inline), expenses; other kinds one tap away.
struct OwnerApprovalsHubView: View {
    enum Filter: Hashable { case all, reports, credit, expenses }
    let model: OwnerModel
    let back: () -> Void
    let push: (AnyHashable) -> Void
    @State private var filter: Filter = .all
    @State private var reports = Loader<Page<MachineReportDTO>>()
    @State private var credit = Loader<Page<HoursPurchaseDTO>>()
    @State private var approvals = Loader<Page<ApprovalRequestDTO>>()
    @State private var busy: UUID?
    @State private var error: String?

    var body: some View {
        let r = reports.value?.items ?? [], c = credit.value?.items ?? [], e = approvals.value?.items ?? []
        VStack(spacing: 0) {
            ShellHeader(T.tileApprovals, action: back)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    chip(.all, T.filterAll(r.count + c.count + e.count))
                    if model.features.machineReports { chip(.reports, T.filterReports(r.count)) }
                    if model.features.creditActivate { chip(.credit, T.filterCredit(c.count)) }
                    if model.features.approvals { chip(.expenses, T.filterExpenses(e.count)) }
                }
                .padding(.horizontal, 16)
            }
            .padding(.bottom, 10)
            ScrollView {
                VStack(spacing: 12) {
                    if let error { Text(error).font(.system(size: 13)).foregroundStyle(Shell.badText) }
                    if filter == .all || filter == .reports { ForEach(r) { reportCard($0) } }
                    if filter == .all || filter == .credit { ForEach(c) { creditCard($0) } }
                    if filter == .all || filter == .expenses { ForEach(e) { expenseCard($0) } }
                    if r.isEmpty && c.isEmpty && e.isEmpty && reports.value != nil {
                        ShellCard { Text(T.nothingWaiting).foregroundStyle(Shell.muted) }
                    }
                    if model.features.approvalsScreen {
                        Button { push(MoreItem.approvals) } label: {
                            CardRow(T.otherApprovals, subtitle: T.otherApprovalsSub, last: true) {
                                Image(systemName: "chevron.right").foregroundStyle(Shell.muted)
                            }
                        }
                        .buttonStyle(.plain)
                        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                    }
                }
                .padding(.horizontal, 16).padding(.bottom, 16)
            }
            .refreshable { await reload() }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .task(id: model.changeTick) { await reload() }
    }

    private func chip(_ value: Filter, _ title: String) -> some View {
        let on = filter == value
        return Button { filter = value } label: {
            Text(title).font(.system(size: 13, weight: on ? .semibold : .regular))
                .foregroundStyle(on ? Shell.onAccent : Shell.text)
                .padding(.horizontal, 12).padding(.vertical, 8)
                .background(on ? Shell.accent : Shell.card, in: Capsule())
        }
        .buttonStyle(.plain)
    }

    private func header(_ kind: String, _ when: Date) -> some View {
        HStack {
            Text(kind).font(.system(size: 12, weight: .semibold)).tracking(0.6).foregroundStyle(Shell.muted)
            Spacer()
            Text(T.when(when)).font(.system(size: 12)).foregroundStyle(Shell.muted)
        }
    }

    private func reportCard(_ report: MachineReportDTO) -> some View {
        let customers = Set(report.lines.compactMap(\.customerID)).count
        let total = report.hours.value
        return Button { push(OwnerRoute.machineReport(report.id)) } label: {
            VStack(alignment: .leading, spacing: 8) {
                header(T.kindReport, report.submittedAt)
                Text(T.reportCard(report.machineCode ?? "", T.h(total), report.submittedByName ?? ""))
                    .font(.system(size: 16, weight: .semibold)).foregroundStyle(Shell.text)
                SplitBar(total > 0 ? [(fraction(report.customerHours.value, total), Shell.accent),
                                      (fraction(report.nonProductiveHours.value, total), Shell.nonProductive)] : [], height: 8)
                Text(T.reportSplit(customerHours: T.h(report.customerHours.value), customers: customers,
                                   idle: T.h(report.nonProductiveHours.value)))
                    .font(.system(size: 13)).foregroundStyle(Shell.muted)
            }
            .padding(14).frame(maxWidth: .infinity, alignment: .leading)
            .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("approvals.report.\(report.reportNumber)")
    }

    private func creditCard(_ order: HoursPurchaseDTO) -> some View {
        let hours = order.totals.awaitingActivation.value
        let amount = order.creditAmount?.value ?? order.amount.value
        let blocked = model.mutationBlock(permitted: model.features.creditActivate, showingCachedData: credit.isFromCache)
        return VStack(alignment: .leading, spacing: 8) {
            header(T.kindCredit, order.createdAt)
            Text(T.creditCard(order.customerName ?? "", T.h(hours))).font(.system(size: 16, weight: .semibold)).foregroundStyle(Shell.text)
            Text(T.creditDetail(order.creditInvoice?.invoiceNumber, OwnerFormat.money(amount, currency: order.currency)))
                .font(.system(size: 13)).foregroundStyle(Shell.muted)
            HStack(spacing: 10) {
                OutlineButton(T.reject, height: 40) { push(OwnerRoute.hoursPurchase(order.id)) }
                Button { Task { await approveCredit(order, hours: hours) } } label: {
                    Text(busy == order.id ? "…" : T.approveCredit).font(.system(size: 14, weight: .bold))
                        .frame(maxWidth: .infinity, minHeight: 40)
                        .foregroundStyle(Shell.onAccent).background(Shell.accent, in: RoundedRectangle(cornerRadius: 14))
                }
                .buttonStyle(.plain)
                .disabled(blocked != nil || busy != nil || hours <= 0)
                .accessibilityIdentifier("approvals.credit.approve")
            }
            if let blocked { Text(blocked.message).font(.system(size: 12)).foregroundStyle(Shell.muted) }
        }
        .padding(14).frame(maxWidth: .infinity, alignment: .leading)
        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
    }

    private func expenseCard(_ request: ApprovalRequestDTO) -> some View {
        Button { push(OwnerRoute.approval(request.id)) } label: {
            VStack(alignment: .leading, spacing: 6) {
                header(request.subjectType.lowercased().contains("expense") ? T.kindExpense : OwnerFormat.humanize(request.subjectType).uppercased(),
                       request.requestedAt)
                Text("\(request.reason) · \(OwnerFormat.money(request.amount, currency: request.currency))")
                    .font(.system(size: 16, weight: .semibold)).foregroundStyle(Shell.text)
            }
            .padding(14).frame(maxWidth: .infinity, alignment: .leading)
            .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
        }
        .buttonStyle(.plain)
    }

    private func fraction(_ part: Decimal, _ total: Decimal) -> Double { NSDecimalNumber(decimal: part / total).doubleValue }

    private func approveCredit(_ order: HoursPurchaseDTO, hours: Decimal) async {
        guard let repository = model.repository else { return }
        busy = order.id
        defer { busy = nil }
        do {
            _ = try await repository.send(OwnerAPI.activateCredit(order.id, hours: hours, reason: T.creditApprovedReason,
                                                                  idempotencyKey: UUID()))
            error = nil
            await reload()
        } catch {
            self.error = DecisionErrorText.message(for: error)
            model.handle(error)
        }
    }

    private func reload() async {
        let f = model.features
        if f.machineReports { await reports.load(model, .machineReportQueue, OwnerAPI.machineReports(pending: true)) }
        if f.creditActivate { await credit.load(model, .creditToApprove, OwnerAPI.creditToApprove()) }
        if f.approvals { await approvals.load(model, .approvals(.pending), OwnerAPI.approvals(status: .pending)) }
    }
}

/// One machine report to decide (design OwnerReportApproval): meter photo, readings, the split with each customer's
/// hours before and after, notes, the tracker cross-check, Approve / Reject with a reason. Never the approver's own.
struct OwnerReportApprovalView: View {
    let model: OwnerModel
    let reportID: UUID
    @State private var loader = Loader<MachineReportDTO>()
    @State private var photoURL: URL?
    @State private var reason = ""
    @State private var busy = false
    @State private var error: String?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        Group {
            if let report = loader.value {
                content(report)
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .task(id: model.changeTick) { await reload() }
    }

    private func content(_ report: MachineReportDTO) -> some View {
        let decision = MachineReportApproval.decision(report, me: model.me.userID, permissions: Set(model.features.permissions))
        let customers = report.lines.filter { $0.lineKind == .customer }
        let others = report.lines.filter { $0.lineKind == .nonProductive }
        return VStack(spacing: 0) {
            ShellHeader(T.reportTitle(report.machineCode ?? ""),
                        subtitle: [report.submittedByName, T.when(report.submittedAt)].compactMap { $0 }.joined(separator: " · "),
                        action: { dismiss() })
            ScrollView {
                VStack(spacing: 12) {
                    HStack(spacing: 14) {
                        Group {
                            if let photoURL {
                                AsyncImage(url: photoURL) { $0.resizable().scaledToFill() } placeholder: { ProgressView() }
                            } else {
                                Image(systemName: "photo").foregroundStyle(Shell.muted)
                            }
                        }
                        .frame(width: 96, height: 72).clipped()
                        .background(Shell.sunken, in: RoundedRectangle(cornerRadius: 10))
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .accessibilityLabel("Meter photo")
                        VStack(alignment: .leading, spacing: 3) {
                            Text(T.readings(T.h(report.startReading.value), T.h(report.endReading.value)))
                                .font(.system(size: 18, weight: .bold)).foregroundStyle(Shell.text)
                            Text(T.readByPhone(T.h(report.hours.value), nil)).font(.system(size: 13)).foregroundStyle(Shell.muted)
                            if let state = report.state {
                                if state != .submitted {
                                    ShellPill(state == .approved ? T.decidedApproved : T.decidedRejected, tone: state == .approved ? .good : .bad)
                                }
                            }
                        }
                        Spacer(minLength: 0)
                    }
                    .padding(14).background(Shell.card, in: RoundedRectangle(cornerRadius: 18))

                    VStack(alignment: .leading, spacing: 0) {
                        group(T.customersHeader(T.h(report.customerHours.value)))
                        ForEach(customers) { line in
                            HStack(alignment: .firstTextBaseline) {
                                Text(line.customerName ?? "")
                                    + Text(MachineReportApproval.beforeAfter(line).map {
                                        " " + T.leftAfter(T.h($0.before), T.h($0.after))
                                    } ?? "").font(.system(size: 12)).foregroundColor(Shell.muted)
                                Spacer()
                                Text("\(T.h(line.hours.value)) h").fontWeight(.semibold)
                            }
                            .foregroundStyle(Shell.text).padding(.horizontal, 16).padding(.vertical, 8)
                        }
                        Divider().overlay(Shell.border).padding(.top, 4)
                        group(T.nonProductiveHeader(T.h(report.nonProductiveHours.value)))
                        ForEach(others) { line in
                            VStack(alignment: .leading, spacing: 2) {
                                HStack {
                                    Text(line.reasonName ?? line.reasonCode ?? "")
                                    Spacer()
                                    Text("\(T.h(line.hours.value)) h").fontWeight(.semibold)
                                }
                                if let note = line.note, !note.isEmpty {
                                    Text("“\(note)”").font(.system(size: 13)).foregroundStyle(Shell.muted)
                                }
                            }
                            .foregroundStyle(Shell.text).padding(.horizontal, 16).padding(.vertical, 8)
                        }
                        if let note = report.note, !note.isEmpty {
                            Text("“\(note)”").font(.system(size: 13)).foregroundStyle(Shell.muted).padding(16)
                        }
                    }
                    .padding(.bottom, 8)
                    .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))

                    Text(trackerLine(report)).font(.system(size: 13)).lineSpacing(3).foregroundStyle(Shell.text)
                        .padding(.horizontal, 14).padding(.vertical, 12).frame(maxWidth: .infinity, alignment: .leading)
                        .background(Shell.raised, in: RoundedRectangle(cornerRadius: 14))

                    if let note = report.decisionNote, report.state == .rejected {
                        Text(note).font(.system(size: 13)).foregroundStyle(Shell.badText)
                    }
                    switch decision {
                    case .allowed:
                        FieldBox(T.rejectReason) {
                            TextField(T.rejectPlaceholder, text: $reason, axis: .vertical).lineLimit(1...4)
                                .accessibilityIdentifier("report.rejectReason")
                        }
                    case .ownReport:
                        ShellCard { Text(T.ownReport).foregroundStyle(Shell.muted) }
                    case .notPermitted:
                        ShellCard { Text(T.notPermitted).foregroundStyle(Shell.muted) }
                    case .decided:
                        EmptyView()
                    }
                    if let error { Text(error).font(.system(size: 13)).foregroundStyle(Shell.badText) }
                }
                .padding(.horizontal, 16).padding(.bottom, 12)
            }
            if decision == .allowed {
                let blocked = model.mutationBlock(permitted: true, showingCachedData: loader.isFromCache)
                VStack(spacing: 6) {
                    HStack(spacing: 10) {
                        Button { Task { await decide(report, approve: false) } } label: {
                            Text(T.reject).font(.system(size: 16, weight: .bold)).frame(maxWidth: .infinity, minHeight: 54)
                                .foregroundStyle(Shell.badText)
                                .background(Shell.badFill, in: RoundedRectangle(cornerRadius: 16))
                        }
                        .buttonStyle(.plain)
                        .disabled(busy || blocked != nil || !MachineReportApproval.rejectReasonValid(reason))
                        .accessibilityIdentifier("report.reject")
                        PrimaryButton(T.approve, enabled: !busy && blocked == nil, identifier: "report.approve") {
                            Task { await decide(report, approve: true) }
                        }
                    }
                    if let blocked { Text(blocked.message).font(.system(size: 12)).foregroundStyle(Shell.muted) }
                }
                .padding(.horizontal, 16).padding(.vertical, 12)
            }
        }
    }

    private func group(_ title: String) -> some View {
        Text(title).font(.system(size: 13, weight: .semibold)).foregroundStyle(Shell.muted)
            .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 16).padding(.top, 12).padding(.bottom, 6)
    }

    private func trackerLine(_ report: MachineReportDTO) -> String {
        guard let tracker = report.tracker, tracker.available, let hours = tracker.trackerHours else { return T.noTracker }
        return T.tracker(T.h(hours.value), T.h(tracker.meterHours.value))
    }

    private func reload() async {
        await loader.load(model, .machineReport(reportID), OwnerAPI.machineReport(reportID))
        if photoURL == nil, let attachment = loader.value?.photoAttachmentID, model.isOnline, let repository = model.repository {
            photoURL = try? await repository.send(OwnerAPI.attachmentURL(attachment)).url
        }
    }

    private func decide(_ report: MachineReportDTO, approve: Bool) async {
        guard let repository = model.repository else { return }
        busy = true
        defer { busy = false }
        do {
            let updated = try await repository.send(approve
                ? OwnerAPI.approveMachineReport(report.id, note: nil, idempotencyKey: UUID())
                : OwnerAPI.rejectMachineReport(report.id, reason: reason, idempotencyKey: UUID()))
            loader.replace(updated)
            error = nil
            dismiss()
        } catch {
            self.error = DecisionErrorText.message(for: error)
            model.handle(error)
        }
    }
}
#endif
