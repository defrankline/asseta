import AssetaModel
import AssetaStore
import Foundation

// Supervisor inbox rules shared by every list and detail screen (word for word the Android
// `core:domain` InboxRules.kt): one combined status per record from the local outbox state and the
// server's copy, matching local records to server records, and the small derived figures.

/// Colour family of a status pill (the views map it onto the palette).
public enum Tone: Sendable { case neutral, good, warning, bad, info }

/// The one status pill a record shows. `needsAttention` items are listed in the Inbox.
public enum InboxStatus: String, Sendable, CaseIterable {
    case waiting, notSynced, synced, accepted, provisional, flagged, reviewed, rejected, superseded
    case pendingApproval, approved, claimed, verified, pending, recorded

    public var label: String {
        switch self {
        case .waiting: "Waiting to sync"
        case .notSynced: "Not synced"
        case .synced: "Synced"
        case .accepted: "Accepted"
        case .provisional: "Provisional"
        case .flagged: "Flagged"
        case .reviewed: "Reviewed"
        case .rejected: "Rejected"
        case .superseded: "Superseded"
        case .pendingApproval: "Pending approval"
        case .approved: "Approved"
        case .claimed: "Awaiting verification"
        case .verified: "Verified"
        case .pending: "Pending"
        case .recorded: "Recorded"
        }
    }

    public var tone: Tone {
        switch self {
        case .waiting, .superseded: .neutral
        case .notSynced, .rejected: .bad
        case .synced, .accepted, .approved, .verified, .recorded: .good
        case .provisional, .flagged, .pendingApproval, .claimed, .pending: .warning
        case .reviewed: .info
        }
    }

    public var needsAttention: Bool { self == .notSynced || self == .flagged || self == .rejected }
}

public enum InboxStatusRules {
    /// A record known only on this phone: waiting (pending, sending, held), refused, or acknowledged.
    public static func local(_ status: ClientOperationStatus) -> InboxStatus {
        switch status {
        case .pending, .sent, .quarantined: .waiting
        case .failed, .conflict: .notSynced
        case .acked: .synced
        }
    }

    /// Rejected or superseded first, then open findings (flagged), reviewed findings, then the state.
    public static func reading(state: String, reviewStatus: String, findingStatuses: [String]) -> InboxStatus {
        if state == "REJECTED" { return .rejected }
        if state == "SUPERSEDED" { return .superseded }
        if reviewStatus == "PENDING_REVIEW" || findingStatuses.contains("OPEN") { return .flagged }
        if reviewStatus == "REVIEWED" || !findingStatuses.isEmpty { return .reviewed }
        return state == "PROVISIONAL" ? .provisional : .accepted
    }

    public static func expense(_ status: String) -> InboxStatus {
        switch status {
        case "APPROVED": .approved
        case "REJECTED": .rejected
        default: .pendingApproval
        }
    }

    /// Cash collections and handovers (CLAIMED until the office verifies or rejects them).
    public static func settlement(_ status: String) -> InboxStatus {
        switch status {
        case "VERIFIED": .verified
        case "REJECTED": .rejected
        default: .claimed
        }
    }

    public static func reset(_ status: String) -> InboxStatus {
        switch status {
        case "APPROVED": .approved
        case "REJECTED": .rejected
        default: .pending
        }
    }

    /// The server's copy wins once it arrived; until then the local outbox state.
    public static func combined(local: ClientOperationStatus?, server: InboxStatus?) -> InboxStatus {
        server ?? local.map(Self.local) ?? .waiting
    }
}

/// A local record for matching: its entity id (client id / capture id) and server id once acked.
public struct LocalKey: Sendable, Equatable {
    public let entityID: UUID
    public let serverID: UUID?

    public init(entityID: UUID, serverID: UUID?) {
        self.entityID = entityID
        self.serverID = serverID
    }

    var keys: [UUID] { [entityID] + (serverID.map { [$0] } ?? []) }
}

/// One list row: the server's copy, the local one, or both once matched.
public struct Merged<S, L> {
    public let server: S?
    public let local: L?
}

public enum InboxMerge {
    /// Pairs server records with local records: a local record matches the server record whose id or
    /// client id equals the local entity id (client id / capture id) or the server id the
    /// acknowledgement returned. Every record appears exactly once; local records without a server
    /// copy stay (waiting to sync, refused, or acked but not yet pulled).
    public static func merge<S, L>(server: [S], local: [L], serverKeys: (S) -> [UUID],
                                   localKey: (L) -> LocalKey) -> [Merged<S, L>] {
        var byKey: [UUID: Int] = [:]
        for (index, record) in server.enumerated() {
            for key in serverKeys(record) where byKey[key] == nil { byKey[key] = index }
        }
        var matched: [Int: L] = [:]
        var unmatched: [L] = []
        for record in local {
            let index = localKey(record).keys.lazy.compactMap { byKey[$0] }.first
            if let index, matched[index] == nil { matched[index] = record } else { unmatched.append(record) }
        }
        return server.enumerated().map { Merged(server: $0.element, local: matched[$0.offset]) }
            + unmatched.map { Merged(server: nil, local: $0) }
    }
}

/// Work-log entry for totals (server activity or local entry); `end` nil while running.
public struct WorkSpan: Sendable, Equatable {
    public let activityType: String
    public let start: Date
    public let end: Date?

    public init(activityType: String, start: Date, end: Date?) {
        self.activityType = activityType
        self.start = start
        self.end = end
    }
}

public enum JobFigures {
    /// Total minutes per activity type (running entries count up to `now`), types in first-seen order.
    public static func minutesByType(_ spans: [WorkSpan], now: Date) -> [(type: String, minutes: Int)] {
        var order: [String] = []
        var totals: [String: Int] = [:]
        for span in spans.sorted(by: { $0.start < $1.start }) where span.activityType != "NOTE" {
            let end = span.end ?? now
            if totals[span.activityType] == nil { order.append(span.activityType) }
            totals[span.activityType, default: 0] += max(0, Int(end.timeIntervalSince(span.start))) / 60
        }
        return order.map { ($0, totals[$0] ?? 0) }
    }

    /// Closing minus opening reading (meter hours), or nil until both are known (or when negative).
    public static func meterHours(opening: String?, closing: String?) -> Decimal? {
        guard let o = opening.flatMap(Self.decimal), let c = closing.flatMap(Self.decimal) else { return nil }
        let hours = c - o
        return hours >= 0 ? hours : nil
    }

    /// "2 h 05 min" / "45 min".
    public static func duration(minutes: Int) -> String {
        minutes >= 60 ? "\(minutes / 60) h \(String(format: "%02d", minutes % 60)) min" : "\(minutes) min"
    }

    static func decimal(_ text: String) -> Decimal? {
        Decimal(string: text, locale: Locale(identifier: "en_US_POSIX"))
    }
}

/// What tapping a server notification opens (from its `target`).
public enum InboxLink: Sendable, Equatable {
    /// `machine`: a machine of mine (missing daily report, unexplained engine hours).
    case job(UUID), expense(UUID), money, machine(UUID), none
    /// A transfer (`isFloat` false) or float sent to me: its answer when still waiting, else the Money tab.
    case cashToAcknowledge(UUID, isFloat: Bool)
    /// One of my requests to keep cash (its status).
    case retention(UUID)
    /// An overdue-remittance flag of mine ("Overdue remittance"; the Money tab when it cannot be read).
    case remittanceOverdue(UUID)

    /// The exact record when the notification names one (`data.kind` + `record_id`), else its target.
    public static func from(_ notification: NotificationDTO) -> InboxLink {
        if let record = notification.dataRecord, let link = from(record: record) { return link }
        return from(entity: notification.target?.entity, id: notification.target?.id)
    }

    /// The field app's screen of an accountability record; nil for kinds it does not show (the caller falls back).
    public static func from(record: RecordRef) -> InboxLink? {
        switch record.kind {
        case .cashTransfer: .cashToAcknowledge(record.id, isFloat: false)
        case .cashFloat: .cashToAcknowledge(record.id, isFloat: true)
        case .cashRetention: .retention(record.id)
        case .remittanceOverdue: .remittanceOverdue(record.id)
        // DEC-031 Phase 5: UNBILLED_WORK names the job.
        case .job: .job(record.id)
        default: nil
        }
    }

    public static func from(entity: String?, id: String?) -> InboxLink {
        if let record = RecordKind.resolve(kind: nil, recordID: nil, entity: entity, entityID: id),
           let link = from(record: record) {
            return link
        }
        let uuid = id.flatMap(UUID.init(uuidString:))
        switch entity {
        case "job": return uuid.map(InboxLink.job) ?? .none
        case "expense": return uuid.map(InboxLink.expense) ?? .none
        case "staff_member", "cash_custody": return .money
        // Cash transfers and floats to acknowledge are answered on the Money tab.
        case "cash_transfer", "supervisor_cash_custody", "cash_remittance_overdue": return .money
        case "machine": return uuid.map(InboxLink.machine) ?? .none
        default: return .none
        }
    }
}

/// Offline checks of a meter reset request (the server re-validates; reason 10…2000 characters).
public enum ResetRules {
    public static let minReason = 10
    public static let maxReason = 2000

    public static func validate(oldReading: String, newReading: String, reason: String, hasPhoto: Bool) -> [String] {
        var issues: [String] = []
        if parse(oldReading) == nil { issues.append("Enter the reading before the reset (a number).") }
        if parse(newReading) == nil { issues.append("Enter the reading after the reset (a number).") }
        let r = reason.trimmingCharacters(in: .whitespacesAndNewlines)
        if r.count < minReason { issues.append("Explain the reset in at least \(minReason) characters.") }
        if r.count > maxReason { issues.append("The reason can be at most \(maxReason) characters.") }
        if !hasPhoto { issues.append("Take a photo of the meter as evidence.") }
        return issues
    }

    /// A non-negative decimal ("," accepted), as the plain wire string, or nil.
    public static func parse(_ text: String) -> String? {
        let t = text.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: ".")
        guard t.range(of: #"^\d+(\.\d+)?$"#, options: .regularExpression) != nil,
              let value = Decimal(string: t, locale: Locale(identifier: "en_US_POSIX")) else { return nil }
        var copy = value
        return NSDecimalString(&copy, Locale(identifier: "en_US_POSIX"))
    }
}

/// User-facing wording of server findings (same words on Android).
public enum FindingTexts {
    public static func type(_ code: String) -> String {
        switch code {
        case "GPS_UNAVAILABLE": "No GPS position"
        case "GPS_INACCURATE": "GPS position not accurate enough"
        case "GPS_STALE": "GPS position too old"
        case "LOCATION_MISMATCH": "Not at the job site"
        case "MODE_POLICY_VIOLATION": "Capture mode not allowed"
        case "PHOTO_MISSING": "Photo missing"
        case "LOW_OCR_CONFIDENCE": "Meter photo hard to read"
        case "MANUAL_CORRECTION": "Reading corrected by hand"
        case "METER_DECREASE": "Reading lower than before"
        case "IMPOSSIBLE_INCREMENT": "Reading increased too much"
        case "CONTINUITY_GAP": "Gap since the last reading"
        case "DUPLICATE_IMAGE": "Photo used before"
        case "TELEMETRY_MISMATCH": "Does not match the tracker"
        case "CLOCK_SKEW": "Phone clock was wrong"
        case "POLICY_SNAPSHOT_UNVERIFIED": "Capture rules could not be verified"
        case "HOURS_OVERRUN": "Hours beyond purchase"
        case "UNEXPLAINED_HOURS": "Engine hours not yet explained"
        case "MISSING_DAILY_REPORT": "Daily report missing"
        case "OVERLAPPING_ALLOCATION": "Overlaps another job's hours"
        case "OVERLAPPING_ACTIVITY": "Overlapping work log entries"
        default: InboxTexts.sentence(code)
        }
    }

    public static func severity(_ code: String) -> String { InboxTexts.sentence(code) }

    public static func review(_ status: String) -> String {
        switch status {
        case "OPEN": "Waiting for review"
        case "EXPLAINED": "Explained"
        case "CONFIRMED": "Confirmed"
        default: InboxTexts.sentence(status)
        }
    }
}
