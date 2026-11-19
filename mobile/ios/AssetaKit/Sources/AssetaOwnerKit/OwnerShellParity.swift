import AssetaModel
import Foundation

// ADR-008 Owner side menu and Home as on Android (`ui/OwnerMenu.kt`, `ui/home/OwnerHomeScreen.kt`): which entries and
// tiles a role sees, the "MORE" group, and the Home figures.

/// One side-menu entry that opens a screen.
public enum OwnerMenuEntry: String, CaseIterable, Hashable, Sendable {
    // Main group (design OwnerSideNav).
    case home, approvals, customers, machines, money, reports, notifications
    // "MORE": the screens kept from before ADR-008, with the gating they always had.
    case setup, dashboard, accountability, lookup, scorecard, fleet, alerts, exceptions, fieldSpend, cash, investigations

    public var label: String {
        switch self {
        case .home: OwnerMenuTexts.home
        case .approvals: OwnerMenuTexts.approvals
        case .customers: OwnerMenuTexts.customers
        case .machines: OwnerMenuTexts.machines
        case .money: OwnerMenuTexts.money
        case .reports: OwnerMenuTexts.reports
        case .notifications: OwnerMenuTexts.notifications
        case .setup: SetupTexts.more
        case .dashboard: OwnerMenuTexts.dashboard
        case .accountability: OwnerAccountabilityTexts.moreAccountability
        case .lookup: ManagementTexts.lookupMore
        case .scorecard: OversightTexts.scoreMore
        case .fleet: OwnerMenuTexts.fleet
        case .alerts: OwnerMenuTexts.alerts
        case .exceptions: OwnerMenuTexts.exceptions
        case .fieldSpend: OwnerMenuTexts.fieldSpend
        case .cash: OwnerMenuTexts.cash
        case .investigations: OwnerMenuTexts.investigations
        }
    }
}

/// A titled group of the side menu (`header` nil: the first group, untitled).
public struct OwnerMenuGroup: Equatable, Sendable {
    public let header: String?
    public let entries: [OwnerMenuEntry]
}

/// Side-menu wording (Android `MenuTexts`).
public enum OwnerMenuTexts {
    public static let home = "Home"
    public static let approvals = "Approvals"
    public static let customers = "Customers & hours"
    public static let machines = "Machines"
    public static let money = "Money"
    public static let reports = "Reports"
    public static let notifications = "Notifications"
    public static let more = "More"
    public static let dashboard = "Dashboard"
    public static let fleet = "Fleet map"
    public static let alerts = "Alerts"
    public static let exceptions = "Meter exceptions"
    public static let fieldSpend = "Field spend"
    public static let cash = "Cash with supervisors"
    public static let investigations = "Investigations"
    public static let switchCompany = "Switch company"
    public static let settings = "Settings"
    public static let signOut = "Sign out"
    public static let readOnly = "This company is read-only. Viewing only."
    /// Sign-out dialog (Settings wording): title, confirm, cancel.
    public static let signOutConfirm = "Sign out?"
    public static let signOutAction = "Sign out"
    public static let signOutBody = "Your company's records stay safe on Asseta. This only removes the copy kept on this phone for offline viewing."
    public static let cancel = "Cancel"
}

extension OwnerFeatures {
    /// Customers & hours (hours bought, used, left and credit invoices).
    public var customersScreen: Bool { hoursRead }
    /// Machines: the fleet map and/or this week's machine-report hours.
    public var machinesScreen: Bool { fleet || machineReports }
    /// Money: sales by method and credit invoices (hours on), cash with supervisors (finance).
    public var moneyScreen: Bool { finance || hoursRead }
    /// Reports: machine hours (machine reports), hours sold (hours), money (finance).
    public var reportsScreen: Bool { machineReports || hoursRead || finance }

    /// Whether the role sees `entry` in the side menu.
    public func shows(_ entry: OwnerMenuEntry) -> Bool {
        switch entry {
        case .home: true
        case .approvals: approvalsScreen
        case .customers: customersScreen
        case .machines: machinesScreen
        case .money: moneyScreen
        case .reports: reportsScreen
        case .notifications: notifications
        case .setup: setupRead
        case .dashboard: overview
        case .accountability: accountability
        case .lookup: lookup
        case .scorecard: scorecard
        case .fleet: fleet
        case .alerts: alertsOn
        case .exceptions: meterEvidence
        case .fieldSpend: expenses
        case .cash: finance
        case .investigations: cases
        }
    }

    /// The side menu's groups: the business screens, then "More" with the older screens; an empty group is left out.
    public var menuGroups: [OwnerMenuGroup] {
        let main: [OwnerMenuEntry] = [.home, .approvals, .customers, .machines, .money, .reports, .notifications]
        let more: [OwnerMenuEntry] = [.setup, .dashboard, .accountability, .lookup, .scorecard, .fleet, .alerts, .exceptions,
                                      .fieldSpend, .cash, .investigations]
        return [OwnerMenuGroup(header: nil, entries: main.filter(shows)),
                OwnerMenuGroup(header: OwnerMenuTexts.more, entries: more.filter(shows))].filter { !$0.entries.isEmpty }
    }
}

/// Home wording (Android `HomeTexts`).
public enum OwnerHomeTexts {
    public static let nothing = "Nothing needs your attention right now."
    public static let none = "—"
    public static let notifications = "Notifications"

    /// The bell's accessibility label: "Notifications", or "Notifications, 3 unread" (`99+` above 99).
    public static func bell(unread: Int?) -> String {
        notifications + (OwnerFormat.badge(unread).map { ", \($0) unread" } ?? "")
    }
}

/// Pure Home figures (Android `HomePresentation`).
public enum OwnerHomePresentation {
    /// Cash with supervisors of the overview's first currency, compact ("5.2M"); "—" without it.
    public static func cash(_ overview: TenantOverviewDTO?) -> String {
        overview?.money?.currencies.first.map { OwnerFigures.compactMoney($0.cashWithSupervisors.value) } ?? OwnerHomeTexts.none
    }

    /// Hours of the orders recorded this week (cancelled ones left out): "92 h"; "—" before they load.
    public static func hoursSold(_ orders: [HoursPurchaseDTO]?) -> String {
        guard let orders else { return OwnerHomeTexts.none }
        return OwnerFigures.hours(orders.filter { $0.cancelledAt == nil }.reduce(Decimal(0)) { $0 + $1.hours.value })
    }

    /// Customer hours over all hours of the period's reports (rejected ones left out): "73%"; "—" without hours.
    public static func productive(_ reports: [MachineReportDTO]?) -> String {
        guard let counted = reports?.filter({ $0.state != .rejected }) else { return OwnerHomeTexts.none }
        let total = counted.reduce(Decimal(0)) { $0 + $1.hours.value }
        return OwnerFigures.percent(counted.reduce(Decimal(0)) { $0 + $1.customerHours.value }, of: total) ?? OwnerHomeTexts.none
    }

    /// "Last approved reading 1,510 h" or that there is none yet (overdue rows).
    public static func overdueDetail(_ state: MachineReportStatusDTO) -> String {
        state.lastApprovedReading.map { "Last approved reading \(OwnerFigures.hoursNumber($0.value)) h" } ?? "No approved reading yet"
    }
}
