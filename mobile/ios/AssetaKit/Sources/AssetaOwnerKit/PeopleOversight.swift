import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

// DEC-031 Phase 5 in the Owner app: the people scorecard, unbilled work, idle machines and site check-ins. Read-only;
// reads may come from the encrypted snapshot cache like every Owner screen.

// MARK: - Requests

extension SnapshotKey {
    public static func scorecard(from: String, to: String) -> SnapshotKey { SnapshotKey("scorecard.\(from).\(to)") }
    public static func scorecardPerson(_ id: UUID, from: String, to: String, item: String?) -> SnapshotKey {
        SnapshotKey("scorecard.person.\(id.lowercased).\(from).\(to).\(item ?? "all")")
    }
    public static let unbilledWork = SnapshotKey("oversight.unbilled")
    public static let idleMachines = SnapshotKey("oversight.idle")
    public static let siteCheckins = SnapshotKey("oversight.checkins")
    public static func siteCheckin(_ id: UUID) -> SnapshotKey { SnapshotKey("oversight.checkin.\(id.lowercased)") }
}

extension OwnerAPI {
    /// `GET /scorecard?day_from&day_to` (most items first; at most 93 days).
    public static func scorecard(from: String, to: String, pageSize: Int = 200) -> APIRequest<Page<ScorecardRowDTO>> {
        .get("\(tenant)/scorecard", query: compact([("day_from", from), ("day_to", to)]) + paging(1, pageSize))
    }

    /// `GET /scorecard/{staff_member_id}?day_from&day_to[&item]`: the person's row and the records behind it.
    public static func scorecardPerson(_ id: UUID, from: String, to: String, item: String? = nil) -> APIRequest<ScorecardDetailDTO> {
        .get("\(tenant)/scorecard/\(id.lowercased)", query: compact([("day_from", from), ("day_to", to), ("item", item)]))
    }

    /// `GET /unbilled-work` (oldest first).
    public static func unbilledWork(pageSize: Int = 200) -> APIRequest<Page<UnbilledJobDTO>> {
        .get("\(tenant)/unbilled-work", query: paging(1, pageSize))
    }

    /// `GET /idle-machines` (longest idle first).
    public static func idleMachines(pageSize: Int = 200) -> APIRequest<Page<IdleMachineDTO>> {
        .get("\(tenant)/idle-machines", query: paging(1, pageSize))
    }

    /// `GET /site-checkins?day_from&day_to` (the office list, newest first).
    public static func siteCheckins(from: String? = nil, to: String? = nil, pageSize: Int = 100) -> APIRequest<Page<SiteCheckinDTO>> {
        .get("\(tenant)/site-checkins", query: compact([("day_from", from), ("day_to", to)]) + paging(1, pageSize))
    }

    /// `GET /site-checkins/{id}`.
    public static func siteCheckin(_ id: UUID) -> APIRequest<SiteCheckinDTO> { .get("\(tenant)/site-checkins/\(id.lowercased)") }
}

// MARK: - Wording (strings doc "DEC-031 Phase 5 — oversight", owner.score.* / owner.dash.* / owner.unbilled.* /
// owner.idle.*)

public enum OversightTexts {
    // Scorecard list
    public static let scoreMore = "People scorecard"
    public static let scoreTitle = "People scorecard"
    public static let scoreEmpty = "No one to show for this period."
    public static let scoreFooter = "Counts of items to look at for each person, most first. A count is not a verdict: open the person to see each record."
    public static func items(_ n: Int) -> String {
        switch n {
        case 0: "Nothing to look at"
        case 1: "1 item to look at"
        default: "\(n) items to look at"
        }
    }
    public static let inactive = "Inactive"

    // Person
    public static let figures = "Figures"
    public static let period = "Period"
    public static let machines = "Machines responsible for"
    public static let reportsMissing = "Daily reports missing"
    public static let reportsLate = "Daily reports late"
    public static let unexplained = "Unexplained engine hours"
    public static func unexplainedValue(hours: String, n: Int) -> String { "\(hours) h · \(n) items" }
    public static let alerts = "Alerts"
    public static func alertsValue(n: Int, open: Int) -> String { "\(n) · \(open) open" }
    public static let ackTime = "Time to acknowledge"
    public static func ackTimeValue(avg: String, max: String) -> String { "average \(avg) h · longest \(max) h" }
    public static let cashHeldTooLong = "Cash held too long"
    public static let cashDifferences = "Cash differences"
    public static let nearThreshold = "Near the case threshold"
    public static let revenueDifferences = "Revenue differences"
    public static let refused = "Refused attempts"
    public static let checkins = "Site check-ins"
    public static func checkinsValue(made: Int, missed: Int) -> String { "\(made) made · \(missed) missed" }
    public static let patterns = "Repeated patterns"
    public static let cashHeld = "Cash held now"
    public static func heldSince(date: String, days: Int?) -> String { "since \(date)" + (days.map { " (\(Self.days($0)))" } ?? "") }
    public static let records = "Records"
    public static let recordsEmpty = "No records in this period."
    public static func scheduled(_ time: String) -> String { "Scheduled \(time)" }

    /// `owner.score.item.*` (unknown items humanized).
    public static func item(_ item: ScorecardItem) -> String {
        switch item {
        case .missingDailyReport: "Daily report missing"
        case .lateDailyReport: "Daily report late"
        case .unexplainedHours: "Unexplained engine hours"
        case .alert: "Alert"
        case .cashHeldTooLong: "Cash held too long"
        case .cashDifference: "Cash difference"
        case .revenueDifference: "Revenue difference"
        case .refusedAttempt: "Refused attempt"
        case .missedCheckin: "Missed site check-in"
        case .patternSignal: "Repeated pattern"
        default: OwnerFormat.humanize(item.rawValue)
        }
    }

    // Dashboard tiles
    public static let dashUnbilled = "Unbilled work"
    public static let dashUnbilledJobs = "Jobs"
    public static let dashUnbilledValue = "Value"
    public static let dashOldest = "Oldest"
    public static func dashUnbilledFooter(_ days: String) -> String { "Completed jobs not on an issued invoice after \(days)." }
    public static let dashIdle = "Idle machines"
    public static let dashIdleMachines = "Machines"
    public static let dashLongestIdle = "Longest idle"
    public static func dashIdleFooter(_ days: String) -> String { "Machines with no running job and no engine hours for \(days)." }

    // Unbilled work
    public static let unbilledTitle = "Unbilled work"
    public static let unbilledEmpty = "No completed jobs waiting for an invoice."
    public static func unbilledRow(job: String, customer: String) -> String { "\(job) · \(customer)" }
    public static func unbilledCompleted(date: String, days: String) -> String { "Completed \(date) · \(days) unbilled" }
    public static let unbilledDraft = "On a draft invoice"
    public static let unbilledFooter = "Completed jobs not on an issued invoice yet. Invoices are made on the web."

    // Idle machines
    public static let idleTitle = "Idle machines"
    public static let idleEmpty = "No idle machines."
    public static func idleSince(date: String, days: String) -> String { "Idle since \(date) (\(days))" }
    public static func idleLastJob(job: String, date: String) -> String { "Last job \(job) completed \(date)" }
    public static func idlePlanned(_ job: String) -> String { "Planned job \(job)" }
    public static let idleFooter = "Machines with no running job and no engine hours for a while."

    /// "1 day" / "{n} days".
    public static func days(_ n: Int) -> String { n == 1 ? "1 day" : "\(n) days" }
}

// MARK: - Presentation

/// Scorecard period chips (owner.score.period.*): local days, at most 93.
public enum ScorecardPeriod: String, CaseIterable, Sendable, Hashable {
    case last7Days, last30Days, thisMonth, lastMonth

    public static let `default` = ScorecardPeriod.last30Days

    public var label: String {
        switch self {
        case .last7Days: "Last 7 days"
        case .last30Days: "Last 30 days"
        case .thisMonth: "This month"
        case .lastMonth: "Last month"
        }
    }

    /// (day_from, day_to) as local `YYYY-MM-DD`.
    public func range(now: Date = Date(), timeZone: TimeZone = .current) -> (from: String, to: String) {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        let day = { (d: Date) in CashRecordPresentation.localDay(d, timeZone: timeZone) }
        let monthStart = calendar.date(from: calendar.dateComponents([.year, .month], from: now)) ?? now
        switch self {
        case .last7Days: return (day(calendar.date(byAdding: .day, value: -6, to: now) ?? now), day(now))
        case .last30Days: return (day(calendar.date(byAdding: .day, value: -29, to: now) ?? now), day(now))
        case .thisMonth: return (day(monthStart), day(now))
        case .lastMonth:
            let start = calendar.date(byAdding: .month, value: -1, to: monthStart) ?? monthStart
            let end = calendar.date(byAdding: .day, value: -1, to: monthStart) ?? monthStart
            return (day(start), day(end))
        }
    }
}

/// One list row: headline, subtitle, caption (and an optional trailing value).
public struct OversightRow: Hashable, Sendable {
    public let title: String
    public let subtitle: String
    public let caption: String?
    public let trailing: String?
}

/// One record behind a person's scorecard: what it shows and the screen it opens (nil: details only).
public struct ScorecardRecordRow: Hashable, Sendable {
    public let label: String
    public let value: String?
    public let caption: String
    public let route: OwnerRoute?
}

/// Pure presentation of the scorecard, unbilled work and idle machines (as Android `OversightPresentation`).
public enum OversightPresentation {
    typealias T = OversightTexts

    static func formatter(_ format: String, _ timeZone: TimeZone) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = timeZone
        f.dateFormat = format
        return f
    }

    /// "26 Oct 2026".
    public static func date(_ date: Date, timeZone: TimeZone = .current) -> String { formatter("d MMM yyyy", timeZone).string(from: date) }

    static func h(_ value: DecimalString) -> String { OwnerFormat.hoursNumber(value) }

    public static func name(_ r: ScorecardRowDTO) -> String { DisplayName.or(r.staffMemberName, id: r.staffMemberID) }

    /// Most items first, then by name.
    public static func sorted(_ rows: [ScorecardRowDTO]) -> [ScorecardRowDTO] {
        rows.sorted {
            $0.itemsTotal != $1.itemsTotal ? $0.itemsTotal > $1.itemsTotal
                : name($0).localizedCaseInsensitiveCompare(name($1)) == .orderedAscending
        }
    }

    /// The non-zero figures in the documented order (the list shows the first three).
    public static func figures(_ r: ScorecardRowDTO) -> [String] {
        var out: [String] = []
        func add(_ n: Int, _ text: String) { if n > 0 { out.append("\(n) \(text)") } }
        add(r.dailyReportsMissing, "missing reports")
        add(r.dailyReportsLate, "late reports")
        if r.unexplainedHours.value > 0 { out.append("\(h(r.unexplainedHours)) h unexplained") }
        add(r.alertsOpen, "open alerts")
        add(r.cashHeldTooLong, "cash held too long")
        add(r.cashDifferences, "cash differences")
        add(r.revenueDifferences, "revenue differences")
        add(r.refusedAttempts, "refused attempts")
        add(r.checkinsMissed ?? 0, "missed check-ins")
        add(r.patternSignals, "repeated patterns")
        return out
    }

    public static func row(_ r: ScorecardRowDTO) -> OversightRow {
        let caption = figures(r).prefix(3).joined(separator: " · ")
        return OversightRow(title: name(r), subtitle: ([T.items(r.itemsTotal)] + (r.isActive ? [] : [T.inactive])).joined(separator: " · "),
                            caption: caption.isEmpty ? nil : caption, trailing: nil)
    }

    /// "TZS 20,000.00, USD 5.00" (nil when there are none).
    static func money(_ totals: [AmountByCurrencyDTO]) -> String? {
        totals.isEmpty ? nil : totals.map { OwnerFormat.money($0.amount, currency: $0.currency) }.joined(separator: ", ")
    }

    /// The person's Figures rows in the documented order.
    public static func figureRows(_ r: ScorecardRowDTO) -> [DecisionField] {
        var rows: [(String, String)] = [
            (T.period, RevenuePresentation.period(from: r.dayFrom, to: r.dayTo)), (T.machines, "\(r.machines)"),
            (T.reportsMissing, "\(r.dailyReportsMissing)"), (T.reportsLate, "\(r.dailyReportsLate)"),
            (T.unexplained, T.unexplainedValue(hours: h(r.unexplainedHours), n: r.unexplainedItems)),
            (T.alerts, T.alertsValue(n: r.alerts, open: r.alertsOpen)),
        ]
        if let avg = r.avgHoursToAcknowledge {
            rows.append((T.ackTime, T.ackTimeValue(avg: h(avg), max: r.maxHoursToAcknowledge.map(h) ?? h(avg))))
        }
        rows.append((T.cashHeldTooLong, "\(r.cashHeldTooLong)"))
        rows.append((T.cashDifferences, (["\(r.cashDifferences)"] + [money(r.cashDifferenceTotals)].compactMap { $0 }).joined(separator: " · ")))
        if r.cashDifferencesNearThreshold > 0 { rows.append((T.nearThreshold, "\(r.cashDifferencesNearThreshold)")) }
        rows.append((T.revenueDifferences, (["\(r.revenueDifferences)"] + [money(r.revenueDifferenceTotals)].compactMap { $0 }).joined(separator: " · ")))
        rows.append((T.refused, "\(r.refusedAttempts)"))
        if let missed = r.checkinsMissed { rows.append((T.checkins, T.checkinsValue(made: r.checkinsMade, missed: missed))) }
        rows.append((T.patterns, "\(r.patternSignals)"))
        return rows.map { DecisionField(label: $0.0, value: $0.1) }
    }

    /// Cash held now: label the money, value "since {date} ({days})" (empty when the server sent no date).
    public static func cashHeldRows(_ r: ScorecardRowDTO, timeZone: TimeZone = .current) -> [DecisionField] {
        r.cashHeld.map { c in
            let since = c.heldSince.map { T.heldSince(date: date($0, timeZone: timeZone), days: c.heldDays) }
            return DecisionField(label: OwnerFormat.money(c.amount, currency: c.currency), value: since ?? "")
        }
    }

    /// The screen a record opens, when the app has one and the role may open it.
    public static func route(_ record: ScorecardRecordDTO, features: OwnerFeatures) -> OwnerRoute? {
        let id = record.recordID
        let route: OwnerRoute? = switch record.recordType {
        case "job_exception": id.map(OwnerRoute.exception)
        case "tracking_alert": id.map(OwnerRoute.alert)
        case "cash_remittance_overdue": id.map(OwnerRoute.overdueRemittance)
        case "cash_variance": id.map { OwnerRoute.decision(.writeOff, $0) }
        case "revenue_difference": id.map(OwnerRoute.revenueDifference)
        case "risk_signal": record.detail?["case_id"]?.stringValue.flatMap(UUID.init(uuidString:)).map(OwnerRoute.investigation)
        case "engine_interval": record.machineID.map(OwnerRoute.machine)
        default: nil
        }
        guard let route, features.allows(route), features.route(route) == route else { return nil }
        return route
    }

    /// One record row: item, money or hours, then day · machine · job · status and the item's own details.
    public static func record(_ r: ScorecardRecordDTO, features: OwnerFeatures, timeZone: TimeZone = .current) -> ScorecardRecordRow {
        let value: String? = if let amount = r.amount, let currency = r.currency {
            OwnerFormat.money(amount, currency: currency)
        } else {
            r.hours.map { "\(h($0)) h" }
        }
        let machine = (r.machineCode ?? r.machineName) == nil ? nil : DisplayName.machine(code: r.machineCode, name: r.machineName, id: nil)
        var parts: [String] = [r.day.map(RevenuePresentation.day) ?? date(r.at, timeZone: timeZone), machine, r.jobNumber,
                               r.status.map(OwnerFormat.humanize)].compactMap { $0 }.filter { !$0.isEmpty }
        if r.nearThreshold { parts.append(T.nearThreshold) }
        switch r.item {
        case .alert:
            if let title = r.detail?["title"]?.stringValue, !title.isEmpty { parts.append(title) }
        case .missedCheckin:
            if let at = r.detail?["scheduled_at"]?.stringValue.flatMap(AssetaJSON.parseInstant) {
                parts.append(T.scheduled(formatter("HH:mm", timeZone).string(from: at)))
            }
        case .refusedAttempt:
            for key in ["action", "permission"] {
                if let text = r.detail?[key]?.stringValue, !text.isEmpty { parts.append(text) }
            }
        default: break
        }
        return ScorecardRecordRow(label: T.item(r.item), value: value, caption: parts.joined(separator: " · "),
                                  route: route(r, features: features))
    }

    /// Records newest first.
    public static func records(_ detail: ScorecardDetailDTO, features: OwnerFeatures, timeZone: TimeZone = .current) -> [ScorecardRecordRow] {
        detail.records.sorted { $0.at > $1.at }.map { record($0, features: features, timeZone: timeZone) }
    }

    // Unbilled work

    public static func unbilledSorted(_ items: [UnbilledJobDTO]) -> [UnbilledJobDTO] {
        items.sorted { $0.daysUnbilled > $1.daysUnbilled }
    }

    public static func unbilled(_ u: UnbilledJobDTO, timeZone: TimeZone = .current) -> OversightRow {
        let machine = DisplayName.machine(code: u.machineCode, name: u.machineName, id: u.machineID)
        let subtitle = ([machine] + [u.jobSiteName].compactMap { $0 }.filter { !$0.isEmpty }).joined(separator: " · ")
        let caption = T.unbilledCompleted(date: date(u.completedAt, timeZone: timeZone), days: T.days(u.daysUnbilled))
            + (u.draftInvoiceID != nil ? " · " + T.unbilledDraft : "")
        return OversightRow(title: T.unbilledRow(job: u.jobNumber ?? "—", customer: DisplayName.or(u.customerName, id: u.customerID)),
                            subtitle: subtitle, caption: caption, trailing: u.total.map { OwnerFormat.money($0, currency: u.currency) })
    }

    // Idle machines

    public static func idleSorted(_ items: [IdleMachineDTO]) -> [IdleMachineDTO] { items.sorted { $0.idleDays > $1.idleDays } }

    /// Headline machine, caption idle since, second caption the last job and the planned job.
    public static func idle(_ m: IdleMachineDTO, timeZone: TimeZone = .current) -> OversightRow {
        var more: [String] = []
        if m.lastJobID != nil {
            more.append(T.idleLastJob(job: m.lastJobNumber ?? "—", date: m.lastJobCompletedAt.map { date($0, timeZone: timeZone) } ?? "—"))
        }
        if m.plannedJobID != nil { more.append(T.idlePlanned(m.plannedJobNumber ?? "—")) }
        return OversightRow(title: DisplayName.machine(code: m.machineCode, name: m.machineName, id: m.machineID),
                            subtitle: T.idleSince(date: date(m.idleSince, timeZone: timeZone), days: T.days(m.idleDays)),
                            caption: more.isEmpty ? nil : more.joined(separator: " · "), trailing: nil)
    }

    // Dashboard tiles

    /// The Unbilled work and Idle machines tiles (hidden when null or switched off); each links to its list.
    public static func tiles(unbilled: JSONValue?, idle: JSONValue?, off: Set<String>) -> [DashboardTile] {
        var out: [DashboardTile] = []
        if !off.contains(TenantCapability.unbilledWork), let u = unbilled, u != .null {
            var amounts: [String] = []
            if case let .array(items)? = u["amounts"] {
                for item in items {
                    guard let currency = item["currency"]?.stringValue,
                          let amount = item["amount"]?.stringValue.flatMap({ DecimalString(string: $0) }) else { continue }
                    amounts.append(OwnerFormat.money(amount, currency: currency))
                }
            }
            var rows: [DashboardTile.Row] = [
                .init(T.dashUnbilledJobs, "\(u["count"]?.intValue ?? 0)"),
                .init(T.dashUnbilledValue, amounts.isEmpty ? OwnerAccountabilityTexts.dashNone : amounts.joined(separator: ", ")),
            ]
            if let oldest = u["oldest_days"]?.intValue { rows.append(.init(T.dashOldest, T.days(oldest))) }
            out.append(DashboardTile(id: "unbilled_work", title: T.dashUnbilled, rows: rows, route: .unbilledWork,
                                     footer: u["after_days"]?.intValue.map { T.dashUnbilledFooter(T.days($0)) }))
        }
        if !off.contains(TenantCapability.idleMachines), let i = idle, i != .null {
            var rows: [DashboardTile.Row] = [.init(T.dashIdleMachines, "\(i["count"]?.intValue ?? 0)")]
            if let longest = i["longest_idle_days"]?.intValue { rows.append(.init(T.dashLongestIdle, T.days(longest))) }
            out.append(DashboardTile(id: "idle_machines", title: T.dashIdle, rows: rows, route: .idleMachines,
                                     footer: i["after_days"]?.intValue.map { T.dashIdleFooter(T.days($0)) }))
        }
        return out
    }
}
