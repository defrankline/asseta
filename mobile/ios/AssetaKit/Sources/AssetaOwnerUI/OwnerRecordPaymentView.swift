#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

private typealias T = OwnerPaymentTexts

/// Record payment of a credit invoice (Android `ui/money/PaymentForm.kt`): INVOICE · METHOD · RECEIVED, online only,
/// `tenant.hours.invoice_payment`, at most the balance, a reference for bank and mobile money, one idempotency key per
/// form visit (a retry after a network failure reuses it).
struct OwnerRecordPaymentView: View {
    let model: OwnerModel
    @Environment(\.dismiss) private var dismiss
    @State private var invoices = Loader<Page<CreditInvoiceDTO>>()
    @State private var draft: OwnerPaymentDraft
    @State private var busy = false
    @State private var error: String?
    @State private var done: String?

    init(model: OwnerModel, preselected: UUID?) {
        self.model = model
        _draft = State(initialValue: OwnerPaymentDraft(invoiceID: preselected))
    }

    var body: some View {
        let open = OwnerPaymentRules.open(invoices.value?.items ?? [])
        let invoice = open.first { $0.id == draft.invoiceID }
        let blocked = model.mutationBlock(permitted: model.features.invoicePayment, showingCachedData: invoices.isFromCache)
        let problem = OwnerPaymentRules.problem(draft, invoice: invoice)
        VStack(spacing: 0) {
            ShellHeader(T.title, action: { dismiss() })
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    if let done {
                        Text(done).font(.system(size: 14, weight: .semibold)).foregroundStyle(Shell.accent)
                    }
                    if let blocked { Text(blocked.message).font(.system(size: 13)).foregroundStyle(Shell.muted) }
                    SectionLabel(T.invoice).padding(.top, 4)
                    invoiceList(open)
                    FieldBox(T.amountLabel(invoice?.currency)) {
                        TextField("", text: $draft.amount).keyboardType(.decimalPad)
                            .accessibilityIdentifier("payment-amount")
                    }
                    SectionLabel(T.method).padding(.top, 4)
                    ShellSegments(OwnerPayMethod.allCases.map { ($0, $0.label) }, selection: $draft.method)
                    if draft.method.needsReference {
                        FieldBox(T.reference) {
                            TextField(T.referenceHint, text: $draft.reference).textInputAutocapitalization(.characters)
                                .accessibilityIdentifier("payment-reference")
                        }
                    }
                    Text(draft.method.needsReference ? T.claimedNote : T.cashNote).font(.system(size: 13)).foregroundStyle(Shell.muted)
                    SectionLabel(T.received).padding(.top, 4)
                    ShellSegments([(false, T.today), (true, T.yesterday)], selection: $draft.yesterday)
                    FieldBox(T.note) { TextField("", text: $draft.note, axis: .vertical).lineLimit(2...5) }
                    if let message = error ?? (draft.amount.isEmpty && draft.reference.isEmpty ? nil : problem) {
                        Text(message).font(.system(size: 14)).foregroundStyle(Shell.badText)
                    }
                    PrimaryButton(T.save, enabled: !busy && problem == nil && blocked == nil, identifier: "payment-save") {
                        Task { await submit(invoice) }
                    }
                    .padding(.top, 4)
                }
                .padding(.horizontal, 16).padding(.bottom, 24)
            }
            .refreshable { await reload() }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .onChange(of: draft.amount) { _, v in if v.count > 20 { draft.amount = String(v.prefix(20)) } }
        .onChange(of: draft.reference) { _, v in if v.count > 120 { draft.reference = String(v.prefix(120)) } }
        .onChange(of: draft.note) { _, v in if v.count > 1000 { draft.note = String(v.prefix(1000)) } }
        .onChange(of: draft) { _, _ in error = nil }
        .task(id: model.changeTick) { await reload() }
    }

    @ViewBuilder private func invoiceList(_ open: [CreditInvoiceDTO]) -> some View {
        if invoices.value != nil {
            if open.isEmpty {
                Text(T.noOpen).font(.system(size: 14)).foregroundStyle(Shell.muted)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(open.enumerated()), id: \.element.id) { index, inv in
                        Button { draft.invoiceID = inv.id } label: {
                            CardRow(OwnerMoneyParity.invoiceTitle(inv), subtitle: T.left(inv), last: index == open.count - 1) {
                                if inv.id == draft.invoiceID {
                                    ShellPill("✓", tone: .due)
                                } else {
                                    let pill = OwnerMoneyParity.pill(inv)
                                    ShellPill(pill.label, tone: pill.tone.shell)
                                }
                            }
                        }
                        .buttonStyle(.plain)
                        .accessibilityAddTraits(inv.id == draft.invoiceID ? .isSelected : [])
                    }
                }
                .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
            }
        } else if let failure = invoices.error {
            Text(failure).font(.system(size: 14)).foregroundStyle(Shell.muted)
        }
    }

    private func reload() async {
        await invoices.load(model, .creditInvoices, OwnerAPI.creditInvoices())
    }

    /// Sends the payment once (the same key on a retry after a network failure).
    private func submit(_ invoice: CreditInvoiceDTO?) async {
        let d = draft
        guard !busy, let invoice, OwnerPaymentRules.problem(d, invoice: invoice) == nil, let repository = model.repository else { return }
        busy = true
        error = nil
        defer { busy = false }
        do {
            let saved = try await repository.send(OwnerAPI.recordCreditInvoicePayment(invoice.id, OwnerPaymentRules.body(d)))
            done = T.done(saved)
            AccessibilityNotification.Announcement(T.done(saved)).post()
            // A new form visit: a second payment gets its own key.
            draft = OwnerPaymentDraft(invoiceID: saved.balance.value > 0 ? saved.id : nil)
            await reload()
        } catch {
            let code = (error as? APIError)?.code
            self.error = T.refusal(code, fallback: DecisionErrorText.message(for: error))
            if code?.hasPrefix("INVOICE_") == true { await reload() }
            model.handle(error)
        }
    }
}
#endif
