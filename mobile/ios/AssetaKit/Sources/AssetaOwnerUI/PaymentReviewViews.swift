#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

private typealias T = PaymentReviewText

/// One row of the Approvals "Payments to confirm" section.
struct PendingPaymentRow: View {
    let payment: CustomerPaymentRecordDTO

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(T.headline(payment)).font(.headline)
            Text(T.summary(payment)).font(.subheadline).foregroundStyle(.secondary)
            Text(T.received(payment)).font(.caption).foregroundStyle(.secondary)
            if let line = T.recordedBy(payment) { Text(line).font(.caption).foregroundStyle(.secondary) }
        }
        .accessibilityElement(children: .combine)
    }
}

/// Approvals section "Payments to confirm" (`tenant.finance.read` and `tenant.finance.verify`).
struct PendingPaymentsSection: View {
    let loader: Loader<Page<CustomerPaymentRecordDTO>>

    var body: some View {
        Section(T.section) {
            let items = loader.value?.items ?? []
            if items.isEmpty {
                Text(loader.value == nil ? (loader.error ?? "Loading…") : T.empty).foregroundStyle(.secondary)
            }
            ForEach(items) { payment in
                NavigationLink(value: OwnerRoute.customerPayment(payment.id)) { PendingPaymentRow(payment: payment) }
            }
        }
    }
}

/// One customer payment, read by id: confirm or reject while it waits. Online only; never by its recorder.
struct PaymentReviewView: View {
    let model: OwnerModel
    let paymentID: UUID
    @State private var record = Loader<CustomerPaymentRecordDTO>()
    @State private var evidence = Loader<[PaymentEvidenceDTO]>()
    @State private var decided: CustomerPaymentRecordDTO?
    @State private var invoiceNumbers: [UUID: String] = [:]
    @State private var sheet: Mode?
    @State private var message: String?
    @State private var photo: Int?

    enum Mode: String, Identifiable { case confirm, reject; var id: String { rawValue } }

    private var payment: CustomerPaymentRecordDTO? { decided ?? record.value }
    private var photos: [UUID] { evidence.value?.map(\.attachmentID) ?? [] }

    var body: some View {
        Form {
            if let payment {
                Section(T.card) {
                    Text(T.headline(payment)).font(.headline)
                    ForEach(T.fields(payment), id: \.self) { LabeledContent($0.label, value: $0.value) }
                    LabeledContent(T.fieldStatus) { Pill(text: T.status(payment.status), color: T.statusTone(payment.status).color) }
                    ForEach(T.decisionFields(payment), id: \.self) { LabeledContent($0.label, value: $0.value) }
                }
                links(payment)
                evidenceSection(payment)
                if T.decidable(payment) { decision(payment) }
                if let message { Text(message).foregroundStyle(Brand.amber).accessibilityIdentifier("payment.message") }
            } else if let error = record.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView()
            }
        }
        .staleBanner(record, model: model)
        .navigationTitle(T.screenTitle)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
        .sheet(isPresented: Binding(get: { photo != nil }, set: { if !$0 { photo = nil } })) {
            if let payment, let index = photo, photos.indices.contains(index) {
                EvidencePhotoView(model: model, title: T.photo(index + 1).capitalizedFirst,
                                  request: OwnerAPI.paymentEvidenceURL(paymentID: payment.id, attachmentID: photos[index]))
            }
        }
        .sheet(item: $sheet) { mode in
            if let payment {
                PaymentDecisionSheet(model: model, payment: payment, confirm: mode == .confirm) { updated, text in
                    decided = updated
                    message = text
                    UIAccessibility.post(notification: .announcement, argument: text)
                    if updated == nil { await reload() }
                }
            }
        }
    }

    @ViewBuilder private func links(_ payment: CustomerPaymentRecordDTO) -> some View {
        let purchases = T.purchases(payment)
        if !purchases.isEmpty {
            Section(T.linksPurchases) {
                ForEach(purchases, id: \.id) { purchase in
                    if model.features.allows(.hoursPurchase(purchase.id)) {
                        NavigationLink(value: OwnerRoute.hoursPurchase(purchase.id)) { Text(purchase.text) }
                    } else {
                        Text(purchase.text)
                    }
                }
            }
        }
        let invoices = T.invoices(payment, numbers: invoiceNumbers)
        if !invoices.isEmpty {
            Section(T.linksInvoices) { ForEach(invoices, id: \.self) { Text($0) } }
        }
    }

    @ViewBuilder private func evidenceSection(_ payment: CustomerPaymentRecordDTO) -> some View {
        Section(T.evidence) {
            if evidence.value == nil, evidence.error != nil {
                Text(T.evidenceFailed).font(.footnote).foregroundStyle(.secondary)
            } else if photos.isEmpty {
                Text(evidence.value == nil ? "Loading…" : T.evidenceNone).font(.footnote).foregroundStyle(.secondary)
            } else {
                ForEach(Array(photos.enumerated()), id: \.offset) { index, _ in
                    PhotoButton(label: T.photo(index + 1), isOnline: model.isOnline) { photo = index }
                        .accessibilityIdentifier("payment.photo.\(index + 1)")
                }
            }
        }
    }

    @ViewBuilder private func decision(_ payment: CustomerPaymentRecordDTO) -> some View {
        Section {
            if let block = model.mutationBlock(permitted: model.features.verifyHandovers, showingCachedData: record.isFromCache) {
                BlockedNote(block: block)
            } else if T.isOwn(payment, userID: model.me.userID) {
                Label(T.own, systemImage: "lock").font(.footnote).foregroundStyle(.secondary)
                    .accessibilityIdentifier("payment.own")
            } else {
                HStack {
                    Button(T.confirm) { sheet = .confirm }
                        .buttonStyle(.borderedProminent).tint(Palette.live)
                        .accessibilityIdentifier("payment.confirm")
                    Spacer()
                    Button(T.reject, role: .destructive) { sheet = .reject }
                        .buttonStyle(.bordered)
                        .accessibilityIdentifier("payment.reject")
                }
            }
        } header: { Text(T.decision) } footer: { Text(T.explanation) }
    }

    private func reload() async {
        async let a: Void = record.load(model, .paymentReview(paymentID), OwnerAPI.paymentReview(paymentID))
        async let b: Void = evidence.load(model, .paymentEvidence(paymentID), OwnerAPI.paymentEvidence(paymentID))
        _ = await (a, b)
        if record.error == nil && !record.isFromCache { decided = nil }
        await loadInvoiceNumbers()
    }

    /// Best effort: an invoice whose number cannot be read shows its short id.
    private func loadInvoiceNumbers() async {
        guard let repository = model.repository, let payment else { return }
        for id in Set(T.activeAllocations(payment).map(\.invoiceID)) where invoiceNumbers[id] == nil {
            if let number = try? await repository.load(.invoiceNumber(id), OwnerAPI.invoiceNumber(id)).value.invoiceNumber, !number.isEmpty {
                invoiceNumbers[id] = number
            }
        }
    }
}

/// "Confirm this payment?" with an optional note, or "Reject this payment?" with a required reason.
struct PaymentDecisionSheet: View {
    let model: OwnerModel
    let payment: CustomerPaymentRecordDTO
    let confirm: Bool
    /// The decided payment (nil when it must be reloaded) and the message to show.
    let done: (CustomerPaymentRecordDTO?, String) async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var text = ""
    @State private var working = false
    @State private var error: String?
    @State private var idempotencyKey = UUID()

    private var canSubmit: Bool { T.canDecide(confirm: confirm, note: text) }
    private var tooShort: Bool { !confirm && !text.isEmpty && !canSubmit }

    var body: some View {
        NavigationStack {
            Form {
                Section { Text(T.headline(payment)) }
                Section {
                    TextField(confirm ? T.noteOptional : T.reasonRequired, text: $text, axis: .vertical)
                        .lineLimit(2...5)
                        .accessibilityIdentifier(confirm ? "payment.confirm.note" : "payment.reject.reason")
                    if tooShort { Text(T.errReasonShort).font(.footnote).foregroundStyle(Palette.offline) }
                }
                if let error {
                    Text(error).font(.footnote).foregroundStyle(Palette.offline).accessibilityIdentifier("payment.error")
                }
            }
            .navigationTitle(confirm ? T.confirmTitle : T.rejectTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button(T.cancel) { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(confirm ? T.confirm : T.reject) { Task { await submit() } }
                        .disabled(working || !canSubmit)
                }
            }
        }
    }

    private func submit() async {
        guard let repository = model.repository, canSubmit else { return }
        working = true
        defer { working = false }
        do {
            let updated = try await repository.send(OwnerAPI.decidePayment(payment.id, confirm: confirm, note: text, idempotencyKey: idempotencyKey))
            dismiss()
            await done(updated, T.done(confirm: confirm))
        } catch {
            self.error = T.message(for: error)
            idempotencyKey = UUID() // a corrected retry is a new request
            model.handle(error)
            if T.needsReload(error) {
                dismiss()
                await done(nil, T.alreadyDecided)
            }
        }
    }
}
#endif
