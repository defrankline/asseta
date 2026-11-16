#if os(iOS)
import AssetaAppShell
import AssetaFleetMap
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

private typealias T = MachineReportOwnerTexts

private func percent(_ part: Decimal, of total: Decimal) -> Double {
    total > 0 ? min(1, NSDecimalNumber(decimal: part / total).doubleValue) : 0
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
        let rows = all.filter { search.isEmpty || ($0.customerName ?? "").localizedCaseInsensitiveContains(search) }
        let open = (invoices.value?.items ?? []).filter { $0.balance.value > 0 && $0.status != "CANCELLED" }
        VStack(spacing: 0) {
            ShellHeader(T.customersTitle, action: back)
            ScrollView {
                VStack(spacing: 12) {
                    HStack {
                        Image(systemName: "magnifyingglass").foregroundStyle(Shell.muted)
                        TextField(T.searchCustomers, text: $search).foregroundStyle(Shell.text)
                    }
                    .padding(.horizontal, 14).frame(height: 46)
                    .background(Shell.card, in: RoundedRectangle(cornerRadius: 14))
                    HStack(spacing: 8) {
                        stat(T.bought, "\(T.h(all.reduce(0) { $0 + $1.bought.value })) h")
                        stat(T.used, "\(T.h(all.reduce(0) { $0 + $1.used.value })) h")
                        stat(T.creditOwed, T.short(all.reduce(0) { $0 + $1.creditOwed.value }), warn: true)
                    }
                    .padding(16).background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                    if let error = hours.error, hours.value == nil { LoadFailure(message: error) { await reload() } }
                    ForEach(rows) { row in card(row, invoices: open.filter { $0.customerID == row.customerID }) }
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
        let awaiting = row.awaitingActivation.value
        let detail = T.boughtUsed(T.h(row.bought.value), T.h(row.used.value))
            + (row.creditOwed.value == 0 && awaiting == 0 ? " · \(T.allPaid)" : "")
            + (awaiting > 0 ? " · " + T.awaitingCredit("\(T.h(awaiting)) h") : "")
        return Button { push(OwnerRoute.hoursStatement(customer: row.customerID, name: row.customerName)) } label: {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(row.customerName ?? "").font(.system(size: 16, weight: .semibold))
                    Spacer()
                    Text(T.hoursLeft(T.h(row.left.value))).font(.system(size: 15, weight: .bold))
                        .foregroundStyle(row.left.value > 0 ? Shell.accent : Shell.muted)
                }
                .foregroundStyle(Shell.text)
                SplitBar([(percent(row.used.value, of: row.bought.value), Shell.accent)], height: 8)
                Text(detail).font(.system(size: 13)).foregroundStyle(Shell.muted)
                ForEach(invoices) { invoice in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(T.invoiceRow(invoice.invoiceNumber)).font(.system(size: 14, weight: .semibold)).foregroundStyle(Shell.text)
                            Text(T.invoiceLine(T.short(invoice.amount.value), T.short(invoice.paid.value), OwnerPeriod.short(invoice.dueDate)))
                                .font(.system(size: 12)).foregroundStyle(Shell.muted)
                        }
                        Spacer()
                        ShellPill(T.owed(T.short(invoice.balance.value)), tone: invoice.overdue ? .bad : .waiting)
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

/// Machines (design OwnerMachines): the map (or list) and this week's productive vs non-productive hours per machine;
/// machines with no report for days.
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
        let summary = MachineHoursSummary.of(reports.value?.items ?? [])
        let reported = Set(summary.machines.map(\.id))
        let overdue = OverdueMachine.list(states.value ?? [], reminderDays: policy.reminderDays)
        let overdueByMachine = Dictionary(overdue.map { ($0.state.machineID, $0.overdue) }, uniquingKeysWith: { a, _ in a })
        let silent = overdue.filter { !reported.contains($0.state.machineID) }
        VStack(spacing: 0) {
            ShellHeader(T.machinesTitle, action: back) {
                if model.features.fleet {
                    ShellSegments([(true, T.map), (false, T.list)], selection: $showMap, compact: true).fixedSize()
                }
            }
            ScrollView {
                VStack(spacing: 0) {
                    if showMap && model.features.fleet {
                        FleetMapView(machines: fleet.value ?? [], dataIsCached: fleet.isFromCache) { push(OwnerRoute.machine($0)) }
                            .frame(height: 300).clipShape(RoundedRectangle(cornerRadius: 18))
                    }
                    SectionLabel(T.thisWeek).padding(.top, 16).padding(.bottom, 8)
                    VStack(spacing: 0) {
                        ForEach(Array(summary.machines.enumerated()), id: \.element.id) { index, m in
                            Button { if model.features.fleet { push(OwnerRoute.machine(m.id)) } } label: {
                                VStack(alignment: .leading, spacing: 6) {
                                    HStack {
                                        Text([m.code, m.name].filter { !$0.isEmpty }.joined(separator: " · ")).font(.system(size: 15, weight: .semibold))
                                        Spacer()
                                        if let late = overdueByMachine[m.id] {
                                            ShellPill(late.pill, tone: .bad)
                                        } else {
                                            Text(m.submittedBy?.split(separator: " ").first.map(String.init) ?? "")
                                                .font(.system(size: 13)).foregroundStyle(Shell.muted)
                                        }
                                    }
                                    .foregroundStyle(Shell.text)
                                    SplitBar([(percent(m.productive, of: m.total), Shell.accent),
                                              (percent(m.nonProductive, of: m.total), Shell.nonProductive)], height: 8)
                                    Text(T.machineWeek(T.h(m.total), T.h(m.productive), m.lastReading.map { T.h($0) }, pending: m.lastPending))
                                        .font(.system(size: 13)).foregroundStyle(Shell.muted)
                                }
                                .padding(.horizontal, 16).padding(.vertical, 12)
                            }
                            .buttonStyle(.plain)
                            if index < summary.machines.count - 1 || !silent.isEmpty { Divider().overlay(Shell.border) }
                        }
                        ForEach(Array(silent.enumerated()), id: \.element.state.machineID) { index, row in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text([row.state.machineCode, row.state.machineName].compactMap { $0 }.joined(separator: " · "))
                                        .font(.system(size: 15, weight: .semibold)).foregroundStyle(Shell.text)
                                    Spacer()
                                    ShellPill(row.overdue.pill, tone: .bad)
                                }
                            }
                            .padding(.horizontal, 16).padding(.vertical, 12)
                            if index < silent.count - 1 { Divider().overlay(Shell.border) }
                        }
                        if summary.machines.isEmpty && silent.isEmpty {
                            Text(T.noReports).font(.system(size: 14)).foregroundStyle(Shell.muted).padding(16)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                }
                .padding(.horizontal, 16).padding(.bottom, 16)
            }
            .refreshable { await reload() }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .task(id: model.changeTick) { await reload() }
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

/// Money (design OwnerMoney): sold by method, cash with each supervisor, credit invoices; Expenses and Record payment.
struct OwnerMoneyView: View {
    let model: OwnerModel
    let back: () -> Void
    let push: (AnyHashable) -> Void
    @State private var period: OwnerPeriod = .week
    @State private var orders = Loader<Page<HoursPurchaseDTO>>()
    @State private var cash = Loader<[CashSupervisorSummaryDTO]>()
    @State private var invoices = Loader<Page<CreditInvoiceDTO>>()
    @State private var expenses = Loader<Page<ExpenseDTO>>()
    @State private var paying: CreditInvoiceDTO?
    @State private var choosing = false

    var body: some View {
        let sold = SoldByMethod.of(orders.value?.items ?? [])
        let open = (invoices.value?.items ?? []).filter { $0.balance.value > 0 && $0.status != "CANCELLED" }
        let currency = orders.value?.items.first?.currency ?? open.first?.currency ?? ""
        VStack(spacing: 0) {
            ShellHeader(T.tileMoney, action: back) {
                ShellSegments(OwnerPeriod.allCases.map { ($0, $0.label) }, selection: $period)
            }
            ScrollView {
                VStack(spacing: 0) {
                    if model.features.hoursRead {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(T.soldIn(period.phrase)).font(.system(size: 13, weight: .semibold)).opacity(0.8)
                            Text(OwnerFormat.money(sold.total, currency: currency)).font(.system(size: 30, weight: .bold))
                                .minimumScaleFactor(0.6).lineLimit(1)
                            Text(T.soldLine(cash: T.short(sold.cash), bank: T.short(sold.bank), mobile: T.short(sold.mobileMoney),
                                            credit: T.short(sold.credit))).font(.system(size: 13))
                        }
                        .foregroundStyle(Shell.onAccent).padding(18).frame(maxWidth: .infinity, alignment: .leading)
                        .background(Shell.accent, in: RoundedRectangle(cornerRadius: 20)).padding(.top, 4)
                    }
                    if model.features.finance {
                        SectionLabel(T.cashSupervisors).padding(.top, 18).padding(.bottom, 8)
                        let rows = (cash.value ?? []).sorted { $0.closingOutstanding.value > $1.closingOutstanding.value }
                        VStack(spacing: 0) {
                            ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                                Button { push(OwnerRoute.cash) } label: {
                                    CardRow(row.staffName,
                                            subtitle: row.claimedUnverifiedHandovers.value > 0
                                                ? T.handedAwaiting(T.short(row.claimedUnverifiedHandovers.value)) : nil,
                                            last: index == rows.count - 1) {
                                        Text(T.short(row.closingOutstanding.value)).font(.system(size: 16, weight: .bold))
                                            .foregroundStyle(Shell.text)
                                    }
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                    }
                    if model.features.hoursRead {
                        SectionLabel(T.creditInvoices).padding(.top, 18).padding(.bottom, 8)
                        VStack(spacing: 0) {
                            if open.isEmpty { Text(T.noInvoices).font(.system(size: 14)).foregroundStyle(Shell.muted).padding(16) }
                            ForEach(Array(open.enumerated()), id: \.element.id) { index, invoice in
                                Button { if model.features.invoicePayment { paying = invoice } } label: {
                                    CardRow("\(invoice.invoiceNumber) · \(invoice.customerName ?? "")",
                                            subtitle: T.invoiceLine(T.short(invoice.amount.value), T.short(invoice.paid.value),
                                                                    OwnerPeriod.short(invoice.dueDate)),
                                            last: index == open.count - 1) {
                                        ShellPill(MachineReportOwnerTexts.invoiceStatus(invoice), tone: invoice.overdue ? .bad : .waiting)
                                    }
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                    }
                }
                .padding(.horizontal, 16).padding(.bottom, 16)
            }
            .refreshable { await reload() }
            HStack(spacing: 10) {
                if model.features.expenses {
                    OutlineButton(T.expenses(expenses.value?.items.count ?? 0), height: 54) { push(OwnerRoute.fieldSpend) }
                }
                if model.features.invoicePayment {
                    PrimaryButton(T.recordPayment, enabled: !open.isEmpty, identifier: "money.recordPayment") { choosing = true }
                }
            }
            .padding(.horizontal, 16).padding(.vertical, 12)
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .task(id: "\(model.changeTick)-\(period.rawValue)") { await reload() }
        .confirmationDialog(T.recordPayment, isPresented: $choosing, titleVisibility: .visible) {
            ForEach(open) { invoice in
                Button("\(invoice.invoiceNumber) · \(invoice.customerName ?? "") · \(T.short(invoice.balance.value))") { paying = invoice }
            }
        }
        .sheet(item: $paying) { invoice in
            OwnerInvoicePaymentSheet(model: model, invoice: invoice) { Task { await reload() } }
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
        }
        if f.expenses { await expenses.load(model, .expenses(pendingOnly: true), OwnerAPI.expenses(status: "PENDING_APPROVAL")) }
    }
}

extension MachineReportOwnerTexts {
    /// "Unpaid", "Part paid", "Paid", "Overdue".
    static func invoiceStatus(_ invoice: CreditInvoiceDTO) -> String {
        if invoice.overdue { return overdue }
        switch invoice.status {
        case "PART_PAID": return "Part paid"
        case "PAID": return "Paid"
        default: return "Unpaid"
        }
    }
}

/// Record a payment (part or full) of a credit invoice from the office (online, `recordCreditInvoicePayment`).
struct OwnerInvoicePaymentSheet: View {
    let model: OwnerModel
    let invoice: CreditInvoiceDTO
    let saved: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var clientID = UUID()
    @State private var amount = ""
    @State private var method = "CASH"
    @State private var reference = ""
    @State private var note = ""
    @State private var receivedAt = Date()
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        let value = Decimal(string: amount.replacingOccurrences(of: ",", with: "."), locale: Locale(identifier: "en_US_POSIX"))
        let valid = (value ?? 0) > 0 && (value ?? 0) <= invoice.balance.value
            && (method == "CASH" || !reference.trimmingCharacters(in: .whitespaces).isEmpty)
        let blocked = model.mutationBlock(permitted: model.features.invoicePayment, showingCachedData: false)
        NavigationStack {
            Form {
                Section {
                    LabeledContent("Invoice", value: invoice.invoiceNumber)
                    LabeledContent("Customer", value: invoice.customerName ?? "")
                    LabeledContent("Balance", value: OwnerFormat.money(invoice.balance, currency: invoice.currency))
                }
                Section {
                    Picker("Method", selection: $method) {
                        Text("Cash").tag("CASH")
                        Text("Bank").tag("BANK")
                        Text("M-money").tag("MOBILE_MONEY")
                    }
                    .pickerStyle(.segmented)
                    TextField("Amount received", text: $amount).keyboardType(.decimalPad).accessibilityIdentifier("pay.amount")
                    if method != "CASH" { TextField("Reference", text: $reference) }
                    DatePicker("Received", selection: $receivedAt, in: ...Date())
                    TextField("Note (optional)", text: $note, axis: .vertical)
                }
                if let blocked { Section { Text(blocked.message).foregroundStyle(.secondary) } }
                if let error { Section { Text(error).foregroundStyle(.red) } }
            }
            .navigationTitle(T.recordPayment)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { Task { await save(value ?? 0) } }.disabled(!valid || busy || blocked != nil)
                }
            }
        }
    }

    private func save(_ value: Decimal) async {
        guard let repository = model.repository else { return }
        busy = true
        defer { busy = false }
        do {
            let ref = reference.trimmingCharacters(in: .whitespaces)
            let trimmedNote = note.trimmingCharacters(in: .whitespacesAndNewlines)
            _ = try await repository.send(OwnerAPI.recordCreditInvoicePayment(invoice.id, CreditInvoicePaymentIn(
                clientID: clientID, amount: value, method: method, reference: method == "CASH" || ref.isEmpty ? nil : ref,
                receivedAt: min(receivedAt, Date()), note: trimmedNote.isEmpty ? nil : trimmedNote)))
            saved()
            dismiss()
        } catch {
            self.error = DecisionErrorText.message(for: error)
            model.handle(error)
        }
    }
}

// MARK: - Reports

/// Reports (design OwnerReports): machine hours by reason, hours sold and used, and the report exports.
struct OwnerReportsView: View {
    let model: OwnerModel
    let back: () -> Void
    @State private var period: OwnerPeriod = .month
    @State private var reports = Loader<Page<MachineReportDTO>>()
    @State private var orders = Loader<Page<HoursPurchaseDTO>>()
    @State private var hours = Loader<[CustomerHoursSummaryDTO]>()
    @State private var pdfURL: URL?
    @State private var busy: String?
    @State private var error: String?

    var body: some View {
        let summary = MachineHoursSummary.of(reports.value?.items ?? [])
        let sold = SoldByMethod.of(orders.value?.items ?? [])
        let left = (hours.value ?? []).reduce(Decimal(0)) { $0 + $1.left.value }
        let currency = orders.value?.items.first?.currency ?? ""
        VStack(spacing: 0) {
            ShellHeader(T.reportsTitle, action: back) {
                ShellSegments([(OwnerPeriod.week, OwnerPeriod.week.label), (.month, OwnerPeriod.month.label)], selection: $period)
            }
            ScrollView {
                VStack(spacing: 0) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(T.machineHoursIn(period.phrase)).font(.system(size: 13)).foregroundStyle(Shell.muted)
                        Text("\(T.h(summary.total)) h").font(.system(size: 26, weight: .bold)).foregroundStyle(Shell.text)
                        SplitBar(summary.byReason.enumerated().map { i, r in
                            (percent(r.hours, of: summary.total), Shell.series[min(i, Shell.series.count - 1)])
                        }, height: 12)
                        FlowLegend(items: summary.byReason.enumerated().map { i, r in
                            (Shell.series[min(i, Shell.series.count - 1)], "\(r.name) \(T.h(r.hours)) h")
                        })
                    }
                    .padding(16).frame(maxWidth: .infinity, alignment: .leading)
                    .background(Shell.card, in: RoundedRectangle(cornerRadius: 18)).padding(.top, 4)
                    HStack(spacing: 12) {
                        figure(T.hoursSold, "\(T.h(sold.hours)) h", OwnerFormat.money(sold.total, currency: currency))
                        figure(T.hoursUsed, "\(T.h(summary.productive)) h", T.stillWithCustomers(T.h(left)))
                    }
                    .padding(.top, 12)
                    SectionLabel(T.reportsHeader).padding(.top, 18).padding(.bottom, 8)
                    VStack(spacing: 0) {
                        ForEach(Array(T.reportCodes.enumerated()), id: \.offset) { index, item in
                            Button { Task { await open(item.code) } } label: {
                                CardRow(item.title, last: index == T.reportCodes.count - 1) {
                                    if busy == item.code { ProgressView() } else { Text("›").foregroundStyle(Shell.muted) }
                                }
                            }
                            .buttonStyle(.plain)
                            .disabled(!model.isOnline || busy != nil)
                        }
                    }
                    .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                    if let error { Text(error).font(.system(size: 13)).foregroundStyle(Shell.badText).padding(.top, 8) }
                }
                .padding(.horizontal, 16).padding(.bottom, 16)
            }
            .refreshable { await reload() }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .task(id: "\(model.changeTick)-\(period.rawValue)") { await reload() }
        .quickLookPreview($pdfURL)
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

    private func reload() async {
        let range = period.range
        if model.features.machineReports {
            await reports.load(model, .machineReports(from: range.from, to: range.to), OwnerAPI.machineReports(from: range.from, to: range.to))
        }
        if model.features.hoursRead {
            await orders.load(model, .hoursPurchases(from: range.from, to: range.to), OwnerAPI.hoursPurchases(from: range.from, to: range.to))
            await hours.load(model, .customerHoursSummary, OwnerAPI.customerHoursSummary())
        }
    }

    /// Downloads the report's PDF for the period and previews it.
    private func open(_ code: String) async {
        guard let repository = model.repository else { return }
        busy = code
        defer { busy = nil }
        let range = period.range
        let dated = ["machine_hours", "sales_collections", "credit_invoice_payments", "cash"].contains(code)
        do {
            let raw = try await repository.send(OwnerAPI.reportPDF(code, from: dated ? range.from : nil, to: dated ? range.to : nil))
            let dir = FileManager.default.temporaryDirectory.appendingPathComponent("reports", isDirectory: true)
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            let file = dir.appendingPathComponent("\(code).pdf")
            try raw.data.write(to: file, options: [.atomic, .completeFileProtection])
            error = nil
            pdfURL = file
        } catch {
            self.error = DecisionErrorText.message(for: error)
            model.handle(error)
        }
    }
}

/// Legend entries that wrap onto several lines.
private struct FlowLegend: View {
    let items: [(Color, String)]

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 140), alignment: .leading)], alignment: .leading, spacing: 6) {
            ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                (Text("■ ").foregroundColor(item.0) + Text(item.1).foregroundColor(Shell.text)).font(.system(size: 13))
            }
        }
    }
}
#endif
