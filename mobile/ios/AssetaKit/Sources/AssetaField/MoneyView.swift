#if os(iOS)
import AssetaAppShell
import AssetaCapture
import AssetaModel
import AssetaSync
import SwiftUI

private typealias T = MachineReportTexts
private typealias S = SupervisorShellTexts
private typealias F = SupervisorFigures

/// Money (design Money, as Android `MoneyHomeScreen`): cash in hand, collections by method, handed over, expenses; Hand
/// over, Expense and Petty cash (each only with its permission), "Record a credit invoice payment"
/// (`CREDIT_INVOICE_PAYMENT`), and every record list one tap away ("Cash records, transfers and more").
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
        // Collected: my sales and credit-invoice payments of the period, credit left out.
        let collected = sales.total - sales.credit
        let handovers = model.inbox.handovers.filter { $0.at >= since && $0.status != .rejected }
        let handed = sum(handovers.map(\.amount))
        let expenses = model.inbox.expenses.filter { $0.at >= since && $0.status != .rejected }
        let spent = sum(expenses.map(\.amount))
        let a = model.access
        VStack(spacing: 0) {
            ShellHeader(T.tileMoney, action: back) {
                ShellSegments(ActivityPeriod.allCases.map { ($0, $0.label) }, selection: $period)
            }
            ScrollView {
                VStack(spacing: 0) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(T.moneyCashInHand).font(.system(size: 13, weight: .semibold)).opacity(0.8)
                        if let line {
                            Text(F.money(line.estimatedInHand, currency: line.currency)).font(.system(size: 32, weight: .bold)).tracking(-0.6)
                                .minimumScaleFactor(0.6).lineLimit(1).accessibilityIdentifier("money.inHand")
                        } else {
                            Text(S.noCash).font(.system(size: 17, weight: .bold)).accessibilityIdentifier("money.inHand")
                        }
                        Text(T.moneyCashLine(collected: F.grouped(collected), handed: F.grouped(handed), expenses: F.grouped(spent)))
                            .font(.system(size: 13)).padding(.top, 2)
                    }
                    .foregroundStyle(Shell.onAccent)
                    .padding(18).frame(maxWidth: .infinity, alignment: .leading)
                    .background(Shell.accent, in: RoundedRectangle(cornerRadius: 20))
                    .padding(.top, 4)

                    SectionLabel(T.moneyByMethod).padding(.top, 18).padding(.bottom, 8)
                    VStack(spacing: 0) {
                        ValueRow(T.moneyCash, F.grouped(sales.cash))
                        ValueRow(T.moneyBank, F.grouped(sales.bank))
                        ValueRow(T.moneyMobile, F.grouped(sales.mobileMoney))
                        HStack {
                            Text(T.moneyCredit) + Text(T.moneyCreditAwaiting).font(.system(size: 12)).foregroundColor(Shell.warnText)
                            Spacer()
                            Text(F.grouped(sales.credit)).fontWeight(.semibold).monospacedDigit()
                        }
                        .font(.system(size: 15)).foregroundStyle(Shell.text).padding(.horizontal, 16).padding(.vertical, 13)
                        Divider().overlay(Shell.border)
                        ValueRow(T.moneyTotalSold, F.grouped(sales.total), bold: true, last: true)
                    }
                    .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))

                    HStack(spacing: 12) {
                        let awaiting = handovers.contains { $0.status == .claimed || $0.status == .waiting }
                        smallCard(T.moneyHandedOver, F.grouped(handed), awaiting ? T.moneyAwaitingCheck : nil, warn: awaiting)
                        smallCard(T.moneyExpenses, F.grouped(spent),
                                  T.moneyReceipts(expenses.count,
                                                  pending: expenses.filter { [.pendingApproval, .waiting, .notSynced].contains($0.status) }.count),
                                  warn: false)
                    }
                    .padding(.top, 18)

                    if model.canRecordCash || model.canRecordExpenses || a.pettyCash {
                        HStack(spacing: 10) {
                            if model.canRecordCash {
                                actionButton(T.moneyHandOver, "arrow.up.forward.circle", primary: true) { sheet(.handover) }
                            }
                            if model.canRecordExpenses { actionButton(T.moneyExpense, "doc.text.viewfinder") { recordExpense() } }
                            if a.pettyCash { actionButton(T.moneyPettyCash, "tray.full") { open(.pettyCash) } }
                        }
                        .padding(.top, 18)
                    }

                    if a.invoicePayment {
                        PrimaryButton(S.recordInvoicePayment, identifier: "money.invoicePayment") { sheet(.invoicePayment(nil)) }
                            .padding(.top, 12)
                    }

                    Button { open(.moneyRecords) } label: {
                        HStack {
                            Text(S.moneyRecords).font(.system(size: 15))
                            Spacer()
                            Image(systemName: "chevron.right")
                        }
                        .foregroundStyle(Shell.text).padding(16)
                        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                    }
                    .buttonStyle(.plain).padding(.top, 12)
                    .accessibilityIdentifier("money.records")

                    Text(S.moneyFooter).font(.system(size: 12)).foregroundStyle(Shell.muted)
                        .frame(maxWidth: .infinity, alignment: .leading).padding(.top, 12).padding(.horizontal, 4)
                }
                .padding(.horizontal, 16).padding(.bottom, 16)
            }
            .refreshable { await model.sync(force: true); await model.refreshAccountability() }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
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

    private func actionButton(_ title: String, _ icon: String, primary: Bool = false, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 6) {
                Image(systemName: icon).font(.system(size: 20, weight: .semibold))
                Text(title).font(.system(size: 14, weight: primary ? .bold : .semibold))
            }
            .frame(maxWidth: .infinity, minHeight: 76)
            .foregroundStyle(primary ? Shell.onAccent : Shell.text)
            .background(primary ? Shell.accent : Shell.card, in: RoundedRectangle(cornerRadius: 16))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("money.\(title)")
    }
}

/// A payment (part or full) on an open credit invoice chosen from those on this phone (`CREDIT_INVOICE_PAYMENT`), as
/// Android `InvoicePaymentScreen`: invoice picker ("CI-2026-00042 · Msasani", "owes 2,000,000 · due 2026-11-30"),
/// method, amount, reference and photos for bank / mobile money, received time.
struct InvoicePaymentFormView: View {
    let model: FieldModel
    @State private var invoiceID: UUID?
    @Environment(\.dismiss) private var dismiss
    @State private var clientID = UUID()
    @State private var amountText = ""
    @State private var method = "CASH"
    @State private var reference = ""
    @State private var receivedAt = Date()
    @State private var photos: [(evidence: StoredEvidence, data: Data)] = []
    @State private var error: String?

    init(model: FieldModel, invoiceID: UUID?) {
        self.model = model
        _invoiceID = State(initialValue: invoiceID)
    }

    var body: some View {
        let open = model.openCreditInvoices.filter { $0.balance > 0 }
        let invoice = open.first { $0.id == invoiceID }
        let a = model.access
        let methods = a.saleMethods
        NavigationStack {
            Form {
                Section {
                    SearchablePickerField(label: T.payInvoice, options: open.map { inv in
                        PickerOption(id: inv.id, title: S.invoiceOption(inv.invoice.invoiceNumber, inv.invoice.customerName),
                                     subtitle: S.invoiceOwes(F.grouped(inv.balance), inv.invoice.dueDate))
                    }, selection: $invoiceID, emptyMessage: S.noInvoices, identifier: "pay.invoice")
                    if methods.count > 1 {
                        Picker(FieldAccountabilityTexts.hoursMethod, selection: $method) {
                            ForEach(methods, id: \.self) { Text(T.saleMethodLabel($0)).tag($0) }
                        }.pickerStyle(.segmented)
                    }
                    TextField(T.payAmount, text: $amountText).keyboardType(.decimalPad).font(.title3.monospacedDigit())
                        .accessibilityIdentifier("pay.amount")
                    if method != "CASH" {
                        TextField(T.saleReference, text: $reference)
                        if reference.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            Text(FieldAccountabilityTexts.hoursReferenceLine).font(.footnote).foregroundStyle(.red)
                        }
                    }
                    DatePicker(FieldAccountabilityTexts.hoursReceived, selection: $receivedAt, in: ...Date())
                } footer: { Text(T.payFooter) }
                if method != "CASH" {
                    EvidencePhotosSection(model: model, photos: $photos, error: $error, title: T.salePhoto)
                }
                if let invoice, !amountText.isEmpty,
                   case let .failure(problems) = check(invoice) {
                    Section { Text(problems.text).foregroundStyle(.red).font(.footnote) }
                }
            }
            .navigationTitle(T.payTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { photos.forEach { model.discardEvidence($0.evidence) }; dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(T.paySave) { save(invoice) }.disabled(!valid(invoice)).accessibilityIdentifier("pay.save")
                }
            }
            .alert("Not saved", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
                Button("OK") { error = nil }
            } message: { Text(error ?? "") }
        }
        .interactiveDismissDisabled()
    }

    private func check(_ invoice: OpenCreditInvoice) -> Result<(amount: Decimal, reference: String?), AccountabilityRules.Problems> {
        CreditPaymentRules.check(amountText: amountText, balance: invoice.balance, method: method, reference: reference,
                                 noncashAllowed: model.access.noncashPayments)
    }

    private func valid(_ invoice: OpenCreditInvoice?) -> Bool {
        guard let invoice, case .success = check(invoice) else { return false }
        return true
    }

    private func save(_ invoice: OpenCreditInvoice?) {
        guard let invoice else { return }
        let a = model.access
        do {
            try model.perform {
                try $0.recordCreditInvoicePayment(invoice, amountText: amountText, method: method, reference: reference, note: "",
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
