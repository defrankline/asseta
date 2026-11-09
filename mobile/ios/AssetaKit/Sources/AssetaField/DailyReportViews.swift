#if os(iOS)
import AssetaAppShell
import AssetaCapture
import AssetaModel
import AssetaStore
import AssetaSync
import SwiftUI

private typealias T = DailyReportTexts

/// Daily report queries for the views (DEC-032; gating by ``FieldAccess``, the server enforces everything).
extension FieldModel {
    /// The tenant's zone cuts report days, wherever the phone is; the phone's zone only until the server has sent it.
    var reportTimeZone: TimeZone { accountabilityData?.reportTimeZone() ?? .current }

    var canReadDailyReports: Bool { tenant.permissions.contains("tenant.meter.read") }

    /// My reports (server copies merged with this phone's unsent ones).
    var dailyReportRows: [DailyReportRow] {
        _ = accountabilityTick
        return services?.accountability.dailyReportRows(userID: userID) ?? []
    }

    /// The signed-in user (`/me`); nil before the profile is loaded.
    private var userID: UUID? {
        if case let .ready(me) = session.phase { return me.userID }
        return nil
    }

    var dailyReportsReturned: Int { dailyReportRows.filter(\.returned).count }

    /// Re-reads my reports when online; false when they could not be read (the saved copy stays).
    @discardableResult
    func refreshDailyReports() async -> Bool {
        guard canReadDailyReports, isOnline, let online else { return false }
        let done = await online.refreshDailyReports(timeZone: reportTimeZone)
        refresh()
        return done
    }

    /// Readings of `machineID` a report can name: mine that still count.
    func reportReadings(machineID: UUID) -> [ReportReading] {
        inbox.readings.filter { $0.counts && inbox.machine(of: $0) == machineID }
            .map { ReportReading(id: $0.id, reading: $0.reading, at: $0.at, synced: $0.server != nil || $0.op?.status == .acked) }
    }

    var unbillableReasonOptions: [PickerOption] {
        (accountabilityData?.unbillableReasons ?? []).map { PickerOption(id: $0.id, title: $0.name, subtitle: $0.description) }
    }

    var engineHoursPolicy: EngineHoursPolicyValues? { accountabilityData?.engineHoursPolicy }

    private var syncsChangeoverJobs: Bool { access.capabilities?.contains(SyncCapability.changeoverJobs) == true }

    /// Customers the machine can move on to: every synced one and those of the jobs that can follow it (office-created
    /// jobs may be for customers outside my own list), never the job's current customer.
    func changeoverCustomers(_ job: FieldJob) -> [PickerOption] {
        let known = customerOptions
        let extra = syncsChangeoverJobs ? ChangeoverRules.nextCustomers(accountabilityData?.changeoverJobs ?? [], machineID: job.job.machineID, excluding: job.id)
            .filter { option in !known.contains { $0.id == option.id } }
            .map { PickerOption(id: $0.id, title: $0.name, subtitle: nil) } : []
        return (known + extra).filter { $0.id != job.customer?.id }
    }

    /// Jobs that can follow on this machine for `customerID`: the synced list, or my own jobs from an older server.
    func changeoverJobs(_ job: FieldJob, customerID: UUID?) -> [PickerOption] {
        guard let customerID else { return [] }
        if syncsChangeoverJobs {
            return ChangeoverRules.nextJobs(accountabilityData?.changeoverJobs ?? [], machineID: job.job.machineID,
                                            customerID: customerID, excluding: job.id)
                .map { PickerOption(id: $0.id, title: $0.jobNumber, subtitle: nil) }
        }
        return jobs.filter { $0.id != job.id && $0.job.machineID == job.job.machineID && $0.contract?.customerID == customerID
            && ChangeoverRules.jobOffered($0.job.status) }
            .map { PickerOption(id: $0.id, title: $0.job.jobNumber, subtitle: $0.site?.name) }
    }
}

/// "Daily reports": what was sent back to me first, then my reports (last 60 days; saved for offline reading).
struct DailyReportListView: View {
    let model: FieldModel
    @State private var offline = false

    var body: some View {
        let rows = model.dailyReportRows
        let returned = rows.filter(\.returned)
        let mine = rows.filter { !$0.returned }
        List {
            if rows.isEmpty {
                ContentUnavailableView(T.empty, systemImage: "doc.text", description: Text(T.emptyHint))
            }
            if !returned.isEmpty { Section(T.sectionReturned) { ForEach(returned) { row(for: $0) } } }
            if !mine.isEmpty {
                Section {
                    ForEach(mine) { row(for: $0) }
                } header: { Text(T.sectionMine) } footer: { if offline { Text(T.staleFooter) } }
            }
        }
        .navigationTitle(T.listTitle)
        .refreshable { offline = !(await model.refreshDailyReports()) }
        .task(id: model.isOnline) { offline = !(await model.refreshDailyReports()) }
    }

    private func row(for row: DailyReportRow) -> some View {
        NavigationLink(value: FieldRoute.dailyReport(row.id)) {
            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(title(row)).font(.headline).lineLimit(2)
                    Spacer()
                }
                if let server = row.server {
                    Text(T.rowLine(total: T.hours(server.totalHours.value), billable: T.hours(server.billableHours.value)))
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                Pill(text: row.statusText, color: DailyReportDetailView.tone(row))
            }
        }
    }

    private func title(_ row: DailyReportRow) -> String {
        let machine = row.server?.machineCode ?? row.machineID.flatMap { model.inbox.machines[$0]?.assetCode }
            ?? row.machineID.map(DisplayName.shortID) ?? ""
        return [machine, ReportDay.text(row.reportDate)].filter { !$0.isEmpty }.joined(separator: " · ")
    }
}

/// `26 Oct 2026` from a `yyyy-MM-dd` wire day.
enum ReportDay {
    static func text(_ wire: String) -> String {
        let parse = DateFormatter()
        parse.locale = Locale(identifier: "en_US_POSIX")
        parse.timeZone = TimeZone(identifier: "UTC")
        parse.dateFormat = "yyyy-MM-dd"
        guard let date = parse.date(from: wire) else { return wire }
        let out = DateFormatter()
        out.locale = Locale(identifier: "en_US_POSIX")
        out.timeZone = TimeZone(identifier: "UTC")
        out.dateFormat = "d MMM yyyy"
        return out.string(from: date)
    }
}

/// One report: status, figures, reasons, allocations, the office's note and the sync state in plain words.
struct DailyReportDetailView: View {
    let model: FieldModel
    let id: UUID
    let resubmit: (DailyReportDTO) -> Void
    @State private var fetched: DailyReportDTO?

    static func tone(_ row: DailyReportRow) -> Color {
        if let server = row.server {
            switch server.status {
            case DailyReportStatuses.returned: return Palette.warning
            case DailyReportStatuses.reviewed: return Palette.live
            default: return .secondary
            }
        }
        return row.op?.status == .failed || row.op?.status == .conflict ? Palette.offline : .secondary
    }

    var body: some View {
        let found = model.dailyReportRows.first { $0.id == id }
        let row = found ?? fetched.map { DailyReportRow(id: $0.id, server: $0, local: nil, op: nil) }
        Group {
            if let row {
                report(row)
            } else {
                ContentUnavailableView(T.notFound, systemImage: "doc.questionmark", description: Text(T.notFoundHint))
            }
        }
        .navigationTitle(T.detailTitle)
        .refreshable { await load() }
        .task(id: model.isOnline) { await load() }
    }

    private func load() async {
        if model.dailyReportRows.first(where: { $0.id == id })?.server == nil { fetched = await model.online?.dailyReport(id) }
        await model.refreshDailyReports()
    }

    private func machineName(_ row: DailyReportRow) -> String {
        row.server?.machineCode ?? row.machineID.flatMap { model.inbox.machines[$0]?.assetCode } ?? row.machineID.map(DisplayName.shortID) ?? ""
    }

    private func report(_ row: DailyReportRow) -> some View {
        let s = row.server
        return List {
            Section {
                LabeledContent(T.statusLabel) { Pill(text: row.statusText, color: Self.tone(row)) }
                LabeledContent(T.machine, value: machineName(row))
                LabeledContent(T.day, value: ReportDay.text(row.reportDate))
                if let s {
                    LabeledContent(T.openingValue, value: T.hours(s.openingReading.value))
                    LabeledContent(T.closingValue, value: T.hours(s.closingReading.value))
                    LabeledContent(T.totalHours, value: "\(T.hours(s.totalHours.value)) h")
                    LabeledContent(T.billableHours, value: "\(T.hours(s.billableHours.value)) h")
                    LabeledContent(T.unbillableHours, value: "\(T.hours(s.unbillableHours.value)) h")
                    if s.differenceHours.value != 0 { LabeledContent(T.notAccounted, value: "\(T.hours(s.differenceHours.value)) h") }
                    LabeledContent(T.submitted, value: s.submittedAt.listText)
                    if let by = DisplayName.optional(s.submittedByName, id: s.submittedBy) { LabeledContent(T.submittedBy, value: by) }
                    if s.isLate { Text(T.flagLate).font(.footnote).foregroundStyle(Palette.warning) }
                    if s.isDuplicate { Text(T.flagRepeat).font(.footnote).foregroundStyle(Palette.warning) }
                }
            }
            if let s, !s.unbillable.isEmpty {
                Section(T.unbillable) {
                    ForEach(s.unbillable, id: \.self) {
                        LabeledContent(DisplayName.or($0.reasonName, id: $0.reasonID), value: "\(T.hours($0.hours.value)) h")
                    }
                }
            }
            if let s, !s.allocations.isEmpty {
                Section(T.allocations) {
                    ForEach(s.allocations) { a in
                        LabeledContent([T.allocationKind(a.kind), DisplayName.optional(a.customerName, id: a.customerID), a.jobNumber].compactMap { $0 }.joined(separator: " · "),
                                       value: "\(T.hours(a.hours.value)) h")
                    }
                }
            }
            if let note = s?.note ?? row.local?.note, !note.isEmpty { Section(T.noteLabel) { Text(note) } }
            if let s, let note = s.reviewNote, !note.isEmpty {
                Section(T.officeNote) {
                    Text(note)
                    if let by = DisplayName.optional(s.reviewedByName, id: s.reviewedBy) {
                        LabeledContent(s.status == DailyReportStatuses.returned ? T.returnedBy : T.reviewedBy, value: by)
                    }
                }
            }
            photos(s, op: row.op)
            if s == nil, let op = row.op {
                Section(T.syncSection) {
                    LabeledContent(T.onThisPhone) { SyncStateLabel(status: op.status) }
                    if let code = op.errorCode {
                        Text(FieldAccountabilityTexts.conflictText(code) ?? "\(code): \(op.lastError ?? "")")
                            .font(.caption).foregroundStyle(Palette.offline)
                    }
                }
            }
            if row.returned, model.access.dailyReport, let s {
                Section { Button(T.resubmit, systemImage: "arrow.uturn.forward") { resubmit(s) }.accessibilityIdentifier("report.resubmit") }
            }
        }
    }

    @ViewBuilder private func photos(_ s: DailyReportDTO?, op: ClientOperation?) -> some View {
        let online = model.online
        if let ids = s?.evidenceAttachmentIDs, !ids.isEmpty {
            Section(T.photos) {
                ForEach(Array(ids.enumerated()), id: \.offset) { index, attachment in
                    EvidenceImage(description: "Daily report photo \(index + 1)", local: nil, remote: { await online?.attachmentURL(attachment) })
                }
            }
        } else if let op, case let files = model.evidenceFiles(of: op), !files.isEmpty {
            Section(T.photos) {
                ForEach(Array(files.enumerated()), id: \.offset) { index, file in
                    EvidenceImage(description: "Daily report photo \(index + 1)", local: { model.localEvidence(file) }, remote: nil)
                }
            }
        }
    }
}

/// Machine and day (fixed on a resubmission; otherwise today or the two days before), the readings, billable and
/// unbillable hours, note and photos. One report per form visit (`reportID`).
struct DailyReportFormView: View {
    let model: FieldModel
    let machineID: UUID
    let resubmitting: DailyReportDTO?
    @Environment(\.dismiss) private var dismiss
    @State private var reportID = UUID()
    @State private var day: String
    @State private var openingRef: UUID?
    @State private var closingRef: UUID?
    @State private var billable = ""
    @State private var lines: [UnbillableDraft] = []
    @State private var note = ""
    @State private var photos: [(evidence: StoredEvidence, data: Data)] = []
    @State private var prefill: DailyReportPrefillDTO?
    @State private var error: String?

    private static let maxCandidates = 30

    init(model: FieldModel, machineID: UUID, resubmitting: DailyReportDTO? = nil) {
        self.model = model
        self.machineID = machineID
        self.resubmitting = resubmitting
        _day = State(initialValue: resubmitting?.reportDate ?? DailyReportRules.localDay(Date(), timeZone: model.reportTimeZone))
        if let r = resubmitting {
            _openingRef = State(initialValue: r.openingRef)
            _closingRef = State(initialValue: r.closingRef)
            _billable = State(initialValue: AccountabilityRules.plain(r.billableHours.value))
            _lines = State(initialValue: r.unbillable.map { UnbillableDraft(reasonID: $0.reasonID, hoursText: AccountabilityRules.plain($0.hours.value)) })
            _note = State(initialValue: r.note ?? "")
        }
    }

    private var evidenceRequired: Bool { model.engineHoursPolicy?.dailyReportEvidenceRequired == true }

    /// Today and the two days before, in the tenant's zone.
    private var days: [String] { DailyReportRules.recentDays(now: Date(), timeZone: model.reportTimeZone) }

    private func bounds(_ wire: String) -> (start: Date, end: Date) {
        DailyReportRules.dayBounds(wire, timeZone: model.reportTimeZone) ?? (Date(), Date())
    }

    /// This phone's readings plus those only the server has (pre-fill, or the report being corrected), newest first.
    private var readings: [ReportReading] {
        var all = model.reportReadings(machineID: machineID)
        func add(_ id: UUID?, _ reading: DecimalString?, _ at: Date?) {
            guard let id, let reading, !all.contains(where: { $0.id == id }) else { return }
            all.append(ReportReading(id: id, reading: reading.description, at: at ?? bounds(day).start, synced: true))
        }
        add(prefill?.openingRef, prefill?.openingReading, prefill?.openingAt)
        add(prefill?.closingRef, prefill?.closingReading, prefill?.closingAt)
        add(resubmitting?.openingRef, resubmitting?.openingReading, nil)
        add(resubmitting?.closingRef, resubmitting?.closingReading, nil)
        return all.sorted { $0.at > $1.at }
    }

    /// Readings offered for the day: at most its end, newest first (bounded so the picker stays short).
    private var options: [PickerOption] {
        readings.filter { $0.at < bounds(day).end }.prefix(Self.maxCandidates).map {
            PickerOption(id: $0.id, title: $0.synced ? T.readingOption(reading: $0.reading, dateTime: $0.at.listText)
                : T.readingNotSynced(reading: $0.reading, dateTime: $0.at.listText), subtitle: nil)
        }
    }

    private func value(_ id: UUID?) -> String? { readings.first { $0.id == id }?.reading }

    private var draft: DailyReportDraft {
        var d = DailyReportDraft(machineID: machineID, reportDate: day, openingRef: openingRef, closingRef: closingRef,
                                 supersedesID: resubmitting?.id)
        d.openingReading = value(openingRef)
        d.closingReading = value(closingRef)
        d.billableText = billable
        d.unbillable = lines
        d.note = note
        return d
    }

    private var isRepeat: Bool { resubmitting == nil && prefill?.existingReportIDs.isEmpty == false }

    var body: some View {
        let total = DailyReportRules.total(opening: value(openingRef), closing: value(closingRef))
        NavigationStack {
            Form {
                Section {
                    LabeledContent(T.machine, value: model.inbox.machines[machineID].map { "\($0.assetCode) · \($0.name)" } ?? "")
                    if resubmitting != nil { LabeledContent(T.day, value: ReportDay.text(day)) }
                } footer: { if resubmitting != nil { Text(T.resubmitFooter) } }
                if resubmitting == nil {
                    FilterChips(options: days.map { ($0, ReportDay.text($0)) }, selection: $day)
                        .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                }
                if isRepeat { Text(T.repeatWarning).foregroundStyle(Palette.warning) }
                readingsSection(total)
                Section {
                    TextField(T.billable, text: $billable).keyboardType(.decimalPad).accessibilityIdentifier("report.billable")
                } header: { Text(T.billableHours) } footer: { Text(T.billableFooter) }
                unbillableSection(total)
                Section {
                    TextField(T.note, text: Binding(get: { note }, set: { note = String($0.prefix(DailyReportRules.maxNote)) }), axis: .vertical)
                        .lineLimit(2...5).accessibilityIdentifier("report.note")
                }
                EvidencePhotosSection(model: model, photos: $photos, error: $error, title: evidenceRequired ? T.photoRequired : T.photoOptional,
                                      footer: T.photoFooter, photograph: T.takePhoto, addPhoto: T.addPhoto, removeLabel: T.removePhoto)
                if let error { Text(error).foregroundStyle(Palette.offline) }
            }
            .navigationTitle(resubmitting == nil ? T.formTitle : T.resubmitTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { discard(); dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(T.send, action: send).disabled(openingRef == nil || closingRef == nil).accessibilityIdentifier("report.send")
                }
            }
            .task(id: day) { await selectDay() }
        }
        .interactiveDismissDisabled(!photos.isEmpty)
    }

    private func readingsSection(_ total: Decimal?) -> some View {
        Section {
            if options.isEmpty { Text(T.noReadings).font(.footnote).foregroundStyle(.secondary) }
            SearchablePickerField(label: T.opening, options: options, selection: $openingRef, noneTitle: T.chooseReading,
                                  emptyMessage: T.noReadings, identifier: "report.opening")
            SearchablePickerField(label: T.closing, options: options, selection: $closingRef, noneTitle: T.chooseReading,
                                  emptyMessage: T.noReadings, identifier: "report.closing")
            if let total { LabeledContent(T.total, value: "\(T.hours(total)) h") }
        } header: { Text(T.readings) } footer: { Text(T.readingsFooter) }
    }

    private func unbillableSection(_ total: Decimal?) -> some View {
        Section(T.unbillable) {
            let reasons = model.unbillableReasonOptions
            if reasons.isEmpty { Text(T.reasonsEmpty).font(.footnote).foregroundStyle(.secondary) }
            ForEach($lines) { $line in
                SearchablePickerField(label: T.reason, options: reasons, selection: $line.reasonID, noneTitle: T.chooseReason,
                                      emptyMessage: T.reasonsEmpty, identifier: "report.reason")
                TextField(T.reasonHours, text: $line.hoursText).keyboardType(.decimalPad)
                Button(T.removeReason, role: .destructive) { lines.removeAll { $0.id == line.id } }.font(.footnote)
            }
            if !reasons.isEmpty && lines.count < DailyReportRules.maxLines {
                Button(T.addReason, systemImage: "plus") { lines.append(UnbillableDraft()) }
            }
            if let left = DailyReportRules.notAccounted(total: total, billableText: billable, lines: lines), left != 0 {
                LabeledContent(T.notAccounted, value: "\(T.hours(left)) h")
            }
        }
    }

    /// The day's readings from this phone, then what the server adds (a reading the phone lacks, earlier reports).
    private func selectDay() async {
        guard resubmitting == nil else { return }
        prefill = nil
        let (start, end) = bounds(day)
        let picked = DailyReportRules.prefill(model.reportReadings(machineID: machineID), dayStart: start, dayEnd: end)
        openingRef = picked.opening
        closingRef = picked.closing
        guard model.isOnline, let online = model.online else { return }
        let asked = day
        guard let fresh = try? await online.dailyReportPrefill(machineID: machineID, day: asked), asked == day else { return }
        prefill = fresh
        openingRef = openingRef ?? fresh.openingRef
        closingRef = closingRef ?? fresh.closingRef
    }

    private func discard() {
        photos.forEach { model.discardEvidence($0.evidence) }
        photos = []
    }

    private func send() {
        do {
            try model.perform {
                try $0.recordDailyReport(draft, evidenceRequired: evidenceRequired, evidence: photos.map(\.evidence), reportID: reportID)
            }
            photos = [] // now owned by the queued report
            dismiss()
        } catch {
            self.error = JobDetailView.describe(error)
        }
    }
}
#endif
