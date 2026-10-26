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
    @State private var resets = Loader<[MeterResetDTO]>()
    @State private var pendingJobs = Loader<Page<JobDTO>>()
    @State private var handovers = Loader<Page<CashHandoverDTO>>()
    @State private var supervisorNames: [UUID: String] = [:]
    @State private var openExceptions = Loader<Page<MeterExceptionDTO>>()
    @State private var jobNumbers: [UUID: String] = [:]

    var body: some View {
        List {
            if model.features.approvals {
                FilterChips(options: ApprovalText.filters, selection: $status)
                    .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                approvalRequests
            }
            ForEach(model.features.decisionKinds.filter { $0 != .nonRevenue }, id: \.self) { kind in
                DecisionKindSection(model: model, kind: kind)
            }
            // DEC-031: "Revenue differences" then "Non-revenue hours".
            if model.features.revenueRead { RevenueDifferencesSection(model: model) }
            if model.features.decisionKinds.contains(.nonRevenue) { DecisionKindSection(model: model, kind: .nonRevenue) }
            otherSections
        }
        .staleBanner(loader, model: model)
        .navigationTitle("Approvals")
        .refreshable { await reload() }
        .task(id: ReloadKey(tick: model.changeTick, filter: status.rawValue)) { await reload() }
    }

    @ViewBuilder private var approvalRequests: some View {
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

    @ViewBuilder private var otherSections: some View {
            if model.features.jobs {
                Section(JobApprovalText.sectionTitle) {
                    let items = pendingJobs.value?.items ?? []
                    if items.isEmpty {
                        Text(pendingJobs.value == nil ? (pendingJobs.error ?? "Loading…") : JobApprovalText.empty)
                            .foregroundStyle(.secondary)
                    }
                    ForEach(items) { job in
                        NavigationLink(value: OwnerRoute.job(job.id)) { PendingJobRow(job: job) }
                    }
                }
            }
            if model.features.finance {
                PendingHandoversSection(loader: handovers, names: supervisorNames)
            }
            if model.features.meterEvidence {
                Section(ExceptionReviewText.sectionTitle) {
                    let items = openExceptions.value?.items ?? []
                    if items.isEmpty {
                        Text(openExceptions.value == nil ? (openExceptions.error ?? "Loading…") : ExceptionReviewText.empty)
                            .foregroundStyle(.secondary)
                    }
                    ForEach(items) { exception in
                        NavigationLink(value: OwnerRoute.exception(exception.id)) {
                            PendingExceptionRow(exception: exception, jobNumber: exception.jobID.flatMap { jobNumbers[$0] })
                        }
                    }
                }
            }
            if model.features.meterEvidence {
                Section(MeterResetText.sectionTitle) {
                    let items = resets.value ?? []
                    if items.isEmpty {
                        Text(resets.value == nil ? (resets.error ?? "Loading…") : MeterResetText.empty).foregroundStyle(.secondary)
                    }
                    ForEach(items) { reset in
                        NavigationLink(value: OwnerRoute.meterReset(reset.id)) { MeterResetRow(reset: reset) }
                    }
                }
            }
    }

    private func reload() async {
        async let a: Void = loadApprovals()
        async let b: Void = loadResets()
        async let c: Void = loadPendingJobs()
        async let d: Void = loadHandovers()
        async let e: Void = loadExceptions()
        _ = await (a, b, c, d, e)
    }

    private func loadApprovals() async {
        guard model.features.approvals else { return }
        await loader.load(model, .approvals(status), OwnerAPI.approvals(status: status, pageSize: 100))
    }

    private func loadHandovers() async {
        guard model.features.finance else { return }
        await handovers.loadClaimed(model)
        supervisorNames = await OwnerLookups.supervisorNames(model)
    }

    private func loadExceptions() async {
        guard model.features.meterEvidence else { return }
        await openExceptions.load(model, .exceptions(openOnly: true, jobID: nil),
                                  OwnerAPI.exceptions(status: ExceptionReviewText.openStatus, pageSize: 100))
        jobNumbers = await OwnerLookups.jobNumbers(model, ids: openExceptions.value?.items.map(\.jobID) ?? [])
    }

    private func loadPendingJobs() async {
        guard model.features.jobs else { return }
        await pendingJobs.load(model, .jobs(.pendingApproval), OwnerAPI.jobs(status: .pendingApproval, pageSize: 100))
    }

    private func loadResets() async {
        guard model.features.meterEvidence else { return }
        await resets.load(model, .meterResets(pendingOnly: true), OwnerAPI.meterResets(status: MeterResetText.pendingStatus))
    }
}

struct MeterResetRow: View {
    let reset: MeterResetDTO

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(MeterResetText.title).font(.headline)
            Text(MeterResetText.detail(reset)).font(.subheadline).foregroundStyle(.secondary)
            Text(reset.reason).font(.caption).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
    }
}

/// One meter reset request: found in the pending list, else in the full list. Approve or reject with a required note
/// when permitted; the server refuses a decision by the person who requested the reset.
struct MeterResetDetailView: View {
    let model: OwnerModel
    let resetID: UUID
    @State private var pending = Loader<[MeterResetDTO]>()
    @State private var all = Loader<[MeterResetDTO]>()
    @State private var decided: MeterResetDTO?
    @State private var note = ""
    @State private var working = false
    @State private var decisionError: String?
    @State private var message: String?
    @State private var showPhoto = false

    private var reset: MeterResetDTO? {
        decided ?? pending.value?.first { $0.id == resetID } ?? all.value?.first { $0.id == resetID }
    }

    /// The list the shown record came from (its cache state gates the decision).
    private var showingCachedData: Bool {
        pending.value?.contains { $0.id == resetID } == true ? pending.isFromCache : all.isFromCache
    }

    var body: some View {
        Form {
            if let reset {
                Section(MeterResetText.title) {
                    LabeledContent("Old reading", value: reset.oldReading.description)
                    LabeledContent("New reading", value: reset.newReading.description)
                    LabeledContent("Effective at", value: reset.effectiveAt.shortStamp)
                    LabeledContent("Reason", value: reset.reason)
                    LabeledContent("Status") {
                        Pill(text: OwnerFormat.humanize(reset.status), color: MeterResetText.statusTone(reset.status).color)
                    }
                    if let at = reset.decidedAt { LabeledContent("Decided", value: at.shortStamp) }
                    if reset.evidenceAttachmentID != nil {
                        PhotoButton(label: "evidence photo", isOnline: model.isOnline) { showPhoto = true }
                    }
                }
                if reset.status == MeterResetText.pendingStatus && model.features.meterApprove { decision }
                if let message { Text(message).foregroundStyle(Brand.amber).accessibilityIdentifier("reset.message") }
            } else if let error = pending.error ?? all.error {
                LoadFailure(message: error) { await reload() }
            } else if pending.value != nil && all.value != nil {
                EmptyState(title: MeterResetText.notFound, systemImage: "questionmark")
            } else {
                ProgressView()
            }
        }
        .staleBanner(pending.value?.contains { $0.id == resetID } == true ? pending : all, model: model)
        .navigationTitle(MeterResetText.title)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
        .sheet(isPresented: $showPhoto) {
            if let id = reset?.evidenceAttachmentID {
                EvidencePhotoView(model: model, title: MeterResetText.title, request: OwnerAPI.attachmentURL(id))
            }
        }
    }

    @ViewBuilder private var decision: some View {
        let block = model.mutationBlock(permitted: model.features.meterApprove, showingCachedData: showingCachedData)
        Section("Decision") {
            if let block {
                BlockedNote(block: block)
            } else {
                TextField(MeterResetText.noteLabel, text: $note, axis: .vertical)
                    .lineLimit(2...5)
                HStack {
                    Button(MeterResetText.approve) { Task { await decide(approve: true) } }
                        .buttonStyle(.borderedProminent).tint(Palette.live)
                    Spacer()
                    Button(MeterResetText.reject, role: .destructive) { Task { await decide(approve: false) } }
                        .buttonStyle(.bordered)
                }
                .disabled(working || !MeterResetText.canDecide(note: note))
                if let decisionError {
                    Text(decisionError).font(.footnote).foregroundStyle(Palette.offline)
                        .accessibilityIdentifier("reset.error")
                }
            }
        }
    }

    private func decide(approve: Bool) async {
        guard let repository = model.repository, MeterResetText.canDecide(note: note) else { return }
        working = true
        defer { working = false }
        do {
            let request = try OwnerAPI.decideMeterReset(resetID, approve: approve, note: note, idempotencyKey: UUID())
            decided = try await repository.send(request)
            decisionError = nil
            note = ""
            message = MeterResetText.done(approve: approve)
            UIAccessibility.post(notification: .announcement, argument: message)
            await reload()
        } catch {
            decisionError = DecisionErrorText.resetMessage(for: error)
            model.handle(error)
            if DecisionErrorText.needsReload(error) {
                decided = nil
                await reload()
            }
        }
    }

    private func reload() async {
        await pending.load(model, .meterResets(pendingOnly: true), OwnerAPI.meterResets(status: MeterResetText.pendingStatus))
        if pending.value?.contains(where: { $0.id == resetID }) != true {
            await all.load(model, .meterResets(pendingOnly: false), OwnerAPI.meterResets())
        }
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
