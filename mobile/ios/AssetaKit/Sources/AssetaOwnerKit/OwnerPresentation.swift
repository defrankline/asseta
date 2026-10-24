import AssetaModel
import Foundation

// Screen content shared with the Android Owner app: labels, ordering, filters and empty states. Android keeps the
// same strings in `OverviewPresentation`, `FleetRows`, `JobsPresentation`, `AlertText`, `ApprovalText`, `CaseText`,
// `MachineText`, `SettingsText` and `InboxText`; `ParityPresentationTests` (both platforms) pin them. Change both.

// MARK: - Overview

/// Emphasis of a KPI; the UI maps it to a colour (the label always says what it is).
public enum KPITone: Equatable, Sendable { case normal, good, warning, critical, muted }

public struct OverviewRow: Equatable, Sendable {
    public let label: String
    public let value: String
    public var detail: String?
    public var tone: KPITone = .normal
    public var route: OwnerRoute?
}

public struct OverviewGroup: Equatable, Sendable {
    public let heading: String?
    public let rows: [OverviewRow]
}

public struct OverviewAction: Equatable, Sendable {
    public let label: String
    public let route: OwnerRoute
}

public struct OverviewSection: Equatable, Sendable {
    public let title: String
    public let freshness: String
    public let groups: [OverviewGroup]
    public var actions: [OverviewAction] = []
    public var emptyText: String?
}

public enum OverviewPresentation {
    public static let noSections = "Your role has no dashboard sections in this company."
    public static let jobStatusOrder = ["IN_PROGRESS", "APPROVED", "PENDING_APPROVAL", "DRAFT", "COMPLETED", "CANCELLED"]

    /// `Figures as of 22 Oct 2026, 08:00 (Africa/Dar_es_Salaam)`, in the company's time zone.
    public static func asOf(_ o: TenantOverviewDTO) -> String {
        "Figures as of \(OwnerFormat.stamp(o.asOf, timeZone: TimeZone(identifier: o.timezone) ?? .current)) (\(o.timezone))"
    }

    public static func breakdown(_ c: OverviewSeverityCounts) -> String {
        "\(c.critical) critical · \(c.warning) warning · \(c.info) info"
    }

    /// `cached`: the overview is an offline snapshot, so "live" counts describe the moment it was saved.
    public static func sections(_ o: TenantOverviewDTO, cached: Bool, now: Date = Date(),
                                money: (DecimalString, String) -> String = { OwnerFormat.money($0, currency: $1) })
        -> [OverviewSection] {
        var out: [OverviewSection] = []
        if let f = o.fleet {
            let c = f.connectivity
            var rows = [
                OverviewRow(label: "Machines", value: "\(f.machines)"),
                OverviewRow(label: cached ? "Live when saved" : "Live now", value: "\(c.live)", tone: cached ? .muted : .good),
                OverviewRow(label: "Recent", value: "\(c.recent)"),
                OverviewRow(label: "Stale", value: "\(c.stale)", tone: c.stale > 0 ? .warning : .normal),
                OverviewRow(label: "Offline", value: "\(c.offline)", tone: c.offline > 0 ? .critical : .normal),
                OverviewRow(label: "Never reported", value: "\(c.never)", tone: .muted),
                OverviewRow(label: "No tracker", value: "\(c.noTracker)", tone: .muted),
                OverviewRow(label: "Engine on (tracker verified)", value: "\(f.engineOnVerified)"),
            ]
            rows += f.reportedWorkState.keys.sorted().map {
                OverviewRow(label: "Reported \(OwnerFormat.humanize($0).lowercased())", value: "\(f.reportedWorkState[$0] ?? 0)")
            }
            rows.append(OverviewRow(label: "Open alerts", value: "\(f.openAlerts.total)", detail: breakdown(f.openAlerts),
                                    tone: f.openAlerts.critical > 0 ? .critical : .normal, route: .alerts))
            out.append(OverviewSection(title: "Fleet", freshness: OwnerFormat.sourceFreshness(f.latestSourceAt, now: now),
                                       groups: [OverviewGroup(heading: nil, rows: rows)],
                                       actions: [OverviewAction(label: "Open fleet map", route: .fleet)]))
        }
        if let w = o.work {
            let order = { (s: String) in jobStatusOrder.firstIndex(of: s) ?? Int.max }
            let statuses = w.jobsByStatus.keys.sorted { (order($0), $0) < (order($1), $1) }
            var rows = statuses.map { OverviewRow(label: OwnerFormat.humanize($0), value: "\(w.jobsByStatus[$0] ?? 0)") }
            if let n = w.pendingApprovals {
                rows.append(OverviewRow(label: "Pending approvals", value: "\(n)", tone: n > 0 ? .warning : .normal, route: .approvals))
            }
            if let n = w.readingsNeedingReview { rows.append(OverviewRow(label: "Readings needing review", value: "\(n)")) }
            if let n = w.openExceptions {
                rows.append(OverviewRow(label: "Open meter exceptions", value: "\(n)", tone: n > 0 ? .warning : .normal,
                                        route: .exceptions(jobID: nil)))
            }
            out.append(OverviewSection(title: "Jobs and work", freshness: OwnerFormat.sourceFreshness(w.latestSourceAt, now: now),
                                       groups: [OverviewGroup(heading: nil, rows: rows)],
                                       actions: [OverviewAction(label: "Open jobs", route: .jobs)]))
        }
        if let m = o.money {
            let groups = m.currencies.map { c in
                OverviewGroup(heading: c.currency, rows: [
                    OverviewRow(label: "Receivables outstanding", value: money(c.receivablesOutstanding, c.currency)),
                    OverviewRow(label: "Overdue (\(c.overdueInvoices) invoices)", value: money(c.receivablesOverdue, c.currency),
                                tone: c.overdueInvoices > 0 ? .critical : .normal),
                    OverviewRow(label: "Verified receipts this month", value: money(c.verifiedReceiptsMTD, c.currency), tone: .good),
                    OverviewRow(label: "Approved expenses this month", value: money(c.approvedExpensesMTD, c.currency)),
                    OverviewRow(label: "Cash with supervisors", value: money(c.cashWithSupervisors, c.currency)),
                ])
            }
            out.append(OverviewSection(title: "Money (month from \(m.monthStart))",
                                       freshness: OwnerFormat.sourceFreshness(m.latestSourceAt, now: now), groups: groups,
                                       emptyText: groups.isEmpty ? "No financial activity this month." : nil))
        }
        if let r = o.risk {
            var rows: [OverviewRow] = []
            if let c = r.openCases {
                rows.append(OverviewRow(label: "Open investigations", value: "\(c.total)", detail: breakdown(c),
                                        tone: c.critical > 0 ? .critical : .normal))
            }
            if let s = r.signalsLast7Days {
                rows.append(OverviewRow(label: "Signals (last 7 days)", value: "\(s.total)", detail: breakdown(s)))
            }
            out.append(OverviewSection(title: "Investigations and signals",
                                       freshness: OwnerFormat.sourceFreshness(r.latestSourceAt, now: now),
                                       groups: [OverviewGroup(heading: nil, rows: rows)],
                                       actions: [OverviewAction(label: "Open investigations", route: .investigations)]))
        }
        return out
    }
}

// MARK: - Navigation

/// Bottom tabs of the Owner app, in order.
public enum OwnerTabKind: String, CaseIterable, Sendable {
    case overview = "Overview", fleet = "Fleet", jobs = "Jobs", alerts = "Alerts", more = "More"
}

extension OwnerFeatures {
    /// Tabs this role can use (same gating as Android): Overview needs fleet/jobs/finance; Fleet and Alerts need fleet.
    public var tabs: [OwnerTabKind] {
        OwnerTabKind.allCases.filter {
            switch $0 {
            case .overview: overview
            case .fleet, .alerts: fleet
            case .jobs: jobs
            case .more: true
            }
        }
    }

    /// Whether the role can open the screen a route leads to (links to other screens are hidden otherwise).
    public func allows(_ route: OwnerRoute) -> Bool {
        switch route {
        case .fleet, .machine, .alerts, .alert: fleet
        case .jobs, .job: jobs
        case .approvals: approvalsScreen
        case .approval: approvals
        case let .decision(kind, _): decisionKinds.contains(kind)
        case .accountability: accountability
        case .exceptions, .meterReset, .exception: meterEvidence
        case .fieldSpend: expenses
        case .cash, .handover: finance
        case .investigations, .investigation: cases
        case .notifications, .notification: notifications
        }
    }

    /// Entries of the More tab, in order.
    public var moreEntries: [String] {
        (approvalsScreen ? ["Approvals"] : []) + (accountability ? [OwnerAccountabilityTexts.moreAccountability] : [])
            + (meterEvidence ? ["Meter exceptions"] : []) + (expenses ? ["Field spend"] : [])
            + (finance ? ["Cash with supervisors"] : []) + (cases ? ["Investigations"] : [])
            + (notifications ? ["Notifications"] : []) + ["Settings"]
    }
}

// MARK: - Fleet

extension FleetPresentation {
    public static func title(_ m: MachineMapDTO) -> String { "\(m.assetCode) · \(m.name)" }

    /// Pill text: "Live", "Recent", "Stale", "Offline", "Never reported", "No tracker".
    public static func statusLabel(_ m: MachineMapDTO, dataIsCached: Bool, now: Date = Date()) -> String {
        switch style(for: m, dataIsCached: dataIsCached, now: now).tone {
        case .live: "Live"
        case .recent: "Recent"
        case .stale: "Stale"
        case .offline: "Offline"
        case .unknown: m.connectivity.humanized
        }
    }

    /// "Last seen 5 min ago · engine on · moving" ("Never seen · …" without any message).
    public static func detailLine(_ m: MachineMapDTO, dataIsCached: Bool, now: Date = Date()) -> String {
        "\(lastSeenText(m, dataIsCached: dataIsCached, now: now)) · engine \(m.observedEngine.humanized.lowercased())"
            + " · \(m.observedMotion.humanized.lowercased())"
    }

    public static func reportedLine(_ m: MachineMapDTO) -> String {
        "Reported: \(OwnerFormat.humanize(m.reportedWorkStatus))" + (m.operator.map { " · operator \($0)" } ?? "")
    }

    public static func alertsLine(_ count: Int) -> String { count == 1 ? "1 open alert" : "\(count) open alerts" }

    public static func unplacedNote(_ count: Int) -> String? {
        switch count {
        case ...0: nil
        case 1: "1 machine has no known position (see List)."
        default: "\(count) machines have no known position (see List)."
        }
    }

    public static let emptyTitle = "No machines"
    public static let emptyMessage = "Nothing matches this search or filter."
}

// MARK: - Machine

public enum MachineText {
    public static let statusFooter = "Engine and motion are observed from tracker telemetry; reported work comes from the field team."
    public static let noTrack = "No positions in the last 24 hours."
    public static let truncated = "Track shortened by the server; some points are not shown."

    /// Status rows in display order (label, value); optional rows only when known.
    public static func statusRows(_ m: MachineMapDTO, info: OwnerMachineDTO?, dataIsCached: Bool,
                                  now: Date = Date()) -> [(String, String)] {
        var rows: [(String, String)] = [("Machine", FleetPresentation.title(m))]
        let seen = FleetPresentation.lastSeenText(m, dataIsCached: dataIsCached, now: now)
        rows.append(("Last seen", seen == "Never seen" ? "Never" : String(seen.dropFirst("Last seen ".count)).capitalizedFirstLetter))
        rows.append(("Position time", m.positionTime.map { OwnerFormat.timestamp($0) } ?? "—"))
        if let a = m.accuracyM { rows.append(("Accuracy", "± \(Int(a.rounded())) m")) }
        rows += [
            ("Engine (tracker)", m.observedEngine.humanized),
            ("Motion (tracker)", m.observedMotion.humanized),
            ("Reported work status", OwnerFormat.humanize(m.reportedWorkStatus)),
            ("Location compliance", m.locationCompliance.humanized),
            ("Machine status", OwnerFormat.humanize(m.machineStatus)),
        ]
        if let op = m.operator { rows.append(("Operator", op)) }
        if let s = m.supervisor { rows.append(("Supervisor", s)) }
        if let t = m.trackerState { rows.append(("Tracker", OwnerFormat.humanize(t))) }
        if let line = info?.modelLine { rows.append(("Model", line)) }
        if let info { rows.append(("Ownership", OwnerFormat.humanize(info.ownership))) }
        return rows
    }

    public static func distance(_ km: Double) -> String { String(format: "%.1f km", locale: Locale(identifier: "en_US_POSIX"), km) }

    public static func stopLine(_ start: Date, durationSeconds: Int) -> String {
        "Stopped \(OwnerFormat.timestamp(start)) for \(durationSeconds / 60) min"
    }

    public static func visitLine(_ v: SiteVisitDTO) -> String {
        "At \(v.geofenceName): \(v.enteredAt.map { OwnerFormat.timestamp($0) } ?? "—") – \(v.exitedAt.map { OwnerFormat.timestamp($0) } ?? "—")"
    }
}

/// Meter reading lines (machine and job screens).
public enum ReadingText {
    public static let photoFooter = "Evidence photos are downloaded only when you open them and are never saved on this phone."

    public static func title(_ c: MeterCaptureDTO) -> String { "\(OwnerFormat.humanize(c.kind)) · \(c.reading.description)" }

    /// "22 Oct 2026, 14:05 · Ocr · corrected by hand · OCR 93% · GPS ok"
    public static func detail(_ c: MeterCaptureDTO) -> String {
        var s = "\(OwnerFormat.timestamp(c.capturedAt)) · \(OwnerFormat.humanize(c.captureMode))"
        if c.manuallyCorrected { s += " · corrected by hand" }
        if let conf = c.ocrConfidence { s += " · OCR \(Int(conf * 100))%" }
        return s + " · GPS \(OwnerFormat.humanize(c.gpsStatus.rawValue).lowercased())"
    }
}

// MARK: - Jobs

public enum JobsPresentation {
    /// Status chips in display order; nil = all. The list opens on jobs in progress.
    public static let filters: [(JobStatus?, String)] = [
        (.inProgress, "In progress"), (.approved, "Approved"), (.pendingApproval, "Pending approval"),
        (.completed, "Completed"), (.cancelled, "Cancelled"), (nil, "All"),
    ]
    public static let defaultFilter: JobStatus? = .inProgress
    public static let moreInConsole = "Use the web console for the full list."
    public static let emptyTitle = "No jobs"
    public static let emptyMessage = "Nothing matches this filter."

    public static func countLine(shown: Int, total: Int) -> String { "\(shown) of \(total) jobs" }

    public static func datesLine(_ job: JobDTO) -> String {
        if let done = job.completedAt { return "Completed \(OwnerFormat.timestamp(done))" }
        if let started = job.startedAt { return "Started \(OwnerFormat.timestamp(started))" }
        return "Planned \(OwnerFormat.timestamp(job.plannedStart))"
    }
}

public enum JobDetailText {
    public static let noCharges = "Charges appear once both readings are in."

    public static func billing(_ s: JobSummaryDTO) -> String {
        if s.billingReady { return "Ready to invoice." }
        if s.blockingExceptions > 0 { return "Not ready to invoice: \(s.blockingExceptions) blocking exception(s)." }
        return "Not ready to invoice."
    }

    public static func exceptions(_ open: Int) -> String? {
        open > 0 ? "\(open) open exception(s) need review." : nil
    }
}

// MARK: - Alerts, approvals, investigations, inbox, settings

public enum AlertText {
    public static let filters: [(AlertStatus?, String)] = [
        (.open, "Open"), (.acknowledged, "Acknowledged"), (.resolved, "Resolved"), (nil, "All"),
    ]
    public static let emptyTitle = "No alerts"
    public static let emptyMessage = "Nothing needs attention here."
    public static let notFoundTitle = "Alert not found"
    public static let notFoundMessage = "It may be older than the latest 200 alerts. Open it in the web console."
    public static let noteLabel = "Note (required to resolve)"

    /// Most severe first, then newest.
    public static func sorted(_ items: [AlertDTO]) -> [AlertDTO] {
        items.sorted { ($0.severity.rank, $0.eventTime) > ($1.severity.rank, $1.eventTime) }
    }

    public static func done(_ status: AlertStatus) -> String { "Alert \(status.humanized.lowercased())." }

    public static func evidence(_ value: JSONValue) -> String {
        switch value {
        case let .string(s): s
        case let .number(n): "\(n)"
        case let .bool(b): b ? "Yes" : "No"
        case .null: "—"
        default: (try? value.jsonString()) ?? "—"
        }
    }
}

public enum ApprovalText {
    public static let filters: [(ApprovalStatus, String)] = [(.pending, "Pending"), (.approved, "Approved"), (.rejected, "Rejected")]
    public static let emptyTitle = "Nothing here"
    public static let emptyMessage = "No requests with this status."
    public static let notFoundTitle = "Request not found"
    public static let notFoundMessage = "It may be older than the latest 200 requests."
    public static let noteLabel = "Note (optional to approve, required to reject)"
    public static let sodFooter = "The person who submitted a request can't decide it (segregation of duties)."
    public static let sodTitle = "Not allowed: segregation of duties"
    public static let confirmReject = "Reject this request?"

    /// A rejection must say why; an approval note is optional.
    public static func canDecide(approve: Bool, note: String) -> Bool {
        approve || !note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    public static func summary(_ r: ApprovalRequestDTO) -> String { "\(OwnerFormat.humanize(r.subjectType)) · \(r.reason)" }
}

public enum CaseText {
    public static let filters: [(CaseStatus?, String)] = [(nil, "All"), (.open, "Open"), (.inReview, "In review"), (.resolved, "Resolved")]
    public static let intro = "Cases group signals for review. A case is not a conclusion about anyone."
    public static let emptyTitle = "No investigations"
    public static let emptyMessage = "Nothing needs review."
    public static let detailFooter = "Signals are indicators that need review; they are not conclusions. "
        + "Review and outcomes are recorded in the web console."

    public static func summary(_ c: AnomalyCaseDTO) -> String {
        let n = c.signalCount ?? 0
        return "\(OwnerFormat.humanize(c.subjectType)) · \(n) signal\(n == 1 ? "" : "s") · last signal \(OwnerFormat.timestamp(c.lastSignalAt))"
    }
}

public enum InboxText {
    public static let emptyTitle = "No notifications"
    public static let noTarget = "Open the web console for details."

    public static func visible(_ items: [NotificationDTO], unreadOnly: Bool) -> [NotificationDTO] {
        unreadOnly ? items.filter(\.isUnread) : items
    }
}

public enum SettingsText {
    public static let matrixTitle = "Push priorities"
    public static let matrixFooter = "Choose which notifications reach this phone as push. Locked switches are required by Asseta. "
        + "Every notification stays in the in-app inbox."
    public static let saved = "Notification settings saved."
    public static let devicesFooter = "Push notifications go to this phone for the company that is open. Signing out unregisters it."
    public static let pushUnavailable = "Push is not configured for this build. You still get notifications in the inbox and "
        + "live while the app is open."
    public static let offlineData = "Screens you have opened are kept encrypted on this phone for up to 7 days so you can look "
        + "at them offline. Saved data is clearly marked stale and can't be changed. Signing out erases it."
    public static let signOutConfirm = "Sign out?"
    public static let signOutAction = "Sign out and erase saved data"

    public static func pushStatus(available: Bool, registered: Bool, tenantName: String) -> String {
        if !available { return "Not available in this build" }
        return registered ? "Registered for \(tenantName)" : "Not registered yet"
    }
}

extension String {
    var capitalizedFirstLetter: String { prefix(1).uppercased() + dropFirst() }
}
