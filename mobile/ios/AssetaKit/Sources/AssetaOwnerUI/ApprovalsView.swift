#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import SwiftUI

/// Approval requests; approve/reject with a note when permitted. The server enforces segregation
/// of duties (the submitter can't approve) and the app explains that refusal plainly.
struct ApprovalsView: View {
    let model: OwnerModel
    @State private var status: ApprovalStatus? = .pending
    @State private var loader = Loader<Page<ApprovalRequestDTO>>()

    var body: some View {
        List {
            Picker("Status", selection: $status) {
                Text("Pending").tag(ApprovalStatus?.some(.pending))
                Text("Approved").tag(ApprovalStatus?.some(.approved))
                Text("Rejected").tag(ApprovalStatus?.some(.rejected))
            }
            .pickerStyle(.segmented)
            .listRowBackground(Color.clear)
            if let page = loader.value {
                if page.items.isEmpty {
                    ContentUnavailableView("Nothing here", systemImage: "checkmark.seal",
                                           description: Text("No requests with this status."))
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
        .task(id: ReloadKey(tick: model.changeTick, filter: status?.rawValue)) { await reload() }
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
                Pill(text: request.status.humanized, color: color)
            }
            Text("\(request.subjectType.capitalized) · \(request.reason)").font(.subheadline).foregroundStyle(.secondary)
            Text("Requested \(request.requestedAt.shortStamp)").font(.caption).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
    }

    private var color: Color {
        switch request.status {
        case .approved: .green
        case .rejected: .red
        default: .orange
        }
    }
}

/// One request (found in the latest list; there is no single-request endpoint).
struct ApprovalDetailView: View {
    let model: OwnerModel
    let approvalID: UUID
    @State private var loader = Loader<Page<ApprovalRequestDTO>>()
    @State private var decided: ApprovalRequestDTO?
    @State private var note = ""
    @State private var working = false
    @State private var decisionError: String?
    @State private var confirmReject = false

    private var request: ApprovalRequestDTO? { decided ?? loader.value?.items.first { $0.id == approvalID } }

    var body: some View {
        Form {
            if let request {
                Section("Request") {
                    LabeledContent("Amount", value: OwnerFormat.money(request.amount, currency: request.currency))
                    LabeledContent("Type", value: request.subjectType.capitalized)
                    LabeledContent("Reason", value: request.reason)
                    LabeledContent("Requested", value: request.requestedAt.shortStamp)
                    LabeledContent("Status", value: request.status.humanized)
                    if let at = request.decidedAt { LabeledContent("Decided", value: at.shortStamp) }
                    if let decisionNote = request.decisionNote { LabeledContent("Decision note", value: decisionNote) }
                    LabeledContent("Policy", value: request.policyVersion)
                }
                if request.status == .pending { decision }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else if loader.value != nil {
                ContentUnavailableView("Request not found", systemImage: "questionmark",
                                       description: Text("It may be older than the latest 200 requests."))
            } else {
                ProgressView()
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle("Approval")
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
        .confirmationDialog("Reject this request?", isPresented: $confirmReject, titleVisibility: .visible) {
            Button("Reject", role: .destructive) { Task { await decide(approve: false) } }
        }
    }

    @ViewBuilder private var decision: some View {
        let block = model.mutationBlock(permitted: model.features.decideApprovals, showingCachedData: loader.isFromCache)
        Section {
            if let block {
                BlockedNote(block: block)
            } else {
                TextField("Note (optional for approval, recommended for rejection)", text: $note, axis: .vertical)
                    .lineLimit(2...5)
                HStack {
                    Button("Approve") { Task { await decide(approve: true) } }
                        .buttonStyle(.borderedProminent).tint(.green)
                    Spacer()
                    Button("Reject", role: .destructive) { confirmReject = true }
                        .buttonStyle(.bordered)
                }
                .disabled(working)
                if let decisionError {
                    Label(decisionError, systemImage: "hand.raised")
                        .foregroundStyle(.red).font(.footnote)
                        .accessibilityIdentifier("approval.error")
                }
            }
        } header: {
            Text("Decision")
        } footer: {
            Text("The person who submitted a request can't decide it (segregation of duties).")
        }
    }

    private func decide(approve: Bool) async {
        guard let repository = model.repository else { return }
        working = true
        defer { working = false }
        do {
            let request = try OwnerAPI.decideApproval(approvalID, approve: approve, note: note, idempotencyKey: UUID())
            decided = try await repository.send(request)
            decisionError = nil
            UIAccessibility.post(notification: .announcement, argument: approve ? "Approved" : "Rejected")
        } catch {
            decisionError = DecisionErrorText.message(for: error)
            model.handle(error)
        }
    }

    private func reload() async {
        await loader.load(model, .approvals(nil), OwnerAPI.approvals(status: nil, pageSize: 200))
    }
}
#endif
