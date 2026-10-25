import AssetaModel
import Foundation

/// `AccountabilitySummaryDto`: the 3.6 oversight list. A tile is null when the tenant's OVERSIGHT policy hides it or
/// the capability behind it is not available (`unavailable_tiles`). Module tiles (customer hours, engine hours,
/// unexplained hours, missing reports) are open objects, read leniently so a newer server never breaks the app.
public struct AccountabilitySummaryDTO: Codable, Hashable, Sendable {
    public let asOf: Date
    public let policyVersion: String
    public let hiddenTiles: [String]
    public let unavailableTiles: [String]
    /// Capabilities the tenant switched off (CUSTOMER_HOURS, ENGINE_HOURS, CASH_CUSTODY): their tiles/rows are hidden.
    public let disabledCapabilities: [String]
    public let customerHours: JSONValue?
    public let hoursAwaitingActivation: JSONValue?
    public let engineHours: JSONValue?
    public let unexplainedHours: JSONValue?
    public let missingDailyReports: JSONValue?
    public let investigations: Investigations?
    public let cash: Cash?
    public let payments: Payments?
    public let discrepancies: Discrepancies?
    public let unauthorizedAttempts: Attempts?
    public let outstandingApprovals: Approvals?

    public struct CountAmount: Codable, Hashable, Sendable {
        public let currency: String
        public let count: Int
        public let amount: DecimalString
    }

    public struct Custodian: Codable, Hashable, Sendable {
        public let staffMemberID: UUID
        public let staffName: String
        public let currency: String
        public let outstanding: DecimalString
        public let inTransitOut: DecimalString
        public let claimedUnverifiedHandovers: DecimalString
        public let pendingFloats: DecimalString

        enum CodingKeys: String, CodingKey {
            case currency, outstanding, staffMemberID = "staff_member_id", staffName = "staff_name"
            case inTransitOut = "in_transit_out", claimedUnverifiedHandovers = "claimed_unverified_handovers"
            case pendingFloats = "pending_floats"
        }
    }

    public struct Cash: Codable, Hashable, Sendable {
        public let custodians: [Custodian]
        public let transfersAwaitingAcknowledgement: [CountAmount]
        public let floatsAwaitingAcknowledgement: [CountAmount]
        public let remittancesAwaitingConfirmation: [CountAmount]
        public let partialRemittancesInWindow: Int
        /// Tenant-local daily remittance cut-off; nil = no cut-off.
        public let remittanceCutoffHour: Int?
        /// Custodians flagged today for unremitted cash past the cut-off; nil = no cut-off configured.
        public let remittancesOverdueToday: Int?

        enum CodingKeys: String, CodingKey {
            case remittanceCutoffHour = "remittance_cutoff_hour", remittancesOverdueToday = "remittances_overdue_today"
            case custodians, transfersAwaitingAcknowledgement = "transfers_awaiting_acknowledgement"
            case floatsAwaitingAcknowledgement = "floats_awaiting_acknowledgement"
            case remittancesAwaitingConfirmation = "remittances_awaiting_confirmation"
            case partialRemittancesInWindow = "partial_remittances_in_window"
        }
    }

    public struct Payments: Codable, Hashable, Sendable {
        public let awaitingConfirmation: [CountAmount]
        enum CodingKeys: String, CodingKey { case awaitingConfirmation = "awaiting_confirmation" }
    }

    public struct Investigations: Codable, Hashable, Sendable {
        public let open: Int
        public let inReview: Int
        enum CodingKeys: String, CodingKey { case open, inReview = "in_review" }
    }

    public struct Discrepancies: Codable, Hashable, Sendable {
        public let openVariances: [CountAmount]
        public let writeOffsProposed: Int
        public let syncConflictsUnresolved: Int
        enum CodingKeys: String, CodingKey {
            case openVariances = "open_variances", writeOffsProposed = "write_offs_proposed"
            case syncConflictsUnresolved = "sync_conflicts_unresolved"
        }
    }

    public struct Attempts: Codable, Hashable, Sendable {
        public let windowDays: Int
        public let permissionDenied: Int
        public let segregationOfDuties: Int
        enum CodingKeys: String, CodingKey {
            case windowDays = "window_days", permissionDenied = "permission_denied", segregationOfDuties = "segregation_of_duties"
        }
    }

    public struct Approvals: Codable, Hashable, Sendable {
        public let approvalRequests: Int
        public let cashRetentions: Int
        public let custodyAdjustments: Int
        public let writeOffs: Int
        public let paymentsToVerify: Int
        public let remittancesToVerify: Int
        public let total: Int
        enum CodingKeys: String, CodingKey {
            case total, approvalRequests = "approval_requests", cashRetentions = "cash_retentions"
            case custodyAdjustments = "custody_adjustments", writeOffs = "write_offs", paymentsToVerify = "payments_to_verify"
            case remittancesToVerify = "remittances_to_verify"
        }
    }

    enum CodingKeys: String, CodingKey {
        case cash, payments, discrepancies, investigations, asOf = "as_of", policyVersion = "policy_version"
        case hiddenTiles = "hidden_tiles", unavailableTiles = "unavailable_tiles", customerHours = "customer_hours"
        case disabledCapabilities = "disabled_capabilities"
        case hoursAwaitingActivation = "hours_awaiting_activation", engineHours = "engine_hours"
        case unexplainedHours = "unexplained_hours", missingDailyReports = "missing_daily_reports"
        case unauthorizedAttempts = "unauthorized_attempts", outstandingApprovals = "outstanding_approvals"
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        asOf = try c.decode(Date.self, forKey: .asOf)
        policyVersion = try c.decode(String.self, forKey: .policyVersion)
        hiddenTiles = try c.decodeIfPresent([String].self, forKey: .hiddenTiles) ?? []
        unavailableTiles = try c.decodeIfPresent([String].self, forKey: .unavailableTiles) ?? []
        disabledCapabilities = (try? c.decodeIfPresent([String].self, forKey: .disabledCapabilities)) ?? []
        func open(_ key: CodingKeys) -> JSONValue? {
            let value = try? c.decodeIfPresent(JSONValue.self, forKey: key)
            return value == .null ? nil : value ?? nil
        }
        customerHours = open(.customerHours)
        hoursAwaitingActivation = open(.hoursAwaitingActivation)
        engineHours = open(.engineHours)
        unexplainedHours = open(.unexplainedHours)
        missingDailyReports = open(.missingDailyReports)
        // A tile that does not decode is left out rather than failing the whole dashboard.
        investigations = (try? c.decodeIfPresent(Investigations.self, forKey: .investigations)) ?? nil
        cash = (try? c.decodeIfPresent(Cash.self, forKey: .cash)) ?? nil
        payments = (try? c.decodeIfPresent(Payments.self, forKey: .payments)) ?? nil
        discrepancies = (try? c.decodeIfPresent(Discrepancies.self, forKey: .discrepancies)) ?? nil
        unauthorizedAttempts = (try? c.decodeIfPresent(Attempts.self, forKey: .unauthorizedAttempts)) ?? nil
        outstandingApprovals = (try? c.decodeIfPresent(Approvals.self, forKey: .outstandingApprovals)) ?? nil
    }
}

/// One dashboard tile as rows (title + value), the same on both apps.
public struct DashboardTile: Hashable, Sendable, Identifiable {
    public struct Row: Hashable, Sendable {
        public let label: String
        public let value: String
        public let detail: String?

        public init(_ label: String, _ value: String, detail: String? = nil) {
            self.label = label
            self.value = value
            self.detail = detail
        }
    }

    /// A further list the tile opens (label + screen), after the tile's own link.
    public struct Link: Hashable, Sendable {
        public let label: String
        public let route: OwnerRoute
    }

    public let id: String
    public let title: String
    public let rows: [Row]
    /// Where the tile leads (filtered list), when the app has that screen.
    public let route: OwnerRoute?
    /// A note under the tile (e.g. "Cut-off 07:00").
    public var footer: String? = nil
    /// Further lists the tile opens, e.g. today's overdue remittances from the cash tile (Android `moreLinks`).
    public var moreLinks: [Link] = []
}

public enum AccountabilityDashboard {
    typealias T = OwnerAccountabilityTexts

    static func counts(_ items: [AccountabilitySummaryDTO.CountAmount]) -> String {
        items.isEmpty ? T.dashNone : items.map { T.dashCount($0.count, OwnerFormat.money($0.amount, currency: $0.currency)) }
            .joined(separator: "\n")
    }

    static func hours(_ value: JSONValue?) -> String {
        guard let text = value?.stringValue, let decimal = DecimalString(string: text) else { return "—" }
        return OwnerFormat.hours(decimal)
    }

    /// The summary as tiles in the dashboard order (hidden or unavailable tiles are simply absent). Capabilities
    /// switched off in `/me` (`disabled`) or in the summary's own `disabled_capabilities` leave out their tiles and
    /// rows (follow-up F1, as Android): CUSTOMER_HOURS the customer-hours tiles, ENGINE_HOURS the engine-hour tiles,
    /// CASH_CUSTODY the custody additions (transfers, floats to acknowledge, partial and overdue remittances,
    /// retentions, adjustments, write-offs, variances); the cash basics stay.
    public static func tiles(_ s: AccountabilitySummaryDTO, disabled: Set<String> = [],
                             timeZone: TimeZone = .current) -> [DashboardTile] {
        let off = disabled.union(s.disabledCapabilities)
        let customerHours = !off.contains(TenantCapability.customerHours)
        let engineOn = !off.contains(TenantCapability.engineHours)
        let cashOn = !off.contains(TenantCapability.cashCustody)
        var out: [DashboardTile] = []
        if let a = s.outstandingApprovals {
            var rows: [DashboardTile.Row] = [
                .init(T.dashTotal, "\(a.total)"),
                .init(T.dashApprovalRequests, "\(a.approvalRequests)"), .init(T.dashPaymentsToVerify, "\(a.paymentsToVerify)"),
                .init(T.dashRemittancesToVerify, "\(a.remittancesToVerify)"),
            ]
            if cashOn {
                rows += [.init(T.dashCashRetentions, "\(a.cashRetentions)"), .init(T.dashCustodyAdjustments, "\(a.custodyAdjustments)"),
                         .init(T.dashWriteOffs, "\(a.writeOffs)")]
            }
            out.append(DashboardTile(id: "outstanding_approvals", title: T.dashApprovals, rows: rows, route: .approvals))
        }
        if let c = s.cash {
            // CASH_CUSTODY off: only the cash basics (remittances awaiting confirmation, what each custodian holds).
            var rows: [DashboardTile.Row] = cashOn ? [
                .init(T.dashTransfersAwaiting, counts(c.transfersAwaitingAcknowledgement)),
                .init(T.dashFloatsAwaiting, counts(c.floatsAwaitingAcknowledgement)),
            ] : []
            rows.append(.init(T.dashRemittancesAwaiting, counts(c.remittancesAwaitingConfirmation)))
            if cashOn { rows.append(.init(T.dashPartialRemittances, "\(c.partialRemittancesInWindow)")) }
            // Remittance cut-off (null = the tenant has none): today's overdue count, the cut-off under the tile, and a
            // link to the flagged custodians (as Android).
            let overdueToday = cashOn ? c.remittancesOverdueToday : nil
            if let overdue = overdueToday { rows.append(.init(T.dashRemittancesOverdue, "\(overdue)")) }
            for custodian in c.custodians {
                let outstanding = T.dashCustodianLine(OwnerFormat.money(custodian.outstanding, currency: custodian.currency))
                let transit = custodian.inTransitOut.value == 0 ? nil
                    : T.dashInTransit(OwnerFormat.money(custodian.inTransitOut, currency: custodian.currency))
                // On one line, as Android: "TZS 150,000.00 outstanding · TZS 20,000.00 in transit".
                rows.append(.init(custodian.staffName, [outstanding, transit].compactMap { $0 }.joined(separator: " · ")))
            }
            let overdue = overdueToday != nil
            out.append(DashboardTile(id: "cash", title: T.dashCash, rows: rows, route: .cash,
                                     footer: overdue ? c.remittanceCutoffHour.map(T.dashCutoff) : nil,
                                     moreLinks: overdue ? [.init(label: T.dashRemittancesOverdue, route: .overdueRemittances)] : []))
        }
        if let p = s.payments {
            out.append(DashboardTile(id: "payments", title: T.dashPayments, rows: [.init(T.dashPayments, counts(p.awaitingConfirmation))],
                                     route: nil))
        }
        if let d = s.discrepancies {
            let custody: [DashboardTile.Row] = cashOn ? [
                .init(T.dashOpenVariances, counts(d.openVariances)), .init(T.dashWriteOffsProposed, "\(d.writeOffsProposed)"),
            ] : []
            out.append(DashboardTile(id: "discrepancies", title: T.dashDiscrepancies,
                                     rows: custody + [.init(T.dashSyncConflicts, "\(d.syncConflictsUnresolved)")], route: .approvals))
        }
        if let i = s.investigations {
            out.append(DashboardTile(id: "investigations", title: T.dashInvestigations,
                                     rows: [.init(T.dashOpen, "\(i.open)"), .init(T.dashInReview, "\(i.inReview)")],
                                     route: .investigations))
        }
        if let a = s.unauthorizedAttempts {
            out.append(DashboardTile(id: "unauthorized_attempts", title: T.dashAttempts, rows: [
                .init(T.dashPermissionDenied, "\(a.permissionDenied)"), .init(T.dashSod, "\(a.segregationOfDuties)"),
            ], route: nil, footer: T.dashWindow(a.windowDays)))
        }
        if customerHours, let h = s.customerHours {
            var rows: [DashboardTile.Row] = [
                .init(T.dashHoursActivated, hours(h["activated"])), .init(T.dashHoursConsumed, hours(h["consumed"])),
                .init(T.dashHoursRemaining, hours(h["remaining"])), .init(T.dashHoursAwaiting, hours(h["awaiting_activation"])),
                .init(T.dashHoursExpired, hours(h["expired"])),
            ]
            if let overruns = h["open_overruns"]?.intValue { rows.append(.init(T.dashOpenOverruns, "\(overruns)")) }
            out.append(DashboardTile(id: "customer_hours", title: T.dashCustomerHours, rows: rows, route: nil))
        }
        if customerHours, let h = s.hoursAwaitingActivation {
            out.append(DashboardTile(id: "hours_awaiting_activation", title: T.dashHoursAwaitingTile, rows: [
                .init(T.dashHoursAwaiting, hours(h["hours"])),
                .init(T.dashPurchasesAwaitingPayment, "\(h["purchases_awaiting_payment"]?.intValue ?? 0)"),
                .init(T.dashPurchasesPartlyActive, "\(h["purchases_partly_active"]?.intValue ?? 0)"),
            ], route: nil))
        }
        if engineOn, let e = s.engineHours {
            var rows: [DashboardTile.Row] = [.init(T.dashMachines, "\(e["machines"]?.intValue ?? 0)")]
            if case let .object(byStatus)? = e["by_status"] {
                for key in ["NO_BASELINE", "RECONCILED", "PENDING_REVIEW", "UNEXPLAINED"] + byStatus.keys.sorted()
                    where byStatus[key] != nil && !rows.contains(where: { $0.label == T.engineStatus(key) }) {
                    rows.append(.init(T.engineStatus(key), "\(byStatus[key]?.intValue ?? 0)"))
                }
            }
            out.append(DashboardTile(id: "engine_hours", title: T.dashEngineHours, rows: rows, route: nil))
        }
        if engineOn, let u = s.unexplainedHours {
            var rows: [DashboardTile.Row] = [.init(T.dashMachines, "\(u["machines"]?.intValue ?? 0)"),
                                             .init(T.fieldHours, hours(u["hours"]))]
            if case let .array(items)? = u["items"] {
                for item in items {
                    let line = T.dashUnexplainedLine(hours: item["unexplained_hours"]?.stringValue ?? "0",
                                                     days: item["oldest_open_item_days"]?.intValue ?? 0)
                    rows.append(.init(item["machine_code"]?.stringValue ?? "—", line))
                }
            }
            out.append(DashboardTile(id: "unexplained_hours", title: T.dashUnexplained, rows: rows, route: .exceptions(jobID: nil)))
        }
        if engineOn, let m = s.missingDailyReports {
            var rows: [DashboardTile.Row] = [.init(T.dashMissingReports, "\(m["count"]?.intValue ?? 0)")]
            if case let .array(items)? = m["items"] {
                for item in items {
                    rows.append(.init(T.dashMissingLine(machine: item["machine_code"]?.stringValue ?? "—",
                                                        day: item["day"]?.stringValue ?? ""), ""))
                }
            }
            out.append(DashboardTile(id: "missing_daily_reports", title: T.dashMissingReports, rows: rows, route: nil))
        }
        return out
    }

    /// "Policy v3 · As of 22 Oct 2026, 14:05".
    public static func footer(_ s: AccountabilitySummaryDTO, timeZone: TimeZone = .current) -> String {
        T.dashFooter(version: s.policyVersion, time: OwnerFormat.stamp(s.asOf, timeZone: timeZone))
    }

    /// Some tiles hidden by the tenant's settings.
    public static func showsHiddenNote(_ s: AccountabilitySummaryDTO) -> Bool { !s.hiddenTiles.isEmpty }
}
