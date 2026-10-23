#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

/// Approval requests; approve/reject with a note when permitted. The server enforces segregation
/// of duties (the submitter can't approve) and the app explains that refusal plainly.
struct ApprovalsView: View {
    let model: OwnerModel
    @State private var status: ApprovalStatus = .pending
    @State private var loader = Loader<Page<ApprovalRequestDTO>>()

    var body: some View {
        List {
            FilterChips(options: ApprovalText.filters, selection: $status)
                .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
            if let page = loader.value {
                if page.items.isEmpty {
                    EmptyState(title: ApprovalText.emptyTitle, message: ApprovalText.emptyMessage, systemImage: "checkmark.seal")
                }
                ForEach(page.items) { request in
                    NavigationLink(value: OwnerRoute.approval(request.id)) { ApprovalRow(request: request) }
                }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle("Approvals")
        .refreshable { await reload() }
        .task(id: ReloadKey(tick: model.changeTick, filter: status.rawValue)) { await reload() }
    }

    private func reload() async {
        await loader.load(model, .approvals(status), OwnerAPI.approvals(status: status, pageSize: 100))
    }
}

struct ApprovalRow: View {
    let request: ApprovalRequestDTO

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(OwnerFormat.money(request.amount, currency: request.currency)).font(.headline)
                Spacer()
                Pill(text: request.status.humanized, color: request.status.color)
            }
            Text(ApprovalText.summary(request)).font(.subheadline).foregroundStyle(.secondary)
            Text("Requested \(request.requestedAt.shortStamp)").font(.caption).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
    }
}

extension ApprovalStatus {
    var color: Color {
        switch self {
        case .approved: Palette.live
        case .rejected: Palette.offline
        default: Palette.warning
        }
    }
}

/// One request (found in the latest 200; there is no single-request endpoint).
struct ApprovalDetailView: View {
    let model: OwnerModel
    let approvalID: UUID
    @State private var loader = Loader<Page<ApprovalRequestDTO>>()
    @State private var decided: ApprovalRequestDTO?
    @State private var note = ""
    @State private var working = false
    @State private var decisionError: (message: String, segregation: Bool)?
    @State private var message: String?
    @State private var confirmReject = false

    private var request: ApprovalRequestDTO? { decided ?? loader.value?.items.first { $0.id == approvalID } }

    var body: some View {
        Form {
            if let request {
                Section("Request") {
                    LabeledContent("Amount", value: OwnerFormat.money(request.amount, currency: request.currency))
                    LabeledContent("Type", value: OwnerFormat.humanize(request.subjectType))
                    LabeledContent("Reason", value: request.reason)
                    LabeledContent("Requested", value: request.requestedAt.shortStamp)
                    LabeledContent("Status", value: request.status.humanized)
                    if let at = request.decidedAt { LabeledContent("Decided", value: at.shortStamp) }
                    if let decisionNote = request.decisionNote { LabeledContent("Decision note", value: decisionNote) }
                    LabeledContent("Policy", value: request.policyVersion)
                }
                if request.subjectType == "EXPENSE" {
                    ExpenseSection(model: model, expenseID: request.subjectID, isOnline: model.isOnline && !loader.isFromCache)
                }
                if request.status == .pending { decision }
                if let message { Text(message).foregroundStyle(Brand.amber).accessibilityIdentifier("approval.message") }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else if loader.value != nil {
                EmptyState(title: ApprovalText.notFoundTitle, message: ApprovalText.notFoundMessage, systemImage: "questionmark")
            } else {
                ProgressView()
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle("Approval")
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
        .confirmationDialog(ApprovalText.confirmReject, isPresented: $confirmReject, titleVisibility: .visible) {
            Button("Reject", role: .destructive) { Task { await decide(approve: false) } }
        }
    }

    @ViewBuilder private var decision: some View {
        let block = model.mutationBlock(permitted: model.features.decideApprovals, showingCachedData: loader.isFromCache)
        Section {
            if let block {
                BlockedNote(block: block)
            } else {
                TextField(ApprovalText.noteLabel, text: $note, axis: .vertical)
                    .lineLimit(2...5)
                HStack {
                    Button("Approve") { Task { await decide(approve: true) } }
                        .buttonStyle(.borderedProminent).tint(Palette.live)
                    Spacer()
                    Button("Reject", role: .destructive) { confirmReject = true }
                        .buttonStyle(.bordered)
                        .disabled(!ApprovalText.canDecide(approve: false, note: note))
                }
                .disabled(working)
                if let decisionError {
                    VStack(alignment: .leading, spacing: 2) {
                        if decisionError.segregation { Text(ApprovalText.sodTitle).font(.subheadline.bold()) }
                        Text(decisionError.message).font(.footnote)
                    }
                    .foregroundStyle(Palette.offline)
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("approval.error")
                }
            }
        } header: {
            Text("Decision")
        } footer: {
            Text(ApprovalText.sodFooter)
        }
    }

    private func decide(approve: Bool) async {
        guard let repository = model.repository, ApprovalText.canDecide(approve: approve, note: note) else { return }
        working = true
        defer { working = false }
        do {
            let request = try OwnerAPI.decideApproval(approvalID, approve: approve, note: note, idempotencyKey: UUID())
            decided = try await repository.send(request)
            decisionError = nil
            note = ""
            message = approve ? "Approved." : "Rejected."
            UIAccessibility.post(notification: .announcement, argument: message)
        } catch {
            decisionError = (DecisionErrorText.message(for: error), (error as? APIError)?.code == "SEGREGATION_OF_DUTIES")
            model.handle(error)
            if DecisionErrorText.needsReload(error) {
                decided = nil
                await reload()
            }
        }
    }

    private func reload() async {
        await loader.load(model, .recentApprovals, OwnerAPI.approvals(status: nil, pageSize: 200))
    }
}

/// The expense behind an approval: fetched on demand (online only, never cached), with receipt photos.
struct ExpenseSection: View {
    let model: OwnerModel
    let expenseID: UUID
    let isOnline: Bool
    @State private var expense: ExpenseDTO?
    @State private var error: String?
    @State private var receipt: Receipt?

    private struct Receipt: Identifiable { let id: UUID }

    var body: some View {
        Section("Expense") {
            if let expense {
                LabeledContent("Description", value: expense.description)
                if let supplier = expense.supplier { LabeledContent("Supplier", value: supplier) }
                LabeledContent("Paid from", value: OwnerFormat.humanize(expense.paidFrom))
                LabeledContent("Incurred", value: expense.incurredAt.shortStamp)
                ForEach(expense.receiptAttachmentIDs, id: \.self) { id in
                    PhotoButton(label: "receipt", isOnline: isOnline) { receipt = Receipt(id: id) }
                }
            } else {
                Button(isOnline ? "Expense details" : "Expense details (online only)") { Task { await load() } }
                    .disabled(!isOnline)
            }
            if let error { Text(error).font(.footnote).foregroundStyle(Palette.offline) }
        }
        .sheet(item: $receipt) { receipt in
            EvidencePhotoView(model: model, title: "Receipt",
                              request: OwnerAPI.receiptURL(expenseID: expenseID, attachmentID: receipt.id))
        }
    }

    private func load() async {
        guard let repository = model.repository else { return }
        do {
            expense = try await repository.send(OwnerAPI.expense(expenseID))
            error = nil
        } catch {
            self.error = DecisionErrorText.message(for: error)
            model.handle(error)
        }
    }
}
#endif
