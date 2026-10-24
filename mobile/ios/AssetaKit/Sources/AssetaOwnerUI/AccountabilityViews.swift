#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

private typealias T = OwnerAccountabilityTexts

/// One kind of accountability decision waiting under Approvals ("Customer discounts", "Meter baselines", ...).
struct DecisionKindSection: View {
    let model: OwnerModel
    let kind: DecisionKind
    @State private var loader = Loader<Page<JSONValue>>()

    /// Shown only when something waits (a capability the company does not use never adds an empty section).
    var body: some View {
        let items = loader.value.map { PendingDecision.list($0, kind: kind).filter(\.isPending) } ?? []
        Group {
            if !items.isEmpty {
                Section(kind.sectionTitle) {
                    ForEach(items) { item in
                        NavigationLink(value: OwnerRoute.decision(kind, item.recordID)) { DecisionRow(item: item) }
                    }
                }
            }
        }
        .task(id: model.changeTick) {
            await loader.load(model, .decisions(kind, pendingOnly: true), OwnerAPI.decisions(kind, pendingOnly: true))
        }
    }
}

struct DecisionRow: View {
    let item: PendingDecision

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(item.headline).font(.headline)
            if let reason = item.reason, !reason.isEmpty {
                Text(reason).font(.subheadline).foregroundStyle(.secondary).lineLimit(2)
            }
            Text(T.approvalsProposed(item.proposedAt.shortStamp) + (item.proposedByName.map { " · \($0)" } ?? ""))
                .font(.caption).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
    }
}

/// One decision of any kind: what was proposed, by whom and why; Approve / Reject with a note when permitted. The
/// proposer can never decide their own request (the server refuses it; Approve is disabled with the reason).
struct DecisionDetailView: View {
    let model: OwnerModel
    let kind: DecisionKind
    let recordID: UUID
    @State private var pending = Loader<Page<JSONValue>>()
    @State private var all = Loader<Page<JSONValue>>()
    @State private var decided: PendingDecision?
    @State private var note = ""
    @State private var working = false
    @State private var decisionError: String?
    @State private var message: String?
    @State private var confirmReject = false
    @State private var showPhoto = false
    @State private var machines: [UUID: String] = [:]

    private func find(_ loader: Loader<Page<JSONValue>>) -> PendingDecision? {
        loader.value.flatMap { PendingDecision.list($0, kind: kind, machines: machines).first { $0.recordID == recordID } }
    }

    private var item: PendingDecision? { decided ?? find(pending) ?? find(all) }
    private var showingCachedData: Bool { find(pending) != nil ? pending.isFromCache : all.isFromCache }

    var body: some View {
        Form {
            if let item {
                Section(T.decisionRequest) {
                    Text(item.headline).font(.headline)
                    ForEach(item.fields, id: \.self) { field in
                        if !field.value.isEmpty { LabeledContent(field.label, value: field.value) }
                    }
                    if let reason = item.reason, !reason.isEmpty { LabeledContent(T.fieldReason, value: reason) }
                    LabeledContent(T.fieldProposed, value: item.proposedAt.shortStamp)
                    LabeledContent(T.fieldStatus, value: OwnerFormat.humanize(item.status))
                    if let photo = item.photoAttachmentID {
                        PhotoButton(label: "evidence photo", isOnline: model.isOnline) { showPhoto = true }
                            .sheet(isPresented: $showPhoto) {
                                EvidencePhotoView(model: model, title: kind.decisionTitle, request: OwnerAPI.attachmentURL(photo))
                            }
                    }
                    if let machine = item.machineID, model.features.fleet {
                        NavigationLink(value: OwnerRoute.machine(machine)) { Label(T.fieldMachine, systemImage: "gauge.with.dots.needle.33percent") }
                    }
                }
                if item.isPending && model.features.canDecide(kind) { decision(item) }
                if let message { Text(message).foregroundStyle(Brand.amber).accessibilityIdentifier("decision.message") }
            } else if let error = pending.error ?? all.error {
                LoadFailure(message: error) { await reload() }
            } else if pending.value != nil && all.value != nil {
                EmptyState(title: T.decisionNotFoundTitle, message: T.decisionNotFoundMessage, systemImage: "questionmark")
            } else {
                ProgressView()
            }
        }
        .staleBanner(find(pending) != nil ? pending : all, model: model)
        .navigationTitle(kind.decisionTitle)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
        .confirmationDialog(T.decisionConfirmReject, isPresented: $confirmReject, titleVisibility: .visible) {
            Button(T.decisionReject, role: .destructive) { Task { await decide(approve: false) } }
        }
    }

    @ViewBuilder private func decision(_ item: PendingDecision) -> some View {
        let block = model.mutationBlock(permitted: model.features.canDecide(kind), showingCachedData: showingCachedData)
        let own = item.isOwn(userID: model.me.userID)
        Section {
            if let block {
                BlockedNote(block: block)
            } else {
                TextField(DecisionRules.noteLabel(kind), text: $note, axis: .vertical).lineLimit(2...5)
                HStack {
                    Button(T.decisionApprove) { Task { await decide(approve: true) } }
                        .buttonStyle(.borderedProminent).tint(Palette.live)
                        .disabled(own || !DecisionRules.canDecide(kind, approve: true, note: note))
                        .accessibilityHint(own ? T.decisionOwnRequest : "")
                    Spacer()
                    Button(T.decisionReject, role: .destructive) { confirmReject = true }
                        .buttonStyle(.bordered)
                        .disabled(own || !DecisionRules.canDecide(kind, approve: false, note: note))
                }
                .disabled(working)
                if own { Text(T.decisionOwnRequest).font(.footnote).foregroundStyle(.secondary) }
                if let decisionError {
                    Text(decisionError).font(.footnote).foregroundStyle(Palette.offline).accessibilityIdentifier("decision.error")
                }
            }
        } header: { Text(T.decisionDecision) } footer: { Text(T.decisionFooter) }
    }

    private func decide(approve: Bool) async {
        guard let repository = model.repository, DecisionRules.canDecide(kind, approve: approve, note: note) else { return }
        working = true
        defer { working = false }
        do {
            let result = try await repository.send(OwnerAPI.decide(kind, id: recordID, approve: approve, note: note,
                                                                   idempotencyKey: UUID()))
            decided = PendingDecision.from(result, kind: kind, machines: machines)
            decisionError = nil
            note = ""
            message = approve ? T.decisionApproved : T.decisionRejected
            UIAccessibility.post(notification: .announcement, argument: message)
            await reload()
        } catch {
            decisionError = DecisionRules.message(for: error)
            model.handle(error)
            if DecisionRules.needsReload(error) {
                decided = nil
                await reload()
            }
        }
    }

    private func reload() async {
        if kind == .hoursTransfer { machines = await OwnerLookups.machineNames(model) }
        await pending.load(model, .decisions(kind, pendingOnly: true), OwnerAPI.decisions(kind, pendingOnly: true))
        if find(pending) == nil {
            await all.load(model, .decisions(kind, pendingOnly: false), OwnerAPI.decisions(kind, pendingOnly: false, pageSize: 200))
        }
    }
}

/// The accountability dashboard summary (More → Accountability): every tile the company shows; tiles lead to the
/// filtered lists the Owner app has.
struct AccountabilityDashboardView: View {
    let model: OwnerModel
    @State private var loader = Loader<AccountabilitySummaryDTO>()

    var body: some View {
        List {
            if let summary = loader.value {
                let tiles = AccountabilityDashboard.tiles(summary)
                if AccountabilityDashboard.showsHiddenNote(summary) {
                    Text(T.dashHiddenNote).font(.footnote).foregroundStyle(.secondary)
                }
                if tiles.isEmpty { EmptyState(title: T.dashEmpty, systemImage: "checkmark.shield") }
                ForEach(tiles) { tile in
                    Section {
                        ForEach(Array(tile.rows.enumerated()), id: \.offset) { _, row in
                            VStack(alignment: .leading, spacing: 2) {
                                if row.value.isEmpty {
                                    Text(row.label)
                                } else {
                                    LabeledContent(row.label) { Text(row.value).multilineTextAlignment(.trailing) }
                                }
                                if let detail = row.detail { Text(detail).font(.caption).foregroundStyle(.secondary) }
                            }
                            .accessibilityElement(children: .combine)
                        }
                        if let route = tile.route, model.features.allows(route) {
                            NavigationLink(value: route) { Text(tile.title).foregroundStyle(Color.accentColor) }
                        }
                    } header: { Text(tile.title) }
                }
                Section { Text(AccountabilityDashboard.footer(summary)).font(.footnote).foregroundStyle(.secondary) }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(T.dashTitle)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private func reload() async { await loader.load(model, .accountability, OwnerAPI.accountabilitySummary()) }
}
#endif
