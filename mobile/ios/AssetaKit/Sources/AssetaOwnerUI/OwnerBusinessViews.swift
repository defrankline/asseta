#if os(iOS)
import AssetaAppShell
import AssetaFleetMap
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

private typealias T = MachineReportOwnerTexts
private typealias Fig = OwnerFigures

private func percent(_ part: Decimal, of total: Decimal) -> Double {
    total > 0 ? min(1, NSDecimalNumber(decimal: part / total).doubleValue) : 0
}

extension OwnerPillTone {
    var shell: ShellPill.Tone {
        switch self {
        case .waiting: .waiting
        case .good: .good
        case .bad: .bad
        case .neutral: .neutral
        }
    }
}

/// A grey line in place of a list (empty state, a read that failed).
private struct ShellNote: View {
    let text: String
    init(_ text: String) { self.text = text }

    var body: some View {
        Text(text).font(.system(size: 14)).foregroundStyle(Shell.muted).frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Customers & hours

/// Customers & hours (design OwnerCustomers): bought / used / credit owed, each customer's hours left and their credit
/// invoices.
struct OwnerCustomersView: View {
    let model: OwnerModel
    let back: () -> Void
    let push: (AnyHashable) -> Void
    @State private var hours = Loader<[CustomerHoursSummaryDTO]>()
    @State private var invoices = Loader<Page<CreditInvoiceDTO>>()
    @State private var search = ""

    var body: some View {
        let all = hours.value ?? []
        let rows = OwnerCustomersParity.filter(all, query: search)
        let allInvoices = invoices.value?.items ?? []
        VStack(spacing: 0) {
            ShellHeader(T.customersTitle, action: back)
            ScrollView {
                VStack(spacing: 12) {
                    HStack {
                        Image(systemName: "magnifyingglass").foregroundStyle(Shell.muted)
                        TextField(T.searchCustomers, text: $search).foregroundStyle(Shell.text)
                            .onChange(of: search) { _, value in if value.count > 100 { search = String(value.prefix(100)) } }
                    }
                    .padding(.horizontal, 14).frame(height: 46)
                    .background(Shell.card, in: RoundedRectangle(cornerRadius: 14))
                    if hours.value != nil {
                        let owed = all.reduce(Decimal(0)) { $0 + $1.creditOwed.value }
                        HStack(spacing: 8) {
                            stat(T.bought, Fig.hours(all.reduce(Decimal(0)) { $0 + $1.bought.value }))
                            stat(T.used, Fig.hours(all.reduce(Decimal(0)) { $0 + $1.used.value }))
                            stat(T.creditOwed, Fig.compactMoney(owed), warn: owed > 0)
                        }
                        .padding(16).background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                        if rows.isEmpty {
                            ShellNote(all.isEmpty ? OwnerCustomersParity.empty : OwnerCustomersParity.noMatch).padding(.vertical, 8)
                        }
                    }
                    if let error = hours.error, hours.value == nil { LoadFailure(message: error) { await reload() } }
                    ForEach(rows) { row in card(row, invoices: OwnerCustomersParity.openInvoices(row.customerID, allInvoices)) }
                    if let error = invoices.error, invoices.value == nil { ShellNote(error) }
                }
                .padding(.horizontal, 16).padding(.bottom, 16)
            }
            .refreshable { await reload() }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .task(id: model.changeTick) { await reload() }
    }

    private func stat(_ title: String, _ value: String, warn: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.system(size: 12)).foregroundStyle(Shell.muted)
            Text(value).font(.system(size: 17, weight: .bold)).foregroundStyle(warn ? Shell.warnText : Shell.text)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func card(_ row: CustomerHoursSummaryDTO, invoices: [CreditInvoiceDTO]) -> some View {
        Button { push(OwnerRoute.hoursStatement(customer: row.customerID, name: row.customerName)) } label: {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(row.customerName ?? row.customerID.uuidString).font(.system(size: 16, weight: .semibold))
                    Spacer()
                    Text(T.hoursLeft(Fig.hoursNumber(row.left.value))).font(.system(size: 15, weight: .bold))
                        .foregroundStyle(row.left.value > 0 ? Shell.accent : Shell.muted)
                }
                .foregroundStyle(Shell.text)
                SplitBar([(percent(row.used.value, of: row.bought.value), Shell.accent)], height: 8)
                Text(OwnerCustomersParity.detail(row)).font(.system(size: 13)).foregroundStyle(Shell.muted)
                ForEach(invoices) { invoice in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(T.invoiceRow(invoice.invoiceNumber)).font(.system(size: 14, weight: .semibold)).foregroundStyle(Shell.text)
                            Text(OwnerCustomersParity.invoiceLine(invoice)).font(.system(size: 12)).foregroundStyle(Shell.muted)
                        }
                        Spacer()
                        ShellPill(T.owed(Fig.compactMoney(invoice.balance.value)), tone: invoice.overdue ? .bad : .waiting)
                    }
                    .padding(10).background(Shell.raised, in: RoundedRectangle(cornerRadius: 12))
                }
            }
            .padding(14).frame(maxWidth: .infinity, alignment: .leading)
            .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
        }
        .buttonStyle(.plain)
    }

    private func reload() async {
        await hours.load(model, .customerHoursSummary, OwnerAPI.customerHoursSummary())
        await invoices.load(model, .creditInvoices, OwnerAPI.creditInvoices())
    }
}

// MARK: - Machines

/// Machines (design OwnerMachines): the map (or list) and this week's hours of every machine with a report status or a
/// report this week; overdue machines first.
struct OwnerMachinesView: View {
    let model: OwnerModel
    let back: () -> Void
    let push: (AnyHashable) -> Void
    @State private var showMap = true
    @State private var fleet = Loader<[MachineMapDTO]>()
    @State private var reports = Loader<Page<MachineReportDTO>>()
    @State private var states = Loader<[MachineReportStatusDTO]>()
    @State private var policy = Loader<EffectivePolicyDTO<CustomerHoursPolicyValues>>()

    var body: some View {
        let f = model.features
        let machines = fleet.value ?? []
        let rows = OwnerMachinesParity.rows(statuses: states.value ?? [], reports: reports.value?.items ?? [], fleet: machines,
                                            fleetOn: f.fleet, tracking: f.tracking, machineReports: f.machineReports,
                                            reminderDays: policy.reminderDays)
        VStack(spacing: 0) {
            ShellHeader(T.machinesTitle, action: back) {
                if f.fleet {
                    ShellSegments([(true, T.map), (false, T.list)], selection: $showMap, compact: true).fixedSize()
                }
            }
            ScrollView {
                VStack(spacing: 0) {
                    if showMap && f.fleet {
                        let placed = machines.filter(\.hasPosition).count
                        FleetMapView(machines: machines, dataIsCached: fleet.isFromCache) { push(OwnerRoute.machine($0)) }
                            .frame(height: 300).clipShape(RoundedRectangle(cornerRadius: 18))
                            .accessibilityElement(children: .contain)
                            .accessibilityLabel(OwnerMachinesParity.mapAccessibility(placed))
                        if fleet.value != nil && placed == 0 { ShellNote(OwnerMachinesParity.mapEmpty).padding(.top, 8) }
                        if let error = fleet.error, fleet.value == nil { ShellNote(error).padding(.top, 8) }
                    }
                    if f.machineReports {
                        SectionLabel(T.thisWeek).padding(.top, 16).padding(.bottom, 8)
                        if let error = states.error ?? reports.error, states.value == nil || reports.value == nil {
                            ShellNote(error).padding(.bottom, 8)
                        }
                        if rows.isEmpty && states.value != nil && !states.isLoading {
                            ShellNote(OwnerMachinesParity.noMachines).padding(.bottom, 8)
                        }
                        if !rows.isEmpty {
                            VStack(spacing: 0) {
                                ForEach(Array(rows.enumerated()), id: \.element.id) { index, m in
                                    row(m)
                                    if index < rows.count - 1 { Divider().overlay(Shell.border) }
                                }
                            }
                            .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                        }
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

    private func row(_ m: OwnerMachineWeek) -> some View {
        Button {
            switch m.open {
            case let .machine(id): push(OwnerRoute.machine(id))
            case let .report(id): push(OwnerRoute.machineReport(id))
            case nil: break
            }
        } label: {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text(m.title).font(.system(size: 15, weight: .semibold))
                    Spacer()
                    if let late = m.overdue {
                        ShellPill(late.pill, tone: .bad)
                    } else if let supervisor = m.supervisor {
                        Text(supervisor).font(.system(size: 13)).foregroundStyle(Shell.muted)
                    }
                }
                .foregroundStyle(Shell.text)
                if m.hours > 0 {
                    SplitBar([(percent(m.productive, of: m.hours), Shell.accent),
                              (percent(m.nonProductive, of: m.hours), Shell.nonProductive)], height: 8)
                }
                Text(m.detail).font(.system(size: 13)).foregroundStyle(Shell.muted)
            }
            .padding(.horizontal, 16).padding(.vertical, 12)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(m.open == nil)
    }

    private func reload() async {
        let week = OwnerPeriod.week.range
        if model.features.fleet { await fleet.load(model, .fleetMap, OwnerAPI.fleetMap()) }
        if model.features.machineReports {
            await reports.load(model, .machineReports(from: week.from, to: week.to), OwnerAPI.machineReports(from: week.from, to: week.to))
            await states.load(model, .machineReportStatus, OwnerAPI.machineReportStatus())
            await policy.load(model, .customerHoursPolicy, OwnerAPI.customerHoursPolicy())
        }
    }
}

// MARK: - Money

/// Opens Record payment, for one invoice or to choose one.
struct PaymentTarget: Hashable { let invoiceID: UUID? }

/// Money (design OwnerMoney): sold by method, cash with each supervisor, credit invoices; Expenses and Record payment.
struct OwnerMoneyView: View {
    let model: OwnerModel
    let back: () -> Void
    let push: (AnyHashable) -> Void
    @State private var period: OwnerPeriod = .week
    @State private var orders = Loader<Page<HoursPurchaseDTO>>()
    @State private var cash = Loader<[CashSupervisorSummaryDTO]>()
    @State private var overdue = Loader<Page<RemittanceOverdueDTO>>()
    @State private var invoices = Loader<Page<CreditInvoiceDTO>>()
    @State private var expenses = Loader<Page<ExpenseDTO>>()
    @State private var paying: PaymentTarget?

    var body: some View {
        let f = model.features
        let liveOrders = orders.value?.items ?? []
        let sold = SoldByMethod.of(liveOrders)
        let currency = liveOrders.first?.currency ?? invoices.value?.items.first?.currency ?? ""
        VStack(spacing: 0) {
            ShellHeader(T.tileMoney, action: back) {
                ShellSegments(OwnerPeriod.allCases.map { ($0, $0.label) }, selection: $period)
            }
            ScrollView {
                VStack(spacing: 0) {
                    if f.hoursRead { soldCard(sold, currency: currency) }
                    if f.finance { cashSection() }
                    if f.hoursRead { invoiceSection() }
                }
                .padding(.horizontal, 16).padding(.bottom, 16)
            }
            .refreshable { await reload() }
            HStack(spacing: 10) {
                if f.expenses {
                    OutlineButton(OwnerMoneyParity.expenses(expenses.value?.total), height: 54) { push(OwnerRoute.fieldSpend) }
                }
                if f.invoicePayment {
                    PrimaryButton(T.recordPayment, identifier: "money.recordPayment") { paying = PaymentTarget(invoiceID: nil) }
                }
            }
            .padding(.horizontal, 16).padding(.vertical, 12)
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .task(id: "\(model.changeTick)-\(period.rawValue)") { await reload() }
        .navigationDestination(item: $paying) { target in
            OwnerRecordPaymentView(model: model, preselected: target.invoiceID)
        }
    }

    @ViewBuilder private func soldCard(_ sold: SoldByMethod, currency: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(T.soldIn(period.phrase)).font(.system(size: 13, weight: .semibold)).opacity(0.8)
            if let items = orders.value?.items {
                if OwnerMoneyParity.hasSales(items) {
                    Text(Fig.money(sold.total, currency: currency)).font(.system(size: 30, weight: .bold))
                        .minimumScaleFactor(0.6).lineLimit(1)
                    let methods = OwnerMoneyParity.methods(sold)
                    if !methods.isEmpty { Text(methods).font(.system(size: 13)) }
                } else {
                    Text(OwnerMoneyParity.noSales).font(.system(size: 14))
                }
            } else if let error = orders.error {
                Text(error).font(.system(size: 13))
            }
        }
        .foregroundStyle(Shell.onAccent).padding(18).frame(maxWidth: .infinity, alignment: .leading)
        .background(Shell.accent, in: RoundedRectangle(cornerRadius: 20)).padding(.top, 4)
    }

    @ViewBuilder private func cashSection() -> some View {
        SectionLabel(T.cashSupervisors).padding(.top, 18).padding(.bottom, 8)
        if let all = cash.value {
            let rows = OwnerMoneyParity.cashRows(all)
            let flags = overdue.value?.items ?? []
            if rows.isEmpty {
                ShellNote(OwnerMoneyParity.noCash)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                        let flag = flags.first { $0.staffMemberID == row.staffMemberID }
                        Button { push(OwnerRoute.cash) } label: {
                            CardRow(row.staffName, subtitle: OwnerMoneyParity.cashDetail(row, overdue: flag), last: index == rows.count - 1) {
                                Text(Fig.compactMoney(row.closingOutstanding.value)).font(.system(size: 16, weight: .bold))
                                    .foregroundStyle(Shell.text)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
                .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
            }
        } else if let error = cash.error {
            ShellNote(error)
        }
    }

    @ViewBuilder private func invoiceSection() -> some View {
        SectionLabel(T.creditInvoices).padding(.top, 18).padding(.bottom, 8)
        if let all = invoices.value?.items {
            let list = OwnerMoneyParity.invoices(all)
            if list.isEmpty {
                ShellNote(OwnerMoneyParity.noInvoices)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(list.enumerated()), id: \.element.id) { index, invoice in
                        let pill = OwnerMoneyParity.pill(invoice)
                        let payable = model.features.invoicePayment && OwnerMoneyParity.payable(invoice)
                        Button { if payable { paying = PaymentTarget(invoiceID: invoice.id) } } label: {
                            CardRow(OwnerMoneyParity.invoiceTitle(invoice), subtitle: OwnerMoneyParity.invoiceDetail(invoice),
                                    last: index == list.count - 1) {
                                ShellPill(pill.label, tone: pill.tone.shell)
                            }
                        }
                        .buttonStyle(.plain)
                        .disabled(!payable)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
            }
        } else if let error = invoices.error {
            ShellNote(error)
        }
    }

    private func reload() async {
        let range = period.range
        let f = model.features
        if f.hoursRead {
            await orders.load(model, .hoursPurchases(from: range.from, to: range.to), OwnerAPI.hoursPurchases(from: range.from, to: range.to))
            await invoices.load(model, .creditInvoices, OwnerAPI.creditInvoices())
        }
        if f.finance {
            await cash.load(model, SnapshotKey("cash.supervisors.\(range.from).\(range.to)"),
                            OwnerAPI.cashSupervisorSummary(from: range.from, to: range.to))
            if f.cashCustody {
                let today = OwnerPeriod.day(Date())
                await overdue.load(model, .overdueRemittances(day: today), OwnerAPI.remittanceOverdue(day: today))
            }
        }
        if f.expenses { await expenses.load(model, .expenses(pendingOnly: true), OwnerAPI.expenses(status: "PENDING_APPROVAL")) }
    }
}

// MARK: - Reports

/// Reports (design OwnerReports): machine hours by customers and reasons, hours sold and used, and the REPORTS rows,
/// each opening its screen.
struct OwnerReportsView: View {
    let model: OwnerModel
    let back: () -> Void
    let push: (AnyHashable) -> Void
    @State private var period: OwnerPeriod = .month
    @State private var reports = Loader<Page<MachineReportDTO>>()
    @State private var orders = Loader<Page<HoursPurchaseDTO>>()
    @State private var byReason = false

    var body: some View {
        let f = model.features
        let split = reports.value.map { OwnerReportsPresentation.split($0.items) }
        let sold = orders.value.map { OwnerReportsPresentation.sold($0.items) }
        let links = OwnerReportsPresentation.links(f)
        VStack(spacing: 0) {
            ShellHeader(T.reportsTitle, action: back) {
                ShellSegments([(OwnerPeriod.week, OwnerPeriod.week.label), (.month, OwnerPeriod.month.label)], selection: $period)
            }
            ScrollView {
                VStack(spacing: 0) {
                    if f.machineReports {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(OwnerReportsTexts.title(month: period == .month)).font(.system(size: 13)).foregroundStyle(Shell.muted)
                            if let split {
                                if split.total == 0 {
                                    ShellNote(OwnerReportsTexts.noHours)
                                } else {
                                    Text(Fig.hours(split.total)).font(.system(size: 26, weight: .bold)).foregroundStyle(Shell.text)
                                    HoursSplitBar(split: split)
                                    HoursLegend(split: split)
                                }
                            } else if let error = reports.error {
                                ShellNote(error)
                            }
                        }
                        .padding(16).frame(maxWidth: .infinity, alignment: .leading)
                        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18)).padding(.top, 4)
                    }
                    if f.hoursRead || f.machineReports {
                        HStack(spacing: 12) {
                            if f.hoursRead {
                                figure(OwnerReportsTexts.hoursSold, sold.map { Fig.hours($0.hours) } ?? "—", sold?.amount)
                            }
                            if f.machineReports {
                                let used = split?.customers
                                let left = sold.flatMap { s in used.map { max(0, s.hours - $0) } }
                                figure(OwnerReportsTexts.hoursUsed, used.map { Fig.hours($0) } ?? "—",
                                       left.map { OwnerReportsTexts.stillWithCustomers($0) })
                            }
                        }
                        .padding(.top, 12)
                    }
                    if !links.isEmpty {
                        SectionLabel(OwnerReportsTexts.reports).padding(.top, 18).padding(.bottom, 8)
                        VStack(spacing: 0) {
                            ForEach(Array(links.enumerated()), id: \.offset) { index, link in
                                Button { open(link.open) } label: {
                                    CardRow(link.label, last: index == links.count - 1) {
                                        Image(systemName: "chevron.right").font(.system(size: 14, weight: .semibold))
                                            .foregroundStyle(Shell.muted)
                                    }
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                    }
                }
                .padding(.horizontal, 16).padding(.bottom, 16)
            }
            .refreshable { await reload() }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .task(id: "\(model.changeTick)-\(period.rawValue)") { await reload() }
        .navigationDestination(isPresented: $byReason) { OwnerHoursByReasonView(model: model, period: $period) }
    }

    private func open(_ link: OwnerReportLink) {
        switch link {
        case .customers: push(OwnerScreen.customers)
        case .machines: push(OwnerScreen.machines)
        case .hoursByReason: byReason = true
        case .money: push(OwnerScreen.money)
        case .cash: push(OwnerRoute.cash)
        }
    }

    private func figure(_ title: String, _ value: String, _ detail: String?) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.system(size: 13)).foregroundStyle(Shell.muted)
            Text(value).font(.system(size: 22, weight: .bold)).foregroundStyle(Shell.text).padding(.top, 2)
            if let detail { Text(detail).font(.system(size: 12)).foregroundStyle(Shell.muted) }
        }
        .padding(14).frame(maxWidth: .infinity, alignment: .leading)
        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
    }

    private func reload() async {
        let range = period.range
        if model.features.machineReports {
            await reports.load(model, .machineReports(from: range.from, to: range.to), OwnerAPI.machineReports(from: range.from, to: range.to))
        }
        if model.features.hoursRead {
            await orders.load(model, .hoursPurchases(from: range.from, to: range.to), OwnerAPI.hoursPurchases(from: range.from, to: range.to))
        }
    }
}

/// Non-productive hours by reason for the period chosen on Reports (with each reason's share of the machine hours).
struct OwnerHoursByReasonView: View {
    let model: OwnerModel
    @Binding var period: OwnerPeriod
    @Environment(\.dismiss) private var dismiss
    @State private var reports = Loader<Page<MachineReportDTO>>()

    var body: some View {
        let split = reports.value.map { OwnerReportsPresentation.split($0.items) }
        VStack(spacing: 0) {
            ShellHeader(OwnerReportsTexts.byReason, action: { dismiss() }) {
                ShellSegments([(OwnerPeriod.week, OwnerPeriod.week.label), (.month, OwnerPeriod.month.label)], selection: $period)
            }
            ScrollView {
                VStack(spacing: 0) {
                    if let split {
                        if split.reasons.isEmpty {
                            ShellNote(OwnerReportsTexts.noHours).padding(.top, 8)
                        } else {
                            SectionLabel(OwnerReportsTexts.nonProductiveHeader(split.nonProductive)).padding(.top, 8).padding(.bottom, 8)
                            VStack(spacing: 0) {
                                ForEach(Array(split.reasons.enumerated()), id: \.offset) { index, reason in
                                    CardRow(reason.name, subtitle: OwnerReportsTexts.share(reason.hours, of: split.total),
                                            last: index == split.reasons.count - 1) {
                                        Text(Fig.hours(reason.hours)).font(.system(size: 15, weight: .bold)).foregroundStyle(Shell.text)
                                    }
                                }
                            }
                            .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                            ShellNote(OwnerReportsTexts.counted).font(.system(size: 13)).padding(.top, 12)
                        }
                    } else if let error = reports.error {
                        ShellNote(error).padding(.top, 8)
                    }
                }
                .padding(.horizontal, 16).padding(.bottom, 16)
            }
            .refreshable { await reload() }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .staleBanner(reports, model: model)
        .task(id: "\(model.changeTick)-\(period.rawValue)") { await reload() }
    }

    private func reload() async {
        guard model.features.machineReports else { return }
        let range = period.range
        await reports.load(model, .machineReports(from: range.from, to: range.to), OwnerAPI.machineReports(from: range.from, to: range.to))
    }
}

/// Bar colours: amber for customers, then one colour per reason (repeating), as Android `REASON_COLORS`.
private let reasonColors: [Color] = [
    Color(red: 0xE5 / 255, green: 0x67 / 255, blue: 0x5C / 255), Color(red: 0x4F / 255, green: 0xA3 / 255, blue: 0xE0 / 255),
    Color(red: 0x9B / 255, green: 0x7B / 255, blue: 0xE0 / 255), Color(red: 0x5C / 255, green: 0xC8 / 255, blue: 0xA8 / 255),
    Color(red: 0xB7 / 255, green: 0xC4 / 255, blue: 0xD1 / 255), Color(red: 0x7B / 255, green: 0xA0 / 255, blue: 0x5C / 255),
]

private func reasonColor(_ index: Int) -> Color { reasonColors[index % reasonColors.count] }

/// Customers and each reason as one bar.
private struct HoursSplitBar: View {
    let split: OwnerHoursSplit

    var body: some View {
        let customers: (Double, Color) = (percent(split.customers, of: split.total), Shell.accent)
        let reasons: [(Double, Color)] = split.reasons.enumerated().map { i, r in (percent(r.hours, of: split.total), reasonColor(i)) }
        return SplitBar([customers] + reasons, height: 14)
            .accessibilityElement()
            .accessibilityLabel(OwnerReportsTexts.barAccessibility)
    }
}

/// "■ Customers 880 h", "■ Breakdown 40 h", ...
private struct HoursLegend: View {
    let split: OwnerHoursSplit

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            entry(Shell.accent, "\(OwnerReportsTexts.customers) \(Fig.hours(split.customers))")
            ForEach(Array(split.reasons.enumerated()), id: \.offset) { i, r in entry(reasonColor(i), "\(r.name) \(Fig.hours(r.hours))") }
        }
    }

    private func entry(_ color: Color, _ text: String) -> some View {
        HStack(spacing: 8) {
            RoundedRectangle(cornerRadius: 3).fill(color).frame(width: 10, height: 10)
            Text(text).font(.system(size: 14)).foregroundStyle(Shell.text)
        }
    }
}
#endif
