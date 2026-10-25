#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

// The boss's decisions from the field: confirm or dispute cash handovers, review meter exceptions, issue cash floats.
// Same wording and rules as the Android Owner app; every action is gated like other owner actions.

/// Names and numbers the handover and exception rows need (the records only carry ids).
@MainActor
enum OwnerLookups {
    /// Supervisor names by staff id, from today's cash summary (best effort, as Android); saved data offline.
    static func supervisorNames(_ model: OwnerModel) async -> [UUID: String] {
        guard let repository = model.repository, model.features.finance else { return [:] }
        let range = CashText.range(.today)
        if let snapshot = try? await repository.load(.cash(.today), OwnerAPI.cashSupervisorSummary(from: range.from, to: range.to)) {
            return HandoverText.names(snapshot.value)
        }
        return repository.cached(.cash(.today), as: [CashSupervisorSummaryDTO].self).map { HandoverText.names($0.value) } ?? [:]
    }

    /// "EX-07 · CAT 320" by machine id, from the fleet map (best effort; saved data offline).
    static func machineNames(_ model: OwnerModel) async -> [UUID: String] {
        guard let repository = model.repository, model.features.fleet else { return [:] }
        let machines = (try? await repository.load(.fleetMap, OwnerAPI.fleetMap()))?.value
            ?? repository.cached(.fleetMap, as: [MachineMapDTO].self)?.value ?? []
        return Dictionary(machines.map { ($0.machineID, "\($0.assetCode) · \($0.name)") }, uniquingKeysWith: { a, _ in a })
    }

    /// Job numbers by job id (job summaries, saved for offline like the job screen).
    static func jobNumbers(_ model: OwnerModel, ids: [UUID?]) async -> [UUID: String] {
        guard let repository = model.repository, model.features.jobs else { return [:] }
        var numbers: [UUID: String] = [:]
        var seen = Set<UUID>()
        let distinct = ids.compactMap { $0 }.filter { seen.insert($0).inserted }
        for id in distinct.prefix(ExceptionReviewText.maxJobLookups) {
            if let snapshot = try? await repository.load(.job(id), OwnerAPI.jobSummary(id)) {
                numbers[id] = snapshot.value.job.jobNumber
            } else if let saved = repository.cached(.job(id), as: JobSummaryDTO.self) {
                numbers[id] = saved.value.job.jobNumber
            }
        }
        return numbers
    }
}

// MARK: - Cash handovers

/// "<supervisor> handed over TZS 150,000.00" · "Claimed <date time>" · note.
struct PendingHandoverRow: View {
    let handover: CashHandoverDTO
    let supervisor: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(HandoverText.title(handover, supervisor: supervisor)).font(.headline)
            Text(HandoverText.claimed(handover)).font(.subheadline).foregroundStyle(.secondary)
            if let note = handover.note, !note.isEmpty {
                Text(note).font(.caption).foregroundStyle(.secondary).lineLimit(3)
            }
        }
        .accessibilityElement(children: .combine)
    }
}

/// "Cash handovers" list section (Approvals and Cash screens): CLAIMED handovers, each opening its detail.
struct PendingHandoversSection: View {
    let loader: Loader<Page<CashHandoverDTO>>
    let names: [UUID: String]

    var body: some View {
        Section(HandoverText.sectionTitle) {
            let items = loader.value?.items ?? []
            if items.isEmpty {
                Text(loader.value == nil ? (loader.error ?? "Loading…") : HandoverText.empty).foregroundStyle(.secondary)
            }
            ForEach(items) { handover in
                NavigationLink(value: OwnerRoute.handover(handover.id)) {
                    PendingHandoverRow(handover: handover, supervisor: names[handover.staffMemberID])
                }
            }
        }
    }
}

extension Loader where Value == Page<CashHandoverDTO> {
    func loadClaimed(_ model: OwnerModel) async {
        guard model.features.finance else { return }
        await load(model, .cashHandovers(claimedOnly: true),
                   OwnerAPI.cashHandovers(status: HandoverText.claimedStatus, pageSize: 100))
    }
}

/// One handover, read by id (exact-record links): Confirm received or Dispute when permitted.
struct HandoverDetailView: View {
    let model: OwnerModel
    let handoverID: UUID
    @State private var record = Loader<CashHandoverDTO>()
    @State private var decided: CashHandoverDTO?
    @State private var names: [UUID: String] = [:]
    @State private var sheet: Mode?
    @State private var message: String?

    enum Mode: String, Identifiable { case confirm, dispute; var id: String { rawValue } }

    private var handover: CashHandoverDTO? { decided ?? record.value }

    var body: some View {
        Form {
            if let handover {
                Section(HandoverText.card) {
                    Text(HandoverText.title(handover, supervisor: names[handover.staffMemberID])).font(.headline)
                    Text(HandoverText.claimed(handover)).foregroundStyle(.secondary)
                    if let reference = handover.reference { LabeledContent("Reference", value: reference) }
                    if let note = handover.note, !note.isEmpty { LabeledContent(HandoverText.note, value: note) }
                    LabeledContent("Status") {
                        Pill(text: OwnerFormat.humanize(handover.status), color: HandoverText.statusTone(handover.status).color)
                    }
                    if let note = handover.decisionNote { LabeledContent("Decision note", value: note) }
                    if let name = handover.recordedByName { LabeledContent(OwnerAccountabilityTexts.fieldRecordedBy, value: name) }
                    if let name = handover.verifiedByName { LabeledContent(OwnerAccountabilityTexts.fieldDecidedBy, value: name) }
                    if let expected = handover.expectedBalance {
                        LabeledContent(OwnerAccountabilityTexts.remitExpected,
                                       value: OwnerFormat.money(expected, currency: handover.currency))
                    }
                    if let shortfall = handover.partialShortfall {
                        LabeledContent(OwnerAccountabilityTexts.remitShortfall,
                                       value: OwnerFormat.money(shortfall, currency: handover.currency))
                            .foregroundStyle(Palette.warning)
                    }
                    if let received = handover.amountReceived {
                        LabeledContent(OwnerAccountabilityTexts.remitReceivedLabel,
                                       value: OwnerFormat.money(received, currency: handover.currency))
                    }
                }
                if handover.status == HandoverText.claimedStatus { decision(handover) }
                if let message { Text(message).foregroundStyle(Brand.amber).accessibilityIdentifier("handover.message") }
            } else if let error = record.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView()
            }
        }
        .staleBanner(record, model: model)
        .navigationTitle(HandoverText.screenTitle)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
        .sheet(item: $sheet) { mode in
            if let handover {
                HandoverDecisionSheet(model: model, handover: handover, supervisor: names[handover.staffMemberID],
                                      confirm: mode == .confirm) { updated, text in
                    decided = updated
                    message = text
                    UIAccessibility.post(notification: .announcement, argument: text)
                    if updated == nil { await reload() }
                }
            }
        }
    }

    @ViewBuilder private func decision(_ handover: CashHandoverDTO) -> some View {
        Section(JobApprovalText.decisionTitle) {
            if let block = model.mutationBlock(permitted: model.features.verifyHandovers,
                                               showingCachedData: record.isFromCache) {
                BlockedNote(block: block)
            } else {
                HStack {
                    Button(HandoverText.confirm) { sheet = .confirm }
                        .buttonStyle(.borderedProminent).tint(Palette.live)
                        .accessibilityIdentifier("handover.confirm")
                    Spacer()
                    Button(HandoverText.dispute, role: .destructive) { sheet = .dispute }
                        .buttonStyle(.bordered)
                        .accessibilityIdentifier("handover.dispute")
                }
            }
        }
    }

    private func reload() async {
        await record.load(model, .handover(handoverID), OwnerAPI.cashHandover(handoverID))
        if record.error == nil && !record.isFromCache { decided = nil }
        if record.value?.staffMemberName == nil { names = await OwnerLookups.supervisorNames(model) }
    }
}

/// "Confirm this handover?" with an optional note, or "Dispute this handover?" with a required reason.
struct HandoverDecisionSheet: View {
    let model: OwnerModel
    let handover: CashHandoverDTO
    let supervisor: String?
    let confirm: Bool
    /// The decided handover (nil when it must be reloaded) and the message to show.
    let done: (CashHandoverDTO?, String) async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var text = ""
    @State private var received: String?
    @State private var working = false
    @State private var error: String?
    @State private var idempotencyKey = UUID()

    private var receivedText: String { received ?? HandoverText.prefill(handover) }
    private var canSubmit: Bool {
        confirm ? HandoverText.canConfirm(amountReceived: receivedText, text: text) : HandoverText.canDecide(confirm: false, text: text)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text(HandoverText.title(handover, supervisor: supervisor))
                    Text(HandoverText.claimed(handover)).foregroundStyle(.secondary)
                }
                if confirm {
                    Section {
                        TextField(OwnerAccountabilityTexts.remitAmountReceived,
                                  text: Binding(get: { receivedText }, set: { received = $0 }))
                            .keyboardType(.decimalPad).font(.title3.monospacedDigit())
                            .accessibilityIdentifier("handover.confirm.received")
                        if HandoverText.parseReceived(receivedText) == nil {
                            Text(OwnerAccountabilityTexts.remitErrAmount).font(.footnote).foregroundStyle(Palette.offline)
                        }
                    } header: { Text(OwnerAccountabilityTexts.remitAmountReceived) } footer: {
                        Text(OwnerAccountabilityTexts.remitAmountReceivedFooter)
                    }
                }
                Section {
                    TextField(confirm ? HandoverText.note : HandoverText.reason, text: $text, axis: .vertical)
                        .lineLimit(2...5)
                        .accessibilityIdentifier(confirm ? "handover.confirm.note" : "handover.dispute.reason")
                }
                if let error {
                    Text(error).font(.footnote).foregroundStyle(Palette.offline).accessibilityIdentifier("handover.error")
                }
            }
            .navigationTitle(confirm ? HandoverText.confirmTitle : HandoverText.disputeTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(confirm ? HandoverText.confirm : HandoverText.dispute) { Task { await submit() } }
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
            let updated = try await repository.send(
                OwnerAPI.decideHandover(handover.id, confirm: confirm, note: text,
                                        amountReceived: confirm ? HandoverText.parseReceived(receivedText) : nil,
                                        idempotencyKey: idempotencyKey))
            dismiss()
            await done(updated, HandoverText.done(confirm: confirm))
        } catch {
            self.error = HandoverText.message(for: error)
            idempotencyKey = UUID() // a corrected retry is a new request
            model.handle(error)
            if HandoverText.needsReload(error) {
                dismiss()
                await done(nil, HandoverText.alreadyDecided)
            }
        }
    }
}

// MARK: - Cash floats

/// "Issue a cash float" to one supervisor in the currency of their cash card.
struct IssueFloatSheet: View {
    let model: OwnerModel
    let staffMemberID: UUID
    let supervisor: String
    let currency: String?
    let done: (String) async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var amount = ""
    @State private var note = ""
    @State private var working = false
    @State private var error: String?
    @State private var idempotencyKey = UUID()

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text(supervisor).font(.headline)
                    TextField(FloatText.amountLabel(currency: currency), text: $amount)
                        .keyboardType(.decimalPad)
                        .accessibilityIdentifier("float.amount")
                    TextField(FloatText.note, text: $note, axis: .vertical)
                        .lineLimit(2...5)
                        .accessibilityIdentifier("float.note")
                }
                if let error {
                    Text(error).font(.footnote).foregroundStyle(Palette.offline).accessibilityIdentifier("float.error")
                }
            }
            .navigationTitle(FloatText.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(FloatText.submit) { Task { await submit() } }
                        .disabled(working || !FloatText.canIssue(amount: amount, note: note))
                }
            }
        }
    }

    private func submit() async {
        guard let repository = model.repository, let value = FloatText.parseAmount(amount),
              FloatText.canIssue(amount: amount, note: note) else { return }
        working = true
        defer { working = false }
        do {
            _ = try await repository.send(OwnerAPI.issueFloat(staffMemberID: staffMemberID, amount: value, currency: currency,
                                                              note: note, idempotencyKey: idempotencyKey))
            dismiss()
            await done(FloatText.issued)
        } catch {
            self.error = FloatText.message(for: error)
            // Same key on a plain retry after a lost response (the server replays); a new one once the input changes.
            if case .transport? = error as? APIError {} else { idempotencyKey = UUID() }
            model.handle(error)
        }
    }
}

// MARK: - Exceptions

/// "<type label> on <job number>" · severity and time.
struct PendingExceptionRow: View {
    let exception: MeterExceptionDTO
    let jobNumber: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(ExceptionReviewText.title(exception, jobNumber: jobNumber)).font(.headline)
                Spacer()
                if exception.blocking { Pill(text: "Blocking", color: Palette.offline) }
            }
            Text("\(OwnerFormat.humanize(exception.severity)) · \(exception.createdAt.shortStamp)")
                .font(.subheadline).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
    }
}

/// One meter exception (found among the open ones, else the latest 200), with Review when it is open and permitted.
struct ExceptionDetailView: View {
    let model: OwnerModel
    let exceptionID: UUID
    @State private var open = Loader<Page<MeterExceptionDTO>>()
    @State private var all = Loader<Page<MeterExceptionDTO>>()
    @State private var reviewed: MeterExceptionDTO?
    @State private var reviewing = false
    @State private var message: String?

    private var inOpen: Bool { open.value?.items.contains { $0.id == exceptionID } == true }

    private var exception: MeterExceptionDTO? {
        reviewed ?? open.value?.items.first { $0.id == exceptionID } ?? all.value?.items.first { $0.id == exceptionID }
    }

    var body: some View {
        Form {
            if let exception {
                Section(ExceptionReviewText.typeLabel(exception.exceptionType)) {
                    LabeledContent("Status") {
                        Pill(text: OwnerFormat.humanize(exception.status), color: tone(exception).color)
                    }
                    LabeledContent("Severity", value: OwnerFormat.humanize(exception.severity))
                    if exception.blocking { LabeledContent("Blocking", value: ExceptionReviewText.blocksBilling) }
                    LabeledContent("Recorded", value: exception.createdAt.shortStamp)
                    if let at = exception.reviewedAt { LabeledContent("Reviewed", value: at.shortStamp) }
                    if let note = exception.reviewNote, !note.isEmpty {
                        LabeledContent(ExceptionReviewText.noteLabel, value: note)
                    }
                    if let jobID = exception.jobID, model.features.jobs {
                        NavigationLink(value: OwnerRoute.job(jobID)) { Text(ExceptionReviewText.openJob) }
                    }
                }
                if case let .object(fields)? = exception.evidence, !fields.isEmpty {
                    Section("Evidence") {
                        ForEach(fields.keys.sorted(), id: \.self) { key in
                            LabeledContent(OwnerFormat.humanize(key), value: AlertText.evidence(fields[key] ?? .null))
                        }
                    }
                }
                if exception.status == ExceptionReviewText.openStatus { decision }
                if let message { Text(message).foregroundStyle(Brand.amber).accessibilityIdentifier("exception.message") }
            } else if let error = open.error ?? all.error {
                LoadFailure(message: error) { await reload() }
            } else if open.value != nil && (inOpen || all.value != nil) {
                EmptyState(title: ExceptionReviewText.notFound, systemImage: "questionmark")
            } else {
                ProgressView()
            }
        }
        .staleBanner(inOpen ? open : all, model: model)
        .navigationTitle(ExceptionReviewText.screenTitle)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
        .sheet(isPresented: $reviewing) {
            if let exception {
                ExceptionReviewSheet(model: model, exception: exception) { updated, text in
                    reviewed = updated
                    message = text
                    UIAccessibility.post(notification: .announcement, argument: text)
                    if updated == nil { await reload() }
                }
            }
        }
    }

    private func tone(_ x: MeterExceptionDTO) -> KPITone {
        switch x.status {
        case "OPEN": .warning
        case "EXPLAINED": .good
        case "CONFIRMED": .critical
        default: .muted
        }
    }

    @ViewBuilder private var decision: some View {
        Section(JobApprovalText.decisionTitle) {
            if let block = model.mutationBlock(permitted: model.features.reviewExceptions,
                                               showingCachedData: inOpen ? open.isFromCache : all.isFromCache) {
                BlockedNote(block: block)
            } else {
                Button(ExceptionReviewText.review) { reviewing = true }
                    .buttonStyle(.borderedProminent)
                    .accessibilityIdentifier("exception.review")
            }
        }
    }

    private func reload() async {
        await open.load(model, .exceptions(openOnly: true, jobID: nil),
                        OwnerAPI.exceptions(status: ExceptionReviewText.openStatus, pageSize: 100))
        if !inOpen && reviewed == nil {
            await all.load(model, .exceptions(openOnly: false, jobID: nil), OwnerAPI.exceptions(pageSize: 200))
        }
    }
}

/// The review form, as the web `ReviewExceptionDialog`: Outcome (required) and Review note (5 to 2000 characters).
struct ExceptionReviewSheet: View {
    let model: OwnerModel
    let exception: MeterExceptionDTO
    /// The reviewed exception (nil when it must be reloaded) and the message to show.
    let done: (MeterExceptionDTO?, String) async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var outcome: ExceptionReviewOutcome?
    @State private var note = ""
    @State private var touched = false
    @State private var working = false
    @State private var error: String?
    @State private var idempotencyKey = UUID()

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text(ExceptionReviewText.intro).font(.subheadline).foregroundStyle(.secondary)
                }
                Section {
                    Picker(ExceptionReviewText.outcomeLabel, selection: $outcome) {
                        Text(ExceptionReviewText.chooseOutcome).tag(ExceptionReviewOutcome?.none)
                        ForEach(ExceptionReviewOutcome.allCases) { Text($0.label).tag(Optional($0)) }
                    }
                    .pickerStyle(.inline)
                    .accessibilityIdentifier("exception.review.outcome")
                } header: {
                    Text(ExceptionReviewText.outcomeLabel)
                }
                Section {
                    TextField(ExceptionReviewText.noteLabel, text: $note, axis: .vertical)
                        .lineLimit(3...8)
                        .onChange(of: note) { touched = true }
                        .accessibilityIdentifier("exception.review.note")
                } header: {
                    Text(ExceptionReviewText.noteLabel)
                } footer: {
                    if touched, let problem = ExceptionReviewText.noteError(note) { Text(problem).foregroundStyle(Palette.offline) }
                }
                if let error {
                    Text(error).font(.footnote).foregroundStyle(Palette.offline).accessibilityIdentifier("exception.review.error")
                }
            }
            .navigationTitle(ExceptionReviewText.reviewTitle(exception))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(ExceptionReviewText.submit) { Task { await submit() } }
                        .disabled(working || !ExceptionReviewText.canReview(outcome: outcome, note: note))
                }
            }
        }
    }

    private func submit() async {
        guard let repository = model.repository, let outcome,
              ExceptionReviewText.canReview(outcome: outcome, note: note) else { return }
        working = true
        defer { working = false }
        do {
            let updated = try await repository.send(
                OwnerAPI.reviewException(exception.id, outcome: outcome, note: note, idempotencyKey: idempotencyKey))
            dismiss()
            await done(updated, ExceptionReviewText.reviewed)
        } catch {
            self.error = ExceptionReviewText.message(for: error)
            idempotencyKey = UUID()
            model.handle(error)
            if ExceptionReviewText.needsReload(error) {
                dismiss()
                await done(nil, ExceptionReviewText.alreadyReviewed)
            }
        }
    }
}
#endif
