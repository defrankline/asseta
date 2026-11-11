#if os(iOS)
import AssetaAppShell
import AssetaCapture
import AssetaModel
import AssetaSync
import SwiftUI

private typealias P = PettyCashTexts

// DEC-033 petty cash on the Supervisor app: "My petty cash" and its offline forms (same screens as Android
// `MyPettyCashScreen` and the petty cash forms; strings doc "DEC-033 — petty cash funds").

extension FieldModel {
    /// My petty cash from the last snapshot with this phone's answers (empty while the feature is off for me).
    var pettyCash: PettyCashView {
        guard access.pettyCash, let services else { return PettyCashView() }
        return services.directory.pettyCash()
    }

    /// Colleagues by name for a count witness (online only).
    func searchPeople(_ query: String) async -> [PersonDTO]? {
        guard isOnline, let online = services?.online else { return nil }
        return try? await online.searchPeople(query)
    }
}

/// Forms of the petty cash screen (sheets, as the other field forms).
enum PettyCashSheet: Identifiable {
    case ack(UUID), topUp(UUID), returnFund(UUID), count(UUID), holderChange(UUID), advance(UUID)

    var id: String {
        switch self {
        case let .ack(id): "pc-ack-\(id)"
        case let .topUp(id): "pc-topup-\(id)"
        case let .returnFund(id): "pc-return-\(id)"
        case let .count(id): "pc-count-\(id)"
        case let .holderChange(id): "pc-holder-\(id)"
        case let .advance(id): "pc-advance-\(id)"
        }
    }

    @MainActor @ViewBuilder func view(_ model: FieldModel) -> some View {
        switch self {
        case let .ack(id): PettyCashAckFormView(model: model, movementID: id)
        case let .topUp(id): PettyCashTopUpFormView(model: model, fundID: id)
        case let .returnFund(id): PettyCashReturnFormView(model: model, fundID: id)
        case let .count(id): PettyCashCountFormView(model: model, fundID: id)
        case let .holderChange(id): PettyCashHolderChangeFormView(model: model, changeID: id)
        case let .advance(id): PettyCashAdvanceFormView(model: model, advanceID: id)
        }
    }
}

/// Money tab: the entry to My petty cash (with how many items wait for me).
struct PettyCashMoneySection: View {
    let model: FieldModel

    var body: some View {
        let _ = model.accountabilityTick
        if model.access.pettyCash {
            let waiting = model.pettyCash.waiting.count
            Section {
                NavigationLink(value: FieldRoute.pettyCash) { Label(P.row, systemImage: "banknote") }
                    .accessibilityIdentifier("money.pettyCash")
            } header: { Text(P.section) } footer: {
                if waiting > 0 { Text(P.rowWaiting(waiting)) }
            }
        }
    }
}

/// "To check": an expense's control flags in neutral words.
struct ExpenseFlagsSection: View {
    let flags: [String]

    var body: some View {
        let lines = ExpenseFlags.lines(flags)
        if !lines.isEmpty {
            Section(ExpenseFlags.title) {
                ForEach(lines, id: \.self) { Label($0, systemImage: "exclamationmark.circle").foregroundStyle(Palette.warning) }
            }
        }
    }
}

// MARK: - My petty cash

struct MyPettyCashView: View {
    let model: FieldModel
    /// Set by the root when a notification asks for a form.
    @Binding var sheet: PettyCashSheet?

    var body: some View {
        let _ = model.accountabilityTick
        let view = model.pettyCash
        List {
            if !model.access.pettyCash {
                ContentUnavailableView(P.title, systemImage: "banknote", description: Text(P.unavailable))
            } else if view.funds.isEmpty && view.waiting.isEmpty && view.advances.isEmpty {
                ContentUnavailableView(P.emptyTitle, systemImage: "banknote", description: Text(P.emptyMessage))
            }
            if !view.waiting.isEmpty {
                Section(P.waiting) {
                    ForEach(view.waiting) { item in
                        Button { open(item) } label: { Text(item.title) }
                            .foregroundStyle(.primary)
                            .accessibilityIdentifier("pettyCash.waiting.\(item.id)")
                    }
                }
            }
            ForEach(view.funds) { fund in fundSection(fund) }
            if !view.advances.isEmpty {
                Section(P.advances) {
                    ForEach(view.advances) { row in
                        let a = row.advance
                        let line = P.advanceDetail(amount: P.money(a.remaining, a.currency), date: a.dueAt?.listText ?? "")
                        if row.fromMyFund {
                            Button { sheet = .advance(a.id) } label: {
                                InboxRow(P.advanceRow(number: a.number, amount: P.money(a.amount, a.currency)), nil, row.who, line,
                                         a.overdue == true ? P.advanceOverdue : nil)
                            }
                            .foregroundStyle(.primary)
                        } else {
                            InboxRow(P.advanceRow(number: a.number, amount: P.money(a.amount, a.currency)), nil, row.who, line,
                                     a.overdue == true ? P.advanceOverdue : nil)
                        }
                    }
                }
            }
            if !view.onPhone.isEmpty {
                Section(P.onPhone) {
                    ForEach(view.onPhone) { op in
                        let currency = P.recordFundID(op).flatMap { id in view.funds.first { $0.id == id }?.currency }
                        VStack(alignment: .leading, spacing: 4) {
                            Text(P.recordTitle(op, currency: currency)).font(.headline)
                            Text(op.createdAtDevice.listText).font(.subheadline).foregroundStyle(.secondary)
                            SyncStateLabel(status: op.status)
                            if op.status == .failed || op.status == .conflict {
                                Text(P.refusal(op)).font(.caption).foregroundStyle(Palette.offline)
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle(P.title)
        .refreshable { await model.sync(force: true) }
    }

    @ViewBuilder private func fundSection(_ fund: PettyCashFundDTO) -> some View {
        let b = fund.balance
        Section {
            if let b {
                LabeledContent(P.balance, value: P.money(b.balance, fund.currency)).font(.headline)
                LabeledContent(P.available, value: P.money(b.availableToSpend, fund.currency))
            }
            if let v = b?.pendingSpending, v.value != 0 { LabeledContent(P.pendingSpending, value: P.money(v, fund.currency)) }
            if let v = b?.awaitingAcknowledgement, v.value != 0 { LabeledContent(P.awaitingAck, value: P.money(v, fund.currency)) }
            if let v = b?.returnsClaimed, v.value != 0 { LabeledContent(P.returnsClaimed, value: P.money(v, fund.currency)) }
            if b?.belowLowBalance == true { Text(P.low).foregroundStyle(Palette.warning) }
            if b != nil { LabeledContent(P.lastCount, value: b?.lastCountAt?.listText ?? P.notCounted) }
            if let due = b?.nextCountDueAt { LabeledContent(P.nextCount, value: due.listText) }
            LabeledContent(P.limit, value: P.money(fund.approvedLimit, fund.currency))
            Button(P.actionTopUp, systemImage: "arrow.down.circle") { sheet = .topUp(fund.id) }
            Button(P.actionReturn, systemImage: "arrow.up.forward.circle") { sheet = .returnFund(fund.id) }
            if model.access.pettyCashCount {
                Button(P.actionCount, systemImage: "checklist") { sheet = .count(fund.id) }
            }
        } header: { Text(P.fundHeader(code: fund.code, name: fund.name)) } footer: {
            if let asOf = b?.asOf { Text(P.asOf(asOf.listText)) }
        }
    }

    private func open(_ item: PettyCashWaiting) {
        switch item {
        case let .movement(m): sheet = .ack(m.id)
        case let .holderChange(c): sheet = .holderChange(c.id)
        }
    }
}

// MARK: - Forms

/// Shared chrome of the petty cash forms: title, Cancel, Save (label per form) and the "Not saved" alert.
private struct PettyCashForm<Content: View>: View {
    let title: String
    var saveLabel: String = "Save"
    var canSave: Bool
    var showsSave = true
    let onCancel: () -> Void
    let onSave: () -> Void
    @Binding var error: String?
    @ViewBuilder let content: () -> Content

    var body: some View {
        NavigationStack {
            Form { content() }
                .navigationTitle(title)
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("Cancel", action: onCancel) }
                    if showsSave {
                        ToolbarItem(placement: .confirmationAction) { Button(saveLabel, action: onSave).disabled(!canSave) }
                    }
                }
                .alert("Not saved", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
                    Button("OK") { error = nil }
                } message: { Text(error ?? "") }
        }
    }
}

/// A fund's summary at the top of the top-up and return forms: balance, available to spend and limit (as Android).
private struct FundSummarySection: View {
    let fund: PettyCashFundDTO
    var body: some View {
        Section {
            if let b = fund.balance {
                LabeledContent(P.balance, value: P.money(b.balance, fund.currency))
                LabeledContent(P.available, value: P.money(b.availableToSpend, fund.currency))
            }
            LabeledContent(P.limit, value: P.money(fund.approvedLimit, fund.currency))
        } header: { Text(P.fundHeader(code: fund.code, name: fund.name)) }
    }
}

private struct Unavailable: View {
    let title: String
    let message: String
    var body: some View { ContentUnavailableView(title, systemImage: "banknote", description: Text(message)) }
}

@MainActor private func fund(_ model: FieldModel, _ id: UUID) -> PettyCashFundDTO? { model.pettyCash.funds.first { $0.id == id } }

private func trimmedEmpty(_ text: String) -> Bool { text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }

/// Acknowledge or dispute a funding / top-up the office issued.
struct PettyCashAckFormView: View {
    let model: FieldModel
    let movementID: UUID
    @Environment(\.dismiss) private var dismiss
    @State private var received: String?
    @State private var note = ""
    @State private var error: String?

    var body: some View {
        let waiting = (try? model.recorder?.alreadySaved(.pettyCashAcknowledgement, clientID: movementID)) ?? false
        let movement = model.pettyCash.waiting.compactMap { item -> PettyCashMovementDTO? in
            if case let .movement(m) = item, m.id == movementID { return m }
            return nil
        }.first
        PettyCashForm(title: P.titleAck, canSave: false, showsSave: false, onCancel: { dismiss() }, onSave: {}, error: $error) {
            if waiting {
                Section { Text(P.ackWaiting).foregroundStyle(Palette.warning) }
            } else if !model.access.pettyCash {
                Unavailable(title: P.titleAck, message: P.unavailable)
            } else if let m = movement {
                let issued = m.amount.description
                Section {
                    Text(m.kind == PettyCashMovementDTO.funding ? P.ackFunding : P.ackTopUp).font(.headline)
                    LabeledContent(P.fund, value: m.pettyCashFundName ?? model.pettyCash.funds.first { $0.id == m.fundID }?.name ?? "")
                    LabeledContent(P.ackNumber, value: m.number)
                    LabeledContent(P.ackIssued, value: P.money(m.amount, m.currency))
                    if let at = m.issuedAt { LabeledContent(P.ackIssuedAt, value: at.listText) }
                    if let by = m.issuedByName { LabeledContent(P.ackIssuedBy, value: by) }
                    if let reference = m.reference, !reference.isEmpty { LabeledContent(P.ackReference, value: reference) }
                    if let text = m.note, !text.isEmpty { Text(text).foregroundStyle(.secondary) }
                }
                Section {
                    TextField(P.ackAmount, text: Binding(get: { received ?? issued }, set: { received = $0 }))
                        .keyboardType(.decimalPad).font(.title3.monospacedDigit())
                    TextField(P.note, text: $note, axis: .vertical)
                } footer: { Text(P.ackFooter) }
                Section {
                    Button(P.ackAcknowledge) { answer(true, issued: issued) }.buttonStyle(.borderedProminent).tint(Palette.live)
                    Button(P.ackDispute, role: .destructive) { answer(false, issued: issued) }.disabled(trimmedEmpty(note))
                    if trimmedEmpty(note) { Text(P.ackDisputeReason).font(.footnote).foregroundStyle(.secondary) }
                }
            } else {
                Unavailable(title: P.titleAck, message: P.notFound)
            }
        }
    }

    private func answer(_ acknowledge: Bool, issued: String) {
        do {
            try model.perform {
                try $0.acknowledgePettyCash(movementID: movementID, acknowledge: acknowledge, receivedText: received ?? issued, note: note)
            }
            dismiss()
        } catch { self.error = JobDetailView.describe(error) }
    }
}

/// Ask the office for a top-up of a fund I hold.
struct PettyCashTopUpFormView: View {
    let model: FieldModel
    let fundID: UUID
    @Environment(\.dismiss) private var dismiss
    @State private var clientID = UUID()
    @State private var amount = ""
    @State private var note = ""
    @State private var aboveReason = ""
    @State private var error: String?

    var body: some View {
        let f = fund(model, fundID)
        let check = f.map { PettyCashRules.topUp(amountText: amount, aboveReason: aboveReason, fund: $0) }
        PettyCashForm(title: P.titleTopUp, saveLabel: P.topUpSend, canSave: model.access.pettyCash && check?.isValid == true,
                      onCancel: { dismiss() }, onSave: save, error: $error) {
            if !model.access.pettyCash {
                Unavailable(title: P.titleTopUp, message: P.unavailable)
            } else if let f {
                FundSummarySection(fund: f)
                Section {
                    TextField(P.topUpAmount, text: $amount).keyboardType(.decimalPad).font(.title3.monospacedDigit())
                } footer: { Text(P.topUpAmountFooter) }
                if PettyCashRules.topUpAboveCap(amountText: amount, fund: f) {
                    Section {
                        TextField(P.topUpAboveReason, text: $aboveReason, axis: .vertical)
                    } footer: {
                        Text(P.topUpAboveFooter(InboxTexts.money(DecimalString(PettyCashRules.capEstimate(f) ?? 0).description, f.currency)))
                    }
                }
                Section {
                    TextField(P.note, text: $note, axis: .vertical)
                } footer: { Text(P.topUpFooter) }
            } else {
                Unavailable(title: P.titleTopUp, message: P.notFound)
            }
        }
    }

    private func save() {
        do {
            try model.perform {
                try $0.requestPettyCashTopUp(fundID: fundID, amountText: amount, note: note, aboveReason: aboveReason, clientID: clientID)
            }
            dismiss()
        } catch { self.error = JobDetailView.describe(error) }
    }
}

/// Hand money of a fund back to the office (with photos when the tenant requires them).
struct PettyCashReturnFormView: View {
    let model: FieldModel
    let fundID: UUID
    @Environment(\.dismiss) private var dismiss
    @State private var clientID = UUID()
    @State private var amount: String?
    @State private var method = PettyCashTexts.returnMethods[0]
    @State private var accountID: UUID?
    @State private var reference = ""
    @State private var note = ""
    @State private var photos: [(evidence: StoredEvidence, data: Data)] = []
    @State private var error: String?

    var body: some View {
        let f = fund(model, fundID)
        let required = model.pettyCash.policy.returnEvidenceRequired
        let available = f?.balance?.availableToSpend
        let prefill = available.flatMap { $0.value > 0 ? $0.description : nil } ?? ""
        let text = amount ?? prefill
        let check = PettyCashRules.returnFund(amountText: text, photoCount: photos.count, evidenceRequired: required)
        PettyCashForm(title: P.titleReturn, canSave: model.access.pettyCash && f != nil && check.isValid,
                      onCancel: { discard(); dismiss() }, onSave: save, error: $error) {
            if !model.access.pettyCash {
                Unavailable(title: P.titleReturn, message: P.unavailable)
            } else if let f {
                FundSummarySection(fund: f)
                Section {
                    TextField(P.returnAmount, text: Binding(get: { text }, set: { amount = $0 }))
                        .keyboardType(.decimalPad).font(.title3.monospacedDigit())
                    Picker(P.returnMethod, selection: $method) {
                        ForEach(P.returnMethods, id: \.self) { Text(P.returnMethodLabel($0)).tag($0) }
                    }
                    if model.access.depositAccountsOn {
                        let accounts = model.depositAccounts.filter { $0.isActive && $0.currency == f.currency }
                            .map { PickerOption(id: $0.id, title: $0.name, subtitle: RemittanceRules.subtitle($0)) }
                        if !accounts.isEmpty {
                            SearchablePickerField(label: P.returnAccount, options: accounts, selection: $accountID,
                                                  noneTitle: P.returnNoAccount, identifier: "pettyCash.return.account")
                        }
                    }
                    TextField(P.returnReference, text: $reference)
                    TextField(P.note, text: $note, axis: .vertical)
                } footer: { Text(P.returnFooter) }
                EvidencePhotosSection(model: model, photos: $photos, error: $error, footer: required ? P.returnEvidenceRequired
                                          : FieldAccountabilityTexts.hoursEvidenceFooter)
            } else {
                Unavailable(title: P.titleReturn, message: P.notFound)
            }
        }
        .interactiveDismissDisabled(!photos.isEmpty)
    }

    private func discard() {
        photos.forEach { model.discardEvidence($0.evidence) }
        photos = []
    }

    private func save() {
        let prefill = fund(model, fundID)?.balance?.availableToSpend.description ?? ""
        do {
            try model.perform {
                try $0.returnPettyCash(fundID: fundID, amountText: amount ?? prefill, method: method, depositAccountID: accountID,
                                       reference: reference, note: note, evidence: photos.map(\.evidence),
                                       evidenceRequired: model.pettyCash.policy.returnEvidenceRequired, clientID: clientID)
            }
            photos = []
            dismiss()
        } catch { self.error = JobDetailView.describe(error) }
    }
}

/// Count the cash of a fund (with a witness when the tenant asks for one; chosen online).
struct PettyCashCountFormView: View {
    let model: FieldModel
    let fundID: UUID
    @Environment(\.dismiss) private var dismiss
    @State private var clientID = UUID()
    @State private var counted = ""
    @State private var note = ""
    @State private var query = ""
    @State private var results: [PersonDTO]?
    @State private var witness: PersonDTO?
    @State private var photos: [(evidence: StoredEvidence, data: Data)] = []
    @State private var error: String?

    var body: some View {
        let f = fund(model, fundID)
        let witnessRequired = model.pettyCash.policy.countWitnessRequired
        let check = PettyCashRules.count(countedText: counted)
        PettyCashForm(title: P.titleCount, canSave: model.access.pettyCashCount && f != nil && check.isValid,
                      onCancel: { discard(); dismiss() }, onSave: save, error: $error) {
            if !model.access.pettyCashCount {
                Unavailable(title: P.titleCount, message: P.unavailable)
            } else if let f {
                Section {
                    TextField(P.countAmount, text: $counted).keyboardType(.decimalPad).font(.title3.monospacedDigit())
                    TextField(P.note, text: $note, axis: .vertical)
                } header: { Text(P.fundHeader(code: f.code, name: f.name)) } footer: { Text(P.countFooter) }
                if witnessRequired { witnessSection }
                EvidencePhotosSection(model: model, photos: $photos, error: $error)
            } else {
                Unavailable(title: P.titleCount, message: P.notFound)
            }
        }
        .interactiveDismissDisabled(!photos.isEmpty)
    }

    @ViewBuilder private var witnessSection: some View {
        Section {
            if let witness {
                LabeledContent(P.countWitness, value: witness.displayName)
                Button(P.countWitnessNone, role: .destructive) { self.witness = nil }
            } else if model.isOnline {
                TextField(P.countWitnessSearch, text: $query)
                    .autocorrectionDisabled()
                    .task(id: query) {
                        try? await Task.sleep(for: .milliseconds(300))
                        results = query.trimmingCharacters(in: .whitespaces).count >= PettyCashRules.minWitnessQuery
                            ? await model.searchPeople(query) : nil
                    }
                if let results {
                    if results.isEmpty { Text(P.countWitnessNoResults).foregroundStyle(.secondary) }
                    ForEach(results) { person in Button(person.displayName) { witness = person } }
                }
            } else {
                Text(P.countWitnessOffline).foregroundStyle(.secondary)
            }
        } header: { Text(P.countWitness) } footer: {
            Text(witness == nil ? "\(P.countWitnessFooter) \(P.countNoWitness)" : P.countWitnessFooter)
        }
    }

    private func discard() {
        photos.forEach { model.discardEvidence($0.evidence) }
        photos = []
    }

    private func save() {
        do {
            try model.perform {
                try $0.countPettyCash(fundID: fundID, countedText: counted, witnessUserID: witness?.userID, note: note,
                                      evidence: photos.map(\.evidence), clientID: clientID)
            }
            photos = []
            dismiss()
        } catch { self.error = JobDetailView.describe(error) }
    }
}

/// Take over a fund being handed to me, or decline it with a reason.
struct PettyCashHolderChangeFormView: View {
    let model: FieldModel
    let changeID: UUID
    @Environment(\.dismiss) private var dismiss
    @State private var note = ""
    @State private var error: String?

    var body: some View {
        let waiting = (try? model.recorder?.alreadySaved(.pettyCashHolderChangeAcknowledgement, clientID: changeID)) ?? false
        let change = model.pettyCash.waiting.compactMap { item -> PettyCashHolderChangeDTO? in
            if case let .holderChange(c) = item, c.id == changeID { return c }
            return nil
        }.first
        PettyCashForm(title: P.titleHolderChange, canSave: false, showsSave: false, onCancel: { dismiss() }, onSave: {}, error: $error) {
            if waiting {
                Section { Text(P.ackWaiting).foregroundStyle(Palette.warning) }
            } else if !model.access.pettyCash {
                Unavailable(title: P.titleHolderChange, message: P.unavailable)
            } else if let c = change {
                let from = c.fromStaffName ?? P.someone
                Section {
                    LabeledContent(P.fund, value: c.pettyCashFundName ?? P.fund)
                    LabeledContent(P.holderFrom, value: from)
                    if let by = c.requestedByName { LabeledContent(P.holderRequestedBy, value: by) }
                    if let at = c.requestedAt { LabeledContent(P.holderRequestedAt, value: at.listText) }
                    if let text = c.note, !text.isEmpty { Text(text).foregroundStyle(.secondary) }
                } footer: { Text(P.holderFooter(from)) }
                Section { TextField(P.note, text: $note, axis: .vertical) }
                Section {
                    Button(P.holderAccept) { answer(true) }.buttonStyle(.borderedProminent).tint(Palette.live)
                    Button(P.holderDecline, role: .destructive) { answer(false) }
                        .disabled(!PettyCashRules.holderChange(accept: false, note: note).isValid)
                    if !PettyCashRules.holderChange(accept: false, note: note).isValid {
                        Text(P.holderDeclineReason).font(.footnote).foregroundStyle(.secondary)
                    }
                }
            } else {
                Unavailable(title: P.titleHolderChange, message: P.notFound)
            }
        }
    }

    private func answer(_ accept: Bool) {
        do {
            try model.perform { try $0.answerPettyCashHolderChange(changeID: changeID, accept: accept, note: note) }
            dismiss()
        } catch { self.error = JobDetailView.describe(error) }
    }
}

/// Clear an advance handed out from my fund: the change I take back.
struct PettyCashAdvanceFormView: View {
    let model: FieldModel
    let advanceID: UUID
    @Environment(\.dismiss) private var dismiss
    @State private var change: String?
    @State private var note = ""
    @State private var error: String?

    var body: some View {
        let row = model.pettyCash.advances.first { $0.advance.id == advanceID && $0.fromMyFund }
        let prefill = row?.advance.remaining?.description ?? ""
        let text = change ?? prefill
        let check = PettyCashRules.clearAdvance(changeText: text)
        PettyCashForm(title: P.titleAdvance, saveLabel: P.advanceClear, canSave: model.access.pettyCash && row != nil && check.isValid,
                      onCancel: { dismiss() }, onSave: save, error: $error) {
            if !model.access.pettyCash {
                Unavailable(title: P.titleAdvance, message: P.unavailable)
            } else if let a = row?.advance {
                Section {
                    LabeledContent(P.fund, value: a.pettyCashFundName ?? model.pettyCash.funds.first { $0.id == a.fundID }?.name ?? "")
                    LabeledContent(P.advanceRecipient, value: a.recipientStaffName ?? P.someone)
                    LabeledContent(P.advanceAmount, value: P.money(a.amount, a.currency))
                    if let purpose = a.purpose { LabeledContent(P.advancePurpose, value: purpose) }
                    LabeledContent(P.advanceApproved, value: P.money(a.approvedSpending, a.currency))
                    if (a.pendingSpending?.value ?? 0) != 0 { LabeledContent(P.advancePending, value: P.money(a.pendingSpending, a.currency)) }
                    LabeledContent(P.advanceRemaining, value: P.money(a.remaining, a.currency))
                    if let due = a.dueAt { LabeledContent(P.advanceDue, value: due.listText) }
                } header: { Text(a.number) }
                if (a.pendingSpending?.value ?? 0) > 0 {
                    Section { Text(P.advancePendingWarning).foregroundStyle(Palette.warning) }
                }
                Section {
                    TextField(P.advanceChange, text: Binding(get: { text }, set: { change = $0 }))
                        .keyboardType(.decimalPad).font(.title3.monospacedDigit())
                    TextField(P.note, text: $note, axis: .vertical)
                } footer: { Text(P.advanceFooter) }
            } else {
                Unavailable(title: P.titleAdvance, message: P.notFound)
            }
        }
    }

    private func save() {
        let prefill = model.pettyCash.advances.first { $0.advance.id == advanceID }?.advance.remaining?.description ?? ""
        do {
            try model.perform { try $0.clearPettyCashAdvance(advanceID: advanceID, changeText: change ?? prefill, note: note) }
            dismiss()
        } catch { self.error = JobDetailView.describe(error) }
    }
}
#endif
