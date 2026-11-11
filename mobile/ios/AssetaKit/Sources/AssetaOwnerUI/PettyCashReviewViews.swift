#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

private typealias T = PettyCashReviewText

/// Approvals section "Petty cash to approve" (DEC-033; `tenant.pettycash.read` + `tenant.pettycash.approve`).
struct PendingPettyCashSection: View {
    let movements: Loader<Page<PettyCashMovementDTO>>
    let adjustments: Loader<Page<PettyCashAdjustmentDTO>>

    var body: some View {
        let rows = T.rows(movements: movements.value?.items ?? [], adjustments: adjustments.value?.items ?? [])
        Section(T.section) {
            if rows.isEmpty {
                Text(movements.value == nil ? (movements.error ?? "Loading…") : T.empty).foregroundStyle(.secondary)
            }
            ForEach(rows) { row in
                NavigationLink(value: row.route) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(T.headline(row)).font(.headline)
                        Text(T.summary(row)).font(.subheadline).foregroundStyle(.secondary)
                        if let reason = T.reasonLine(row) { Text(reason).font(.caption).foregroundStyle(.secondary).lineLimit(2) }
                        if let at = T.createdAt(row) { Text(OwnerFormat.stamp(at)).font(.caption).foregroundStyle(.secondary) }
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }
}

/// One petty cash funding / top-up (`adjustment` false) or fund adjustment, read by id: approve or reject while it
/// waits. Online only; never by its proposer (nor, the server adds, by the fund's holder).
struct PettyCashReviewView: View {
    let model: OwnerModel
    let id: UUID
    let adjustment: Bool
    @State private var movement = Loader<PettyCashMovementDTO>()
    @State private var record = Loader<PettyCashAdjustmentDTO>()
    @State private var expenses = Loader<[PettyCashTopUpExpenseDTO]>()
    @State private var decidedMovement: PettyCashMovementDTO?
    @State private var decidedAdjustment: PettyCashAdjustmentDTO?
    @State private var sheet: Mode?
    @State private var message: String?

    enum Mode: String, Identifiable { case approve, reject; var id: String { rawValue } }

    private var m: PettyCashMovementDTO? { decidedMovement ?? movement.value }
    private var a: PettyCashAdjustmentDTO? { decidedAdjustment ?? record.value }
    private var request: PettyCashRequest? { adjustment ? a.map(PettyCashRequest.adjustment) : m.map(PettyCashRequest.movement) }
    private var error: String? { adjustment ? record.error : movement.error }

    var body: some View {
        Form {
            if let request {
                let (status, createdBy, fields, decision): (String, UUID?, [DecisionField], [DecisionField]) = switch request {
                case let .movement(m): (m.status, m.createdBy, T.fields(m),
                                        T.decisionFields(decidedByName: m.decidedByName, decidedBy: m.decidedBy, note: m.decisionNote))
                case let .adjustment(a): (a.status, a.createdBy, T.fields(a),
                                          T.decisionFields(decidedByName: a.decidedByName, decidedBy: a.decidedBy, note: a.decisionNote))
                }
                Section(T.card) {
                    Text(T.headline(request)).font(.headline)
                    ForEach(fields, id: \.self) { LabeledContent($0.label, value: $0.value) }
                    LabeledContent(T.fieldStatus) { Pill(text: T.status(status), color: T.statusTone(status).color) }
                    ForEach(decision, id: \.self) { LabeledContent($0.label, value: $0.value) }
                }
                if case let .movement(m) = request, m.kind == PettyCashMovementDTO.topUp { expensesSection(m) }
                if T.decidable(status) { decisionSection(createdBy: createdBy) }
                if let message { Text(message).foregroundStyle(Brand.amber).accessibilityIdentifier("pettyCash.message") }
            } else if let error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView()
            }
        }
        .navigationTitle(adjustment ? T.titleAdjustment : T.titleMovement)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
        .sheet(item: $sheet) { mode in
            if let request {
                PettyCashDecisionSheet(model: model, request: request, approve: mode == .approve) { updated, text in
                    switch updated {
                    case let .movement(m)?: decidedMovement = m
                    case let .adjustment(a)?: decidedAdjustment = a
                    case nil: break
                    }
                    message = text
                    UIAccessibility.post(notification: .announcement, argument: text)
                    if updated == nil { await reload() }
                }
            }
        }
    }

    @ViewBuilder private func expensesSection(_ m: PettyCashMovementDTO) -> some View {
        Section(T.expenses) {
            if expenses.value == nil, expenses.error != nil {
                Text(T.expensesFailed).font(.footnote).foregroundStyle(.secondary)
            } else if let rows = expenses.value {
                if rows.isEmpty { Text(T.expensesNone).font(.footnote).foregroundStyle(.secondary) }
                ForEach(rows) { Text(T.expenseLine($0, currency: m.currency)) }
            } else {
                ProgressView()
            }
        }
    }

    @ViewBuilder private func decisionSection(createdBy: UUID?) -> some View {
        Section {
            let cached = adjustment ? record.isFromCache : movement.isFromCache
            if let block = model.mutationBlock(permitted: model.features.pettyCashApprove, showingCachedData: cached) {
                BlockedNote(block: block)
            } else if T.isOwn(createdBy: createdBy, userID: model.me.userID) {
                Label(T.own, systemImage: "lock").font(.footnote).foregroundStyle(.secondary)
                    .accessibilityIdentifier("pettyCash.own")
            } else {
                HStack {
                    Button(T.approve) { sheet = .approve }
                        .buttonStyle(.borderedProminent).tint(Palette.live)
                        .accessibilityIdentifier("pettyCash.approve")
                    Spacer()
                    Button(T.reject, role: .destructive) { sheet = .reject }
                        .buttonStyle(.bordered)
                        .accessibilityIdentifier("pettyCash.reject")
                }
            }
        } header: { Text(T.decision) } footer: {
            Text(adjustment ? T.explanationAdjustment : T.explanationMovement)
        }
    }

    private func reload() async {
        if adjustment {
            await record.load(model, .pettyCashAdjustment(id), OwnerAPI.pettyCashAdjustment(id))
            if record.error == nil && !record.isFromCache { decidedAdjustment = nil }
        } else {
            await movement.load(model, .pettyCashMovement(id), OwnerAPI.pettyCashMovement(id))
            if movement.error == nil && !movement.isFromCache { decidedMovement = nil }
            if m?.kind == PettyCashMovementDTO.topUp {
                await expenses.load(model, .pettyCashMovementExpenses(id), OwnerAPI.pettyCashMovementExpenses(id))
            }
        }
    }
}

/// "Approve this request?" with an optional note, or "Reject this request?" with a required reason.
struct PettyCashDecisionSheet: View {
    let model: OwnerModel
    let request: PettyCashRequest
    let approve: Bool
    /// The decided record (nil when it must be reloaded) and the message to show.
    let done: (PettyCashRequest?, String) async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var text = ""
    @State private var working = false
    @State private var error: String?
    @State private var idempotencyKey = UUID()

    private var canSubmit: Bool { T.canDecide(approve: approve, note: text) }
    private var tooShort: Bool { !approve && !text.isEmpty && !canSubmit }

    var body: some View {
        NavigationStack {
            Form {
                Section { Text(T.headline(request)) }
                Section {
                    TextField(approve ? T.noteOptional : T.reasonRequired, text: $text, axis: .vertical)
                        .lineLimit(2...5)
                        .accessibilityIdentifier(approve ? "pettyCash.approve.note" : "pettyCash.reject.reason")
                    if tooShort { Text(T.errReasonShort).font(.footnote).foregroundStyle(Palette.offline) }
                }
                if let error {
                    Text(error).font(.footnote).foregroundStyle(Palette.offline).accessibilityIdentifier("pettyCash.error")
                }
            }
            .navigationTitle(approve ? T.approveTitle : T.rejectTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button(T.cancel) { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(approve ? T.approve : T.reject) { Task { await submit() } }
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
            let updated: PettyCashRequest = switch request {
            case let .movement(m):
                .movement(try await repository.send(OwnerAPI.decidePettyCashMovement(m.id, approve: approve, note: text,
                                                                                    idempotencyKey: idempotencyKey)))
            case let .adjustment(a):
                .adjustment(try await repository.send(OwnerAPI.decidePettyCashAdjustment(a.id, approve: approve, note: text,
                                                                                        idempotencyKey: idempotencyKey)))
            }
            dismiss()
            await done(updated, T.done(approve: approve))
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
