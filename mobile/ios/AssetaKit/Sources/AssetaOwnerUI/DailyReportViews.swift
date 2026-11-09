#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

// DEC-032 Phase 1 Owner screens: daily reports to review (Approvals section + review screen), the extras of the work
// allocation correction decision (the entry being corrected and the evidence) and a machine day's allocation cards.

private typealias T = DailyReportOwnerTexts

/// One evidence photo opened in a sheet.
private struct EvidenceRef: Identifiable { let id: UUID }

/// Daily reports waiting for review under Approvals; shown only when something waits.
struct DailyReportsSection: View {
    let model: OwnerModel
    @State private var loader = Loader<Page<DailyReportDTO>>()

    var body: some View {
        let items = loader.value?.items ?? []
        Group {
            if !items.isEmpty {
                Section(T.section) {
                    ForEach(items) { report in
                        NavigationLink(value: OwnerRoute.dailyReport(report.id)) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(AllocationPresentation.rowHeadline(report)).font(.headline)
                                Text(AllocationPresentation.rowLine(report)).font(.subheadline).foregroundStyle(.secondary)
                                ForEach(AllocationPresentation.flags(report), id: \.self) {
                                    Text($0).font(.caption).foregroundStyle(Palette.warning)
                                }
                                Text(DisplayName.optional(report.submittedByName, id: report.submittedBy)
                                    .map { OwnerAccountabilityTexts.approvalsProposedBy(report.submittedAt.shortStamp, $0) }
                                    ?? OwnerAccountabilityTexts.approvalsProposed(report.submittedAt.shortStamp))
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            .accessibilityElement(children: .combine)
                        }
                    }
                }
            }
        }
        .task(id: model.changeTick) {
            await loader.load(model, .dailyReports(status: DailyReportStatuses.submitted),
                              OwnerAPI.dailyReports(status: DailyReportStatuses.submitted))
        }
    }
}

/// One daily report: figures, reasons, allocations, evidence and flags; a note with "Mark as reviewed" / "Send back"
/// (`tenant.meter.review`, never the sender; the server refuses it too).
struct DailyReportReviewView: View {
    let model: OwnerModel
    let reportID: UUID
    @State private var loader = Loader<DailyReportDTO>()
    @State private var note = ""
    @State private var working = false
    @State private var actionError: String?
    @State private var message: String?
    @State private var photo: EvidenceRef?

    var body: some View {
        Form {
            if let r = loader.value {
                Section(T.figures) {
                    FieldRows(fields: AllocationPresentation.figures(r))
                    LabeledContent(OwnerAccountabilityTexts.fieldStatus) {
                        Pill(text: T.status(r.status), color: r.status == DailyReportStatuses.returned ? Palette.warning : Palette.live)
                    }
                    ForEach(AllocationPresentation.flags(r), id: \.self) { Text($0).font(.footnote).foregroundStyle(Palette.warning) }
                }
                let reasons = AllocationPresentation.reasons(r)
                if !reasons.isEmpty { Section(T.reasons) { FieldRows(fields: reasons) } }
                let allocations = AllocationPresentation.allocations(r)
                if !allocations.isEmpty { Section(T.allocations) { FieldRows(fields: allocations) } }
                if let note = r.note, !note.isEmpty { Section(T.note) { Text(note) } }
                if !r.evidenceAttachmentIDs.isEmpty {
                    Section(T.evidence) {
                        ForEach(Array(r.evidenceAttachmentIDs.enumerated()), id: \.offset) { index, id in
                            PhotoButton(label: "\(T.evidence.lowercased()) \(index + 1)", isOnline: model.isOnline) { photo = EvidenceRef(id: id) }
                        }
                    }
                }
                let review = AllocationPresentation.reviewFields(r)
                if !review.isEmpty { Section(T.review) { FieldRows(fields: review) } }
                if r.status == DailyReportStatuses.submitted && model.features.reviewDailyReports { reviewSection(r) }
                if let message { Text(message).foregroundStyle(Brand.amber).accessibilityIdentifier("report.message") }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView()
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(T.title)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
        .sheet(item: $photo) { EvidencePhotoView(model: model, title: T.evidence, request: OwnerAPI.attachmentURL($0.id)) }
    }

    @ViewBuilder private func reviewSection(_ r: DailyReportDTO) -> some View {
        let block = model.mutationBlock(permitted: model.features.reviewDailyReports, showingCachedData: loader.isFromCache)
        let own = DailyReportReview.isOwn(r, userID: model.me.userID)
        Section {
            if let block {
                BlockedNote(block: block)
            } else if own {
                Label(T.own, systemImage: "lock").font(.footnote).foregroundStyle(.secondary)
            } else {
                TextField(T.noteLabel, text: Binding(get: { note }, set: { note = String($0.prefix(DailyReportReview.noteMax)) }), axis: .vertical)
                    .lineLimit(2...5).accessibilityIdentifier("report.reviewNote")
                HStack {
                    Button(T.markReviewed) { Task { await review(DailyReportReview.reviewed, done: T.reviewed) } }
                        .buttonStyle(.borderedProminent).tint(Palette.live).accessibilityIdentifier("report.markReviewed")
                    Spacer()
                    Button(T.sendBack, role: .destructive) { Task { await review(DailyReportReview.returned, done: T.sentBack) } }
                        .buttonStyle(.bordered).accessibilityIdentifier("report.sendBack")
                }
                .disabled(working || !DailyReportReview.noteOK(note))
                if let actionError {
                    Text(actionError).font(.footnote).foregroundStyle(Palette.offline).accessibilityIdentifier("report.error")
                }
            }
        } header: { Text(T.review) } footer: { Text(T.reviewFooter) }
    }

    private func review(_ decision: String, done: String) async {
        guard let repository = model.repository, DailyReportReview.noteOK(note), !working else { return }
        working = true
        actionError = nil
        message = nil
        defer { working = false }
        do {
            loader.replace(try await repository.send(OwnerAPI.reviewDailyReport(reportID, decision: decision, note: note, idempotencyKey: UUID())))
            note = ""
            message = done
            UIAccessibility.post(notification: .announcement, argument: done)
        } catch {
            actionError = DailyReportReview.message(for: error)
            model.handle(error)
            if DailyReportReview.needsReload(error) { await reload() }
        }
    }

    private func reload() async {
        await loader.load(model, .dailyReport(reportID), OwnerAPI.dailyReport(reportID))
    }
}

/// The correction decision's extras: the entry as it stands now, and the evidence of the proposal.
struct AllocationCorrectionExtras: View {
    let model: OwnerModel
    let correction: AllocationCorrectionDTO
    @State private var original = Loader<WorkAllocationDTO>()
    @State private var photo: EvidenceRef?

    var body: some View {
        let evidence = Array(Set(correction.entries.flatMap(\.evidenceAttachmentIDs))).sorted { $0.uuidString < $1.uuidString }
        Group {
            if let a = original.value {
                Section { LabeledContent(T.allocationOriginal, value: AllocationPresentation.originalLine(a)) }
            }
            if !evidence.isEmpty {
                Section(T.evidence) {
                    ForEach(Array(evidence.enumerated()), id: \.offset) { index, id in
                        PhotoButton(label: "\(T.evidence.lowercased()) \(index + 1)", isOnline: model.isOnline) { photo = EvidenceRef(id: id) }
                    }
                }
            }
        }
        .task(id: correction.supersedesID) {
            guard let id = correction.supersedesID else { return }
            await original.load(model, .workAllocation(id), OwnerAPI.workAllocation(id))
        }
        .sheet(item: $photo) { EvidencePhotoView(model: model, title: T.evidence, request: OwnerAPI.attachmentURL($0.id)) }
    }
}

/// One allocation: kind, who, readings and hours, the lots it drew from.
struct AllocationEntryRow: View {
    let entry: WorkAllocationDTO

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text(T.kind(entry.kind)).font(.headline)
                    .foregroundStyle(entry.kind == AllocationKinds.unexplained ? Palette.warning : Color.primary)
                Spacer()
            }
            let who = AllocationPresentation.who(entry)
            if !who.isEmpty { Text(who).font(.subheadline) }
            Text(AllocationPresentation.entryLine(entry)).font(.subheadline.monospacedDigit()).foregroundStyle(.secondary)
            ForEach(AllocationPresentation.lots(entry), id: \.self) { Text($0).font(.caption).foregroundStyle(.secondary) }
        }
        .accessibilityElement(children: .combine)
    }
}

/// "Hours allocated" and "Work allocations" of one machine on one day (`tenant.meter.read`, ENGINE_HOURS on).
struct AllocationDaySections: View {
    let model: OwnerModel
    let machineID: UUID
    let day: String
    @State private var reconciliation = Loader<[AllocationDayDTO]>()
    @State private var active = Loader<Page<WorkAllocationDTO>>()

    var body: some View {
        let entries = (active.value?.items ?? []).sorted { $0.startAt < $1.startAt }
        Group {
            if let d = reconciliation.value?.first {
                Section {
                    FieldRows(fields: AllocationPresentation.dayFields(d))
                } header: { Text(T.dayCard) } footer: { Text(d.reconciled ? T.dayReconciled : T.dayNotReconciled) }
            }
            if active.value != nil {
                Section(T.entries) {
                    if entries.isEmpty { Text(T.entriesEmpty).font(.footnote).foregroundStyle(.secondary) }
                    ForEach(entries) { AllocationEntryRow(entry: $0) }
                }
            }
        }
        .task(id: model.changeTick) {
            await reconciliation.load(model, .allocationDay(machineID: machineID, day: day), OwnerAPI.allocationDay(machineID: machineID, day: day))
            await active.load(model, .workAllocations(machineID: machineID, day: day, status: AllocationStatuses.active),
                              OwnerAPI.workAllocations(machineID: machineID, day: day, status: AllocationStatuses.active))
        }
    }
}

/// A machine's days of the ledger (last 14, newest first): the day list while revenue checks are off.
struct LedgerDaysView: View {
    let model: OwnerModel
    let machineID: UUID
    @State private var loader = Loader<[AllocationDayDTO]>()

    var body: some View {
        let range = RevenuePresentation.sheetRange()
        List {
            if let days = loader.value {
                let rows = days.sorted { $0.day > $1.day }
                if rows.isEmpty { EmptyState(title: T.daysEmpty, systemImage: "calendar") }
                ForEach(rows, id: \.day) { day in
                    NavigationLink(value: OwnerRoute.dailySheetDay(machineID, day.day)) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(RevenuePresentation.day(day.day)).font(.headline)
                            Text(AllocationPresentation.dayLine(day)).font(.subheadline.monospacedDigit()).foregroundStyle(.secondary)
                            if let unexplained = AllocationPresentation.dayUnexplained(day) {
                                Text(unexplained).font(.caption).foregroundStyle(Palette.warning)
                            }
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload(range) }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(RevenueTexts.sheetTitle)
        .refreshable { await reload(range) }
        .task(id: model.changeTick) { await reload(range) }
    }

    private func reload(_ range: (from: String, to: String)) async {
        await loader.load(model, .allocationDays(machineID: machineID, from: range.from, to: range.to),
                          OwnerAPI.allocationDays(machineID: machineID, from: range.from, to: range.to))
    }
}

/// One machine on one day, revenue checks off: only the "Hours allocated" and "Work allocations" cards.
struct LedgerDayView: View {
    let model: OwnerModel
    let machineID: UUID
    let day: String

    var body: some View {
        Form { AllocationDaySections(model: model, machineID: machineID, day: day) }
            .navigationTitle(RevenuePresentation.day(day))
    }
}

/// Labelled values (label left, value right).
private struct FieldRows: View {
    let fields: [DecisionField]

    var body: some View {
        ForEach(fields, id: \.self) { field in
            LabeledContent(field.label) { Text(field.value).multilineTextAlignment(.trailing) }
        }
    }
}
#endif
