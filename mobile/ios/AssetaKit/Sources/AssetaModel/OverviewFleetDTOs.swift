import Foundation

// Read DTOs of `GET /tenant/overview`, `/tenant/fleet/map`, `/tenant/fleet/machines/{id}` and
// `/history` (`TenantOverviewDto`, `MachineMapDto`, `HistoryDto` in `contracts/openapi.json`).
// Money stays a decimal string; coordinates are plain JSON numbers in the contract.

// MARK: - Overview

public struct TenantOverviewDTO: Codable, Hashable, Sendable {
    public let tenantID: UUID
    /// When the server computed the overview.
    public let asOf: Date
    public let timezone: String
    /// A section is `nil` when the caller lacks its permission.
    public let fleet: OverviewFleetSection?
    public let work: OverviewWorkSection?
    public let money: OverviewMoneySection?
    public let risk: OverviewRiskSection?

    enum CodingKeys: String, CodingKey {
        case tenantID = "tenant_id", asOf = "as_of", timezone, fleet, work, money, risk
    }
}

public struct OverviewConnectivityCounts: Codable, Hashable, Sendable {
    public let live: Int
    public let recent: Int
    public let stale: Int
    public let offline: Int
    public let never: Int
    public let noTracker: Int

    enum CodingKeys: String, CodingKey { case live, recent, stale, offline, never, noTracker = "no_tracker" }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        live = try c.decodeIfPresent(Int.self, forKey: .live) ?? 0
        recent = try c.decodeIfPresent(Int.self, forKey: .recent) ?? 0
        stale = try c.decodeIfPresent(Int.self, forKey: .stale) ?? 0
        offline = try c.decodeIfPresent(Int.self, forKey: .offline) ?? 0
        never = try c.decodeIfPresent(Int.self, forKey: .never) ?? 0
        noTracker = try c.decodeIfPresent(Int.self, forKey: .noTracker) ?? 0
    }
}

public struct OverviewSeverityCounts: Codable, Hashable, Sendable {
    public let critical: Int
    public let warning: Int
    public let info: Int

    public var total: Int { critical + warning + info }

    public init(critical: Int, warning: Int, info: Int) {
        self.critical = critical
        self.warning = warning
        self.info = info
    }

    enum CodingKeys: String, CodingKey { case critical, warning, info }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        critical = try c.decodeIfPresent(Int.self, forKey: .critical) ?? 0
        warning = try c.decodeIfPresent(Int.self, forKey: .warning) ?? 0
        info = try c.decodeIfPresent(Int.self, forKey: .info) ?? 0
    }
}

public struct OverviewFleetSection: Codable, Hashable, Sendable {
    public let machines: Int
    public let connectivity: OverviewConnectivityCounts
    public let reportedWorkState: [String: Int]
    public let engineOnVerified: Int
    public let openAlerts: OverviewSeverityCounts
    /// Freshest underlying data this section was computed from.
    public let latestSourceAt: Date?

    enum CodingKeys: String, CodingKey {
        case machines, connectivity
        case reportedWorkState = "reported_work_state", engineOnVerified = "engine_on_verified"
        case openAlerts = "open_alerts", latestSourceAt = "latest_source_at"
    }
}

public struct OverviewWorkSection: Codable, Hashable, Sendable {
    public let jobsByStatus: [String: Int]
    /// `nil` when the caller lacks the permission behind the count.
    public let pendingApprovals: Int?
    public let readingsNeedingReview: Int?
    public let openExceptions: Int?
    public let latestSourceAt: Date?

    enum CodingKeys: String, CodingKey {
        case jobsByStatus = "jobs_by_status", pendingApprovals = "pending_approvals"
        case readingsNeedingReview = "readings_needing_review", openExceptions = "open_exceptions"
        case latestSourceAt = "latest_source_at"
    }
}

public struct OverviewCurrencyMoney: Codable, Hashable, Sendable, Identifiable {
    public let currency: String
    public let receivablesOutstanding: DecimalString
    public let receivablesOverdue: DecimalString
    public let overdueInvoices: Int
    public let verifiedReceiptsMTD: DecimalString
    public let approvedExpensesMTD: DecimalString
    public let cashWithSupervisors: DecimalString

    public var id: String { currency }

    enum CodingKeys: String, CodingKey {
        case currency
        case receivablesOutstanding = "receivables_outstanding", receivablesOverdue = "receivables_overdue"
        case overdueInvoices = "overdue_invoices", verifiedReceiptsMTD = "verified_receipts_mtd"
        case approvedExpensesMTD = "approved_expenses_mtd", cashWithSupervisors = "cash_with_supervisors"
    }
}

public struct OverviewMoneySection: Codable, Hashable, Sendable {
    /// Calendar date (`YYYY-MM-DD`) the month-to-date figures start from.
    public let monthStart: String
    public let currencies: [OverviewCurrencyMoney]
    public let latestSourceAt: Date?

    enum CodingKeys: String, CodingKey {
        case monthStart = "month_start", currencies, latestSourceAt = "latest_source_at"
    }
}

public struct OverviewRiskSection: Codable, Hashable, Sendable {
    public let openCases: OverviewSeverityCounts?
    public let signalsLast7Days: OverviewSeverityCounts?
    public let latestSourceAt: Date?

    enum CodingKeys: String, CodingKey {
        case openCases = "open_cases", signalsLast7Days = "signals_last_7_days", latestSourceAt = "latest_source_at"
    }
}

// MARK: - Fleet map

public struct Connectivity: OpenStringEnum {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let live = Connectivity(rawValue: "LIVE")
    public static let recent = Connectivity(rawValue: "RECENT")
    public static let stale = Connectivity(rawValue: "STALE")
    public static let offline = Connectivity(rawValue: "OFFLINE")
    public static let neverReported = Connectivity(rawValue: "NEVER_REPORTED")
    public static let noTracker = Connectivity(rawValue: "NO_TRACKER")
}

/// `ON|OFF|MOVING|STATIONARY|UNKNOWN` (engine or motion as observed from telemetry).
public struct ObservedState: OpenStringEnum {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let on = ObservedState(rawValue: "ON")
    public static let off = ObservedState(rawValue: "OFF")
    public static let moving = ObservedState(rawValue: "MOVING")
    public static let stationary = ObservedState(rawValue: "STATIONARY")
    public static let unknown = ObservedState(rawValue: "UNKNOWN")
}

public struct LocationCompliance: OpenStringEnum {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let compliant = LocationCompliance(rawValue: "COMPLIANT")
    public static let nonCompliant = LocationCompliance(rawValue: "NON_COMPLIANT")
    public static let unknown = LocationCompliance(rawValue: "UNKNOWN")
}

/// One machine's last-known status (`MachineMapDto`).
public struct MachineMapDTO: Codable, Hashable, Sendable, Identifiable {
    public let machineID: UUID
    public let assetCode: String
    public let name: String
    public let machineStatus: String
    public let longitude: Double?
    public let latitude: Double?
    public let accuracyM: Double?
    public let positionTime: Date?
    public let lastMessageAt: Date?
    public let lastSeenAgeSeconds: Int?
    public let positionSource: String?
    public let positionQuality: String?
    public let connectivity: Connectivity
    public let isLive: Bool
    public let reportedWorkStatus: String
    public let observedEngine: ObservedState
    public let observedMotion: ObservedState
    public let locationCompliance: LocationCompliance
    public let trackerID: UUID?
    public let trackerState: String?
    public let supervisor: String?
    public let `operator`: String?
    public let openAlerts: Int
    public let policyVersion: String

    public var id: UUID { machineID }

    /// Both coordinates present (a machine without a fix is listed but not placed on the map).
    public var hasPosition: Bool { latitude != nil && longitude != nil }

    enum CodingKeys: String, CodingKey {
        case machineID = "machine_id", assetCode = "asset_code", name, machineStatus = "machine_status"
        case longitude, latitude, accuracyM = "accuracy_m", positionTime = "position_time"
        case lastMessageAt = "last_message_at", lastSeenAgeSeconds = "last_seen_age_seconds"
        case positionSource = "position_source", positionQuality = "position_quality", connectivity
        case isLive = "is_live", reportedWorkStatus = "reported_work_status", observedEngine = "observed_engine"
        case observedMotion = "observed_motion", locationCompliance = "location_compliance"
        case trackerID = "tracker_id", trackerState = "tracker_state", supervisor, `operator`
        case openAlerts = "open_alerts", policyVersion = "policy_version"
    }
}

// MARK: - History

public struct TrackPointDTO: Codable, Hashable, Sendable {
    public let eventTime: Date
    public let longitude: Double
    public let latitude: Double
    public let accuracyM: Double?
    public let speedKmh: Double?
    public let headingDeg: Double?
    public let ignition: Bool?
    public let quality: String
    public let isLate: Bool
    public let receivedAt: Date

    enum CodingKeys: String, CodingKey {
        case eventTime = "event_time", longitude, latitude, accuracyM = "accuracy_m", speedKmh = "speed_kmh"
        case headingDeg = "heading_deg", ignition, quality, isLate = "is_late", receivedAt = "received_at"
    }
}

public struct StopDTO: Codable, Hashable, Sendable {
    public let start: Date
    public let end: Date
    public let durationSeconds: Int
    public let longitude: Double
    public let latitude: Double

    enum CodingKeys: String, CodingKey { case start, end, durationSeconds = "duration_seconds", longitude, latitude }
}

public struct SiteVisitDTO: Codable, Hashable, Sendable {
    public let geofenceID: UUID
    public let geofenceName: String
    public let enteredAt: Date?
    public let exitedAt: Date?
    public let durationSeconds: Int

    enum CodingKeys: String, CodingKey {
        case geofenceID = "geofence_id", geofenceName = "geofence_name", enteredAt = "entered_at"
        case exitedAt = "exited_at", durationSeconds = "duration_seconds"
    }
}

public struct HistoryDTO: Codable, Hashable, Sendable {
    public let machineID: UUID
    public let points: [TrackPointDTO]
    /// The server capped the number of points; the track is incomplete.
    public let truncated: Bool
    public let stops: [StopDTO]
    public let distanceKm: Double
    public let siteVisits: [SiteVisitDTO]
    public let policyVersion: String

    enum CodingKeys: String, CodingKey {
        case machineID = "machine_id", points, truncated, stops, distanceKm = "distance_km"
        case siteVisits = "site_visits", policyVersion = "policy_version"
    }
}
