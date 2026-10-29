import Foundation

// Go-live setup checklist (commit 5a0a2e6). Shapes follow `contracts/openapi.json` (`SetupChecklistDto`,
// `SetupStepDto`, `SetupCheckDto`, `NotNeededDto`, `NotNeededIn`, `ConfirmControlsIn`); same as Android.

/// `StepKey`: the go-live steps, in the server's order. Open so a new server step decodes.
public struct SetupStepKey: OpenStringEnum {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let companySettings = SetupStepKey(rawValue: "COMPANY_SETTINGS")
    public static let people = SetupStepKey(rawValue: "PEOPLE")
    public static let machineTypesAndRates = SetupStepKey(rawValue: "MACHINE_TYPES_AND_RATES")
    public static let machines = SetupStepKey(rawValue: "MACHINES")
    public static let trackers = SetupStepKey(rawValue: "TRACKERS")
    public static let sites = SetupStepKey(rawValue: "SITES")
    public static let customersAndContracts = SetupStepKey(rawValue: "CUSTOMERS_AND_CONTRACTS")
    public static let controlsChosen = SetupStepKey(rawValue: "CONTROLS_CHOSEN")
    public static let reasonLists = SetupStepKey(rawValue: "REASON_LISTS")
    public static let depositAccounts = SetupStepKey(rawValue: "DEPOSIT_ACCOUNTS")
    public static let meterBaselines = SetupStepKey(rawValue: "METER_BASELINES")
    public static let fieldAppSignedIn = SetupStepKey(rawValue: "FIELD_APP_SIGNED_IN")
    public static let firstJob = SetupStepKey(rawValue: "FIRST_JOB")
}

/// `StepStatus`.
public struct SetupStepStatus: OpenStringEnum {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let done = SetupStepStatus(rawValue: "DONE")
    public static let todo = SetupStepStatus(rawValue: "TODO")
    public static let notNeeded = SetupStepStatus(rawValue: "NOT_NEEDED")
    public static let notApplicable = SetupStepStatus(rawValue: "NOT_APPLICABLE")
}

/// `SetupCheckDto`: one part of a step, with the web route that fixes it.
public struct SetupCheckDTO: Codable, Hashable, Sendable, Identifiable {
    public let key: String
    public let label: String
    public let done: Bool
    /// Advice only: never holds the step back.
    public let optional: Bool
    public let doneCount: Int?
    public let totalCount: Int?
    public let link: String
    public let requiredPermission: String

    public var id: String { key }

    enum CodingKeys: String, CodingKey {
        case key, label, done, optional, link
        case doneCount = "done_count", totalCount = "total_count", requiredPermission = "required_permission"
    }
}

/// `NotNeededDto`: set while the owner marked a step as not needed.
public struct SetupNotNeededDTO: Codable, Hashable, Sendable {
    public let reason: String?
    public let markedBy: UUID
    public let markedByName: String?
    public let markedAt: Date

    enum CodingKeys: String, CodingKey {
        case reason, markedBy = "marked_by", markedByName = "marked_by_name", markedAt = "marked_at"
    }
}

/// `SetupStepDto`.
public struct SetupStepDTO: Codable, Hashable, Sendable, Identifiable {
    public let key: SetupStepKey
    public let order: Int
    public let title: String
    public let description: String
    public let status: SetupStepStatus
    public let doneCount: Int?
    public let totalCount: Int?
    /// Web route of the first part still to do.
    public let link: String
    public let requiredPermission: String
    public let canMarkNotNeeded: Bool
    public let notNeeded: SetupNotNeededDTO?
    public let checks: [SetupCheckDTO]

    public var id: String { key.rawValue }

    enum CodingKeys: String, CodingKey {
        case key, order, title, description, status, link, checks
        case doneCount = "done_count", totalCount = "total_count", requiredPermission = "required_permission"
        case canMarkNotNeeded = "can_mark_not_needed", notNeeded = "not_needed"
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        key = try c.decode(SetupStepKey.self, forKey: .key)
        order = try c.decode(Int.self, forKey: .order)
        title = try c.decode(String.self, forKey: .title)
        description = try c.decode(String.self, forKey: .description)
        status = try c.decode(SetupStepStatus.self, forKey: .status)
        doneCount = try c.decodeIfPresent(Int.self, forKey: .doneCount)
        totalCount = try c.decodeIfPresent(Int.self, forKey: .totalCount)
        link = try c.decode(String.self, forKey: .link)
        requiredPermission = try c.decode(String.self, forKey: .requiredPermission)
        canMarkNotNeeded = try c.decode(Bool.self, forKey: .canMarkNotNeeded)
        notNeeded = try c.decodeIfPresent(SetupNotNeededDTO.self, forKey: .notNeeded)
        checks = try c.decodeIfPresent([SetupCheckDTO].self, forKey: .checks) ?? []
    }
}

/// `SetupChecklistDto` (`GET /tenant/setup-checklist`; every write returns it too).
public struct SetupChecklistDTO: Codable, Hashable, Sendable {
    public let steps: [SetupStepDTO]
    /// DONE + NOT_NEEDED steps.
    public let stepsDone: Int
    /// Steps that apply (NOT_APPLICABLE excluded).
    public let stepsTotal: Int
    public let percent: Int
    public let complete: Bool
    public let dismissed: Bool
    public let dismissedBy: UUID?
    public let dismissedByName: String?
    public let dismissedAt: Date?
    public let controlsConfirmedBy: UUID?
    public let controlsConfirmedByName: String?
    public let controlsConfirmedAt: Date?
    public let asOf: Date

    enum CodingKeys: String, CodingKey {
        case steps, percent, complete, dismissed
        case stepsDone = "steps_done", stepsTotal = "steps_total", dismissedBy = "dismissed_by"
        case dismissedByName = "dismissed_by_name", dismissedAt = "dismissed_at"
        case controlsConfirmedBy = "controls_confirmed_by", controlsConfirmedByName = "controls_confirmed_by_name"
        case controlsConfirmedAt = "controls_confirmed_at", asOf = "as_of"
    }

    /// Steps in the server's order.
    public var orderedSteps: [SetupStepDTO] { steps.sorted { ($0.order, $0.key.rawValue) < ($1.order, $1.key.rawValue) } }
}

/// `NotNeededIn` (reason 3 to 500 characters).
public struct SetupNotNeededIn: Codable, Hashable, Sendable {
    public let reason: String
    public init(reason: String) { self.reason = reason }
}

/// `ConfirmControlsIn` (note up to 500 characters, optional).
public struct SetupConfirmControlsIn: Codable, Hashable, Sendable {
    public let note: String?
    public init(note: String?) { self.note = note }
}
