import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

// DEC-031 Phase 1 in the Owner app (strings doc "DEC-031 Phase 1 — revenue"): revenue differences (Approvals section +
// detail with Explain / Approve / Reject / Confirm), the "Revenue differences" dashboard tile and the read-only daily
// machine sheet per machine. Online only; reads may come from the encrypted snapshot cache like every Owner screen.
// Non-revenue hours decisions use the generic decision screen (`DecisionKind.nonRevenue`).

/// Wording of the revenue screens, copied exactly from `docs/requirements/accountability-mobile-strings.md`
/// (Android `RevenueTexts`).
public enum RevenueTexts {
    public static let sectionDifferences = "Revenue differences" // owner.rev.sectionDifferences
    public static let sectionNonRevenue = "Non-revenue hours" // owner.rev.sectionNonRevenue
    /// Not shown (sections appear only when something waits); kept for the generic decision kind.
    public static let sectionNonRevenueEmpty = "No non-revenue hours waiting."
    /// "TZS 120,000.00 to explain · EX-01" (owner.rev.rowDifference).
    public static func rowDifference(money: String, machine: String) -> String { "\(money) to explain · \(machine)" }
    /// "1.5 h Mobilization · EX-01" (owner.rev.rowNonRevenue).
    public static func rowNonRevenue(hours: String, type: String, machine: String) -> String { "\(hours) h \(type) · \(machine)" }
    public static let titleDifference = "Revenue difference" // owner.rev.titleDifference
    public static let titleNonRevenue = "Non-revenue hours" // owner.rev.titleNonRevenue
    public static let figures = "Figures"
    public static let machine = "Machine"
    public static let period = "Period"
    public static let job = "Job"
    public static let status = "Status"
    public static let expected = "Expected revenue"
    public static let inProgress = "Work still in progress"
    public static let attributed = "Money attributed"
    public static let difference = "Difference"
    public static let adjustedDifference = "Difference after adjustments"
    public static let customerWork = "Customer-work hours"
    public static let nonRevenueHours = "Non-revenue hours"
    public static let unexplainedHours = "Unexplained hours"
    public static let unexplainedExpected = "Unexplained hours expected as revenue"
    public static let investigation = "Investigation" // owner.rev.case
    public static let jobs = "Jobs"
    public static func jobLine(expected: String, attributed: String) -> String { "Expected \(expected) · Attributed \(attributed)" }
    public static func jobInProgress(_ money: String) -> String { "In progress \(money)" }
    public static let noJobs = "No jobs in this period."
    public static let explanation = "Explanation"
    public static let reason = "Reason"
    public static let note = "Note"
    public static let explainedBy = "Explained by"
    public static let explained = "Explained"
    public static let decidedBy = "Decided by"
    public static let decisionNote = "Decision note"
    public static let adjustments = "Adjustments"
    /// "26 Oct 2026, 14:05: TZS 120,000.00 → TZS 80,000.00" (owner.rev.adjustmentLine).
    public static func adjustmentLine(date: String, previous: String, new: String) -> String { "\(date): \(previous) → \(new)" }
    public static let explain = "Explain this difference"
    public static let explainFooter = "Someone else decides on your explanation."
    public static let chooseReason = "Choose a reason"
    public static let reasonsEmpty = "Your company has no revenue reasons yet. Add them on the web."
    public static let noteLabel = "Note (at least 5 characters)"
    public static let sendExplanation = "Send explanation"
    public static let explanationSent = "Explanation sent. Someone else will decide."
    public static let decide = "Decision"
    public static let decideFooter = "Approve or reject the explanation, or confirm the difference as money to recover. The person who explained it can't decide."
    public static let approve = "Approve explanation"
    public static let reject = "Reject explanation"
    public static let confirm = "Confirm difference"
    public static let confirmReject = "Reject this explanation? The difference goes back to \"To explain\"."
    public static let confirmConfirm = "Confirm this difference? It stays recorded as money to recover."
    public static let approved = "Explanation approved."
    public static let rejected = "Explanation rejected."
    public static let confirmed = "Difference confirmed."
    public static let ownExplanation = "Someone else must decide on your explanation"

    /// owner.rev.status.* (unknown → humanized wire value).
    public static func status(_ wire: String) -> String {
        switch wire {
        case RevenueDifferenceStatus.open: "To explain"
        case RevenueDifferenceStatus.explanationProposed: "Explanation waiting for a decision"
        case RevenueDifferenceStatus.explained: "Explained"
        case RevenueDifferenceStatus.confirmed: "Confirmed difference"
        case RevenueDifferenceStatus.cleared: "Cleared (money arrived)"
        default: OwnerFormat.humanize(wire)
        }
    }

    // Non-revenue hours decision (generic decision screen)
    public static let nonRevType = "Type" // owner.nonrev.type
    public static let nonRevHours = "Hours" // owner.nonrev.hours
    public static let nonRevTime = "Time" // owner.nonrev.time
    public static let nonRevFooter = "Approved time stops counting as revenue. The person who explained it can't approve it." // owner.nonrev.footer

    /// A work-log type (`MOBILIZATION`) as words.
    public static func activityType(_ wire: String) -> String { OwnerFormat.humanize(wire) }

    // Dashboard tile
    public static let dashRevenue = "Revenue differences" // owner.dash.revenue
    public static let dashToExplain = "To explain"
    public static let dashAwaiting = "Awaiting a decision"
    public static let dashAmounts = "Amount"
    public static let dashOldest = "Oldest open"
    public static let dashExplained = "Explained"
    public static let dashConfirmed = "Confirmed"
    public static let dashCleared = "Cleared"
    public static func dashItem(machine: String, period: String) -> String { "\(machine) · \(period)" } // owner.dash.revItem

    // Daily machine sheet
    public static let sheetOpen = "Daily machine sheet" // owner.sheet.open
    public static let sheetTitle = "Daily machine sheet" // owner.sheet.title
    public static let sheetEmpty = "No days with engine hours in the last 14 days."
    public static func sheetRowHours(engine: String, revenue: String) -> String { "Engine \(engine) h · Revenue \(revenue) h" }
    public static func sheetRowDifference(_ money: String) -> String { "Difference \(money)" }
    public static func sheetDayTitle(machine: String, day: String) -> String { "\(machine) · \(day)" }
    public static let sheetHours = "Hours"
    public static let sheetEngine = "Engine hours"
    public static let sheetCustomerWork = "Customer work"
    public static let sheetNonRevenue = "Non-revenue"
    public static let sheetNonRevenuePending = "Non-revenue awaiting approval"
    public static let sheetRevenue = "Revenue hours"
    public static let sheetApprovedNonCustomer = "Approved non-customer"
    public static let sheetIdentifiedVariance = "Identified difference"
    public static let sheetUnexplained = "Unexplained"
    public static let sheetPendingReview = "Awaiting review"
    public static let sheetReadings = "Readings"
    public static let sheetFirstReading = "First reading"
    public static let sheetLastReading = "Last reading"
    public static let sheetReadingCount = "Readings taken"
    public static func sheetMoney(_ currency: String) -> String { "Money (\(currency))" }
    public static let sheetFuel = "Fuel"
    public static func sheetLitres(_ litres: String) -> String { "\(litres) L" }
    public static let sheetFlags = "Flags"
    public static let sheetNoFlags = "No flags."
    public static let sheetFooter = "Read-only. Figures come from the readings, jobs, invoices and prepaid hours of the day."
    /// "Non-revenue · Mobilization" (one row per non-revenue type).
    public static func sheetNonRevenueType(_ type: String) -> String { "\(sheetNonRevenue) · \(activityType(type))" }

    /// owner.sheet.flag.* (unknown → humanized wire value).
    public static func flag(_ wire: String) -> String {
        switch wire {
        case SheetFlag.missingDailyReport: "Daily report missing"
        case SheetFlag.unexplainedHours: "Unexplained hours"
        case SheetFlag.engineOnWithoutJob: "Engine on without a job"
        case SheetFlag.fuelAboveNorm: "Fuel above norm"
        case SheetFlag.revenueDifference: "Revenue difference"
        default: OwnerFormat.humanize(wire)
        }
    }
}

// MARK: - Requests

extension SnapshotKey {
    /// Revenue differences of one status.
    public static func revenueDifferences(status: String) -> SnapshotKey { SnapshotKey("revenue.differences.\(status)") }
    public static func revenueDifference(_ id: UUID) -> SnapshotKey { SnapshotKey("revenue.difference.\(id.lowercased)") }
    public static let revenueReasons = SnapshotKey("revenue.reasons")
    /// One machine's daily sheet from `dayFrom` to `dayTo`.
    public static func dailySheet(machineID: UUID, dayFrom: String, dayTo: String) -> SnapshotKey {
        SnapshotKey("revenue.sheet.\(machineID.lowercased).\(dayFrom).\(dayTo)")
    }
    public static func dailySheetDay(machineID: UUID, day: String) -> SnapshotKey {
        SnapshotKey("revenue.sheet.day.\(machineID.lowercased).\(day)")
    }
}

extension OwnerAPI {
    /// `GET /revenue-differences?status=` (newest first).
    public static func revenueDifferences(status: String?, machineID: UUID? = nil,
                                          pageSize: Int = 100) -> APIRequest<Page<RevenueDifferenceDTO>> {
        .get("\(tenant)/revenue-differences", query: paging(1, pageSize) + compact([
            ("status", status), ("machine_id", machineID?.lowercased),
        ]))
    }

    public static func revenueDifference(_ id: UUID) -> APIRequest<RevenueDifferenceDTO> {
        .get("\(tenant)/revenue-differences/\(id.lowercased)")
    }

    /// `POST /revenue-differences/{id}/explanation` (`tenant.revenue.explain`).
    public static func explainRevenueDifference(_ id: UUID, reasonID: UUID, note: String,
                                                idempotencyKey: UUID) throws -> APIRequest<RevenueDifferenceDTO> {
        try .mutation(.post, "\(tenant)/revenue-differences/\(id.lowercased)/explanation",
                      body: RevenueExplanationIn(reasonID: reasonID, note: note.trimmingCharacters(in: .whitespacesAndNewlines)),
                      idempotencyKey: idempotencyKey)
    }

    /// `POST /revenue-differences/{id}/decision` (`tenant.revenue.decide`; refused to the explainer).
    public static func decideRevenueDifference(_ id: UUID, decision: RevenueDecision, note: String,
                                               idempotencyKey: UUID) throws -> APIRequest<RevenueDifferenceDTO> {
        try .mutation(.post, "\(tenant)/revenue-differences/\(id.lowercased)/decision",
                      body: RevenueDecisionIn(decision: decision.rawValue, note: note.trimmingCharacters(in: .whitespacesAndNewlines)),
                      idempotencyKey: idempotencyKey)
    }

    /// Active revenue reasons (`GET /revenue-reasons`).
    public static func revenueReasons() -> APIRequest<Page<RevenueReasonDTO>> {
        .get("\(tenant)/revenue-reasons", query: paging(1, 200))
    }

    /// `GET /daily-machine-sheet?machine_id=&day_from=&day_to=`.
    public static func dailySheet(machineID: UUID, dayFrom: String, dayTo: String) -> APIRequest<Page<DailyMachineSheetDTO>> {
        .get("\(tenant)/daily-machine-sheet", query: paging(1, 100) + compact([
            ("machine_id", machineID.lowercased), ("day_from", dayFrom), ("day_to", dayTo),
        ]))
    }

    /// `GET /daily-machine-sheet/{machine_id}/{day}`.
    public static func dailySheetDay(machineID: UUID, day: String) -> APIRequest<DailyMachineSheetDTO> {
        .get("\(tenant)/daily-machine-sheet/\(machineID.lowercased)/\(day)")
    }
}

// MARK: - Rules

/// A decision on a revenue difference.
public enum RevenueDecision: String, CaseIterable, Sendable {
    case approve = "APPROVE", reject = "REJECT", confirm = "CONFIRM"
}

/// What the signed-in user may do on a revenue difference (as Android `RevenueRules`).
public enum RevenueRules {
    public static let noteMin = 5, noteMax = 2000

    public static func noteOK(_ note: String) -> Bool {
        let n = note.trimmingCharacters(in: .whitespacesAndNewlines).count
        return n >= noteMin && n <= noteMax
    }

    /// Explain form: OPEN and an explain holder.
    public static func canExplain(_ d: RevenueDifferenceDTO, permissions: [String]) -> Bool {
        d.status == RevenueDifferenceStatus.open && permissions.contains(RevenuePermission.explain)
    }

    /// Decisions offered to a decide holder: OPEN → Confirm; EXPLANATION_PROPOSED → Approve, Reject, Confirm.
    public static func decisions(_ d: RevenueDifferenceDTO, permissions: [String]) -> [RevenueDecision] {
        guard permissions.contains(RevenuePermission.decide) else { return [] }
        switch d.status {
        case RevenueDifferenceStatus.open: return [.confirm]
        case RevenueDifferenceStatus.explanationProposed: return [.approve, .reject, .confirm]
        default: return []
        }
    }

    /// The signed-in user explained it: someone else must decide (the server refuses it too).
    public static func isOwnExplanation(_ d: RevenueDifferenceDTO, userID: UUID?) -> Bool {
        userID != nil && d.explainedBy == userID
    }

    /// Approvals lists OPEN rows only to explain or decide holders; EXPLANATION_PROPOSED rows to every reader.
    public static func listsOpen(permissions: [String]) -> Bool {
        permissions.contains(RevenuePermission.explain) || permissions.contains(RevenuePermission.decide)
    }

    /// Codes after which the difference must be reloaded (someone else acted on it).
    public static func needsReload(_ error: any Error) -> Bool {
        guard let code = (error as? APIError)?.code else { return false }
        return code == "REVENUE_DIFFERENCE_NOT_OPEN" || code == "REVENUE_DIFFERENCE_STATE" || code == "ALREADY_DECIDED"
    }

    public static func message(for error: any Error) -> String {
        if (error as? APIError)?.code == "SEGREGATION_OF_DUTIES" { return RevenueTexts.ownExplanation }
        return DecisionErrorText.message(for: error)
    }

    public static func done(_ decision: RevenueDecision) -> String {
        switch decision {
        case .approve: RevenueTexts.approved
        case .reject: RevenueTexts.rejected
        case .confirm: RevenueTexts.confirmed
        }
    }

    public static func buttonLabel(_ decision: RevenueDecision) -> String {
        switch decision {
        case .approve: RevenueTexts.approve
        case .reject: RevenueTexts.reject
        case .confirm: RevenueTexts.confirm
        }
    }

    /// Active reasons sorted by name.
    public static func pickable(_ reasons: [RevenueReasonDTO]) -> [RevenueReasonDTO] {
        reasons.filter(\.isActive).sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }
}

// MARK: - Presentation

public enum RevenuePresentation {
    typealias T = RevenueTexts

    /// `2026-10-26` → `26 Oct 2026` (unchanged when it does not parse).
    public static func day(_ wire: String) -> String {
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

    /// `26 Oct 2026` in `timeZone`.
    public static func dateOnly(_ date: Date, timeZone: TimeZone = .current) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = timeZone
        f.dateFormat = "d MMM yyyy"
        return f.string(from: date)
    }

    /// `{from} – {to}`, one date when equal.
    public static func period(from: String, to: String) -> String {
        from == to ? day(from) : "\(day(from)) – \(day(to))"
    }

    public static func period(_ d: RevenueDifferenceDTO) -> String { period(from: d.localFrom, to: d.localTo) }

    public static func machine(_ d: RevenueDifferenceDTO) -> String {
        DisplayName.machine(code: d.machineCode, name: d.machineName, id: d.machineID)
    }

    static func money(_ amount: Decimal, _ currency: String) -> String { OwnerFormat.money(amount, currency: currency) }

    /// The amount a row headlines: the adjusted difference when present, else the difference.
    public static func shown(_ d: RevenueDifferenceDTO) -> Decimal { (d.adjustedDifference ?? d.difference).value }

    /// Approvals row: headline, subtitle (`{period} · {status}`) and footnote ("Proposed {time} by {explainer}", only once
    /// explained), as Android `DecisionMapper.revenueDifference`.
    public static func row(_ d: RevenueDifferenceDTO, timeZone: TimeZone = .current) -> (headline: String, subtitle: String, footnote: String?) {
        let footnote = d.explainedAt.map { at in
            let time = OwnerFormat.stamp(at, timeZone: timeZone)
            return DisplayName.optional(d.explainedByName, id: d.explainedBy).map { OwnerAccountabilityTexts.approvalsProposedBy(time, $0) }
                ?? OwnerAccountabilityTexts.approvalsProposed(time)
        }
        return (T.rowDifference(money: money(shown(d), d.currency), machine: d.machineCode ?? d.machineName ?? DisplayName.shortID(d.machineID)),
                "\(period(d)) · \(T.status(d.status))", footnote)
    }

    /// Colour of the status pill.
    public enum StatusTone: Sendable, Equatable { case live, critical, warning }

    public static func statusTone(_ status: String) -> StatusTone {
        switch status {
        case RevenueDifferenceStatus.explained, RevenueDifferenceStatus.cleared: .live
        case RevenueDifferenceStatus.confirmed: .critical
        default: .warning
        }
    }

    /// The Figures card in the strings doc order (zero-only rows left out); the Status pill follows them.
    public static func figures(_ d: RevenueDifferenceDTO) -> [DecisionField] {
        var rows: [(String, String?)] = [(T.machine, machine(d)), (T.period, period(d))]
        if d.jobID != nil { rows.append((T.job, DisplayName.optional(d.jobNumber, id: d.jobID))) }
        rows.append((T.expected, money(d.expectedAmount.value, d.currency)))
        if d.inProgressAmount.value != 0 { rows.append((T.inProgress, money(d.inProgressAmount.value, d.currency))) }
        rows.append((T.attributed, money(d.attributedAmount.value, d.currency)))
        rows.append((T.difference, money(d.difference.value, d.currency)))
        if let adjusted = d.adjustedDifference { rows.append((T.adjustedDifference, money(adjusted.value, d.currency))) }
        rows.append((T.customerWork, OwnerFormat.hours(d.customerWorkHours)))
        rows.append((T.nonRevenueHours, OwnerFormat.hours(d.nonRevenueHours)))
        if d.unexplainedHours.value != 0 { rows.append((T.unexplainedHours, OwnerFormat.hours(d.unexplainedHours))) }
        if d.unexplainedExpectedAmount.value != 0 {
            rows.append((T.unexplainedExpected, money(d.unexplainedExpectedAmount.value, d.currency)))
        }
        if d.caseID != nil { rows.append((T.investigation, DisplayName.optional(d.caseNumber, id: d.caseID))) }
        return PendingDecision.fields(rows)
    }

    /// The Jobs card: `{job number}` + `Expected … · Attributed …` (+ ` · In progress …` when non-zero).
    public static func jobs(_ d: RevenueDifferenceDTO) -> [DecisionField] {
        d.detailJobs.map { job in
            var line = T.jobLine(expected: money(job.expected, job.currency), attributed: money(job.attributed, job.currency))
            if job.inProgress != 0 { line += " · " + T.jobInProgress(money(job.inProgress, job.currency)) }
            return DecisionField(label: DisplayName.or(job.jobNumber, id: job.jobID), value: line)
        }
    }

    /// The Explanation card (when a reason or an explainer is set).
    public static func explanation(_ d: RevenueDifferenceDTO, timeZone: TimeZone = .current) -> [DecisionField] {
        guard d.reasonID != nil || d.explainedBy != nil else { return [] }
        return PendingDecision.fields([
            (T.reason, d.reasonName), (T.note, d.explanationNote),
            (T.explainedBy, DisplayName.optional(d.explainedByName, id: d.explainedBy)),
            (T.explained, d.explainedAt.map { OwnerFormat.stamp($0, timeZone: timeZone) }),
        ])
    }

    /// Decided by / decision note (when decided).
    public static func decided(_ d: RevenueDifferenceDTO) -> [DecisionField] {
        guard d.decidedBy != nil else { return [] }
        return PendingDecision.fields([
            (T.decidedBy, DisplayName.optional(d.decidedByName, id: d.decidedBy)), (T.decisionNote, d.decisionNote),
        ])
    }

    /// Adjustment lines, newest first.
    public static func adjustments(_ d: RevenueDifferenceDTO, timeZone: TimeZone = .current) -> [String] {
        d.adjustments.sorted { $0.createdAt > $1.createdAt }.map {
            T.adjustmentLine(date: dateOnly($0.createdAt, timeZone: timeZone),
                             previous: money($0.previousDifference.value, d.currency),
                             new: money($0.newDifference.value, d.currency))
        }
    }

    // Daily machine sheet

    /// The last 14 tenant-local days (today included): (day_from, day_to) as `YYYY-MM-DD`.
    public static func sheetRange(now: Date = Date(), timeZone: TimeZone = .current) -> (from: String, to: String) {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        let from = calendar.date(byAdding: .day, value: -13, to: now) ?? now
        return (CashRecordPresentation.localDay(from, timeZone: timeZone), CashRecordPresentation.localDay(now, timeZone: timeZone))
    }

    static func number(_ value: DecimalString) -> String { PendingDecision.num(value) }

    /// A sheet list row: day headline, hours line, difference lines (non-zero per currency) and the flags line.
    public static func sheetRow(_ s: DailyMachineSheetDTO) -> (title: String, hours: String, differences: [String], flags: String?) {
        let differences = s.money.filter { $0.difference.value != 0 }
            .map { T.sheetRowDifference(money($0.difference.value, $0.currency)) }
        return (day(s.day), T.sheetRowHours(engine: number(s.engineHours), revenue: number(s.revenueHours)), differences,
                s.flags.isEmpty ? nil : s.flags.map(T.flag).joined(separator: " · "))
    }

    /// Newest day first.
    public static func sheetRows(_ rows: [DailyMachineSheetDTO]) -> [DailyMachineSheetDTO] { rows.sorted { $0.day > $1.day } }

    /// The Hours card: Engine and Revenue hours always, the other rows only when non-zero; one row per non-revenue type.
    public static func sheetHours(_ s: DailyMachineSheetDTO) -> [DecisionField] {
        func h(_ value: DecimalString) -> String { OwnerFormat.hours(value) }
        var rows: [DecisionField] = [DecisionField(label: T.sheetEngine, value: h(s.engineHours))]
        func add(_ label: String, _ value: DecimalString) {
            if value.value != 0 { rows.append(DecisionField(label: label, value: h(value))) }
        }
        add(T.sheetCustomerWork, s.customerWorkHours)
        add(T.sheetNonRevenue, s.nonRevenueHours)
        for type in s.nonRevenueByType.keys.sorted() { add(T.sheetNonRevenueType(type), s.nonRevenueByType[type]!) }
        add(T.sheetNonRevenuePending, s.nonRevenuePendingHours)
        rows.append(DecisionField(label: T.sheetRevenue, value: h(s.revenueHours)))
        add(T.sheetApprovedNonCustomer, s.approvedNonCustomerHours)
        add(T.sheetIdentifiedVariance, s.identifiedVarianceHours)
        add(T.sheetUnexplained, s.unexplainedHours)
        add(T.sheetPendingReview, s.pendingReviewHours)
        return rows
    }

    /// The Readings card: first, last, count, then each reading as `{time} · {reading}` → `{kind}` (as Android).
    public static func sheetReadings(_ s: DailyMachineSheetDTO, timeZone: TimeZone = .current) -> [DecisionField] {
        let time = DateFormatter()
        time.locale = Locale(identifier: "en_US_POSIX")
        time.timeZone = timeZone
        time.dateFormat = "HH:mm"
        return PendingDecision.fields([
            (T.sheetFirstReading, s.firstReading.map(number)), (T.sheetLastReading, s.lastReading.map(number)),
            (T.sheetReadingCount, "\(s.readingCount)"),
        ]) + s.readings.sorted { $0.capturedAt < $1.capturedAt }.map {
            DecisionField(label: "\(time.string(from: $0.capturedAt)) · \(number($0.reading))", value: OwnerFormat.humanize($0.kind))
        }
    }

    /// The Jobs card: `{job number} · {customer}` → `{customer work} h`.
    public static func sheetJobs(_ s: DailyMachineSheetDTO) -> [DecisionField] {
        s.jobs.map { job in
            let label = [DisplayName.or(job.jobNumber, id: job.jobID), job.customerName ?? job.customerID.map(DisplayName.shortID)]
                .compactMap { $0 }.joined(separator: " · ")
            return DecisionField(label: label, value: OwnerFormat.hours(job.customerWorkHours))
        }
    }

    /// One Money card per currency.
    public static func sheetMoney(_ s: DailyMachineSheetDTO) -> [(title: String, fields: [DecisionField])] {
        s.money.map { m in
            var rows: [DecisionField] = [DecisionField(label: T.expected, value: money(m.expected.value, m.currency))]
            if m.inProgress.value != 0 { rows.append(DecisionField(label: T.inProgress, value: money(m.inProgress.value, m.currency))) }
            rows.append(DecisionField(label: T.attributed, value: money(m.attributed.value, m.currency)))
            rows.append(DecisionField(label: T.difference, value: money(m.difference.value, m.currency)))
            if let unexplained = m.unexplainedExpected, unexplained.value != 0 {
                rows.append(DecisionField(label: T.unexplainedExpected, value: money(unexplained.value, m.currency)))
            }
            return (T.sheetMoney(m.currency), rows)
        }
    }

    public static func sheetFuel(_ s: DailyMachineSheetDTO) -> String { T.sheetLitres(number(s.fuelLitres)) }

    public static func sheetFlags(_ s: DailyMachineSheetDTO) -> [String] { s.flags.map(T.flag) }
}

// MARK: - Dashboard tile

extension AccountabilityDashboard {
    /// The "Revenue differences" tile (`revenue_differences`), nil when absent, REVENUE_RECONCILIATION is off or the role
    /// may not read revenue (as Android `RevenuePresentation.tile`).
    public static func revenueTile(_ value: JSONValue?, off: Set<String>, revenueRead: Bool = true) -> DashboardTile? {
        guard revenueRead, !off.contains(TenantCapability.revenueReconciliation), let r = value, r != .null else { return nil }
        let T = RevenueTexts.self
        var rows: [DashboardTile.Row] = [
            .init(T.dashToExplain, "\(r["open"]?.intValue ?? 0)"), .init(T.dashAwaiting, "\(r["awaiting_decision"]?.intValue ?? 0)"),
        ]
        var amounts: [String] = []
        if case let .array(items)? = r["amounts"] {
            for item in items {
                guard let currency = item["currency"]?.stringValue,
                      let amount = item["amount"]?.stringValue.flatMap({ DecimalString(string: $0) }) else { continue }
                amounts.append("\(item["count"]?.intValue ?? 0) · \(OwnerFormat.money(amount, currency: currency))")
            }
        }
        rows.append(.init(T.dashAmounts, amounts.isEmpty ? OwnerAccountabilityTexts.dashNone : amounts.joined(separator: ", ")))
        if let oldest = r["oldest_open_days"]?.intValue { rows.append(.init(T.dashOldest, OwnerAccountabilityTexts.days(oldest))) }
        rows += [
            .init(T.dashExplained, "\(r["explained_in_window"]?.intValue ?? 0)"),
            .init(T.dashConfirmed, "\(r["confirmed_in_window"]?.intValue ?? 0)"),
            .init(T.dashCleared, "\(r["cleared_in_window"]?.intValue ?? 0)"),
        ]
        if case let .array(items)? = r["items"] {
            for item in items {
                let from = item["local_from"]?.stringValue ?? ""
                let period = RevenuePresentation.period(from: from, to: item["local_to"]?.stringValue ?? from)
                let money = item["difference"]?.stringValue.flatMap { DecimalString(string: $0) }
                    .map { OwnerFormat.money($0, currency: item["currency"]?.stringValue ?? "") } ?? "—"
                rows.append(.init(T.dashItem(machine: item["machine_code"]?.stringValue ?? "", period: period), money))
            }
        }
        return DashboardTile(id: "revenue_differences", title: T.dashRevenue, rows: rows, route: .approvals,
                             footer: r["window_days"]?.intValue.map(OwnerAccountabilityTexts.dashWindow))
    }
}
