import AssetaModel
import AssetaStore // UUID.lowercased
import Foundation

/// Where a figure, employee record or lookup match opens (strings doc "Where a figure opens", same table on both apps):
/// an app screen when one exists, shows those records and the role may open it; else the web, for safe `/tenant/` paths.
public enum FigureTarget: Hashable, Sendable {
    case screen(OwnerRoute)
    case web(String)
}

public enum ManagementRoutes {
    /// Web path for `route`, only when it starts `/tenant/` (never absolute, `//` or containing `\`).
    static func webPath(_ route: String) -> String? {
        guard route.hasPrefix("/tenant/"), !route.contains("//"), !route.contains("\\") else { return nil }
        return route
    }

    private static let pendingStatuses: Set<String?> = [nil, "PENDING", "PROPOSED"]

    /// The target of a server `route`; nil when it is empty or may not be opened on the web either.
    public static func target(_ route: String?, features: OwnerFeatures) -> FigureTarget? {
        guard let route, !route.isEmpty else { return nil }
        if let screen = screen(route, features: features), features.allows(screen), features.route(screen) == screen { return .screen(screen) }
        return webPath(route).map(FigureTarget.web)
    }

    /// Excavator rows use the machine: daily sheet, else machine, else web on the route.
    public static func excavatorTarget(machineID: UUID, route: String, features: OwnerFeatures) -> FigureTarget? {
        for screen in [OwnerRoute.dailySheet(machineID), .machine(machineID)] where features.allows(screen) && features.route(screen) == screen {
            return .screen(screen)
        }
        return webPath(route).map(FigureTarget.web)
    }

    static func screen(_ route: String, features: OwnerFeatures) -> OwnerRoute? {
        let pieces = route.split(separator: "?", maxSplits: 1).map(String.init)
        let query = pieces.count > 1 ? parseQuery(pieces[1]) : [:]
        let parts = pieces.first.map { $0.split(separator: "/").map(String.init) } ?? []
        guard parts.first == "tenant", parts.count >= 2 else { return nil }
        let status = query["status"]
        let rest = Array(parts.dropFirst())
        let hasID = rest.last.flatMap(UUID.init(uuidString:)) != nil

        // Record routes with an id open the record, like a notification deep link.
        if hasID, let record = DeepLinkParser.route(path: route), record.identifiesRecord { return record }

        switch rest[0] {
        case "staff":
            return DeepLinkParser.route(path: route)
        case "hours":
            if rest.count == 2, rest[1] == "balances" {
                return query["customer_id"].flatMap(UUID.init(uuidString:)).map { .hoursStatement(customer: $0, name: nil) } ?? .customerHours
            }
            if rest.count == 2, ["transfers", "cancellations", "credit", "discounts"].contains(rest[1]), status == "PENDING" || status == "PROPOSED" {
                return .approvals
            }
            return nil
        case "meter-corrections", "meter-baselines", "meter-resets", "non-revenue-approvals", "approvals":
            return rest.count == 1 && pendingStatuses.contains(status) ? .approvals : nil
        case "engine-hours":
            return rest == ["engine-hours", "classifications"] && pendingStatuses.contains(status) ? .approvals : nil
        case "work-allocations":
            return rest == ["work-allocations", "corrections"] && pendingStatuses.contains(status) ? .approvals : nil
        case "jobs":
            return rest.count == 1 && status == "PENDING_APPROVAL" ? .approvals : nil
        case "daily-reports":
            return rest.count == 1 && status == "SUBMITTED" ? .approvals : nil
        case "revenue-differences":
            return rest.count == 1 && (status == nil || status == "EXPLANATION_PROPOSED") ? .approvals : nil
        case "accountability":
            return rest == ["accountability", "pending-adjustments"] ? .approvals : nil
        case "exceptions":
            return rest.count == 1 ? .exceptions(jobID: nil) : nil
        case "cases":
            return rest.count == 1 ? .investigations : nil
        case "finance":
            return finance(Array(rest.dropFirst()), query: query, status: status)
        default:
            return nil
        }
    }

    private static func finance(_ rest: [String], query: [String: String], status: String?) -> OwnerRoute? {
        if rest == ["adjustments", "requests"], pendingStatuses.contains(status) { return .approvals }
        guard rest.first == "cash" else { return nil }
        let cash = Array(rest.dropFirst())
        if cash.isEmpty { return query.isEmpty ? .cash : nil }
        guard cash.count == 1 else { return nil }
        switch cash[0] {
        case "remittance-overdue": return .overdueRemittances
        case "retentions", "adjustments": return status == "PENDING" ? .approvals : nil
        case "variances": return status == "WRITE_OFF_PROPOSED" || status == "CLOSURE_PROPOSED" ? .approvals : nil
        case "remittances": return status == "CLAIMED" || query["partial_reason_pending"] == "true" ? .approvals : nil
        default: return nil
        }
    }

    private static func parseQuery(_ text: String) -> [String: String] {
        var out: [String: String] = [:]
        for pair in text.split(separator: "&") {
            let kv = pair.split(separator: "=", maxSplits: 1).map(String.init)
            if kv.count == 2 { out[kv[0]] = kv[1].removingPercentEncoding ?? kv[1] }
        }
        return out
    }
}
