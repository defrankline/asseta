import AssetaCapture
import AssetaModel
import AssetaNetwork
import AssetaStore
import Foundation

// DEC-032 Phase 1 in the Supervisor app: the machine's daily operational report (`DAILY_REPORT`, queued offline, with
// evidence photos) and the mid-job changeover reading (`METER_CAPTURE` kind DAILY on the running job). The report's
// figures come from the server's pre-fill (`GET /daily-reports/prefill`); the server re-validates everything.

/// A reading a report can name; `synced` false: the server does not have it yet (the report waits for it).
public struct ReportReading: Sendable, Equatable, Identifiable {
    public let id: UUID
    public let reading: String
    public let at: Date
    public let synced: Bool

    public init(id: UUID, reading: String, at: Date, synced: Bool) {
        self.id = id
        self.reading = reading
        self.at = at
        self.synced = synced
    }
}

/// Checks of the daily report form (same rules and order as Android `DailyReportRules`; the server re-validates).
public enum DailyReportRules {
    public static let maxEvidence = 10
    public static let maxNote = 2000
    public static let maxLines = 20
    static let hoursDecimals = 2

    /// The values the report is sent with.
    public struct Values: Sendable, Equatable {
        public let billable: Decimal?
        public let unbillable: [UnbillableLineIn]
        public let note: String?
    }

    /// Opening and closing as the server pre-fills them: the day's first when it has two or more, else the latest
    /// reading before the day; the closing is the day's last.
    public static func prefill(_ readings: [ReportReading], dayStart: Date, dayEnd: Date) -> (opening: UUID?, closing: UUID?) {
        let day = readings.filter { $0.at >= dayStart && $0.at < dayEnd }.sorted { $0.at < $1.at }
        let opening = day.count > 1 ? day.first : readings.filter { $0.at < dayStart }.max { $0.at < $1.at }
        return (opening?.id, day.last?.id)
    }

    /// Hours between the readings; nil when unknown or going backwards (an approved meter reset is for the server).
    public static func total(opening: String?, closing: String?) -> Decimal? {
        guard let from = opening.flatMap(number), let to = closing.flatMap(number), to >= from else { return nil }
        return to - from
    }

    static func number(_ text: String) -> Decimal? { Decimal(string: text, locale: Locale(identifier: "en_US_POSIX")) }

    static func hours(_ text: String, allowZero: Bool) -> Decimal? {
        AccountabilityRules.value(text, decimals: hoursDecimals, allowZero: allowZero)
    }

    static func blank(_ text: String) -> Bool { text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }

    /// Total minus billable and unbillable hours, for display; nil while it cannot be worked out. An empty billable
    /// field means the total minus the unbillable hours.
    public static func notAccounted(total: Decimal?, billableText: String, lines: [UnbillableDraft]) -> Decimal? {
        guard let total else { return nil }
        let unbillable = lines.reduce(Decimal(0)) { $0 + (hours($1.hoursText, allowZero: false) ?? 0) }
        let billable: Decimal
        if blank(billableText) {
            billable = max(total - unbillable, 0)
        } else {
            guard let typed = hours(billableText, allowZero: true) else { return nil }
            billable = typed
        }
        return total - billable - unbillable
    }

    /// Every problem of the form, or the values to send.
    public static func check(_ d: DailyReportDraft, photos: Int, evidenceRequired: Bool) -> AccountabilityRules.Check<Values> {
        typealias T = DailyReportTexts
        var m: [String] = []
        if d.openingRef == nil { m.append(T.errOpening) }
        if d.closingRef == nil { m.append(T.errClosing) }
        if let opening = d.openingRef, opening == d.closingRef { m.append(T.errSameReading) }
        var billable: Decimal?
        if !blank(d.billableText) {
            billable = hours(d.billableText, allowZero: true)
            if billable == nil { m.append(T.errBillable) }
        }
        let lines = d.unbillable.filter { !($0.reasonID == nil && blank($0.hoursText)) }
        if lines.contains(where: { $0.reasonID == nil }) { m.append(T.errReasonMissing) }
        if lines.contains(where: { hours($0.hoursText, allowZero: false) == nil }) { m.append(T.errReasonHours) }
        let ids = lines.compactMap(\.reasonID)
        if Set(ids).count != ids.count { m.append(T.errReasonRepeated) }
        if evidenceRequired && photos == 0 { m.append(T.errPhoto) }
        if m.isEmpty, let total = total(opening: d.openingReading, closing: d.closingReading) {
            let claimed = lines.reduce(billable ?? 0) { $0 + (hours($1.hoursText, allowZero: false) ?? 0) }
            if claimed > total { m.append(T.errExceeds(AccountabilityRules.plain(total))) }
        }
        guard m.isEmpty else { return .failure(AccountabilityRules.Problems(messages: m)) }
        let sent = lines.compactMap { line -> UnbillableLineIn? in
            guard let reason = line.reasonID, let value = hours(line.hoursText, allowZero: false) else { return nil }
            return UnbillableLineIn(reasonID: reason, hours: value)
        }
        return .success(Values(billable: billable, unbillable: sent, note: AccountabilityRules.trimmed(d.note, max: maxNote)))
    }

    /// Active UNBILLABLE_REASON reasons by name.
    public static func pickable(_ reasons: [EngineHourReasonDTO]) -> [EngineHourReasonDTO] {
        reasons.filter { $0.isActive && $0.kind == EngineHourReasonKinds.unbillable }
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    /// Only a RETURNED report can be sent again (the new report supersedes it).
    public static func canResubmit(_ report: DailyReportDTO) -> Bool { report.status == DailyReportStatuses.returned }

    /// The day `yyyy-MM-dd` of `date` in `timeZone` (the tenant's: the server cuts report days in it).
    public static func localDay(_ date: Date, timeZone: TimeZone = .current) -> String { CashToday.localDay(date, timeZone: timeZone) }

    /// Today and the two days before, in `timeZone`, newest first.
    public static func recentDays(now: Date, timeZone: TimeZone) -> [String] {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        return (0...2).compactMap { calendar.date(byAdding: .day, value: -$0, to: now) }.map { localDay($0, timeZone: timeZone) }
    }

    /// Start (inclusive) and end (exclusive) of the wire day `yyyy-MM-dd` in `timeZone`; nil when it is not a day.
    public static func dayBounds(_ day: String, timeZone: TimeZone) -> (start: Date, end: Date)? {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.calendar = Calendar(identifier: .gregorian)
        f.timeZone = timeZone
        f.dateFormat = "yyyy-MM-dd"
        guard let parsed = f.date(from: day) else { return nil }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        let start = calendar.startOfDay(for: parsed)
        guard let end = calendar.date(byAdding: .day, value: 1, to: start) else { return nil }
        return (start, end)
    }
}

/// The zone that decides which day a reading belongs to: the tenant's, as the server counts days (Android `TenantZone`).
public enum TenantZone {
    /// The first valid zone id of `known` (best source first), else `device`.
    public static func resolve(_ known: [String?], device: TimeZone) -> TimeZone {
        known.lazy.compactMap { $0.flatMap(TimeZone.init(identifier:)) }.first ?? device
    }
}

/// Why a changeover cannot be saved (as Android `ChangeoverRules`).
public enum ChangeoverRules {
    /// Which jobs can follow: one the hours are billed to must still be waiting for approval (else the server answers
    /// `CHANGEOVER_JOB_INVALID`); an optional one, kept for the record, may also be approved.
    public static func jobOffered(_ status: JobStatus, jobRequired: Bool) -> Bool {
        status == .pendingApproval || (!jobRequired && status == .approved)
    }

    public static func problem(customerID: UUID?, jobID: UUID?, jobRequired: Bool) -> String? {
        if customerID == nil { return DailyReportTexts.changeoverErrorCustomer }
        if jobRequired && jobID == nil { return DailyReportTexts.changeoverErrorJob }
        return nil
    }
}

/// `EngineHourReasonKind` values the apps ask for.
public enum EngineHourReasonKinds {
    public static let unbillable = "UNBILLABLE_REASON"
}

/// One unbillable line as typed.
public struct UnbillableDraft: Sendable, Equatable, Identifiable {
    public let id: UUID
    public var reasonID: UUID?
    public var hoursText: String

    public init(id: UUID = UUID(), reasonID: UUID? = nil, hoursText: String = "") {
        self.id = id
        self.reasonID = reasonID
        self.hoursText = hoursText
    }
}

/// The daily report form as typed.
public struct DailyReportDraft: Sendable, Equatable {
    public var machineID: UUID
    public var reportDate: String
    public var openingRef: UUID?
    public var closingRef: UUID?
    /// The chosen readings' values: they give the hours between the readings.
    public var openingReading: String?
    public var closingReading: String?
    public var billableText = ""
    public var unbillable: [UnbillableDraft] = []
    public var note = ""
    public var supersedesID: UUID?

    public init(machineID: UUID, reportDate: String, openingRef: UUID? = nil, closingRef: UUID? = nil, supersedesID: UUID? = nil) {
        self.machineID = machineID
        self.reportDate = reportDate
        self.openingRef = openingRef
        self.closingRef = closingRef
        self.supersedesID = supersedesID
    }
}

extension FieldAccess {
    /// "Daily report": the server takes `DAILY_REPORT`, the user records readings, engine-hour controls are on.
    public var dailyReport: Bool { supports(SyncCapability.dailyReport) && can(Self.meterCapture) && engineHoursOn }
    /// "Record a changeover" on a running job (`METER_CHANGEOVER`).
    public var changeover: Bool { supports(SyncCapability.meterChangeover) && can(Self.meterCapture) && engineHoursOn }
}

extension FieldRecorder {
    /// Queues a `DAILY_REPORT` once per form visit (the operation id is the report id). It waits for every photo upload
    /// (purpose DAILY_REPORT_EVIDENCE) and for the operations of any chosen reading the server does not have yet.
    @discardableResult
    public func recordDailyReport(_ draft: DailyReportDraft, evidenceRequired: Bool, evidence: [StoredEvidence],
                                  at date: Date = Date(), reportID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.dailyReport)
        let values: DailyReportRules.Values
        switch DailyReportRules.check(draft, photos: evidence.count, evidenceRequired: evidenceRequired) {
        case let .failure(problems): throw Self.invalid(problems)
        case let .success(checked): values = checked
        }
        guard let opening = draft.openingRef, let closing = draft.closingRef else { throw FieldRecorderError.invalid(DailyReportTexts.errOpening) }
        guard try store.syncState.entity(type: "machine", id: draft.machineID, tenantID: tenantID) != nil else {
            throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.machineMissing)
        }
        if try alreadySaved(.dailyReport, clientID: reportID) { throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved) }
        let all = try store.outbox.operations(tenantID: tenantID, owner: owner?.subject, statuses: Set(ClientOperationStatus.allCases))
        let parents = all.filter { $0.opType == OperationType.meterCapture.rawValue && ($0.entityID == opening || $0.entityID == closing) }
        if parents.contains(where: { $0.status == .failed || $0.status == .conflict }) {
            throw FieldRecorderError.notAllowed(DailyReportTexts.readingNotAccepted)
        }
        return try store.database.transaction {
            let locals = try evidence.prefix(DailyReportRules.maxEvidence).map { try addAttachment($0, purpose: .dailyReportEvidence) }
            let payload = DailyReportPayload(
                machineID: draft.machineID, reportDate: draft.reportDate, openingRef: opening, closingRef: closing,
                billableHours: values.billable, unbillable: values.unbillable, note: values.note, supersedesID: draft.supersedesID,
                clientCreatedAt: date)
            return try enqueue(.dailyReport, entityType: "daily_report", entityID: reportID, payload: payload,
                               dependsOn: parents.filter { $0.status != .acked }.map(\.id),
                               attachments: locals.map { ($0, .evidenceUploads) }, createdAt: date, operationID: reportID)
        }
    }

    /// Queues a mid-job changeover: a DAILY reading on the running job (`machine_id` null) with the customer the machine
    /// moves to. The job keeps running; it waits for this phone's START when that is still unsent.
    @discardableResult
    public func recordChangeover(job: JobDTO, toCustomerID: UUID?, toJobID: UUID?, jobRequired: Bool, mode: CaptureMode,
                                 reading: String, ocr: MeterOCRResult?, photo: StoredEvidence?, gps: GpsPayload,
                                 capturedAt: Date, snapshot: MeterPolicySnapshot, captureID: UUID = UUID()) throws -> ClientOperation {
        try requireCapability(SyncCapability.meterChangeover)
        let progress = try progress(jobID: job.id, serverStatus: job.status)
        guard progress.displayStatus == .inProgress else { throw FieldRecorderError.notAllowed(DailyReportTexts.changeoverNotRunning) }
        if let problem = ChangeoverRules.problem(customerID: toCustomerID, jobID: toJobID, jobRequired: jobRequired) {
            throw FieldRecorderError.notAllowed(problem)
        }
        guard let toCustomerID else { throw FieldRecorderError.notAllowed(DailyReportTexts.changeoverErrorCustomer) }
        if try alreadySaved(.meterCapture, clientID: captureID) { throw FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved) }
        return try store.database.transaction {
            let photoLocal = try photo.map { try addAttachment($0, purpose: .meterPhoto) }
            let payload = capturePayload(id: captureID, jobID: job.id, machineID: nil, kind: .daily, mode: mode, reading: reading,
                                         ocr: ocr, gps: gps, capturedAt: capturedAt, snapshot: snapshot)
                .withChangeover(customerID: toCustomerID, jobID: toJobID)
            return try enqueue(.meterCapture, entityType: "meter_capture", entityID: captureID, payload: payload,
                               dependsOn: [progress.startOp].compactMap { $0 }, attachments: photoLocal.map { [($0, .photo)] } ?? [],
                               createdAt: capturedAt)
        }
    }
}

/// A daily report as the field app shows it: the server's copy and/or this phone's unsent one (`id` is the report id).
public struct DailyReportRow: Sendable, Equatable, Identifiable {
    public static let days = 60

    public let id: UUID
    public let server: DailyReportDTO?
    public let local: DailyReportPayload?
    public let op: ClientOperation?

    public init(id: UUID, server: DailyReportDTO?, local: DailyReportPayload?, op: ClientOperation?) {
        self.id = id
        self.server = server
        self.local = local
        self.op = op
    }

    public var machineID: UUID? { server?.machineID ?? local?.machineID }
    public var reportDate: String { server?.reportDate ?? local?.reportDate ?? "" }
    public var returned: Bool { server?.status == DailyReportStatuses.returned }

    /// The status line: the server's status, else the sync state (waiting / not accepted).
    public var statusText: String {
        if let server { return DailyReportTexts.status(server.status) }
        return op?.status == .failed || op?.status == .conflict ? DailyReportTexts.statusNotAccepted : DailyReportTexts.statusWaiting
    }

    /// Server copies win (the operation id is the report id); unsent operations are added; newest day first.
    public static func merge(server: [DailyReportDTO], ops: [ClientOperation]) -> [DailyReportRow] {
        let byID = Dictionary(ops.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        let known = Set(server.map(\.id))
        let local = ops.filter { !known.contains($0.id) }.compactMap { op -> DailyReportRow? in
            guard let payload = try? JSONValue.parse(op.payloadJSON).decode(as: DailyReportPayload.self) else { return nil }
            return DailyReportRow(id: op.id, server: nil, local: payload, op: op)
        }
        return (server.map { DailyReportRow(id: $0.id, server: $0, local: nil, op: byID[$0.id]) } + local)
            .sorted { $0.reportDate > $1.reportDate }
    }
}

extension MeterCapturePayload {
    /// The same reading marked as a changeover to `customerID`.
    func withChangeover(customerID: UUID, jobID: UUID?) -> MeterCapturePayload {
        MeterCapturePayload(id: id, jobID: self.jobID, machineID: machineID, kind: kind, captureMode: captureMode, reading: reading,
                            ocrRawText: ocrRawText, ocrValue: ocrValue, ocrConfidence: ocrConfidence, ocrEngine: ocrEngine,
                            photoAttachmentID: photoAttachmentID, gps: gps, deviceID: deviceID, capturedAt: capturedAt,
                            policyVersionIDs: policyVersionIDs, changeoverToCustomerID: customerID, changeoverToJobID: jobID)
    }
}

extension SupervisorOnline {
    /// What the server already knows of the machine-day (`GET /daily-reports/prefill`).
    public func dailyReportPrefill(machineID: UUID, day: String) async throws -> DailyReportPrefillDTO {
        try await client.send(APIRequest<DailyReportPrefillDTO>.get(
            "\(Self.tenant)/daily-reports/prefill",
            query: [URLQueryItem(name: "machine_id", value: machineID.lowercased), URLQueryItem(name: "report_date", value: day)]))
    }

    /// Refreshes my daily reports of the last 60 days and saves them; false when the server could not be read.
    @discardableResult
    public func refreshDailyReports(timeZone: TimeZone = .current) async -> Bool {
        let from = now().addingTimeInterval(-Double(DailyReportRow.days) * 86_400)
        do {
            let page = try await client.send(APIRequest<Page<DailyReportDTO>>.get(
                "\(Self.tenant)/daily-reports",
                query: Self.page(200) + [URLQueryItem(name: "from", value: DailyReportRules.localDay(from, timeZone: timeZone))]))
            try SavedOnline.write(SavedOnline(value: page.items, forbidden: false, fetchedAt: now()), store, tenantID, AccountabilityKey.dailyReports)
            return true
        } catch {
            return false
        }
    }

    /// One report: the saved copy, else read online and saved (a notification); nil offline or refused.
    public func dailyReport(_ id: UUID) async -> DailyReportDTO? {
        let saved = SavedOnline<[DailyReportDTO]>.read(store, tenantID, AccountabilityKey.dailyReports)
        if let found = saved?.value?.first(where: { $0.id == id }) { return found }
        guard let dto = try? await client.send(APIRequest<DailyReportDTO>.get("\(Self.tenant)/daily-reports/\(id.lowercased)")) else { return nil }
        try? SavedOnline.write(SavedOnline(value: (saved?.value ?? []) + [dto], forbidden: false, fetchedAt: saved?.fetchedAt ?? now()),
                               store, tenantID, AccountabilityKey.dailyReports)
        return dto
    }

    /// Active unbillable reasons (online; saved for the offline form by ``refreshAccountability``).
    public func unbillableReasons() async throws -> [EngineHourReasonDTO] {
        DailyReportRules.pickable(try await client.send(APIRequest<Page<EngineHourReasonDTO>>.get(
            "\(Self.tenant)/engine-hour-reasons",
            query: Self.page(200) + [URLQueryItem(name: "kind", value: EngineHourReasonKinds.unbillable)])).items)
    }
}

extension AccountabilityDirectory {
    /// The unbillable reasons saved on this phone (for the offline form).
    public var unbillableReasons: [EngineHourReasonDTO] {
        DailyReportRules.pickable(SavedOnline<[EngineHourReasonDTO]>.read(store, tenantID, AccountabilityKey.unbillableReasons)?.value ?? [])
    }

    /// My daily reports: the server's copies (last online read, the ones I sent) merged with this phone's unsent ones.
    public func dailyReportRows(userID: UUID?) -> [DailyReportRow] {
        let saved = SavedOnline<[DailyReportDTO]>.read(store, tenantID, AccountabilityKey.dailyReports)?.value ?? []
        let mine = saved.filter { userID == nil || $0.submittedBy == nil || $0.submittedBy == userID }
        let ops = ((try? store.outbox.operations(tenantID: tenantID, owner: owner?.subject,
                                                 statuses: Set(ClientOperationStatus.allCases))) ?? [])
            .filter { $0.opType == OperationType.dailyReport.rawValue }
        return DailyReportRow.merge(server: mine, ops: ops)
    }

    public var dailyReportsFetchedAt: Date? {
        SavedOnline<[DailyReportDTO]>.read(store, tenantID, AccountabilityKey.dailyReports)?.fetchedAt
    }

    /// The zone id sync announced (`tenant_timezone`, kept when a pull omits it); nil from an older server.
    public var syncedTenantTimezone: String? {
        (try? store.syncState.value(SyncKey.tenantTimezone, tenant: tenantID.uuidString.lowercased())) ?? nil
    }

    /// The zone that cuts report days: sync's, else the saved cash reconciliation's, else the saved check-ins', else `device`.
    public func reportTimeZone(device: TimeZone = .current) -> TimeZone {
        let text = try? store.syncState.value(SyncKey.cashToday, tenant: tenantID.uuidString.lowercased())
        let cash = text.flatMap { $0 }.flatMap { try? AssetaJSON.decoder().decode(CashTodaySnapshot.self, from: Data($0.utf8)) }
        return TenantZone.resolve([syncedTenantTimezone, cash?.rows.first?.timezone, siteCheckins?.value?.timezone], device: device)
    }

    /// The saved ENGINE_HOURS policy (nil when never read or refused: treated as "no photo required", the server re-checks).
    public var engineHoursPolicy: EngineHoursPolicyValues? {
        SavedOnline<EngineHoursPolicyValues>.read(store, tenantID, AccountabilityKey.engineHoursPolicy)?.value
    }
}
