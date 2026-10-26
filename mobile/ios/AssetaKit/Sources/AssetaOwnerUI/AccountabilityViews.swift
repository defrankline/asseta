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
            Text(item.proposedByName.map { T.approvalsProposedBy(item.proposedAt.shortStamp, $0) }
                ?? T.approvalsProposed(item.proposedAt.shortStamp))
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
    /// The record read by id (`GET .../{id}`), so a decided request shows its status and decision.
    @State private var record = Loader<JSONValue>()
    @State private var decided: PendingDecision?
    @State private var note = ""
    @State private var working = false
    @State private var decisionError: String?
    @State private var message: String?
    @State private var confirmReject = false
    @State private var showPhoto = false

    private var item: PendingDecision? {
        decided ?? record.value.flatMap { PendingDecision.from($0, kind: kind) }
    }
    private var showingCachedData: Bool { record.isFromCache }

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
            } else if let error = record.error {
                LoadFailure(message: error) { await reload() }
            } else if record.value != nil {
                EmptyState(title: T.decisionNotFoundTitle, message: T.decisionNotFoundMessage, systemImage: "questionmark")
            } else {
                ProgressView()
            }
        }
        .staleBanner(record, model: model)
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
            decided = PendingDecision.from(result, kind: kind)
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
        await record.load(model, .decision(kind, id: recordID), OwnerAPI.decision(kind, id: recordID))
        if record.error == nil && !record.isFromCache { decided = nil }
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
                let tiles = AccountabilityDashboard.tiles(summary, disabled: model.features.disabledCapabilities)
                if AccountabilityDashboard.showsHiddenNote(summary) {
                    Text(T.dashHiddenNote).font(.footnote).foregroundStyle(.secondary)
                }
                if tiles.isEmpty { EmptyState(title: T.dashEmpty, systemImage: "checkmark.shield") }
                ForEach(tiles) { tile in
                    Section {
                        ForEach(Array(tile.rows.enumerated()), id: \.offset) { _, row in TileRow(row: row) }
                        if let route = tile.route, model.features.allows(route) {
                            NavigationLink(value: route) { Text(tile.title).foregroundStyle(Color.accentColor) }
                        }
                        ForEach(tile.moreLinks.filter { model.features.allows($0.route) }, id: \.self) { link in
                            NavigationLink(value: link.route) { Text(link.label).foregroundStyle(Color.accentColor) }
                        }
                    } header: { Text(tile.title) } footer: { if let footer = tile.footer { Text(footer) } }
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
/// One label/value line of a dashboard tile.
private struct TileRow: View {
    let row: DashboardTile.Row

    var body: some View {
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
}

// MARK: - Cash records (exact-record links) and overdue remittances

/// Labelled values of a read-only record.
private struct FieldRows: View {
    let fields: [DecisionField]

    var body: some View {
        ForEach(fields, id: \.self) { field in
            LabeledContent(field.label) { Text(field.value).multilineTextAlignment(.trailing) }
        }
    }
}

/// One cash transfer between custodians (read-only).
struct CashTransferRecordView: View {
    let model: OwnerModel
    let transferID: UUID
    @State private var loader = Loader<CashTransferDTO>()

    var body: some View {
        RecordForm(loader: loader, model: model, title: T.recordTransferTitle,
                   fields: { CashRecordPresentation.transfer($0) }) {
            await loader.load(model, .cashTransfer(transferID), OwnerAPI.cashTransfer(transferID))
        }
    }
}

/// One cash float issued to a custodian (read-only).
struct CashFloatRecordView: View {
    let model: OwnerModel
    let floatID: UUID
    @State private var loader = Loader<CashFloatDTO>()

    var body: some View {
        RecordForm(loader: loader, model: model, title: T.recordFloatTitle, fields: { CashRecordPresentation.float($0) }) {
            await loader.load(model, .cashFloat(floatID), OwnerAPI.cashFloat(floatID))
        }
    }
}

/// One overdue-remittance flag (read-only).
struct OverdueRemittanceView: View {
    let model: OwnerModel
    let overdueID: UUID
    @State private var loader = Loader<RemittanceOverdueDTO>()

    var body: some View {
        RecordForm(loader: loader, model: model, title: T.overdueDetailTitle, fields: { CashRecordPresentation.overdue($0) },
                   footer: { CashRecordPresentation.overdueFooter($0) }) {
            await loader.load(model, .overdueRemittance(overdueID), OwnerAPI.remittanceOverdue(overdueID))
        }
    }
}

/// A read-only record screen: its fields, a load failure, or progress.
private struct RecordForm<Value: Codable & Sendable>: View {
    let loader: Loader<Value>
    let model: OwnerModel
    let title: String
    let fields: (Value) -> [DecisionField]
    /// Optional line under the fields (the overdue reason's sentence).
    var footer: ((Value) -> String)? = nil
    let reload: () async -> Void

    var body: some View {
        Form {
            if let value = loader.value {
                Section { FieldRows(fields: fields(value)) } footer: { if let footer { Text(footer(value)) } }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView()
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(title)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }
}

/// Today's overdue remittances: custodians still holding cash after the tenant's cut-off.
struct OverdueRemittancesView: View {
    let model: OwnerModel
    @State private var loader = Loader<Page<RemittanceOverdueDTO>>()

    var body: some View {
        let day = CashRecordPresentation.localDay(Date())
        List {
            if let page = loader.value {
                if page.items.isEmpty { EmptyState(title: T.overdueEmpty, systemImage: "checkmark.circle") }
                ForEach(page.items) { item in
                    let row = CashRecordPresentation.overdueRow(item)
                    NavigationLink(value: OwnerRoute.overdueRemittance(item.id)) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(row.title).font(.headline)
                            Text(row.amounts).font(.subheadline.monospacedDigit())
                            Text(row.line).font(.caption).foregroundStyle(.secondary)
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload(day) }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(T.overdueTitle)
        .refreshable { await reload(day) }
        .task(id: model.changeTick) { await reload(day) }
    }

    private func reload(_ day: String) async {
        await loader.load(model, .overdueRemittances(day: day), OwnerAPI.remittanceOverdue(day: day))
    }
}
#endif
