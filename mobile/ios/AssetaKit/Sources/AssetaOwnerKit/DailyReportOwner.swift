import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

// DEC-032 Phase 1 in the Owner app (strings doc "DEC-032 Phase 1"): daily reports to review, work allocation corrections
// to decide (generic decision screen, `DecisionKind.allocationCorrection`), a machine day's allocations and value at risk.
// Actions are online only; reads may come from the encrypted snapshot cache like every Owner screen.

/// Wording copied exactly from `docs/requirements/accountability-mobile-strings.md` (Android `DailyReportOwnerTexts`).
public enum DailyReportOwnerTexts {
    public static let section = "Daily reports to review" // owner.report.section
    public static let empty = "No daily reports waiting." // owner.report.empty
    public static let title = "Daily report" // owner.report.title
    public static func rowHeadline(machine: String, date: String) -> String { "\(machine) · \(date)" } // owner.report.rowHeadline
    public static func rowLine(total: String, billable: String, unbillable: String) -> String { // owner.report.rowLine
        "\(total) h in total · \(billable) h billable · \(unbillable) h unbillable"
    }
    public static let figures = "Figures"
    public static let machine = "Machine"
    public static let day = "Day"
    public static let opening = "Opening reading"
    public static let closing = "Closing reading"
    public static let total = "Total hours"
    public static let billable = "Billable hours"
    public static let unbillable = "Unbillable hours"
    public static let notAccounted = "Not accounted for"
    public static let reasons = "Unbillable hours by reason"
    public static let allocations = "Hours by customer"
    public static let note = "Supervisor's note"
    public static let submittedBy = "Sent by"
    public static let submitted = "Sent"
    public static let flagLate = "Sent after the daily cut-off"
    public static let flagRepeat = "Repeat report for this day"
    public static let replaces = "Replaces an earlier report"
    public static let evidence = "Evidence"
    public static let review = "Review"
    public static let reviewFooter = "Someone other than the sender reviews a report. Sending it back asks the sender to correct it."
    public static let noteLabel = "Note (at least 5 characters)"
    public static let markReviewed = "Mark as reviewed"
    public static let sendBack = "Send back"
    public static let reviewed = "Marked as reviewed."
    public static let sentBack = "Sent back to the supervisor."
    public static let own = "You sent this report, so someone else must review it."
    public static let reviewedBy = "Reviewed by"
    public static let reviewNote = "Review note"

    /// owner.report.status.* (unknown → humanized wire value).
    public static func status(_ wire: String) -> String {
        switch wire {
        case DailyReportStatuses.submitted: "To review"
        case DailyReportStatuses.reviewed: "Reviewed"
        case DailyReportStatuses.returned: "Sent back"
        case DailyReportStatuses.superseded: "Replaced"
        default: OwnerFormat.humanize(wire)
        }
    }

    public static let errAlreadyReviewed = "This report was already reviewed or replaced. Reload to see it." // owner.report.error.REPORT_ALREADY_REVIEWED

    // Work allocations
    public static let allocationSection = "Work allocation corrections" // owner.allocation.section
    public static let allocationEmpty = "No corrections waiting." // owner.allocation.empty
    public static let allocationTitle = "Work allocation correction" // owner.allocation.title
    public static func allocationRow(machine: String, date: String, hours: String) -> String { "\(machine) · \(date) · \(hours) h" } // owner.allocation.rowHeadline
    public static let allocationOriginal = "Now recorded as" // owner.allocation.original
    public static func allocationPart(_ kind: String) -> String { "Proposed: \(kind)" } // owner.allocation.part
    public static func allocationPartValue(hours: String, who: String) -> String { // owner.allocation.partValue
        who.isEmpty ? "\(hours) h" : "\(hours) h · \(who)"
    }
    public static let errNotActive = "The original entry has changed. Reload to see it." // owner.allocation.error.ALLOCATION_NOT_ACTIVE
    public static let errPending = "Another correction of this entry is already waiting." // owner.allocation.error.ALLOCATION_CORRECTION_PENDING

    /// owner.allocation.kind.* (unknown → humanized wire value).
    public static func kind(_ wire: String) -> String {
        switch wire {
        case AllocationKinds.customerWork: "Customer work"
        case AllocationKinds.authorizedActivity: "Authorized activity"
        case AllocationKinds.unexplained: "Unexplained"
        default: OwnerFormat.humanize(wire)
        }
    }

    public static let dayCard = "Hours allocated"
    public static let dayTotal = "Engine hours"
    public static let dayCustomer = "Customer work"
    public static let dayAuthorized = "Authorized activity"
    public static let dayUnexplained = "Unexplained"
    public static let dayAllocated = "Allocated"
    public static let dayDifference = "Difference"
    public static let dayReconciled = "Every engine hour is allocated."
    public static let dayNotReconciled = "Some engine hours are not allocated yet."
    public static let entries = "Work allocations"
    public static let daysEmpty = "No engine hours in the last 14 days." // owner.allocation.daysEmpty
    public static func dayLine(engine: String, allocated: String) -> String { "\(engine) h engine · \(allocated) h allocated" } // owner.allocation.dayLine
    public static func dayUnexplained(_ hours: String) -> String { "\(hours) h unexplained" } // owner.allocation.dayUnexplainedLine
    public static let entriesEmpty = "No allocations for this day."
    public static func entryLine(start: String, end: String, hours: String) -> String { "\(start) → \(end) · \(hours) h" } // owner.allocation.entryLine
    public static func lotLine(purchase: String, hours: String) -> String { "From \(purchase): \(hours) h" } // owner.allocation.lotLine
    public static let proposedPill = "Waiting for approval"
    public static let valueAtRisk = "Value at risk" // owner.valueAtRisk
    public static let valueAtRiskFooter = "Unexplained hours at the job's rate. Not part of expected revenue or the shortfall." // owner.valueAtRiskFooter
}

/// Review rules of a daily report (as Android `DailyReportRules` in the Owner app; the server re-checks).
public enum DailyReportReview {
    public static let noteMin = 5, noteMax = 2000
    public static let reviewed = "REVIEWED", returned = "RETURNED"

    public static func noteOK(_ note: String) -> Bool {
        let n = note.trimmingCharacters(in: .whitespacesAndNewlines).count
        return n >= noteMin && n <= noteMax
    }

    /// The signed-in user sent it: someone else must review it (the server refuses it too).
    public static func isOwn(_ report: DailyReportDTO, userID: UUID?) -> Bool { userID != nil && report.submittedBy == userID }

    public static func needsReload(_ error: any Error) -> Bool { (error as? APIError)?.code == "REPORT_ALREADY_REVIEWED" }

    public static func message(for error: any Error) -> String {
        switch (error as? APIError)?.code {
        case "REPORT_ALREADY_REVIEWED": DailyReportOwnerTexts.errAlreadyReviewed
        case "SEGREGATION_OF_DUTIES": DailyReportOwnerTexts.own
        default: DecisionErrorText.message(for: error)
        }
    }
}

/// Rows of the daily report and allocation screens.
public enum AllocationPresentation {
    typealias T = DailyReportOwnerTexts

    public static func machine(_ r: DailyReportDTO) -> String { DisplayName.machine(code: r.machineCode, name: r.machineName, id: r.machineID) }

    public static func rowHeadline(_ r: DailyReportDTO) -> String {
        T.rowHeadline(machine: r.machineCode ?? r.machineName ?? DisplayName.shortID(r.machineID), date: RevenuePresentation.day(r.reportDate))
    }

    public static func rowLine(_ r: DailyReportDTO) -> String {
        T.rowLine(total: OwnerFormat.hoursNumber(r.totalHours), billable: OwnerFormat.hoursNumber(r.billableHours),
                  unbillable: OwnerFormat.hoursNumber(r.unbillableHours))
    }

    public static func figures(_ r: DailyReportDTO, timeZone: TimeZone = .current) -> [DecisionField] {
        var rows: [(String, String?)] = [
            (T.machine, machine(r)), (T.day, RevenuePresentation.day(r.reportDate)),
            (T.opening, OwnerFormat.hoursNumber(r.openingReading)), (T.closing, OwnerFormat.hoursNumber(r.closingReading)),
            (T.total, OwnerFormat.hours(r.totalHours)), (T.billable, OwnerFormat.hours(r.billableHours)),
            (T.unbillable, OwnerFormat.hours(r.unbillableHours)),
        ]
        if r.differenceHours.value != 0 { rows.append((T.notAccounted, OwnerFormat.hours(r.differenceHours))) }
        rows += [(T.submittedBy, DisplayName.optional(r.submittedByName, id: r.submittedBy)),
                 (T.submitted, OwnerFormat.stamp(r.submittedAt, timeZone: timeZone))]
        return PendingDecision.fields(rows)
    }

    public static func flags(_ r: DailyReportDTO) -> [String] {
        (r.isLate ? [T.flagLate] : []) + (r.isDuplicate ? [T.flagRepeat] : []) + (r.supersedesID != nil ? [T.replaces] : [])
    }

    public static func reasons(_ r: DailyReportDTO) -> [DecisionField] {
        r.unbillable.map { DecisionField(label: DisplayName.or($0.reasonName, id: $0.reasonID), value: OwnerFormat.hours($0.hours)) }
    }

    public static func reviewFields(_ r: DailyReportDTO) -> [DecisionField] {
        PendingDecision.fields([(T.reviewedBy, DisplayName.optional(r.reviewedByName, id: r.reviewedBy)), (T.reviewNote, r.reviewNote)])
    }

    /// Who an allocation served: customer · job, the reason or activity of authorized work, nothing when unexplained.
    public static func who(kind: String, customer: String?, job: String?, reason: String?, activity: String?) -> String {
        switch kind {
        case AllocationKinds.customerWork: [customer, job].compactMap { $0 }.joined(separator: " · ")
        case AllocationKinds.authorizedActivity: reason ?? activity.map(OwnerFormat.humanize) ?? ""
        default: ""
        }
    }

    public static func who(_ a: WorkAllocationDTO) -> String {
        who(kind: a.kind, customer: DisplayName.optional(a.customerName, id: a.customerID), job: a.jobNumber, reason: a.reasonName, activity: a.activityType)
    }

    /// One row per report allocation: kind, then "{hours} h · {who}".
    public static func allocations(_ r: DailyReportDTO) -> [DecisionField] {
        r.allocations.map {
            DecisionField(label: T.kind($0.kind), value: T.allocationPartValue(
                hours: OwnerFormat.hoursNumber($0.hours),
                who: who(kind: $0.kind, customer: DisplayName.optional($0.customerName, id: $0.customerID), job: $0.jobNumber, reason: nil, activity: $0.activityType)))
        }
    }

    public static func entryLine(_ a: WorkAllocationDTO) -> String {
        T.entryLine(start: OwnerFormat.hoursNumber(a.startReading), end: OwnerFormat.hoursNumber(a.endReading), hours: OwnerFormat.hoursNumber(a.hours))
    }

    /// "Customer work · 3 h · Acme": the entry a correction would replace.
    public static func originalLine(_ a: WorkAllocationDTO) -> String {
        "\(T.kind(a.kind)) · \(T.allocationPartValue(hours: OwnerFormat.hoursNumber(a.hours), who: who(a)))"
    }

    /// One row of the machine's allocated days.
    public static func dayLine(_ d: AllocationDayDTO) -> String {
        T.dayLine(engine: OwnerFormat.hoursNumber(d.totalEngineHours), allocated: OwnerFormat.hoursNumber(d.allocatedHours))
    }

    /// "1.5 h unexplained" when the day has unexplained hours.
    public static func dayUnexplained(_ d: AllocationDayDTO) -> String? {
        d.unexplainedHours.value == 0 ? nil : T.dayUnexplained(OwnerFormat.hoursNumber(d.unexplainedHours))
    }

    public static func lots(_ a: WorkAllocationDTO) -> [String] {
        a.lots.map { T.lotLine(purchase: DisplayName.or($0.purchaseNumber, id: $0.purchaseID), hours: OwnerFormat.hoursNumber($0.hours)) }
    }

    public static func dayFields(_ d: AllocationDayDTO) -> [DecisionField] {
        [DecisionField(label: T.dayTotal, value: OwnerFormat.hours(d.totalEngineHours)),
         DecisionField(label: T.dayCustomer, value: OwnerFormat.hours(d.customerHours)),
         DecisionField(label: T.dayAuthorized, value: OwnerFormat.hours(d.authorizedHours)),
         DecisionField(label: T.dayUnexplained, value: OwnerFormat.hours(d.unexplainedHours)),
         DecisionField(label: T.dayAllocated, value: OwnerFormat.hours(d.allocatedHours)),
         DecisionField(label: T.dayDifference, value: OwnerFormat.hours(d.differenceHours))]
    }

    /// `value_at_risk` of a dashboard tile: one row per currency (nothing when empty; never added to another figure).
    public static func valueAtRiskRows(_ tile: JSONValue?) -> [DashboardTile.Row] {
        guard case let .array(items)? = tile?["value_at_risk"] else { return [] }
        return items.compactMap { item in
            guard let currency = item["currency"]?.stringValue,
                  let amount = item["amount"]?.stringValue.flatMap({ DecimalString(string: $0) }) else { return nil }
            return .init(T.valueAtRisk, OwnerFormat.money(amount, currency: currency))
        }
    }

    /// The correction groups waiting, one row per group (`GET /work-allocations?status=PROPOSED`).
    static func groups(_ page: Page<JSONValue>) -> [PendingDecision] {
        let entries = page.items.compactMap { try? $0.decode(as: WorkAllocationDTO.self) }
        var order: [UUID] = []
        var byGroup: [UUID: [WorkAllocationDTO]] = [:]
        for entry in entries {
            guard let group = entry.correctionGroupID else { continue }
            if byGroup[group] == nil { order.append(group) }
            byGroup[group, default: []].append(entry)
        }
        return order.compactMap { decision(group: $0, status: AllocationStatuses.proposed, entries: byGroup[$0] ?? []) }
    }

    /// One correction group as a decision.
    static func decision(group: UUID, status: String, entries: [WorkAllocationDTO], timeZone: TimeZone = .current) -> PendingDecision? {
        guard let first = entries.first else { return nil }
        let hours = DecimalString(entries.reduce(Decimal(0)) { $0 + $1.hours.value })
        let code = first.machineCode ?? first.machineName ?? DisplayName.shortID(first.machineID)
        let day = RevenuePresentation.day(first.workDate)
        typealias O = OwnerAccountabilityTexts
        var rows: [(String, String?)] = [(O.fieldMachine, DisplayName.machine(code: first.machineCode, name: first.machineName, id: first.machineID))]
        rows += entries.map { (T.allocationPart(T.kind($0.kind)), T.allocationPartValue(hours: OwnerFormat.hoursNumber($0.hours), who: who($0))) }
        let proposer = DisplayName.optional(first.recordedByName, id: first.recordedBy)
        rows.append((O.fieldProposedBy, proposer))
        rows += [(O.fieldDecidedBy, DisplayName.optional(first.decidedByName, id: first.decidedBy)), (O.fieldDecisionNote, first.decisionNote)]
        return PendingDecision(kind: .allocationCorrection, recordID: group,
                               headline: T.allocationRow(machine: code, date: day, hours: OwnerFormat.hoursNumber(hours)),
                               status: status, proposedBy: first.recordedBy, proposedByName: proposer, proposedAt: first.createdAt,
                               reason: first.correctionReason, fields: PendingDecision.fields(rows), machineID: first.machineID,
                               photoAttachmentID: nil)
    }
}

extension OwnerFeatures {
    /// Daily reports, allocations and corrections are readable (`tenant.meter.read`, ENGINE_HOURS on).
    public var allocationsRead: Bool { engineHours && meterEvidence }
    /// Mark a daily report as reviewed or send it back (`tenant.meter.review`).
    public var reviewDailyReports: Bool { allocationsRead && reviewExceptions }
    /// Machine days are open to this role: with money (revenue checks) or the allocations alone.
    public var machineDays: Bool { revenueRead || allocationsRead }
}

extension SnapshotKey {
    public static func dailyReports(status: String) -> SnapshotKey { SnapshotKey("allocation.reports.\(status)") }
    public static func dailyReport(_ id: UUID) -> SnapshotKey { SnapshotKey("allocation.report.\(id.lowercased)") }
    public static func workAllocation(_ id: UUID) -> SnapshotKey { SnapshotKey("allocation.entry.\(id.lowercased)") }
    public static func workAllocations(machineID: UUID, day: String, status: String) -> SnapshotKey {
        SnapshotKey("allocation.entries.\(machineID.lowercased).\(day).\(status)")
    }
    public static func allocationDay(machineID: UUID, day: String) -> SnapshotKey {
        SnapshotKey("allocation.day.\(machineID.lowercased).\(day)")
    }
    public static func allocationDays(machineID: UUID, from: String, to: String) -> SnapshotKey {
        SnapshotKey("allocation.days.\(machineID.lowercased).\(from).\(to)")
    }
}

extension OwnerAPI {
    public static func dailyReports(status: String, pageSize: Int = 100) -> APIRequest<Page<DailyReportDTO>> {
        .get("\(tenant)/daily-reports", query: paging(1, pageSize) + compact([("status", status)]))
    }

    public static func dailyReport(_ id: UUID) -> APIRequest<DailyReportDTO> { .get("\(tenant)/daily-reports/\(id.lowercased)") }

    /// `decision` is ``DailyReportReview/reviewed`` or ``DailyReportReview/returned``; the note needs 5+ characters.
    public static func reviewDailyReport(_ id: UUID, decision: String, note: String, idempotencyKey: UUID) throws -> APIRequest<DailyReportDTO> {
        try .mutation(.post, "\(tenant)/daily-reports/\(id.lowercased)/review",
                      body: DailyReportReviewIn(decision: decision, note: note.trimmingCharacters(in: .whitespacesAndNewlines)),
                      idempotencyKey: idempotencyKey)
    }

    public static func workAllocation(_ id: UUID) -> APIRequest<WorkAllocationDTO> { .get("\(tenant)/work-allocations/\(id.lowercased)") }

    /// One machine's allocations of one day in one status.
    public static func workAllocations(machineID: UUID, day: String, status: String, pageSize: Int = 100) -> APIRequest<Page<WorkAllocationDTO>> {
        .get("\(tenant)/work-allocations", query: paging(1, pageSize) + compact([
            ("machine_id", machineID.lowercased), ("from", day), ("to", day), ("status", status),
        ]))
    }

    public static func allocationDay(machineID: UUID, day: String) -> APIRequest<[AllocationDayDTO]> {
        allocationDays(machineID: machineID, from: day, to: day)
    }

    public static func allocationDays(machineID: UUID, from: String, to: String) -> APIRequest<[AllocationDayDTO]> {
        .get("\(tenant)/work-allocations/reconciliation", query: compact([("from", from), ("to", to), ("machine_id", machineID.lowercased)]))
    }
}
