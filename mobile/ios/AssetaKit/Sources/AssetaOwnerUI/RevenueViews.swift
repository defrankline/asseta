#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

// DEC-031 Phase 1 Owner screens (strings doc "DEC-031 Phase 1 — revenue"): the "Revenue differences" Approvals
// section, the revenue difference screen (figures, jobs, explanation, adjustments; Explain / Approve / Reject /
// Confirm), and the read-only daily machine sheet per machine. Online only; reads may show the cached snapshot.

private typealias T = RevenueTexts

/// Revenue differences waiting under Approvals: EXPLANATION_PROPOSED for every reader, OPEN only for explain or decide
/// holders. Shown only when something waits.
struct RevenueDifferencesSection: View {
    let model: OwnerModel
    @State private var open = Loader<Page<RevenueDifferenceDTO>>()
    @State private var proposed = Loader<Page<RevenueDifferenceDTO>>()

    private var listsOpen: Bool { RevenueRules.listsOpen(permissions: model.features.permissions) }

    var body: some View {
        let items = ((listsOpen ? open.value?.items : nil) ?? []) + (proposed.value?.items ?? [])
        Group {
            if !items.isEmpty {
                Section(T.sectionDifferences) {
                    ForEach(items) { item in
                        NavigationLink(value: OwnerRoute.revenueDifference(item.id)) { RevenueDifferenceRow(item: item) }
                    }
                }
            }
        }
        .task(id: model.changeTick) {
            guard model.features.revenueRead else { return }
            if listsOpen {
                await open.load(model, .revenueDifferences(status: RevenueDifferenceStatus.open),
                                OwnerAPI.revenueDifferences(status: RevenueDifferenceStatus.open))
            }
            await proposed.load(model, .revenueDifferences(status: RevenueDifferenceStatus.explanationProposed),
                                OwnerAPI.revenueDifferences(status: RevenueDifferenceStatus.explanationProposed))
        }
    }
}

struct RevenueDifferenceRow: View {
    let item: RevenueDifferenceDTO

    var body: some View {
        let row = RevenuePresentation.row(item)
        VStack(alignment: .leading, spacing: 4) {
            Text(row.headline).font(.headline)
            Text(row.subtitle).font(.subheadline).foregroundStyle(.secondary).lineLimit(2)
            if let footnote = row.footnote { Text(footnote).font(.caption).foregroundStyle(.secondary) }
        }
        .accessibilityElement(children: .combine)
    }
}

/// One revenue difference, read by id: figures, jobs, explanation, decision and adjustments; Explain (OPEN, explain
/// holder) and the decision (decide holder, never the explainer). When both show they share one note (as Android).
struct RevenueDifferenceView: View {
    let model: OwnerModel
    let differenceID: UUID
    @State private var loader = Loader<RevenueDifferenceDTO>()
    @State private var reasons = Loader<Page<RevenueReasonDTO>>()
    @State private var reasonID: UUID?
    @State private var note = ""
    @State private var working = false
    @State private var actionError: String?
    @State private var message: String?
    @State private var confirming: RevenueDecision?

    var body: some View {
        Form {
            if let d = loader.value {
                let explain = model.features.revenueExplain && RevenueRules.canExplain(d, permissions: model.features.permissions)
                let decisions = model.features.revenueDecide ? RevenueRules.decisions(d, permissions: model.features.permissions) : []
                Section(T.figures) {
                    FieldList(fields: RevenuePresentation.figures(d))
                    LabeledContent(T.status) { Pill(text: T.status(d.status), color: tone(d.status)) }
                }
                Section(T.jobs) {
                    let jobs = RevenuePresentation.jobs(d)
                    if jobs.isEmpty { Text(T.noJobs).font(.footnote).foregroundStyle(.secondary) }
                    FieldList(fields: jobs)
                }
                let explanation = RevenuePresentation.explanation(d) + RevenuePresentation.decided(d)
                if !explanation.isEmpty {
                    Section(T.explanation) { FieldList(fields: explanation) }
                }
                let adjustments = RevenuePresentation.adjustments(d)
                if !adjustments.isEmpty {
                    Section(T.adjustments) {
                        ForEach(adjustments, id: \.self) { Text($0).font(.subheadline) }
                    }
                }
                if explain { explainSection }
                if !decisions.isEmpty { decisionSection(d, decisions, sharesNote: explain) }
                if let message { Text(message).foregroundStyle(Brand.amber).accessibilityIdentifier("revenue.message") }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView()
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(T.titleDifference)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
        .confirmationDialog(confirming.map(confirmText) ?? "", isPresented: Binding(
            get: { confirming != nil }, set: { if !$0 { confirming = nil } }), titleVisibility: .visible) {
            if let decision = confirming {
                Button(RevenueRules.buttonLabel(decision), role: .destructive) { Task { await decide(decision) } }
            }
        }
    }

    private func tone(_ status: String) -> Color {
        switch RevenuePresentation.statusTone(status) {
        case .live: Palette.live
        case .critical: Palette.offline
        case .warning: Palette.warning
        }
    }

    private func confirmText(_ decision: RevenueDecision) -> String {
        decision == .reject ? T.confirmReject : T.confirmConfirm
    }

    private var errorText: some View {
        Text(actionError ?? "").font(.footnote).foregroundStyle(Palette.offline).accessibilityIdentifier("revenue.error")
    }

    @ViewBuilder private var explainSection: some View {
        let block = model.mutationBlock(permitted: model.features.revenueExplain, showingCachedData: loader.isFromCache)
        let options = RevenueRules.pickable(reasons.value?.items ?? [])
        Section {
            if let block {
                BlockedNote(block: block)
            } else {
                if options.isEmpty && reasons.value != nil {
                    Text(T.reasonsEmpty).font(.footnote).foregroundStyle(.secondary)
                }
                Picker(T.chooseReason, selection: $reasonID) {
                    ForEach(options) { Text($0.name).tag(UUID?.some($0.id)) }
                }
                .pickerStyle(.inline)
                TextField(T.noteLabel, text: Binding(get: { note }, set: { note = String($0.prefix(RevenueRules.noteMax)) }),
                          axis: .vertical).lineLimit(2...5)
                    .accessibilityIdentifier("revenue.note")
                Button(T.sendExplanation) { Task { await explain() } }
                    .buttonStyle(.borderedProminent)
                    .disabled(working || reasonID == nil || !RevenueRules.noteOK(note))
                    .accessibilityIdentifier("revenue.explain")
                if actionError != nil { errorText }
            }
        } header: { Text(T.explain) } footer: { Text(T.explainFooter) }
    }

    @ViewBuilder private func decisionSection(_ d: RevenueDifferenceDTO, _ decisions: [RevenueDecision], sharesNote: Bool) -> some View {
        let block = model.mutationBlock(permitted: model.features.revenueDecide, showingCachedData: loader.isFromCache)
        let own = RevenueRules.isOwnExplanation(d, userID: model.me.userID)
        Section {
            if let block {
                BlockedNote(block: block)
            } else {
                if own { Label(T.ownExplanation, systemImage: "lock").font(.footnote).foregroundStyle(.secondary) }
                if !sharesNote {
                    TextField(T.noteLabel, text: Binding(get: { note }, set: { note = String($0.prefix(RevenueRules.noteMax)) }),
                              axis: .vertical).lineLimit(2...5)
                        .disabled(own)
                        .accessibilityIdentifier("revenue.decisionNote")
                }
                if decisions.contains(.approve) {
                    HStack {
                        Button(T.approve) { Task { await decide(.approve) } }
                            .buttonStyle(.borderedProminent).tint(Palette.live)
                            .accessibilityIdentifier("revenue.approve")
                        Spacer()
                        Button(T.reject, role: .destructive) { confirming = .reject }
                            .buttonStyle(.bordered)
                            .accessibilityIdentifier("revenue.reject")
                    }
                    .disabled(working || own || !RevenueRules.noteOK(note))
                }
                if decisions.contains(.confirm) {
                    Button(T.confirm) { confirming = .confirm }
                        .buttonStyle(.bordered).tint(Palette.warning)
                        .disabled(working || own || !RevenueRules.noteOK(note))
                        .accessibilityIdentifier("revenue.confirm")
                }
                if !sharesNote && actionError != nil { errorText }
            }
        } header: { Text(T.decide) } footer: { Text(T.decideFooter) }
    }

    private func explain() async {
        guard let reasonID else { return }
        await send(T.explanationSent) {
            try await $0.send(OwnerAPI.explainRevenueDifference(differenceID, reasonID: reasonID, note: note, idempotencyKey: UUID()))
        }
    }

    private func decide(_ decision: RevenueDecision) async {
        await send(RevenueRules.done(decision)) {
            try await $0.send(OwnerAPI.decideRevenueDifference(differenceID, decision: decision, note: note, idempotencyKey: UUID()))
        }
    }

    private func send(_ done: String, _ call: (OwnerRepository) async throws -> RevenueDifferenceDTO) async {
        guard let repository = model.repository, RevenueRules.noteOK(note), !working else { return }
        working = true
        actionError = nil
        message = nil
        defer { working = false }
        do {
            loader.replace(try await call(repository))
            note = ""
            reasonID = nil
            message = done
            UIAccessibility.post(notification: .announcement, argument: done)
        } catch {
            actionError = RevenueRules.message(for: error)
            model.handle(error)
            if RevenueRules.needsReload(error) { await reload() }
        }
    }

    private func reload() async {
        await loader.load(model, .revenueDifference(differenceID), OwnerAPI.revenueDifference(differenceID))
        if model.features.revenueExplain { await reasons.load(model, .revenueReasons, OwnerAPI.revenueReasons()) }
    }
}

/// One machine's daily machine sheet: the last 14 tenant-local days, newest first (read-only).
struct DailySheetView: View {
    let model: OwnerModel
    let machineID: UUID
    @State private var loader = Loader<Page<DailyMachineSheetDTO>>()

    var body: some View {
        let range = RevenuePresentation.sheetRange()
        List {
            if let page = loader.value {
                let rows = RevenuePresentation.sheetRows(page.items)
                if rows.isEmpty { EmptyState(title: T.sheetEmpty, systemImage: "calendar") }
                Section {
                    ForEach(rows) { day in
                        let row = RevenuePresentation.sheetRow(day)
                        NavigationLink(value: OwnerRoute.dailySheetDay(machineID, day.day)) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(row.title).font(.headline)
                                Text(row.hours).font(.subheadline.monospacedDigit()).foregroundStyle(.secondary)
                                ForEach(row.differences, id: \.self) { Text($0).font(.subheadline).foregroundStyle(.secondary) }
                                if let flags = row.flags { Text(flags).font(.caption).foregroundStyle(Palette.warning) }
                            }
                            .accessibilityElement(children: .combine)
                        }
                    }
                } footer: { if !rows.isEmpty { Text(T.sheetFooter) } }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload(range) }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(T.sheetTitle)
        .refreshable { await reload(range) }
        .task(id: model.changeTick) { await reload(range) }
    }

    private func reload(_ range: (from: String, to: String)) async {
        await loader.load(model, .dailySheet(machineID: machineID, dayFrom: range.from, dayTo: range.to),
                          OwnerAPI.dailySheet(machineID: machineID, dayFrom: range.from, dayTo: range.to))
    }
}

/// One machine on one day: hours, readings, jobs, money per currency, fuel and flags (read-only).
struct DailySheetDayView: View {
    let model: OwnerModel
    let machineID: UUID
    let day: String
    @State private var loader = Loader<DailyMachineSheetDTO>()

    var body: some View {
        Form {
            if let s = loader.value {
                Section(T.sheetHours) {
                    Text(T.sheetDayTitle(machine: DisplayName.machine(code: s.machineCode, name: s.machineName, id: s.machineID),
                                         day: RevenuePresentation.day(s.day))).font(.headline)
                    FieldList(fields: RevenuePresentation.sheetHours(s))
                }
                Section(T.sheetReadings) { FieldList(fields: RevenuePresentation.sheetReadings(s)) }
                let jobs = RevenuePresentation.sheetJobs(s)
                if !jobs.isEmpty { Section(T.jobs) { FieldList(fields: jobs) } }
                ForEach(Array(RevenuePresentation.sheetMoney(s).enumerated()), id: \.offset) { _, card in
                    Section(card.title) { FieldList(fields: card.fields) }
                }
                Section(T.sheetFuel) { LabeledContent(T.sheetFuel, value: RevenuePresentation.sheetFuel(s)) }
                Section {
                    let flags = RevenuePresentation.sheetFlags(s)
                    if flags.isEmpty { Text(T.sheetNoFlags).font(.footnote).foregroundStyle(.secondary) }
                    ForEach(flags, id: \.self) { Text($0).font(.subheadline).foregroundStyle(Palette.warning) }
                } header: { Text(T.sheetFlags) } footer: { Text(T.sheetFooter) }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView()
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(RevenuePresentation.day(day))
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private func reload() async {
        await loader.load(model, .dailySheetDay(machineID: machineID, day: day), OwnerAPI.dailySheetDay(machineID: machineID, day: day))
    }
}

/// Labelled values (label left, value right).
private struct FieldList: View {
    let fields: [DecisionField]

    var body: some View {
        ForEach(fields, id: \.self) { field in
            LabeledContent(field.label) { Text(field.value).multilineTextAlignment(.trailing) }
        }
    }
}
#endif
