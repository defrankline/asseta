#if os(iOS)
import AssetaAppShell
import AssetaCapture
import AssetaModel
import AssetaSync
import SwiftUI

private typealias T = MachineReportTexts

/// Money (design Money): cash in hand, collections by method, handed over, expenses; Hand over, Expense, Petty cash; and
/// payments on open credit invoices (`CREDIT_INVOICE_PAYMENT`). Every record list stays one tap away ("Records").
struct MoneyView: View {
    let model: FieldModel
    let back: () -> Void
    let open: (FieldRoute) -> Void
    let sheet: (FieldSheet) -> Void
    let recordExpense: () -> Void
    @State private var period: ActivityPeriod = .today

    var body: some View {
        let since = period.start()
        let summary = model.cashSummary()
        let base = summary?.baseCurrency ?? model.baseCurrency
        let line = summary?.lines.first { $0.currency == base } ?? summary?.lines.first
        let sales = FieldActivity.salesByMethod(model.myOperations, since: since)
        let collections = sum(model.inbox.collections.filter { $0.at >= since && $0.status != .rejected }.map(\.amount))
        let handovers = model.inbox.handovers.filter { $0.at >= since && $0.status != .rejected }
        let handed = sum(handovers.map(\.amount))
        let expenses = model.inbox.expenses.filter { $0.at >= since && $0.status != .rejected }
        let spent = sum(expenses.map(\.amount))
        VStack(spacing: 0) {
            ShellHeader(T.tileMoney, action: back) {
                ShellSegments(ActivityPeriod.allCases.map { ($0, $0.label) }, selection: $period)
            }
            ScrollView {
                VStack(spacing: 0) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(T.moneyCashInHand).font(.system(size: 13, weight: .semibold)).opacity(0.8)
                        Text(model.money(line?.estimatedInHand ?? 0)).font(.system(size: 32, weight: .bold)).tracking(-0.6)
                            .minimumScaleFactor(0.6).lineLimit(1).accessibilityIdentifier("money.inHand")
                        Text(T.moneyCashLine(collected: model.money(max(collections, sales.cash), currency: false),
                                             handed: model.money(handed, currency: false), expenses: model.money(spent, currency: false)))
                            .font(.system(size: 13)).padding(.top, 2)
                    }
                    .foregroundStyle(Shell.onAccent)
                    .padding(18).frame(maxWidth: .infinity, alignment: .leading)
                    .background(Shell.accent, in: RoundedRectangle(cornerRadius: 20))
                    .padding(.top, 4)

                    SectionLabel(T.moneyByMethod).padding(.top, 18).padding(.bottom, 8)
                    VStack(spacing: 0) {
                        ValueRow(T.moneyCash, model.money(sales.cash, currency: false))
                        ValueRow(T.moneyBank, model.money(sales.bank, currency: false))
                        ValueRow(T.moneyMobile, model.money(sales.mobileMoney, currency: false))
                        HStack {
                            Text(T.moneyCredit) + Text(" " + T.moneyCreditAwaiting).font(.system(size: 12)).foregroundColor(Shell.warnText)
                            Spacer()
                            Text(model.money(sales.credit, currency: false)).fontWeight(.semibold).monospacedDigit()
                        }
                        .font(.system(size: 15)).foregroundStyle(Shell.text).padding(.horizontal, 16).padding(.vertical, 13)
                        Divider().overlay(Shell.border)
                        ValueRow(T.moneyTotalSold, model.money(sales.total, currency: false), bold: true, last: true)
                    }
                    .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))

                    HStack(spacing: 12) {
                        smallCard(T.moneyHandedOver, model.money(handed, currency: false),
                                  handovers.contains { $0.status == .claimed || $0.status == .waiting } ? T.moneyAwaitingCheck
                                      : handovers.isEmpty ? nil : T.moneyAllChecked,
                                  warn: handovers.contains { $0.status == .claimed || $0.status == .waiting })
                        smallCard(T.moneyExpenses, model.money(spent, currency: false),
                                  T.moneyReceipts(expenses.count,
                                                  pending: expenses.filter { [.pendingApproval, .waiting, .notSynced].contains($0.status) }.count),
                                  warn: false)
                    }
                    .padding(.top, 18)

                    if model.access.invoicePayment { invoices }

                    Button { open(.moneyRecords) } label: {
                        HStack {
                            Text(T.moneyRecords).font(.system(size: 13, weight: .semibold)).tracking(0.6)
                            Spacer()
                            Image(systemName: "chevron.right")
                        }
                        .foregroundStyle(Shell.muted).padding(16)
                        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                    }
                    .buttonStyle(.plain).padding(.top, 18)
                    .accessibilityIdentifier("money.records")
                }
                .padding(.horizontal, 16)
            }
            .refreshable { await model.sync(force: true); await model.refreshAccountability() }
            HStack(spacing: 10) {
                actionButton(T.moneyHandOver, "arrow.up.forward.circle", primary: true, enabled: model.canRecordCash) {
                    sheet(.handover)
                }
                actionButton(T.moneyExpense, "doc.text.viewfinder", enabled: model.canRecordExpenses) { recordExpense() }
                actionButton(T.moneyPettyCash, "tray.full", enabled: model.access.pettyCash) { open(.pettyCash) }
            }
            .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 12)
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
    }

    @ViewBuilder private var invoices: some View {
        let open = model.openCreditInvoices.filter { $0.balance > 0 }
        if !open.isEmpty {
            SectionLabel(T.creditInvoices).padding(.top, 18).padding(.bottom, 8)
            VStack(spacing: 0) {
                ForEach(Array(open.enumerated()), id: \.element.id) { index, invoice in
                    Button { sheet(.invoicePayment(invoice.id)) } label: {
                        CardRow("\(invoice.invoice.invoiceNumber) · \(invoice.invoice.customerName ?? "")",
                                subtitle: T.invoiceLine(model.money(invoice.invoice.amount.value, currency: false),
                                                        model.money(invoice.invoice.amount.value - invoice.balance, currency: false),
                                                        invoice.invoice.dueDate.map(Self.day)),
                                last: index == open.count - 1) {
                            VStack(alignment: .trailing, spacing: 4) {
                                ShellPill(T.invoiceStatus(invoice.invoice.status, overdue: invoice.invoice.overdue),
                                           tone: invoice.invoice.overdue ? .bad : .waiting)
                                Text(T.payTitle).font(.system(size: 12, weight: .semibold)).foregroundStyle(Shell.accent)
                            }
                        }
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("money.invoice.\(invoice.invoice.invoiceNumber)")
                }
            }
            .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
        }
    }

    /// "2026-11-30" → "30 Nov".
    static func day(_ text: String) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        guard let date = f.date(from: text) else { return text }
        return date.formatted(.dateTime.day().month(.abbreviated))
    }

    private func sum(_ amounts: [String]) -> Decimal {
        amounts.compactMap { DecimalString(string: $0)?.value }.reduce(0, +)
    }

    private func smallCard(_ title: String, _ value: String, _ detail: String?, warn: Bool) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.system(size: 13)).foregroundStyle(Shell.muted)
            Text(value).font(.system(size: 19, weight: .bold)).foregroundStyle(Shell.text).monospacedDigit()
            if let detail { Text(detail).font(.system(size: 12)).foregroundStyle(warn ? Shell.warnText : Shell.muted) }
        }
        .padding(14).frame(maxWidth: .infinity, alignment: .leading)
        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
    }

    private func actionButton(_ title: String, _ icon: String, primary: Bool = false, enabled: Bool,
                              action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 6) {
                Image(systemName: icon).font(.system(size: 20, weight: .semibold))
                Text(title).font(.system(size: 14, weight: primary ? .bold : .semibold))
            }
            .frame(maxWidth: .infinity, minHeight: 76)
            .foregroundStyle(primary ? Shell.onAccent : Shell.text)
            .background(primary ? Shell.accent : Shell.card, in: RoundedRectangle(cornerRadius: 16))
            .opacity(enabled ? 1 : 0.45)
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityIdentifier("money.\(title)")
    }
}

/// Record a payment (part or full) on an open credit invoice, in the field (`CREDIT_INVOICE_PAYMENT`).
struct InvoicePaymentFormView: View {
    let model: FieldModel
    let invoiceID: UUID
    @Environment(\.dismiss) private var dismiss
    @State private var clientID = UUID()
    @State private var amountText = ""
    @State private var method = "CASH"
    @State private var reference = ""
    @State private var note = ""
    @State private var receivedAt = Date()
    @State private var photos: [(evidence: StoredEvidence, data: Data)] = []
    @State private var error: String?

    var body: some View {
        let invoice = model.openCreditInvoices.first { $0.id == invoiceID }
        let a = model.access
        let methods = a.saleMethods
        NavigationStack {
            Form {
                if let invoice {
                    Section {
                        LabeledContent(T.payInvoice, value: invoice.invoice.invoiceNumber)
                        LabeledContent(MachineReportTexts.saleCustomer, value: invoice.invoice.customerName ?? "")
                        Text(T.payBalance(model.money(invoice.balance))).font(.headline)
                    }
                    Section {
                        if methods.count > 1 {
                            Picker(FieldAccountabilityTexts.hoursMethod, selection: $method) {
                                ForEach(methods, id: \.self) { Text(T.saleMethodLabel($0)).tag($0) }
                            }.pickerStyle(.segmented)
                        }
                        TextField(T.payAmount, text: $amountText).keyboardType(.decimalPad).font(.title3.monospacedDigit())
                            .accessibilityIdentifier("pay.amount")
                        if method != "CASH" { TextField(FieldAccountabilityTexts.hoursReference, text: $reference) }
                        DatePicker(FieldAccountabilityTexts.hoursReceived, selection: $receivedAt, in: ...Date())
                        TextField(FieldAccountabilityTexts.noteOptional, text: $note, axis: .vertical)
                    } footer: { Text(T.payFooter) }
                    if method != "CASH" {
                        EvidencePhotosSection(model: model, photos: $photos, error: $error)
                    }
                    if case let .failure(problems) = CreditPaymentRules.check(amountText: amountText, balance: invoice.balance,
                                                                             method: method, reference: reference,
                                                                             noncashAllowed: a.noncashPayments),
                       !amountText.isEmpty {
                        Section { Text(problems.text).foregroundStyle(.red).font(.footnote) }
                    }
                } else {
                    ContentUnavailableView(T.payTitle, systemImage: "doc.text", description: Text(T.payErrPaid))
                }
            }
            .navigationTitle(T.payTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { photos.forEach { model.discardEvidence($0.evidence) }; dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(T.paySave) { save(invoice) }.disabled(invoice == nil || !valid(invoice)).accessibilityIdentifier("pay.save")
                }
            }
            .alert("Not saved", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
                Button("OK") { error = nil }
            } message: { Text(error ?? "") }
        }
        .interactiveDismissDisabled()
    }

    private func valid(_ invoice: OpenCreditInvoice?) -> Bool {
        guard let invoice else { return false }
        if case .success = CreditPaymentRules.check(amountText: amountText, balance: invoice.balance, method: method,
                                                    reference: reference, noncashAllowed: model.access.noncashPayments) { return true }
        return false
    }

    private func save(_ invoice: OpenCreditInvoice?) {
        guard let invoice else { return }
        let a = model.access
        do {
            try model.perform {
                try $0.recordCreditInvoicePayment(invoice, amountText: amountText, method: method, reference: reference, note: note,
                                                  evidence: method == "CASH" ? [] : photos.map(\.evidence),
                                                  noncashAllowed: a.noncashPayments, cashHolderID: nil,
                                                  receivedAt: min(receivedAt, Date()), clientID: clientID)
            }
            if method == "CASH" { photos.forEach { model.discardEvidence($0.evidence) } }
            photos = []
            dismiss()
        } catch {
            self.error = FieldErrors.describe(error)
        }
    }
}
#endif
